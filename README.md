# freight-lineitems

- [PROGRESS_UPDATE.md](PROGRESS_UPDATE.md): what changed since the 2026-11-05 sync, what can be run, and what is not done yet.
- [STATUS.md](STATUS.md): the status board, one card per piece of work with its colour and the evidence behind it.
- [WORKFLOW.md](WORKFLOW.md): the pipeline diagram, with one sentence on what each step does.
- [QUESTIONS_FOR_JAKE.md](QUESTIONS_FOR_JAKE.md): the ten open questions for the client, each with our current assumption.

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

- The run prints aggregates only (counts by recommendation, parse status, Delta consistency) and the `run_id`.
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
| `records.jsonl` | one JSON object per record with three layers: `facts`, `judgment`, `process` |
| `records_before_duplicates.jsonl` | the same, saved before duplicate flags are added |
| `run.sqlite` | the run in SQLite (schema: `config/schema_v1.yaml`) |
| `export_facts.json` | for downstream use: only readings that passed the checks, agree with Delta and have the recommendation `PASSED_CHECKS` |
| `export_review.json` | for reviewers: every dispute with its recommendation and flags |
| `run_info.json` | run id, versions, model settings, ledger entry |

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

## Repository layout

| path | content |
|---|---|
| `src/freight_lineitems/` | the pipeline: `pipeline.py` (steps and batch runner), `agent.py` (loop, Delta judge), `tools.py`, `checks.py`, `numbers.py`, `textprep.py`, `disposition.py`, `duplicates.py`, `db.py`, `budget.py` |
| `config/` | `rules.yaml` (flag severities, thresholds), `taxonomy.yaml`, `tax_rules.yaml`, `schema_v1.yaml`, `model.yaml` |
| `skill/freight-dispute-line-items/` | `SKILL.md`, its README, synthetic examples |
| `tests/` | pytest suite |
| `scratch/` | runners and analysis scripts (`autorun/`), status-board generator (`status/`), example generator (`skill/`) |
| `docs/` | architecture note, status board, plans, decisions, run logs and reports (aggregates only) |
| `data/` | git-ignored: raw file, splits, run outputs |

Add a dependency with `uv add <package>`.
