# Data dictionary: merged annotation table (task 15)

File: `data/interim/annotation/deliverable/merged_annotations.csv` (git-ignored: it holds substrings of real records). One row per number of an annotated record. A synthetic example with the same columns is `docs/annotation/merged_annotations_example.csv`. Built by `scratch/annotation/build_deliverable.py`.

| Column | Meaning | Values |
|---|---|---|
| `record_key` | The dev-split record (one explanation, its first row) | `dev#r<row>` |
| `number_id` | The number's id in the number table (same as in the pack) | `#1`, `#2`, ... ; `?1` for an unrecognised region |
| `substring` | The number exactly as written in the text | text |
| `annotators` | Who annotated this record | `P1`, `P2`, `P3`, or `P1+P2+P3` for the 15 common records |
| `p1_what`, `p2_what`, `p3_what` | Each annotator's item 1, as returned | `MONEY`, `WEIGHT`, `DATE`, `ID`, `QUANTITY`, `RATE`, `PERCENT`; empty if that annotator did not do this record |
| `p1_claim`, `p2_claim`, `p3_claim` | Each annotator's item 2, as returned (empty for numbers that are not money) | `COUNTED`, `NOT_HISTORY`, `NOT_TOTAL`, `NOT_REFERENCE`, `CREDIT`, `UNCLEAR` |
| `p1_category`, `p2_category`, `p3_category` | Each annotator's item 3 (only for counted amounts) | `LINEHAUL`, `FUEL`, `RATE_CORRECTION`, `ACCESSORIAL`, `DETENTION_STORAGE`, `DRAYAGE`, `TAX`, `OTHER`, `PENDING`, `NO_CHARGE_NAMED` |
| `final_what`, `final_claim`, `final_category` | The task-14 finalised label (rules R-1 to R-7); `NOT_MONEY` in `final_claim` for numbers that are not money; `DROPPED` when the record was removed by R-3 or R-4 | as above, plus `NOT_MONEY`, `DROPPED` |
| `finalisation_rules` | Which finalisation rules changed this row or its record | `R-1` to `R-6`, joined with `+`; empty if none |
| `rejudge_class` | Task-15 re-judging of the 19 records with an Unclear cell | `R-A5`, `R-BD`, `R-QR`, `R-HIST`, `R-NONE`; empty for the other records |
| `rejudged_claim`, `rejudged_category` | The label after re-judging (where a rule gives an answer); the finalised label otherwise | as `final_*` |
| `needs_person_by_standard` | Record level: does this record need a person under the written standard (truth side only) | `yes`, `no`, `not judged` (dropped records) |
| `needs_person_reasons` | Which conditions made it a yes (definitions in `docs/deliverables/T15-confusion-matrix/01-preregistration.zh.md`, section 1.1) | `G1` to `G8`, joined with `+` |

Condition codes: G1 Unclear and not covered by a rule; G2 covered by a rule that requires a person; G3 a counted amount with no charge name; G4 a counted amount categorised OTHER; G5 empty or numbers-only text; G6 a tax named with no counted tax amount; G7 a copy row with an empty or repeated PK; G8 the system's reading differs from the label (computed by the confusion script).
