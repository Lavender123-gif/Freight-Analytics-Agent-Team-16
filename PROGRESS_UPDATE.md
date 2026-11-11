# Progress update since the 2026-11-05 sync (for teammates and their agents)

- **Baseline ("last time")**: commit `5497fd2`, 2026-11-05, "Sync work through 2026-11-05": the last commit sent to the team remote (branch `freight-lineitems`; checked against the remote on 2026-11-10, nothing newer there).
- **This note describes**: branch `autorun-leg2` at commit `6dc2dd4` (2026-11-10), 39 commits after the baseline. It reaches the team remote as one squashed commit on branch `team-update-2026-11-10`, with real record text replaced by synthetic text in tests and the four English entry files moved to the repository root.
- English is the main version; Chinese: [`2026-11-10_progress_update.zh.md`](docs/status/2026-11-10_progress_update.zh.md).

## 1. Summary

At the baseline the model had never been connected and half the prototype conflicted with the 2026-11-04 decisions. Now the whole pipeline runs end to end in `src/`: read-in and redaction, blind parsing with the model, submission checks, flags, three recommendations, a SQLite store, two exports, and a local review screen. It has run on all 953 dev records and on the public mock. 16 of the 23 Must tasks are done and waiting for acceptance; the 7 left are mostly human work (annotation, questions to Jake, final test run, presentations). **Every result so far is in-sample: nothing is verified yet** (verified 0 of 26 cards).

## 2. What changed in the approach (against the 11-05 plan and design)

| Change | Why |
|---|---|
| "Suggest return" is now only for empty text and numbers-only text; everything else that needs attention goes to a human | Only facts the code can decide alone should trigger a return; the owner's rule for leg 2 ([rule changes](docs/autorun/rule_changes_leg2.zh.md)) |
| The colour comes from three flag severities in `config/rules.yaml`, not from scores | Decision 2.3 can be expressed directly, with no score threshold to tune |
| Claimed amounts are summed with sign (credits negative) before the comparison with Delta | Comparing absolute values would accept "refund read as charge" |
| Default redaction changed from Presidio to a word allow-list (**owner has not confirmed, P-20**) | Measured miss rate 29.0% → 10.9% with no measured harm to parsing ([comparison](docs/deliverables/T10-redaction-comparison/README.zh.md)) |
| Review screen is built by us (standard library + SQLite), not an open-source tool | The tools evaluated cannot expand by invoice or count flags by severity; evaluation was from documentation only ([U1](docs/deliverables/U1-review-tool-evaluation/README.zh.md)) |
| The baseline experiment is the "guardrails off" arm: one direct-extraction call, no number table, checks or flags | With checks merely switched off the two arms would not differ |
| Wording tuning uses a "worse" threshold fixed before each run and based on measured run-to-run range; 4 of 5 rounds were reverted | Changes inside the noise must not be kept ([tuning log](docs/autorun/tuning_log.zh.md)) |
| Real dev examples for the SKILL stay in git-ignored files; the repository holds 5 synthetic ones | Real rows may not enter the repository |
| Annotation is 3 packs × 45 records with 15 shared (105 distinct), not "100 with 20 double" | Lets two or three people work in parallel; any two packs give 75 records with 15 double-annotated |
| S1, H1, U1, K1 were planned as human work but were produced by CC | Their outputs came out of the autonomous runs; they still need a human check |
| Reading the test split or raw file is refused in code unless the owner sets a switch | A deny rule alone did not cover every path |

All decisions made without the owner: [decision log](docs/autorun/decision_log.zh.md). Open ones: [pending list](docs/autorun/pending.zh.md).

## 3. What can be run and looked at

Data under `data/` is git-ignored: without the dev split, the mock and an API key you can run the tests and read the documents, but not the pipeline.

| What | Entry |
|---|---|
| Tests (160 pass, 2 skipped) | `uv run pytest -q` |
| Pipeline on a small sample | `uv run python scratch/autorun/run_sample.py demo --n 10 --seed 1` (see [`README.md`](README.md)) |
| Review screen | `uv run python -m freight_lineitems.review_ui --run <run_id> --read-only`, then `http://127.0.0.1:8765/` ([U2](docs/deliverables/U2-review-ui/README.zh.md)) |
| Metrics | `scratch/eval/metrics.py`, definitions in [`docs/eval/metrics.zh.md`](docs/eval/metrics.zh.md) |
| Annotation | guide [`annotation_guide.en.md`](docs/annotation/annotation_guide.en.md); `scratch/annotation/` builds packs, imports returned files, computes agreement |
| Rules, skill, architecture | `config/rules.yaml`, `skill/freight-dispute-line-items/`, [`docs/architecture.md`](docs/architecture.md) |
| Questions for Jake (10, none sent) | [`QUESTIONS_FOR_JAKE.md`](QUESTIONS_FOR_JAKE.md) (tracking table and the not-asking list, in Chinese: [`docs/client/jake_questions.md`](docs/client/jake_questions.md)) |
| Board and progress | `sh scratch/status/run.sh`, `uv run python scratch/plan/progress.py` |

## 4. How to read the numbers

All in-sample. "Final version" = SKILL v1.2, rules v1.1, allow-list redaction. Reports: [leg 2](docs/deliverables/T10-autorun-leg2/test_report.en.md), [guardrails](docs/deliverables/V3a-guardrails/test_report.en.md).

| Number | Data and version | What it does not show |
|---|---|---|
| Passed checks / human review / suggest return = 760 / 188 / 5 | All 953 dev records, **older version** (SKILL v1.1, Presidio) | Not the final version (not re-run). "Passed" means the reading is internally clean and agrees with Delta, not that it is correct or payable |
| 44 / 54 / 2 and 79 / 19 / 2 | Dev samples A and B2, 100 each, final version | Stratified, not frequency samples; wording was tuned while looking at A |
| Claim total correct 333 of 360 | Public mock (375 rows), final version | Mock is synthetic and its expected answers are partly out of date (M1); same version varied 327–330 over three runs, so differences of a few are noise |
| Guardrails on vs off: invented amounts 0 vs 3 (mock) and 4 (A); claim total 333 vs 323; 26 of 27 misreads sent to a human; injection flagged 22 of 30, **threshold 27 not met** | Public mock and sample A, thresholds written before the run | Guardrails make errors visible and stop invented amounts; they do not raise the share read correctly (without one control class: on 283, off 288 of 300) |

No number here says whether the model reads real records correctly: that needs the human annotation (H2a → H3) and the single test-set run (V4).

## 5. How to read the board and the progress file

- [Board](STATUS.md), one colour per card: red = not started; yellow = partly done; light green = built, run on dev, has a deliverable, in-sample evidence only; dark green = met a threshold written in advance on independent data or by human review; grey = removed or not coloured. Now: shaped (light + dark green) 8 of 26 Must cards = 31%; verified (dark green) 0%.
- [Progress file](docs/status/progress.zh.md), by the 23 Must tasks and plan hours (midpoint of each range, 146.5 h in total). **Workload** = hours of tasks done ÷ all hours = 62.8% (CC side 89.8%, human side 0%). **Completion** = hours × factor (accepted 1.0, done but not accepted 0.7, not done 0) ÷ all hours = 44.0%; nothing is accepted yet.
- Card IDs and plan task IDs are two different sets; use the "plan task" column.

## 6. Not done yet

Hours are the plan's ranges; difficulty is CC's estimate. Unassigned: pick what you can take.

| Item | Who can do it | Hours | Difficulty | Note |
|---|---|---|---|---|
| H2a annotate the packs | Human | 10–14 (about 2 per pack) | Low to medium | Packs and guide ready; nobody has trial-annotated yet |
| J01 send questions to Jake, follow up, fill in answers | Human | 4–6 | Low | Blocks tax, currency and duplicate rules |
| D1 mid-term report | Human | 5–8 | Medium | |
| D2 final presentation, demo, written report | Human | 14–22 | High | Needs V4 numbers |
| V4 final test-set run, once | Human opens the switch; CC runs | 2–3 | Low, but one shot | Only after everything else is frozen |
| Accept the 16 done tasks; walk through the review screen as a reviewer | Human | not in plan | Low to medium | Status only changes when a person accepts |
| M1 update mock expectations, add duplicate cases | CC | 5–8 | Medium | Mock is kept by another agent; who edits is undecided |
| H3 score the model against annotations | CC | 3–5 | Low | Waits for H2a; threshold not written yet |
| Re-run all dev records on the final version | CC | under 1, about $10 | Low | Waits for the redaction decision (P-20) |

Optional tasks (R1c, P4b and others) are untouched: see [`docs/plan/2026-11-05_workload_v2.zh.md`](docs/plan/2026-11-05_workload_v2.zh.md).

## 7. Reading order for an agent

1. [`CLAUDE.md`](CLAUDE.md): hard boundaries (no pay/deny logic, no carrier-specific code, data rules, closing checks).
2. This note, then [`docs/autorun/run_state.zh.md`](docs/autorun/run_state.zh.md): where the work stopped.
3. [`docs/decisions/2026-11-04_framework_decisions.zh.md`](docs/decisions/2026-11-04_framework_decisions.zh.md): the frozen design decisions.
4. [`docs/architecture.md`](docs/architecture.md) and [`README.md`](README.md): modules, data flow, commands.
5. [`progress.zh.md`](docs/status/progress.zh.md) and the [board](STATUS.md): task and card status with evidence.
6. [`docs/autorun/pending.zh.md`](docs/autorun/pending.zh.md) and [`decision_log.zh.md`](docs/autorun/decision_log.zh.md): what is open, what was decided and why.
7. `config/rules.yaml` and `skill/freight-dispute-line-items/SKILL.md`: the rules and the model's instructions.

## 8. Known problems and limits

- Nothing is verified; all evidence is in-sample.
- The full dev run is on an older version than the sample and mock numbers.
- Injection detection is below its threshold; with allow-list redaction the model reported fewer injections on the mock (18, against 25–27 before).
- Allow-list redaction still misses 10.9% of synthetic personal-data cases (the suggested target was 2%) and masks charge words it has not seen.
- One known misread remains on sample A: an overpayment read as a charge instead of a credit; the wording that fixed it was reverted for lowering mock results.
- Tax, currency and duplicate handling rest on assumptions that wait for Jake's answers; all tax goes to a human.
- The review screen has a button named "approve": it only records the reviewer's own decision, but the name is close to what the project forbids (P-24).
- Annotation packs cap each text template at 2 records, so they are not an unbiased frequency sample (P-25); the Excel files were checked by program only.
- Model spend so far is $71.67 of a $110 cap (API list-price estimate, not a bill); doing every optional item would exceed the cap.
