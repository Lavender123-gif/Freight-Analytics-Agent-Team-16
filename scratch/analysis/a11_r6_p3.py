"""Task 01b-C2..C4: split a3's R6, test whether P3 is P2, and replace the 21.9% figure (aggregates + examples).

Run from repo root: `uv run python scratch/analysis/a11_r6_p3.py`
"""

import io
import re
from contextlib import redirect_stdout

import pandas as pd

from common import BALANCE_RE, EPS, EVENT_KEY, load_events, money_values, number_tokens, redact

with redirect_stdout(io.StringIO()):
    import a3_reconcile as A3  # row-level relation R0..R10, same 953 rows

df = A3.df.copy()
df["R"] = df.rel.str.extract(r"^(R\d+)")[0]
n = len(df)

# Position of each row's event inside its shipment (events ordered by Event Date; ties marked)
ev = load_events().sort_values(["SHIPMENT_GID", "ts", "Invoice Amount"])
ev["n_events"] = ev.groupby("SHIPMENT_GID").ts.transform("size")
ev["rank"] = ev.groupby("SHIPMENT_GID").cumcount()
ev["tied"] = ev.duplicated(["SHIPMENT_GID", "ts"], keep=False)
ev["prev_delta"] = ev.groupby("SHIPMENT_GID").Delta.shift()
ev["prev_text"] = ev.groupby("SHIPMENT_GID").text_norm.shift()


def position(r) -> str:
    if r.n_events == 1:
        return "only event of its shipment"
    if r.tied:
        return "multi-event shipment, same Event Date as another event"
    return "first event of a multi-event shipment" if r["rank"] == 0 else "later event of a multi-event shipment"


ev["position"] = ev.apply(position, axis=1)
df = df.merge(ev[EVENT_KEY + ["position", "prev_delta", "prev_text", "n_events"]], on=EVENT_KEY, how="left")


def relists_previous(r) -> bool:
    """Later event whose amounts before the balance include an amount from the previous event's text (or its Delta)."""
    if not r.position.startswith("later") or not isinstance(r.prev_text, str):
        return False
    prev = money_values(r.prev_text) + [round(r.prev_delta, 2)]
    return any(abs(v - u) <= EPS for v in money_values(r.text_norm)[:-1] for u in prev)
assert df.position.notna().all() and len(df) == n

# ---------------------------------------------------------------------------------------------
# C2. Split R6 (Delta = sum of $ amounts)
STATED_TOTAL = re.compile(r"=\s*\$\s?(\d+(?:\.\d+)?)")


def r6_kind(s: str, d: float) -> str:
    m = STATED_TOTAL.search(s)
    if m and abs(2 * float(m.group(1)) - d) <= EPS:
        return "R6c Delta = 2 x the text's own stated total ('a + b = c')"
    if BALANCE_RE.search(s):
        return "R6b BALANCE DUE: Delta = listed items + balance"
    return "R6a normal multi-item claim: Delta = sum of named charges"


r6 = df[df.R == "R6"].copy()
r6["kind"] = [r6_kind(s, d) for s, d in zip(r6.text_norm, r6.Delta)]
print(f"C2. R6 rows: {len(r6)}")
for k, g in r6.groupby("kind"):
    print(f"   {k}: {len(g)} rows, {g.text_norm.nunique()} distinct texts; largest carrier {int(g.carrier.eq(A3.df.carrier.value_counts().index[0]).sum())}")
    for t in g.text_norm.value_counts().index[:3]:
        print(f"      e.g. {redact(t)[:110]}")
print("   R6 x position:")
print(pd.crosstab(r6.kind.str[:4], r6.position).to_string())

# ---------------------------------------------------------------------------------------------
# C3. P3's 45 rows (a4 definition): BALANCE DUE, >=2 $ amounts, Delta != last amount, Delta = sum of amounts
def p3_rel(s: str, d: float) -> str | None:
    if not re.search(r"BALANCE DUE|ALANCE DUE", s):
        return None
    if len([x for x in number_tokens(s) if x["has_dollar"]]) < 2:
        return None
    v = money_values(s)
    if abs(v[-1] - d) <= EPS:
        return "Delta = balance (last)"
    if abs(sum(v) - d) <= EPS:
        return "Delta = sum incl. balance"
    return "other"


df["p3"] = [p3_rel(s, d) for s, d in zip(df.text_norm, df.Delta)]
p3 = df[df.p3 == "Delta = sum incl. balance"].copy()
print(f"\nC3. P3 rows where Y is an independent amount (Delta = sum incl. balance): {len(p3)} rows, "
      f"{p3.drop_duplicates(EVENT_KEY).shape[0]} events")
print(p3.position.value_counts().to_string())


def balance_ratio(s: str) -> float | None:
    """Y / (amount just before BALANCE DUE)."""
    v = money_values(s)
    return v[-1] / v[-2] if len(v) >= 2 and v[-2] > 0 else None


p3["y_over_x"] = p3.text_norm.map(balance_ratio)
p3["y_105"] = p3.y_over_x.between(1.03, 1.07)
p3["x_is_prev_delta"] = [
    pd.notna(pd_) and any(abs(v - pd_) <= EPS for v in money_values(s)[:-1]) for s, pd_ in zip(p3.text_norm, p3.prev_delta)
]
p3["relists_prev"] = p3.apply(relists_previous, axis=1)
p3["kind"] = [r6_kind(s, d)[:3] if r == "R6" else r for s, d, r in zip(p3.text_norm, p3.Delta, p3.R)]
print("   P3 rows by R6 kind x position:")
print(pd.crosstab(p3.kind, p3.position).to_string())
print("   Y is 1.03-1.07 x the amount before it, by position:")
print(p3.groupby("position").y_105.agg(["sum", "size"]).to_string())
later = p3[p3.position.str.startswith("later")]
print(f"   later events: an amount before BALANCE DUE equals the previous event's Delta: {int(later.x_is_prev_delta.sum())} / {len(later)}; "
      f"re-lists any amount of the previous event: {int(later.relists_prev.sum())} / {len(later)}")
only = p3[p3.position.str.startswith("only") & p3.kind.eq("R6b")]
print(f"   only-event R6b rows: {len(only)}; Y 1.03-1.07 x X: {int(only.y_105.sum())}; Event Dates: {sorted(only['Event Date'].str[:10].unique())}")
first = p3[~p3.position.str.startswith("later")]
print(f"   not-later events: Event Date range {first['Event Date'].min()} .. {first['Event Date'].max()}; "
      f"carrier is the largest: {int(first.carrier.eq(A3.df.carrier.value_counts().index[0]).sum())} / {len(first)}")
print(f"   largest carrier's first dispute in dev: {ev[ev.carrier == A3.df.carrier.value_counts().index[0]].ts.min()}")
for t in first.text_norm.value_counts().index[:5]:
    print(f"      e.g. {redact(t)[:110]}")

# Same view for the whole BALANCE DUE + earlier-amount template, whatever the Delta relation
tmpl = df.text_norm.str.contains(r"\$\d+(?:\.\d+)? B?ALANCE DUE \$") | df.text_norm.str.contains(r"\d BALANCE DUE \$?\d")
print(f"   all rows of the form '... $X BALANCE DUE $Y': {int(tmpl.sum())}; by position: {df[tmpl].position.value_counts().to_dict()}")

# ---------------------------------------------------------------------------------------------
# C4. Replacement for 21.9%: rows where Delta really is not this dispute's amount
R5_RULES = [
    ("weight after the amount", r"\d\s*(?:LBS|KG)\b"),
    ("ZIP / percentage after the amount", r"ZIP|%"),
    ("unit rate after the amount (@ / EACH / A DAY)", r"@|EACH|A DAY|DAYS AT"),
    ("payment history / approval numbers", r"SHORT PAID|OVERPAYMENT|APPROVED|APPROVAL|ADJUSTED OFF"),
    ("freight total after the amount", r"FREIGHT TOTAL"),
]


def r5_kind(s: str) -> str:
    for name, p in R5_RULES:
        if re.search(p, s):
            return name
    return "other"


def verdict(r) -> str:
    R = r.R
    if R in ("R0", "R1", "R2"):
        return "0 not comparable (empty, no number, or Delta = 0; see P5)"
    if R in ("R3", "R4", "R7"):
        return "1 Delta = the amount the text states"
    if R == "R5":
        return "1 Delta = the amount the text states"  # trailing numbers are not money (kinds below)
    if R == "R6":
        k = r6_kind(r.text_norm, r.Delta)
        if k.startswith("R6a"):
            return "1 Delta = the amount the text states"
        if k.startswith("R6c"):
            return "3 Delta != this dispute's amount"
        if relists_previous(r):
            return "2 Delta = this text's sum, but the sum re-lists amounts of the previous dispute"
        if r.position.startswith("later"):
            return "2c Delta = items + balance, later event, nothing re-listed"
        return "2b Delta = items + balance, no earlier event visible"
    return "3 Delta != this dispute's amount"  # R8, R9, R10


df["verdict"] = df.apply(verdict, axis=1)
print("\nC4. rows by verdict (rows / events):")
evv = df.drop_duplicates(EVENT_KEY)
for k in sorted(df.verdict.unique()):
    print(f"   {k:85s} {int((df.verdict == k).sum()):4d} ({(df.verdict == k).mean():.1%})   events {int((evv.verdict == k).sum()):4d}")
print(f"   denominator: {n} rows, {len(evv)} events")
print("   R5 kinds:", df[df.R == "R5"].text_norm.map(r5_kind).value_counts().to_dict())
print("   BALANCE DUE rows in R9 (Delta excludes the balance) by position:",
      df[(df.R == "R9") & df.text_norm.str.contains("BALANCE DUE")].position.value_counts().to_dict())
for k in ["3 Delta != this dispute's amount"]:
    g = df[df.verdict == k]
    print(f"   [{k}] by a3 relation: {g.R.value_counts().to_dict()}")
    for t, d in g.drop_duplicates("text_norm")[["text_norm", "Delta"]].itertuples(index=False):
        print(f"      d={d:.2f} | {redact(t)[:110]}")
