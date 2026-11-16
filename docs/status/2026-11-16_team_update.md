# Team update: what changed since the last push (10 November)

For Team 16. The last branch pushed to the team repository was `team-update-2026-11-10`. This page lists what changed
between that push and the branch `team-update-mvp-v1` (code tag `mvp-v1.2`). Details: `PROGRESS_UPDATE.md` (11-15
milestone), `docs/status/2026-11-16_project_summary.md` and `docs/status/2026-11-16_midterm_report.md`.

## What the client told us (13 November) and what it changed

- Delta, Invoice Amount and Invoice Dups Removed are the client's own spreadsheet estimates. The model no longer sees
  or is checked against them; they are kept only as an evaluation baseline.
- Costs belong to the shipment (SAP BOL). Order copies of one explanation are merged and read once, and every
  shipment is rolled up into the client's table: original amount, each charge with the client's name, tax on its own
  line, new total, change.
- Our 37 internal charge codes are mapped to the client's charge list (`config/charge_map.yaml`).

## What is new in the code

| area | change |
|---|---|
| Reading | The skill is now a core plus five topic notes chosen by code (`routed`); every business term is defined once in `config/rules.yaml` `concepts`; two new reading fields (earlier-claim quote, stated amount due) |
| Safety | A second, fuzzy injection check before redaction, and a separate screening skill that flags text addressed to the system |
| Shipment step | `pipeline.finish_batch` runs the roll-up inside every run; production, the offline run and the evaluation scripts use this one function |
| BALANCE DUE | Compared with the explanation's other amounts wherever it is written; only an amount that fits no decided relation goes to a person |
| Gap | Line total, stated amount due and their difference are shown per explanation and per single-explanation shipment; information only |
| Outputs | `shipments.jsonl`, `shipment_table.csv` / `.json` (client format), two new SQLite tables; `schema_version` on both outputs; contracts in `docs/reading_output_contract.md` and `docs/shipment_output_contract.md` |
| Review page | The APPROVE button is now `ACCEPT_READING` ("accept this reading", not a payment approval); decisions export to CSV |
| Runs | Each run records the git commit, redaction method, skill layout, versions and model |
| No key needed | `python -m freight_lineitems.offline` runs the whole pipeline on the synthetic batch in `tests/fixtures/smoke/` with stored readings (see README) |
| Extension points | Cross-batch history (three states, default "not provided"), relation suggestions for a later history skill, reviewer feedback export |
| Audit fixes (16 Nov) | After an independent audit: code checks that a credit (negative amount) has support in the text; the review list counts shipment-level reminders; both output contracts list every field, marked stable or diagnostic, and a test keeps them in step with the code; the client's two real examples are compared item by item (all match) |

## Evaluation since the last push

- Hand annotations (101 explanations from the team's packs): the share of explanations needing a person that the
  system sends to one is 93.9% (31/33), 100% (31/31) after two labels were corrected by the charge list. In sample.
- Public mock round 3: 94.2% / 96.7% (mock answers / our standard). In sample. The same events score 95.4% / 96.6%
  in round 4 because the round-4 files re-judged 51 of them under the mock's new conventions; our readings and
  recommendations did not change.
- Public mock round 4: results in the midterm report; its 122 new events are the first independent check. It also
  has the injection results grouped by the written text and the post-hoc "passed but total wrong" count (0 of 561).

## What you can do

- Run `uv run pytest -q` and the offline command in the README on a fresh clone; tell us if any step fails.
- Read the two output contracts if you build anything on the outputs.
- Midterm report: `docs/status/2026-11-16_midterm_report.md` is a draft for the slides.
