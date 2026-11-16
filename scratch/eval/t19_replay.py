"""Task 19 step 1: replay stored readings through today's code and fingerprint every result, so a refactor that must
not change any output can be checked (run once before the change with --tag before, once after with --tag after,
then `diff before after`). No model call.

Per explanation: the mandatory-check errors, the reviewer diagnostics and the claim arithmetic of check_submission on
the stored final reading; reading_diagnostics; the recommendation recomputed from the stored record-level diagnostics
plus the recomputed reading-level ones; the db column counted_in_claim (db.write_run into a temporary SQLite file).
Per shipment: the roll-up (default change, line statuses, flags, recommendation).
Readings that predate a field added later validate with that field's default (schemas.Submission).

Usage: uv run python scratch/eval/t19_replay.py run --tag before
       uv run python scratch/eval/t19_replay.py diff before after
Per-record output: data/interim/eval/t19/ (git-ignored). Prints aggregates only.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "autorun")]
import compare_variants as cv  # noqa: E402

from freight_lineitems import db, duplicates  # noqa: E402
from freight_lineitems.checks import Ctx, check_submission  # noqa: E402
from freight_lineitems.config import RULES  # noqa: E402
from freight_lineitems.disposition import flags_from, recommend  # noqa: E402
from freight_lineitems.reading_checks import reading_diagnostics  # noqa: E402
from freight_lineitems.pipeline import shipments_of as rollup_results  # task 20: one shipment path  # noqa: E402
from freight_lineitems.schemas import Diagnostic, ParseResult, Submission  # noqa: E402

OUT = ROOT / "data" / "interim" / "eval" / "t19"
RUNS = {"dev": "devFullV12-5d09", "mock3": "mockR3V12-f0d3"}
READING_CODES = {"CLAIM.NOTHING_COUNTED", "ITEM.AMOUNT.LEADING_DOT_COUNTED", "CLAIM.EARLIER_CLAIM_MENTIONED"}


def _ctx(e: dict) -> Ctx:
    f, s = e["facts"], e["facts"]["source"]
    ed = s.get("event_date")
    ed = datetime.fromisoformat(ed) if isinstance(ed, str) and ed not in ("", "None") else None
    return Ctx(record_id=e["record_id"], text=f["text_redacted"], parse=ParseResult.model_validate(f["number_table"]),
               origin_state=s.get("origin_state"), destination_state=s.get("destination_state"), event_date=ed)


def fingerprint(run: str) -> dict:
    ex = cv.explanations(run)
    recs = cv.records_for(ex[0]["facts"]["source"]["source"])
    per: dict[str, dict] = {}
    for e in ex:
        f = e["facts"]
        group = [recs[s["record_id"]] for s in f["source_rows"]]
        stored = [Diagnostic(**d) for d in e["judgment"]["diagnostics"]
                  if d["code"] != "SHIP.COPY.SAME_OR_NO_PK" and d["step"] != "4" and d["code"] not in READING_CODES]
        fp: dict = {"parse_status": f["parse_status"]}
        new: list[Diagnostic] = []
        reading = f.get("reading")
        if reading and f["parse_status"] == "PASSED_CHECKS":
            sub = Submission.model_validate(reading)
            errs, rec, claim = check_submission(_ctx(e), sub)
            fp["errors"] = sorted(x.code + "@" + x.path for x in errs)
            fp["rec"] = sorted(d.code + "@" + d.path for d in rec)
            fp["claim"] = None if claim is None else {"counted_ids": sorted(claim.counted_ids),
                                                      "signed_sum": str(claim.signed_sum),
                                                      "expected_tax": str(claim.expected_tax)}
            new = list(rec) + reading_diagnostics(f["number_table"], reading)
            fp["reading_diags"] = sorted(d.code for d in reading_diagnostics(f["number_table"], reading))
        else:
            new = [Diagnostic(**d) for d in e["judgment"]["diagnostics"] if d["step"] == "4"]
        diags = stored + new + duplicates.copy_diagnostics(group)
        fl = flags_from(diags)
        e["judgment"] = {"flags": fl, **recommend(fl), "diagnostics": [d.model_dump() for d in diags]}
        e["facts"] |= duplicates.source_rows(group)
        fp["recommendation"] = e["judgment"]["recommendation"]
        fp["flags"] = sorted(x["code"] for x in fl)
        per[e["record_id"]] = fp
    # db column counted_in_claim
    with tempfile.TemporaryDirectory() as td:
        con = db.connect(Path(td) / "r.sqlite")
        rows = [r for e in ex for r in (recs[s["record_id"]] for s in e["facts"]["source_rows"])]
        db.write_run(con, "replay", "replay", rows, ex, {"model": "replay"}, RULES)
        q = """SELECT pr.dispute_id, nr.token_id, nr.counted_in_claim FROM number_reading nr
               JOIN parse_attempt pa ON pa.attempt_id = nr.attempt_id JOIN parse_run pr ON pr.parse_run_id = pa.parse_run_id
               WHERE pr.final_attempt_id = pa.attempt_id"""
        con.row_factory = sqlite3.Row
        for r in con.execute(q):
            per.setdefault(r["dispute_id"], {}).setdefault("db_counted", {})[r["token_id"]] = bool(r["counted_in_claim"])
        con.close()
    ships = {}
    for s in rollup_results(ex):
        ships[s["shipment_key"]] = {"default_change": s["default_change"], "recommendation": s["recommendation"],
                                    "flags": sorted(x["code"] for x in s["flags"]),
                                    "lines": sorted((ln["line_id"], ln["status"], ln["amount"]) for ln in s["lines"])}
    return {"explanations": per, "shipments": ships}


def cmd_run(tag: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = {k: fingerprint(r) for k, r in RUNS.items()}
    (OUT / f"replay_{tag}.json").write_text(json.dumps(res, indent=0, sort_keys=True, default=str))
    for k, v in res.items():
        print(k, "explanations", len(v["explanations"]), "shipments", len(v["shipments"]),
              "sent", sum(1 for x in v["explanations"].values() if x["recommendation"] != "PASSED_CHECKS"))


def cmd_diff(a: str, b: str) -> None:
    A = json.loads((OUT / f"replay_{a}.json").read_text())
    B = json.loads((OUT / f"replay_{b}.json").read_text())
    report = {}
    for k in RUNS:
        diffs = {"explanations": {}, "shipments": {}}
        for part in ("explanations", "shipments"):
            for key in sorted(set(A[k][part]) | set(B[k][part])):
                x, y = A[k][part].get(key), B[k][part].get(key)
                if x != y:
                    fields = sorted(f for f in set(x or {}) | set(y or {}) if (x or {}).get(f) != (y or {}).get(f))
                    diffs[part][key] = {f: {"before": (x or {}).get(f), "after": (y or {}).get(f)} for f in fields}
        report[k] = diffs
        by_field: dict[str, int] = {}
        for part in ("explanations", "shipments"):
            for d in diffs[part].values():
                for f in d:
                    by_field[f"{part}.{f}"] = by_field.get(f"{part}.{f}", 0) + 1
        print(k, "changed explanations", len(diffs["explanations"]), "changed shipments", len(diffs["shipments"]), by_field)
    (OUT / f"replay_diff_{a}_{b}.json").write_text(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--tag", required=True)
    d = sp.add_parser("diff")
    d.add_argument("a")
    d.add_argument("b")
    a = ap.parse_args()
    cmd_run(a.tag) if a.cmd == "run" else cmd_diff(a.a, a.b)
