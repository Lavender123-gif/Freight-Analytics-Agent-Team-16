"""B03 deliverable: the auto-reject pre-check (after step 2, before step 3; a hit means the model is not called).

Run from repo root: sh scratch/deliverables/run.sh B03_auto_reject_precheck.py
Dev split, all 908 events, plus three synthetic cases for the exemption rule. Compares against 02 §7.3. No LLM calls.
The pre-check reuses the step-5.5 history code in pre-check mode (earlier records only); those counts are listed too.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from decimal import Decimal

from _shared import md_table, results_dir, rowlevel_dir, run_code_only, safe_for_docs
from disposition import aggregate, decide, reject_draft
from gate import diag
from history import HistEntry, history_diagnostics
from number_parse import parse
from schemas import ObjectType

FOLDER = "B03-auto-reject-precheck"
rows, ev, records = run_code_only()
n_rows = {r.source.record_id: len(r.source.source_rows) for r in records}

disp = Counter(r.disposition.outcome for r in records)
disp_rows_n = Counter()
for r in records:
    disp_rows_n[r.disposition.outcome] += n_rows[r.source.record_id]
ar = [r for r in records if r.disposition.outcome == "AUTO_REJECT"]
ar_reasons = Counter(tuple(r.disposition.reasons) for r in ar)
not_called = sum(r.run.status == "not_run_auto_reject" for r in records)
exempted = [r for r in records if {"REC.TEXT.EMPTY", "REC.TEXT.NUMBERS_ONLY"} & {f.code for f in r.flags}
            and r.disposition.outcome != "AUTO_REJECT"]

# later explained version (informational; the rule itself only looks at earlier records)
by_ship = {}
for (_, e), r in zip(ev.iterrows(), records):
    by_ship.setdefault(e.SHIPMENT_GID, []).append((e.ts, r))
later_explained = 0
for (_, e), r in zip(ev.iterrows(), records):
    if r.disposition.outcome == "AUTO_REJECT":
        later_explained += any(ts > e.ts and abs(o.source.delta - r.source.delta) <= Decimal("0.005")
                               and any(ch.isalpha() for ch in o.text.redacted) for ts, o in by_ship[e.SHIPMENT_GID])

checks = [["AUTO_REJECT events", disp["AUTO_REJECT"], "10 (02 §7.3)", disp["AUTO_REJECT"] == 10],
          ["AUTO_REJECT rows", disp_rows_n["AUTO_REJECT"], "15", disp_rows_n["AUTO_REJECT"] == 15],
          ["  of which numbers only", ar_reasons[("auto_reject:REC.TEXT.NUMBERS_ONLY",)], "6", ar_reasons[("auto_reject:REC.TEXT.NUMBERS_ONLY",)] == 6],
          ["  of which empty text", ar_reasons[("auto_reject:REC.TEXT.EMPTY",)], "4", ar_reasons[("auto_reject:REC.TEXT.EMPTY",)] == 4],
          ["model not called (run.status = not_run_auto_reject)", not_called, "= AUTO_REJECT", not_called == disp["AUTO_REJECT"]],
          ["auto-reject candidates exempted by an earlier explained record", len(exempted), "0", len(exempted) == 0],
          ["auto-rejected with a LATER same-Delta explained version (informational)", later_explained, "5 of 10", later_explained == 5],
          ["auto-rejects with an automatic notice", sum(r.reject_draft is not None and r.reject_draft.automatic for r in ar),
           "= AUTO_REJECT", all(r.reject_draft is not None and r.reject_draft.automatic for r in ar)]]

# synthetic: the exemption rule and the "earlier only" visibility rule
T0 = datetime(2022, 1, 1, 10, 0)


def synth(earlier: list[HistEntry]) -> str:
    text, delta = "56.56", Decimal("56.56")
    d = [diag("REC.TEXT.NUMBERS_ONLY", ObjectType.RECORD, "text", {"text": text, "numbers": [text]}, "2")]
    d += history_diagnostics("cur", T0, delta, text, parse(text), earlier)
    return decide(aggregate(d)).outcome


syn = [["numbers-only text, no earlier record", synth([]), "AUTO_REJECT"],
       ["numbers-only text, earlier record with same Delta and a charge name",
        synth([HistEntry("e1", datetime(2021, 12, 31), Decimal("56.56"), "ZONE FACTOR CORRECTION 56.56")]), "HUMAN_REVIEW"],
       ["numbers-only text, same-Delta explained record but LATER",
        synth([HistEntry("e2", datetime(2022, 1, 2), Decimal("56.56"), "ZONE FACTOR CORRECTION 56.56")]), "AUTO_REJECT"]]
syn_rows = [[a, b, c, "PASS" if b == c else "FAIL"] for a, b, c in syn]

hist_pre = Counter(d.code for r in records for d in r.diagnostics if d.code.startswith("HIST."))
hist_ev = Counter(c for r in records for c in {d.code for d in r.diagnostics if d.code.startswith("HIST.")})

# examples: auto-rejected texts and the notice sent (text from the diagnostics catalog)
ex_rows = []
seen = set()
for r in ar:
    if not safe_for_docs(r.text.redacted) or (r.text.redacted, str(r.source.delta)) in seen:
        continue
    seen.add((r.text.redacted, str(r.source.delta)))
    ex_rows.append([f"`{r.text.redacted}`" if r.text.redacted else "(empty)", str(r.source.delta),
                    r.disposition.reasons[0].split(":")[1], "; ".join(r.reject_draft.required_changes),
                    "; ".join(r.reject_draft.acceptance_criteria)])
    if len(ex_rows) == 4:
        break

res = results_dir(FOLDER)
summary = ["# B03 auto-reject pre-check — results\n",
           "Generated by `sh scratch/deliverables/run.sh B03_auto_reject_precheck.py`. Dev split, all 908 events (953 rows). Not the test set.\n",
           md_table(["check", "value", "expected", "pass"], [[a, b, c, "PASS" if d else "FAIL"] for a, b, c, d in checks]),
           "\n## Synthetic cases (exemption and earlier-only visibility)\n",
           md_table(["case", "outcome", "expected", "check"], syn_rows),
           "\n## Disposition of all 908 events from code-only flags (context for B09; no step 3)\n",
           md_table(["outcome", "events", "rows"], [[k, disp[k], disp_rows_n[k]] for k in ["AUTO_REJECT", "HUMAN_REVIEW", "SPLIT_TRUSTED"]]),
           "\n## History diagnostics in pre-check mode (step 5.5 code, earlier records only)\n",
           md_table(["code", "diagnostics", "events"], [[f"`{c}`", hist_pre[c], hist_ev[c]] for c in sorted(hist_pre)])]
(res / "summary.md").write_text("\n".join(summary))
(res / "examples.md").write_text("\n".join([
    "# B03 auto-reject pre-check — examples (before → after)\n",
    "Before: the redacted text and Delta. After: no model call; the automatic notice built from the diagnostics catalog.\n",
    md_table(["text (before)", "Delta", "trigger", "notice: required change", "notice: acceptance"], ex_rows)]))

rl = rowlevel_dir("B03")
with open(rl / "dispositions.jsonl", "w") as f:
    for r in records:
        f.write(json.dumps({"record_id": r.source.record_id, "outcome": r.disposition.outcome, "reasons": r.disposition.reasons}) + "\n")
print("\n".join(summary))
print(f"examples: {len(ex_rows)}; row-level -> {rl}")
