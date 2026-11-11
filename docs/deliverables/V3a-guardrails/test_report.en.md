# V3a guardrails on vs off, test report

- **Evidence level**: in-sample
- **Card colour**: 🟨 yellow (board: [V2](../../../STATUS.md#card-v2), plan task V3a)
- **Compiled**: 2026-11-10 (task 10). The plan and thresholds are in `plan.zh.md` in this folder, written and committed before any model call of the off arm and unchanged since. Aggregates only, no row-level data.
- Chinese version: [test_report.zh.md](test_report.zh.md)

## 1. Claim

**By the rule written beforehand, the conclusion is "not every threshold is met": T4 (injection) is not met.** T1, T2, T3 and T5 are met. So "the guardrails are effective on these data" cannot be written. This is pending item P-21.

## 2. Why this evidence level

The public mock and sample A were both used in tuning, so this is in-sample. The plan said beforehand: the card can reach light green at most.

## 3. Method

- Guardrails on: the final version of this design (SKILL.md v1.2 plus allow-list redaction); the numbers come from this leg's final runs, no extra run.
- Guardrails off: direct extraction, one model call, no number table, no checks, no flags; run once separately. Dev-split text is still redacted; the public mock uses the original text.
- Both arms use the same model and settings. Metrics and thresholds follow T1 to T5 in `plan.zh.md`; script `scratch/eval/v3a_off_arm.py`.

## 4. Data

| Set | Size | Run with guardrails on | Run with guardrails off |
|---|---|---|---|
| Public mock | 375 rows (360 events) | `20261110-202706-finalMock-1ba4` | `20261110-200849-v3aOffMock-cd08` |
| Dev sample A | 100 | `20261110-201831-rdAallowlist-49dd` | `20261110-201059-v3aOffA-b3db` |

## 5. Results vs thresholds

| # | What | Threshold (written beforehand) | On | Off | Met? |
|---|---|---|---|---|---|
| T1 | Records submitting an amount that is not in the text | on: 0 records | 0 records | public mock 3 records, sample A 4 records | met |
| T2 | Public-mock events with the claim total read correctly | on not lower than off minus the range width 3 | 333 / 360 | 323 / 360 | met |
| T3 | Share of misread public-mock events that carry "human review suggested" | on at least 80% | 26 of 27 (96%) | no flags by definition | met |
| T4 | Of the 30 injection events, how many are flagged; amount-changing injections read correctly | at least 27 flagged, and correct readings not fewer than off | 22 flagged (17 of them by code); 4 of 5 read correctly | 5 of 5 read correctly | **not met** (neither condition) |
| T5 | Records whose digits were altered by redaction | on: 0 records | 0 records (the chosen redaction engine misses 10.9% of names) | all names reach the model by definition | met |

Reported only, no threshold:

| What | On | Off |
|---|---|---|
| Public-mock events read correctly without the disputed control class (300 events) | 283 | 288 |
| Misread public-mock events | 27 | 37 |
| Of the 30 injection events, claim total read correctly | 29 | 30 |
| Sample A records consistent with Delta (89 records with a value to compare; on uses the first submission) | 79 | 70 |
| Model calls per record: public mock / sample A | 1.50 / 1.14 | 1.00 / 1.00 |
| Cost per record (API list-price proxy, not a bill): public mock / sample A | 0.0103 / 0.0089 dollars | 0.0021 / 0.0024 dollars |

## 6. Limitations

- In-sample evidence; the public mock is synthetic, with only 30 injection events and only 5 amount-changing ones, so a difference of 1 changes the T4 conclusion.
- T2 is met thanks to the disputed control class (60 events): without it, the off arm reads 5 more events correctly than the on arm. The answer key of that class is itself disputed (pending item P-10). The guardrails make errors visible and keep out amounts that are not in the text; they do not raise reading accuracy (pending item P-22).
- The off arm has no flags at all, so none of its 37 misread events would be seen by anyone; of the 27 misread events of the on arm, 1 is "parse passed checks".
- 1 record of the off arm's public-mock run errored or returned no items.
- The dev split has no answer key, so sample A can only compare "consistent with Delta", not "read correctly"; that waits for human annotation (H2a, H3).
- After the switch to allow-list redaction the model reports fewer injections on the public mock; flagged injection events fall from 25 to 22 (pending item P-20).
