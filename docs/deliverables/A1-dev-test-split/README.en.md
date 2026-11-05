# A1 Dev / test split

## What it does
Splits the raw dispute data into a dev set and a test set by shipment, so all rows of one shipment land on the same side. Within each carrier with at least 4 shipments, 30% of shipments are drawn at random into test (seed 16); carriers with fewer than 4 shipments go entirely to dev. The test set stays closed during development and is run once, at the final test (V4).

## Input and output
- Input: `data/raw/AutoPay_Dispute_Data_20220815.xlsx` (1347 rows, confidential, git-ignored)
- Output: `data/processed/dev.csv` (953 rows), `data/processed/test.csv` (394 rows), both git-ignored
- Code: `src/freight_lineitems/data_split.py`; tests: `tests/test_data_split.py` (commit 42490b6)

## Reproduce with one command
```
uv run python scratch/deliverables/A1_split_check.py
```
It runs the existing `tests/test_data_split.py`, then counts rows and shipments on both sides. Results go to `results/summary.md`. The split itself was produced by `uv run python -m freight_lineitems.data_split`; this deliverable does not re-split.

## Validation data
The full dev split (953 rows, 813 shipments). **This card has one approved exception to the "do not open the test set" rule**: the overlap and row-count checks need both sides, so `test.csv` is read with `usecols=["SHIPMENT_GID"]` only, for row and shipment counts (the same way the existing tests read it). No other test column is read, and no ID appears in the deliverable; only counts and pass/fail. Reason: without the test IDs there is no way to show the two sides do not overlap.

## Results
All 8 checks pass (`results/summary.md`):
- The 5 existing tests pass (3 synthetic, 2 that read the ID column)
- Shipments in both splits: 0
- Rows: 953 + 394 = 1347, equal to the raw row count
- 813 shipments in dev, 343 in test; test holds 29.7% of shipments
- Every dev shipment has exactly one carrier
- Dev distribution by carrier rank is in the summary (carrier codes withheld)

## Limitations
- The largest carrier accounts for 582 of 953 dev rows, and the test split has a similar make-up, so test results will mostly reflect that carrier (01 P20).
- Carriers with fewer than 4 shipments are all in dev, so the test set cannot measure their phrasing.
- Test row counts come from counting the ID column; the test content was not inspected and should not be during development.
