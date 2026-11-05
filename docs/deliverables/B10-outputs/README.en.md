# B10 Step 7: outputs

## What it does
Writes each dispute's result in three forms (02 §2.5, D7):
1. **Record-object JSON** (one `Record` per line): source, redacted text, number table, model input, run info, split content, claim summary, diagnostics, flags, disposition, reject draft, versions
2. **Append-only event log** (one `Event` per line): ingested, flag, disposition events; event types for reviewer decisions and carrier resubmissions are defined in the schema
3. **Excel export** (two sheets): `records` (one row per event) and `flags` (one row per flag)

`Dispute Status` enters neither the record object nor the model input; it is joined back only when exporting to Excel (02 D7).

## Input and output
- Input: the `Record` produced by steps 0-6
- Output: `records.jsonl`, `events.jsonl`, `export.xlsx`, all in the git-ignored `data/interim/deliverables/B10/`
- Code: `Record`, `Event` in `scratch/prototype/schemas.py`; export logic in section 5 of `run_dev.py` (prototype, unchanged; the deliverable script copies that logic with a different output folder)

## Reproduce with one command
```
sh scratch/deliverables/run.sh B10_outputs.py
```
Results go to `results/summary.md`; the structure of one record object (identifying fields withheld) is in `results/example_record.json`.

## Validation data
The full dev split: 908 events. Not the test set. Code-only run, **no step 3**.

## Results
All 11 checks **pass**:
- All 908 record objects read back against the schema; `record_id` is unique
- All 2190 events in the log read back against the schema; exactly one disposition event per record; flag events = flags on records (374)
- The Excel file has two sheets, `records` (908 rows) and `flags` (374 rows)
- `Dispute Status` is absent from the record JSON and the model-input schema and present only in Excel

## Limitations
- Step 3 (B04) is not connected to a model yet, so `llm_input`, `content` and `claim` are empty for all 908 records. The split-content output has only appeared in the 10 walk-throughs of 02 §8, whose step 3 was role-played.
- The event log currently writes only `ingested`, `flag` and `disposition`; `diagnostic`, `auto_reject_sent`, `reject_draft_created`, `reviewer_decision` and `carrier_resubmission_linked` are defined in the schema but not written by the code.
- The Excel columns and layout have not been reviewed by the client (reviewers).
