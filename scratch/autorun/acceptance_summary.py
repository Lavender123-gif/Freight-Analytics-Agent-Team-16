"""Acceptance-package numbers (task 09 stage 5). Aggregates only; writes JSON to data/interim/autorun/acceptance/.

Run: uv run python scratch/autorun/acceptance_summary.py
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_run import load, rec_cost  # noqa: E402
from mock_eval import score  # noqa: E402

from freight_lineitems import budget  # noqa: E402
from freight_lineitems.config import ROOT  # noqa: E402
from freight_lineitems.records import load_dev  # noqa: E402
from freight_lineitems.sampling import style  # noqa: E402
from freight_lineitems.tools import _template, load_examples  # noqa: E402

RUNS = {"A": "20261110-184540-finA-d700", "B": "20261110-184723-finB2-4b6b", "mock": "20261110-184540-finMock-da71"}
STAGE1 = "20261110-171337-stage1-1cc1"
REPEATS = ["20261110-174720-rep1-bee6", "20261110-174817-rep2-238e", "20261110-174911-rep3-9d1e"]
OUT = ROOT / "data" / "interim" / "autorun" / "acceptance"
REC = ["PASSED_CHECKS", "HUMAN_REVIEW", "RETURN_SUGGESTED"]

# prototype rules-v0.1 roles, mapped onto today's codes (for requirement f)
OLD_POINTS = {"RUN.AGENT.UNCERTAINTY_REPORTED": 2, "NUM.JUDGMENT.SPACE_MERGED_IN_CLAIM": 2, "ITEM.CODE.OTHER": 2,
              "CLAIM.RECON.TOTAL_MISMATCH": 2, "ITEM.ARITH.RELATION_FAILS": 2, "CLAIM.DELTA.MATCH_AFTER_REVISION": 1,
              "ITEM.AMOUNT.UNNAMED": 2, "ITEM.CODE.COMBINED": 1, "NUM.PARSE.UNRECOGNIZED_REGION": 1,
              "ITEM.TAX.NO_AMOUNT": 1, "ITEM.TAX.NO_RULE": 2}
OLD_THRESHOLD = 3


def pct(c: Counter, n: int) -> dict:
    return {k: f"{c.get(k, 0)} ({c.get(k, 0) / n:.0%})" for k in REC}


def weighted(rs: list[dict], dev_strata: Counter) -> dict:
    """Recommendation shares re-weighted to the dev split's carrier x style frequencies."""
    samp = Counter((r["facts"]["source"]["carrier"], style(r["facts"]["text_redacted"])) for r in rs)
    w = Counter()
    for r in rs:
        k = (r["facts"]["source"]["carrier"], style(r["facts"]["text_redacted"]))
        w[r["judgment"]["recommendation"]] += dev_strata[k] / samp[k]
    tot = sum(w.values())
    covered = sum(dev_strata[k] for k in samp)
    return {**{k: f"{w[k] / tot:.0%}" for k in REC}, "dev_rows_in_covered_strata": f"{covered}/{sum(dev_strata.values())}"}


def counterfactual_scoring(r: dict) -> str:
    """Requirement f: the colour under the prototype's points scheme with today's flags (attention-tier only)."""
    att = [f["code"] for f in r["judgment"]["flags"] if f["severity"] == "attention"]
    ret = [f["code"] for f in r["judgment"]["flags"] if f["severity"] == "return"]
    alone = [c for c in att if c not in OLD_POINTS]
    pts = sum(OLD_POINTS[c] for c in att if c in OLD_POINTS) + sum(OLD_POINTS.get(c, 0) for c in ret)
    if alone or pts >= OLD_THRESHOLD:
        return "HUMAN_REVIEW"
    if [c for c in ret if c not in OLD_POINTS]:
        return "RETURN_SUGGESTED"
    return "PASSED_CHECKS" if not ret else "RETURN_SUGGESTED"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dev = load_dev()
    dev_strata = Counter((r.carrier, style(r.text_raw)) for r in dev)
    ex_templates = [_template(e["marked_text"]) for e in load_examples()]
    data = {k: load(v) for k, v in RUNS.items()}
    s = {"runs": RUNS, "columns": {}}
    for name, rs in data.items():
        n = len(rs)
        same_tpl = [r for r in rs if _template(r["facts"]["number_table"]["marked_text"]) in ex_templates]
        rest = [r for r in rs if r not in same_tpl]
        tools = Counter(b.get("name") for r in rs for c in r["process"]["transcript"]["calls"] for b in c["content"]
                        if b.get("type") == "tool_use")
        ttot = sum(tools.values())
        flags = Counter(f["code"] for r in rs for f in r["judgment"]["flags"])
        first_mm = [r for r in rs if r["facts"]["first_check"] == "MISMATCH"]
        expl = Counter()
        for r in first_mm:
            codes = {f["code"] for f in r["judgment"]["flags"]}
            if "CLAIM.DELTA.TOTAL_COUNTED_TWICE_PATTERN" in codes:
                expl["Delta = items + their stated total"] += 1
            elif "CLAIM.DELTA.DIFFERENCE_MATCHES_AMOUNTS" in codes:
                expl["gap equals one to three amounts in the text"] += 1
            else:
                expl["no code explanation"] += 1
        col = {
            "n": n,
            "recommendation_sample": pct(Counter(r["judgment"]["recommendation"] for r in rs), n),
            "first_check": dict(Counter(r["facts"]["first_check"] for r in rs)),
            "first_mismatch_rate": f"{len(first_mm) / n:.1%}",
            "final_mismatch_rate": f"{sum(r['facts']['delta_consistency'].startswith('MISMATCH') for r in rs) / n:.1%}",
            "final_consistency": dict(Counter(r["facts"]["delta_consistency"] for r in rs)),
            "first_mismatch_explained_by_code": dict(expl),
            "response_after_inconsistent": dict(Counter(a["response_type"] for r in rs for a in r["process"]["attempts"]
                                                        if a["attempt_no"] > 1)),
            "parse_status": dict(Counter(r["facts"]["parse_status"] for r in rs)),
            "repair_errors_total": sum(len(a["repair_errors"]) for r in rs for a in r["process"]["attempts"]),
            "mean_model_calls": round(sum(r["process"]["n_model_calls"] for r in rs) / n, 2),
            "cost_per_record_usd": round(sum(rec_cost(r) for r in rs) / n, 5),
            "tool_calls": {k: f"{v} ({v / ttot:.0%})" for k, v in tools.most_common()},
            "unnamed_amount_rate": f"{sum(any(f['code'] == 'ITEM.AMOUNT.UNNAMED' for f in r['judgment']['flags']) for r in rs) / n:.0%}",
            "uncertainty_rate": f"{sum(any(f['code'] == 'RUN.AGENT.UNCERTAINTY_REPORTED' for f in r['judgment']['flags']) for r in rs) / n:.0%}",
            "flag_counts_non_info": {c: v for c, v in flags.most_common() if not c.startswith(("REC.TEXT.PII", "NUM.PARSE", "REC.FIELD.CROSS",
                                                                                          "REC.FIELD.CURRENCY", "ITEM.NATURE", "ITEM.BASIS",
                                                                                          "ITEM.CODE.PENDING", "NUM.JUDGMENT.DOLLAR"))},
            "same_template_as_examples": len(same_tpl),
            "excluding_same_template": {"n": len(rest), "recommendation": pct(Counter(r["judgment"]["recommendation"] for r in rest), len(rest)),
                                        "first_mismatch_rate": f"{sum(r['facts']['first_check'] == 'MISMATCH' for r in rest) / max(len(rest), 1):.1%}"},
        }
        if name != "mock":
            col["recommendation_weighted_to_dev"] = weighted(rs, dev_strata)
        cf = Counter((r["judgment"]["recommendation"], counterfactual_scoring(r)) for r in rs)
        changed = defaultdict(Counter)
        for r in rs:
            old = counterfactual_scoring(r)
            if old != r["judgment"]["recommendation"]:
                key = f"{old} -> {r['judgment']['recommendation']}"
                for f in r["judgment"]["flags"]:
                    if f["severity"] in ("attention", "return"):
                        changed[key][f["code"]] += 1
        col["three_tier_vs_scoring"] = {"pairs (new, old)": {f"{a} | {b}": v for (a, b), v in cf.items()},
                                        "changed_records_flag_codes": {k: dict(v) for k, v in changed.items()}}
        s["columns"][name] = col
    s["mock_vs_ground_truth"] = score(RUNS["mock"])
    s["repeat"] = json.loads((ROOT / "data/interim/autorun/repeat_final.json").read_text())
    s["repeat_v10_before_audit"] = json.loads((ROOT / "data/interim/autorun/repeat.json").read_text())
    led = budget.read_ledger()
    s["budget"] = {"spent_usd": budget.spent_usd(), "cap_usd": budget.CAP_USD,
                   "tokens": {k: sum(p.get(k, 0) for e in led for p in e["usage"]) for k in budget.CLASSES},
                   "window": f"{led[0]['started_at']} .. {led[-1]['finished_at']}", "n_runs": len(led)}
    # spot-check list (rule-based, seeded): per recommendation 4 random from A u B; per major non-info flag 1 random;
    # plus the two RETURN_SUGGESTED records of stage 1 (user requirement e)
    rng = random.Random(20261110)
    pool = data["A"] + data["B"]
    picks, why = [], {}
    for rec in REC:
        cands = sorted([r["record_id"] for r in pool if r["judgment"]["recommendation"] == rec])
        for rid in rng.sample(cands, min(4, len(cands))):
            picks.append(rid); why.setdefault(rid, []).append(f"recommendation {rec}")
    major = [c for c, v in Counter(f["code"] for r in pool for f in r["judgment"]["flags"] if f["severity"] != "info").most_common(7)]
    for code in major:
        cands = sorted({r["record_id"] for r in pool if any(f["code"] == code for f in r["judgment"]["flags"])} - set(picks))
        if cands:
            rid = rng.choice(cands)
            picks.append(rid); why.setdefault(rid, []).append(f"flag {code}")
    st1 = load(STAGE1)
    for r in st1:
        if r["judgment"]["recommendation"] == "RETURN_SUGGESTED":
            picks.append(r["record_id"]); why.setdefault(r["record_id"], []).append("stage-1 RETURN_SUGGESTED (user req. e)")
    s["spot_check"] = {"rule": "seed 20261110; 4 random per recommendation from A u B baseline; 1 random per top-7 non-info flag "
                               "(not already picked); plus both stage-1 RETURN_SUGGESTED records",
                       "records": [{"record_id": rid, "why": why[rid]} for rid in dict.fromkeys(picks)],
                       "major_flags": major}
    (OUT / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(s, indent=1, ensure_ascii=False, default=str)[:9000])


if __name__ == "__main__":
    main()
