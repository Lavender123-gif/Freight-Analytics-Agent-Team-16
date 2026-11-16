"""T12-15 / task 14 stage 3, evaluation two: the system's default change per shipment against the client's Excel
baselines, on every dev shipment. Disagreements are put into categories written down before the run (card V6).

Baselines (C8):
  B1  Delta summed over the shipment's distinct explanations
  B2  Invoice Dups Removed summed over the shipment's rows, minus Shipment Amount (no B2 when they are all zero)
Categories, tried in this order; the first whose amount equals the difference (system minus baseline, within 0.005)
explains it. 'difference' D = system default change - baseline.
  C1 stated_total_counted_again  the baseline also counts a total the text states: D = -(sum of $ amounts the reading
                                 marks TOTAL)
  C2 later_restates_earlier      A3: a later explanation replaced an earlier line: D = -(sum of lines the roll-up
                                 replaced by rule 2)
  C3 balance_due_ratio           A5: BALANCE DUE or the next explanation at 1.03-1.07x replaced an earlier amount:
                                 D = -(sum of lines replaced or not counted by rule 6)
  C4 baseline_counts_history     D = -(sum of $ amounts the reading marks BILLED, PAID or DEDUCTED)
  C5 baseline_misses_no_dollar   D = +(sum of counted amounts written without '$')
  C6 baseline_keeps_one_row      B2 only: the baseline equals one explanation's Delta while the shipment has several
  C7 order_copies                D = -(Delta over all rows - Delta over distinct explanations)
  C8 system_incomplete           the roll-up is incomplete (an explanation without a usable reading)
  C9 two_of_the_above            D equals the sum of the amounts of two categories above
  C0 unclassified
Prints aggregates only; per-shipment rows go to data/interim/eval/excel_baseline/<run>.csv (git-ignored).
Usage: uv run python scratch/eval/excel_baseline.py --run <run>
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from decimal import Decimal
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scratch" / "autorun"))
import compare_variants as cv  # noqa: E402

from freight_lineitems.checks import region_value  # noqa: E402
from freight_lineitems.records import load_dev  # noqa: E402
from freight_lineitems.pipeline import shipments_of as rollup_results  # task 20: one shipment path  # noqa: E402

TOL = Decimal("0.005")
OUT = ROOT / "data" / "interim" / "eval" / "excel_baseline"
NAMES = {"C1": "stated_total_counted_again", "C2": "later_restates_earlier", "C3": "balance_due_ratio",
         "C4": "baseline_counts_history", "C5": "baseline_misses_no_dollar", "C6": "baseline_keeps_one_row",
         "C7": "order_copies", "C8": "system_incomplete", "C9": "two_of_the_above", "C0": "unclassified"}


def numbers_by_status(r: dict) -> dict[str, Decimal]:
    f = r["facts"]
    if not f.get("reading"):
        return {}
    t = f["number_table"]
    vals = {n["id"]: (Decimal(n["value"]), n["has_dollar"]) for n in t["numbers"]} | {
        u["id"]: (region_value(u["raw"]), False) for u in t["unrecognized"]}
    out = Counter()
    js = list(f["reading"]["numbers"]) + [u["as_number"] | {"id": u["region_id"]} for u in f["reading"].get("unrecognized_reads", [])]
    for j in js:
        if j["id"] not in vals:
            continue
        v, dollar = vals[j["id"]]
        if j["kind"] == "TOTAL" and dollar:
            out["total"] += v
        if j["status"] in ("BILLED", "PAID", "DEDUCTED") and dollar:
            out["history"] += v
        if j["status"] in ("CLAIMED", "UNPAID") and j["kind"] in ("CHARGE_AMOUNT", "UNSPECIFIED_AMOUNT", "TAX_AMOUNT") and not dollar:
            out["no_dollar"] += -v if j.get("is_credit") else v
    return dict(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = cv.replay.find_run(a.run)
    expl = cv.explanations(run)
    rows = {r.record_id: r for r in load_dev()}
    by_ship: dict[str, list[dict]] = {}
    for e in expl:
        by_ship.setdefault(e["facts"]["source"]["shipment_key"], []).append(e)
    ships = rollup_results(expl)
    out_rows, stats = [], {"B1": Counter(), "B2": Counter()}
    for sh in ships:
        es = by_ship[sh["shipment_key"]]
        d_sys = Decimal(sh["default_change"])
        all_rows = [rows[x["record_id"]] for e in es for x in e["facts"]["source_rows"]]
        b1 = sum((rows[e["record_id"]].delta or Decimal(0)) for e in es)
        idr = sum((r.invoice_dups_removed or Decimal(0)) for r in all_rows)
        b2 = idr - Decimal(sh["original_amount"]) if idr else None
        st = Counter()
        for e in es:
            st.update(numbers_by_status(e))
        replaced2 = sum((Decimal(l["amount"]) for l in sh["lines"] if l["status"] == "SUPERSEDED"
                         and any(f["code"] == "SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE" and any(ev.get("event") == l["event"] for ev in f["evidence"]) for f in sh["flags"])), Decimal(0))
        replaced6 = sum((Decimal(l["amount"]) for l in sh["lines"] if l["status"] in ("SUPERSEDED", "NOT_COUNTED")
                         and any(f["code"] == "SHIP.ROLLUP.RATIO_SUPERSEDED" and any(ev.get("event") == l["event"] for ev in f["evidence"]) for f in sh["flags"])), Decimal(0))
        added_by_code = sum((Decimal(l["amount"]) for l in sh["lines"] if l["added_by_code"]), Decimal(0))
        copies = sum((r.delta or Decimal(0)) for r in all_rows) - b1
        cand = {"C1": -st.get("total", Decimal(0)), "C2": -replaced2, "C3": -(replaced6 - added_by_code) if replaced6 else Decimal(0),
                "C4": -st.get("history", Decimal(0)), "C5": st.get("no_dollar", Decimal(0)), "C7": -copies}
        for name, base in (("B1", b1), ("B2", b2)):
            if base is None:
                stats[name]["no_baseline"] += 1
                continue
            stats[name]["shipments"] += 1
            diff = d_sys - base
            if abs(diff) <= TOL:
                stats[name]["equal"] += 1
                cat = "equal"
            else:
                stats[name]["differ"] += 1
                cat = "C0"
                if not sh["complete"]:
                    cat = "C8"
                else:
                    for k, v in cand.items():
                        if v != 0 and abs(diff - v) <= TOL:
                            cat = k
                            break
                    if cat == "C0" and name == "B2" and len(es) > 1 and any(
                            abs(base - (rows[e["record_id"]].delta or Decimal(0))) <= TOL for e in es):
                        cat = "C6"
                    if cat == "C0":
                        nz = [(k, v) for k, v in cand.items() if v != 0]
                        if any(abs(diff - (v1 + v2)) <= TOL for (_, v1), (_, v2) in combinations(nz, 2)):
                            cat = "C9"
                stats[name][cat] += 1
            out_rows.append({"shipment": sh["shipment_key"], "baseline": name, "system_change": str(d_sys),
                             "baseline_change": str(base), "difference": str(diff), "category": cat,
                             "n_explanations": len(es), "recommendation": sh["recommendation"]})
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / f"{run}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    res = {"run": run, "shipments": len(ships)}
    for name, c in stats.items():
        differ = c["differ"]
        res[name] = {"shipments": c["shipments"], "equal": c["equal"], "differ": differ, "no_baseline": c["no_baseline"],
                     "categories": {f"{k} {NAMES[k]}": c[k] for k in NAMES if c[k]},
                     "unclassified_share_of_differ": round(c["C0"] / differ, 4) if differ else 0.0}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
