# B10 7 Outputs: test report

- **Evidence level**: in-sample
- **Card colour**: 🟩 Light green (board: [B10](../../status/project_status.en.md#card-b10))
- **Compiled on**: 2026-11-03 (task 04). Content taken from task 03's deliverable; no check was rerun this time.
- Deliverable description: [README.en.md](README.en.md); result file: [results/summary.md](results/summary.md); structure example: [results/example_record.json](results/example_record.json); Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claimed conclusion

The three outputs, record-object JSON, append-only event log and Excel (two sheets, records and flags), are generated on the 908 events of the dev split and all read back against the schema; `Dispute Status` appears only in Excel (02 D7).

## 2. Why this evidence level

The check was run on the dev split, code part only; the checks and the output code come from the same author, there was no human review, and the Excel has not been shown to the client. So this is "in-sample".

## 3. Test method

`scratch/deliverables/B10_outputs.py` (copies the export logic of section 5 of `run_dev.py`, with a different output folder) generates the three outputs, then runs 11 structural checks: records read back against the `Record` schema, `record_id` unique, events read back against the `Event` schema, one disposition event per record, number of flag events equals the number of flags on records, the two Excel sheets and their row counts, `Dispute Status` absent from the record JSON and the model-input schema and present only in Excel.

## 4. Test data

All 908 events of the dev split, code part only, **no step 3**. **Not the test set**; the raw Excel was not read.

## 5. Threshold and whether it was set in advance

**Threshold not set in advance.** The expected values of the 11 checks (e.g. 908, 374, "absent") were derived from the design at check time and were not written into the card in advance.

## 6. Results

11 / 11 pass (`results/summary.md`):

| Check | Result |
|---|---|
| Records read back / `record_id` unique | 908 / 908 |
| Event log read back | 2190 events |
| One disposition event per record | 908 |
| Flag events = flags on records | 374 = 374 |
| Excel sheets / `records` rows / `flags` rows | records, flags / 908 / 374 |
| `Dispute Status` not in record JSON, not in model-input schema, only in Excel | yes / yes / yes |

How each part of the record object is filled: `source`, `text`, `parse`, `run`, `disposition`, `versions` in 908; `diagnostics`, `flags` in 273; `reject_draft` in 37; `llm_input`, `content`, `claim` in **0**.

## 7. Limitations

- Step 3 (B04) is not connected to a model, so `llm_input`, `content` and `claim` are empty for all 908 records. The output format of the split content has only appeared in the 10 walk-throughs of 02 §8, and step 3 of those walk-throughs was role-played.
- The event log writes only three types: `ingested`, `flag` and `disposition`; the other 5 are defined in the schema but not yet written by the code.
- The Excel columns and layout have not been reviewed by the client (reviewers).

## 8. Reproduction command

Run from the repo root:

```
sh scratch/deliverables/run.sh B10_outputs.py
```

## 9. Check plan for moving up to Dark green

- **Independent data or checker**: (a) real model output once B04 runs, data that did not exist when this card was developed; (b) human review: a client-side reviewer looks at the Excel export once.
- **Method**: (a) rerun the 11 checks with real content, plus content checks: whether `content`, `claim` and `llm_input` are non-empty and read back against the schema; (b) the reviewer comments on the columns, hints and layout, and the comments are recorded.
- **Threshold**: all structural checks pass; content fields non-empty in 100% of records other than auto-reject; no blocking comments from the reviewer `[suggestion, to be confirmed]`. The threshold must be written into the card's done-when criteria before the rerun and before asking the reviewer.
- **Depends on B04**: yes. The content part needs B04's real output; the reviewer's look at the Excel layout can be done first.
