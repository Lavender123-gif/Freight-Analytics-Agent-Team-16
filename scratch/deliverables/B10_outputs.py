"""B10 deliverable: step 7 outputs (record-object JSON, append-only event log, Excel export with two sheets).

Run from repo root: sh scratch/deliverables/run.sh B10_outputs.py
Dev split, all 908 events, code-only (no step 3, so `content`, `claim` and `llm_input` are empty by design).
Writes the three outputs to the git-ignored data/interim/deliverables/B10/ with the same logic as
scratch/prototype/run_dev.py section 5, then checks their shape. Tracked results: structure and counts only.
"""

from __future__ import annotations

import json
from collections import Counter

import pandas as pd

from _shared import md_table, results_dir, rowlevel_dir, run_code_only
from schemas import Event, LLMInput, Record

FOLDER = "B10-outputs"
rows, ev, records = run_code_only()
out = rowlevel_dir("B10")

# ---- write (same as run_dev.py section 5) ----
with open(out / "records.jsonl", "w") as f:
    for r in records:
        f.write(r.model_dump_json() + "\n")
events = []
for r in records:
    for typ, payload in [("ingested", {"source_rows": r.source.source_rows})] + \
            [("flag", fl.model_dump(mode="json")) for fl in r.flags] + [("disposition", r.disposition.model_dump(mode="json"))]:
        events.append(Event(event_id=f"e{len(events) + 1}", record_id=r.source.record_id,
                            ts=r.diagnostics[0].created_at if r.diagnostics else r.source.event_date,
                            actor="system", type=typ, payload=payload))
with open(out / "events.jsonl", "w") as f:
    for e in events:
        f.write(e.model_dump_json() + "\n")
src = rows.set_index("row")
sheet1 = pd.DataFrame([{
    "record_id": r.source.record_id, "outcome": r.disposition.outcome, "reasons": "; ".join(r.disposition.reasons),
    "flags": "; ".join(f.code for f in r.flags), "text_redacted": r.text.redacted, "delta": float(r.source.delta),
    "n_rows": len(r.source.source_rows),
    "Dispute Status": src.loc[r.source.source_rows[0], "Dispute Status"]} for r in records])
sheet2 = pd.DataFrame([{"record_id": r.source.record_id, "code": f.code, "severity": f.severity.value, "role": f.escalation_role,
                        "locations": ", ".join(f.locations)} for r in records for f in r.flags])
with pd.ExcelWriter(out / "export.xlsx") as w:
    sheet1.to_excel(w, sheet_name="records", index=False)
    sheet2.to_excel(w, sheet_name="flags", index=False)

# ---- read back and check ----
back = [Record.model_validate_json(line) for line in (out / "records.jsonl").read_text().splitlines()]
ev_back = [Event.model_validate_json(line) for line in (out / "events.jsonl").read_text().splitlines()]
xl = pd.read_excel(out / "export.xlsx", sheet_name=None)
raw_json = (out / "records.jsonl").read_text()
fill = {k: sum(getattr(r, k) not in (None, [], {}) for r in back) for k in Record.model_fields}

checks = [
    ["records.jsonl lines re-validate as Record", len(back), "908", len(back) == 908],
    ["record_id unique", len({r.source.record_id for r in back}), "908", len({r.source.record_id for r in back}) == 908],
    ["events.jsonl lines re-validate as Event", len(ev_back), f"= {len(events)}", len(ev_back) == len(events)],
    ["one 'disposition' event per record", sum(e.type == "disposition" for e in ev_back), "908",
     sum(e.type == "disposition" for e in ev_back) == 908],
    ["'flag' events = flags on records", sum(e.type == "flag" for e in ev_back), sum(len(r.flags) for r in back),
     sum(e.type == "flag" for e in ev_back) == sum(len(r.flags) for r in back)],
    ["Excel sheets", ", ".join(xl), "records, flags", list(xl) == ["records", "flags"]],
    ["Excel 'records' rows", len(xl["records"]), "908", len(xl["records"]) == 908],
    ["Excel 'flags' rows = flags on records", len(xl["flags"]), sum(len(r.flags) for r in back), len(xl["flags"]) == sum(len(r.flags) for r in back)],
    ["'Dispute Status' absent from record JSON (02 D7)", "Dispute Status" not in raw_json and "PMT_" not in raw_json, "True",
     "Dispute Status" not in raw_json and "PMT_" not in raw_json],
    ["'Dispute Status' absent from LLMInput schema", "dispute_status" not in LLMInput.model_fields, "True",
     "dispute_status" not in LLMInput.model_fields],
    ["'Dispute Status' present only in the Excel export", "Dispute Status" in xl["records"].columns, "True", "Dispute Status" in xl["records"].columns],
]
fill_rows = [[f"`{k}`", v, "empty by design until B04 (step 3) runs" if k in ("llm_input", "content", "claim") else ""]
             for k, v in fill.items()]
ev_types = Counter(e.type for e in ev_back)
declared = Event.model_fields["type"].annotation.__args__
type_rows = [[f"`{t}`", ev_types.get(t, 0), "" if ev_types.get(t) else "declared, not written by the code-only run"] for t in declared]
col_rows = [[name, len(df), ", ".join(df.columns)] for name, df in xl.items()]

# one structural example: field tree of an auto-rejected record with identifying values withheld
r0 = next(r for r in back if r.disposition.outcome == "AUTO_REJECT" and r.text.redacted)
d0 = json.loads(r0.model_dump_json())
for k in ("record_id", "shipment_id", "invoice_pks", "source_rows", "carrier", "reason_code", "origin_state",
          "destination_state", "event_date", "invoice_amount", "shipment_amount"):
    d0["source"][k] = "<withheld>"
d0["text"]["original_sha1"] = "<withheld>"
for dg in d0["diagnostics"]:
    dg["created_at"] = "<ts>"
    dg["evidence"] = {k: ("<withheld>" if "record" in k or "rows" in k else v) for k, v in dg["evidence"].items()}
for fl in d0["flags"]:
    fl["locations"] = ["<path>"]
    fl["evidence"] = ["<see diagnostics>"]

res = results_dir(FOLDER)
summary = ["# B10 outputs — results\n",
           "Generated by `sh scratch/deliverables/run.sh B10_outputs.py`. Dev split, all 908 events. Not the test set. "
           "Code-only run: step 3 (LLM) not executed.\n",
           md_table(["check", "value", "expected", "pass"], [[a, b, c, "PASS" if d else "FAIL"] for a, b, c, d in checks]),
           "\n## Record object: how many of the 908 records have each part filled\n",
           md_table(["part", "records filled", "note"], fill_rows),
           "\n## Event log: event types\n", md_table(["type", "events", "note"], type_rows),
           "\n## Excel export\n", md_table(["sheet", "rows", "columns"], col_rows)]
(res / "summary.md").write_text("\n".join(summary))
(res / "example_record.json").write_text(json.dumps(d0, ensure_ascii=False, indent=2) + "\n")
print("\n".join(summary))
print("example text:", r0.text.redacted)
