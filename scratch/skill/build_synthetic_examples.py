"""Builds skill/freight-dispute-line-items/examples/synthetic_examples.json (tracked; pending P-06, decided).

The texts below are newly written for the repository. They are not taken or adapted from the dev split, name no
carrier and no person, and use only generic freight wording. The file has exactly the shape of the git-ignored
runtime library (data/interim/skill/examples.json), so `tools.load_examples()` can fall back to it.

Each example is produced by the real code, not typed by hand:
- the text goes through `pipeline.prepare` (normalise, redact, number table), so `marked_text` and the number ids
  are exactly what the model would be shown; redaction must leave a synthetic text unchanged;
- the hand-written reading is validated with the `Submission` schema and `checks.check_submission`
  (zero repair errors), and the amounts code counts are compared with the sum written here.

Run:  uv run python scratch/skill/build_synthetic_examples.py          (writes the file)
      uv run python scratch/skill/build_synthetic_examples.py --check  (validates, compares with the file, no write)
No model call is made.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from decimal import Decimal

from freight_lineitems.checks import check_submission
from freight_lineitems.config import SYNTHETIC_EXAMPLES_PATH
from freight_lineitems.pipeline import prepare
from freight_lineitems.records import InputRecord
from freight_lineitems.schemas import Submission


# task 19 addendum: the amount each text presents as owed now in total, or none
STATED_AMOUNT_DUE = {"SYN-2": {"number_id": "#4", "evidence_phrase": "= TOTAL $215.00"},
                     "SYN-3": {"number_id": "#3", "evidence_phrase": "IS STILL OWED"}}


def N(i, kind, status, codes=(), ev="", excl=None, other=None, credit=False):
    return {"id": i, "kind": kind, "status": status, "is_credit": credit, "charge_codes": list(codes),
            "other_phrase": other, "evidence_phrase": ev, "exclusion_phrase": excl}


def L(ref, label, codes=(), reason=None, btype="NONE", basis=None):
    return {"amount_ref": ref, "charge_codes": list(codes), "raw_charge_label": label, "carrier_stated_reason": reason,
            "carrier_stated_basis_type": btype, "carrier_stated_basis": basis}


# (text, destination province, expected counted sum, reading, note)
EX = [
    ("INSIDE DELIVERY CHARGE OF $85.00 WAS NOT INCLUDED ON THE ORIGINAL INVOICE", "AB", "85.00",
     {"numbers": [N("#1", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.INSIDE_DELIVERY"], "INSIDE DELIVERY CHARGE OF $85.00")],
      "line_items": [L("#1", "INSIDE DELIVERY CHARGE", reason="WAS NOT INCLUDED ON THE ORIGINAL INVOICE")],
      "relations": [], "unrecognized_reads": []},
     "One named charge with one amount: one CLAIMED number, one line item; the reason is quoted, not judged."),

    ("LUMPER $120.00 + APPOINTMENT $35.00 + RESIDENTIAL $60.00 = TOTAL $215.00", "AB", "215.00",
     {"numbers": [N("#1", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.LUMPER"], "LUMPER $120.00"),
                  N("#2", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.APPOINTMENT"], "APPOINTMENT $35.00"),
                  N("#3", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.RESIDENTIAL"], "RESIDENTIAL $60.00"),
                  N("#4", "TOTAL", "NONE", [], "= TOTAL $215.00")],
      "line_items": [L("#1", "LUMPER"), L("#2", "APPOINTMENT"), L("#3", "RESIDENTIAL")],
      "relations": [{"relation_type": "SUM", "operand_ids": ["#1", "#2", "#3"], "result_id": "#4"}],
      "unrecognized_reads": []},
     "Several items and their stated total: each item is CLAIMED with its own line item; the total is a TOTAL, never "
     "a line item, and a SUM relation lets code recompute it."),

    ("ORIGINAL INVOICE BILLED $940.00. PAYMENT RECEIVED $865.00 WAS PAID ON THE FIRST REMITTANCE. "
     "$75.00 IS STILL OWED FOR DRIVER DETENTION", "AB", "75.00",
     {"numbers": [N("#1", "UNSPECIFIED_AMOUNT", "BILLED", [], "ORIGINAL INVOICE BILLED $940.00", excl="BILLED"),
                  N("#2", "UNSPECIFIED_AMOUNT", "PAID", [], "PAYMENT RECEIVED $865.00 WAS PAID", excl="WAS PAID"),
                  N("#3", "CHARGE_AMOUNT", "UNPAID", ["DETENTION_STORAGE.DRIVER_DETENTION"],
                    "$75.00 IS STILL OWED FOR DRIVER DETENTION")],
      "line_items": [L("#3", "DRIVER DETENTION", reason="IS STILL OWED")],
      "relations": [], "unrecognized_reads": []},
     "Payment history: the billed and paid amounts are history, each with an exclusion phrase because it carries '$'; "
     "only the amount still owed is counted (UNPAID). The text states no arithmetic, so no relation is written."),

    ("EQUIPMENT DETENTION 3 DAYS AT $40.00 PER DAY = $120.00. TRAILER WAS HELD WITH 18,500 LBS ON 22 PALLETS, "
     "PICKUP NUMBER 4471902", "AB", "120.00",
     {"numbers": [N("#1", "QUANTITY", "NONE", [], "3 DAYS"),
                  N("#2", "RATE", "NONE", [], "AT $40.00 PER DAY", excl="PER DAY"),
                  N("#3", "CHARGE_AMOUNT", "CLAIMED", ["DETENTION_STORAGE.EQUIPMENT_DETENTION"],
                    "EQUIPMENT DETENTION 3 DAYS AT $40.00 PER DAY = $120.00"),
                  N("#4", "QUANTITY", "NONE", [], "18,500 LBS"),
                  N("#5", "QUANTITY", "NONE", [], "22 PALLETS"),
                  N("#6", "REFERENCE", "NONE", [], "PICKUP NUMBER 4471902")],
      "line_items": [L("#3", "EQUIPMENT DETENTION", reason="TRAILER WAS HELD")],
      "relations": [{"relation_type": "PRODUCT", "operand_ids": ["#1", "#2"], "result_id": "#3"}],
      "unrecognized_reads": []},
     "Quantity x rate with the result stated: the result is the charge; the unit price is a RATE excluded with "
     "'PER DAY', the day count a QUANTITY. Weight, pallet count and a document number are not money."),

    ("REDELIVERY CHARGE $95.00 PLUS GST. LESS CREDIT OF $20.00 FOR FUEL SURCHARGE BILLED TWICE", "AB", "75.00",
     {"numbers": [N("#1", "CHARGE_AMOUNT", "CLAIMED", ["ACCESSORIAL.REDELIVERY"], "REDELIVERY CHARGE $95.00"),
                  N("#2", "CHARGE_AMOUNT", "CLAIMED", ["FUEL.SURCHARGE"], "LESS CREDIT OF $20.00 FOR FUEL SURCHARGE",
                    credit=True)],
      "line_items": [L("#1", "REDELIVERY CHARGE"),
                     L("#2", "FUEL SURCHARGE", reason="BILLED TWICE"),
                     L(None, "GST", ["TAX.GST"])],
      "relations": [], "unrecognized_reads": []},
     "A credit is still part of the claim: CLAIMED with is_credit true, and code subtracts it. A tax named without "
     "an amount ('PLUS GST') is a line item with no amount_ref; code works out the implied tax."),
]


def build() -> list[dict]:
    out = []
    for k, (text, dest, expected, reading, note) in enumerate(EX, 1):
        sid = f"SYN-{k}"
        rec = InputRecord(record_id=f"synthetic#{sid}", source="synthetic", row_number=k, shipment_key=f"SYNTHETIC.{sid}",
                          carrier="SYNTHETIC", carrier_invoice=None, pk=None, event_date=datetime(2022, 1, 1),
                          text_raw=text, delta=Decimal(expected), invoice_amount=None, shipment_amount=None,
                          origin_state=dest, destination_state=dest, reason_code=None)
        p = prepare(rec)
        assert p["redacted"] == text, f"{sid}: redaction or normalisation changed a synthetic text: {p['redacted']!r}"
        assert p["parse"].coverage_ok and not p["parse"].unrecognized, f"{sid}: unrecognized regions"
        # task 19: the two description fields (concepts.earlier_claim_mention, concepts.stated_amount_due)
        reading = {"response_type": "FIRST", "reason": None, **reading,
                   "earlier_claim_quote": None,
                   "stated_amount_due_id": STATED_AMOUNT_DUE.get(sid, {}).get("number_id"),
                   "stated_amount_due_evidence": STATED_AMOUNT_DUE.get(sid, {}).get("evidence_phrase")}
        errs, _diags, claim = check_submission(p["ctx"], Submission.model_validate(reading))
        assert not errs, f"{sid}: repair errors {[(e.code, e.path, e.evidence) for e in errs]}"
        assert claim is not None and claim.signed_sum == Decimal(expected), f"{sid}: counted {claim.signed_sum}, expected {expected}"
        out.append({"example_id": sid, "record_id": rec.record_id, "shipment_key": rec.shipment_key,
                    "marked_text": p["parse"].marked_text, "reading": reading, "note": note})
    return out


def main() -> None:
    new = json.dumps(build(), indent=1) + "\n"
    if "--check" in sys.argv[1:]:
        same = SYNTHETIC_EXAMPLES_PATH.exists() and SYNTHETIC_EXAMPLES_PATH.read_text() == new
        print(f"{len(EX)} examples valid; committed file", "matches" if same else "DIFFERS (re-run without --check)")
        sys.exit(0 if same else 1)
    SYNTHETIC_EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYNTHETIC_EXAMPLES_PATH.write_text(new)
    print(f"{len(EX)} examples written to {SYNTHETIC_EXAMPLES_PATH}")


if __name__ == "__main__":
    main()
