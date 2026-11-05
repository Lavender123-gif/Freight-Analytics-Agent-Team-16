"""Task 01b-A: can Event Date be used to order disputes within a shipment? (aggregates only)

Run from repo root: `uv run python scratch/analysis/a8_event_date.py`
"""

import re

import pandas as pd

from common import load_dev

df = load_dev()
EVENT_KEY = ["SHIPMENT_GID", "Event Date", "text_norm", "Invoice Amount", "Delta"]

# 1. Format and precision
raw = df["Event Date"]
fmt_ok = raw.str.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
ed = pd.to_datetime(raw, format="%Y-%m-%d %H:%M:%S")
print(f"rows {len(df)}; Event Date matches 'YYYY-MM-DD HH:MM:SS': {fmt_ok.sum()}; null: {raw.isna().sum()}")
print(f"rows with non-zero seconds: {(ed.dt.second != 0).sum()}  -> precision is one minute")
print(f"range: {ed.min()} .. {ed.max()}")
print("hour of day:", ed.dt.hour.value_counts().sort_index().to_dict())
night = ed.dt.hour.between(0, 7)
print("rows at 00:00-07:59 by carrier:", df[night].carrier.value_counts().to_dict())
print("weekday (0=Mon):", ed.dt.dayofweek.value_counts().sort_index().to_dict())

# 2. Events and ties within a shipment
ev = df.drop_duplicates(EVENT_KEY).copy()
ev["ts"] = pd.to_datetime(ev["Event Date"])
per_ship = ev.groupby("SHIPMENT_GID").size()
multi_ids = per_ship[per_ship > 1].index
print(f"\nevents {len(ev)}; shipments with >1 event: {len(multi_ids)}; events in them: {per_ship[per_ship > 1].sum()}")
tie = ev.groupby(["SHIPMENT_GID", "Event Date"]).size()
tie = tie[tie > 1]
print(f"(shipment, Event Date) groups holding >1 distinct event: {len(tie)}; events involved: {tie.sum()}; "
      f"shipments affected: {tie.index.get_level_values(0).nunique()}")
tie_ev = ev.set_index(["SHIPMENT_GID", "Event Date"]).loc[tie.index].reset_index()
same_text = tie_ev.groupby(["SHIPMENT_GID", "Event Date"]).text_norm.nunique().eq(1).sum()
print(f"  of these groups, same text (differ only in Invoice Amount / Delta): {same_text}; different text: {len(tie) - same_text}")
# In a tie, exactly one event carries the non-zero 'Invoice Dups Removed'? (hint of separate invoice lines)
nz_in_tie = tie_ev.assign(nz=tie_ev["Invoice Dups Removed"].abs() > 0.005).groupby(["SHIPMENT_GID", "Event Date"]).nz.sum()
print(f"  tie groups by count of events with non-zero 'Invoice Dups Removed': {nz_in_tie.value_counts().to_dict()}")
ships_with_tie = tie.index.get_level_values(0).unique()
print(f"multi-event shipments fully orderable (no tie): {len(set(multi_ids) - set(ships_with_tie))} / {len(multi_ids)}")

# 3. Is it one export time, or per-event?
ts_ships = ev.groupby("Event Date").SHIPMENT_GID.nunique()
print(f"\ndistinct timestamps {len(ts_ships)} for {len(ev)} events; timestamps shared by >1 shipment: {(ts_ships > 1).sum()} "
      f"(max {ts_ships.max()} shipments)")

# 4. Dates written inside the text vs Event Date. If Event Date were the time the text was written,
#    no date in the text could lie in the future of Event Date.
FULL = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
MD = re.compile(r"(?<![/\d])(\d{1,2})/(\d{1,2})(?![/\d])|(?<![/\d])(\d{1,2})/(\d{1,2})(?=/\d{1,2}(?![/\d]))")


def text_dates(text: str, t: pd.Timestamp) -> list[pd.Timestamp]:
    out = []
    for m in FULL.finditer(text):
        try:
            if m.group(1):
                out.append(pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3))))
            else:
                y = int(m.group(6))
                out.append(pd.Timestamp(y + 2000 if y < 100 else y, int(m.group(4)), int(m.group(5))))
        except ValueError:
            pass
    rest = FULL.sub(" ", text)
    for m in MD.finditer(rest):
        mo, da = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        try:
            d = pd.Timestamp(t.year, int(mo), int(da))  # no year written: take Event Date's year,
        except ValueError:
            continue
        if (d - t).days > 180:  # ...shifting across New Year only when the gap would exceed half a year
            d -= pd.DateOffset(years=1)
        elif (t - d).days > 180:
            d += pd.DateOffset(years=1)
        out.append(d)
    return out


ev["multi"] = ev.SHIPMENT_GID.isin(multi_ids)
rows = []
for text, t, mult in zip(ev.text_norm, ev.ts, ev.multi):
    ds = text_dates(text, t)
    if ds:
        rows.append(((max(ds) - t.normalize()).days, mult))
lag = pd.DataFrame(rows, columns=["days_after", "multi"])
after = lag.days_after > 1  # allow one day for time-zone shifts
print(f"\nevents whose text contains a date: {len(lag)}")
print(f"  latest text date is >1 day AFTER Event Date: {int(after.sum())} "
      f"(in multi-event shipments: {int((after & lag.multi).sum())}); within +-1 day: {int(lag.days_after.abs().le(1).sum())}; "
      f">1 day before: {int((lag.days_after < -1).sum())}")
print(f"  days after, for those: {sorted(lag.days_after[after].tolist())}")
pay_after = 0
for text, t in zip(ev.text_norm, ev.ts):
    if re.search(r"PYMT ADVICE|PAYMENT ADVICE", text):
        ds = text_dates(text, t)
        pay_after += bool(ds) and max(ds) > t
print(f"  texts citing a payment advice dated after Event Date: {pay_after}")
# Clock pattern: share of events at an exact round hour, by carrier (date-only entry converted to a timestamp?)
ev["round_hour"] = ev.ts.dt.minute.eq(0)
rh = ev.groupby("carrier").round_hour.agg(["sum", "size"])
print("events at an exact HH:00, by carrier (only carriers with any):", rh[rh["sum"] > 0].to_dict("index"))

# 5. Gaps between consecutive events of the same shipment
m = ev[ev.SHIPMENT_GID.isin(multi_ids)].sort_values(["SHIPMENT_GID", "ts"])
gaps = m.groupby("SHIPMENT_GID").ts.diff().dropna().dt.total_seconds() / 86400
print(f"\ngaps between consecutive events (days): n {len(gaps)}, zero {int((gaps == 0).sum())}, "
      f"<1 day {int(((gaps > 0) & (gaps < 1)).sum())}, median {gaps.median():.1f}, max {gaps.max():.0f}")
print(f"  gaps that are an exact multiple of 7 days to the minute (>0): {int(((gaps > 0) & ((gaps * 1440).round() % (7 * 1440) == 0)).sum())}")

# 6. Shipment number order vs first Event Date (shipments are numbered on creation)
first = ev.groupby("SHIPMENT_GID").ts.min()
num = pd.Series(first.index.str.extract(r"(\d+)\D*$")[0].astype(int).values, index=first.index)
print(f"\nSpearman (Pearson on ranks)(shipment number, first Event Date) = {num.rank().corr(first.rank()):.3f}")

# 7. Event Date vs Dispute Status: does a later event ever carry an 'earlier-stage' status in a way that suggests review time?
print("\nDispute Status by month (events):")
print(pd.crosstab(ev.ts.dt.to_period("Q"), ev["Dispute Status"].str.replace("PPGTM.PMT_", "", regex=False)).to_string())

# 8. Direction test: does the later event (by Event Date) build on the earlier one more often than the reverse?
#    fwd: the later text quotes the earlier Delta, the earlier text does not quote the later Delta.
#    bwd: the mirror image. Only pairs whose two Deltas differ are informative.
from common import number_tokens  # noqa: E402


def nums(s: str) -> set[float]:
    return {round(x["value"], 2) for x in number_tokens(s)}


fwd = bwd = both = neither = same_delta = 0
mm = ev[ev.multi].sort_values(["SHIPMENT_GID", "ts"])
for sid, p in mm.groupby("SHIPMENT_GID"):
    p = p.reset_index(drop=True)
    for i in range(1, len(p)):
        a, b = p.iloc[i - 1], p.iloc[i]
        if a.ts == b.ts:
            continue  # tie: no order to test
        da, db = round(a.Delta, 2), round(b.Delta, 2)
        if abs(da - db) <= 0.005:
            same_delta += 1
            continue
        f, r = da in nums(b.text_norm), db in nums(a.text_norm)
        if f and not r:
            fwd += 1
        elif r and not f:
            bwd += 1
        elif f and r:
            both += 1
        else:
            neither += 1
print(f"\nadjacent ordered pairs with different Delta: later quotes earlier Delta only {fwd}; "
      f"earlier quotes later Delta only {bwd}; both {both}; neither {neither}; (pairs with equal Delta skipped: {same_delta})")
