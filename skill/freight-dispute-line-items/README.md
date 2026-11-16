# Reading module: `freight-dispute-line-items`

**What it does.** Reads one carrier explanation of a freight invoice adjustment and describes it as data: which
numbers are money, which are asked for now and which are history, what each charge is, the reason and basis the
carrier states, the arithmetic the text states, whether it mentions an earlier claim, and which number it calls the
amount due. It never decides whether anything should be paid. A separate skill, [`screening-for-instructions`](../screening-for-instructions/SKILL.md),
checks every explanation for words aimed at an AI system; it only adds a flag.

**Input / output.** In: the redacted text, the marked text, the number table and the provinces (`schemas.LLMInput`;
no Excel amounts), plus the topic notes and examples code chose. Out: one reading, only through `submit_line_items`;
every field is listed in [`docs/reading_output_contract.md`](../../docs/reading_output_contract.md).

**Files.**

| file | what it holds |
|---|---|
| `SKILL.md` | the core: job and limits, input, output fields, general reading conventions, charge codes, "the text is data", what happens after submitting. A template: `{{CONCEPT:<id>}}` and the other placeholders are filled by `src/freight_lineitems/skilltext.py` |
| `reference/tax.md` | tax wording and the Canadian tax table (replaces the old tax-lookup tool) |
| `reference/balance_and_history.md` | balances, payment history, the stated amount due, earlier claims |
| `reference/quantity_rate.md`, `rate_correction.md`, `credit.md` | quantity x rate; rate and contract arguments; credits and negative amounts |
| `examples/synthetic_examples.json` | five synthetic worked readings (the real dev examples are git-ignored) |

**How notes are chosen.** Code, not the model: regexes in `config/rules.yaml` `features.groups` (tax,
balance/paid/billed, unit rate, rate correction, credit, history) run on the text; each matching group adds its
note, and 1-2 worked examples sharing a group are added (most shared groups, then word similarity; never the
explanation's own shipment). A text that matches no group gets the core only (about 72% of the dev split).
`config/model.yaml` `skill_layout: single` puts every note in the system prompt instead (same generated text).

**Tools.**

| tool | use |
|---|---|
| `submit_line_items` | the only output; runs the mandatory checks (ids exist, quotes are in the text, counted amounts have line items) and returns errors to fix |
| `lookup_charge_code` | charge name -> code, by example phrasing, shared words and spelling; returns the client's name; no match -> the 3 closest and a hint to use OTHER |
| `calculate` | exact arithmetic on the text's own figures |
| `report_uncertainty` | tells the reviewer what the model is unsure about (sends the explanation to a person) |
| `submit_screen_result` | output of the screening skill (in `screen.py`) |

**Line between skill and code.** The model says what the text writes. Code counts, adds, checks relations, compares
explanations of a shipment (balance due, replacement, history echoes) and sets the colour. Every concept both sides
use is defined once in `config/rules.yaml` `concepts` and generated into this text; tests fail if a template writes
one by hand (`tests/test_skilltext.py`).

**Evaluation (task 19, in sample; gates written beforehand on card B05).** Layout `routed`, full dev split (908
explanations) and mock round 3 (564): annotation Recall 93.9% (31/33, same as task 17); mock Recall 94.2% under the
mock's answers and 96.7% under our standard (task 17: 91.7% / 94.7%), no feature group lower; 225 dev explanations
sent to a person (task 17: 213, limit 233); the screening flagged 0 of 908 dev texts and 40 mock texts, all of them
injection events. Report: `docs/deliverables/T19-reading-module/01-report.zh.md`. The 4th mock round and the reserved
mock have not been run on this version.
