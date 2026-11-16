# freight-lineitems

## Base v1 (16 November 2026)

This release is called Base v1. Base v1 = the internal checkpoint `mvp-v1.4` plus the release documents (tag
`base-v1`).

- [docs/reports/README.md](docs/reports/README.md): the midterm report, a case study that follows one explanation
  through every step, and the team update, with who each one is for.
- [docs/flow.md](docs/flow.md): the pipeline diagram, with the planned additions drawn separately.

## Earlier documents

- [PROGRESS_UPDATE.md](PROGRESS_UPDATE.md): the milestone progress report (2026-11-15): what the system does, what is built, what changed after the client's answers, assumptions, progress and next steps.
- [STATUS.md](STATUS.md): the status board, one card per piece of work with its colour and the evidence behind it.
- [WORKFLOW.md](WORKFLOW.md): the pipeline diagram, with one sentence on what each step does.
- [QUESTIONS_FOR_JAKE.md](QUESTIONS_FOR_JAKE.md): the questions for the client and his answers (2026-11-13, paraphrased), with what each answer changed.

## About the project

CMU Intro to AI client project (Team 16). Carriers explain freight invoice adjustments in free text. This project
converts each explanation into structured line items, checks the result for internal consistency, and raises flags
for a human reviewer.

The system does not decide whether a charge should be paid. Every record goes to a reviewer.

- How it works: [docs/architecture.md](docs/architecture.md)
- The skill (instructions, tools, examples): [skill/freight-dispute-line-items/](skill/freight-dispute-line-items/README.md)
- Status board: [STATUS.md](STATUS.md)
  ([中文](docs/status/project_status.zh.md)); pipeline diagram: [WORKFLOW.md](WORKFLOW.md)

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/).
- macOS or Linux. Name redaction reads the system word list `/usr/share/dict/words`.
- An Anthropic API key, only for running records through the model. Tests need no key.

## Setup

```
uv sync
```

This installs the dependencies, including the spaCy model used for name redaction (a download of about 400 MB
the first time).

To call the model, create a file named `.env` in the repository root with one line:

```
ANTHROPIC_API_KEY=<your key>
```

`.env` is git-ignored. An `ANTHROPIC_API_KEY` already set in the environment takes precedence.

### Data rules

- Everything under `data/` is git-ignored. The client's data is confidential: never commit it, and never copy
  real rows into a tracked file (code, tests, docs).
- The test split in `data/processed/` is not read, sampled or inspected during development.
- Text is redacted (names, emails, phone numbers) before it is sent to the model; the pipeline does this itself.

## Run the tests

```
uv run pytest -q
```

Tests make no model call and need no data files; tests that use local data are skipped when it is absent.

A second check that needs no key and no data: run the five synthetic examples of the skill through the real
preparation step and the real submission checks.

```
uv run python scratch/skill/build_synthetic_examples.py --check
```

Expected output: `5 examples valid; committed file matches`.

## Run the whole pipeline without a key (smoke test)

The repository carries a small synthetic batch (`tests/fixtures/smoke/`: 7 rows in the client's column layout, 5
shipments, one with two explanations, one with two order copies) and a stored reading for each explanation. The
offline runner uses every production step except the model call: it reads the CSV, merges order copies, redacts and
parses the text, submits each stored reading through the same checks the model's submission goes through, and then
runs the shipment roll-up and writes every output. No key, no data files, no cost.

```
uv run python -m freight_lineitems.offline --input tests/fixtures/smoke/batch.csv \
    --readings tests/fixtures/smoke/readings.json --name smoke
```

Expected: a JSON summary with `"rows": 7`, `"explanations": 6`, `"shipments": 5`, explanation recommendations
`PASSED_CHECKS` 5 and `HUMAN_REVIEW` 1, and the files listed in [Where the outputs are](#where-the-outputs-are) in
`data/interim/runs/<run_id>/`. The shipment table is `shipment_table.csv` there. Add `--out <folder>` to write
somewhere else. To check that the fixture still matches the skill's synthetic examples:
`uv run python scratch/smoke/build_smoke_fixture.py --check`.

## Run a sample through the pipeline

These commands call the model and cost money. They need the `.env` file and input data under `data/`:

| source | file needed | how to get it |
|---|---|---|
| `dev` (default) | `data/processed/dev.csv` | made once by the project owner from the client's Excel file in `data/raw/` with `FL_ALLOW_RAW=1 uv run python -m freight_lineitems.data_split`. Code refuses to read the raw file or the test split without the owner's switch |
| `mock` | `data/external/mock_public/mock_records.jsonl` | the public mock set (synthetic; ask the team) |

A stratified sample of 10 dev records:

```
uv run python scratch/autorun/run_sample.py demo --n 10 --seed 1
```

The public mock set (all records in the file; `--n` does not apply):

```
uv run python scratch/autorun/run_sample.py demo-mock --source mock
```

The first argument is a name that becomes part of the run id. All options:
`uv run python scratch/autorun/run_sample.py --help`.

What to expect:

- The run prints aggregates only (counts by recommendation and parse status) and the `run_id`.
- Before calling the model, the run reserves its estimated cost (`--est`, USD per record, default 0.04) against
  a cumulative cap (`CAP_USD` in `src/freight_lineitems/budget.py`). If the cap would be exceeded the run stops
  with `budget: …` and makes no call. After the run, one line with the measured token usage is appended to
  `docs/autorun/budget_ledger.jsonl`. Dollar figures there are an API list-price proxy, not a bill.
- Worked examples: if `data/interim/skill/examples.json` (real redacted examples, git-ignored) is absent, the
  run uses the synthetic examples in the skill folder, prints a warning, and records
  `examples_source: synthetic` in its output. Results from the two example sets are not comparable.

## Where the outputs are

Each run writes to `data/interim/runs/<run_id>/` (git-ignored):

| file | content |
|---|---|
| `records.jsonl` | the reading output: one JSON object per explanation with three layers: `facts`, `judgment`, `process` ([contract](docs/reading_output_contract.md)) |
| `records_before_duplicates.jsonl` | the same, saved before duplicate flags are added (model runs only) |
| `shipments.jsonl` | the shipment output: one roll-up per shipment ([contract](docs/shipment_output_contract.md)) |
| `shipment_table.csv`, `shipment_table.json` | the client's table: per shipment the original amount, every line (client name, internal code, amount, status, replaced by; tax on its own line), new total, change, other-reading totals, stated amount due, gap, reminders, recommendation |
| `run.sqlite` | the run in SQLite (schema: `config/schema_v1.yaml`), including `shipment_result` and `shipment_line` |
| `export_facts.json` | for downstream use: only readings that passed the checks and have the recommendation `PASSED_CHECKS` |
| `export_review.json` | for reviewers: every dispute with its recommendation and flags |
| `export_facts.csv`, `export_review.csv` | the same two exports as flat tables for Excel (UTF-8 with BOM): one row per line item, with `signed_amount` (credits negative), and one row per dispute with flag counts and codes. Text cells that would run as a spreadsheet formula get a leading apostrophe |
| `run_info.json` | run id, counts, `run_record` (git commit, redaction method, skill layout, skill / rules / taxonomy versions, model), ledger entry |

The review page (`uv run python -m freight_lineitems.review_ui --run <run_id>`, English) shows in each invoice header
the stored shipment result (recommendation, new total, change, other-reading totals, stated amount due, gap,
shipment reminders; [contract section 2.2](docs/shipment_output_contract.md)). Reviewer decisions recorded there can be
exported: `uv run python -m freight_lineitems.review_ui --run <run_id> --export-decisions decisions.csv`.

Aggregates of a run:

```
uv run python scratch/autorun/analyze_run.py <run_id>
```

## Open the read-only results page

The results page is one static HTML file: no scripts, no buttons, no external resources. It shows row-level
redacted text, so it is written to a git-ignored folder.

1. In `scratch/autorun/build_results_page.py`, set `RUNS` to the run ids you want to show (label → `run_id`).
   The ids in the file are those of the acceptance runs and exist only on the machine that produced them.
2. Build the page:

   ```
   uv run python scratch/autorun/build_results_page.py
   ```

3. Open it in a browser:

   ```
   open data/interim/autorun/acceptance/results.html
   ```

   (`open` is the macOS command; on Linux use `xdg-open`.)

The page labels are in Chinese; the three recommendations are 解析通过检查 (`PASSED_CHECKS`), 建议人工审核
(`HUMAN_REVIEW`) and 建议退回承运商 (`RETURN_SUGGESTED`).

## Extend the system

| to add | edit | then run | notes |
|---|---|---|---|
| a charge code | `config/taxonomy.yaml` (code, category, definition, example phrasings) and `config/charge_map.yaml` (the client's Addenda B name, relation, EDI candidates; normally regenerated with `scratch/rollup/build_charge_map.py` from `docs/deliverables/T13-taxonomy-mapping/scripts/t13_mapping.py`) | `uv run pytest -q tests/test_charge_map.py tests/test_tools_and_rules.py` | the taxonomy is part of the model's prompt: a new code changes the model-facing text, so readings must be rerun before results are comparable |
| a rule (a flag) | the check in code (`checks.py` for one reading, `reading_checks.py` for reading fields, `rollup.py` for a shipment) raises a `Diagnostic` with a new code; its severity (`info`, `attention`, `return`) goes in `config/rules.yaml` `flags`; settings it reads go in `rules.yaml` too; a business term it uses goes in `rules.yaml` `concepts` | `uv run pytest -q` (add a test with a synthetic text for when the rule fires and when it does not) | a code missing from `rules.yaml` still shows up, as an `attention` flag marked unconfigured (`tests/test_tools_and_rules.py`); no carrier names in rules |
| a topic reference file | a new file in `skill/freight-dispute-line-items/reference/`; a regex for the wording that needs it in `config/rules.yaml` `features.groups` and the file name in `features.references` | `uv run pytest -q tests/test_skilltext.py tests/test_concepts.py` | concept text in the file is a placeholder `{{CONCEPT:<id>}}` filled from `rules.yaml` `concepts`; in the `routed` layout code adds the file to an explanation's input when its regex matches |
| a cross-batch history source | a subclass of `rollup.PriorHistory` passed to `pipeline.finish_batch(prior_history=...)` | `uv run pytest -q tests/test_rollup_t20.py` | three states: `FOUND`, `CHECKED_NONE`, `NOT_PROVIDED` ([contract](docs/shipment_output_contract.md) section 5) |

## Try the review screen without a key or data

`scratch/demo/build_offline_demo.py` builds a run from the 7 synthetic rows of `tests/fixtures/smoke` plus 6 more invented
rows (none is a real row), with hand-written readings in place of the model, so it needs no API key, no `data/` folder
and costs nothing. It uses `freight_lineitems.offline`: every stored reading goes through the real submission checks, and
everything after the model is the real pipeline (redaction, number table, flags, recommendation, shipment roll-up,
SQLite store, JSON and CSV exports).

```
uv run python scratch/demo/build_offline_demo.py
uv run python -m freight_lineitems.review_ui --run demo-offline
```

Then open `http://127.0.0.1:8765/`. The review screen is in English. The records cover each colour (passed checks, human
review, return suggested), a sum with a stated total, order copies, a credit with tax, an empty text, digits only, a text
with no number, an instruction-like text, a redacted name and a reading whose quoted evidence is not in the text. The
numbers are not evidence about model accuracy: the readings are written by hand. `tests/test_offline_demo.py` fails if a
rule change moves a demo record to another colour.

If `import freight_lineitems` fails on macOS with the project under `~/Desktop`, the `.pth` file in `.venv` was marked
hidden; run `chflags -R nohidden .venv`.

## Plain-language rule sheet

`docs/rule_sheet.en.md` lists every flag, its severity and when it is raised, in plain English, for reviewers and the client. It is generated from `config/rules.yaml` (severities and numbers) and `config/rule_sheet_text.en.yaml` (wording). After changing either, run `uv run python scratch/rules/build_rule_sheet.py`; `--check` (also run by the tests) fails if wording is missing or the sheet is out of date.

## Repository layout

| path | content |
|---|---|
| `src/freight_lineitems/` | the pipeline: `pipeline.py` (steps, batch runner, `finish_batch`), `agent.py` (loop), `rollup.py` (shipment roll-up, gap, extension points), `charge_map.py` (client names), `shipment_table.py` (client-format table), `offline.py` (run with stored readings), `tools.py`, `checks.py`, `numbers.py`, `textprep.py`, `disposition.py`, `duplicates.py`, `db.py`, `budget.py`, `review_ui.py` |
| `config/` | `rules.yaml` (flag severities, thresholds), `taxonomy.yaml`, `tax_rules.yaml`, `schema_v1.yaml`, `model.yaml` |
| `skill/freight-dispute-line-items/` | `SKILL.md`, its README, synthetic examples |
| `tests/` | pytest suite; `tests/fixtures/smoke/` the synthetic smoke batch |
| `scratch/` | runners and analysis scripts (`autorun/`), status-board generator (`status/`), example generator (`skill/`) |
| `docs/` | architecture note, status board, plans, decisions, run logs and reports (aggregates only) |
| `data/` | git-ignored: raw file, splits, run outputs |

Add a dependency with `uv add <package>`.
