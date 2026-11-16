# Project summary (16 November 2026, Base v1)

Team 16, CMU Intro to AI, client project for PPG. State of the repository at Base v1 (tag `base-v1`, branch `mvp-v1`): the internal checkpoint `mvp-v1.4` plus the
release documents. Midterm report, case study and team update: [`docs/reports/`](../reports/README.md); pipeline
diagram: [`docs/flow.md`](../flow.md).
Chinese version: [`2026-11-16_project_summary.zh.md`](2026-11-16_project_summary.zh.md). Every number below names
its evidence level: **in sample** (data we looked at while building), **independent** (data not used while building)
or **human annotation** (compared with answers written by people).

## 1. The product and who uses it

When a carrier bills PPG more than the planned freight amount, it explains the adjustment in free text ("LIFTGATE $50
+ GST $2.50", "BALANCE DUE IS ..."). Reviewers read these by hand. The system turns each explanation into structured
line items (charge, amount, tax on its own line), checks them against the text itself, rolls every explanation of a
shipment up into the client's table (original amount, each charge, new total, change), and attaches flags that tell a
reviewer where to look. It recommends one of three things: passed checks, human review, or return suggested. It never
decides whether a charge should be paid.

Users: PPG's freight-audit reviewers (the shipment table and the review page), and downstream systems that read the
structured output (the reading contract and the shipment contract).

## 2. Who does what

"Code" is deterministic; "skill" is a model call guided by a skill file; "tool" is a function the model may call.

| job | done by | where |
|---|---|---|
| read rows, merge order copies into explanations | code | `records.py`, `duplicates.py` |
| redact names and emails before any model call | code | `textprep.redact` |
| spot text addressed to a system (injection) | code (two layers) + skill `screening-for-instructions` | `textprep`, `screen.py` |
| number table: every number gets an id | code | `numbers.py` |
| say what each numbered amount is (money or not, asked for now or history, charge, reason, stated amount due) | skill `freight-dispute-line-items` | `SKILL.md` + topic notes chosen by code |
| charge name to code; exact arithmetic | tools `lookup_charge_code`, `calculate` | `tools.py` |
| check a reading (ids exist, phrases are in the text, arithmetic holds) | code inside tool `submit_line_items` | `checks.py` |
| roll a shipment up, BALANCE DUE rule, gap, other-reading totals | code | `rollup.py`, `pipeline.finish_batch` |
| client charge names, client table | code | `charge_map.py`, `shipment_table.py` |
| flags to recommendation | code, thresholds in `config/rules.yaml` | `disposition.py` |
| review decisions | person, on a local page | `review_ui.py` |
| improve rules and the skill | person decides; Claude Code proposes and verifies | `scratch/eval/` |

The model only says what the text writes, referring to number ids: it cannot write a number that is not in the text,
the sign it gives an amount (credit or not) must have support in the text next to that amount (a credit word, parentheses or a
minus sign directly before the number), which code checks; a bare minus sign that may be a separator goes to a person, and it never sees an expected total. Code computes every total and decides every colour.

## 3. Key decisions (one line each; full log in `docs/autorun/decision_log.zh.md`)

1. Every record goes through the model and then to a person; nothing is rejected before the model (decision 2.1).
2. No approve / deny / payment output anywhere; the review button records "accept this reading" (D-99).
3. The client's Delta, Invoice Amount and Invoice Dups Removed are spreadsheet estimates: kept only as an evaluation baseline, never shown to the model (client answer 2026-11-13).
4. Costs belong to the shipment: order copies on one truck are one explanation, read once (client answer).
5. A later explanation of the same charge (finest internal code) replaces the earlier one; different charges add (A3).
6. A BALANCE DUE amount 1.03-1.07x an earlier amount replaces it; wherever BALANCE DUE is written, an amount that fits no decided relation goes to a person (A5, D-81, D-95).
7. Tax is its own line and follows its explanation.
8. The gap (stated amount due minus line total) is its own column, information only (D-96).
9. Names are redacted with an allow-list method chosen by a pre-stated rule (task 10).
10. Each business concept is defined once in `rules.yaml` `concepts` and generated into the skill text (task 19).
11. The reading skill is a core plus topic notes chosen by code (routed layout, task 19).
12. A separate screening skill looks for text addressed to the system; it adds a flag, never changes a reading (D-85).
13. Thresholds for an evaluation are written on the status card before the run (status-board rule).
14. No carrier-specific rules in code; carrier phrasing lives only in example data (project rule).

## 4. How we got here (one line per round)

| round | what it did |
|---|---|
| 01 | Problem inventory: what goes wrong in the free text, from the development split |
| 02 | Design proposal: model reads numbered amounts, code checks |
| 03-04 | Status board with colours backed by test reports |
| 06 | Research, data relations, schema v0 and audit trail design |
| 07-08 | Plan and team split, rescoped to the real hour budget (about 80 team hours) |
| 09 | First autonomous leg: pipeline built end to end, full development run |
| 10 | Second leg: rule changes, redaction comparison, tuning, annotation packs, questions for the client |
| 11 | Clean structure and the first team export |
| 12 | Stocktake and replan after the client's answers (Delta is an estimate, costs belong to the shipment) |
| 13 | Our charge codes mapped to the client's charge list |
| 14 | Milestone build: Delta removed, order copies merged, shipment roll-up, client names, review page |
| 15 | Confusion matrices on "needs a person" against human annotation and the mock |
| 16 | Diagnosis of where misses come from |
| 17 | Four code fixes, rules frozen |
| 18 | Architecture review and redesign of the reading module |
| 19 | Reading module rebuilt (core + topic notes, one definition per concept, screening skill); gates met |
| 20 | Base v1 build: roll-up wired into the main flow, BALANCE DUE anywhere, gap column, client table export, output contracts, extension points, clean-checkout smoke test |
| 20b | Midterm additions: post-hoc metrics, injection results by written text, review page reads the stored shipment result |
| 23 | Fixes after an independent audit: the credit sign is checked against the text, the review list counts shipment reminders, complete field lists in both contracts with a test, the client's real examples compared item by item (tag `mvp-v1.2`) |
| 23b | Credit sign check completed after the audit recheck: a credit word counts only next to its own amount; a bare minus sign that may be a separator goes to a person whichever way it was read (tag `mvp-v1.3`) |
| 23c | The stretch of text that counts as an amount's own is bounded only by money-like numbers (`$` or exactly two decimals): in `CREDIT MEMO 12345 $50.00` the reference no longer cuts the credit word off from the amount; replay on three stored runs unchanged (tag `mvp-v1.4`) |
| 24 | Base v1 release: the version is named Base v1; pipeline diagram with the planned additions (`docs/flow.md`); midterm report, case study and team update in `docs/reports/`; no code change (tag `base-v1`) |

## 5. Results

| what | result | evidence level |
|---|---|---|
| Human-annotated explanations (101 of the development split): share of those needing a person that are sent (Recall) | 93.9% (31/33, 95% CI 80.4-98.3); 100% (31/31, CI 89.0-100) after the two labels corrected by the charge list (D-97) | human annotation, in sample (the split was seen while building) |
| Same set: share of passed explanations that needed a person (FOR) | 3.6% (2/55); 0% (0/55) after D-97 | human annotation, in sample |
| Public synthetic mock, round 3 (568 events), mock answers | Recall 94.2% (245/260), FOR 8.5% (15/176) | in sample (used while building) |
| Same, our written standard | Recall 96.7% (350/362), FOR 6.8% (12/176) | in sample |
| Full development split | 908 explanations, 226 sent to a person (24.9%; 225 in the run, plus 1 sent by the credit-sign check when the stored readings were replayed through the current checks), 813 shipments each with a default total | in sample (no truth) |
| Screening false alarms on the development split | 0 of 908 | in sample |
| The client's two worked examples | real version: every item the client wrote matches (original amount; each line's charge name, amount and whether it is a tax line; new total; change), on the Base v1 readings through the production path and in the client-format table; not compared: line order, recommendation, reminders, gap, and example 2's split over 8 orders. Synthetic version: the table format character for character | in sample, regression |
| Shipment step in the main flow vs. the evaluation scripts (task-19 stored readings) | identical on all 813 + 471 shipments except the new information-only gap flags | in sample, replay |
| Mock round 4, 122 new events in real-data style | Recall 100% (6/6, CI 61.0-100), FOR 0% (0/37); 79 of 116 events the mock expects to pass are sent, mostly replacement reminders (A3, rule 7) | independent, synthetic |
| Mock round 4, the 568 round-3 events | Recall 95.4% (A) / 96.6% (B), FOR 6.8%; the 12 misses are injections. Differs from the round-3 line above because the round-4 files re-judged 51 of these events under the mock's new conventions (same readings and recommendations; the three other earlier misses, one amount for two charges, are no longer positives) | in sample |
| Injection events in the round-4 mock (60, all in the round-3 part), grouped by the written text | counted once per distinct text: 33 of 35 texts sent. Plain English 20/20 sent (18 by the injection flags, 2 by other flags); each category's own misspellings and look-alike letters 10/10 (9 / 1); five templates repeated across all six injection categories 18/30 (3 of the 5 texts sent every time, 2 never: `ovrriide ch3cks`, `bypa ss rev1ew`, 6 events each). No missed event had an amount changed (counted total and shipment new total equal the mock's) | in sample, synthetic |
| Mock round 4, shipment new total equal to the mock's | new part: 89.7% single, 78.1% multi; round-3 part: 94.2%, 84.2% | independent / in sample |
| Mock round 4, shipments passed although their default new total differs from the mock's (**defined after the results**) | 0 of 561. Totals differ on 48 (round-3 part 35: 23 single, 12 multi; new part 13: 6 single, 7 multi); all 48 sent to a person | in sample / independent; synthetic |
| Weighted "close to real" Recall | 99.9%, but 68.1% of real wording has no positive mock event, so it says little | mixed |
| Reserved mocks, test split | not run yet | — |

The main-matrix targets (Recall >= 95%, FOR <= 2%) are met on the annotation set after D-97 and on the round-4 new
events (too few positives to be convincing); FOR is not met on the round-3 mock. Only the round-4 new events are
independent, and they are synthetic.

An independent code audit of the checkpoint found 1 blocking and 3 important issues; all were fixed (rounds 23 to
23c) and confirmed in a recheck.

## 6. Known limits

- Little independent evidence: only the 122 synthetic round-4 events (6 positives) were not seen during development.
- About 59% of development rows come from one carrier and one charge type, so overall numbers mostly describe it.
- A single misread amount is caught only when the model reports a doubt or a code check catches it; there is no
  external total to compare with (by decision).
- Cross-explanation relations are decided by codes, amounts and ratios only; the text's own replacement words are
  not captured yet. Cross-batch history is not connected (shown as "not provided").
- The gap is shown for single-explanation shipments only.
- Redaction misses about 10.9% of synthetic names (task 10 measurement).

## 7. Extension points (each with an interface, a default and tests)

| point | default | where |
|---|---|---|
| cross-batch history | `NOT_PROVIDED` (never shown as "no earlier claim") | `rollup.PriorHistory`, `pipeline.finish_batch(prior_history=...)` |
| relation suggestions (a possible history-reading skill) | none; rule-7 shipments are marked | `finish_batch(relation_suggestions=...)` |
| reviewer feedback | CSV export of `reviewer_decision` | `review_ui --export-decisions` |
| charge codes, rules, topic notes | how-to in the README | `README.md` "Extend the system" |
| output versions | `reading-output-1.0`, `shipment-output-1.0` | `docs/reading_output_contract.md`, `docs/shipment_output_contract.md` |

## 8. Next steps

1. The reserved mocks and the one-time test-split run at the end (method and gates written first).
2. Cross-batch history and the cross-explanation concepts (replacement words, references, dates).
3. Review page by shipment (the shipment table, then each explanation).
4. Midterm slides and the final presentation and report (team).
