# Reading output contract

Task 19 addendum. What the reading module (the skill `freight-dispute-line-items`, its tools and the checks that run on
one explanation) hands to the steps after it. Cross-explanation and cross-batch features (shipment roll-up,
cross-batch history, a possible history-reading skill) take this output as their input, so these fields are fixed
before the next full rerun. Definitions of the business terms live in `config/rules.yaml` `concepts`; this page
cites them by id. All examples are synthetic.

## 1. Where the output is

One output record per explanation (`pipeline.assemble`; stored in `data/interim/runs/<run>/records.jsonl` and in
`run.sqlite`). Every record carries `schema_version` (`reading-output-1.0`, task 20); the shipment step that reads it
is described in `docs/shipment_output_contract.md`. The reading is `facts.reading`, exactly as the model submitted it and as `submit_line_items`
accepted it. Code adds facts derived from it (`facts.claim`, `facts.stated_amount_due`) and flags (`judgment`).

Example text used below: `DETENTION BILLED $200.00 PAID $150.00 BALANCE DUE $50.00 + HST`
(number table: `#1` = $200.00, `#2` = $150.00, `#3` = $50.00).

## 2. Fields written by the model (`facts.reading`)

| field | meaning | values | example |
|---|---|---|---|
| `response_type`, `reason` | protocol: first submission or a revision after failed checks | `FIRST`, `REVISED`, `INSISTED`; reason text or null | `FIRST`, null |
| `numbers[].id` | the number's id in the number table | `#n` | `#3` |
| `numbers[].kind` | what the number is | `CHARGE_AMOUNT`, `UNSPECIFIED_AMOUNT`, `TAX_AMOUNT`, `TOTAL`, `RATE`, `QUANTITY`, `REFERENCE` | `CHARGE_AMOUNT` |
| `numbers[].status` | asked for now, history, or not money (`concepts.counted`, `concepts.history`) | `CLAIMED`, `UNPAID`, `BILLED`, `PAID`, `DEDUCTED`, `NONE` | `#1` BILLED, `#2` PAID, `#3` UNPAID |
| `numbers[].is_credit` | the text presents it as a credit (`concepts.credit`). Checked by code (tasks 23, 23b, 23c) against the amount's local scope, the text from the end of the previous money-like number-table entry to the start of the next one (money-like: a `$` or exactly two decimals, judged from the number table, not from the reading; references, quantities, weights and dates do not bound it; not `evidence_phrase`): true needs a credit word (`rules.yaml` `exclusion_basis.categories.credit`) in the local scope, parentheses around the amount, or a minus sign directly before it, else the submission is refused. For counted item amounts: read as false with a credit word in the local scope or in parentheses gets `NUM.JUDGMENT.CREDIT_MARK_NOT_CREDIT` (attention); a minus sign directly before it ('-$20', '$-20', 'PLACEMENT-$69.00') with no credit word and no parentheses gets `NUM.JUDGMENT.CREDIT_MINUS_UNCLEAR` (attention) whether read true or false, because such a dash may be a separator. A spaced dash ('- $18.00') is no support and raises nothing | true / false | false |
| `numbers[].charge_codes` | internal taxonomy codes; several = one amount for several charges | list of codes from `config/taxonomy.yaml` | `["DETENTION_STORAGE.DRIVER_DETENTION"]` |
| `numbers[].other_phrase` | the charge name when the code is `OTHER` (`concepts.other`) | verbatim text or null | null |
| `numbers[].evidence_phrase` | words supporting the judgment | verbatim text | `BALANCE DUE $50.00` |
| `numbers[].exclusion_phrase` | why a `$` amount is not counted (`concepts.exclusion_basis`) | verbatim text or null | `#1`: `BILLED` |
| `line_items[]` | one per counted amount (`amount_ref`), plus one per charge named without an amount (`amount_ref` null, codes on the item) | see the fields below | `{amount_ref: "#3"}`, `{amount_ref: null, charge_codes: ["TAX.HST"]}` |
| `line_items[].raw_charge_label` | the charge name as written | verbatim text or null | `DETENTION` |
| `line_items[].carrier_stated_reason`, `carrier_stated_basis`, `carrier_stated_basis_type` | the carrier's stated reason and basis, not verified | verbatim text or null; `PPG_NOTIFIED`, `PPG_APPROVED`, `PPG_LIST`, `CONTRACT_OR_TARIFF`, `SHIPPING_DOCUMENT`, `OTHER`, `NONE` | null, null, `NONE` |
| `relations[]` | arithmetic the text states; code recomputes it | `PRODUCT`, `SUM`, `TAX` with operand ids and a result id or null | none here |
| `unrecognized_reads[]` | the model's reading of chunks the parser could not read | digits read + a number judgment | none here |
| `earlier_claim_quote` | the words that mention an earlier claim, dispute or request for this shipment (`concepts.earlier_claim_mention`); payment history alone is not one | verbatim text or null | null (for `EARLIER CLAIM $100.00 FOR PRIOR ACCESSORIAL`: `EARLIER CLAIM`) |
| `stated_amount_due_id`, `stated_amount_due_evidence` | the number the text presents as what is owed now in total, and the words that say so (`concepts.stated_amount_due`); read by no rule | number id and verbatim text, or both null | `#3`, `BALANCE DUE $50.00` |

Every phrase is checked against the redacted text and every id against the number table before the reading is
accepted (`checks.check_submission`). "Verbatim" in this table means found in the redacted text **ignoring case and
whitespace**, not character for character (section 6, last paragraph).

## 3. Facts code derives from the reading

| field | meaning | example |
|---|---|---|
| `facts.parse_status` | `PASSED_CHECKS` when the reading was accepted; otherwise why not | `PASSED_CHECKS` |
| `facts.claim.counted_ids`, `signed_sum`, `expected_tax` | counted numbers (`claim.is_counted`), their signed sum, the implied tax for a tax named without an amount | `["#3"]`, `50.00`, `6.50` (ON) |
| `facts.stated_amount_due` | `{number_id, value, evidence_phrase}` from the two fields above, with the value from the number table | `{#3, 50.00, BALANCE DUE $50.00}` |
| `facts.number_table`, `facts.text_redacted` | what the model read (ids, values, spans, `has_dollar`) | — |
| `judgment.flags`, `judgment.recommendation` | flags from all checks, and the recommendation they give | `CLAIM.EARLIER_CLAIM_MENTIONED` when a quote is given |
| `process.routing`, `process.screening` | which topic notes and examples were added; the screening answer | `{references: [balance_and_history.md, tax.md]}` |

## 4. Which downstream step uses which field

| field | shipment roll-up (today, `pipeline.finish_batch` -> `rollup.py`) | cross-batch history (next week) | history-reading skill (possible later) |
|---|---|---|---|
| `parse_status` | yes: an unusable reading leaves the explanation out (rule 8) | yes | yes |
| `numbers[].kind`, `status`, `is_credit` | yes: counted lines, history amounts (rule 9) | yes: earlier batches' history and counted amounts | yes |
| `numbers[].charge_codes`, `other_phrase` | yes: same charge (rule 2), undecidable (rule 7) | yes: same charge across batches | yes |
| `line_items[].raw_charge_label` | yes: label of a line, OTHER comparison | yes | yes |
| `number_table` values, spans, `has_dollar`; `text_redacted` | yes: BALANCE DUE position and ratio (rule 6) | yes | yes |
| `earlier_claim_quote` | not yet | yes: an explanation that mentions an earlier claim but has no earlier explanation in this or an earlier batch gets a reminder | yes: the quote says which claim to look for |
| `stated_amount_due` | yes since task 20: the gap columns (`concepts.gap`, shipment contract section 3); no rule reads it, the gap only raises info flags | candidate: compare with the shipment's running total | yes |
| `relations[]` | no | no | yes |
| `carrier_stated_*` | no | no | yes |
| `judgment.recommendation` | yes: the shipment takes the worst of its explanations | yes | — |

## 5. Fields the cross-explanation work will still need (not implemented)

Listed so the next rerun can add them together; none exists today.

| field (proposed) | why it is needed |
|---|---|
| `numbers[].replaces_quote` - words saying this amount replaces or corrects an earlier one ("REVISED", "CORRECTED AMOUNT", "INSTEAD OF") | rules 2, 5 and 7 now infer replacement from codes and ratios only; when the codes differ or no charge is named, the text's own word is the best evidence and today it is not captured |
| `numbers[].reference_type` for `REFERENCE` numbers (invoice, PRO, BOL, PO, other) | cross-batch history must link explanations that cite the same invoice or PRO number; today a reference is not sub-typed |
| `numbers[].date_ref` - the date token an amount is tied to ("BILLED ON 6/22") | ordering history amounts within and across batches; dates are in the number table but not linked to amounts |
| `stated_amount_due_scope` - whether the stated amount covers only this text or the whole shipment so far | needed before `stated_amount_due` can be compared with a running total (the 'gap' column) |
| `history_refers_to` - whether a history amount belongs to this shipment's earlier invoice or to another document | rule 9 (history echo) assumes the same shipment; the text sometimes cites another invoice |

## 6. Every field, and which ones are stable (task 23)

The table below lists every field of an output record to the second level, exactly. `tests/test_output_contracts.py`
builds records on synthetic input (model run, model not run, screening run, order copies) and fails when the set of
fields it sees differs from this list, so a field added or removed without updating this page breaks the build.

Classes:

- **stable**: a downstream step may rely on it. Changing its meaning or removing it needs a new major version of
  `schema_version`; adding a stable field needs a new minor version.
- **diagnostic**: kept so a person can see how the reading was made (attempts, the model transcript, raw
  diagnostics). It may change at any time without a version change; downstream steps must not depend on it.

Deeper levels: `facts.reading` is described field by field in section 2, `facts.claim` and `facts.stated_amount_due`
in section 3. `judgment.flags[]` objects have `code`, `severity`, `evidence` (stable) and `unconfigured`, `origin`,
`paths`, `points_to`, `review_group`, and, when a flag was lowered by `rules.yaml` `subsumption`,
`severity_before_subsumption`, `subsumed_by` (diagnostic). `facts.number_table` is the parser's output
(`schemas.ParseResult`): `numbers[]` with `id`, `raw`, `span`, `value`, `digits`, `has_dollar` and the parse
features, `dates[]`, `unrecognized[]`, `marked_text`, `coverage_ok`; of these, ids, `raw`, `span`, `value` and
`has_dollar` are stable, the parse features are diagnostic.

<!-- fields:start -->
| field | class | present | meaning |
|---|---|---|---|
| `schema_version` | stable | always | `reading-output-1.0` |
| `record_id` | stable | always | record id of the explanation's representative row (its first row) |
| `facts` | stable | always | what the text says and what code derived from it |
| `facts.source` | stable | always | the representative row's input fields as read (`records.InputRecord`, without the original text). It includes `delta`, `invoice_amount` and `invoice_dups_removed`, the client's own spreadsheet estimates: stored for evaluation only, read by no rule |
| `facts.invoice_key` | stable | always | carrier and carrier invoice, the review page's invoice |
| `facts.origin_country` | stable | always | country of the origin province or state |
| `facts.destination_country` | stable | always | country of the destination province or state |
| `facts.currency` | stable | always | `USD` (client answer: all amounts are USD) |
| `facts.currency_basis` | stable | always | `FIXED_USD` |
| `facts.text_sha256` | stable | always | hash of the normalised original text (identifies the text without holding it) |
| `facts.text_redacted` | stable | always | the text the model read, names and emails replaced by placeholders |
| `facts.number_table` | stable | always | the parser's number table (see above) |
| `facts.parse_status` | stable | always | section 3 |
| `facts.reading` | stable | always | the model's reading, section 2; null when there is none |
| `facts.claim` | stable | always | section 3; null when no reading passed the checks |
| `facts.stated_amount_due` | stable | always | section 3; null when the reading names none |
| `facts.source_rows` | stable | always | every row of this explanation (`record_id`, `row_number`, `pk`); added by `pipeline.finish_batch` |
| `facts.n_rows` | stable | always | number of rows (order copies) of this explanation |
| `facts.n_orders` | stable | always | distinct order numbers (PKs) among them |
| `judgment` | stable | always | flags and the recommendation (rules only) |
| `judgment.flags` | stable | always | the flags, grouped by code, most pressing first |
| `judgment.recommendation` | stable | always | `PASSED_CHECKS`, `HUMAN_REVIEW` or `RETURN_SUGGESTED` |
| `judgment.decisive_flags` | stable | always | the flag codes that decided the recommendation |
| `judgment.return_draft` | stable | always | the draft request to the carrier when a `return` flag exists, else null; never sent by the system |
| `judgment.rules_version` | stable | always | `rules.yaml` version that produced the flags |
| `judgment.recommendation_zh` | diagnostic | always | Chinese label of `recommendation`; use `recommendation` |
| `judgment.diagnostics` | diagnostic | always | the raw findings behind the flags; use `judgment.flags` |
| `judgment.duplicate_clear_rules_applied` | diagnostic | if the explanation has order copies that raised `SHIP.COPY.SAME_OR_NO_PK` | the `rules.yaml` `duplicates.clear_rules` in force |
| `process` | diagnostic | always | how the reading was made |
| `process.model_ran` | diagnostic | always | whether the model was called; use `facts.parse_status` |
| `process.routing` | diagnostic | if the model ran | which topic references and examples code added to the input (`offline` for stored readings) |
| `process.screening` | diagnostic | if the screening call ran | the screening answer, call count and usage |
| `process.attempts` | diagnostic | if the model ran | every submission (the first included), its repair errors and diagnostics |
| `process.final` | diagnostic | if the model ran | status and number of the attempt kept |
| `process.n_model_calls` | diagnostic | if the model ran | model calls for the reading |
| `process.transcript` | diagnostic | if the model ran | the full model transcript: requests, responses, tool calls, usage (redacted text only) |
| `versions` | stable | always | versions of everything that shaped the reading |
| `versions.rules` | stable | always | `rules.yaml` version |
| `versions.taxonomy` | stable | always | `taxonomy.yaml` version |
| `versions.tax` | stable | always | tax table version |
| `versions.taxonomy_layout` | stable | always | how the code list was given to the model |
| `versions.skill_sha` | stable | always | hash of the reading skill's text |
| `versions.skill_folder_sha` | stable | always | hash of the reading skill's folder |
| `versions.skill_layout` | stable | always | `routed` or `single` |
| `versions.screen_skill_sha` | stable | always | hash of the screening skill |
| `versions.examples_sha` | stable | always | hash of the worked examples |
| `versions.examples_source` | stable | always | where the worked examples came from |
| `versions.system_prompt_sha` | stable | always | hash of the system prompt sent; null when no prompt was built (offline) |
<!-- fields:end -->

Phrase matching (audit F-05): every phrase field above described as "verbatim" (`evidence_phrase`, `other_phrase`,
`exclusion_phrase`, `raw_charge_label`, `carrier_stated_reason`, `carrier_stated_basis`, `earlier_claim_quote`,
`stated_amount_due_evidence`) is accepted when it appears in the redacted text **ignoring case and whitespace**
(`checks.phrase_found`: an exact match first, then both sides upper-cased with all whitespace removed). It is not a
character-for-character match, and the output holds no span for it: `LIFT GATE $50.00` is accepted for the text
`Liftgate $ 50.00`. Amounts are never taken from a phrase; they come from the number table by id.
