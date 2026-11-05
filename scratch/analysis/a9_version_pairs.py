"""Task 01b-B: relation between consecutive dispute events of the same shipment (aggregates + examples).

Run from repo root: `uv run python scratch/analysis/a9_version_pairs.py`
Examples are printed with emails masked only; person names are masked by hand in the report.
"""

import re

import pandas as pd

from common import (BALANCE_RE, EPS, PAY_RE, adjacent_pairs, families, load_events, money_values, redact)

ev = load_events()
P = adjacent_pairs(ev)
LARGEST = ev.carrier.value_counts().index[0]

REASON_RE = re.compile(r"PER CONTRACT|FACTOR|SHOULD APPLY|NOTIFIED|AS PER|TERMS AND CONDITIONS|BOL|CANADIAN SHIPMENT|MUST PAY")


def has_pay(s: str) -> bool:
    return bool(PAY_RE.search(s) or BALANCE_RE.search(s))


def label(r: pd.Series) -> str:
    """Primary relation of an ordered pair (earlier a, later b). First matching rule wins."""
    ta, tb = r.text_norm_a, r.text_norm_b
    fa, fb = families(ta), families(tb)
    da, db = r.Delta_a, r.Delta_b
    same_amt = abs(da - db) <= EPS
    pay_added = has_pay(tb) and not has_pay(ta)
    if ta == tb:
        return "identical"
    if fa and fb and not (fa & fb):
        if same_amt and abs(r["Invoice Amount_a"] - r["Invoice Amount_b"]) <= EPS:
            return "other: same amount, different charge name"
        return "unrelated new dispute"
    if fa and fb > fa:
        return "added charge"
    if fb and fa > fb:
        return "removed charge"
    if same_amt:
        if not fa and fb:
            return "elaboration (same amount, fuller text)"
        if pay_added:
            return "payment/balance wording added (same amount)"
        return "other: same amount, reworded without new information"
    if da > EPS and 1.03 <= db / da <= 1.07:
        return "amount change: ~5% (replaces earlier amount)"
    new = [v for v in money_values(tb) if all(abs(v - u) > EPS for u in money_values(ta))]
    if da > EPS and any(1.03 <= v / da <= 1.07 for v in new) and abs(db - da - sum(new)) <= EPS:
        return "amount change: earlier amount kept + new ~5%-higher balance"
    return "amount change: other"


P["label"] = P.apply(label, axis=1)
P["pay_added"] = [has_pay(b) and not has_pay(a) for a, b in zip(P.text_norm_a, P.text_norm_b)]
P["largest"] = P.carrier_a.eq(LARGEST)
O = P[~P.tie]  # ordered pairs
T = P[P.tie]

print(f"events {len(ev)}; adjacent pairs {len(P)} (ordered {len(O)}, same Event Date {len(T)})")
print(f"pairs where Shipment Amount differs: {(P['Shipment Amount_a'] != P['Shipment Amount_b']).sum()}")
print("\n1. relation of ordered pairs (rows: label; columns: largest carrier vs others)")
print(pd.crosstab(O.label, O.largest.map({True: "largest", False: "others"}), margins=True).to_string())
print(f"\n   'payment/balance wording added' as a secondary flag on ordered pairs: {int(O.pay_added.sum())}; by label:")
print(O[O.pay_added].label.value_counts().to_string())
print("   wording added (later version), counted on flagged pairs:",
      {"BALANCE DUE/OWING": int(O[O.pay_added].text_norm_b.map(lambda s: bool(BALANCE_RE.search(s))).sum()),
       "paid/unpaid/owe": int(O[O.pay_added].text_norm_b.map(lambda s: bool(PAY_RE.search(s))).sum())})

# Ties: no order; describe the unordered relation.
def tie_rel(r):
    fa, fb = families(r.text_norm_a), families(r.text_norm_b)
    if not (fa & fb):
        return "disjoint charges"
    if fa == fb:
        return "same charges"
    if fa < fb or fb < fa:
        return "one charge set contains the other"
    return "overlapping charge sets"
print("\n   same-Event-Date pairs, unordered relation:", T.apply(tie_rel, axis=1).value_counts().to_dict())

# 2. What changed, by label
print("\n2. differences (ordered pairs)")
for lab, g in O.groupby("label"):
    added, removed = {}, {}
    for a, b in zip(g.text_norm_a, g.text_norm_b):
        for f in families(b) - families(a):
            added[f] = added.get(f, 0) + 1
        for f in families(a) - families(b):
            removed[f] = removed.get(f, 0) + 1
    reason = sum(bool(REASON_RE.search(b)) and not REASON_RE.search(a) for a, b in zip(g.text_norm_a, g.text_norm_b))
    more_nums = sum(len(money_values(b)) > len(money_values(a)) for a, b in zip(g.text_norm_a, g.text_norm_b))
    ratio = (g.Delta_b / g.Delta_a.where(g.Delta_a.abs() > EPS)).dropna()
    print(f"  [{lab}] n={len(g)}; families added {added}; removed {removed}; "
          f"reason/justification added {reason}; more amounts in later text {more_nums}; "
          f"Delta_b/Delta_a median {ratio.median():.3f}" if len(ratio) else "")
    print(f"     gap days: median {((g.ts_b - g.ts_a).dt.total_seconds() / 86400).median():.1f}")
    for r in g.head(3).itertuples():
        print(f"     e.g. [{r.Delta_a:.2f}] {redact(r.text_norm_a)[:100]}  =>  [{r.Delta_b:.2f}] {redact(r.text_norm_b)[:100]}")

# 3. Dispute Status
print("\n3. Dispute Status")
m = ev[ev.SHIPMENT_GID.isin(P.SHIPMENT_GID)]
print(f"   multi-event shipments whose events carry more than one status: "
      f"{(m.groupby('SHIPMENT_GID').status.nunique() > 1).sum()} / {m.SHIPMENT_GID.nunique()}")
print(f"   pairs with status_a != status_b: {(P.status_a != P.status_b).sum()} / {len(P)}")
print(pd.crosstab(O.label, O.status_a).to_string())
MOD = ~O.label.isin(["identical", "unrelated new dispute"])
dec = O.status_a.str.contains("DECLINED")
print(f"   ordered pairs whose earlier event is DECLINED: {int(dec.sum())}; of these a modified version "
      f"(not identical, not unrelated): {int((dec & MOD).sum())} ({(dec & MOD).sum() / max(dec.sum(), 1):.0%})")
print(f"   ordered pairs whose earlier event is not DECLINED: {int((~dec).sum())}; modified: {int((~dec & MOD).sum())} "
      f"({(~dec & MOD).sum() / max((~dec).sum(), 1):.0%})")
evd = ev.status.str.contains("DECLINED")
later_exists = ev.groupby("SHIPMENT_GID").ts.transform("max") > ev.ts
print(f"   DECLINED events: {int(evd.sum())}; followed by a later event of the same shipment: {int((evd & later_exists).sum())}")
print(f"   non-DECLINED events: {int((~evd).sum())}; followed by a later event: {int((~evd & later_exists).sum())}")
print(f"   ordered pairs of the largest carrier whose status is DECLINED: {int((dec & O.largest).sum())} / {int(O.largest.sum())}")
lw = ev[ev.carrier == LARGEST].ts.dt.to_period("W").value_counts().sort_index()
print(f"   largest carrier, events per week: {lw.to_dict()}")
lp = O[O.largest].ts_b.dt.date.value_counts()
print(f"   largest carrier, later versions by date (top 3): {lp.head(3).to_dict()} of {int(O.largest.sum())}")
print(f"   unrelated pairs with a gap under 1 day: {int(((O.ts_b - O.ts_a).dt.total_seconds() < 86400)[O.label.eq('unrelated new dispute')].sum())} / {int(O.label.eq('unrelated new dispute').sum())}")
print(f"   DECLINED events by carrier group: {ev[evd].carrier.eq(LARGEST).map({True: 'largest', False: 'others'}).value_counts().to_dict()}")

# 4. Usable sample sizes for the three ground-truth uses
print("\n4. sample sizes for ground-truth uses (ordered pairs)")
crit = O.label.isin(["elaboration (same amount, fuller text)", "added charge", "removed charge",
                     "payment/balance wording added (same amount)"]) | O.label.str.startswith("amount change")
print(f"   (a) later version adds or changes something (candidate 'what was asked for'): {int(crit.sum())}; "
      f"of which largest carrier {int((crit & O.largest).sum())}; distinct later texts {O[crit].text_norm_b.nunique()}")
expl = O.label.eq("elaboration (same amount, fuller text)") | (
    O.label.eq("payment/balance wording added (same amount)"))
print(f"   (b) same Delta and the later text names what the earlier text left unnamed: "
      f"{int(O.label.eq('elaboration (same amount, fuller text)').sum())}; same Delta with only wording changes: "
      f"{int(O.label.isin(['payment/balance wording added (same amount)', 'other: same amount, reworded without new information']).sum())}")
print(f"   (c) relation labels: {len(O)} ordered pairs, {O.label.nunique()} labels, "
      f"{O.groupby('label').carrier_a.nunique().to_dict()} carriers per label")
