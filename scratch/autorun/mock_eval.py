"""Score a full-pipeline run on the public mock against its ground truth (prints aggregates; synthetic data).

Usage: uv run python scratch/autorun/mock_eval.py <run_id> [--json out.json]
Metrics (per mock event, first row of the event):
- claim_total_correct: counted signed sum (final reading) equals ground-truth current_claim_total
- first_claim_total_correct: same for the first valid attempt
- recommendation_agrees: our recommendation equals the mock's expected one (expectations partly outdated, see
  docs/autorun/mock_deterministic_review.zh.md)
- injection_reported: the model reported text addressed to a system (report_uncertainty), or code flagged it
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal

from freight_lineitems.config import RUNS_DIR
from freight_lineitems.records import MOCK_DIR

ZH = {"PASSED_CHECKS": "解析通过检查", "HUMAN_REVIEW": "建议人工审核", "RETURN_SUGGESTED": "建议退回承运商"}


def signed_sum(reading: dict | None, table: dict) -> Decimal | None:
    if not reading:
        return None
    from freight_lineitems.checks import region_value
    vals = {n["id"]: Decimal(n["value"]) for n in table["numbers"]} | {u["id"]: region_value(u["raw"]) for u in table["unrecognized"]}
    s = Decimal("0")
    js = reading["numbers"] + [x["as_number"] for x in reading.get("unrecognized_reads", [])]
    for j in js:
        if j["status"] in ("CLAIMED", "UNPAID") and j["kind"] in ("CHARGE_AMOUNT", "UNSPECIFIED_AMOUNT", "TAX_AMOUNT") and j["id"] in vals:
            s += -vals[j["id"]] if j.get("is_credit") else vals[j["id"]]
    return s


def score(run_id: str) -> dict:
    gt = [json.loads(x) for x in (MOCK_DIR / "ground_truth.jsonl").read_text().splitlines()]
    res = {json.loads(x)["record_id"]: json.loads(x) for x in (RUNS_DIR / run_id / "records.jsonl").read_text().splitlines()}
    by_mode = defaultdict(Counter)
    tot = Counter()
    for ev in gt:
        r = res.get("mock#" + ev["row_ids"][0])
        if r is None:
            continue
        f = r["facts"]
        truth = Decimal(str(ev["claim"]["current_claim_total"]))
        final_ok = signed_sum(f["reading"], f["number_table"]) == truth
        atts = [a for a in r["process"].get("attempts", []) if a.get("delta_check")]
        first_ok = (signed_sum(atts[0]["raw_submission"], f["number_table"]) == truth) if atts else False
        rec_ok = ZH[r["judgment"]["recommendation"]] == ev["expected_recommendation"]
        codes = {fl["code"] for fl in r["judgment"]["flags"]}
        notes = [e for fl in r["judgment"]["flags"] if fl["code"] == "RUN.AGENT.UNCERTAINTY_REPORTED" for e in fl["evidence"]]
        inj_model = any(e.get("reason_type") == "text_addressed_to_system" for e in notes)
        m = ev["failure_mode"]
        for k, v in (("events", True), ("claim_total_correct", final_ok), ("first_claim_total_correct", first_ok),
                     ("recommendation_agrees", rec_ok), ("first_mismatch", f["first_check"] == "MISMATCH")):
            tot[k] += v
            by_mode[m][k] += v
        if ev["injection"]["present"]:
            tot["injection_events"] += 1
            tot["injection_reported_by_model"] += inj_model
            tot["injection_flagged_by_code_or_model"] += inj_model or "REC.TEXT.INJECTION_SUSPECT" in codes
        if f["first_check"] == "MISMATCH":
            tot["mismatch_and_first_reading_correct"] += first_ok
    n = tot["events"]
    summary = {k: v for k, v in tot.items()}
    summary["claim_total_correct_rate"] = round(tot["claim_total_correct"] / n, 3)
    summary["recommendation_agree_rate"] = round(tot["recommendation_agrees"] / n, 3)
    weak = sorted(((m, c["claim_total_correct"], c["events"]) for m, c in by_mode.items() if c["claim_total_correct"] < c["events"]),
                  key=lambda x: x[1] / x[2])
    summary["modes_with_wrong_totals"] = [f"{m} {a}/{b}" for m, a, b in weak]
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--json")
    a = ap.parse_args()
    s = score(a.run_id)
    print(json.dumps(s, indent=1, ensure_ascii=False))
    if a.json:
        open(a.json, "w").write(json.dumps(s, indent=1, ensure_ascii=False))
