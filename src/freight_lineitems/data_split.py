"""Split the raw dispute data into dev and test sets at the shipment level.

Run with: uv run python -m freight_lineitems.data_split

Only aggregate statistics are printed. Row contents are never printed,
so the test split stays unseen during development.
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "AutoPay_Dispute_Data_20220815.xlsx"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

GROUP_COL = "SHIPMENT_GID"
STRATA_COL = "Carrier"
SEED = 16  # Team 16; any fixed integer works.
TEST_FRAC = 0.3

# Small-carrier rule: carriers with fewer than MIN_SHIPMENTS shipments go
# entirely to dev. With only 1-3 shipments, a 70/30 split would put either
# nothing or 33-100% of that carrier in test, so its share could not match
# across splits. Keeping these rare carriers in dev also means development
# sees every carrier's phrasing at least once.
MIN_SHIPMENTS = 4


def split_shipments(
    df: pd.DataFrame,
    test_frac: float = TEST_FRAC,
    min_shipments: int = MIN_SHIPMENTS,
    seed: int = SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (dev, test), stratified by carrier and grouped by shipment.

    All rows of one shipment end up in the same split. In each carrier with
    at least `min_shipments` shipments, round(test_frac * n) shipments go to
    test. Smaller carriers go entirely to dev (see MIN_SHIPMENTS).
    Carriers and shipment IDs are sorted before shuffling, so the result
    depends only on the data and the seed, not on the input row order.
    """
    shipment_carrier = df.groupby(GROUP_COL)[STRATA_COL].nunique()
    if (shipment_carrier > 1).any():
        raise ValueError("Some shipments have more than one carrier; cannot stratify.")

    rng = np.random.default_rng(seed)
    test_ids: set = set()
    for _, ids in df.groupby(STRATA_COL, sort=True)[GROUP_COL]:
        unique_ids = np.sort(ids.unique())
        if len(unique_ids) < min_shipments:
            continue
        n_test = int(round(test_frac * len(unique_ids)))
        test_ids.update(rng.permutation(unique_ids)[:n_test])

    is_test = df[GROUP_COL].isin(test_ids)
    return df[~is_test], df[is_test]


def summarize(dev: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Per-carrier counts of shipments and rows in each split (aggregates only)."""
    def counts(part: pd.DataFrame, name: str) -> pd.DataFrame:
        g = part.groupby(STRATA_COL)
        return pd.DataFrame(
            {f"{name}_ship": g[GROUP_COL].nunique(), f"{name}_rows": g.size()}
        )

    table = counts(dev, "dev").join(counts(test, "test"), how="outer").fillna(0).astype(int)
    total = table["dev_ship"] + table["test_ship"]
    table["test_share"] = (table["test_ship"] / total).round(3)
    table["all_dev"] = np.where(total < MIN_SHIPMENTS, "yes", "")
    table = table[["dev_ship", "test_ship", "test_share", "dev_rows", "test_rows", "all_dev"]]
    return table.sort_values(["dev_ship", "test_ship"], ascending=False)


def main() -> None:
    df = pd.read_excel(RAW_PATH, dtype={GROUP_COL: str})
    dev, test = split_shipments(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dev.to_csv(PROCESSED_DIR / "dev.csv", index=False)
    test.to_csv(PROCESSED_DIR / "test.csv", index=False)

    n_rows, n_ship = len(df), df[GROUP_COL].nunique()
    print(f"Seed {SEED}, test_frac {TEST_FRAC}, min shipments per carrier {MIN_SHIPMENTS}")
    for name, part in [("dev", dev), ("test", test)]:
        s = part[GROUP_COL].nunique()
        print(
            f"{name:>4}: {len(part):5d} rows ({len(part) / n_rows:.1%}), "
            f"{s:5d} shipments ({s / n_ship:.1%})"
        )
    print(f"total: {n_rows:5d} rows, {n_ship:5d} shipments\n")
    print(summarize(dev, test).to_string())


if __name__ == "__main__":
    main()
