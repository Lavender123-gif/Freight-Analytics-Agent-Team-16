"""T12 stocktake 2.1(8): are the three returned annotation packs the packs that were sent out?

Read-only, structure only. It compares each returned workbook with the pack kept locally
(data/interim/annotation/packs/) and with the local key (key_dev.json), and counts unfilled or invalid cells.
It does NOT compare annotations with any system output (brief 1.4: annotations are for evaluation only).

Run: uv run python docs/deliverables/T12-replan-after-jake/scripts/s4_annotation_integrity.py
"""

from __future__ import annotations

import json
import re
import sys
import warnings
from collections import Counter, defaultdict

import openpyxl
import pandas as pd

from freight_lineitems.config import DEV_PATH, ROOT
from freight_lineitems.textprep import normalize

sys.path.insert(0, str(ROOT / "scratch" / "annotation"))
import annot_schema as S  # noqa: E402

warnings.filterwarnings("ignore")
INCOMING = ROOT / "data" / "incoming" / "2026-11-13"
SENT = ROOT / "data" / "interim" / "annotation" / "packs"
KEY = json.loads((ROOT / "data" / "interim" / "annotation" / "key_dev.json").read_text())
BRIEF = INCOMING / "cc_task_replan_after_jake.md"
FIXED = ["item_id", "text", "number_id", "number_raw", "context"]
FILLED = ["what", "claim", "category", "confident", "note"]


def rows(path) -> tuple[list[dict], str | None, str | None]:
    wb = openpyxl.load_workbook(path)
    ws = wb["Annotation"]
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        d = {k: (r[S.COL[k] - 1] if len(r) >= S.COL[k] else None) for k in S.COL}
        if any(v not in (None, "") for v in d.values()):
            out.append({k: ("" if v is None else str(v).strip()) for k, v in d.items()})
    ins = wb["Instructions"]
    return out, ins[S.PACK_ID_CELL].value, ins[S.ANNOTATOR_CELL].value


def main() -> None:
    dev = pd.read_csv(DEV_PATH, dtype=str)
    key_items = {i["item_id"]: i for i in KEY["items"]}
    print("key: items", len(KEY["items"]), "| distinct records", len({i["record_id"] for i in KEY["items"]}),
          "| split", KEY["split"], "| fields", sorted(KEY["items"][0]))
    all_item_records = {}
    common = Counter()
    for pack in ("P1", "P2", "P3"):
        ret = next(p for p in sorted(INCOMING.glob(f"annotation_pack_{pack}*.xlsx")))
        got, pid, annot = rows(ret)
        sent, _, _ = rows(SENT / f"annotation_pack_{pack}.xlsx")
        c = Counter()
        c["rows_returned"], c["rows_sent"] = len(got), len(sent)
        # carry the item id down (it is written on the first row of an item only, if so)
        for lst in (got, sent):
            cur = ""
            for r in lst:
                cur = r["item_id"] or cur
                r["_item"] = cur
        items_got = list(dict.fromkeys(r["_item"] for r in got))
        items_sent = list(dict.fromkeys(r["_item"] for r in sent))
        c["items_returned"], c["items_sent"] = len(items_got), len(items_sent)
        c["item_order_same"] = int(items_got == items_sent)
        c["items_not_in_key"] = sum(1 for i in items_got if i not in key_items)
        sent_by = {(r["_item"], r["number_id"]): r for r in sent}
        got_by = Counter((r["_item"], r["number_id"]) for r in got)
        c["rows_added"] = sum(1 for k in got_by if k not in sent_by)
        c["rows_removed"] = sum(1 for k in sent_by if k not in got_by)
        c["rows_duplicated"] = sum(1 for v in got_by.values() if v > 1)
        for r in got:
            s = sent_by.get((r["_item"], r["number_id"]))
            if s is None:
                continue
            for f in ("text", "number_raw", "context"):
                if r[f] != s[f]:
                    c[f"changed_{f}"] += 1
        c["row_order_same"] = int([(r["_item"], r["number_id"]) for r in got] == [(r["_item"], r["number_id"]) for r in sent])
        # fill state and dropdown validity (structure only)
        valid = {f: set(S.LABEL_TO_CODE[f]) for f in ("what", "claim", "category", "confident")}
        money = {lab for lab, code in S.LABEL_TO_CODE["what"].items() if code in ("AMOUNT", "MONEY")} or None
        first_rows = set()
        seen = set()
        for n, r in enumerate(got):
            if r["_item"] not in seen:
                seen.add(r["_item"])
                first_rows.add(n)
            for f in ("what", "claim", "category", "confident"):
                if r[f] and r[f] not in valid[f]:
                    c[f"invalid_{f}"] += 1
            c["what_empty"] += r["what"] == ""
            wc = S.LABEL_TO_CODE["what"].get(r["what"])
            cc = S.LABEL_TO_CODE["claim"].get(r["claim"])
            is_money = wc is not None and (wc == next(iter(S.WHAT)))     # the first WHAT option is 'an amount of money'
            c["money_rows"] += is_money
            c["money_without_claim"] += is_money and r["claim"] == ""
            c["claim_on_non_money"] += (not is_money) and r["claim"] != ""
            counted = cc == "COUNTED"
            c["counted_rows"] += counted
            c["counted_without_category"] += counted and r["category"] == ""
            c["category_on_not_counted"] += (not counted) and r["category"] != ""
            c["notes"] += r["note"] != ""
        c["items_without_confident"] = sum(1 for n in first_rows if got[n]["confident"] == "")
        c["pack_id_cell_ok"] = int(pid == pack)
        c["annotator_filled"] = int(bool(annot and str(annot).strip()))
        # back to the source records
        ok = 0
        for i in items_got:
            k = key_items.get(i)
            if not k:
                continue
            all_item_records[(pack, i)] = k["record_id"]
            common[k["record_id"]] += 1
            m = re.fullmatch(r"dev#r(\d+)", k["record_id"])
            ok += bool(m and int(m.group(1)) in dev.index)
        c["items_traced_to_a_dev_row"] = ok
        print(f"\n{pack}  ({ret.name})")
        for k in sorted(c):
            print(f"   {k}: {c[k]}")
    recs = set(all_item_records.values())
    print("\nall packs: distinct records", len(recs), "| records in all three packs", sum(1 for v in common.values() if v == 3))

    # what the annotated records cover at shipment level (for the evaluation plan; no annotation content is used)
    idx = [int(r.split("r")[-1]) for r in recs]
    sub = dev.loc[idx]
    dev["text_n"] = dev["Descritipion"].map(normalize)
    per_gid_units = dev.groupby("SHIPMENT_GID").apply(lambda x: x.drop_duplicates(["Event Date", "text_n"]).shape[0], include_groups=False)
    ann_units = defaultdict(set)
    for i in idx:
        r = dev.loc[i]
        ann_units[r.SHIPMENT_GID].add((r["Event Date"], r.text_n))
    full = sum(1 for g, u in ann_units.items() if len(u) == per_gid_units[g])
    multi_full = sum(1 for g, u in ann_units.items() if len(u) == per_gid_units[g] and per_gid_units[g] > 1)
    multi_any = sum(1 for g in ann_units if per_gid_units[g] > 1)
    print("shipments touched by an annotated record:", len(ann_units), "| every explanation of the shipment annotated:", full,
          "| of those, shipments with 2+ explanations:", multi_full, "| touched shipments with 2+ explanations:", multi_any)
    keys = set(re.findall(r"\b\d{17}\b", BRIEF.read_text()))
    print("annotated records that belong to Jake's two example shipments:", int(sub["SAP BOL"].isin(keys).sum()))


if __name__ == "__main__":
    main()
