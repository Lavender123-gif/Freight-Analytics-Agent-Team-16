"""T12 stocktake 2.1(6)(7): re-check the data facts of the task brief (section 1.2) on the DEV split only.

Read-only. No model calls. Prints aggregates only (no row text, no identifiers) and writes the same numbers to
data/interim/deliverables/T12/dev_facts.json (git-ignored).

Run: uv run python docs/deliverables/T12-replan-after-jake/scripts/s1_dev_facts.py

The two example keys are read from the git-ignored task brief, never hard-coded here.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pandas as pd

from freight_lineitems.config import DEV_PATH, ROOT, assert_readable
from freight_lineitems.numbers import parse
from freight_lineitems.textprep import normalize

OUT = ROOT / "data" / "interim" / "deliverables" / "T12"
BRIEF = ROOT / "data" / "incoming" / "2026-11-13" / "cc_task_replan_after_jake.md"
D = lambda x: None if x is None or pd.isna(x) or x == "" else Decimal(str(x)).quantize(Decimal("0.01"))  # noqa: E731
TOL = Decimal("0.005")
LO, HI = Decimal("1.03"), Decimal("1.07")


def dollar_amounts(text: str) -> list[Decimal]:
    return [n.value for n in parse(text).numbers if n.has_dollar]


def all_amount_like(text: str) -> list[Decimal]:
    return [n.value for n in parse(text).numbers]


def main() -> None:
    df = pd.read_csv(assert_readable(DEV_PATH), dtype=str)
    df["text"] = df["Descritipion"].map(normalize)
    df["delta"] = df["Delta"].map(D)
    df["inv"] = df["Invoice Amount"].map(D)
    df["ship"] = df["Shipment Amount"].map(D)
    df["dups"] = df["Invoice Dups Removed"].map(D)
    df["bol"] = df["SAP BOL"]
    df["gid"] = df["SHIPMENT_GID"]
    df["ed"] = pd.to_datetime(df["Event Date"])
    df["dol"] = df["text"].map(dollar_amounts)
    res: dict = {"n_rows": len(df), "n_gid": int(df.gid.nunique()), "n_bol_nonnull": int(df.bol.nunique())}

    # 1. Delta = sum of every '$' amount in the text
    with_dol = df[df.dol.map(len) > 0]
    eq = with_dol.apply(lambda r: r.delta is not None and abs(sum(r.dol) - r.delta) <= TOL, axis=1)
    multi = with_dol[with_dol.dol.map(len) > 1]
    eq_multi = multi.apply(lambda r: r.delta is not None and abs(sum(r.dol) - r.delta) <= TOL, axis=1)
    res["f1"] = {"rows_with_dollar": len(with_dol), "delta_eq_sum_of_dollar": int(eq.sum()),
                 "rows_with_2plus_dollar": len(multi), "delta_eq_sum_of_dollar_2plus": int(eq_multi.sum()),
                 "rows_without_dollar": int((df.dol.map(len) == 0).sum()),
                 "rows_without_dollar_delta_zero": int(((df.dol.map(len) == 0) & (df.delta == 0)).sum())}

    # 2. Invoice Amount = Shipment Amount + this row's Delta (per row, not cumulative)
    ok = df.apply(lambda r: None not in (r.inv, r.ship, r.delta) and abs(r.inv - r.ship - r.delta) <= TOL, axis=1)
    res["f2"] = {"rows_inv_eq_ship_plus_delta": int(ok.sum()), "rows": len(df)}

    # 3. Invoice Dups Removed keeps one row per SAP BOL
    g = df.groupby("gid")
    nz = g.apply(lambda x: int(sum(1 for v in x.dups if v is not None and v != 0)), include_groups=False)
    multi_text = g.text.nunique()
    res["f3"] = {"gid_with_exactly_one_nonzero": int((nz == 1).sum()), "gid_with_zero_nonzero": int((nz == 0).sum()),
                 "gid_with_2plus_nonzero": int((nz > 1).sum()),
                 "gid_with_2plus_texts": int((multi_text > 1).sum()),
                 "gid_with_2plus_texts_and_one_nonzero": int(((multi_text > 1) & (nz == 1)).sum()),
                 "rows_dups_eq_inv": int(sum(1 for a, b in zip(df.dups, df.inv) if a is not None and a != 0 and a == b)),
                 "rows_dups_nonzero": int(sum(1 for a in df.dups if a is not None and a != 0))}

    # 4. keys
    nn = df[df.bol.notna()]
    res["f4"] = {"bol_null_rows": int(df.bol.isna().sum()), "gid_null_rows": int(df.gid.isna().sum()),
                 "bol_per_gid_max": int(nn.groupby("gid").bol.nunique().max()),
                 "gid_per_bol_max": int(nn.groupby("bol").gid.nunique().max()),
                 "gid_of_null_bol_rows": int(df[df.bol.isna()].gid.nunique()),
                 "shipment_number_eq_bol_6_12": int((nn["Shipment Number"] == nn.bol.str[5:12]).sum()),
                 "rows_bol_nonnull": len(nn), "shipment_number_values": int(nn["Shipment Number"].nunique()),
                 "bol_values": int(nn.bol.nunique())}

    # 5. one origin, one destination, one carrier per shipment
    res["f5"] = {c: int((g[c].nunique(dropna=False) > 1).sum()) for c in
                 ["Carrier", "Source State", "Source City", "Source Address", "Destination State", "Destination City",
                  "Destination Address", "Shipment Amount"]}

    # 6. the same explanation on more than one row of a shipment
    cg = df.groupby(["gid", "text"])
    groups = [(k, x) for k, x in cg if len(x) > 1]
    per_pk = [x for _, x in groups if x.PK.notna().all() and x.PK.nunique() == len(x)]
    other = [x for _, x in groups if not (x.PK.notna().all() and x.PK.nunique() == len(x))]
    same_ed = sum(1 for _, x in groups if x.ed.nunique() == 1)
    same_delta = sum(1 for _, x in groups if x.Delta.nunique() == 1)
    same_inv = sum(1 for _, x in groups if x["Invoice Amount"].nunique() == 1)
    res["f6"] = {"texts_on_2plus_rows": len(groups), "extra_rows": sum(len(x) - 1 for _, x in groups),
                 "one_row_per_distinct_pk": len(per_pk), "one_row_per_distinct_pk_extra_rows": sum(len(x) - 1 for x in per_pk),
                 "pk_same_or_null": len(other), "pk_same_or_null_extra_rows": sum(len(x) - 1 for x in other),
                 "groups_same_event_date": same_ed, "groups_same_delta": same_delta, "groups_same_invoice_amount": same_inv}
    # C4 merge key (gid, event date, text) against the current content key (gid, carrier invoice, text, Delta, event date)
    k_new = df.groupby(["gid", "ed", "text"], dropna=False).ngroups
    k_old = df.groupby(["gid", "Carrier Invoice", "text", "Delta", "ed"], dropna=False).ngroups
    k_txt = cg.ngroups
    res["f6_keys"] = {"units_by_gid_eventdate_text": k_new, "units_by_current_content_key": k_old, "units_by_gid_text": k_txt}

    # 7. PK coverage per shipment
    npk = g.PK.nunique()
    res["f7"] = {"gid_no_pk": int((npk == 0).sum()), "gid_one_pk": int((npk == 1).sum()), "gid_multi_pk": int((npk > 1).sum())}

    # 8. shipments with more than one distinct explanation
    nt = g.text.nunique()
    res["f8"] = {"gid_with_2plus_texts": int((nt > 1).sum()), "distribution": dict(sorted(Counter(nt.tolist()).items()))}

    # 9. BALANCE DUE after other '$' amounts (distinct texts)
    cls = Counter()
    for t in sorted(set(df.text)):
        p = parse(t)
        m = re.search(r"BALANCE\s+DUE", t)
        if not m:
            continue
        cls["texts_with_balance_due"] += 1
        before = [n.value for n in p.numbers if n.has_dollar and n.span[1] <= m.start()]
        after = [n.value for n in p.numbers if n.has_dollar and n.span[0] >= m.end()]
        if not before or not after:
            cls["no_dollar_before_or_after"] += 1
            continue
        cls["has_dollar_before_and_after"] += 1
        bd = after[0]
        if abs(sum(before) - bd) <= TOL and len(before) > 1:
            cls["eq_sum_of_preceding(2plus)"] += 1
        elif any(v > 0 and LO <= bd / v <= HI for v in before):
            cls["approx_1.03_1.07_of_a_preceding"] += 1
        elif len(before) == 1 and abs(before[0] - bd) <= TOL:
            cls["eq_the_single_preceding"] += 1
        else:
            cls["neither"] += 1
    res["f9"] = dict(cls)

    # 10. adjacent explanations on one shipment: one amount each, later = 1.03..1.07 x earlier, old number not restated
    pairs = restated = 0
    for _, x in g:
        u = x.drop_duplicates(["ed", "text"]).sort_values(["ed"], kind="stable")
        rows = list(u.itertuples())
        for a, b in zip(rows, rows[1:]):
            if a.text == b.text:
                continue
            da, db = all_amount_like(a.text), all_amount_like(b.text)
            da, db = (a.dol or da), (b.dol or db)
            if len(a.dol) == 1 and len(b.dol) == 1 and a.dol[0] > 0 and LO <= b.dol[0] / a.dol[0] <= HI:
                pairs += 1
            elif len(a.dol) == 1 and len(b.dol) >= 2 and a.dol[0] in b.dol and any(
                    a.dol[0] > 0 and LO <= v / a.dol[0] <= HI for v in b.dol):
                restated += 1
    res["f10"] = {"pairs_not_restated": pairs, "pairs_restated_old_amount": restated}

    # 11. purchased transportation
    pt = df[df.text.str.contains(r"PURCHAS", regex=True)]
    first20 = int(sum(1 for d in pt.dol if d and d[0] == Decimal("20")))
    res["f11"] = {"rows": len(pt), "distinct_texts": int(pt.text.nunique()), "gid": int(pt.gid.nunique()),
                  "carriers": int(pt.Carrier.nunique()), "first_dollar_eq_20_rows": first20,
                  "named_surcharge_rows": int(pt.text.str.contains("SURCHARGE").sum()),
                  "named_fee_rows": int(pt.text.str.contains(r"\bFEE\b", regex=True).sum()),
                  "share_of_dev_rows": round(len(pt) / len(df), 3)}

    # 12. shipment amount per shipment
    sa = g.ship.first().map(float)
    res["f12"] = {"median": round(float(sa.median()), 2), "gid_below_300": int((sa < 300).sum()), "gid": len(sa)}

    # 2.1(7) + Jake's two examples: which split, and the Excel columns on them (aggregates only)
    keys = sorted(set(re.findall(r"\b\d{17}\b", BRIEF.read_text())))
    ex = []
    for k in keys:
        x = df[df.bol == k]
        e = {"in_dev": bool(len(x)), "rows": len(x)}
        if len(x):
            u = x.drop_duplicates(["ed", "text"])
            e |= {"distinct_texts": int(x.text.nunique()), "distinct_pk": int(x.PK.nunique()),
                  "shipment_amount": sorted({str(v) for v in x.ship}),
                  "per_text_delta": sorted(str(v) for v in u.delta), "per_text_invoice_amount": sorted(str(v) for v in u.inv),
                  "sum_delta_over_distinct_texts": str(sum(u.delta)), "sum_delta_over_all_rows": str(sum(x.delta)),
                  "rows_with_nonzero_dups_removed": int(sum(1 for v in x.dups if v is not None and v != 0)),
                  "distinct_event_dates": int(x.ed.nunique())}
        ex.append(e)
    res["jake_examples_in_brief_order_sorted_by_key"] = ex

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dev_facts.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
