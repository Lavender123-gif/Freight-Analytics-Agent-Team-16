# Annotations: how they were made and what is in the deliverable (task 15)

## Sampling
Three packs of 45 dev-split explanations each, 105 distinct records; 15 records are in all three packs (inter-annotator agreement). Half of each pack was drawn by real frequency (with at most two records per text template, so this half is not an unbiased frequency sample, pending P-25); the other half from hard buckets: first-attempt Delta mismatches, tax, quantity x rate, several numbers, payment history. Records used as runtime worked examples were excluded. Packs were built by `scratch/annotation/build_packs.py`. 43 of the 105 records are also in tuning sample A; 4 belong to the client's two worked examples.

## Guide (summary)
For every number: (1) what it is (money, weight, date, ID, quantity, rate, percent); (2) for money, whether it is part of this claim (counted, not counted because history, total or reference, credit, unclear); (3) for counted amounts, the charge category; (4) per record, whether the annotator is confident. When the text allows two readings the answer is "unclear". Full guide: `annotation_guide.en.md` (Chinese: `annotation_guide.zh.md`).

## Finalisation and re-judging
Task 14 finalised the returned packs by written rules R-1 to R-7 (`scratch/annotation/finalize.py`): 101 records kept, 4 dropped. Task 15 re-judged the 19 records with an Unclear cell against the rules decided later (supersession, BALANCE DUE, quantity x rate), from the text, the labels and the rules only (`docs/deliverables/T15-confusion-matrix/02-rejudge.zh.md`).

## Inter-annotator agreement (the 15 common records, Cohen's kappa)
| Field | P1 x P2 | P1 x P3 | P2 x P3 |
|---|---|---|---|
| what (item 1) | 1.000 | 0.621 | 0.621 |
| is money | 1.000 | 0.791 | 0.791 |
| claim (item 2) | 0.939 | 0.930 | 1.000 |
| category (item 3, both counted) | 1.000 | 1.000 | 1.000 |
| confident (item 4) | 0.762 | 0.762 | 1.000 |

The common records are mostly simple, single-amount items, so these figures are optimistic.

## Known limitations
- All records are from the dev split; 43 were seen during tuning.
- The annotation categories are coarse and were filled in without the taxonomy's example phrasings; 10 category disagreements with the system match a taxonomy phrasing exactly (task 15 report).
- The R-5 finalisation rule turned two unanimous BALANCE DUE records into Unclear.
- P3 swapped quantity and unit price in several items (dropped or outvoted by R-4 / R-6).

## Files
| File | Where | Tracked |
|---|---|---|
| Merged annotation table | `data/interim/annotation/deliverable/merged_annotations.csv` | no (real text) |
| Finalisation and re-judging log | `data/interim/annotation/deliverable/finalisation_and_rejudge_log.csv` | no |
| Re-judging result | `data/interim/annotation/deliverable/rejudge.json` | no |
| Data dictionary | `docs/annotation/data_dictionary.md` | yes |
| Synthetic example rows | `docs/annotation/merged_annotations_example.csv` | yes |
