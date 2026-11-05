# A2 Problem inventory (01, 01b): reproducing the numbers

> `copies/` holds copies of `docs/analysis/01_problem_inventory.md` and `01b_version_pairs.md` (copied in task 03 so the folder stands alone). **The originals in `docs/analysis/` are authoritative**; re-copy after any revision.

The Chinese version (`README.zh.md`) is authoritative; this file mirrors it.

## What this card does

Checks whether the key 【事实】 (fact) numbers in the two problem-inventory reports, `docs/analysis/01_problem_inventory.md` and `docs/analysis/01b_version_pairs.md`, are reproduced unchanged by rerunning the scripts in `scratch/analysis/`. Neither the scripts nor the reports were modified; this card only reruns, extracts and compares.

## Inputs and outputs

- Inputs: the dev split `data/processed/dev.csv` (read through `scratch/analysis/common.py`); analysis scripts `a1_structure.py` to `a11_r6_p3.py`; the numbers stated in the two reports (hard-coded in the comparison list of the reproduction script).
- Outputs:
  - `results/comparison.md`: comparison table of 61 numbers (report section, report value, script, rerun value, match, note). Aggregates only.
  - `results/examples.md`: 5 short redacted examples (problem pattern + dev-split count).
  - Full stdout of each script in the git-ignored `data/interim/deliverables/A2/<script>.txt` (may contain row text; not tracked).

## Reproduce with one command

From the repo root:

```
uv run python scratch/deliverables/A2_reproduce_inventory.py
```

The script runs the 11 analysis scripts as subprocesses, saves their output, extracts numbers with regexes, and prints and writes the comparison table. No LLM calls, no extra dependencies.

## Data checked

The full dev split: 953 rows, 908 dispute events after P1 de-duplication, 813 shipments, 18 carriers. **Not the test split**; neither `data/processed/test.csv` nor the raw Excel was read.

## Results

61 items (multi-value items compared value by value on "/"; decimals rounded to 3 places): **57 match, 2 do not match, 2 are not printed by any script and cannot be reproduced.**

Mismatches:

1. **01b §2.4, ordered pairs whose earlier event is not DECLINED that are a modified version**: report 57 (85%), rerun 56 (84%). From the a9 cross-table: 67 pairs − 2 identical − 9 unrelated = 56. A typo in the report; the conclusion (no clear difference from the DECLINED group's 78%) is unchanged.
2. **01 P3, the 8 of 53 "BALANCE DUE with ≥2 `$` amounts" rows outside the 45**: the report says "Delta = sum of items excluding the balance 4 rows, other 4 rows"; a4 actually prints "Delta = balance (last amount) 2, other 6" and has no "excludes balance" category. The headline 45 is reproduced. 01b §3.3 and §5 items 3–4 already correct P3: 5 rows where Delta excludes the balance (4 only-event, 1 later event); this corrected value is reproduced by a11.

Not reproducible (no script prints the number):

1. 01 P11: "the most frequent text appears 75 times".
2. 01 P12: the lower bound $20.09 of the non-$20 amounts (a6 only prints the range of all amounts, 20.00 to 535.18).

Numbers corrected by 01b are compared at their corrected value; the original was checked too:

- 01 P2's 21.9% (209 rows) → 01b §5.2: 21 rows (2.2%), with 48 rows (5.0%) and an upper bound of 61 rows (6.4%). Both corrected and original values reproduce (a11 and a3); the original interpretation is superseded.
- 01 P2's 41/94 → 01b §5.8: 39 ~5% uplifts (ratio 1.032 / 1.050 / 1.055; 29 within 1.0475–1.0525). Both reproduce (a10, a5).
- 01 P2's "36/95 later events where Delta is a sum of numbers" → 01b §5.1 explains this is an in-text sum, not a cross-dispute cumulative; the number itself reproduces.
- 01 P3 → see mismatch 2 above.

One unit-labelling issue, counted as a match: 01b §0 says the largest, second and third carriers have 580, 164 and 87 "rows"; these are **event** counts (a8). By rows they are 582, 185 and 87 (a1).

## Limitations

- All counts hold for the dev split only, not for the test split or the full data.
- Extraction relies on regexes over the scripts' print format; if that format changes, the reproduction script shows "(未匹配)" (no match) rather than a wrong number.
- The report values were copied by hand into the comparison list and cover 61 key numbers, not every number in the reports; 【推测】 (inference) content is out of scope.
- A match only shows that the script yields the same number again, not that the script's rules (e.g. a4's regexes, a9's relation labels) are correct; the reports themselves say these rules were written from a read-through of the dev split and are not guaranteed for unseen carriers.
- Conclusions from manual reading in 01b (e.g. "all 85 ordered pairs checked by hand") cannot be reproduced by a script.
