"""Builds tests/fixtures/smoke/batch.csv and readings.json (tracked, synthetic) for the clean-checkout smoke test
(task 20 section 2.8) and the offline run (`python -m freight_lineitems.offline`).

The texts and readings are the skill's five synthetic examples (skill/freight-dispute-line-items/examples/
synthetic_examples.json, written for the repository, no real rows) plus one synthetic BALANCE DUE text written here.
Shipments are arranged so the batch exercises the shipment roll-up: one shipment with two explanations on two days,
one explanation with two order copies (two PKs), and single-explanation shipments. Every reading is validated by the
real checks before the files are written. No model call.

Run:  uv run python scratch/smoke/build_smoke_fixture.py          (writes the files)
      uv run python scratch/smoke/build_smoke_fixture.py --check  (validates, compares with the files, no write)
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from freight_lineitems.checks import check_submission
from freight_lineitems.config import ROOT, SYNTHETIC_EXAMPLES_PATH
from freight_lineitems.pipeline import prepare
from freight_lineitems.records import InputRecord
from freight_lineitems.schemas import Submission

OUT = ROOT / "tests" / "fixtures" / "smoke"
COLUMNS = ["SHIPMENT_GID", "SAP BOL", "PK", "Carrier Invoice", "Descritipion", "Shipment Amount", "Carrier",
           "Source State", "Destination State", "Event Date", "Reason Code"]

BD_TEXT = "TL FUEL SURCHARGE SHOULD APPLY. BALANCE DUE IS $36.40 + GST $1.82 = $38.22"
BD_READING = {
    "response_type": "FIRST", "reason": None,
    "numbers": [
        {"id": "#1", "kind": "CHARGE_AMOUNT", "status": "CLAIMED", "is_credit": False, "charge_codes": ["RATE_CORRECTION.FUEL_TIER"],
         "other_phrase": None, "evidence_phrase": "BALANCE DUE IS $36.40", "exclusion_phrase": None},
        {"id": "#2", "kind": "TAX_AMOUNT", "status": "CLAIMED", "is_credit": False, "charge_codes": ["TAX.GST"],
         "other_phrase": None, "evidence_phrase": "GST $1.82", "exclusion_phrase": None},
        {"id": "#3", "kind": "TOTAL", "status": "NONE", "is_credit": False, "charge_codes": [],
         "other_phrase": None, "evidence_phrase": "= $38.22", "exclusion_phrase": None}],
    "line_items": [
        {"amount_ref": "#1", "charge_codes": [], "raw_charge_label": "TL FUEL SURCHARGE", "carrier_stated_reason": None,
         "carrier_stated_basis_type": "NONE", "carrier_stated_basis": None},
        {"amount_ref": "#2", "charge_codes": [], "raw_charge_label": "GST", "carrier_stated_reason": None,
         "carrier_stated_basis_type": "NONE", "carrier_stated_basis": None}],
    "relations": [{"relation_type": "SUM", "operand_ids": ["#1", "#2"], "result_id": "#3"}],
    "unrecognized_reads": [], "earlier_claim_quote": None,
    "stated_amount_due_id": "#3", "stated_amount_due_evidence": "BALANCE DUE IS $36.40 + GST $1.82 = $38.22"}

# (shipment, SAP BOL, PK, invoice, example id or 'BD', shipment amount, origin, destination, event date)
ROWS = [
    ("SYN-SHIP-A", "900000000000000001", "PK-A1", "INV-A", "SYN-1", "410.00", "ON", "ON", "2022-03-01 10:00:00"),
    ("SYN-SHIP-A", "900000000000000001", "PK-A1", "INV-A", "SYN-2", "410.00", "ON", "ON", "2022-03-04 09:00:00"),
    ("SYN-SHIP-B", "900000000000000002", "PK-B1", "INV-B", "SYN-3", "1200.00", "ON", "QC", "2022-03-02 11:00:00"),
    ("SYN-SHIP-B", "900000000000000002", "PK-B2", "INV-B", "SYN-3", "1200.00", "ON", "QC", "2022-03-02 11:00:00"),
    ("SYN-SHIP-C", "900000000000000003", "PK-C1", "INV-C", "SYN-4", "650.00", "AB", "AB", "2022-03-03 08:30:00"),
    ("SYN-SHIP-D", "900000000000000004", "PK-D1", "INV-D", "SYN-5", "300.00", "AB", "AB", "2022-03-05 14:00:00"),
    ("SYN-SHIP-E", "900000000000000005", "PK-E1", "INV-E", "BD", "520.00", "AB", "AB", "2022-03-06 16:00:00"),
]


def unmark(marked: str) -> str:
    return re.sub(r"\[[#?]\d+ ([^\]]*)\]", r"\1", marked)


def build() -> tuple[str, str]:
    ex = {e["example_id"]: e for e in json.loads(SYNTHETIC_EXAMPLES_PATH.read_text())}
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS)
    readings, seen = {}, set()
    for i, (ship, bol, pk, inv, eid, amt, o, d, day) in enumerate(ROWS):
        text, reading = (BD_TEXT, BD_READING) if eid == "BD" else (unmark(ex[eid]["marked_text"]), ex[eid]["reading"])
        w.writerow([ship, bol, pk, inv, text, amt, "SYNTHETIC CARRIER", o, d, day, "SYN"])
        rec = InputRecord(record_id=f"x#r{i}", source="csv", row_number=i, shipment_key=ship, carrier="C", carrier_invoice=inv,
                          pk=pk, event_date=datetime.fromisoformat(day), text_raw=text, delta=None, invoice_amount=None,
                          shipment_amount=Decimal(amt), origin_state=o, destination_state=d, reason_code="SYN")
        prep = prepare(rec)
        assert prep["redacted"] == text.upper() or prep["redacted"] == text, f"redaction changed synthetic text {eid}"
        errs, _rec, _claim = check_submission(prep["ctx"], Submission.model_validate(reading))
        assert not errs, (eid, [e.code for e in errs])
        key = (ship, day, text)
        if key not in seen:          # order copies share the first row's reading
            readings[str(i)] = reading
            seen.add(key)
    return buf.getvalue(), json.dumps(readings, indent=1) + "\n"


def main() -> None:
    csv_text, readings = build()
    if "--check" in sys.argv:
        ok = (OUT / "batch.csv").read_text() == csv_text and (OUT / "readings.json").read_text() == readings
        print("smoke fixture valid; committed files match" if ok else "smoke fixture valid; committed files DIFFER")
        sys.exit(0 if ok else 1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "batch.csv").write_text(csv_text)
    (OUT / "readings.json").write_text(readings)
    print(f"wrote {OUT}/batch.csv ({len(ROWS)} rows) and readings.json")


if __name__ == "__main__":
    main()
