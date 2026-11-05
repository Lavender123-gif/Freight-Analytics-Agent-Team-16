# B03 Auto-reject pre-check

## What it does
After step 2 and before any model call, decides whether a dispute should go straight back to the carrier (02 D4). The triggers are all code-decidable: empty text, or text with numbers but no words. Exemption: the same shipment has an **earlier** record (strictly earlier Event Date) with the same Delta and a charge name. On a hit without exemption **the model is not called**; an automatic notice to the carrier is built, with all wording taken from the diagnostics catalog (C1).

## Input and output
- Input: step 1-2 diagnostics; earlier records of the same shipment (text, Delta)
- Output: disposition (`AUTO_REJECT` or continue), automatic notice (required change, acceptance criterion)
- Code: `scratch/prototype/pipeline.py` (pre-check branch), `history.py` (pre-check mode), `disposition.py`, `auto_reject` in `rules.yaml` (prototype, unchanged)

## Reproduce with one command
```
sh scratch/deliverables/run.sh B03_auto_reject_precheck.py
```
Results go to `results/summary.md` and `results/examples.md`; per-event dispositions are in the git-ignored `data/interim/deliverables/B03/`.

## Validation data
The full dev split: 908 events (953 rows), not the test set; plus 3 synthetic cases for the exemption and the "earlier records only" rule. Numbers compared with 02 §7.3.

## Results
- All 8 checks and 3 synthetic cases **pass**.
- 10 events (15 rows) auto-rejected: 6 numbers-only, 4 empty, matching 02 §7.3; none of the 10 called the model, all got an automatic notice.
- None was exempted by an earlier explained record.
- For reference: 5 of the 10 have a **later** same-Delta version with words in the same shipment (the rule only looks backwards, so this does not affect the decision), i.e. the missing explanation was in fact supplied later.
- Synthetic: no earlier record → reject; earlier same-Delta explanation → no reject, human review; same-Delta explanation only **later** → still reject.
- The step-5.5 history diagnostics used by the pre-check (pre-check mode) are counted in the summary and match 02 §7.2.

## Limitations
- Whether each reject is right (precision, target 100%, 02 §9.2) needs reviewer confirmation; only the rule logic is tested here.
- Whether PPG wants automatic returns, and through which channel and template, is not confirmed (02 §10.2-12).
- Whether `REC.TEXT.NO_NUMBER` (charge name without amount) should also auto-reject is an open design choice (02 §10.1-8); it currently does not.
- Notice wording is the Chinese draft in the catalog; there is no carrier-facing English version yet.
