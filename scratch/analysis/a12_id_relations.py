"""Task 06 part B: ID relations, multi-PK disputes, country vs US/CAN, fields for CO share.

Dev split only. Prints aggregates only (no row values). Never reads the test split,
the raw Excel, or the `Invoice Dups Removed` column for duplicate reasoning (B3).
Run from repo root: `uv run python scratch/analysis/a12_id_relations.py`.
"""

from collections import Counter
from datetime import datetime

import pandas as pd

from common import EPS, load_dev

df = load_dev()
df["row"] = range(len(df))
N = len(df)
CA = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


print("=== B1 ID cardinalities ===")
print(f"rows {N}; shipments {df.SHIPMENT_GID.nunique()}; PK null {df.PK.isna().sum()}")
pairs = [("SHIPMENT_GID", "PK"), ("SHIPMENT_GID", "Carrier Invoice"), ("PK", "Invoice/Bill ID"),
         ("PK", "Carrier Invoice"), ("SHIPMENT_GID", "SAP BOL"), ("SHIPMENT_GID", "Shipment Number"),
         ("SHIPMENT_GID", "Carrier"), ("Carrier Invoice", "Carrier")]
for a, b in pairs:
    f = df.dropna(subset=[a, b])
    a2b = f.groupby(a)[b].nunique()
    b2a = f.groupby(b)[a].nunique()
    print(f"{a} -> #{b}: {dict(sorted(Counter(a2b).items()))} | {b} -> #{a}: {dict(sorted(Counter(b2a).items()))}")
print("PK == 'PPGTM.' + Invoice/Bill ID:",
      (df.dropna(subset=["PK"]).PK == "PPGTM." + df.dropna(subset=["PK"])["Invoice/Bill ID"]).all())
print("rows per PK:", dict(sorted(Counter(df.groupby("PK").size()).items())))
print("rows per shipment:", dict(sorted(Counter(df.groupby("SHIPMENT_GID").size()).items())))
print("PKs per shipment (incl. 0 = all null):",
      dict(sorted(Counter(df.groupby("SHIPMENT_GID").PK.nunique()).items())))
sn = df.dropna(subset=["Shipment Number"]).groupby("Shipment Number").SHIPMENT_GID.nunique()
print("shipments per 'Shipment Number':", dict(sorted(Counter(sn).items())))
# carrier invoice repeated across carriers?
ci_car = df.groupby("Carrier Invoice").Carrier.nunique()
print("carriers per Carrier Invoice:", dict(Counter(ci_car)))
# Is the shipment-level unit stable? Invoice Amount/Shipment Amount per shipment
sa = df.groupby("SHIPMENT_GID")["Shipment Amount"].nunique()
print("distinct Shipment Amount per shipment:", dict(sorted(Counter(sa).items())))
ia = df.groupby("SHIPMENT_GID")["Invoice Amount"].nunique()
print("distinct Invoice Amount per shipment:", dict(sorted(Counter(ia).items())))
ok = ((df["Invoice Amount"] - df["Shipment Amount"] - df["Delta"]).abs() <= EPS).mean()
print(f"Invoice Amount = Shipment Amount + Delta on {ok:.1%} of rows")

print("\n=== B2 same dispute under several PKs ===")
core = ["SHIPMENT_GID", "text_norm", "Delta", "Event Date"]
g = df.groupby(core, dropna=False)
sz = g.size()
npk = g.PK.nunique()
multi = sz[sz > 1]
print(f"groups (shipment,text,Delta,Event Date): {len(sz)}; with >1 row: {len(multi)}; surplus rows {int((sz - 1).sum())}")
print("group size distribution (>1):", dict(sorted(Counter(multi).items())))
only_pk = [(k, s) for k, s in multi.items() if npk[k] == s]
print(f"groups where every row has a distinct PK (only PK differs): {len(only_pk)}; "
      f"sizes {dict(sorted(Counter(s for _, s in only_pk).items()))}; rows {sum(s for _, s in only_pk)}")
same_pk = [(k, s) for k, s in multi.items() if npk[k] < s]
print(f"groups with repeated rows sharing PK or null PK: {len(same_pk)}; sizes {dict(Counter(s for _, s in same_pk))}")
# Which columns other than PK/Invoice/Bill ID vary inside multi groups?
other_cols = [c for c in df.columns if c not in core + ["PK", "Invoice/Bill ID", "row", "text", "Descritipion", "carrier"]]
vary = Counter()
for k in multi.index:
    part = df.loc[g.indices[k]]
    for c in other_cols:
        if part[c].astype(str).nunique() > 1:
            vary[c] += 1
print("columns (besides PK) that vary within these groups:", dict(vary))
# Shipments in the multi-PK structure: rows = events x PKs?
cross = Counter()
for sid, part in df.groupby("SHIPMENT_GID"):
    k = part.PK.nunique()
    if k > 1:
        e = part.groupby(["Event Date", "text_norm", "Delta"]).ngroups
        cross["rows==events*PKs" if len(part) == e * k else "not cross"] += 1
        cross[f"PKs={k}"] += 1
print("multi-PK shipments:", dict(cross))

# PK date (first 8 digits of Invoice/Bill ID) vs Event Date
f = df.dropna(subset=["PK"]).copy()
f["pk_date"] = pd.to_datetime(f["Invoice/Bill ID"].str[:8], format="%Y%m%d", errors="coerce")
f["ev"] = pd.to_datetime(f["Event Date"])
print(f"PK prefix parses as date: {f.pk_date.notna().sum()} / {len(f)}")
f["lag_days"] = (f.pk_date - f.ev.dt.normalize()).dt.days
print("PK date - Event date (days), describe:", f.lag_days.describe().round(1).to_dict())
bins = pd.cut(f.lag_days, [-10_000, -31, -1, 0, 7, 30, 60, 10_000],
              labels=["<-30", "-30..-1", "same day", "1..7", "8..30", "31..60", ">60"])
print("lag bins (all PK rows):", bins.value_counts().reindex(bins.cat.categories).to_dict())
late = f.lag_days > 0
print(f"rows whose PK date is after the Event Date: {late.sum()} / {len(f)}; "
      f"> 30 days after: {(f.lag_days > 30).sum()}")
in_multi = f.set_index(core).index.isin([k for k, _ in only_pk])
print(f"   among rows in 'only PK differs' groups: after {(late & in_multi).sum()} / {in_multi.sum()}, "
      f">30d {((f.lag_days > 30) & in_multi).sum()}")
print(f"   among other PK rows: after {(late & ~in_multi).sum()} / {(~in_multi).sum()}, "
      f">30d {((f.lag_days > 30) & ~in_multi).sum()}")
# per multi-PK group: how many PKs late
late_counts = Counter()
for k, s in only_pk:
    part = f.set_index(core).loc[[k]]
    late_counts[f"{int((part.lag_days > 30).sum())}/{s} late>30d"] += 1
print("per 'only PK differs' group, PKs dated >30d after event:", dict(late_counts))

print("\n=== B2c the 45-row merge (5 fields) ===")
five = ["SHIPMENT_GID", "Event Date", "text_norm", "Invoice Amount", "Delta"]
e5 = df.groupby(five, dropna=False).ngroups
e4 = df.groupby(core, dropna=False).ngroups
print(f"distinct by 5 fields {e5} (surplus {N - e5}); by (shipment,text,Delta,Event Date) {e4} (surplus {N - e4})")
# are the only-PK-differ groups merged by the five-field key? yes iff Invoice Amount constant in group
merged = sum(1 for k, _ in only_pk if df.loc[g.indices[k], "Invoice Amount"].nunique() == 1)
print(f"'only PK differs' groups that the 5-field key also collapses: {merged} / {len(only_pk)}")
# events per shipment (after collapse) and shipments affected
ev = df.drop_duplicates(five)
per_ship = ev.groupby("SHIPMENT_GID").size()
aff_ship = {k[0] for k, _ in only_pk} | {k[0] for k, _ in same_pk}
print(f"shipments touched by any multi-row group: {len(aff_ship)}; "
      f"their rows {df.SHIPMENT_GID.isin(aff_ship).sum()}; their collapsed events {ev.SHIPMENT_GID.isin(aff_ship).sum()}")

print("\n=== B4 country from province vs US/CAN ===")
def ctry(s):
    if pd.isna(s):
        return "NA"
    return "CA" if s.strip().upper() in CA else "US"
df["o"] = df["Source State"].map(ctry)
df["d"] = df["Destination State"].map(ctry)
print("US/CAN values:", df["US/CAN"].value_counts().to_dict())
print("origin->dest:", Counter(zip(df.o, df.d)))
derived = df.apply(lambda r: "CAN" if (r.o == "CA" or r.d == "CA") else "US", axis=1)
mism = (derived != df["US/CAN"]).sum()
print(f"US/CAN disagrees with 'touches Canada' rule: {mism} / {N} ({mism / N:.1%})")
print(f"pure CA->CA rows with US/CAN=US: {((df.o == 'CA') & (df.d == 'CA') & (df['US/CAN'] == 'US')).sum()}")
print("state values not recognised:", sorted({s for s in pd.concat([df['Source State'], df['Destination State']]).dropna()
                                              if s.strip().upper() not in CA} )[:60])

print("\n=== B5 fields for CO share ===")
for c in ["Invoice Amount", "Shipment Amount", "Delta"]:
    s = df[c]
    print(f"{c}: null {s.isna().sum()}, zero {(s.abs() <= EPS).sum()}, negative {(s < -EPS).sum()}")
print("Shipment Amount constant within shipment:", (sa == 1).sum(), "/", len(sa))
ratio = (df.Delta / df["Shipment Amount"]).replace([float("inf")], float("nan"))
print("Delta / Shipment Amount quantiles:", ratio.quantile([.05, .25, .5, .75, .95]).round(3).to_dict())
print(f"Delta > Shipment Amount: {(df.Delta > df['Shipment Amount']).sum()}")
# in multi-event shipments, does Invoice Amount look cumulative (= previous invoice + delta)?
ev = ev.sort_values(["SHIPMENT_GID", "Event Date"]).rename(columns={"Invoice Amount": "inv"})
cum = Counter()
for sid, part in ev.groupby("SHIPMENT_GID"):
    if len(part) < 2:
        continue
    for a, b in zip(part.iloc[:-1].itertuples(), part.iloc[1:].itertuples()):
        if abs(b.inv - a.inv) <= EPS:
            cum["same Invoice Amount"] += 1
        else:
            cum["Invoice Amount changes"] += 1
print("consecutive events in a shipment:", dict(cum))

print("\n=== B3 extra signals for duplicate causes ===")
from common import number_tokens  # noqa: E402
ev5 = df.drop_duplicates(five).copy()
# (a) same $ amount written twice within one text (possible in-invoice double listing or 'keep + balance')
def rep_money(t):
    v = [round(x["value"], 2) for x in number_tokens(t) if x["has_dollar"]]
    return len(v) != len(set(v))
ev5["rep"] = ev5.text_norm.map(rep_money)
print(f"events whose text repeats the same $ amount: {ev5.rep.sum()} / {len(ev5)}")
# (b) events in same shipment with same Delta but different text / time
same_delta = ev5.groupby(["SHIPMENT_GID", "Delta"]).agg(n=("text_norm", "size"), texts=("text_norm", "nunique"),
                                                        times=("Event Date", "nunique"))
sd = same_delta[same_delta.n > 1]
print(f"(shipment, Delta) with >1 event: {len(sd)}; identical text {(sd.texts == 1).sum()}, different text {(sd.texts > 1).sum()}")
# (c) same-minute siblings within a shipment (different events, same Event Date)
sib = ev5.groupby(["SHIPMENT_GID", "Event Date"]).size()
print(f"(shipment, Event Date) with >1 distinct event: {(sib > 1).sum()}")
# (d) the 5 same-PK/null-PK repeat groups: PK null?
for k, s in same_pk:
    part = df.loc[g.indices[k]]
    print("  same-PK group: PK null rows", int(part.PK.isna().sum()), "of", s, "| distinct PK", part.PK.nunique())
# (e) same text + same Delta at different Event Date (re-submission)
rs = ev5.groupby(["SHIPMENT_GID", "text_norm", "Delta"]).agg(n=("Event Date", "nunique"))
print(f"same shipment+text+Delta at different Event Dates: {(rs.n > 1).sum()} groups")
