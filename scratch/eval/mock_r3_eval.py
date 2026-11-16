"""Task 14 section 4 item 6: evaluate one run on the third round of the public mock (read-only; open part only).

Uses only events and rows with `active: true`. Reports:
  events     claim amount agrees: the counted signed sum of the explanation holding the event's first row equals
             `claim.current_claim_total`
  copies     copy flag right or wrong: SHIP.COPY.SAME_OR_NO_PK on the explanation vs `expected_copy_flag`; order count
             vs `expected_order_count`
  shipments  new total agrees with `shipment_truth_open.new_total`; recommendation agrees with
             `expected_shipment_recommendation`
  excel      (user 2026-11-15) per shipment three totals: the truth `new_total`, the system's default new total, and
             the spreadsheet method (shipment_amount + the `delta` of each distinct explanation, order copies once,
             as baseline B1 on the real data). Four-cell table and its split by failure_mode; the shipments where
             the system is wrong and the spreadsheet right are listed in the git-ignored detail file.
             Limitation: the mock is built from the team's own conventions, so this shows the rules are carried
             out as agreed, not accuracy on real data.
Aggregates only; per-shipment rows go to data/interim/eval/mock_r3/<run>.json (git-ignored).
Usage: uv run python scratch/eval/mock_r3_eval.py --run <run>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scratch" / "autorun"))
import compare_variants as cv  # noqa: E402

from freight_lineitems.records import MOCK_R3_DIR  # noqa: E402
from freight_lineitems.pipeline import shipments_of as rollup_results  # task 20: one shipment path  # noqa: E402

ZH = {"PASSED_CHECKS": "解析通过检查", "HUMAN_REVIEW": "建议人工审核", "RETURN_SUGGESTED": "建议退回承运商"}
OUT = ROOT / "data" / "interim" / "eval" / "mock_r3"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    run = cv.replay.find_run(ap.parse_args().run)
    ex = cv.explanations(run)
    row_to = {s["record_id"]: r for r in ex for s in r["facts"]["source_rows"]}
    gt = [g for g in (json.loads(x) for x in (MOCK_R3_DIR / "ground_truth_open.jsonl").open()) if g.get("active", True)]
    st = [json.loads(x) for x in (MOCK_R3_DIR / "shipment_truth_open.jsonl").open()]
    c = Counter()
    by_mode = {}
    for g in gt:
        r = row_to.get("mock3#" + g["row_ids"][0])
        if r is None:
            c["events_not_in_run"] += 1
            continue
        c["events"] += 1
        truth = Decimal(str(g["claim"]["current_claim_total"]))
        got = sum(a for a, _ in cv.counted(r["facts"]["reading"], r["facts"]["number_table"]).values()) if r["facts"]["reading"] else None
        ok = got == truth
        c["claim_correct"] += ok
        m = by_mode.setdefault(g["failure_mode"], Counter())
        m["n"] += 1
        m["ok"] += ok
        flag = any(f["code"] == "SHIP.COPY.SAME_OR_NO_PK" for f in r["judgment"]["flags"])
        if "expected_copy_flag" in g:
            c["copy_flag_expected"] += bool(g["expected_copy_flag"])
            c["copy_flag_raised"] += flag
            c["copy_flag_agrees"] += flag == bool(g["expected_copy_flag"])
            c["copy_flag_missed"] += bool(g["expected_copy_flag"]) and not flag
            c["copy_flag_extra"] += flag and not g["expected_copy_flag"]
        if g.get("expected_order_count") is not None:
            c["order_count_agrees"] += r["facts"].get("n_orders") == g["expected_order_count"]
        c["event_recommendation_agrees"] += ZH[r["judgment"]["recommendation"]] == g["expected_recommendation"]
    ships = {s["shipment_key"]: s for s in rollup_results(ex)}
    detail = []
    mode_of = {g["mock_id"]: g["failure_mode"] for g in gt}
    four, four_by_mode, sys_wrong_sheet_right = Counter(), {}, []
    by_ship_expl: dict[str, list[dict]] = {}
    for e in ex:
        by_ship_expl.setdefault(e["facts"]["source"]["shipment_key"], []).append(e)
    for t in st:
        s = ships.get(t["shipment_id"])
        if s is None:
            c["shipments_not_in_run"] += 1
            continue
        c["shipments"] += 1
        tot_ok = s["new_total"] is not None and Decimal(s["new_total"]) == Decimal(str(t["new_total"]))
        rec_ok = ZH[s["recommendation"]] == t["expected_shipment_recommendation"]
        c["shipment_new_total_agrees"] += tot_ok
        c["shipment_recommendation_agrees"] += rec_ok
        multi = len(t["event_mock_ids"]) > 1
        c["multi_event_shipments"] += multi
        c["multi_new_total_agrees"] += multi and tot_ok
        c["shipment_alternatives_expected"] += bool(t["alternatives"])
        c["shipment_alternatives_given"] += bool(s["other_readings"])
        es = by_ship_expl.get(t["shipment_id"], [])
        sheet = Decimal(str(t["original_amount"])) + sum((Decimal(str(e["facts"]["source"]["delta"] or 0)) for e in es), Decimal(0))
        truth = Decimal(str(t["new_total"]))
        sheet_ok = abs(sheet - truth) <= Decimal("0.005")
        cell = ("system_right" if tot_ok else "system_wrong") + ("_sheet_right" if sheet_ok else "_sheet_wrong")
        four[cell] += 1
        mode = "+".join(sorted({mode_of.get(m, "?") for m in t["event_mock_ids"]}))
        four_by_mode.setdefault(mode, Counter())[cell] += 1
        if tot_ok is False and sheet_ok:
            sys_wrong_sheet_right.append({"shipment": t["shipment_id"], "events": t["event_mock_ids"], "mode": mode,
                                          "truth": str(truth), "system": s["new_total"], "sheet": str(sheet),
                                          "flags": [f["code"] for f in s["flags"]], "recommendation": ZH[s["recommendation"]]})
        detail.append({"shipment": t["shipment_id"], "sheet_new_total": str(sheet), "events": t["event_mock_ids"], "truth_new_total": t["new_total"],
                       "new_total": s["new_total"], "truth_rec": t["expected_shipment_recommendation"], "rec": ZH[s["recommendation"]],
                       "flags": [f["code"] for f in s["flags"]], "truth_alerts": t["reviewer_alerts"]})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{run}.json").write_text(json.dumps(detail, indent=1, ensure_ascii=False))
    (OUT / f"{run}.system_wrong_sheet_right.json").write_text(json.dumps(sys_wrong_sheet_right, indent=1, ensure_ascii=False))
    weak = sorted(((k, v["ok"], v["n"]) for k, v in by_mode.items() if v["ok"] < v["n"]), key=lambda x: x[1] / x[2])
    print(json.dumps({"run": run, **dict(c), "modes_with_wrong_claims": [f"{k} {a}/{b}" for k, a, b in weak],
                      "excel_four_cells": dict(four), "excel_four_cells_by_failure_mode": {k: dict(v) for k, v in sorted(four_by_mode.items())},
                      "excel_limitation": "the mock follows the team's own conventions: this shows the rules are carried out as agreed, not accuracy on real data"},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
