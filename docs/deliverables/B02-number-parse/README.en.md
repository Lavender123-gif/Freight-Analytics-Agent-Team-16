# B02 Step 2: number recognition

## What it does
Finds every number in the redacted text and numbers them in order (`#1`, `#2`, ...), claiming dates and times first (`D1`, ...). For each number it records objective features: raw form, normalised value, `$`, whether it was merged from space-separated digit groups, leading dot, minus sign, neighbouring words, unit word. The **coverage check** guarantees every digit character in the text is claimed by a number, a date, or an "unrecognized region" (`?1`), so no number is dropped silently. The model can later only refer to these ids; it cannot write amounts itself.

## Input and output
- Input: redacted text from B01
- Output: number table, date table, unrecognized regions, marked text (the version the model sees), and step-2 diagnostics
- Code: `scratch/prototype/number_parse.py`, `step2_diagnostics` in `checks.py` (prototype, unchanged)

## Reproduce with one command
```
sh scratch/deliverables/run.sh B02_number_parse.py
```
Results go to `results/summary.md` and `results/examples.md`; the full parse of every text is in the git-ignored `data/interim/deliverables/B02/`.

## Validation data
The full dev split: 908 events, 529 distinct redacted texts (including the empty text). Not the test set. Numbers compared with 02 §7.2.

## Results
- All 529 texts **pass the coverage check** (matches 02 §7.2).
- 809 numbers, 127 dates/times and 1 unrecognized region (`CV19`) found.
- Event counts of all 8 step-2 diagnostics **match** 02 §7.2: space-merged 99, leading dot 7, adjacent minus 2, unusual decimals 1, unrecognized region 1, numbers only 6, no number 1, text date after Event Date 6.
- 5 examples (text before → marked text and number table after) in `results/examples.md`: space-separated amount, leading dot, unrecognized region, dates + days + unit rate, adjacent minus.

## Limitations
- Coverage means "nothing missed", not "split correctly": space merging (`$ 8 400.00` → 8400.00) is a heuristic and could be two numbers. Split accuracy needs the labelled set (02 §9.2, V1).
- Of the 99 space merges, 94 are weights and 5 are amounts (02 §7.2); when a merged amount is counted in the claim, steps 4-5 add a diagnostic.
- `-250 [PERSON]` in the examples is B01 wrongly redacting `TONU` as a name, not a problem of this step.
- The rules come from dev-split phrasing; new phrasing from unseen carriers falls into "unrecognized regions", which the model reads and the code checks digit by digit.
