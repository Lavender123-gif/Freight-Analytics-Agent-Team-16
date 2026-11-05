# C1 Diagnostics catalog: test report

- **Evidence level**: in-sample
- **Card colour**: 🟩 Light green (board: [C1](../../status/project_status.en.md#card-c1))
- **Compiled on**: 2026-11-03 (task 04). Content taken from task 03's deliverable; no check was rerun this time.
- Deliverable description: [README.en.md](README.en.md); result file: [results/summary.md](results/summary.md); rendered catalog: [results/catalog_rendered.md](results/catalog_rendered.md); examples: [results/examples.md](results/examples.md); Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claimed conclusion

Each of the system's 61 diagnostics has a fixed trigger, evidence, handling and text; the catalog, `rules.yaml` and the prototype code agree with each other; every sentence of every reject notice and reviewer draft generated on the dev split comes from the catalog.

## 2. Why this evidence level

What is checked is the catalog itself, plus the code-only run on the dev split; the catalog and the check script come from the same author, and there was no human review. 41 of the 61 never fired on the dev split. So this is "in-sample".

## 3. Test method

`scratch/deliverables/C1_catalog_check.py` runs 12 consistency checks: number of entries and the return / record only split; required fields (record only entries must have text for the reviewer); handling is valid; code format `对象.子类.类型` (object.subclass.type); record only entries map one-to-one to `rules.yaml`; return entries are not in `rules.yaml`; change requests and acceptance criteria come in pairs; every code in the prototype code is in the catalog; every code fired on the dev split is in the catalog; every sentence of notices and drafts comes from the catalog. In addition, `render_catalog.py` is run; it asserts that every record only entry has a rule configuration.

## 4. Test data

The catalog `scratch/prototype/diagnostics_catalog.yaml`, plus the code-only run on all 908 events of the dev split (no step 3). **Not the test set**; the raw Excel was not read.

## 5. Threshold and whether it was set in advance

**Threshold not set in advance.** The expected values "61, 15 / 46" come from 02 §4.3; every other check expects 0 ("no inconsistency"), written at check time.

One correction during the work (section 3 of the 03 report): the first version of the check required all 61 to have "text for the reviewer" and reported 14 missing; on inspection all 14 were return entries (sent back to the model only; 02 §4.2 and §4.3 already say "none"), so the check was changed to require it only for record only entries. This change was made after seeing the results, and is recorded here as it happened.

## 6. Results

12 / 12 pass (`results/summary.md`):

- 61 diagnostics: 15 return, 46 record only, matching 02 §4.3.
- Missing required fields 0; invalid handling 0; format mismatches 0.
- Record only entries without a rule 0; in the rules but not in the catalog 0; return entries wrongly in the rules 0.
- Change requests and acceptance criteria not paired 0.
- Codes in the prototype code but not in the catalog 0; codes fired on the dev split but not in the catalog 0.
- Notice or draft sentences not from the catalog 0.
- By object: CLAIM 4, HIST 8, ITEM 17, NUM 15, REC 12, RUN 5.
- 20 fired on the dev split; **41 did not fire**.

## 7. Limitations

- Most of the 41 diagnostics that never fired need step-3 model output and have only run in the 17 synthetic cases and the walk-throughs of 02 §8.
- The text is a Chinese draft; the English wording for carriers and the reviewer interface are not decided.
- Whether the texts are useful depends on reviewers' ratings of flags (02 §9.2).

## 8. Reproduction command

Run from the repo root:

```
sh scratch/deliverables/run.sh C1_catalog_check.py
```

## 9. Check plan for moving up to Dark green

- **Independent data or checker**: (a) independent sample: for each of the 41 diagnostics that never fired, hand-write synthetic submissions (`Submission`) or synthetic records, writing down in advance which codes each case should trigger; (b) human review: a team member other than the catalog's author reviews the text for the reviewer and the change requests for the carrier.
- **Method**: (a) run the synthetic cases through prototype functions such as `check_submission` and `history_diagnostics`, and see whether they fire and whether the generated text comes from the catalog; (b) the reviewer marks each entry "clear / unclear / wrong".
- **Threshold**: 61 / 61 can be triggered; 100% of the text generated after triggering comes from the catalog; no blocking comments from the review `[suggestion, to be confirmed]`. The threshold must be written into the card's done-when criteria before the synthetic cases are written.
- **Depends on B04**: partly. Synthetic submissions can be done now; the `RUN.*` class (rounds, submission failures, etc.) only fires naturally in real agent runs, and synthetic cases can only simulate it.
