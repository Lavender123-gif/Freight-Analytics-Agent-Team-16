"""T12-13 / task 14 stage 3: finalise the returned annotations by written, mechanical rules only.

Rules (T12 dev plan 3.2, as decided by the owner on 2026-11-15, decision log D-68). They were fixed before any
system output was compared with the annotations; this script never reads a run.
  R-1  annotator id missing -> taken from the file name (P1, P2, P3)
  R-2  a number that is not money: item 2 is set to NOT_MONEY, whatever the annotator filled in
  R-3  a money amount without item 2, or a counted amount without item 3: structurally invalid; that annotator's
       answer for the whole item is dropped (it still votes in R-6 with the cells it did fill)
  R-4  P3's swapped quantity and unit price (a number without '$' marked as a rate): not sent back. Items in the
       three-way overlap are settled by R-6; any other such item is dropped whole
  R-5  text contains BALANCE DUE and two or more '$' amounts besides the first '$' amount after it: every money
       amount of the item becomes UNCLEAR in all packs (the guide's own rule)
  R-6  the items all three annotated: each field takes the majority; when all three differ, item 2 is UNCLEAR and
       item 1 / item 3 are left empty (not scored)
  R-7  everything written goes to the git-ignored data/interim/annotation/final/
Every change is a row of the correction log: file, row, record, number, field, before, after, rule.

Usage: uv run python scratch/annotation/finalize.py [--incoming data/incoming/2026-11-13]
Prints aggregates only (counts per rule; no text, no record ids).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from annot_schema import COL, LABEL_TO_CODE, SHEETS  # noqa: E402
from import_annotations import import_files  # noqa: E402

from freight_lineitems.config import ROOT  # noqa: E402
from freight_lineitems.numbers import parse  # noqa: E402

KEY = ROOT / "data" / "interim" / "annotation" / "key_dev.json"
OUT = ROOT / "data" / "interim" / "annotation" / "final"
FILES = {"annotation_pack_P1": "P1", "annotation_pack_P2_annotated": "P2", "annotation_pack_P3": "P3"}
BALANCE_DUE = re.compile(r"\bBALANCE\s+DUE\b")
FIELDS = ("what", "claim", "category", "confident")


def raw_claims(path: Path) -> dict[int, str]:
    """Item-2 codes exactly as typed (the import drops item 2 on numbers that are not money; R-2 logs them)."""
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=True)[SHEETS[3]]
    out = {}
    for r in range(2, ws.max_row + 1):
        v = ws.cell(row=r, column=COL["claim"]).value
        if v:
            out[r] = LABEL_TO_CODE["claim"].get(str(v).strip(), str(v).strip())
    return out


def r5_items(key: dict) -> set[str]:
    """Items of rule R-5, decided on the record's own text (normalised, as in the packs)."""
    from freight_lineitems.records import load_dev
    from freight_lineitems.textprep import normalize
    texts = {r.record_id: normalize(r.text_raw) for r in load_dev()}
    out = set()
    for it in key["items"]:
        text = texts.get(it["record_id"], "")
        m = BALANCE_DUE.search(text.upper())
        if not m:
            continue
        dollars = [n for n in parse(text).numbers if n.has_dollar]
        after = [n for n in dollars if n.span[0] >= m.end()]
        others = [n for n in dollars if not after or n.id != after[0].id]
        if len(others) >= 2:
            out.add(it["item_id"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incoming", type=Path, default=ROOT / "data" / "incoming" / "2026-11-13")
    a = ap.parse_args()
    key = json.loads(KEY.read_text())
    items = {i["item_id"]: i for i in key["items"]}
    paths = [a.incoming / f"{stem}.xlsx" for stem in FILES]
    table, _warnings = import_files(paths, key, allow_incomplete=True, annotators=FILES)       # R-1 via the file names
    rows = table.to_dict("records")
    log: list[dict] = []

    def change(r, field, before, after, rule):
        log.append({"file": r["source_file"], "row": r["source_row"], "record_id": r["record_id"], "item_id": r["item_id"],
                    "annotator": r["annotator"], "number_id": r["number_id"], "field": field, "before": before,
                    "after": after, "rule": rule})

    for stem, who in FILES.items():                                                           # R-1 logged
        log.append({"file": f"{stem}.xlsx", "row": "", "record_id": "", "item_id": "", "annotator": who, "number_id": "",
                    "field": "annotator", "before": "", "after": who, "rule": "R-1"})
    typed = {f"{stem}.xlsx": raw_claims(a.incoming / f"{stem}.xlsx") for stem in FILES}
    for r in rows:                                                                            # R-2
        if r["what"] and r["what"] != "MONEY":
            before = typed[r["source_file"]].get(int(r["source_row"]), "")
            change(r, "claim", before, "NOT_MONEY", "R-2")
            r["claim"] = "NOT_MONEY"
    invalid = {(r["annotator"], r["item_id"]) for r in rows
               if (r["what"] == "MONEY" and not r["claim"]) or (r["claim"] == "COUNTED" and not r["category"])}   # R-3
    swapped = {(r["annotator"], r["item_id"]) for r in rows
               if r["annotator"] == "P3" and r["what"] == "RATE" and "$" not in r["number_raw"]}                  # R-4
    common = {i for i, it in items.items() if it["is_common"]}
    dropped = set()
    for who, iid in sorted(invalid | swapped):
        rule = "R-3" if (who, iid) in invalid else "R-4"
        if iid in common:
            for r in rows:
                if r["annotator"] == who and r["item_id"] == iid:
                    change(r, "item", "kept", "voted in R-6 only", rule + "+R-6")
        else:
            dropped.add(iid)
            for r in rows:
                if r["annotator"] == who and r["item_id"] == iid:
                    change(r, "item", "kept", "dropped", rule)
    bal = r5_items(key)                                                                       # R-5
    for r in rows:
        if r["item_id"] in bal and r["what"] == "MONEY" and r["claim"] != "UNCLEAR":
            change(r, "claim", r["claim"], "UNCLEAR", "R-5")
            r["claim"], r["category"] = "UNCLEAR", ""
    final: list[dict] = []
    by_rec: dict[str, list[dict]] = {}
    for r in rows:
        by_rec.setdefault(r["record_id"], []).append(r)
    stats = Counter()
    for rec, rs in by_rec.items():
        iid = rs[0]["item_id"]
        if iid in dropped:
            stats["items_dropped"] += 1
            continue
        if iid not in common:
            for r in rs:
                final.append({**r, "annotator": "FINAL"})
            continue
        stats["common_items"] += 1                                                            # R-6
        by_num: dict[str, list[dict]] = {}
        for r in rs:
            by_num.setdefault(r["number_id"], []).append(r)
        for nid, ns in by_num.items():
            out = {**ns[0], "annotator": "FINAL", "pack": "COMMON", "note": "", "source_file": "R-6", "source_row": ""}
            for f in FIELDS:
                c = Counter(x[f] for x in ns)
                val, n = c.most_common(1)[0]
                if n >= 2:
                    out[f] = val
                else:
                    out[f] = "UNCLEAR" if f == "claim" else ""
                    stats[f"r6_no_majority_{f}"] += 1
                if len(c) > 1:
                    log.append({"file": "R-6", "row": "", "record_id": rec, "item_id": iid, "annotator": "FINAL",
                                "number_id": nid, "field": f, "before": "|".join(f"{x['annotator']}={x[f]}" for x in ns),
                                "after": out[f], "rule": "R-6"})
            if out["claim"] != "COUNTED":
                out["category"] = ""
            final.append(out)
    OUT.mkdir(parents=True, exist_ok=True)
    cols = list(table.columns)
    with (OUT / "final_gold.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(final)
    with (OUT / "correction_log.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log[0]))
        w.writeheader()
        w.writerows(log)
    strata = {it["record_id"]: {"bucket": it["bucket"], "is_common": it["is_common"], "r5": i in bal}
              for i, it in items.items() if i not in dropped}
    (OUT / "strata.json").write_text(json.dumps(strata, indent=1))
    summary = {"records_in_packs": len({it["record_id"] for it in items.values()}),
               "records_final": len({r["record_id"] for r in final}), "numbers_final": len(final),
               "corrections_by_rule": dict(Counter(x["rule"] for x in log)), **stats,
               "r4_items": len({i for _, i in swapped}), "r3_items": len({i for _, i in invalid}), "r5_items": len(bal)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
