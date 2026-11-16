"""Builders for roll-up tests: synthetic explanations with a hand-written reading (no model, no real rows)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from freight_lineitems.pipeline import assemble, prepare
from freight_lineitems.rollup import explanation_from_result, rollup

from helpers import L, N, S, record

DAY1, DAY2, DAY3 = datetime(2022, 3, 1, 10), datetime(2022, 3, 2, 10), datetime(2022, 3, 3, 10)


def expl(text: str, items: list[tuple], row: int, day: datetime = DAY1, rid: str | None = None, usable: bool = True,
         pks=("P1",), recommendation: str = "PASSED_CHECKS", due: str | None = None) -> dict:
    """One explanation as a pipeline result. `items`: (number id, codes, kind, status, label[, credit]) per number;
    numbers of the text not listed are read as REFERENCE / NONE. `due`: the number id the reading gives as the
    stated amount due (facts.stated_amount_due, as pipeline.stated_amount_due stores it)."""
    rec = record(text, "0", rid=rid or f"syn#r{row}", pk=pks[0] if pks else None)
    rec.row_number, rec.event_date = row, day
    out = assemble(prepare(rec), None)
    out["facts"]["parse_status"] = "PASSED_CHECKS" if usable else "FAILED_CHECKS"
    nums, lis, seen = [], [], set()
    for it in items:
        nid, codes, kind, status, label = it[:5]
        credit = it[5] if len(it) > 5 else False
        nums.append(N(nid, kind=kind, status=status, codes=codes, ev=label or "x", credit=credit,
                      other=label if "OTHER" in codes else None))
        if status in ("CLAIMED", "UNPAID"):
            lis.append(L(nid, label=label))
        seen.add(nid)
    for n in out["facts"]["number_table"]["numbers"]:
        if n["id"] not in seen:
            nums.append(N(n["id"], kind="REFERENCE", status="NONE", ev="x"))
    out["facts"]["reading"] = S(nums, lis) if usable else None
    if due is not None:
        val = next(n["value"] for n in out["facts"]["number_table"]["numbers"] if n["id"] == due)
        out["facts"]["stated_amount_due"] = {"number_id": due, "value": str(val), "evidence_phrase": "BALANCE DUE"}
    out["facts"]["source_rows"] = [{"record_id": out["record_id"], "row_number": row, "pk": p} for p in (pks or [None])]
    out["facts"]["n_rows"], out["facts"]["n_orders"] = len(pks or [None]), len([p for p in pks or [] if p])
    out["judgment"] = {"flags": [], "recommendation": recommendation, "diagnostics": []}
    return out


def C(nid, codes, label="", kind="CHARGE_AMOUNT", credit=False):
    """A counted (CLAIMED) amount."""
    return (nid, list(codes), kind, "CLAIMED", label, credit)


def T(nid, code="TAX.GST", label="GST"):
    return (nid, [code], "TAX_AMOUNT", "CLAIMED", label)


def X(nid, kind="TOTAL", status="NONE", codes=()):
    """A number the model did not count (a total, or a history amount)."""
    return (nid, list(codes), kind, status, "")


def roll(*results, original="100.00") -> dict:
    return rollup("S1", Decimal(original), [explanation_from_result(r) for r in results])


def codes(sh: dict) -> set[str]:
    return {f["code"] for f in sh["flags"]}


def status(sh: dict) -> dict[str, str]:
    return {f"{ln['explanation']}{ln['number_id']}": ln["status"] for ln in sh["lines"]}
