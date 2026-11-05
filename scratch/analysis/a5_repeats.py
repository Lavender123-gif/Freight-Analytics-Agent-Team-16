"""Repeated rows, dispute events, and how Delta evolves within a shipment (aggregates only)."""

from common import EPS, load_dev, number_tokens

df = load_dev()
n = len(df)

# 1. Rows that differ only by PK (export join artifact?)
event_key = ["SHIPMENT_GID", "Event Date", "text_norm", "Invoice Amount", "Delta"]
events = df.groupby(event_key, dropna=False)
sizes = events.size()
print(f"rows {n}; distinct (shipment, Event Date, text, Invoice Amount, Delta) events: {len(sizes)}")
print("rows per event:", sizes.value_counts().sort_index().to_dict())
pk_per_event = events["PK"].nunique()
dup_same_pk = (sizes > pk_per_event.clip(lower=1)).sum()
print(f"events whose extra rows all carry different PKs: {((sizes > 1) & (sizes == pk_per_event)).sum()}")
print(f"events with repeated rows that share the same PK (or empty PK): {dup_same_pk}")
print(f"surplus rows that are pure repeats of an event: {n - len(sizes)} ({(n - len(sizes)) / n:.1%})")

# Shipment x PK cross product check: for multi-PK shipments, is rows = events x PKs?
g = df.groupby("SHIPMENT_GID")
cross = 0
multi_pk = 0
for sid, part in g:
    k = part.PK.nunique()
    if k > 1:
        multi_pk += 1
        e = part.groupby(["Event Date", "text_norm", "Invoice Amount", "Delta"]).ngroups
        if len(part) == e * k:
            cross += 1
print(f"shipments with >1 PK: {multi_pk}; of these rows == events x PKs: {cross}")

# 2. Invoice Dups Removed: one non-zero row per shipment?
nz = df.assign(nz=df["Invoice Dups Removed"].abs() > EPS).groupby("SHIPMENT_GID").nz.sum()
print("non-zero 'Invoice Dups Removed' rows per shipment:", nz.value_counts().sort_index().to_dict())

# 3. Distinct dispute events per shipment (after collapsing repeats)
ev = df.drop_duplicates(event_key)
per_ship = ev.groupby("SHIPMENT_GID").size()
print(f"\ndistinct events {len(ev)}; shipments with >1 distinct event: {(per_ship > 1).sum()}")
print("distinct events per shipment:", per_ship.value_counts().sort_index().to_dict())

# 4. Within shipments with >1 event: does Invoice Amount change between events?
multi = ev[ev.SHIPMENT_GID.isin(per_ship[per_ship > 1].index)].sort_values(["SHIPMENT_GID", "Event Date"])
inv_changes = multi.groupby("SHIPMENT_GID")["Invoice Amount"].nunique()
print(f"multi-event shipments where Invoice Amount differs across events: {(inv_changes > 1).sum()} / {len(inv_changes)}")

# 5. Second-and-later events: is Delta = the event's own stated amount, or cumulative?
later = multi.groupby("SHIPMENT_GID").apply(lambda p: p.iloc[1:], include_groups=False).reset_index(level=0)
first = multi.groupby("SHIPMENT_GID").head(1).set_index("SHIPMENT_GID")
cat = {"single/last number = Delta": 0, "sum of numbers = Delta": 0, "other": 0}
grew_5pct = 0
same_text_family = 0
for r in later.itertuples():
    vals = [t["value"] for t in number_tokens(r.text_norm)]
    if vals and abs(vals[-1] - r.Delta) <= EPS:
        cat["single/last number = Delta"] += 1
    elif vals and abs(sum(vals) - r.Delta) <= EPS:
        cat["sum of numbers = Delta"] += 1
    else:
        cat["other"] += 1
print(f"\nlater events in multi-event shipments: {len(later)}", cat)

# 6. Re-billing with an implicit ~5% uplift: later 'balance due' amount vs earlier Delta
uplift = []
for sid, p in multi.groupby("SHIPMENT_GID"):
    p = p.sort_values("Event Date")
    d0 = p.Delta.iloc[0]
    for r in p.iloc[1:].itertuples():
        vals = [t["value"] for t in number_tokens(r.text_norm)]
        if d0 > EPS and vals:
            uplift.append(vals[-1] / d0)
near5 = sum(1 for u in uplift if 1.03 <= u <= 1.07)
print(f"later events whose last stated number is 1.03-1.07 x the first event's Delta: {near5} / {len(uplift)}")
