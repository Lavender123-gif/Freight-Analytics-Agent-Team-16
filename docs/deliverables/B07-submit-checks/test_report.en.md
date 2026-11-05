# B07 4-5 Submission checks: test report (partial results)

- **Evidence level**: in-sample
- **Card colour**: 🟨 Yellow (board: [B07](../../status/project_status.en.md#card-b07))
- **Compiled on**: 2026-11-03 (task 04). This card has no deliverable yet; this folder holds only the test report. Content taken from `scratch/prototype/prototype_checks.py`, task 03's board and the 03 report, and 02 §7 and §8; no check was rerun this time.
- Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claimed conclusion

The checks inside `submit_line_items` (structure, references, phrases, unit conflicts, reconciliation, tax, totals; the return / record only split, the retry limit, an unchanged resubmission ending the run) behave as designed on the synthetic cases and the walk-throughs of 02 §8. This is **not** a claim of "done": this is a yellow card with two known issues, and it has not been run on real model output.

## 2. Why this evidence level

The 17 synthetic cases were written together with the prototype code and used to tune the code during development, so they are "in-sample". Step 3 of the 02 §8 walk-throughs was role-played; the person role-playing knew what the checks would do when writing the submissions (02 §8), so they do not count as an independent sample either.

## 3. Test method

`scratch/prototype/prototype_checks.py` has 17 cases, run with pytest. The 10 directly related to this card:

- Simple pass
- Total mismatch is returned
- Missed `$` amount is record only, not returned
- A unit price does not count as a missed `$` amount
- Delta counting the total twice is record only
- Implied tax reconciles; wrong tax is record only
- Phrase and reference errors are returned
- The reading of an unrecognised region must match the number digit by digit
- An unchanged resubmission ends the run and is judged a failure
- Retry limit

The other 7 test step-2 parsing (5), step 5.5 looking only at earlier records (1) and injection patterns (1).

The 10 walk-throughs of 02 §8: the role-played submissions in `walkthrough.py` are run through the checks.

## 4. Test data

Only synthetic strings (shaped after the way the dev split is written, with no real rows) and the walk-throughs of 02 §8. **Never run on the full dev split**, because that needs model output. **Not the test set**; the raw Excel was not read.

## 5. Threshold and whether it was set in advance

**Threshold not set in advance.** Each case has assertions, but this card's done-when criteria did not set a pass condition in advance.

## 6. Results

- Task 03 reran the 17 cases; all passed. **This result is recorded only on task 03's board and in the 03 report; there is no separate result file**; to verify, rerun with the command in section 8.
- Walk-throughs: the number of submissions, flags and disposition of each are in the table in 02 §8. For example, W3C (silently making the numbers fit) passes reconciliation but is sent to human review by `NUM.JUDGMENT.DOLLAR_EXCLUDED` alone.
- Two known issues (found in task 03, not fixed, because fixing them means changing the prototype):
  1. `NUM.JUDGMENT.DOLLAR_EXCLUDED` fires only when a `$` amount is judged non-money or given status `NONE` (`checks.py` line 300); amounts judged billed, paid or deducted are not covered.
  2. `tools.py` line 214 hard-codes the `reconcile` tolerance as `Decimal("0.005")` instead of reading `tolerances.amount_abs` from `rules.yaml`.

## 7. Limitations

- There are no real-model submissions, so how often returns, resubmissions and `PASSED_AFTER_RETURN` happen is unknown.
- The synthetic cases were designed by the side that wrote the code and cover only cases already thought of.
- The two known issues let some "missed amounts" go undetected (issue 1), and may make the tolerance of the trial calculation differ from that of the final check (issue 2).

## 8. Reproduction command

Run from the repo root (same as the note at the top of `prototype_checks.py`):

```
uv run --with pydantic --with pyyaml --with pytest pytest scratch/prototype/prototype_checks.py -q
```

## 9. What moving up to the next level (Light green) needs

See the done-when criteria of B07 on the board: rerun the synthetic cases after both issues are fixed, and count how often each diagnostic fires in a real-model run on the full dev split. The threshold is not set; it must be written down before the check starts. The full dev run depends on B04.
