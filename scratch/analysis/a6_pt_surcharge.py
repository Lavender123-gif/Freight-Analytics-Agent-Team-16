"""What does the purchase(d)-transportation amount look like? (aggregates only)

Rows whose text names only the purchase(d)-transportation charge with a single
amount equal to Delta. Looks for a flat fee and/or a constant ratio to the
planned Shipment Amount.
"""

import numpy as np

from common import EPS, load_dev, number_tokens

df = load_dev()
t = df.text_norm
pt_only = t.str.match(r"^PUR?CH?A?R?H?SE?D? (?:TRANSPORTATION|TRANSP)(?: SURCHARGE| SURCHARG| FEE)?\s*-?\s*\$?\s?[\d.]+$")
rows = []
for s, d, ship in zip(t[pt_only], df.Delta[pt_only], df["Shipment Amount"][pt_only]):
    v = [x["value"] for x in number_tokens(s)]
    if len(v) == 1 and abs(v[0] - d) <= EPS:
        rows.append((v[0], ship))
amt = np.array([r[0] for r in rows])
ship = np.array([r[1] for r in rows])
print(f"PT-only rows with amount = Delta: {len(rows)}")
print(f"  exactly $20.00: {(abs(amt - 20) <= EPS).sum()}; other amounts: {(abs(amt - 20) > EPS).sum()}")
print(f"  amount range {amt.min():.2f} to {amt.max():.2f}")
other = abs(amt - 20) > EPS
ratio = amt[other] / ship[other]
print(f"  non-$20 rows: amount / Shipment Amount quantiles (10/50/90%): {np.quantile(ratio, [0.1, 0.5, 0.9]).round(4)}")
flat = ~other
print(f"  $20 rows: Shipment Amount quantiles (10/50/90%): {np.quantile(ship[flat], [0.1, 0.5, 0.9]).round(2)}")
print(f"  non-$20 rows: Shipment Amount quantiles (10/50/90%): {np.quantile(ship[other], [0.1, 0.5, 0.9]).round(2)}")
print(f"  share of non-$20 rows with amount/ship within 0.25-0.35: {((ratio > 0.25) & (ratio < 0.35)).mean():.1%}")
