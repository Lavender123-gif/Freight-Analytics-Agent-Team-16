"""Metrics used by the tuning rule (docs/autorun/tuning_log.zh.md) for dev runs and mock runs.

Usage: uv run python scratch/autorun/compare_rounds.py <dev_run_id>... --mock <mock_run_id>...
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_run import load, rec_cost  # noqa: E402
from mock_eval import score  # noqa: E402


def dev_metrics(rid: str) -> dict:
    rs = load(rid)
    has = lambda r, c: any(f["code"] == c for f in r["judgment"]["flags"])  # noqa: E731
    return {
        "run": rid, "n": len(rs),
        "first_mismatch": sum(r["facts"]["first_check"] == "MISMATCH" for r in rs),
        "final_mismatch": sum(r["facts"]["delta_consistency"].startswith("MISMATCH") for r in rs),
        "match_after_revision": sum(r["facts"]["delta_consistency"] == "MATCH_AFTER_REVISION" for r in rs),
        "total_mismatch_flag": sum(has(r, "CLAIM.RECON.TOTAL_MISMATCH") for r in rs),
        "uncertainty_flag": sum(has(r, "RUN.AGENT.UNCERTAINTY_REPORTED") for r in rs),
        "failed_or_none": sum(r["facts"]["parse_status"] != "PASSED_CHECKS" for r in rs),
        "recommendation": dict(Counter(r["judgment"]["recommendation"] for r in rs)),
        "cost_per_record": round(sum(rec_cost(r) for r in rs) / len(rs), 5),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dev", nargs="*")
    ap.add_argument("--mock", nargs="*", default=[])
    a = ap.parse_args()
    for rid in a.dev:
        print(json.dumps(dev_metrics(rid)))
    for rid in a.mock:
        s = score(rid)
        print(json.dumps({"run": rid, **{k: s[k] for k in ("claim_total_correct", "first_claim_total_correct", "recommendation_agrees",
                                                            "first_mismatch", "injection_reported_by_model")},
                          "weak": s["modes_with_wrong_totals"]}, ensure_ascii=False))
