# B08 5.5 History checks: test report (partial results)

- **Evidence level**: in-sample
- **Card colour**: 🟨 Yellow (board: [B08](../../status/project_status.en.md#card-b08))
- **Compiled on**: 2026-11-03 (task 04). This card has no deliverable yet; this folder holds only the test report. Content taken from the result files of the B03 deliverable, the consistency check of the A3 deliverable, and 02 §7 and §8; no check was rerun this time.
- Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claimed conclusion

Step 5.5's **pre-check mode** (only amounts the code can compute; only records of the same shipment with a strictly earlier Event Date) runs on the 908 events of the dev split, and the counts of the 6 history diagnostics match 02 §7.2. **The post-model pass** has only run on two role-played walk-throughs. This is not a claim of "done".

## 2. Why this evidence level

The history rules (same Delta, re-listed old amounts, about 1.05×, etc.) come from 01b's read-through of the same dev split, and the counts were also reproduced on the same dev split, so this is "in-sample". Step 3 of walk-throughs W5 and W9 was role-played.

## 3. Test method

- Pre-check mode: the B03 deliverable script runs `history.py` on the dev split and counts diagnostics and events for each of the 6 history diagnostics; A3's consistency check compares them with 02 §7.2.
- Earlier records only: B03's synthetic case "same-Delta explanation only later → still reject", and the "history looks only at earlier records" case in `prototype_checks.py`.
- Post-model pass: W5 and W9 of 02 §8; their earlier records W5a and W9a were also role-played, so that step 5.5 has charge codes to work with.

## 4. Test data

All 908 events of the dev split; synthetic cases; the 2 walk-throughs of 02 §8. **Not the test set**; the raw Excel was not read.

## 5. Threshold and whether it was set in advance

**Threshold not set in advance.** The expected counts are the numbers in 02 §7.2 (a reproduction target). 02 §9.2 defines the metric (precision and recall of history-relation flags, using 01b's 85 pairs as the test), but sets no value, and it has not been measured yet.

## 6. Results

Pre-check mode, all matching 02 §7.2:

| Diagnostic | Diagnostics | Events | 02 §7.2 (diagnostics / events / rows) |
|---|---|---|---|
| `HIST.REPEAT.IDENTICAL_TEXT` | 4 | 4 | 4 / 4 / 6 |
| `HIST.REPEAT.SAME_DELTA` | 16 | 16 | 16 / 16 / 22 |
| `HIST.AMOUNT.EQUALS_EARLIER_DELTA` | 21 | 21 | 21 / 21 / 21 |
| `HIST.AMOUNT.NEAR_105_EARLIER` | 41 | 41 | 41 / 41 / 43 |
| `HIST.ORDER.SAME_MINUTE_SIBLING` | 10 | 10 | 10 / 10 / 10 |
| `HIST.CONTEXT.EARLIER_EXPLAINED` | 15 | 15 | 15 / 15 / 18 |

- Synthetic cases: the earlier-records-only behaviour is as designed.
- Walk-throughs: W5 produces `REVISED_SAME_CHARGES`, result split trusted, score 2; W9 produces `EQUALS_EARLIER_DELTA`, `NEAR_105`, `REVISED_SAME_CHARGES` and others, result human review, score 5 (02 §8).

## 7. Limitations

- `REVISED_SAME_CHARGES` and `SAME_AMOUNT_NEW_CODES` in `HIST.*` need the model's counted amounts and charge codes, and have never been produced on the full split.
- Precision and recall on the 85 pairs have not been measured.
- How to compare same-minute records is not decided (02 §10.1-7); 01b points out that the text of the earlier version may itself have been written later, which cannot be controlled.

## 8. Reproduction commands

Run from the repo root:

```
sh scratch/deliverables/run.sh B03_auto_reject_precheck.py      # pre-check mode counts
sh scratch/deliverables/run.sh A3_design_consistency.py         # compare with 02 §7.2
sh scratch/prototype/run.sh walkthrough.py                      # 02 §8 walk-throughs (role-played)
```

## 9. What moving up to the next level (Light green) needs

See the done-when criteria of B08 on the board: the post-model pass runs on the full dev split, and precision and recall are reported on 01b's 85 pairs. The threshold is not set; it must be written down before the check starts. Depends on B04.
