"""Task 23 section 1 item 4: replay the is_credit check (audit F-01) on stored readings. No model call.

For every stored final reading: rerun checks.check_submission with today's code on the stored redacted text and count
- rule 1: NUM.JUDGMENT.CREDIT_UNSUPPORTED (is_credit true, no credit word / parentheses / adjacent minus). A stored
  reading cannot be asked again, so each one counts as "sent to a person";
- rule 2: NUM.JUDGMENT.CREDIT_MARK_NOT_CREDIT (counted item read as positive, credit word in its evidence or in
  parentheses). Also counted without the "counted item" restriction, for comparison.
Per-reading rows: data/interim/eval/t23/credit_replay.json (git-ignored; holds no text). Prints the same rows.
Usage: uv run python scratch/eval/t23_credit_replay.py
"""

from __future__ import annotations

import json
from pathlib import Path

from freight_lineitems.checks import Ctx, check_submission, credit_marks, credit_words_in
from freight_lineitems.config import RUNS_DIR
from freight_lineitems.numbers import parse
from freight_lineitems.schemas import Submission

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "interim" / "eval" / "t23"
RUNS = {"dev_t19": "20261115-170854-devFullT19routed-055d", "mock_r3_t19": "20261115-170854-mockR3T19routed-4079",
        "mock_r4_new_t20": "20261115-192714-mockR4newT20-ab8a"}


def replay(run: str) -> dict:
    out = {"readings": 0, "rule1": [], "rule2": [], "rule2_any_number": 0, "parse_mismatch": 0}
    for line in (RUNS_DIR / run / "records.jsonl").open():
        r = json.loads(line)
        f = r["facts"]
        reading = f.get("reading")
        if not reading:
            continue
        out["readings"] += 1
        p = parse(f["text_redacted"])
        if [n.raw for n in p.numbers] != [n["raw"] for n in f["number_table"]["numbers"]]:
            out["parse_mismatch"] += 1
        ctx = Ctx(record_id=r["record_id"], text=f["text_redacted"], parse=p, origin_state=f["source"]["origin_state"],
                  destination_state=f["source"]["destination_state"], event_date=None)
        try:
            sub = Submission.model_validate(reading)
        except Exception:  # noqa: BLE001 - schema-invalid stored attempt; already failed before task 23
            continue
        errs, rec, _ = check_submission(ctx, sub)
        status = (r["process"].get("final") or {}).get("status", f.get("parse_status"))
        toks = {n.id: n for n in p.numbers}
        for e in errs:
            if e.code == "NUM.JUDGMENT.CREDIT_UNSUPPORTED":
                n = toks.get(e.evidence["id"])
                out["rule1"].append({"record_id": r["record_id"], "id": e.evidence["id"], "raw": n.raw if n else None,
                                     "stored_status": status, "recommendation": r["judgment"]["recommendation"]})
        for d in rec:
            if d.code == "NUM.JUDGMENT.CREDIT_MARK_NOT_CREDIT":
                out["rule2"].append({"record_id": r["record_id"], "id": d.evidence["id"], "raw": d.evidence["raw"],
                                     "credit_words": d.evidence["credit_words"], "parentheses": d.evidence["parentheses"],
                                     "stored_status": status, "recommendation_before": r["judgment"]["recommendation"]})
        for j in sub.numbers:
            if not j.is_credit and j.id in toks and (credit_words_in(j.evidence_phrase) or
                                                     credit_marks(f["text_redacted"], toks[j.id].span)["parentheses"]):
                out["rule2_any_number"] += 1
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = {name: replay(run) | {"run": run} for name, run in RUNS.items()}
    (OUT / "credit_replay.json").write_text(json.dumps(res, indent=1))
    for name, o in res.items():
        newly = [x for x in o["rule2"] if x["recommendation_before"] == "PASSED_CHECKS"]
        print(f"{name}: readings {o['readings']}, parse mismatches {o['parse_mismatch']}, rule 1 {len(o['rule1'])}, "
              f"rule 2 {len(o['rule2'])} (of which previously PASSED_CHECKS {len(newly)}), rule 2 without the "
              f"counted-item restriction {o['rule2_any_number']}")
        for x in o["rule1"]:
            print("  rule1", x)
        for x in o["rule2"]:
            print("  rule2", x)


if __name__ == "__main__":
    main()
