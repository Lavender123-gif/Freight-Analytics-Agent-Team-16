# A1 Dev / test split: test report

- **Evidence level**: in-sample
- **Card colour**: 🟩 Light green (board: [A1](../../status/project_status.en.md#card-a1))
- **Compiled on**: 2026-11-03 (task 04). Content is taken from task 03's deliverable; no check was rerun this time.
- Deliverable description: [README.en.md](README.en.md); results file: [results/summary.md](results/summary.md); Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claim

The raw data is split by shipment into a dev split and a test set: the two sides share no shipment, their row counts add up to the raw row count, and the test set was not opened during development (only the ID column was read, for counts).

## 2. Why this evidence level

The check covers every shipment ID, not a sample; but the check script and the split code come from the same side, nobody other than the author of the code has checked them, and they have not been checked on independent data. By the board's definition this is "in-sample"; it does not meet Dark green's "independent sample or human review".

## 3. Test method

- Run the existing tests `tests/test_data_split.py` (5 tests: 3 synthetic cases, 2 that read the ID column).
- The 8 checks of `scratch/deliverables/A1_split_check.py`: pytest result, dev split row count and shipment count, test set row count and shipment count, number of shipments shared by both sides, row-count conservation, exactly one carrier per shipment within the dev split.

## 4. Test data

- Full dev split: `data/processed/dev.csv`, 953 rows, 813 shipments.
- **Test set exception (approved, stated as before)**: the overlap and row-count checks have to look at both sides, so `test.csv` is read for this one column only, with `usecols=["SHIPMENT_GID"]`, to get row and shipment counts, the same way the existing tests read it. No other column of the test set was read; the results contain only counts and pass/fail, no IDs.
- The raw Excel was not read.

## 5. Thresholds and whether they were set in advance

| Threshold | Set in advance? |
|---|---|
| Shipments shared by both sides = 0; rows add up to 1347 | Yes: written in `tests/test_data_split.py` (commit 42490b6) and the Data section of `CLAUDE.md`, before task 03's rerun |
| Test set share of shipments about 30% | Yes: the split design (70/30 within larger carriers); this is a descriptive value, not a pass condition |

Although these thresholds were written down in advance, the evidence is only in-sample (see section 2), so they cannot be used to mark the card Dark green.

## 6. Results

8 / 8 pass (`results/summary.md`):

| Check | Result |
|---|---|
| pytest `tests/test_data_split.py` | 5 passed, 0 failed |
| Dev split rows / shipments | 953 / 813 |
| Test set rows / shipments | 394 / 343 |
| Shipments shared by both sides | 0 |
| Rows added up | 953 + 394 = 1347 |
| Dev split shipments with more than one carrier | 0 |

The test set holds 29.7% of shipments.

## 7. Limitations

- The largest carrier accounts for 582 / 953 rows in the dev split, and the test set has a similar make-up: results on the test set will mainly reflect the largest carrier (01 P20).
- Carriers with fewer than 4 shipments are all in the dev split, so the test set cannot measure these carriers' phrasing.
- The test set was only counted through the ID column; its content was not inspected, and should not be during development.

## 8. Reproduce command

From the repo root:

```
uv run python scratch/deliverables/A1_split_check.py
```

## 9. Check plan for moving up to Dark green

- **Independent data or reviewer**: checked by a teammate other than the author of the code (human review).
- **Method**: the teammate independently runs `A1_split_check.py` and `uv run pytest tests/test_data_split.py` in their own environment, and reads `src/freight_lineitems/data_split.py`: the grouping key is shipment, stratification is by carrier, the small-carrier rule, the fixed seed. Review comments are written into this report.
- **Threshold**: 0 shared shipments; rows add up to 1347; no unresolved review issues `[suggestion, to be confirmed]`. The threshold must be written into the card's "done when" before the teammate starts checking.
- **Depends on B04**: no, it can be done now.
