# B09 6 Aggregate and disposition: test report (partial results)

- **Evidence level**: in-sample
- **Card colour**: 🟨 Yellow (board: [B09](../../status/project_status.en.md#card-b09))
- **Compiled on**: 2026-11-03 (task 04). This card has no deliverable yet; this folder holds only the test report. Content taken from the result files of the B03 and A3 deliverables and 02 §5 and §7; no check was rerun this time.
- Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claimed conclusion

The disposition code (`disposition.py` + `rules.yaml`: auto-reject → alone sends to human review → human review by accumulated score → split trusted) runs on the **code-only flags** of the 908 events of the dev split, and the counts of the 3 dispositions match 02 §7.3. This is not a claim of "done".

## 2. Why this evidence level

The counts are reproduced on the dev split; the threshold 3 and the scores were set by judgement after seeing this data (02 §5.3, §10.1-3). So this is "in-sample".

## 3. Test method

The B03 deliverable script runs steps 0-2, the pre-check and step 5.5 in pre-check mode on the dev split, then computes the disposition with `disposition.py`; A3's consistency check compares the disposition distribution with 02 §7.3 and checks that the threshold in `rules.yaml` agrees with 02 §5.3.

## 4. Test data

All 908 events of the dev split (953 rows), code-only flags only, no step 3. **Not the test set**; the raw Excel was not read.

## 5. Threshold and whether it was set in advance

**Threshold not set in advance.** The expected disposition counts are the numbers in 02 §7.3 (a reproduction target). The most important metric in 02 §9.2, "error rate within split trusted", has no numeric threshold, and measuring it needs a labelled set.

## 6. Results

| Disposition | Events | Rows | vs 02 §7.3 |
|---|---|---|---|
| Auto-reject | 10 | 15 | match |
| Human review | 35 | 37 | match |
| Split trusted | 863 | 901 | match |

`escalation.score_threshold` in `rules.yaml` = 3, matching 02 §5.3 (A3 deliverable).

## 7. Limitations

- No step 3: `ITEM.*`, `CLAIM.*` and `RUN.*` flags have never taken part in a full disposition; "split trusted 863" here only means the code part found no problem, not that the split can be trusted.
- The threshold and scores have no basis; they have to be tuned with reviewers' ratings of flags (02 §10.1-3).
- Items 1, 2, 3, 4 and 10 of 02 §10.1 have no conclusion yet, and each of them would change the disposition results.

## 8. Reproduction commands

Run from the repo root:

```
sh scratch/deliverables/run.sh B03_auto_reject_precheck.py      # disposition distribution
sh scratch/deliverables/run.sh A3_design_consistency.py         # compare with 02 §7.3 and §5.3
```

## 9. What moving up to the next level (Light green) needs

See the done-when criteria of B09 on the board: run on a real-model run of the full dev split, the four open items settled, a deliverable exists. The threshold is not set; it must be written down before the check starts. Depends on B04, B07, B08.
