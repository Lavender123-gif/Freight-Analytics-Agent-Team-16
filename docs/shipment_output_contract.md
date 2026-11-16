# Shipment output contract

Task 20. What the shipment step (`pipeline.finish_batch`: order copies, `rollup.py`, `charge_map.py`) hands to
reviewers and downstream systems. It takes the reading output (`docs/reading_output_contract.md`) of every
explanation of a batch and returns one result per shipment (SHIPMENT_GID, shown with its SAP BOL). Production
(`pipeline.run_batch`), the offline run (`python -m freight_lineitems.offline`) and every evaluation script use this
one path. Definitions of the business terms live in `config/rules.yaml` `concepts`; this page cites them by id. All
examples are synthetic. Nothing here says whether a charge should be paid.

Version: `schema_version` = `shipment-output-1.0` (the reading output carries `reading-output-1.0`). A field is only
added in a minor version; a field whose meaning changes gets a new major version.

## 1. Where the output is

Per run, in `data/interim/runs/<run>/` (git-ignored):

| file / table | content |
|---|---|
| `shipments.jsonl` | one full shipment result per line (all fields below) |
| `shipment_table.csv`, `shipment_table.json` | the client's table: one group per shipment (section 4) |
| `run.sqlite` tables `shipment_result`, `shipment_line` | the same, one row per shipment and one per line (`config/schema_v1.yaml`) |
| `run_info.json` `run_record` | how the run was made (section 7) |

Example used below: shipment `S1`, Shipment Amount $150.00, two explanations on the same day:
`a` = `SORT FEE $40.00 + GST $2.00 = $42.00`, `b` = `FSC SHOULD APPLY. BALANCE DUE IS $18.10 + GST $0.91 = $19.01`
(the reading of `b` gives `$19.01` as the stated amount due).

## 2. Shipment fields (`shipments.jsonl`)

| field | meaning | values | example |
|---|---|---|---|
| `schema_version` | version of this contract | string | `shipment-output-1.0` |
| `shipment_key`, `sap_bol` | the shipment and its SAP BOL (display) | text | `S1`, null |
| `original_amount` | the original freight amount (Shipment Amount) | decimal string or null | `150.00` |
| `explanations[]` | the shipment's explanations in roll-up order (Event Date, then row) with `expl_id`, `event_date`, `first_row`, `n_rows`, `n_orders`, `usable`, `recommendation`, and the three gap numbers of that explanation (section 3) | list | `a`, `b` |
| `n_orders` | distinct order numbers (PKs) over the shipment | integer | 1 |
| `lines[]` | every counted amount of every usable reading (section 2.1), tax on its own line | list | 4 lines |
| `default_change` | sum of the lines whose status is `COUNTED` (credits negative) | decimal string | `61.01` |
| `new_total` | `original_amount + default_change` | decimal string or null | `211.01` |
| `complete` | every explanation has a usable reading (rule 8) | bool | true |
| `other_readings[]` | for each event that has another reading (replacement, ratio, same amount): `event`, `flag`, `change`, `new_total` under that reading (client decision A4) | list | `[]` |
| `other_readings_range` | lowest and highest change and new total over the other readings | object or null | null |
| `items_total`, `stated_amount_due`, `gap`, `gap_note` | the gap columns (section 3) | | `61.01`, null, null, `MULTI_EXPLANATION_NO_SHIPMENT_GAP` |
| `prior_history` | cross-batch history (section 5.1): `{status, items, source}` | `status` one of `FOUND`, `CHECKED_NONE`, `NOT_PROVIDED` | `{NOT_PROVIDED, [], null}` |
| `relation_undecided` | the shipment has a rule-7 event (relation code cannot decide) | bool | false |
| `relation_suggestions` | suggestions passed in for rule-7 relations (section 5.2), copied as given | list | `[]` |
| `flags[]` | the shipment's own flags (`SHIP.ROLLUP.*`, `SHIP.GAP.*`) with severity and evidence | list | `SHIP.GAP.MULTI_EXPLANATION` (info) |
| `shipment_flags_recommendation` | the recommendation from the shipment's own flags alone | `PASSED_CHECKS`, `HUMAN_REVIEW`, `RETURN_SUGGESTED` | `PASSED_CHECKS` |
| `recommendation` | the worst of the explanations' recommendations and the shipment's own | same | `PASSED_CHECKS` |

### 2.1 Line fields (`lines[]`)

| field | meaning | example |
|---|---|---|
| `line_id` | `<explanation id>:<number id>` | `a:#1` |
| `explanation`, `number_id` | where the amount comes from | `a`, `#1` |
| `amount` | signed amount (credits negative; `concepts.credit`) | `40.00` |
| `codes` | internal taxonomy codes (identity for every comparison) | `["ACCESSORIAL.SORT_SEGREGATE"]` |
| `label` | the charge name as written, or the `OTHER` phrase | `SORT FEE` |
| `is_tax` | a tax line | false |
| `status` | `COUNTED`; `SUPERSEDED` (a later explanation replaced it, rules 2, 3, 6b); `NOT_COUNTED` (rule 6a: the BALANCE DUE amount replaces it inside one explanation) | `COUNTED` |
| `replaced_by`, `event` | the line that replaced it and the event id that carries the other reading | null |
| `added_by_code` | rule 6a counted the BALANCE DUE amount although the reading did not | false |
| `client_name`, `edi_candidates`, `reference_names`, `coverage_class` | display columns from `config/charge_map.yaml` (client's Addenda B names) | `SORT,SEGREGATE & STACKING CHG` |

### 2.2 What the review page reads (task 20b)

The review page (`review_ui.py`, section 6) lists invoices; each invoice header shows the stored result of its
shipment, read from `run.sqlite` `shipment_result.result` (the same object as the shipment's line in
`shipments.jsonl`) by `review_ui.shipment_header`. The page copies these fields unchanged and computes no total and
no recommendation of its own:

| shown as | field |
|---|---|
| header colour and label (`Passed checks`, `Human review`, `Return suggested`) | `recommendation` |
| Original amount | `original_amount` |
| New total (default reading) | `new_total` |
| Change from original amount | `default_change` |
| Other readings: event, reminder, change, new total under that reading (one row each) | `other_readings[]`: `event`, `flag`, `change`, `new_total` |
| Stated amount due, Gap, Gap note | `stated_amount_due`, `gap`, `gap_note` (also kept: `items_total`) |
| Shipment reminders with severity (`Attention`, `Return suggested`, `Info`) | `flags[]`: `code`, `severity` (shown in upper case), `evidence` |
| Complete (shown only when false) | `complete` |
| shipment id, SAP BOL, version, number of explanations | `shipment_key`, `sap_bol`, `schema_version`, `explanations[].expl_id` |
| (passed through, not shown) | `relation_undecided` |

When one invoice's disputes belong to more than one shipment, each shipment gets its own block and the invoice
colour is the most pressing of their stored recommendations (decision 2.3 order). A run without a stored shipment
result (made before task 20) shows "No shipment result" instead of a computed value. Each explanation's own block
(text, reading, flags, buttons) is unchanged, and so are the stored decision values (section 6); only their display
labels are English (`review_ui.LABELS`).

## 3. The gap columns (`concepts.gap`)

Three numbers per explanation (in `explanations[]`) and per shipment:

| field | meaning | example (`b`) |
|---|---|---|
| `items_total` | line total: the counted amounts of the explanation's own reading after rule 6a (a line a later explanation replaced still belongs to this explanation's total); for the shipment, the default change | `19.01` |
| `stated_amount_due` | the amount the text presents as owed now (`facts.stated_amount_due` of the reading), or null | `19.01` |
| `gap` | `stated_amount_due - items_total`; null (not 0) when nothing is stated | `0.00` |

Shipment level: a shipment with one explanation takes that explanation's numbers. With two or more explanations the
shipment's `stated_amount_due` and `gap` stay null, `gap_note` is `MULTI_EXPLANATION_NO_SHIPMENT_GAP` when any
explanation states an amount, and `SHIP.GAP.MULTI_EXPLANATION` (info) is raised: which charges one explanation's
stated amount covers is not known until the cross-explanation work. A gap other than 0 raises `SHIP.GAP.NONZERO`
(info). The gap is never a line, never enters a total or a per-charge count, and never changes a recommendation.

## 4. The shipment table (client format)

`shipment_table.csv`: one group of rows per shipment, columns `shipment_key, sap_bol, row, label, internal_code,
amount, status, replaced_by, explanation, note`. Rows in order:

| `row` | label | amount | other columns |
|---|---|---|---|
| `ORIGINAL_AMOUNT` | Original Amount | `original_amount` | |
| `LINE` / `TAX` | client name | line amount | internal code(s) joined by `+`, status, replaced by, explanation; note `added by code (BALANCE DUE)` for rule 6a lines |
| `NEW_TOTAL` | New Disputed Total | `new_total` | |
| `CHANGE_FROM_ORIGINAL` | Delta from Original Amount | `default_change` | |
| `OTHER_READING_TOTAL` (0 or more) | Other reading total | that reading's new total | note: flag, event, change |
| `STATED_AMOUNT_DUE` | Stated amount due | shipment `stated_amount_due` | note: `gap_note` |
| `GAP` | Gap (stated amount due - line total) | shipment `gap` | |
| `REMINDERS` | Reminders | | note: every flag with its severity |
| `RECOMMENDATION` | Recommendation | | note: `recommendation` |

Synthetic example (the shape of the client's first worked example):

```
S1,,ORIGINAL_AMOUNT,Original Amount,,150.00,,,,
S1,,LINE,"SORT,SEGREGATE & STACKING CHG",ACCESSORIAL.SORT_SEGREGATE,40.00,COUNTED,,a,
S1,,TAX,GST - GOODS & SERVICE TAX,TAX.GST,2.00,COUNTED,,a,
S1,,LINE,FUEL SURCHARGE / fuel tier correction (sub-item),RATE_CORRECTION.FUEL_TIER,18.10,COUNTED,,b,
S1,,TAX,GST - GOODS & SERVICE TAX,TAX.GST,0.91,COUNTED,,b,
S1,,NEW_TOTAL,New Disputed Total,,211.01,,,,
S1,,CHANGE_FROM_ORIGINAL,Delta from Original Amount,,61.01,,,,
S1,,STATED_AMOUNT_DUE,Stated amount due,,,,,,MULTI_EXPLANATION_NO_SHIPMENT_GAP
S1,,GAP,Gap (stated amount due - line total),,,,,,
S1,,REMINDERS,Reminders,,,,,,SHIP.GAP.MULTI_EXPLANATION (info)
S1,,RECOMMENDATION,Recommendation,,,,,,PASSED_CHECKS
```

`shipment_table.json` holds the same per shipment as one object (`shipment_table.shipment_json`), plus
`per_explanation_gap`, `prior_history` (status only), `relation_undecided` and `complete`. Both are checked
character for character against the two synthetic worked examples in `tests/test_jake_examples.py`. The two real
examples (git-ignored data; skipped in a clean checkout) are compared item by item with what the client wrote:
original amount, each line's charge name, amount and tax-line status, new total and change; nothing else.

## 5. Extension points

Each has an interface, a default implementation and tests (`tests/test_rollup_t20.py`).

### 5.1 Cross-batch history (`prior_history`)

`rollup.PriorHistory.lookup(shipment_key) -> {status, items, source}`, passed to `pipeline.finish_batch(...,
prior_history=...)`. Default `NoPriorHistory`: every shipment is `NOT_PROVIDED`. `DictPriorHistory` (tests, or an
export of earlier runs): `FOUND` with the items, or `CHECKED_NONE`. The three states are never collapsed:
`NOT_PROVIDED` means nothing is known and must never be shown as "no earlier claim". Today the state is reported only;
it changes no total and no recommendation. Next step: a source that reads earlier runs' `shipments.jsonl`, and a rule
for `FOUND` (for example, an explanation whose `earlier_claim_quote` is set but whose shipment is `CHECKED_NONE`).

### 5.2 Relation suggestions (`relation_suggestions`)

`pipeline.finish_batch(..., relation_suggestions={shipment_key: [suggestion, ...]})`. Default: none. A suggestion is
a free-form dict (proposed: `{line, relation, of, source, evidence}`); it is copied into the shipment's
`relation_suggestions` next to `relation_undecided` and the `SHIP.ROLLUP.RELATION_UNDECIDED` evidence, and changes no
total. A possible history-reading skill would fill it; a reviewer would see both.

### 5.3 Downstream uses

- A payment or audit system reads `new_total`, `default_change` and the `COUNTED` lines with their client names; it
  should treat `recommendation != PASSED_CHECKS` or `complete = false` as "not settled".
- A reviewer works from the table: the lines, the other readings, the gap and the reminders.
- Carrier metrics can count flags per carrier from `shipment_result` joined to `shipment`.
- The gap columns let a reviewer see at once where the carrier's own stated balance and the itemised lines disagree.

## 6. Reviewer feedback (`reviewer_decision`)

The review page (`python -m freight_lineitems.review_ui --run <run>`) appends one row per reviewer action; it never
updates or deletes. Export: `python -m freight_lineitems.review_ui --run <run> --export-decisions decisions.csv`
(`db.export_reviewer_decisions`). Columns, in this order:

| column | meaning |
|---|---|
| `decision_id` | id of the decision |
| `dispute_id` | the explanation (its representative row) |
| `flag_id` | the flag cleared (only for `CLEAR_FLAG`) |
| `action` | `ACCEPT_READING` (the reviewer accepts this reading; not a payment approval), `RETURN_TO_CARRIER`, `CLEAR_FLAG`, `HOLD` |
| `reason` | the reviewer's reason (required for `CLEAR_FLAG`) |
| `bulk_action_id` | id of a bulk action, if any |
| `edited_return_draft` | the return draft as edited by the reviewer (JSON) |
| `flag_feedback` | `USEFUL`, `NOISE`, `WRONG`: the reviewer's view of the flag, for tuning rules |
| `corrected_readings` | a corrected reading, if the reviewer gave one (JSON) |
| `reviewer_id` | internal reviewer id (no names) |
| `decided_at` | UTC timestamp |

Uses: candidates for a reference answer (after filtering), flag precision per code, rule tuning.

## 7. Run record

`run_info.json` `run_record` (`pipeline.run_record`): `git_commit`, `git_dirty`, `redaction_engine`, `skill_layout`,
`skill_sha`, `skill_folder_sha`, `screen_skill_sha`, `examples_sha`, `examples_source`, `rules`, `taxonomy`, `tax`,
`taxonomy_layout`, `screening_enabled`, `model`, `reading_schema_version`, `shipment_schema_version`, and any
`FL_*` environment overrides. `pipeline_run.code_version` in SQLite holds the short commit.

## 8. Every field, and which ones are stable (task 23)

Every field of a shipment result (`shipments.jsonl`, `run.sqlite` `shipment_result.result`) to the second level,
exactly. `tests/test_output_contracts.py` builds shipments on synthetic input and fails when the set of fields it
sees differs from this list. Classes as in the reading contract: **stable** (downstream may rely on it; a change of
meaning or a removal needs a new major `schema_version`, an addition a new minor one) or **diagnostic** (may change
at any time; do not depend on it). `relation_suggestions[]` items are copied as given and their keys are not part of
the contract; `prior_history.items[]` holds what the history source returned.

<!-- fields:start -->
| field | class | present | meaning |
|---|---|---|---|
| `schema_version` | stable | always | `shipment-output-1.0` |
| `shipment_key` | stable | always | SHIPMENT_GID |
| `sap_bol` | stable | always | SAP BOL for display, or null |
| `original_amount` | stable | always | section 2 |
| `explanations` | stable | always | section 2 |
| `explanations[].expl_id` | stable | always | explanation id (`record_id` of its reading output) |
| `explanations[].event_date` | stable | always | Event Date used for ordering |
| `explanations[].first_row` | stable | always | first row number |
| `explanations[].n_rows` | stable | always | rows (order copies) |
| `explanations[].n_orders` | stable | always | distinct PKs |
| `explanations[].usable` | stable | always | the explanation has a usable reading (rule 8) |
| `explanations[].recommendation` | stable | always | the explanation's own recommendation |
| `explanations[].items_total` | stable | always | section 3 |
| `explanations[].stated_amount_due` | stable | always | section 3 |
| `explanations[].gap` | stable | always | section 3 |
| `n_orders` | stable | always | section 2 |
| `lines` | stable | always | section 2.1 |
| `lines[].line_id` | stable | always | section 2.1 |
| `lines[].explanation` | stable | always | section 2.1 |
| `lines[].number_id` | stable | always | section 2.1 |
| `lines[].amount` | stable | always | section 2.1 |
| `lines[].codes` | stable | always | section 2.1 |
| `lines[].label` | stable | always | section 2.1 |
| `lines[].is_tax` | stable | always | section 2.1 |
| `lines[].status` | stable | always | section 2.1 |
| `lines[].replaced_by` | stable | always | section 2.1 |
| `lines[].event` | stable | always | section 2.1 |
| `lines[].added_by_code` | stable | always | section 2.1 |
| `lines[].client_name` | stable | always | section 2.1 (`charge_map.yaml`) |
| `lines[].edi_candidates` | stable | always | section 2.1 |
| `lines[].reference_names` | stable | always | section 2.1 |
| `lines[].coverage_class` | stable | always | section 2.1 |
| `default_change` | stable | always | section 2 |
| `new_total` | stable | always | section 2 |
| `complete` | stable | always | section 2 |
| `other_readings` | stable | always | section 2 |
| `other_readings[].event` | stable | always | event id |
| `other_readings[].flag` | stable | always | the flag that carries this other reading |
| `other_readings[].change` | stable | always | change under that reading |
| `other_readings[].new_total` | stable | always | new total under that reading |
| `other_readings_range` | stable | always | null when there is no other reading |
| `other_readings_range.min_change` | stable | if there is another reading | lowest change |
| `other_readings_range.max_change` | stable | if there is another reading | highest change |
| `other_readings_range.min_new_total` | stable | if there is another reading | lowest new total |
| `other_readings_range.max_new_total` | stable | if there is another reading | highest new total |
| `items_total` | stable | always | section 3 |
| `stated_amount_due` | stable | always | section 3 |
| `gap` | stable | always | section 3 |
| `gap_note` | stable | always | section 3 |
| `prior_history` | stable | always | section 5.1 |
| `prior_history.status` | stable | always | `FOUND`, `CHECKED_NONE`, `NOT_PROVIDED` |
| `prior_history.items` | stable | always | what the history source found |
| `prior_history.source` | stable | always | name of the history source, or null |
| `relation_undecided` | stable | always | section 2 |
| `relation_suggestions` | stable | always; free-form items | section 5.2 |
| `flags` | stable | always | the shipment's own flags |
| `flags[].code` | stable | always | flag code |
| `flags[].severity` | stable | always | `attention`, `return`, `info` |
| `flags[].evidence` | stable | always | one evidence object per finding |
| `flags[].unconfigured` | diagnostic | always | the code is missing from `rules.yaml` (shown as attention) |
| `flags[].origin` | diagnostic | always | `CODE_RULE` or `MODEL_REPORTED` |
| `flags[].paths` | diagnostic | always | where in the record the findings point |
| `flags[].points_to` | diagnostic | always | another record the finding points to, or null |
| `flags[].review_group` | diagnostic | always | display group (`rules.yaml` `review_groups`), or null |
| `flags[].severity_before_subsumption` | diagnostic | if `rules.yaml` `subsumption` lowered the flag (no shipment flag is listed there today) | severity before |
| `flags[].subsumed_by` | diagnostic | if lowered as above | the codes that lowered it |
| `shipment_flags_recommendation` | stable | always | section 2 |
| `recommendation` | stable | always | section 2 |
<!-- fields:end -->
