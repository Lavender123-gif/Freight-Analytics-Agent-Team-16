"""Task 17 (D-77, D-78): corrections to the reference answers, added as new columns; original columns untouched.

- D-77: 10 category disagreements corrected by the code table: the charge wording is an example phrasing written in
  config/taxonomy.yaml, so the category of that code is the reference category.
- D-78: of the task-15 re-judging, the 2 records with BALANCE DUE first and 'amount + tax = total' get the annotators'
  original answers back; the quantity-1 record no longer needs a person (one unit: unit price = whole charge).
Writes data/interim/annotation/deliverable/t17_corrections.json, adds columns to merged_annotations.csv and writes the
post-hoc correction log (all git-ignored). Usage: uv run python scratch/annotation/t17_corrections.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from freight_lineitems.config import CODES, ROOT, category

D = ROOT / "data" / "interim" / "annotation" / "deliverable"
# record -> (number id, code whose example phrasing the text uses)
CATEGORY_BY_CODE_TABLE = {
    "dev#r108": ("#2", "RATE_CORRECTION.FUEL_TIER"), "dev#r23": ("#2", "RATE_CORRECTION.FUEL_TIER"),
    "dev#r65": ("#2", "RATE_CORRECTION.FUEL_TIER"), "dev#r180": ("#1", "RATE_CORRECTION.CONTRACT_GENERAL"),
    "dev#r215": ("#1", "RATE_CORRECTION.CONTRACT_GENERAL"), "dev#r224": ("#1", "RATE_CORRECTION.CONTRACT_GENERAL"),
    "dev#r225": ("#1", "ACCESSORIAL.IN_BOND"), "dev#r37": ("#1", "ACCESSORIAL.SORT_SEGREGATE"),
    "dev#r853": ("#1", "ACCESSORIAL.ROAD_CLOSURE"), "dev#r906": ("#1", "ACCESSORIAL.ROAD_CLOSURE"),
}
RESTORE_ORIGINAL = ["dev#r38", "dev#r159"]
QUANTITY_ONE = {"dev#r233": {"#2": {"claim": "COUNTED", "category": category("DETENTION_STORAGE.DWELL")}}}


def main() -> None:
    rows = list(csv.DictReader((D / "merged_annotations.csv").open()))
    cols = list(rows[0])
    new = ["category_corrected_by_code_table", "t17_claim", "t17_category", "t17_correction"]
    corr, log = {"category": {}, "restore": {}, "quantity_one": QUANTITY_ONE, "drop_rejudge": RESTORE_ORIGINAL + list(QUANTITY_ONE)}, []
    for r in rows:
        for c in new:
            r.setdefault(c, "")
        key = r["record_key"]
        if key in CATEGORY_BY_CODE_TABLE and CATEGORY_BY_CODE_TABLE[key][0] == r["number_id"]:
            code = CATEGORY_BY_CODE_TABLE[key][1]
            assert code in CODES
            r["category_corrected_by_code_table"] = category(code)
            r["t17_category"] = category(code)
            r["t17_correction"] = f"D-77: wording is an example phrasing of {code} in config/taxonomy.yaml"
            corr["category"][key] = {"number_id": r["number_id"], "category": category(code), "code": code}
            log.append({"record": key, "number_id": r["number_id"], "field": "category", "before": r["rejudged_category"] or r["final_category"],
                        "after": category(code), "basis": r["t17_correction"]})
        if key in RESTORE_ORIGINAL:
            ann = [a for a in ("p1", "p2", "p3") if r[f"{a}_claim"] or r[f"{a}_what"]]
            claims = [r[f"{a}_claim"] for a in ann]
            cats = [r[f"{a}_category"] for a in ann]
            claim = max(set(claims), key=claims.count) if claims else ""
            cat = max(set(cats), key=cats.count) if cats else ""
            r["t17_claim"], r["t17_category"] = claim, cat
            r["t17_correction"] = "D-78: annotators' original answer restored (BALANCE DUE first, amount + tax = total)"
            corr["restore"].setdefault(key, {})[r["number_id"]] = {"claim": claim, "category": cat}
            log.append({"record": key, "number_id": r["number_id"], "field": "claim/category", "before": "UNCLEAR",
                        "after": f"{claim}/{cat}", "basis": r["t17_correction"]})
        if key in QUANTITY_ONE and r["number_id"] in QUANTITY_ONE[key]:
            q = QUANTITY_ONE[key][r["number_id"]]
            r["t17_claim"], r["t17_category"] = q["claim"], q["category"]
            r["t17_correction"] = "D-78/D-82: quantity 1, the unit price is the whole charge; no person needed"
            log.append({"record": key, "number_id": r["number_id"], "field": "claim/category", "before": "UNCLEAR",
                        "after": f"{q['claim']}/{q['category']}", "basis": r["t17_correction"]})
    with (D / "merged_annotations.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols + [c for c in new if c not in cols])
        w.writeheader()
        w.writerows(rows)
    (D / "t17_corrections.json").write_text(json.dumps(corr, indent=1))
    with (D / "t17_posthoc_correction_log.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(log[0]))
        w.writeheader()
        w.writerows(log)
    print(f"{len(corr['category'])} category corrections, {len(corr['restore'])} records restored, {len(QUANTITY_ONE)} quantity-1; {len(log)} log rows")
    print({k: v for k, v in corr["restore"].items()})


if __name__ == "__main__":
    main()
