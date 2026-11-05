# B03 Auto-reject pre-check: test report

- **Evidence level**: in-sample
- **Card colour**: 🟩 Light green (board: [B03](../../status/project_status.en.md#card-b03))
- **Compiled on**: 2026-11-03 (task 04). Content is taken from task 03's deliverable; no check was rerun this time.
- Deliverable description: [README.en.md](README.en.md); results file: [results/summary.md](results/summary.md); examples: [results/examples.md](results/examples.md); Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claim

Disputes with empty or numbers-only text are auto-rejected before the model is called (10 on the dev split), and an automatic notice taken from the diagnostics catalog is generated; the exemption rule only looks at earlier records of the same shipment.

## 2. Why this evidence level

- The main check reproduces the counts of 02 §7.3 on the dev split, and the rules were set after looking at this data. This is "in-sample".
- The 3 synthetic cases were added by task 03 after the code was written. They do not come from the dev split, but there are only 3, they were written from the rule, and there was no threshold in advance. So the card as a whole is still marked "in-sample", not independent sample.
- Whether the rejections are correct has not yet been confirmed by human review.

## 3. Test method

- Run the prototype (the pre-check branch of `pipeline.py`, the pre-check mode of `history.py`, `disposition.py`, `auto_reject` in `rules.yaml`) over the full dev split and check 8 items: auto-reject event and row counts, breakdown by reason, no model call, number exempted, number with an explanation only later (for reference), all have an automatic notice.
- 3 synthetic cases: no earlier record; an earlier explanation with the same Delta; an explanation with the same Delta only later.

## 4. Test data

Full dev split: 908 events (953 rows); 3 synthetic cases. **Not the test set**; the raw Excel was not read.

## 5. Thresholds and whether they were set in advance

- Counts: the expected values are the numbers in 02 §7.3; they are reproduction targets.
- Synthetic cases: the expected results follow from the rule; they were not written into the card as a threshold in advance.
- **Reject precision threshold: set in advance at 100% (02 §9.2 "everything auto-rejected should be rejected"), but not yet checked**, because it needs human confirmation.

## 6. Results

| Check | Result | Expected |
|---|---|---|
| Auto-reject events / rows | 10 / 15 | 10 / 15 (02 §7.3) |
| Of which numbers only / empty text | 6 / 4 | 6 / 4 |
| Model not called | 10 | = auto-reject count |
| Exempted by an earlier complete explanation | 0 | 0 |
| A later same-Delta version with an explanation (reference) | 5 / 10 | 5 |
| Automatic notice generated | 10 | = auto-reject count |

Synthetic cases 3 / 3 pass: no earlier record → reject; earlier same-Delta explanation → no reject, human review; same-Delta explanation only later → still reject.

For reference: 5 of the 10 have a later version in the same shipment with the same Delta and written text, which shows that the disputes missing an explanation did later get one. This is indirect support for the direction of the rule, not precision.

## 7. Limitations

- Reject precision (target 100%) is only checked at rule level; it needs reviewer confirmation.
- Whether PPG wants automatic returns, and through which channel and template, is not yet confirmed (02 §10.2-12).
- Whether `REC.TEXT.NO_NUMBER` should also auto-reject is an open design choice (02 §10.1-8); it currently does not.
- The notice text is the Chinese draft in the diagnostics catalog; there is no carrier-facing English version yet.

## 8. Reproduce command

From the repo root:

```
sh scratch/deliverables/run.sh B03_auto_reject_precheck.py
```

## 9. Check plan for moving up to Dark green

- **Independent data or reviewer**: (a) human review: a reviewer or a teammate other than the author of the code checks the 10 auto-rejects on the dev split; (b) independent sample: a new batch of synthetic empty-text and numbers-only variants, including exemption cases with an earlier explanation, records in the same minute, and cases where Delta differs by only a few cents.
- **Method**: (a) for each one, the reviewer judges "should be returned to the carrier" or "should not", and writes down the reason; (b) the expected results of the synthetic cases must be written down before running.
- **Threshold**: auto-reject precision 100%, i.e. 10 / 10 (02 §9.2, set in advance); all synthetic cases pass.
- **Depends on B04**: no. Auto-reject happens before any model call, so it can be done now.
