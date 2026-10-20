import pandas as pd
import pytest

from freight_lineitems.data_split import GROUP_COL, PROCESSED_DIR, split_shipments

DEV_CSV = PROCESSED_DIR / "dev.csv"
TEST_CSV = PROCESSED_DIR / "test.csv"
RAW_ROW_COUNT = 1347

needs_split_files = pytest.mark.skipif(
    not (DEV_CSV.exists() and TEST_CSV.exists()),
    reason="Run `uv run python -m freight_lineitems.data_split` first.",
)


def _read_ids(path) -> pd.Series:
    # Only the ID column is read; no row contents are loaded or shown.
    return pd.read_csv(path, usecols=[GROUP_COL], dtype=str)[GROUP_COL]


@needs_split_files
def test_no_shipment_in_both_splits():
    overlap = set(_read_ids(DEV_CSV)) & set(_read_ids(TEST_CSV))
    assert len(overlap) == 0, f"{len(overlap)} shipments appear in both splits"


@needs_split_files
def test_row_counts_add_up():
    assert len(_read_ids(DEV_CSV)) + len(_read_ids(TEST_CSV)) == RAW_ROW_COUNT


def _synthetic() -> pd.DataFrame:
    rows = []
    for i in range(20):  # big carrier: 20 shipments, some with 2 rows
        rows += [{GROUP_COL: f"A{i}", "Carrier": "A"}] * (1 + i % 2)
    for i in range(3):  # small carrier: 3 shipments
        rows.append({GROUP_COL: f"B{i}", "Carrier": "B"})
    return pd.DataFrame(rows)


def test_small_carrier_goes_to_dev():
    dev, test = split_shipments(_synthetic())
    assert (test["Carrier"] != "B").all()
    assert (dev["Carrier"] == "B").sum() == 3


def test_big_carrier_split_fraction_and_grouping():
    dev, test = split_shipments(_synthetic())
    assert test[GROUP_COL].nunique() == 6  # round(0.3 * 20)
    assert not set(dev[GROUP_COL]) & set(test[GROUP_COL])


def test_deterministic_and_order_independent():
    df = _synthetic()
    _, test1 = split_shipments(df)
    _, test2 = split_shipments(df.sample(frac=1, random_state=0))
    assert set(test1[GROUP_COL]) == set(test2[GROUP_COL])
