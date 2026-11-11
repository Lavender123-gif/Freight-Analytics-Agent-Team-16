# Task 09 first leg: main line with a real model, test report

- **Evidence level**: in-sample
- **Card colour**: 🟨 yellow (board: [B04](../../../STATUS.md#card-b04), [D1](../../../STATUS.md#card-d1), [D2](../../../STATUS.md#card-d2))
- **Compiled**: 2026-11-10 (task 09). Numbers from `scratch/autorun/acceptance_summary.py`; acceptance package entry `docs/autorun/acceptance/README.zh.md`.
- Chinese version: [test_report.zh.md](test_report.zh.md)

## 1. Claim

The main line in `src/freight_lineitems/` (ingest, redaction, number tokens, blind-parsing agent loop, submission checks, three-tier rules, two-level duplicate flags, SQLite and both exports) runs end to end with a real model (`claude-sonnet-5-5`, thinking off): 273 distinct dev-sample records and 375 public-mock rows, every record reached the model, all mandatory checks passed, no silent failures. This is **not** a light-green claim: the full dev split was not run and no threshold was set in advance.

## 2. Why this evidence level

Samples A and B2 come from the dev split, whose wording we saw while writing SKILL.md and the rules; wording tuning looked only at A and was validated on B (B2 after the audit) and the mock, but we also looked at the mock's wording during the deterministic review. All of it counts as in-sample.

## 3. Method

- pytest: 69 tests (the 2 that read test-split IDs skip by default).
- Codex's 88 boundary cases reviewed one by one (`docs/autorun/boundary_cases_review.zh.md`).
- Public mock, deterministic layer (`docs/autorun/mock_deterministic_review.zh.md`).
- Real-model runs: samples A and B2 (100 each), public mock 375 rows, the first 50 of A repeated 3 times.

## 4. Data

| Set | Size | Note |
|---|---|---|
| Sample A | 100 | dev split, stratified by carrier x wording; example records and their shipments excluded |
| Sample B2 | 100 | same, also excluding records sharing a shipment, invoice or content with A, and the first 26 records |
| Public mock | 375 rows (360 events) | synthetic, with ground truth |

## 5. Results vs threshold

| Metric | A | B2 | mock |
|---|---|---|---|
| passed checks / human review / return suggested (sample) | 43% / 49% / 8% | 81% / 17% / 2% | 41% / 57% / 2% |
| first attempt inconsistent with Delta | 10% | 9% | 13.3% |
| mandatory checks finally failing | 0 | 0 | 0 |
| same colour in all 3 repeats | 98% (50 records) | — | — |
| mock claim total equals ground truth | — | — | 329 / 360 |

Threshold: not set in advance, so no light or dark green.

## 6. Limits

- The full dev split was not run; the colour distribution weighted to dev frequencies covers only the strata in the samples (see the package).
- The model's self-reported doubts appear in all 3 repeats only 57% of the time.
- After "inconsistent" the model almost always keeps its reading (all 50 on the mock, 21 of which were wrong readings).
- History checks (R1c) and the alias table (P4b) are not done.
