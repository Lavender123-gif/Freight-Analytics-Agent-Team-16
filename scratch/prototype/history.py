"""Step 5.5: compare a record with earlier records of the same shipment.

Visibility: only records whose Event Date is strictly earlier. Records with the same Event Date (minute
precision) cannot see each other; they only get HIST.ORDER.SAME_MINUTE_SIBLING.

Two modes, same code:
- post-LLM (normal): `claimed` = values of the numbers the accepted submission counts (CLAIMED/UNPAID).
- pre-LLM (used before step 3 for the auto-reject exemption, and for the dev-wide run in this prototype):
  `claimed` is None and the money candidates are approximated by '$' numbers (all unit-less numbers if the text
  has no '$'). Diagnostics then carry evidence.mode = 'pre_llm_approx'.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from config import RULES, TAXONOMY
from gate import diag
from schemas import Diagnostic, ObjectType, ParseResult

TOL = Decimal(str(RULES["tolerances"]["amount_abs"]))
LO, HI = (Decimal(str(x)) for x in RULES["tolerances"]["near_105"])
AR = RULES["auto_reject"]["earlier_explained"]


@dataclass
class HistEntry:
    record_id: str
    ts: datetime
    delta: Decimal
    text: str
    codes: set[str] | None = field(default=None)   # charge codes of its accepted submission, if it has one


def _cats(codes: set[str]) -> set[str]:
    return {TAXONOMY["codes"][c]["category"] for c in codes if c in TAXONOMY["codes"]} - {"TAX", "OTHER"}


def _untaxed(codes: set[str]) -> set[str]:
    return {c for c in codes if not c.startswith("TAX.")}


def auto_rejectable_text(text: str) -> bool:
    return text == "" or not re.search(r"[A-Za-z]", re.sub(r"\[(?:PERSON|EMAIL)_\d+\]", "", text))


def explained(text: str) -> bool:
    return re.search(r"[A-Za-z]{%d,}" % AR["min_letters"], text) is not None and not (
        AR["earlier_must_not_be_auto_rejectable"] and auto_rejectable_text(text))


def approx_money(parse: ParseResult) -> list[tuple[str, Decimal]]:
    d = [(n.id, n.value) for n in parse.numbers if n.has_dollar]
    return d or [(n.id, n.value) for n in parse.numbers if n.unit_hint is None]


def history_diagnostics(rid: str, ts: datetime, delta: Decimal, text: str, parse: ParseResult,
                        others: list[HistEntry], claimed: list[tuple[str, Decimal]] | None = None,
                        codes: set[str] | None = None) -> list[Diagnostic]:
    mode = "post_llm" if claimed is not None else "pre_llm_approx"
    money = claimed if claimed is not None else approx_money(parse)
    out: list[Diagnostic] = []
    for o in others:
        if o.record_id == rid:
            continue
        if o.ts == ts:
            out.append(diag("HIST.ORDER.SAME_MINUTE_SIBLING", ObjectType.HISTORY, f"history/{o.record_id}",
                            {"sibling_record_id": o.record_id}, "5.5"))
            continue
        if o.ts > ts:
            continue                               # later records are invisible
        same_delta = abs(o.delta - delta) <= TOL
        path = f"history/{o.record_id}"
        if same_delta and o.text == text:
            out.append(diag("HIST.REPEAT.IDENTICAL_TEXT", ObjectType.HISTORY, path,
                            {"earlier_record_id": o.record_id, "minutes_between": round((ts - o.ts).total_seconds() / 60)}, "5.5"))
        elif same_delta:
            out.append(diag("HIST.REPEAT.SAME_DELTA", ObjectType.HISTORY, path, {"earlier_record_id": o.record_id}, "5.5"))
            if codes and o.codes and not (_cats(codes) & _cats(o.codes)):
                out.append(diag("HIST.REPEAT.SAME_AMOUNT_NEW_CODES", ObjectType.HISTORY, path,
                                {"earlier_record_id": o.record_id, "earlier_codes": sorted(o.codes), "codes": sorted(codes)}, "5.5"))
        if not same_delta and codes and o.codes and (_untaxed(codes) & _untaxed(o.codes)):
            out.append(diag("HIST.REPEAT.REVISED_SAME_CHARGES", ObjectType.HISTORY, path,
                            {"earlier_record_id": o.record_id, "earlier_delta": str(o.delta),
                             "shared_codes": sorted(_untaxed(codes) & _untaxed(o.codes))}, "5.5"))
        if same_delta and explained(o.text):
            out.append(diag("HIST.CONTEXT.EARLIER_EXPLAINED", ObjectType.HISTORY, path, {"earlier_record_id": o.record_id}, "5.5"))
        if o.delta <= 0:
            continue
        for nid, v in money:
            if not same_delta and abs(v - o.delta) <= TOL:
                out.append(diag("HIST.AMOUNT.EQUALS_EARLIER_DELTA", ObjectType.HISTORY, f"numbers/{nid}",
                                {"id": nid, "amount": str(v), "earlier_record_id": o.record_id,
                                 "earlier_delta": str(o.delta), "mode": mode}, "5.5"))
            ratio = v / o.delta
            if LO <= ratio <= HI:
                out.append(diag("HIST.AMOUNT.NEAR_105_EARLIER", ObjectType.HISTORY, f"numbers/{nid}",
                                {"id": nid, "amount": str(v), "earlier_record_id": o.record_id,
                                 "earlier_delta": str(o.delta), "ratio": str(ratio.quantize(Decimal("0.0001"))), "mode": mode}, "5.5"))
    return out
