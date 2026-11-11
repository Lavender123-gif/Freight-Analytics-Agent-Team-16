"""Run-to-run range of one version on the public mock (task 10 section 3.2). Aggregates only.
Usage: uv run python scratch/autorun/mock_variance.py <mock_run_id> <mock_run_id> ... [--json out]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analyze_run import load
from mock_eval import score
from rerule import dist, current
from freight_lineitems.records import MOCK_DIR

args = [a for a in sys.argv[1:] if not a.startswith("--")]
out_path = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
runs = args if not out_path else [a for a in args if a != out_path]
rows = []
gt = [json.loads(x) for x in (MOCK_DIR / "ground_truth.jsonl").read_text().splitlines()]
for rid in runs:
    s = score(rid)
    cc = next((m for m in s["modes_with_wrong_totals"] if m.startswith("control_clean")), "control_clean 60/60")
    rs = load(rid)
    rows.append({"run": rid, "claim_total_correct": s["claim_total_correct"], "first_claim_total_correct": s["first_claim_total_correct"],
                 "first_mismatch": s["first_mismatch"], "control_clean": cc, "injection_reported_by_model": s["injection_reported_by_model"],
                 "uncertainty_records": sum(any(f["code"] == "RUN.AGENT.UNCERTAINTY_REPORTED" for f in r["judgment"]["flags"]) for r in rs),
                 "failed_or_none": sum(r["facts"]["parse_status"] != "PASSED_CHECKS" for r in rs),
                 **dist(rid)})
rng = {k: [min(r[k] for r in rows), max(r[k] for r in rows), max(r[k] for r in rows) - min(r[k] for r in rows)]
       for k in rows[0] if isinstance(rows[0][k], int)}
# per-record stability of the recommendation across the runs
recs = [{r["record_id"]: current(r)["recommendation"] for r in load(rid)} for rid in runs]
same = sum(len({d[k] for d in recs}) == 1 for k in recs[0])
out = {"runs": rows, "range_min_max_width": rng, "records_same_recommendation_all_runs": [same, len(recs[0])]}
print(json.dumps(out, indent=1, ensure_ascii=False))
if out_path:
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False))
