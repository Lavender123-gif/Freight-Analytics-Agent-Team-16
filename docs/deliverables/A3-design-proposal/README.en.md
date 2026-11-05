# A3 Design proposal v3 (02)

> `copies/02_design_proposal.md` is a copy of `docs/analysis/02_design_proposal.md` (copied in task 03 so the folder stands alone). **The original is authoritative**; re-copy after any revision.

## What it does
`docs/analysis/02_design_proposal.md` is the system's settled design: data model, step-by-step spec, the 61-entry diagnostics catalog, rule configuration, the agent and its five tools, dev-split measurements, 10 end-to-end walk-throughs, the evaluation plan (labelled set, metrics, baselines, experiments E1-E9) and open questions. The deliverable is the document itself, plus a consistency check showing that its configuration and numbers agree with the prototype code, the configuration files and a fresh run on the dev split.

## One-page summary
- **Approach**: code first finds and numbers every number in the text; the LLM only judges the numbered items, and its only exit is `submit_line_items`; checks inside that tool return "errors the model can fix" and only record "problems in the data itself"; code then compares with earlier records of the same shipment; every finding becomes a diagnostic, aggregated into flags, and `rules.yaml` computes one of three dispositions: auto-reject, human review, split trusted (02 §1.1).
- **13 departures from the original flow (D1-D12, incl. D3')**: e.g. no `dispute_type` (D1), the auto-reject pre-check runs before the model (D4), the model gets a "keep my reading" exit (D5), three anti-fitting diagnostics (D6), `Dispute Status` stays out of the record object (D7) (02 §1.3).
- **Open**: 11 design choices (02 §10.1, for the project owner) and 12 questions for the client (02 §10.2).

## Input and output
- Document: `docs/analysis/02_design_proposal.md`
- Checked against: `scratch/prototype/diagnostics_catalog.yaml`, `rules.yaml`, prototype code

## Reproduce with one command
```
sh scratch/deliverables/run.sh A3_design_consistency.py
```
Results go to `results/summary.md`.

## Validation data
The full dev split, 908 events (953 rows), code-only part. Not the test set.

## Results
**Everything agrees**:
- Document structure: 13 decisions D1-D12 (incl. D3'), 11 items in §10.1, 12 in §10.2, 9 experiments in §9.4
- The 61 rows of §4.3 match catalog and rules entry by entry (handling, severity, escalation role, points)
- The 9 thresholds of §5.3 match `rules.yaml`
- The 22 diagnostic-count rows of §7.2 (diagnostics / events / rows) and the 3 disposition counts of §7.3 match the rerun exactly

## Limitations
- The check covers "document ↔ configuration ↔ code-only run". Step 3 in the §8 walk-throughs was role-played and says nothing about model performance; the §9 evaluation has not been done.
- §7.3's "about 80 human reviews if the model reads correctly" is an estimate and cannot be checked without a model.
- Two implementation issues known after 02 was written (B07: `DOLLAR_EXCLUDED` does not cover billed / paid / deducted statuses; tolerance 0.005 hard-coded in `tools.py`) are outside this check; see card B07 on the board.
