"""End-to-end walkthrough of 10 dev records (report section 8).

STEP 3 IS ROLE-PLAYED: the tool calls and submissions below were written by hand by Claude in the design session,
following SKILL.md. They are not a model run and say nothing about how a model would actually behave. Everything
else (steps 0-2, 4-5, 5.5, 6, 7) is the prototype code. The role-play was written knowing what the checks do.

Run: sh scratch/prototype/run.sh walkthrough.py
Records are selected by text and Delta at run time. Output shows redacted text only.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate import collapse, load_rows  # noqa: E402
from history import HistEntry  # noqa: E402
from pipeline import claimed_codes, process  # noqa: E402


def N(i, kind, status, codes=(), ev="", other=None):
    return {"id": i, "kind": kind, "status": status, "charge_codes": list(codes), "other_phrase": other, "evidence_phrase": ev}


def L(ref, basis_type="NONE", basis=None, reason=None, codes=(), q=None, r=None):
    return {"amount_ref": ref, "charge_codes": list(codes), "quantity_ref": q, "unit_rate_ref": r,
            "carrier_stated_reason": reason, "carrier_stated_basis_type": basis_type, "carrier_stated_basis": basis}


def S(numbers, items, reads=()):
    return {"numbers": numbers, "line_items": items, "unrecognized_reads": list(reads)}


PT = "PENDING.PURCHASED_TRANSPORTATION"

# Each play is a list of (tool, kwargs) the role-played model issues, in order.
PLAYS = {
    "W5a": [("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", [PT], "PURCHASED TRANSPORTATION FEE"),
                          N("#2", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.LIFTGATE"], "TAILGATE")],
                         [L("#1"), L("#2")]))],
    "W9a": [("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", [PT], "PURCHASED TRANSPORTATION")], [L("#1")]))],

    "W1": [("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.LIFTGATE"], "TAILGATE REQUIRED")],
                        [L("#1", "PPG_LIST", "AS PER LIST FROM PPG", "TAILGATE REQUIRED TO THIS STORE LOCATION")]))],
    "W2": [("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.INSIDE_DELIVERY"], "INSIDE DELIVERY CHARGE"),
                         N("#2", "CHARGE_AMOUNT", "CLAIMED", [PT], "PURCHASE TRANSPORTATION SURCHARGE"),
                         N("#3", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.LIFTGATE"], "TAILGATE DELIVERY")],
                        [L("#1"), L("#2"), L("#3")]))],
    # W3 variant A: count every amount the text asks for, get a receipt, keep the reading and say why.
    "W3A": [("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.INSIDE_DELIVERY"], "INSIDE DELIVERY"),
                          N("#2", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.LIFTGATE"], "TAILGATE"),
                          N("#3", "CHARGE_AMOUNT", "CLAIMED", [PT], "PURCHASE FEE"),
                          N("#4", "UNSPECIFIED_AMOUNT", "CLAIMED", [], "BALANCE DUE")],
                         [L("#1"), L("#2"), L("#3"), L("#4")])),
            ("report_uncertainty", dict(target_path="numbers/#4", reason_type="delta_does_not_match_text",
                                        note="'BALANCE DUE $21.19' is written as an amount owed, but Delta equals #1+#2+#3 without it.")),
            ("resubmit_same", None)],
    # W3 variant C: silently leave the balance out so the sum fits Delta (the behaviour the design must catch).
    "W3C": [("reconcile", dict(counted_ids=["#1", "#2", "#3", "#4"], total_ids=[], tax_named_without_amount=False)),
            ("reconcile", dict(counted_ids=["#1", "#2", "#3"], total_ids=[], tax_named_without_amount=False)),
            ("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.INSIDE_DELIVERY"], "INSIDE DELIVERY"),
                          N("#2", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.LIFTGATE"], "TAILGATE"),
                          N("#3", "CHARGE_AMOUNT", "CLAIMED", [PT], "PURCHASE FEE"),
                          N("#4", "UNSPECIFIED_AMOUNT", "NONE", [], "BALANCE DUE")],
                         [L("#1"), L("#2"), L("#3")]))],
    "W4": [("submit", S([N("#1", "UNSPECIFIED_AMOUNT", "UNPAID", [], "SHORT PAID"),
                         N("#2", "CHARGE_AMOUNT", "DEDUCTED", ["ACCESSORIAL.HAZMAT"], "ADJUSTED OFF 150.00 HAZMAT"),
                         N("#3", "CHARGE_AMOUNT", "BILLED", ["LINEHAUL.BASE"], "BILLED LINEHAUL"),
                         N("#4", "CHARGE_AMOUNT", "BILLED", ["FUEL.SURCHARGE"], "FUEL SURCHARGE"),
                         N("#5", "CHARGE_AMOUNT", "PAID", ["OTHER"], "50.00 PAID REPOSITIONING CHARGE", other="REPOSITIONING CHARGE")],
                        [L("#1", reason="SHORT PAID")]))],
    "W5": [("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.LIFTGATE", PT], "TAILGATE AND PURCHASE FEE")], [L("#1")]))],
    "W7": [("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", ["RATE_CORRECTION.ZONE_FACTOR"], "ZIP 60506 TO FL IS FACTOR 124.2%"),
                         N("#2", "REFERENCE", "NONE", [], "ZIP 60506"),
                         N("#3", "RATE", "NONE", ["RATE_CORRECTION.ZONE_FACTOR"], "FACTOR 124.2%")],
                        [L("#1", reason="ZIP 60506 TO FL IS FACTOR 124.2%")]))],
    "W8": [("report_uncertainty", dict(target_path="numbers/#1", reason_type="kind_or_status_ambiguous",
                                       note="'.73 FSC' with Delta 0 looks like a fuel surcharge rate, not an amount; nothing is claimed.")),
           ("submit", S([N("#1", "RATE", "NONE", ["FUEL.SURCHARGE"], ".73 FSC")], []))],
    "W9": [("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", [PT], "PURCHASE FEE"),
                         N("#2", "UNSPECIFIED_AMOUNT", "CLAIMED", [], "BALANCE DUE")],
                        [L("#1"), L("#2")]))],
    "W10": [("lookup_tax_rule", dict(province="ON", date="2022-03-21")),
            ("reconcile", dict(counted_ids=["#1", "#2"], total_ids=["#3"], tax_named_without_amount=True)),
            ("submit", S([N("#1", "CHARGE_AMOUNT", "CLAIMED", ["DETENTION_STORAGE.DRIVER_DETENTION"], "DETENTION TIME"),
                          N("#2", "CHARGE_AMOUNT", "CLAIMED", ["OTHER"], "CV19 FEE", other="CV19 FEE"),
                          N("#3", "TOTAL", "CLAIMED", [], "= $63.55")],
                         [L("#1", reason="MISSING"), L("#2"), L(None, codes=["TAX.HST"])],
                         [{"region_id": "?1", "contains_number": True, "value": "19",
                           "as_number": N("?1", "REFERENCE", "NONE", [], "CV19 FEE")}]))],
}

CASES = [  # (case, what it covers, text, delta, how to pick among identical texts, earlier case to play first)
    ("W1", "普通附加费（无 $，依据为 PPG 清单）", "TAILGATE REQUIRED TO THIS STORE LOCATION AS PER LIST FROM PPG 15.75", "15.75", "earlier_different", None),
    ("W2", "多项费用", "INSIDE DELIVERY CHARGE - $13.00 PURCHASE TRANSPORTATION SURCHARGE - $20.00 TAILGATE DELIVERY - $15.00", "48.00", "first", None),
    ("W3A", "BALANCE DUE，Delta 不含余额：如实读，坚持原读法", "INSIDE DELIVERY $13 TAILGATE $15 PURCHASE FEE $20.12 BALANCE DUE $21.19", "48.12", "first", None),
    ("W3C", "同一记录：模型静默排除余额去凑 Delta", "INSIDE DELIVERY $13 TAILGATE $15 PURCHASE FEE $20.12 BALANCE DUE $21.19", "48.12", "first", None),
    ("W4", "付款历史", "SHORT PAID 75.27 ADJUSTED OFF 150.00 HAZMAT BILLED LINEHAUL 1 684.68 FUEL SURCHARGE 513.83 AND 50.00 PAID REPOSITIONING CHARGE PLEASE PROCESS BALANCE DUE ON INVOICE. THANK YOU.", "75.27", "first", None),
    ("W5", "合并金额（后续记录）", "TAILGATE AND PURCHASE FEE BALANCE DUE $35", "35.00", "first", "W5a"),
    ("W6", "只有数字（自动打回）", "56.56", "56.56", "first", None),
    ("W7", "费率主张（W6 的后续记录）", "$56.56 - ZIP 60506 TO FL IS FACTOR 124.2%", "56.56", "first", None),
    ("W8", "Delta 为零", ".73 FSC", "0.00", "first", None),
    ("W9", "多次争议的后续记录：重列旧金额 + 约 1.05 倍余额", "PURCHASE FEE $20 BALANCE DUE $21", "41.00", "earlier_20", "W9a"),
    ("W10", "税只写税种、未识别区域、合计被计两次", "MISSING $41.25 DETENTION TIME AND $15.00 CV19 FEE + HST = $63.55", "119.80", "first", None),
]

ev = collapse(load_rows()).sort_values(["SHIPMENT_GID", "ts", "Invoice Amount"]).reset_index(drop=True)


def pick(text, delta, how):
    m = ev[(ev.text_norm == text) & (ev.Delta == Decimal(delta))]
    for _, r in m.iterrows():
        e = ev[(ev.SHIPMENT_GID == r.SHIPMENT_GID) & (ev.ts < r.ts)]
        if how == "first" or (how == "earlier_different" and len(e) and (e.text_norm != text).all()) or \
                (how == "earlier_20" and len(e) and (e.Delta == Decimal("20.00")).any()):
            return r
    raise LookupError(text)


def player(actions):
    def play(sess, llm_input):
        last = None
        for tool, kw in actions:
            if tool == "submit":
                last = kw
                res = sess.submit(kw)
            elif tool == "resubmit_same":
                res = sess.submit(last)
            elif tool == "reconcile":
                res = sess.reconcile(**kw)
            elif tool == "report_uncertainty":
                res = sess.report_uncertainty(**kw)
            elif tool == "lookup_tax_rule":
                from tools import lookup_tax_rule
                res = lookup_tax_rule(**kw)
                sess.tool_log.append({"tool": "lookup_tax_rule", "input": kw, "result": res})
            print(f"      -> {tool}: {json.dumps(res, ensure_ascii=False, default=str)[:900]}")
            if isinstance(res, dict) and res.get("final"):
                break
    return play


def history_for(r, played: dict) -> list[HistEntry]:
    e = ev[(ev.SHIPMENT_GID == r.SHIPMENT_GID) & (ev.record_id != r.record_id)]
    return [HistEntry(x.record_id, x.ts, x.Delta, played[x.record_id].text.redacted if x.record_id in played else x.text_norm,
                      claimed_codes(played[x.record_id].content) if x.record_id in played else None)
            for x in e.itertuples()]


played: dict = {}
for case, covers, text, delta, how, pre in CASES:
    r = pick(text, delta, how)
    if pre:
        e = ev[(ev.SHIPMENT_GID == r.SHIPMENT_GID) & (ev.ts < r.ts)].iloc[-1]
        print(f"\n### {pre} (earlier record of {case}, played so that its codes are available to step 5.5)")
        print(f"   text: {e.text_norm} | Delta {e.Delta}")
        rec_pre, _ = process(e, history_for(e, played), player(PLAYS[pre]))
        played[e.record_id] = rec_pre
        print(f"   disposition: {rec_pre.disposition.outcome} {rec_pre.disposition.reasons}")
    print(f"\n### {case}: {covers}")
    rec0, _ = process(r, history_for(r, played), None)
    print(f"   [step 0-1] redacted text: {rec0.text.redacted} | Delta {rec0.source.delta} | dest {rec0.source.destination_state}"
          f" | earlier records of this shipment: {int(((ev.SHIPMENT_GID == r.SHIPMENT_GID) & (ev.ts < r.ts)).sum())}")
    print(f"   [step 2] marked: {rec0.parse.marked_text}")
    print(f"   [step 2] numbers: {[(n.id, n.raw, str(n.value), n.unit_hint) for n in rec0.parse.numbers]}; unrecognized: {[u.raw for u in rec0.parse.unrecognized]}")
    if rec0.disposition.outcome == "AUTO_REJECT":
        rec = rec0
        print("   [step 3] not run: auto-reject decided before the model (code-only)")
    else:
        print("   [step 3, ROLE-PLAYED] tool calls and results:")
        rec, _ = process(r, history_for(r, played), player(PLAYS[case]))
    if case != "W3C":
        played[r.record_id] = rec
    print(f"   run: status={rec.run.status}, submissions={rec.run.submissions}, reconcile_calls={rec.run.reconcile_calls}")
    if rec.claim:
        c = rec.claim
        print(f"   claim: counted {c.counted_ids} sum {c.claimed_sum} | Delta {c.delta} | reconciles {c.reconciles} | implied tax {c.implied_tax} | history {c.history_relations}")
    if rec.content:
        print("   line items: " + "; ".join(
            f"{li.amount_ref or '-'} codes={next((j.charge_codes for j in rec.content.numbers if j.id == li.amount_ref), li.charge_codes)} "
            f"reason={li.carrier_stated_reason!r} basis={li.carrier_stated_basis_type.value}:{li.carrier_stated_basis!r}"
            for li in rec.content.line_items))
    print("   flags: " + "; ".join(f"{f.code} [{f.severity.value}/{f.escalation_role}{'+' + str(f.points) if f.points else ''}]" for f in rec.flags))
    print(f"   disposition: {rec.disposition.outcome} {rec.disposition.reasons} score={rec.disposition.score}")
    if rec.reject_draft:
        d = rec.reject_draft
        print(f"   reject draft ({'automatic' if d.automatic else 'for reviewer'}): changes={d.required_changes} | acceptance={d.acceptance_criteria}")
