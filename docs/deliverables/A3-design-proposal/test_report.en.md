# A3 Design proposal v3 (02): test report

- **Evidence level**: in-sample
- **Card colour**: 🟩 Light green (board: [A3](../../status/project_status.en.md#card-a3))
- **Card type**: analysis card. The "check" is a consistency cross-check between the document, the configuration and the rerun results, not a check of whether the design is good.
- **Compiled on**: 2026-11-03 (task 04). Content is taken from task 03's deliverable; no check was rerun this time.
- Deliverable description: [README.en.md](README.en.md); results file: [results/summary.md](results/summary.md); Chinese version (authoritative): [test_report.zh.md](test_report.zh.md)

## 1. Claim

The structural items of `docs/analysis/02_design_proposal.md`, the 61 diagnostics of §4.3, the 9 thresholds of §5.3, the diagnostic counts of §7.2 and the disposition counts of §7.3 agree exactly with the configuration files (`diagnostics_catalog.yaml`, `rules.yaml`) and a fresh run on the dev split.

## 2. Why this evidence level

The rerun uses the same dev split that was used when writing 02, and the cross-check was done by the same executor. This is "in-sample".

## 3. Test method

`scratch/deliverables/A3_design_consistency.py`:
- Counts the document structure: the number of entries in D1-D12 (incl. D3'), §10.1, §10.2 and §9.4.
- Parses the §4.3 table and compares it entry by entry with the diagnostics catalog and `rules.yaml` on handling, severity, human-review role and points.
- Compares the 9 thresholds of §5.3 with `rules.yaml`.
- Reruns the code-only part on the dev split and compares the 22 count rows of §7.2 (diagnostics / events / rows) and the 3 dispositions of §7.3.

## 4. Test data

Full dev split, 908 events (953 rows), running only the part that code can do. **Not the test set**; the raw Excel was not read.

## 5. Thresholds and whether they were set in advance

**Quality threshold not set in advance.** The expected values come from the text of 02, which was written before task 03's rerun; but these expected values are reproduction targets for "document matches code", not a threshold on design quality.

## 6. Results

**Everything agrees** (`results/summary.md`):

| Scope | Items | Result |
|---|---|---|
| Document structure (D1-D12 incl. D3' 13 items, §10.1 11 items, §10.2 12 items, §9.4 9 experiments) | 4 | match |
| §4.3 vs catalog and rules (61 rows; missing from or different in the catalog 0; extra in §4.3 0) | 3 | match |
| §5.3 thresholds | 9 | match |
| §7.2 diagnostic counts | 22 rows | match |
| §7.3 dispositions (auto-reject 10 / 15, human review 35 / 37, split trusted 863 / 901, events / rows) | 3 | match |

## 7. Limitations

- Covers only "document ↔ configuration ↔ run of the code-only part". Step 3 of the walk-throughs in section 8 was role-played and does not represent model performance; the section 9 evaluation has not been done yet.
- In §7.3, "about 80 human reviews if the model reads correctly" is an estimate and cannot be checked without a model.
- The two B07 implementation issues found after 02 was written are outside the scope of this check (see the [B07 test report](../B07-submit-checks/test_report.en.md)).
- Agreement does not mean the design is correct; 02 §10.1 still has 11 open design choices.

## 8. Reproduce command

From the repo root:

```
sh scratch/deliverables/run.sh A3_design_consistency.py
```

## 9. Check plan for moving up to Dark green

- **Independent data or reviewer**: checked by a teammate other than the author of 02 (human review).
- **Method**: the teammate reads the comparison logic of `A3_design_consistency.py` (especially the parsing of the §4.3 table), then, without the script, spot-checks about 10 rows of §4.3 and all 9 thresholds of §5.3 by hand against `diagnostics_catalog.yaml` and `rules.yaml`.
- **Threshold**: 0 unexplained differences `[suggestion, to be confirmed]`. The threshold must be written into the card's "done when" before the check starts.
- **Depends on B04**: no, it can be done now.
