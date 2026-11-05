"""Small follow-up checks cited in the report (aggregates only)."""

import math
import re
from datetime import datetime

from common import EPS, load_dev, number_tokens

df = load_dev()
t = df.text_norm

# Delta = 2 x a stated number: which templates?
dbl = [(c, d) for s, d, c in zip(t, df.Delta, df.carrier)
       if abs(d) > EPS and any(abs(2 * x["value"] - d) <= EPS for x in number_tokens(s))
       and not any(abs(x["value"] - d) <= EPS for x in number_tokens(s))]
print(f"Delta = 2 x a stated number and Delta itself not stated: {len(dbl)} rows; carriers {sorted(set(c for c, _ in dbl))}")

# Driver detention: does amount = 30 * ceil((minutes - 60) / 15)?  (hypothesis, not a known contract term)
hit = tot = 0
for s, d in zip(t, df.Delta):
    if "DRIVER DETENTION" not in s:
        continue
    m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})-(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", s)
    f = "%Y-%m-%d %H:%M:%S"
    if not m:
        m = re.search(r"(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [AP]M)-(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [AP]M)", s)
        f = "%m/%d/%Y %I:%M:%S %p"
    if not m:
        continue
    mins = (datetime.strptime(m.group(2), f) - datetime.strptime(m.group(1), f)).total_seconds() / 60
    tot += 1
    hit += abs(30 * math.ceil((mins - 60) / 15) - d) <= EPS
print(f"driver detention with window: {tot}; amount = $30 per started 15 min after 60 free min: {hit}")

# Zero / negative Delta rows: what is in them?
z = df[df.Delta <= EPS]
kinds = {
    "empty text": (z.text_norm == "").sum(),
    "rate-only like '.73 FSC'": z.text_norm.str.match(r"^\.\d+( FSC)?$").sum(),
    "charge name, no amount": z.text_norm.str.contains(r"--$").sum(),
    "approved amount / overpayment": z.text_norm.str.contains("APPROVED").sum(),
}
print(f"Delta <= 0 rows: {len(z)} ->", {k: int(v) for k, v in kinds.items()})

# Within-shipment explanation added later: a bare-number row followed by an explained row with the same Delta
ev = df.drop_duplicates(["SHIPMENT_GID", "Event Date", "text_norm", "Invoice Amount", "Delta"])
later_expl = 0
for sid, p in ev.groupby("SHIPMENT_GID"):
    p = p.sort_values("Event Date")
    bare = p[p.text_norm.str.match(r"^\$?\s?[\d .]+$")]
    for when, delta in zip(bare["Event Date"], bare.Delta):
        explained = (p["Event Date"] >= when) & ((p.Delta - delta).abs() <= EPS) & ~p.text_norm.str.match(r"^\$?\s?[\d .]+$")
        later_expl += bool(explained.any())
print(f"bare-number events whose shipment has an explained event with the same Delta: {later_expl} of {ev.text_norm.str.match(r'^\$?\s?[\d .]+$').sum()}")
