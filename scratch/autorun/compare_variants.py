"""Task 14 stage 2: metrics and the pre-stated adoption rule for the prompt variants v1.3a / v1.3b against v1.2.

Every run is put on the same footing first: one result per explanation (order copies merged; an old row-level run
takes its lowest row's reading), recommendations under the rules.yaml of the working tree (rules v1.2), Delta,
currency and DUP.* flags dropped. No model call.

Metrics per run:
  colours        passed / human / return over explanations
  other_amounts  counted amounts coded OTHER
  claim_correct  (mock only) events whose counted signed sum equals the ground truth current_claim_total, read from
                 the explanation that holds the event's first row; 'first' = first attempt that passed the checks
                 (for v1.2 runs that is the reading before any Delta feedback; for new runs it is the only one)
Root agreement between two runs: over every number either run counts, share counted by both with the same client root
(charge_map: the client name, or the parent for a sub-item or extension, or our generic entry for one-to-many).

Usage:
  uv run python scratch/autorun/compare_variants.py metrics <run>...
  uv run python scratch/autorun/compare_variants.py roots <run_a> <run_b>
  uv run python scratch/autorun/compare_variants.py gate --base A=<run> B2=<run> mock=<run> --variant A=<run> B2=<run> mock=<run> [--jake <run>]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scratch" / "rollup"))
import replay  # noqa: E402

from freight_lineitems import charge_map  # noqa: E402
from freight_lineitems.checks import region_value  # noqa: E402
from freight_lineitems.config import RUNS_DIR  # noqa: E402
from freight_lineitems.records import MOCK_DIR, load_dev, load_mock, load_mock_r3, load_mock_r4  # noqa: E402

COLOURS = ("PASSED_CHECKS", "HUMAN_REVIEW", "RETURN_SUGGESTED")
# pre-stated in docs/autorun/tuning_log.zh.md (task 14 stage 2), before any variant run
NOISE_CLAIM = 3                       # mock claim-correct, run-to-run width (task 10: 327-330)
NOISE_COLOUR = {   # as written in tuning_log.zh.md (task 14 stage 2): v1.2-rules widths of the three mock repeats; A and B2
    "mock": {"PASSED_CHECKS": 10, "HUMAN_REVIEW": 10, "RETURN_SUGGESTED": 1},   # scaled by explanation count (P-32)
    "A": {"PASSED_CHECKS": 3, "HUMAN_REVIEW": 3, "RETURN_SUGGESTED": 1},
    "B2": {"PASSED_CHECKS": 3, "HUMAN_REVIEW": 3, "RETURN_SUGGESTED": 1}}
_RECS: dict = {}


def records_for(source: str) -> dict:
    if source not in _RECS:
        _RECS[source] = {r.record_id: r for r in {"dev": load_dev, "mock": load_mock, "mock3": load_mock_r3,
                                                  "mock4": load_mock_r4}[source]()}
    return _RECS[source]


def explanations(run: str) -> list[dict]:
    run = replay.find_run(run)
    stored = [json.loads(x) for x in (RUNS_DIR / run / "records.jsonl").open()]
    if all("source_rows" in r["facts"] for r in stored) and not any(
            d["code"].startswith(replay.WITHDRAWN) for r in stored for d in r["judgment"]["diagnostics"]):
        return stored
    return replay.explanations_from_rows(stored, records_for(stored[0]["facts"]["source"]["source"]))


def counted(reading: dict | None, table: dict) -> dict[str, tuple[Decimal, tuple]]:
    """number id -> (signed amount, codes) for the counted money amounts of a reading."""
    if not reading:
        return {}
    vals = {n["id"]: Decimal(n["value"]) for n in table["numbers"]} | {u["id"]: region_value(u["raw"]) for u in table["unrecognized"]}
    js = list(reading["numbers"]) + [u["as_number"] | {"id": u["region_id"]} for u in reading.get("unrecognized_reads", [])]
    out = {}
    for j in js:
        if j["status"] in ("CLAIMED", "UNPAID") and j["kind"] in ("CHARGE_AMOUNT", "UNSPECIFIED_AMOUNT", "TAX_AMOUNT") and j["id"] in vals:
            out[j["id"]] = (-vals[j["id"]] if j.get("is_credit") else vals[j["id"]], tuple(sorted(j.get("charge_codes") or ())))
    return out


def first_passed(r: dict) -> dict | None:
    for a in r["process"].get("attempts", []):
        if a.get("checks_passed") or a.get("delta_check"):
            return a["raw_submission"]
    return None


def metrics(run: str) -> dict:
    ex = explanations(run)
    out = {"run": replay.find_run(run), "explanations": len(ex),
           "colours": {c: sum(r["judgment"]["recommendation"] == c for r in ex) for c in COLOURS},
           "other_amounts": sum("OTHER" in codes for r in ex for _, codes in counted(r["facts"]["reading"], r["facts"]["number_table"]).values()),
           "failed_or_none": sum(r["facts"]["parse_status"] != "PASSED_CHECKS" for r in ex),
           "uncertainty": sum(any(f["code"] == "RUN.AGENT.UNCERTAINTY_REPORTED" for f in r["judgment"]["flags"]) for r in ex)}
    if ex and ex[0]["facts"]["source"]["source"] == "mock":
        row_to = {s["record_id"]: r for r in ex for s in r["facts"]["source_rows"]}
        gt = [json.loads(x) for x in (MOCK_DIR / "ground_truth.jsonl").read_text().splitlines()]
        c = Counter()
        for ev in gt:
            r = row_to.get("mock#" + ev["row_ids"][0])
            if r is None:
                continue
            truth = Decimal(str(ev["claim"]["current_claim_total"]))
            t = r["facts"]["number_table"]
            c["events"] += 1
            c["final"] += sum(a for a, _ in counted(r["facts"]["reading"], t).values()) == truth if r["facts"]["reading"] else 0
            fp = first_passed(r)
            c["first"] += (sum(a for a, _ in counted(fp, t).values()) == truth) if fp else 0
        out["claim_correct"] = dict(c)
    return out


def root(codes: tuple) -> str:
    if not codes:
        return "(none)"
    rs = []
    for c in codes:
        e = charge_map.entry(c)
        rs.append(e["parent"] if e["relation"] in ("CHILD", "EXTENSION") else e["client_names"][0]
                  if e["relation"] in ("EXACT", "APPROX") else e["client_name"])
    return "+".join(sorted(set(rs)))


def roots(run_a: str, run_b: str) -> dict:
    a = {r["record_id"]: r for r in explanations(run_a)}
    b = {r["record_id"]: r for r in explanations(run_b)}
    n = same = only_one = diff_root = 0
    for rid in a.keys() & b.keys():
        ca = counted(a[rid]["facts"]["reading"], a[rid]["facts"]["number_table"])
        cb = counted(b[rid]["facts"]["reading"], b[rid]["facts"]["number_table"])
        for nid in ca.keys() | cb.keys():
            n += 1
            if nid in ca and nid in cb:
                if root(ca[nid][1]) == root(cb[nid][1]):
                    same += 1
                else:
                    diff_root += 1
            else:
                only_one += 1
    return {"runs": [replay.find_run(run_a), replay.find_run(run_b)], "explanations_in_both": len(a.keys() & b.keys()),
            "amounts": n, "same_root": same, "different_root": diff_root, "counted_in_one_only": only_one,
            "same_root_share": round(same / n, 4) if n else None}


def jake(run: str) -> dict:
    """The client's two examples rolled up on a run's readings (expectations from the git-ignored file)."""
    exp = json.loads((ROOT / "data" / "interim" / "tests" / "jake_examples.json").read_text())
    from freight_lineitems.pipeline import shipments_of as rollup_results  # task 20: one shipment path
    ships = {s["sap_bol"]: s for s in rollup_results(explanations(run))}
    res = {}
    for i, e in enumerate(exp["examples"], 1):
        s = ships.get(e["sap_bol"])
        res[f"example_{i}"] = bool(s) and Decimal(s["default_change"]) == Decimal(e["change"]) and Decimal(s["new_total"]) == Decimal(e["new_total"])
    return res


def gate(base: dict, var: dict, jake_run: str | None) -> dict:
    mb = {k: metrics(v) for k, v in base.items()}
    mv = {k: metrics(v) for k, v in var.items()}
    checks = {}
    cb, cv = mb["mock"]["claim_correct"]["first"], mv["mock"]["claim_correct"]["final"]
    checks["1_mock_claim_correct"] = {"base_first": cb, "variant": cv, "min": cb - NOISE_CLAIM, "pass": cv >= cb - NOISE_CLAIM}
    for k in ("A", "B2", "mock"):
        d = {c: mv[k]["colours"][c] - mb[k]["colours"][c] for c in COLOURS}
        checks[f"2_colours_{k}"] = {"base": mb[k]["colours"], "variant": mv[k]["colours"], "change": d,
                                    "limits": NOISE_COLOUR[k], "pass": all(abs(d[c]) <= NOISE_COLOUR[k][c] for c in COLOURS)}
    ob, ov = sum(mb[k]["other_amounts"] for k in mb), sum(mv[k]["other_amounts"] for k in mv)
    checks["3_other_amounts"] = {"base": ob, "variant": ov, "pass": ov <= ob}
    if jake_run:
        j = jake(jake_run)
        checks["4_client_examples"] = {**j, "pass": all(j.values())}
    else:
        checks["4_client_examples"] = {"pass": False, "note": "no run given"}
    roots_ = {k: roots(base[k], var[k]) for k in base}
    return {"checks": checks, "adopt": all(c["pass"] for c in checks.values()), "root_agreement": roots_,
            "metrics_base": mb, "metrics_variant": mv}


def kv(pairs: list[str]) -> dict:
    return dict(p.split("=", 1) for p in pairs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["metrics", "roots", "gate", "jake"])
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--base", nargs="*")
    ap.add_argument("--variant", nargs="*")
    ap.add_argument("--jake")
    a = ap.parse_args()
    if a.cmd == "metrics":
        for r in a.runs:
            print(json.dumps(metrics(r)))
    elif a.cmd == "roots":
        print(json.dumps(roots(*a.runs)))
    elif a.cmd == "jake":
        print(json.dumps(jake(a.runs[0])))
    else:
        print(json.dumps(gate(kv(a.base), kv(a.variant), a.jake), indent=1))
