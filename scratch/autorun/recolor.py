"""Recompute recommendations from retained model outputs under changed rules (task 10 section 1). No model calls.

Usage: uv run python scratch/autorun/recolor.py [--dev-full <run_id>] [--json out.json]
Prints aggregates only. Each step is applied on top of the previous one, and before/after counts are reported:
  step 0  rules as they were at the end of leg 1
  step 1  'return' only when code alone can decide: ITEM.AMOUNT.UNNAMED, ITEM.AMOUNT.MISSING, REC.TEXT.NO_NUMBER -> attention
  step 2  P-13: model self-reported doubt -> info (applied only if the pre-stated rule says so; both shown)
  step 3  P-15: '$' excluded with a basis phrase naming no accepted category -> attention (both shown)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_run import load  # noqa: E402
from mock_eval import signed_sum  # noqa: E402

from freight_lineitems.checks import exclusion_basis_category  # noqa: E402
from freight_lineitems.config import RULES  # noqa: E402
from freight_lineitems.records import MOCK_DIR, load_dev  # noqa: E402
from freight_lineitems.sampling import style  # noqa: E402

RUNS = {"A": "20261110-184540-finA-d700", "B2": "20261110-184723-finB2-4b6b", "mock": "20261110-184540-finMock-da71"}
REC = ["PASSED_CHECKS", "HUMAN_REVIEW", "RETURN_SUGGESTED"]
LEG1 = {"ITEM.AMOUNT.UNNAMED": "return", "ITEM.AMOUNT.MISSING": "return", "REC.TEXT.NO_NUMBER": "return",
        "RUN.AGENT.UNCERTAINTY_REPORTED": "attention"}
STEP1 = {"ITEM.AMOUNT.UNNAMED": "attention", "ITEM.AMOUNT.MISSING": "attention", "REC.TEXT.NO_NUMBER": "attention",
         "_subsumption": True}
SUBSUMPTION = RULES.get("subsumption", {})
STEP2 = {"RUN.AGENT.UNCERTAINTY_REPORTED": "info"}
UNLISTED = "NUM.JUDGMENT.EXCLUSION_BASIS_UNLISTED"


def severities(r: dict, overrides: dict, unlisted: str | None) -> list[str]:
    """Severity of every flag of a record under `overrides`; `unlisted` adds the P-15 flag at that severity."""
    codes = {f["code"] for f in r["judgment"]["flags"]}
    sub = SUBSUMPTION if overrides.get("_subsumption") else {}
    out = ["info" if any(c in codes for c in sub.get(f["code"], [])) else overrides.get(f["code"], f["severity"])
           for f in r["judgment"]["flags"] if f["code"] != UNLISTED]
    if unlisted and has_unlisted(r):
        out.append(unlisted)
    return out


def has_unlisted(r: dict) -> bool:
    return any(exclusion_basis_category(e.get("exclusion_phrase")) is None
               for f in r["judgment"]["flags"] if f["code"] == "NUM.JUDGMENT.DOLLAR_EXCLUDED" for e in f["evidence"])


def color(sev: list[str]) -> str:
    return "HUMAN_REVIEW" if "attention" in sev else "RETURN_SUGGESTED" if "return" in sev else "PASSED_CHECKS"


def dist(rs: list[dict], overrides: dict, unlisted: str | None = None, weights: dict | None = None) -> dict:
    c: Counter = Counter()
    for r in rs:
        c[color(severities(r, overrides, unlisted))] += weights[r["record_id"]] if weights else 1
    tot = sum(c.values())
    return {k: (round(c[k], 1), f"{c[k] / tot:.1%}") for k in REC}


def moves(rs: list[dict], a: tuple, b: tuple) -> dict:
    m = Counter((color(severities(r, *a)), color(severities(r, *b))) for r in rs)
    return {f"{x}->{y}": n for (x, y), n in m.items() if x != y}


def dev_weights(rs: list[dict]) -> dict:
    """Weight of each sampled record = dev rows in its carrier x style stratum / sampled rows in it (as in leg 1)."""
    strata = Counter((r.carrier, style(r.text_raw)) for r in load_dev())
    key = lambda r: (r["facts"]["source"]["carrier"], style(r["facts"]["text_redacted"]))  # noqa: E731
    samp = Counter(key(r) for r in rs)
    return {r["record_id"]: strata[key(r)] / samp[key(r)] for r in rs}


def p13(mock: list[dict]) -> dict:
    """Misread rate (final counted sum != ground truth) among mock events with / without a self-reported doubt."""
    gt = [json.loads(x) for x in (MOCK_DIR / "ground_truth.jsonl").read_text().splitlines()]
    by = {r["record_id"]: r for r in mock}
    n = Counter()
    for ev in gt:
        r = by.get("mock#" + ev["row_ids"][0])
        if r is None:
            continue
        doubt = any(f["code"] == "RUN.AGENT.UNCERTAINTY_REPORTED" for f in r["judgment"]["flags"])
        wrong = signed_sum(r["facts"]["reading"], r["facts"]["number_table"]) != Decimal(str(ev["claim"]["current_claim_total"]))
        n[("doubt" if doubt else "no_doubt", "wrong" if wrong else "right")] += 1
        if ev["failure_mode"] == "control_clean":
            n[("doubt_cc" if doubt else "no_doubt_cc", "wrong" if wrong else "right")] += 1
    def rate(k):
        t = n[(k, "wrong")] + n[(k, "right")]
        return {"events": t, "wrong": n[(k, "wrong")], "rate": round(n[(k, "wrong")] / t, 4) if t else None}
    out = {k: rate(k) for k in ("doubt", "no_doubt")}
    out["ratio"] = round(out["doubt"]["rate"] / out["no_doubt"]["rate"], 2) if out["no_doubt"]["rate"] else None
    out["control_clean_only"] = {k: rate(k + "_cc") for k in ("doubt", "no_doubt")}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-full", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    runs = dict(RUNS) | ({"dev_full": a.dev_full} if a.dev_full else {})
    data = {k: load(v) for k, v in runs.items()}
    out: dict = {"runs": runs}
    out["p13_mock"] = p13(data["mock"])
    for name, rs in data.items():
        s0, s1 = (LEG1, None), (LEG1 | STEP1, None)
        s2 = (LEG1 | STEP1 | STEP2, None)
        col = {"n": len(rs),
               "flag_records": {c: sum(any(f["code"] == c for f in r["judgment"]["flags"]) for r in rs)
                                for c in [*LEG1, "REC.TEXT.EMPTY", "REC.TEXT.NUMBERS_ONLY", "NUM.JUDGMENT.DOLLAR_EXCLUDED"]},
               "records_with_unlisted_basis": sum(has_unlisted(r) for r in rs),
               "step0": dist(rs, *s0), "step1": dist(rs, *s1), "moves_0_to_1": moves(rs, s0, s1),
               "step2_if_doubt_info": dist(rs, *s2), "moves_1_to_2": moves(rs, s1, s2)}
        for label, base in (("on_step1", s1), ("on_step2", s2)):
            b3 = (base[0], "attention")
            col[f"step3_{label}"] = dist(rs, *b3)
            col[f"moves_to_3_{label}"] = moves(rs, base, b3)
        if name in ("A", "B2"):
            w = dev_weights(rs)
            for label, st in (("step0", s0), ("step1", s1), ("step2", s2), ("step1+3", (s1[0], "attention")),
                              ("step2+3", (s2[0], "attention"))):
                col[f"weighted_{label}"] = dist(rs, *st, weights=w)
        out[name] = col
    print(json.dumps(out, indent=1, ensure_ascii=False))
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
