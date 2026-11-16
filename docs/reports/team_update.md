# Team update: Base v1 (16 November 2026)

For Team 16 members who have not followed the last week. It covers everything that changed since the team export of
10 November (commit `5e28bde`, branch `team-update-2026-11-10`) up to Base v1. Base v1 is the internal checkpoint
`mvp-v1.4` plus the release documents; its tag is `base-v1`.

## What the system does now

It takes the client's export as it is, merges the copies of one carrier note that the export writes once per order,
hides names and emails, and gives every figure in the text an id. A language model then says what each numbered
figure is (a charge, tax, an earlier balance, not money), and code checks that reading against the text: the ids
exist, the quoted words are in the text, the arithmetic holds and every credit sign has support next to its amount.
Code then combines all notes of one shipment into the client's table (original amount, each charge with the client's
name, tax on its own line, new total, change, totals under other readings, stated balance and gap), recommends
"passed checks", "human review" or "return suggested", and writes three documented outputs. A reviewer records
decisions on a local page. The system never decides whether a charge should be paid. The whole flow runs from a clean
checkout without a key on a synthetic batch. Diagram: [`docs/flow.md`](../flow.md).

## What changed since 10 November

| area | change |
|---|---|
| Client's answers (13 Nov) | Delta, Invoice Amount and Invoice Dups Removed are now treated as the client's estimates: no runtime step uses them, they are kept only for evaluation. Costs belong to the shipment. |
| Order copies | Copies of one note for several orders on a truck are merged into one explanation and read once. |
| Reading module | The reading instructions were split into a core and five topic notes (tax, balances, quantity times rate, rate corrections, credits) that code adds only when their trigger words appear; each business term is defined once in `config/rules.yaml`. |
| Injection screening | A fuzzy code check and a separate screening skill were added; a hit sends the explanation to a person and never changes the reading. |
| Shipment roll-up | The roll-up now runs inside every batch, in production, in the offline run and in the evaluation scripts alike. |
| Client-format table | Each run writes `shipment_table.csv` / `.json` in the format the client sent, with the client's charge names (`config/charge_map.yaml`). |
| Output contracts | Two written contracts list every output field and mark it stable or diagnostic; a test keeps them in step with the code. |
| Review page | It reads the stored shipment result (new total, other readings, reminders), its text is in English, and its button means "accept this reading", not a payment approval; decisions export to CSV. |
| Credit sign check | Code checks that every amount read as a credit has a credit word, brackets or an attached minus sign next to it; a minus sign that may be a separator goes to a person. |
| Independent audit | An independent code audit found 1 blocking and 3 important issues (credit sign, review list counts, contract completeness, the client's examples); all were fixed and confirmed in a recheck. |
| Run without a key | `python -m freight_lineitems.offline` runs every step except the model call on a synthetic batch in `tests/fixtures/smoke/`. |

Results are in the midterm report ([`midterm_report.md`](midterm_report.md)); a worked example of one explanation
through every step is in the case study ([`case_study_memo.md`](case_study_memo.md)).

## How to run it

Follow the root [`README.md`](../../README.md):

1. `uv sync` (Python 3.12 and uv; the first run downloads a spaCy model of about 400 MB).
2. `uv run pytest -q`: needs no key and no data.
3. The offline smoke run: `uv run python -m freight_lineitems.offline --input tests/fixtures/smoke/batch.csv --readings tests/fixtures/smoke/readings.json --name smoke`.
4. With an API key in `.env` and data under `data/` (never committed): `uv run python scratch/autorun/run_sample.py demo --n 10 --seed 1`. This calls the model and costs money.
5. Review page: `uv run python -m freight_lineitems.review_ui --run <run_id>`.

## Where things are

| what | where |
|---|---|
| Reports (midterm, case study, this update) | [`docs/reports/`](README.md) |
| Pipeline diagram | [`docs/flow.md`](../flow.md); how the code is organised: [`docs/architecture.md`](../architecture.md) |
| Output contracts | [`docs/reading_output_contract.md`](../reading_output_contract.md), [`docs/shipment_output_contract.md`](../shipment_output_contract.md) |
| Rules and code lists | `config/rules.yaml` (flags, thresholds, business terms), `config/taxonomy.yaml`, `config/charge_map.yaml` |
| Skills | `skill/freight-dispute-line-items/` (reading), `skill/screening-for-instructions/` (screening) |
| How to add a charge code, a rule or a topic note | README section "Extend the system" |

## What comes next (open for anyone to pick up)

Hours are team hours. "Plan" means the estimate in the project plan; "estimate" means a new rough estimate for an item
the plan does not list separately. Difficulty is technical difficulty.

| item | what it involves | hours | difficulty |
|---|---|---|---|
| Cross-batch history and replacement words | connect earlier export files of the same shipment through the existing `prior_history` interface; read words such as "REVISED" that say one note replaces another | 8-14 (plan) | high |
| History-reading skill | a model step that suggests how notes of one shipment relate, through the existing relation-suggestion input; needs its own evaluation | 6-10 (estimate) | high |
| Review page by shipment | open the page by shipment from the client table, then each explanation | 6-10 (plan) | medium |
| Reviewer feedback to rule tuning | a script that summarises exported decisions and flag feedback per rule, and a written way to turn it into rule changes | 4-6 (estimate) | low to medium |
| Stronger injection screening | try an open-source prompt-injection detection model as an extra layer; measure false alarms on the development split first | 6-10 (estimate) | medium |
| Mock expectations | update the synthetic mock's expected answers to the decisions made since, and add cases for merged copies | 5-8 (plan) | low to medium |
| Hand annotation | the plan asks for 20 explanations labelled by two people; 15 are | 2-3 (estimate) | low |
| Final independent check | the reserved synthetic mocks and the one run on the held-out test split (method and thresholds written first) | 2-3 (plan) | low, but must follow the written order |
| Midterm slides | slides from the midterm report | 5-8 (plan) | low |
| Final presentation, demo and report | the end-of-course deliverables | 14-22 (plan) | low to medium |
