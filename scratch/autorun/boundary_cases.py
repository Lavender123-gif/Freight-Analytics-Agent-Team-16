"""Run Codex's 88 boundary cases (synthetic, from ppg-codex-review; copy in data/external/) through the new framework.

No model is called. Each case's hypothetical submission is converted from the prototype format to submission v2 and
fed to the real Session (the 'model' resubmits the same reading until processing ends). Cases without a submission
run the deterministic steps only. Output: a JSON of results (git-ignored) that build_boundary_review.py turns into
the keep / modify / void table.

Run: uv run python scratch/autorun/boundary_cases.py
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from freight_lineitems.agent import DeltaJudge, Session
from freight_lineitems.config import ROOT
from freight_lineitems.duplicates import apply as apply_dups
from freight_lineitems.pipeline import assemble, prepare
from freight_lineitems.records import InputRecord

CASES = ROOT / "data" / "external" / "codex_boundary" / "rules_and_diagnostics.jsonl"
OUT = ROOT / "data" / "interim" / "autorun" / "boundary_results.json"
REC_ZH = {"PASSED_CHECKS": "解析通过检查", "HUMAN_REVIEW": "建议人工审核", "RETURN_SUGGESTED": "建议退回承运商"}


def to_record(d: dict, rid: str, row: int) -> InputRecord:
    dec = lambda x: Decimal(str(x)).quantize(Decimal("0.01")) if x not in (None, "") else None  # noqa: E731
    return InputRecord(record_id=rid, source="boundary", row_number=row, shipment_key=d.get("SHIPMENT_GID", "S"),
                       carrier=d.get("Carrier", "C"), carrier_invoice=d.get("Carrier Invoice"), pk=d.get("PK"),
                       event_date=datetime.strptime(d["Event Date"], "%Y-%m-%d %H:%M:%S") if d.get("Event Date") else None,
                       text_raw=d.get("Descritipion") or "", delta=dec(d.get("Delta")) or Decimal("0"),
                       invoice_amount=dec(d.get("Invoice Amount")), shipment_amount=dec(d.get("Shipment Amount")),
                       origin_state=d.get("Source State"), destination_state=d.get("Destination State"),
                       reason_code=d.get("Reason Code"), raw=d)


def convert(sub: dict, prep: dict) -> dict:
    """Prototype submission -> v2. Nothing is invented: exclusion_phrase reuses the model's own evidence phrase,
    quantity_ref/unit_rate_ref become a PRODUCT relation, a contains_number=false read keeps the region's digits."""
    table = {n.id: n for n in prep["parse"].numbers}
    regions = {u.id: u for u in prep["parse"].unrecognized}
    nums = []
    for j in sub.get("numbers", []):
        tok = table.get(j["id"])
        counted = j.get("status") in ("CLAIMED", "UNPAID")
        excl = j.get("evidence_phrase") if (tok and tok.has_dollar and not counted and j.get("kind") != "TOTAL") else None
        nums.append({"id": j["id"], "kind": j["kind"], "status": j["status"], "is_credit": False,
                     "charge_codes": j.get("charge_codes", []), "other_phrase": j.get("other_phrase"),
                     "evidence_phrase": j.get("evidence_phrase", ""), "exclusion_phrase": excl})
    items, rels = [], []
    for li in sub.get("line_items", []):
        items.append({"amount_ref": li.get("amount_ref"), "charge_codes": li.get("charge_codes", []), "raw_charge_label": None,
                      "carrier_stated_reason": li.get("carrier_stated_reason"),
                      "carrier_stated_basis_type": li.get("carrier_stated_basis_type", "NONE"),
                      "carrier_stated_basis": li.get("carrier_stated_basis")})
        if li.get("quantity_ref") and li.get("unit_rate_ref"):
            rels.append({"relation_type": "PRODUCT", "operand_ids": [li["quantity_ref"], li["unit_rate_ref"]],
                         "result_id": li.get("amount_ref")})
    reads = []
    for r in sub.get("unrecognized_reads", []):
        rid = r.get("region_id")
        digits = "".join(ch for ch in str(r.get("value") or (regions[rid].raw if rid in regions else "")) if ch.isdigit())
        an = r.get("as_number") or {"id": rid, "kind": "REFERENCE", "status": "NONE", "charge_codes": [], "other_phrase": None,
                                    "evidence_phrase": regions[rid].raw if rid in regions else ""}
        reads.append({"region_id": rid, "digits_read": digits,
                      "as_number": {"id": an["id"], "kind": an["kind"], "status": an["status"], "is_credit": False,
                                    "charge_codes": an.get("charge_codes", []), "other_phrase": an.get("other_phrase"),
                                    "evidence_phrase": an.get("evidence_phrase", ""), "exclusion_phrase": None}})
    return {"response_type": "FIRST", "reason": None, "numbers": nums, "line_items": items, "relations": rels,
            "unrecognized_reads": reads}


def play(prep: dict, subs: list[dict], trace: list[dict]) -> dict:
    sess = Session(ctx=prep["ctx"], judge=DeltaJudge(prep["rec"].delta), llm_input=prep["llm_input"])
    for t in trace:
        if t.get("tool") == "report_uncertainty":
            sess.report_uncertainty(t.get("target_path", ""), t.get("reason_type", "other"), t.get("note", ""))
    queue = [convert(s, prep) for s in subs]
    last = None
    for _ in range(8):
        if sess.final is not None or not queue and last is None:
            break
        s = queue.pop(0) if queue else dict(last, response_type="INSISTED", reason="hypothetical resubmission")
        if last is not None and s.get("response_type") == "FIRST":
            s = dict(s, response_type="REVISED", reason="hypothetical revision")
        sess.submit(s)
        last = s
    return {"session": sess, "transcript": {"calls": [], "events": [], "first_user_message": ""}}


def _harness(c: dict):
    """Apply what a case's harness note asks for: pad the text to an exact length, or fix the name detector's output."""
    import re as _re
    from freight_lineitems import textprep
    ir = dict(c["input_record"])
    note = c.get("test_harness_note", "")
    m = _re.search(r"(\d+)字符", note)
    if m:
        ir["Descritipion"] = (ir["Descritipion"] + " " + "A" * 1000)[: int(m.group(1))] if len(ir["Descritipion"]) < int(m.group(1)) \
            else ir["Descritipion"][: int(m.group(1))]
    patch = None
    if "assumed_redaction_detector_output" in c:
        thr = 0.5
        names = [x["span"] for x in c["assumed_redaction_detector_output"] if x["score"] >= thr]
        patch = lambda t: [(t.find(n), t.find(n) + len(n)) for n in names if n in t]  # noqa: E731
    if "assumed_redacted_text" in c:
        orig, red = ir["Descritipion"], c["assumed_redacted_text"]
        a = next(i for i in range(len(orig)) if orig[i] != red[i])
        tail = len(orig) - len(red.split("]", 1)[1]) if "]" in red else len(orig)
        patch = lambda t: [(a, tail)] if t == orig else []  # noqa: E731
    return ir, patch


def run_case(c: dict) -> dict:
    from freight_lineitems import textprep
    ir, patch = _harness(c)
    saved = textprep.person_spans
    if patch is not None:
        textprep.person_spans = patch
        textprep.RULES = dict(textprep.RULES, redaction=dict(textprep.RULES["redaction"], context_rules=False))
    try:
        return _run_case(c, ir)
    finally:
        textprep.person_spans = saved
        from freight_lineitems.config import RULES as _R
        textprep.RULES = _R


def _run_case(c: dict, ir: dict) -> dict:
    rec = to_record(ir, f"{c['case_id']}#r0", 10)
    extras = [to_record(d, f"{c['case_id']}#h{i}", i) for i, d in enumerate(c.get("history_records", []) + c.get("additional_input_rows", []))]
    prep = prepare(rec)
    subs = c.get("hypothetical_model_submissions") or ([c["hypothetical_model_submission"]] if c.get("hypothetical_model_submission") else [])
    trace = c.get("hypothetical_model_tool_trace") or []
    trace = trace if isinstance(trace, list) else []      # dict traces (turn counts) cannot be replayed
    if subs:
        res = assemble(prep, play(prep, subs, trace))
    else:
        res = assemble(prep, None) if not trace else assemble(prep, play(prep, [], trace))
    if extras:
        others = [assemble(prepare(e), None) for e in extras]
        res = [x for x in apply_dups([rec] + extras, [res] + others) if x["record_id"] == rec.record_id][0]
    raw_trace = c.get("hypothetical_model_tool_trace")
    never_submitted = isinstance(raw_trace, dict) and raw_trace.get("submit_calls") == 0
    if not subs and not never_submitted:   # no hypothetical reading: the 'model not run' flag is a harness artefact, not part of the case
        from freight_lineitems.disposition import flags_from, recommend
        from freight_lineitems.schemas import Diagnostic
        ds = [Diagnostic(**d) for d in res["judgment"]["diagnostics"] if d["code"] != "RUN.SUBMIT.NONE"]
        fl = flags_from(ds)
        res["judgment"] = {"flags": fl, **recommend(fl), "diagnostics": [d.model_dump() for d in ds]}
    final = res["process"].get("attempts", [])
    last_errs = sorted({e["code"] for a in final[-1:] for e in a["repair_errors"]}) if final else []
    ours = sorted({f["code"] for f in res["judgment"]["flags"]} | set(last_errs))
    return {"case_id": c["case_id"], "target_rule": c["target_rule"], "description": c["description"],
            "expected_diagnostics": c["expected_diagnostics"], "expected_not": c.get("expected_not_diagnostics", []),
            "expected_recommendation": c["expected_recommendation"], "our_codes": ours,
            "our_recommendation": REC_ZH[res["judgment"]["recommendation"]], "parse_status": res["facts"]["parse_status"],
            "delta_consistency": res["facts"]["delta_consistency"], "had_submission": bool(subs),
            "extra_keys": sorted(set(c) - {"case_id", "target_rule", "description", "input_record", "expected_diagnostics",
                                          "expected_recommendation"})}


if __name__ == "__main__":
    cases = [json.loads(x) for x in CASES.read_text().splitlines()]
    out = [run_case(c) for c in cases]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    same_rec = sum(o["our_recommendation"] == o["expected_recommendation"] for o in out)
    all_codes = sum(set(o["expected_diagnostics"]) <= set(o["our_codes"]) for o in out)
    print(f"cases {len(out)}; recommendation same {same_rec}; all expected codes present {all_codes}")
