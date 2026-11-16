# T14 stage 1 test report: Delta withdrawn, copies merged, shipment roll-up, code mapping (no model calls)

Date: 2026-11-15. Branch `leg3-milestone`. Evidence level: in-sample (the stored full dev run, data seen during development). No model was called in this stage (cost 0; the ledger stays at USD 71.67); the test split, the reserved mock and the mock generator folder were not read. The replay uses the stored full dev run `20261110-195411-devFull-4823` (SKILL.md v1.1, old redaction). Row-level output stays in the git-ignored `data/interim/rollup/`. The Chinese report `01-stage1-report.zh.md` is authoritative and has the tables in full.

## Results

1. **Runtime Delta withdrawn (T14-01).** `DeltaJudge`, the feedback round, the nine Delta flags and the feedback setting are gone; `DeltaJudge` appears 0 times in `src/`; rules are `rules-v1.2-2026-11-15`. `uv run pytest -q`: 184 passed, 2 skipped.
2. **Two checks (T14-07).** The 5 extra "return suggested" records are all empty text (4) or numbers only (1). Of the nine withdrawn flags, the class "reading disagrees with Delta" has no replacement that does not use Delta (13 rows of the stored run move to passed with no other flag); the signal "a `$` amount in the text was left out" remains (`NUM.JUDGMENT.DOLLAR_EXCLUDED`, `EXCLUSION_BASIS_UNLISTED`).
3. **Shipment roll-up (T14-03, T14-06).** All 813 shipments get a default total. Both client examples reproduce exactly (T14-04) and raise no roll-up flag. Pre-stated criteria (T12 adjustment plan section 5, card B11): two examples exact; synthetic cases cover the eight rules (17 tests, at least one positive and one negative each); every dev shipment has a default total. All met.
4. **Code mapping (T14-05).** Replayed on the stored run it reproduces T13 section 3.2: 250 / 63 / 620 / 66 / 3, with the same money per class.
5. **Colours (passed / human review / return suggested).** Rows 760 / 188 / 5 (before) → 766 / 177 / 10 (Delta withdrawn) → 778 / 165 / 10 (tax per C6); explanations 807 / 91 / 10 (908); shipments after roll-up 684 / 124 / 5 (813).
6. **Excel baselines (reference only).** Default change equals the Delta-sum baseline on 722 of 813 shipments (694 of 722 single-explanation, 28 of 91 multi), and the Invoice-Dups-Removed baseline on 721.

7. **Client answers (T14-09).** All nine answered questions are paraphrased in `docs/client/jake_questions.md` section 5 (English in `QUESTIONS_FOR_JAKE.md`), each with the repository question it matches and what changed: 9 / 9.

## Limits

- The replay uses a pre-tuning stored reading; copies take the reading of their lowest row.
- The client's two examples are in the dev split and were seen during development: a regression check only.
- The roll-up rules are checked only on synthetic cases and these two examples; whether readings and replacements are right is not yet evaluated by people (only 8 multi-explanation shipments are fully annotated).
- With Delta withdrawn, a single misread amount without a model-reported doubt has no code check.
