import os

import pandas as pd
import pytest

from freight_lineitems.data_split import GROUP_COL, PROCESSED_DIR, split_shipments

DEV_CSV = PROCESSED_DIR / "dev.csv"
TEST_CSV = PROCESSED_DIR / "test.csv"
RAW_ROW_COUNT = 1347

# These two tests read the shipment-ID column of the test split. The test split is off limits during development
# (task 09, decision D-08), so they only run when FL_ALLOW_TEST_SPLIT=1 is set explicitly.
needs_split_files = pytest.mark.skipif(
    os.environ.get("FL_ALLOW_TEST_SPLIT") != "1" or not (DEV_CSV.exists() and TEST_CSV.exists()),
    reason="Reads the test split's ID column; set FL_ALLOW_TEST_SPLIT=1 to run (and run the split first).",
)


def _read_ids(path) -> pd.Series:
    # Only the ID column is read; no row contents are loaded or shown.
    from freight_lineitems.config import assert_readable
    return pd.read_csv(assert_readable(path), usecols=[GROUP_COL], dtype=str)[GROUP_COL]


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


def test_read_layer_refuses_protected_paths(monkeypatch):
    """Pending P-18 / audit L6: the guard works on the resolved path, not on how the path was written."""
    from freight_lineitems.config import ROOT, ProtectedPathError, assert_readable
    from freight_lineitems.records import load_excel
    monkeypatch.delenv("FL_ALLOW_TEST_SPLIT", raising=False)
    monkeypatch.delenv("FL_ALLOW_RAW", raising=False)
    roundabout = ROOT / "data" / "interim" / ".." / "processed" / TEST_CSV.name
    for p in (TEST_CSV, roundabout, str(TEST_CSV)):
        with pytest.raises(ProtectedPathError):
            assert_readable(p)
    raw = ROOT / "data" / "raw"
    for p in (raw / "anything.xlsx", ROOT / "scratch" / ".." / "data" / "raw" / "x" / "y.xlsx"):
        with pytest.raises(ProtectedPathError):
            assert_readable(p)
    with pytest.raises(ProtectedPathError):
        load_excel(raw / "anything.xlsx")           # refused before any file is opened
    assert assert_readable(DEV_CSV) == DEV_CSV.resolve()
    monkeypatch.setenv("FL_ALLOW_TEST_SPLIT", "1")  # the owner's switch opens exactly one gate
    assert assert_readable(TEST_CSV) == TEST_CSV.resolve()
    with pytest.raises(ProtectedPathError):
        assert_readable(raw / "anything.xlsx")
