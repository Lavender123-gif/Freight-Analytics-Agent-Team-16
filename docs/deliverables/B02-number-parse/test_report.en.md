# B02 Step 2 Number parse: test report

- **Evidence level**: in-sample
- **Card colour**: 🟩 Light green (board: [B02](../../status/project_status.en.md#card-b02))
- **Compiled on**: 2026-11-03 (task 04). Content is taken from task 03's deliverable; no check was rerun this time.
- Deliverable description: [README.en.md](README.en.md); results file: [results/summary.md](results/summary.md); examples: [results/examples.md](results/examples.md); Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claim

In the 529 distinct redacted texts of the dev split, every digit character is claimed by some number, date or unrecognized region (the coverage check passes for all); the counts of the 8 step-2 diagnostics match 02 §7.2.

## 2. Why this evidence level

The parsing rules (space merging, leading dot, date claiming, etc.) come from phrasing in the dev split, and the check is done on the same dev split. This is "in-sample". Whether the segmentation is correct has not been checked by hand.

## 3. Test method

- Parse each text with the prototype `number_parse.py` and run the coverage check (every digit character must be claimed).
- Count number features (`$`, leading dot, adjacent minus, space merge, trailing dot, unit word).
- Count events for the 8 step-2 diagnostics with `step2_diagnostics` in `checks.py`, and compare with 02 §7.2.

## 4. Test data

Full dev split: 908 events, 529 distinct redacted texts (including the empty text). **Not the test set**; the raw Excel was not read.

## 5. Thresholds and whether they were set in advance

- 100% coverage: this is a design invariant (02 §3: unclaimed digit characters become an unrecognized region), but it **was not written down in advance as this card's threshold**.
- Diagnostic counts: the expected values are the numbers in 02 §7.2; they are reproduction targets.
- Segmentation accuracy: **threshold not set in advance**, and not measured either (02 §9.2 only defines the metric).

## 6. Results

- 529 / 529 pass the coverage check.
- In total 809 numbers, 127 dates/times and 1 unrecognized region found.
- Number features (counted by text): with `$` 684, space merge 62, unit word 81, leading dot 5, trailing dot 5, adjacent minus 2.
- Step-2 diagnostics (event counts), all matching 02 §7.2: space merge 99, leading dot 7, adjacent minus 2, unusual decimals 1, unrecognized region 1, numbers only 6, no number 1, text date after Event Date 6.

## 7. Limitations

- The coverage check only guarantees "nothing missed", not "segmented correctly": space merging (e.g. `$ 8 400.00` → 8400.00) is a rule-based inference and could really be two numbers.
- Of the 99 space merges, 94 are weights and 5 are amounts (02 §7.2).
- `-250 [PERSON]` in the examples is the result of B01 wrongly removing `TONU`, not a problem of this step.
- New phrasing from unseen carriers falls into unrecognized regions, which the model interprets and which are compared digit by digit.

## 8. Reproduce command

From the repo root:

```
sh scratch/deliverables/run.sh B02_number_parse.py
```

## 9. Check plan for moving up to Dark green

- **Independent data**: (a) a synthetic number-phrasing set: texts generated from known answers, including phrasings that are rare or absent in the dev split, e.g. thousands-separator commas, `USD`, full-width symbols, several adjacent amounts, currency symbol after the number (count which of these are really absent from the dev split before generating); (b) after V1, human review using the hand-labelled segmentation.
- **Method**: (a) run the coverage check and compare the segmentation one by one with the known answers; (b) on the V1 labelled set, compute per-number segmentation accuracy, stratified by phrasing (02 §9.2).
- **Threshold**: 100% coverage; segmentation accuracy ≥ 98% `[suggestion, to be confirmed]`. The thresholds must be written into the card's "done when" before the synthetic data is generated and labelling starts.
- **Depends on B04**: no. (a) can be done now; (b) waits for V1, and V1 does not depend on B04.
