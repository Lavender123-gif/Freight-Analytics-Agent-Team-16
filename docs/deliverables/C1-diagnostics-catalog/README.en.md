# C1 Diagnostics catalog

## What it does
Every kind of problem the system finds is one "diagnostic" in the catalog, coded in three parts: `OBJECT.SUBCLASS.TYPE` (object = where it sits in the record JSON: `REC`, `NUM`, `ITEM`, `CLAIM`, `HIST`, `RUN`). Each diagnostic has a fixed trigger, evidence format, handling (return to the model / record only), text for the reviewer, request to the carrier, and acceptance criterion. Wording in reject notices and reviewer drafts may **only** come from here; the code writes no free text (02 §4). Severity and escalation role are not in the catalog but in `rules.yaml` (C2).

## Input and output
- File: `scratch/prototype/diagnostics_catalog.yaml` (prototype, unchanged)
- Rendering: `scratch/prototype/render_catalog.py` renders catalog + rules into the table of 02 §4.3; this deliverable's rendering is `results/catalog_rendered.md`

## Reproduce with one command
```
sh scratch/deliverables/run.sh C1_catalog_check.py
```
Results go to `results/summary.md`, `results/catalog_rendered.md` and `results/examples.md`.

## Validation data
The catalog itself, plus the code-only run on all 908 dev events (which diagnostics actually fire, where notice wording comes from). Not the test set.

## Results
All 12 checks **pass**:
- 61 diagnostics: 15 return, 46 record-only (matches 02 §4.3)
- Every entry has object, trigger, evidence, step and handling; every record-only entry has reviewer text (return-type entries go back to the model only and never reach a reviewer, so they have none)
- Record-only entries map one-to-one to `rules.yaml`; return-type entries are not in `rules.yaml` (they produce no flag)
- Every carrier request has an acceptance criterion and vice versa
- Every diagnostic code in the prototype source is in the catalog; the 20 that fired on the dev split are all in the catalog
- Every sentence of every notice and draft generated on the dev split comes from the catalog

Five example entries in `results/examples.md`.

## Limitations
- 41 of the 61 did not fire in the code-only dev run: most need step-3 model output and have only run in the 17 synthetic cases and the walk-throughs of 02 §8.
- The wording is a Chinese draft; carrier-facing English wording and the reviewer interface are not decided.
- Whether the reviewer texts are useful depends on reviewers' ratings of flags (02 §9.2).
