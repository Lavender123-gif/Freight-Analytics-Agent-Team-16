"""Task 23b section 2 item 5: replay the local-scope sign check (audit F-01 recheck) on stored readings. No model call.

For every stored final reading: rerun checks.check_submission with today's code on the stored redacted text and list
- refused: NUM.JUDGMENT.CREDIT_UNSUPPORTED (a stored reading cannot be asked again, so each one would go to a person);
- minus: NUM.JUDGMENT.CREDIT_MINUS_UNCLEAR (adjacent minus, no local credit word, no parentheses);
- mark: NUM.JUDGMENT.CREDIT_MARK_NOT_CREDIT (read positive, credit word in the local scope or parentheses).
"newly to a person" = the stored recommendation was PASSED_CHECKS. Rows hold ids and amounts, no text.
Per-reading rows: data/interim/eval/t23b/credit_replay.json (git-ignored). Prints the same rows.
Usage: uv run python scratch/eval/t23b_credit_replay.py
"""

from __future__ import annotations

import json
from pathlib import Path

from freight_lineitems.checks import Ctx, check_submission
from freight_lineitems.config import RUNS_DIR
from freight_lineitems.numbers import parse
from freight_lineitems.schemas import Submission

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "interim" / "eval" / "t23b"
RUNS = {"dev_t19": "20261115-170854-devFullT19routed-055d", "mock_r3_t19": "20261115-170854-mockR3T19routed-4079",
        "mock_r4_new_t20": "20261115-192714-mockR4newT20-ab8a"}
CODES = {"NUM.JUDGMENT.CREDIT_UNSUPPORTED": "refused", "NUM.JUDGMENT.CREDIT_MINUS_UNCLEAR": "minus",
         "NUM.JUDGMENT.CREDIT_MARK_NOT_CREDIT": "mark"}


def replay(run: str) -> dict:
    out = {"readings": 0, "parse_mismatch": 0, "schema_invalid": 0, "credit_numbers": 0, "refused": [], "minus": [], "mark": []}
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
            out["schema_invalid"] += 1
            continue
        out["credit_numbers"] += sum(1 for j in sub.numbers if j.is_credit)
        errs, rec, _ = check_submission(ctx, sub)
        before = r["judgment"]["recommendation"]
        judged = {j.id: j for j in list(sub.numbers) + [u.as_number for u in sub.unrecognized_reads]}
        for x in list(errs) + list(rec):
            if x.code in CODES:
                i = x.evidence["id"]
                j = judged.get(i)
                out[CODES[x.code]].append({"record_id": r["record_id"], "id": i, "raw": x.evidence.get("raw"),
                                           "kind": j.kind.value if j else None, "status": j.status.value if j else None,
                                           "is_credit": bool(j and j.is_credit),
                                           "credit_words": x.evidence.get("credit_words"),
                                           "parentheses": x.evidence.get("parentheses"),
                                           "recommendation_before": before})
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = {name: replay(run) | {"run": run} for name, run in RUNS.items()}
    (OUT / "credit_replay.json").write_text(json.dumps(res, indent=1))
    for name, o in res.items():
        recs = {k: {x["record_id"] for x in o[k]} for k in ("refused", "minus", "mark")}
        newly = {x["record_id"] for k in ("refused", "minus", "mark") for x in o[k] if x["recommendation_before"] == "PASSED_CHECKS"}
        print(f"{name}: readings {o['readings']}, parse mismatches {o['parse_mismatch']}, schema-invalid {o['schema_invalid']}, "
              f"numbers read as credit {o['credit_numbers']}; refused {len(o['refused'])} numbers / {len(recs['refused'])} readings, "
              f"minus {len(o['minus'])}/{len(recs['minus'])}, mark {len(o['mark'])}/{len(recs['mark'])}; "
              f"readings newly to a person (were PASSED_CHECKS) {len(newly)}")
        for k in ("refused", "minus", "mark"):
            for x in o[k]:
                print(f"  {k}", x)


if __name__ == "__main__":
    main()
