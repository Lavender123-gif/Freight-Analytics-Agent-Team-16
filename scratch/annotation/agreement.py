"""Inter-annotator agreement on the records that more than one annotator answered (the 15 common records).

Usage:  uv run python scratch/annotation/agreement.py [data/interim/annotation/annotations_long.csv]

For every pair of annotators and every field: number of units both answered, percent agreement, Cohen's kappa.
Fields (unit = one number unless stated):
- what          item 1, the 7 options
- is_money      item 1 collapsed to money / not money
- claim         item 2, the 6 options, with NOT_MONEY for numbers the annotator said are not money
- claim_coarse  counted / not counted / credit / unclear / not money
- category      item 3, only numbers BOTH annotators marked Counted
- confident     item 4, unit = one record
- claim_sum     unit = one record: signed sum of the counted amounts (credits negative) equal or not; records where
                either annotator has an Unclear cell are left out and counted in `n_skipped`. Percent only, no kappa.
Units where either annotator left the cell empty are skipped (n_skipped).
Kappa is undefined (None) when both annotators use a single identical label throughout.
"""

from __future__ import annotations

import sys
from collections import Counter
from decimal import Decimal
from itertools import combinations
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from annot_schema import CLAIM_COARSE, NOT_MONEY  # noqa: E402

FIELDS = ["what", "is_money", "claim", "claim_coarse", "category", "confident", "claim_sum"]


def cohen_kappa(a: list, b: list) -> float | None:
    """Cohen's kappa for two raters over the same units. None when it is undefined (chance agreement is 1)."""
    if len(a) != len(b):
        raise ValueError("the two raters must rate the same units")
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


def number_value(number_id: str, raw: str) -> Decimal:
    """Value of a number row from the way it is written (same rules as the pipeline's number table)."""
    from freight_lineitems.checks import region_value
    if number_id.startswith("?"):
        return region_value(raw)
    return Decimal(raw.replace("$", "").replace(" ", "").replace(",", ""))


def derive(df: pd.DataFrame) -> pd.DataFrame:
    """Add the derived fields used for agreement and for the metric script."""
    d = df.copy()
    d["is_money"] = d["what"].map(lambda w: "" if not w else ("MONEY" if w == "MONEY" else NOT_MONEY))
    d["claim_full"] = [c if w == "MONEY" else (NOT_MONEY if w else "") for w, c in zip(d["what"], d["claim"])]
    d["claim_coarse"] = d["claim_full"].map(lambda c: CLAIM_COARSE.get(c, c))
    return d


def record_sums(d: pd.DataFrame) -> dict[tuple[str, str], Decimal | None]:
    """(annotator, record_id) -> signed sum of counted amounts; None when the annotator has an Unclear or empty cell."""
    out: dict[tuple[str, str], Decimal | None] = {}
    for (who, rec), g in d.groupby(["annotator", "record_id"]):
        if (g["claim_coarse"].isin(["UNCLEAR", ""])).any():
            out[(who, rec)] = None
            continue
        s = Decimal("0")
        for nid, raw, c in zip(g["number_id"], g["number_raw"], g["claim_coarse"]):
            if c == "COUNTED":
                s += number_value(nid, raw)
            elif c == "CREDIT":
                s -= number_value(nid, raw)
        out[(who, rec)] = s
    return out


def agreement_table(df: pd.DataFrame) -> list[dict]:
    """Pairwise agreement rows: {field, annotator_a, annotator_b, n, n_skipped, agree, percent, kappa}."""
    d = derive(df[df["record_id"] != ""])
    sums = record_sums(d)
    out: list[dict] = []
    for a, b in combinations(sorted(d["annotator"].unique()), 2):
        da, db = d[d["annotator"] == a], d[d["annotator"] == b]
        m = da.merge(db, on=["record_id", "number_id"], suffixes=("_a", "_b"))
        if m.empty:
            continue

        def row(field: str, xs: list, ys: list, skipped: int, kappa: bool = True) -> dict:
            n = len(xs)
            agree = sum(x == y for x, y in zip(xs, ys))
            return {"field": field, "annotator_a": a, "annotator_b": b, "n": n, "n_skipped": skipped, "agree": agree,
                    "percent": round(100 * agree / n, 1) if n else None,
                    "kappa": (None if (k := cohen_kappa(xs, ys)) is None else round(k, 3)) if kappa else None}

        for field, col in (("what", "what"), ("is_money", "is_money"), ("claim", "claim_full"), ("claim_coarse", "claim_coarse")):
            ok = m[(m[col + "_a"] != "") & (m[col + "_b"] != "")]
            out.append(row(field, list(ok[col + "_a"]), list(ok[col + "_b"]), len(m) - len(ok)))
        both = m[(m["claim_full_a"] == "COUNTED") & (m["claim_full_b"] == "COUNTED")]
        ok = both[(both["category_a"] != "") & (both["category_b"] != "")]
        out.append(row("category", list(ok["category_a"]), list(ok["category_b"]), len(both) - len(ok)))
        rec = m.drop_duplicates("record_id")
        ok = rec[(rec["confident_a"] != "") & (rec["confident_b"] != "")]
        out.append(row("confident", list(ok["confident_a"]), list(ok["confident_b"]), len(rec) - len(ok)))
        pairs = [(sums[(a, r)], sums[(b, r)]) for r in rec["record_id"]]
        good = [(x, y) for x, y in pairs if x is not None and y is not None]
        out.append(row("claim_sum", [x for x, _ in good], [y for _, y in good], len(pairs) - len(good), kappa=False))
    return out


def format_table(rows: list[dict]) -> str:
    if not rows:
        return "agreement: no record was answered by two annotators"
    lines = ["agreement on records answered by two annotators (pairwise)",
             f"{'field':<13}{'pair':<16}{'n':>5}{'skipped':>9}{'agree':>7}{'percent':>9}{'kappa':>8}"]
    for r in rows:
        k = "n/a" if r["kappa"] is None else f"{r['kappa']:.3f}"
        pc = "n/a" if r["percent"] is None else f"{r['percent']:.1f}"
        lines.append(f"{r['field']:<13}{r['annotator_a'] + ' x ' + r['annotator_b']:<16}{r['n']:>5}{r['n_skipped']:>9}{r['agree']:>7}{pc:>9}{k:>8}")
    return "\n".join(lines)


if __name__ == "__main__":
    from import_annotations import DEFAULT_OUT, load_long
    print(format_table(agreement_table(load_long(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT))))
