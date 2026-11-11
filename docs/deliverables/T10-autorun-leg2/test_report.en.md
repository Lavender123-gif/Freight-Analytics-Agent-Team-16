# Task 10 second leg: full dev split, rule changes, tuning and this leg's deliverables, test report

- **Evidence level**: in-sample
- **Card colour**: changes supported by this report: [B04](../../../STATUS.md#card-b04) 🟨 yellow → 🟩 light green; new cards [U2](../../../STATUS.md#card-u2), [H1](../../../STATUS.md#card-h1), [V5](../../../STATUS.md#card-v5) are 🟩 light green; [D1](../../../STATUS.md#card-d1), [D2](../../../STATUS.md#card-d2), [B05](../../../STATUS.md#card-b05) and new cards [S1](../../../STATUS.md#card-s1), [K1](../../../STATUS.md#card-k1) stay or start 🟨 yellow. No card reaches dark green.
- **Compiled**: 2026-11-10 (task 10). Aggregates only, no row-level data.
- Chinese version: [test_report.zh.md](test_report.zh.md)

## 1. Claim

1. The main line ran the full dev split, 953 records, with a real model (`claude-sonnet-5-5`): every record reached the model, every record has a run result, no silent failures. The full run used SKILL.md v1.1 with the old redaction engine and was not repeated with the final version (pending item P-23). This is the light-green condition task 03 wrote on card B04, so B04 moves to light green.
2. This leg's rule changes (return kept for two cases only, the exclusion-basis word list) the move of SKILL.md from v1.1 to v1.2 and the change of the default redaction engine to the inverted allow-list were all decided by rules written beforehand; before and after numbers are in section 5.
3. This leg's new deliverables (review interface, annotation packs, metric script, skill folder) each have tests; three of them have run evidence on the dev split or the public mock.
4. None of this is a dark-green claim: all evidence is in-sample, there is no human review, and no dark-green threshold has been written.

## 2. Why this evidence level

The full dev split and samples A and B2 all come from the dev split, whose phrasing was seen while writing SKILL.md, the rules and the basis word list; tuning looked only at A and was verified on B2 and the public mock, but the public mock was used in the deterministic review and in both legs of tuning. The review interface, annotation packs and metric script ran only on the dev split and the public mock. So everything counts as "in-sample". The held-out mock and the test split were not read in this leg.

## 3. Method

- pytest: 160 passed, 2 skipped by default (the two that read the test-split ID column).
- One real-model run over the full dev split; result categories counted from the run database and the retained records.
- Colours recomputed from retained model output to measure each rule change before and after (`scratch/autorun/recolor.py`).
- The public mock run three times on one version to measure the range; two tuning rounds, with the "worse" thresholds written into `docs/autorun/tuning_log.zh.md` before the runs.
- Review interface: 19 tests (synthetic data); also started read-only on the full dev run database, checking the aggregates its API returns and that writes are refused and the database file is unchanged.
- Annotation packs: 14 tests; three packs built on the dev split with a build report.
- Metric script: the `mock` subcommand run on the public-mock run of tuning round 2 and compared with the tuning log.
- Skill folder: 10 tests validate the synthetic examples.

## 4. Data

| Set | Size | Notes |
|---|---|---|
| Full dev split | 953 | run `20261110-195411-devFull-4823`, SKILL.md v1.1, rules v1.1, old redaction engine |
| Sample A | 100 | tuning round 2 `20261110-200845-r2A-ea32`; final version `20261110-201831-rdAallowlist-49dd` |
| Sample B2 | 100 | tuning round 2 `20261110-200845-r2B2-a0fc`; final version `20261110-201832-rdBallowlist-a1fa` |
| Public mock | 375 rows (360 events) | tuning round 2 `20261110-200845-r2Mock-35b8`; final version `20261110-202706-finalMock-1ba4`; synthetic, with answer key |

## 5. Results

### 5.1 Full dev split (the light-green condition of B04)

This run used SKILL.md v1.1 with the old redaction engine (`presidio`) and was not repeated with the final version (pending item P-23).

| Metric | Number |
|---|---|
| Records that reached the model | 953 / 953 |
| Parse passed checks / human review suggested / return suggested | 760 / 188 / 5 (79.7% / 19.7% / 0.5%) |
| First attempt inconsistent with Delta | 44 |
| of which consistent after revision | 4 |
| of which the model insisted and stayed inconsistent | 38 |
| Delta is 0, nothing to compare with | 13 |
| Mandatory checks failed at the end | 1 (retries exhausted; the record carries an explicit failed status, goes to human review, stays out of the downstream export) |
| Model calls | 1028 (1.08 per record on average) |
| Cost (API list-price proxy, not a bill) | the ledger records 7.67 dollars, about 0.0080 dollars per record |

Against the condition: card B04's done-when text is "every record of the full dev split has a real-model run result (passed, failed or auto-rejected), runs can be replayed by version, there is a deliverable to show". All 953 have a result; the run records the versions of the rules, code table, tax table, SKILL.md and examples plus the model settings; the deliverables are this folder and the review interface. That text dates from task 03, before this run. It has no numeric threshold, so it supports light green only.

### 5.2 Rule changes, before and after (no model rerun)

| Change | Rule written beforehand | Result | Decision |
|---|---|---|---|
| "Return suggested" kept only for empty text and numbers-only text | set by the owner | full dev split: 760 / 181 / 12 becomes 760 / 188 / 5, 7 records move from return to human review | changed |
| Demote the model's self-reported doubt to a note? | demote only if the misread rate on the public mock is less than 2 times higher | misread rate 26.3% with a reported doubt, 3.6% without, 7.4 times | stays human review |
| The basis for "has $ but not counted" must be in the word list | adopt only if human review grows by no more than 3 percentage points after weighting | full dev split grows by 0 records, 0.0 percentage points; 13 public-mock rows move to human review | adopted |

Details in `docs/autorun/rule_changes_leg2.zh.md`.

### 5.3 Run-to-run range on the public mock, and tuning

| Metric (one version, three runs) | Min to max | Width |
|---|---|---|
| Claim total correct (360 events) | 327 to 330 | 3 |
| First attempt inconsistent with Delta | 48 to 51 | 3 |
| Records with a self-reported doubt | 75 to 80 | 5 |

Two tuning rounds: round 1 triggered three of the "worse" conditions written beforehand and was reverted; round 2 triggered none of the five and was kept. SKILL.md is now v1.2. Round 2 numbers (v1.2 with the old redaction engine): A 45 / 53 / 2, B2 80 / 18 / 2, public mock 143 / 229 / 3, claim total correct 329 / 360.

### 5.4 Final version (SKILL.md v1.2 plus allow-list redaction)

| Metric | A | B2 | Public mock |
|---|---|---|---|
| Parse passed checks / human review suggested / return suggested | 44 / 54 / 2 | 79 / 19 / 2 | 146 / 224 / 5 |
| First attempt consistent with Delta | 79 | 92 | — |
| First attempt inconsistent with Delta | 10 | 7 | 50 |
| Claim total equals the answer key | — | — | 333 / 360 |

The final version has not been run on the full dev split; the full run used v1.1 with the old redaction engine (pending item P-23).

### 5.5 This leg's new deliverables

| Deliverable | Check | Result |
|---|---|---|
| Review interface (U2) | 19 tests; started read-only on the full dev run database | lists 953 disputes and 813 invoices; in read-only mode a write request is refused and the database checksum is the same before and after |
| Annotation packs and guide (H1) | 14 tests; built on the dev split (rebuilt with the final redaction engine) | 937 of 953 records can be drawn; three packs of 45, 15 in common, 105 distinct records; 88 / 88 / 89 numbers; 5 first-attempt-mismatch records per pack |
| Metric script (V1 in the plan) | run on the public-mock run of tuning round 2 | claim total correct 329 / 360, the three suggestions 143 / 229 / 3, matching the tuning log |
| Skill folder (K1) | 10 tests validate the synthetic examples | pass; nobody other than the author has followed the run instructions |
| Open-source review tool evaluation (U1) | checked item by item against decisions section 6 | conclusion: build our own; based on official documentation only, nothing installed or tried, so not test evidence |

### 5.6 Name redaction comparison

| Variant | Missed on synthetic sentences (1000) | Dev split: digits altered | Dev split: charge words or digits masked | Parsing not worse than the range? |
|---|---|---|---|---|
| former `presidio` | 29.0% | 0 | 0 | baseline |
| `names_list` | 16.8% | 0 | 0 | yes |
| `allowlist` | 10.9% | 0 | 0 | yes |
| `local_ner` | 11.0% | 0 | 0 | no |
| union `allowlist+local_ner` | 4.8% | 0 | 0 | no |

By the selection rule written beforehand (lowest miss rate among the variants meeting all three conditions), the default is now `allowlist`. Details in `docs/deliverables/T10-redaction-comparison/README.zh.md`. Two side effects found after the change are in pending item P-20: charge words missing from the word list get masked; of the 30 injection events of the public mock, those flagged by code or model fall from 25 to 22. The dark-green threshold suggested on card B01 is a name miss rate of at most 2%; none of the five variants reaches it (the chosen one is at 10.9%), so B01's colour does not change.

### 5.7 Spend of this leg

From the ledger `docs/autorun/budget_ledger.jsonl`; an API list-price proxy, not a bill; the four token classes are listed separately. Time window (UTC): first leg from 2026-11-10T21:58:04 to 2026-11-10T23:54:54, second leg from 2026-11-11T00:54:11 to 2026-11-11T01:32:40.

| | Runs | Records | Model calls | input | output | cache write 5m | cache write 1h | cache read | Amount |
|---|---|---|---|---|---|---|---|---|---|
| First leg | 24 | 3,203 | 4,460 | 15,340 | 2,142,244 | 2,070,608 | 0 | 62,296,997 | 32.86 dollars |
| Second leg | 22 | 4,509 | 5,707 | 86,005 | 2,629,307 | 1,965,100 | 0 | 74,282,664 | 38.81 dollars |
| Total | 46 | 7,712 | 10,167 | 101,345 | 4,771,551 | 4,035,708 | 0 | 136,579,661 | 71.67 dollars |

## 6. Limitations

- All evidence is in-sample; no human review, and the held-out mock and the test split were not read.
- The final version (v1.2 plus allow-list redaction) ran only on A, B2 and the public mock, not on the full dev split (pending item P-23).
- 1 record of the full dev split failed the mandatory checks at the end; the cause was not examined record by record.
- Recording decisions in the review interface was exercised only in the synthetic-data tests and on sample A; nobody has walked through it as a reviewer.
- Nobody has tried the annotation guide yet; the metric script's comparison with human annotation was self-tested with fake annotations only.
- The guardrails on-versus-off comparison is a separate report, `docs/deliverables/V3a-guardrails/test_report.zh.md`; one of its thresholds was not met.
- M1 (updating the mock expectations) was not done, and part of the public mock's expected "suggestion" values are out of date, so this report does not use the "suggestion agrees with expectation" number.
