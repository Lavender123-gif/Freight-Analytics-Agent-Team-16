# A2 Problem inventory (01, 01b): test report

- **Evidence level**: in-sample
- **Card colour**: 🟩 Light green (board: [A2](../../status/project_status.en.md#card-a2))
- **Card type**: analysis card. The "check" is script reproducibility and number cross-checking, not a test of a feature.
- **Compiled on**: 2026-11-03 (task 04). Content is taken from task 03's deliverable; no check was rerun this time.
- Deliverable description: [README.en.md](README.en.md); comparison table: [results/comparison.md](results/comparison.md); examples: [results/examples.md](results/examples.md); Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claim

The key numbers marked 【事实】 (fact) in the two problem-inventory reports (`docs/analysis/01_problem_inventory.md`, `01b_version_pairs.md`) are reproduced unchanged by rerunning the scripts under `scratch/analysis/`; the discrepancies are listed and do not affect the reports' conclusions.

## 2. Why this evidence level

The reproduction uses the same dev split that was read when writing 01 and 01b; the report values in the comparison table were copied by hand from the text by task 03, and extraction and comparison were done by the same executor, with no one else checking. This is "in-sample".

## 3. Test method

`scratch/deliverables/A2_reproduce_inventory.py` runs the 11 scripts `a1_structure.py` to `a11_r6_p3.py` one after another as subprocesses, extracts numbers from their output with regexes, and compares them one by one with the 61 report values hard-coded in the comparison table (multi-value items compared value by value on "/", decimals rounded to 3 places). Numbers corrected by 01b are compared at their corrected value, and the original value is checked too.

## 4. Test data

Full dev split: 953 rows, 908 events after P1 de-duplication, 813 shipments, 18 carriers. **Not the test set**; neither `data/processed/test.csv` nor the raw Excel was read.

## 5. Thresholds and whether they were set in advance

**threshold not set in advance.** Task 03 did not write down in advance "how many items must match to pass"; it only listed, as they are, the items that match, do not match, or cannot be reproduced.

## 6. Results

Of 61 items: **57 match, 2 do not match, 2 have no script output**.

Mismatches (both typo-type; the conclusions are unchanged):
1. 01b §2.4: the "modified version" count is reported as 57 (85%); the rerun gives 56 (84%).
2. 01 P3: of the 53 rows, the breakdown of the 8 rows outside the 45 differs from a4's output; the 45 itself reproduces, 01b §3.3 and §5 have already corrected P3, and a11 reproduces the corrected value.

No script output: 01 P11 "the same text appears at most 75 times"; the lower bound $20.09 in 01 P12.

Unit wording: 580, 164 and 87 in 01b §0 are event counts, not row counts; counted as a match.

## 7. Limitations

- All counts hold for the dev split only.
- Extraction relies on regexes over the scripts' print format; if that format changes, the script shows "（未匹配）" (no match) rather than a wrong number.
- Only 61 key numbers are covered, not every number in the reports; 【推测】 (inference) content is out of scope.
- A "match" only shows that rerunning the script gives the same number, not that the script's rules (e.g. a4's regexes, a9's relation labels) are themselves correct.
- Conclusions from manual reading (e.g. the 85 pairs checked one by one) cannot be reproduced by a script.

## 8. Reproduce command

From the repo root:

```
uv run python scratch/deliverables/A2_reproduce_inventory.py
```

## 9. Check plan for moving up to Dark green

- **Independent data or reviewer**: checked by a teammate other than the author of the reports (human review).
- **Method**: the teammate randomly picks about 20 【事实】 (fact) numbers from the text of 01 and 01b (without looking at the comparison table) and runs the matching scripts to check them; then randomly picks 5 of the 85 pairs in 01b and reads the original text to judge the relation label (duplicate submission, modified version, unrelated new dispute).
- **Threshold**: all spot-checked numbers match, or the difference is already in the comparison table; no disagreement on the relation labels of the 5 pairs `[suggestion, to be confirmed]`. The threshold must be written into the card's "done when" before the check starts.
- **Depends on B04**: no, it can be done now.
