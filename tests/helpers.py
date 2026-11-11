"""Shared builders for tests. Texts are synthetic variants of dev-split wording (no real rows in tracked files)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from freight_lineitems.checks import Ctx
from freight_lineitems.numbers import parse
from freight_lineitems.records import InputRecord
from freight_lineitems.schemas import Submission


def ctx(text: str, dest: str | None = "AB", origin: str | None = "AB") -> Ctx:
    return Ctx(record_id="t", text=text, parse=parse(text), origin_state=origin, destination_state=dest,
               event_date=datetime(2022, 3, 1))


def N(i, kind="CHARGE_AMOUNT", status="CLAIMED", codes=(), ev="", excl=None, other=None, credit=False):
    return {"id": i, "kind": kind, "status": status, "is_credit": credit, "charge_codes": list(codes),
            "other_phrase": other, "evidence_phrase": ev, "exclusion_phrase": excl}


def L(ref, codes=(), label=None, reason=None, btype="NONE", basis=None):
    return {"amount_ref": ref, "charge_codes": list(codes), "raw_charge_label": label, "carrier_stated_reason": reason,
            "carrier_stated_basis_type": btype, "carrier_stated_basis": basis}


def S(numbers, items, relations=(), reads=(), rtype="FIRST", reason=None) -> dict:
    return {"response_type": rtype, "reason": reason, "numbers": list(numbers), "line_items": list(items),
            "relations": list(relations), "unrecognized_reads": list(reads)}


def sub(d: dict) -> Submission:
    return Submission.model_validate(d)


def record(text: str, delta: str, rid: str = "dev#r1", shipment: str = "S1", invoice: str = "I1", pk: str | None = "P1",
           dest: str = "AB") -> InputRecord:
    return InputRecord(record_id=rid, source="dev", row_number=1, shipment_key=shipment, carrier="C1", carrier_invoice=invoice,
                       pk=pk, event_date=datetime(2022, 3, 1, 10, 0), text_raw=text, delta=Decimal(delta),
                       invoice_amount=Decimal("100") + Decimal(delta), shipment_amount=Decimal("100"), origin_state="AB",
                       destination_state=dest, reason_code="R")
