"""T12-14 / task 14 stage 3, evaluation one: the frozen system's readings against the finalised human annotations.

Reads the finalised gold (data/interim/annotation/final/, written by scratch/annotation/finalize.py) and one run.
The gold path appears only in the evaluation scripts; runtime code and the example-library builder never read it
(tests/test_eval_isolation.py). Default output: aggregates and strata only. Per-record differences are written only
with --detail, to the git-ignored data/interim/eval/annotations/ (T12 dev plan 3.3: once looked at, the 105 records
can no longer serve as evidence for any later change).

Main metric (threshold on card H3, written before this script was first run on the gold): share of scored
explanations whose counted signed sum equals the human sum. Not scored: records with an Unclear, empty or contested
cell, and records of the A5 BALANCE DUE form (the guide and rule A5 disagree there; reported apart).
Strata (T12 dev plan 3.1): common 15 vs pack-only; frequency half vs hard buckets; in tuning sample A vs not; with
the pending purchased-transportation category vs without. Plus: visibility (misread explanations sent to a person;
passed explanations that are misread) and the shipments whose every explanation is annotated.
Usage: uv run python scratch/eval/eval_annotations.py --run <run> [--detail]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "annotation"), str(ROOT / "scratch" / "autorun")]
import metrics as M  # noqa: E402
from agreement import derive, number_value  # noqa: E402
from import_annotations import load_long  # noqa: E402

from freight_lineitems.config import RULES, RUNS_DIR  # noqa: E402
from freight_lineitems.numbers import parse  # noqa: E402

GOLD = ROOT / "data" / "interim" / "annotation" / "final"
DETAIL = ROOT / "data" / "interim" / "eval" / "annotations"
SAMPLE_A_RUN = "20261110-201831-rdAallowlist-49dd"
RMIN, RMAX = Decimal(str(RULES["rollup"]["ratio_min"])), Decimal(str(RULES["rollup"]["ratio_max"]))
BAL = re.compile(RULES["rollup"]["balance_due_pattern"])


def a5_form(text: str) -> bool:
    m = BAL.search(text.upper())
    if not m:
        return False
    d = [n for n in parse(text).numbers if n.has_dollar]
    before = [n for n in d if n.span[1] <= m.start()]
    after = [n for n in d if n.span[0] >= m.end()]
    return bool(before and after) and any(b.value > 0 and RMIN <= after[0].value / b.value <= RMAX for b in before)


def human_sum(g) -> Decimal | None:
    s = Decimal(0)
    for nid, gn in g.groupby("number_id", sort=False):
        c = set(gn["claim_coarse"])
        if len(c) != 1 or c & {"UNCLEAR", ""}:
            return None
        c = c.pop()
        v = number_value(nid, gn["number_raw"].iloc[0])
        s += v if c == "COUNTED" else -v if c == "CREDIT" else 0
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    import compare_variants as cv
    run_id = cv.replay.find_run(a.run)
    run = M.load_run(run_id)
    gold = derive(load_long(GOLD / "final_gold.csv"))
    strata = json.loads((GOLD / "strata.json").read_text())
    in_a = {json.loads(x)["record_id"] for x in (RUNS_DIR / SAMPLE_A_RUN / "records.jsonl").open()}
    res_all = M.compare(run, gold)
    rows = []
    for rid, g in gold.groupby("record_id"):
        rec = run.get(rid)
        if rec is None:
            continue
        hs = human_sum(g)
        text = rec["facts"].get("text_redacted") or ""
        ms = M.signed_sum(rec["facts"]["reading"], rec["facts"]["number_table"])
        st = strata.get(rid, {})
        rows.append({"record_id": rid, "human": hs, "model": ms, "a5": a5_form(text),
                     "scored": hs is not None and not a5_form(text),
                     "correct": hs is not None and ms is not None and hs == ms,
                     "recommendation": rec["judgment"]["recommendation"],
                     "common": st.get("is_common"), "frequency_half": st.get("bucket") == "frequency",
                     "in_sample_a": rid in in_a, "pending_pt": bool((g["category"] == "PENDING").any()),
                     "shipment": rec["facts"]["source"]["shipment_key"]})

    def main_metric(rs):
        sc = [r for r in rs if r["scored"]]
        ok = sum(r["correct"] for r in sc)
        return {"scored": len(sc), "correct": ok, "percent": round(100 * ok / len(sc), 1) if sc else None,
                "not_scored": len(rs) - len(sc)}
    strata_out = {"all": main_metric(rows)}
    for k in ("common", "frequency_half", "in_sample_a", "pending_pt"):
        strata_out[f"{k}=yes"] = main_metric([r for r in rows if r[k]])
        strata_out[f"{k}=no"] = main_metric([r for r in rows if not r[k]])
    sc = [r for r in rows if r["scored"]]
    wrong = [r for r in sc if not r["correct"]]
    passed = [r for r in sc if r["recommendation"] == "PASSED_CHECKS"]
    visibility = {"misread": len(wrong), "misread_sent_to_person": sum(r["recommendation"] == "HUMAN_REVIEW" for r in wrong),
                  "misread_return_suggested": sum(r["recommendation"] == "RETURN_SUGGESTED" for r in wrong),
                  "passed": len(passed), "passed_but_misread": sum(not r["correct"] for r in passed)}
    # T12 dev plan 3.1: explanations a person marked Unclear are not scored; report whether the system sent them to a person
    unclear = [r for r in rows if r["human"] is None]
    visibility["unclear_records"] = len(unclear)
    visibility["unclear_by_recommendation"] = dict(Counter(r["recommendation"] for r in unclear))
    visibility["unclear_a5_form"] = sum(r["a5"] for r in unclear)
    a5_scorable = [r for r in rows if r["a5"] and r["human"] is not None]
    visibility["a5_form_scorable_by_recommendation"] = dict(Counter(r["recommendation"] for r in a5_scorable))
    # shipments whose every explanation is annotated
    from freight_lineitems.records import group_explanations, load_dev
    dev = load_dev()
    expl_by_ship: dict[str, set] = {}
    for grp in group_explanations(dev):
        expl_by_ship.setdefault(grp[0].shipment_key, set()).add(frozenset(r.record_id for r in grp))
    annotated = {r["record_id"] for r in rows}
    full = [s for s, es in expl_by_ship.items() if all(e & annotated for e in es)]
    by_ship = {}
    for r in rows:
        by_ship.setdefault(r["shipment"], []).append(r)
    from freight_lineitems.pipeline import shipments_of as rollup_results  # task 20: one shipment path
    ships = {s["shipment_key"]: s for s in rollup_results(cv.explanations(run_id))}
    ship_rows = Counter()
    for s in full:
        rs = by_ship.get(s, [])
        multi = len(expl_by_ship[s]) > 1
        if not rs or any(r["human"] is None for r in rs) or s not in ships:
            ship_rows["not_scored_multi" if multi else "not_scored_single"] += 1
            continue
        h = sum(r["human"] for r in rs)
        ok = Decimal(ships[s]["default_change"]) == h
        ship_rows[("multi" if multi else "single") + ("_equal" if ok else "_differ")] += 1
    out = {"run": run_id, "gold_records": gold["record_id"].nunique(), "records_in_run": len(rows),
           "a5_form_records": sum(r["a5"] for r in rows), "main_metric": strata_out, "visibility": visibility,
           "shipments_fully_annotated": {"n": len(full), "multi_explanation": sum(len(expl_by_ship[s]) > 1 for s in full),
                                         **dict(ship_rows), "note": "human shipment total = sum of the human explanation sums (no replacement)"},
           "number_level_pooled": {k: res_all["pooled"][k] for k in ("is_money", "counted_not_counted_credit", "charge_category")},
           "coverage": res_all["coverage"]}
    print(json.dumps(out, indent=1, default=str))
    if a.detail:
        DETAIL.mkdir(parents=True, exist_ok=True)
        (DETAIL / f"{run_id}.json").write_text(json.dumps(rows, indent=1, default=str))


if __name__ == "__main__":
    main()
