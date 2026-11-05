"""Task 01b-C1: is the later event's Delta cumulative? Direct test on ordered version pairs (aggregates only).

Run from repo root: `uv run python scratch/analysis/a10_delta_cumulative.py`
"""

import io
from contextlib import redirect_stdout

import pandas as pd

from common import EPS, money_values

with redirect_stdout(io.StringIO()):
    import a9_version_pairs as A  # reuse the pair table and relation labels

O = A.O.copy()


def close(a: float, b: float, tol: float = EPS) -> bool:
    return abs(a - b) <= tol


rows = []
for r in O.itertuples():
    va, vb = money_values(r.text_norm_a), money_values(r.text_norm_b)
    new = [v for v in vb if all(not close(v, u) for u in va)]
    rows.append({"va": va, "vb": vb, "new": new})
X = pd.DataFrame(rows, index=O.index)
O = O.join(X)
O["d_inv"] = O["Invoice Amount_b"] - O["Invoice Amount_a"]

O["t_own_last"] = [bool(vb) and close(vb[-1], db) for vb, db in zip(O.vb, O.Delta_b)]
O["t_own_sum"] = [bool(vb) and close(sum(vb), db) for vb, db in zip(O.vb, O.Delta_b)]
O["t_own"] = O.t_own_last | O.t_own_sum
O["t_prev_plus_new"] = [bool(n) and close(da + sum(n), db) for n, da, db in zip(O.new, O.Delta_a, O.Delta_b)]
O["t_unchanged"] = [close(da, db) for da, db in zip(O.Delta_a, O.Delta_b)]
O["t_x105_exact"] = [close(1.05 * da, db, 0.01) for da, db in zip(O.Delta_a, O.Delta_b)]
O["t_x105_band"] = [da > EPS and 1.03 <= db / da <= 1.07 for da, db in zip(O.Delta_a, O.Delta_b)]
O["t_d_inv"] = [close(di, db) for di, db in zip(O.d_inv, O.Delta_b)]
tests = ["t_own_last", "t_own_sum", "t_own", "t_prev_plus_new", "t_unchanged", "t_x105_exact", "t_x105_band", "t_d_inv"]
O["t_none"] = ~O[["t_own", "t_prev_plus_new", "t_x105_band", "t_d_inv"]].any(axis=1)

print(f"ordered pairs: {len(O)} (pairs with the same Event Date excluded: {len(A.T)})")
print(f"Shipment Amount identical within every pair: {bool((O['Shipment Amount_a'] == O['Shipment Amount_b']).all())}"
      f"  -> Delta_b - Delta_a == Invoice_b - Invoice_a for every pair: "
      f"{all(close(db - da, di) for da, db, di in zip(O.Delta_a, O.Delta_b, O.d_inv))}")
print("\n1. each test, counted independently (a pair can pass several):")
for t in tests + ["t_none"]:
    g = O[O[t]]
    print(f"   {t:16s} {len(g):3d}   largest carrier {int(g.largest.sum()):3d}   others {int((~g.largest).sum()):3d}")
print("   note: t_d_inv (Delta_b = change in Invoice Amount) is equivalent to Delta_a = 0 here; "
      f"pairs with Delta_a = 0: {int(O.Delta_a.abs().le(EPS).sum())}")

print("\n2. combinations (own / prev+new / x1.05 band / unchanged):")
combo = O.apply(lambda r: "+".join(k for k, c in [("own", r.t_own), ("prev+new", r.t_prev_plus_new),
                                                   ("x1.05", r.t_x105_band), ("unchanged", r.t_unchanged)] if c) or "none", axis=1)
print(pd.crosstab(combo, O.largest.map({True: "largest", False: "others"}), margins=True).to_string())

print("\n3. by relation label (from a9):")
print(O.groupby("label")[["t_own", "t_prev_plus_new", "t_x105_band", "t_unchanged", "t_none"]].sum().astype(int).to_string())

# 4. When Delta_b = Delta_a + new: is the new amount ~1.05 x the earlier Delta?
pn = O[O.t_prev_plus_new]
r105 = [any(da > EPS and 1.03 <= v / da <= 1.07 for v in n) for n, da in zip(pn.new, pn.Delta_a)]
print(f"\n4. prev+new pairs: {len(pn)}; the new amount is 1.03-1.07 x Delta_a: {sum(r105)}; "
      f"the later text repeats Delta_a as an amount: {sum(any(close(v, da) for v in vb) for vb, da in zip(pn.vb, pn.Delta_a))}")

# 5. Pairs where the later Delta is NOT what the later text itself asks for
not_own = O[~O.t_own]
print(f"\n5. later events whose Delta is not the later text's last amount nor the sum of its amounts: {len(not_own)}")
for r in not_own.itertuples():
    print(f"   [{r.label}] Da {r.Delta_a:.2f} Db {r.Delta_b:.2f} | {A.redact(r.text_norm_b)[:100]}")

# 6. Delta direction between versions
print(f"\n6. Delta_b vs Delta_a: larger {int((O.Delta_b > O.Delta_a + EPS).sum())}, "
      f"equal {int(O.t_unchanged.sum())}, smaller {int((O.Delta_b < O.Delta_a - EPS).sum())}")

# 7. How exact is the ~5%? ratio of the uplifted amount to the earlier Delta
up = []
for r in O.itertuples():
    if r.t_x105_band:
        up.append(r.Delta_b / r.Delta_a)
    elif r.t_prev_plus_new:
        up += [v / r.Delta_a for v in r.new if 1.03 <= v / r.Delta_a <= 1.07]
up = pd.Series(up)
print(f"\n7. ~5% uplifts (replacement or stacked balance): {len(up)}; ratio min {up.min():.4f}, median {up.median():.4f}, "
      f"max {up.max():.4f}; within 1.0475-1.0525: {int(up.between(1.0475, 1.0525).sum())}")
