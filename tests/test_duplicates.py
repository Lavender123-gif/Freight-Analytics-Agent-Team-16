"""R1b: row-level and invoice-level duplicate flags (decision 5.3); mock-style positive and negative cases."""

from freight_lineitems import duplicates
from freight_lineitems.pipeline import assemble, prepare

from helpers import record


def fake_result(rec, items):
    """A PASSED_CHECKS result whose reading counts the given (code, amount_id) items."""
    out = assemble(prepare(rec), None)
    out["facts"]["parse_status"] = "PASSED_CHECKS"
    nums = [{"id": f"#{i+1}", "kind": "CHARGE_AMOUNT", "status": "CLAIMED", "is_credit": False, "charge_codes": [c],
             "other_phrase": None, "evidence_phrase": "x", "exclusion_phrase": None} for i, c in enumerate(items)]
    lis = [{"amount_ref": f"#{i+1}", "charge_codes": []} for i, _ in enumerate(items)]
    out["facts"]["reading"] = {"numbers": nums, "line_items": lis, "unrecognized_reads": []}
    out["judgment"] = {"flags": [], "recommendation": "PASSED_CHECKS", "diagnostics": []}   # no model run in this test
    return out


def codes(res):
    return {f["code"] for f in res["judgment"]["flags"]}


def test_row_copies_first_hint_later_flagged_and_pointing_back():
    a = record("DETENTION $50.00", "50", rid="dev#r1", pk="P1")
    b = record("DETENTION $50.00", "50", rid="dev#r2", pk="P2"); b.row_number = 2
    c = record("DETENTION $50.00", "50", rid="dev#r3", pk="P3"); c.row_number = 3
    res = duplicates.apply([a, b, c], [fake_result(x, ["DETENTION_STORAGE.DRIVER_DETENTION"]) for x in (a, b, c)])
    first, second, third = res
    assert "DUP.ROW.HAS_LATER_COPIES" in codes(first) and "DUP.ROW.COPY" not in codes(first)
    assert first["judgment"]["recommendation"] == "PASSED_CHECKS"           # the hint does not change colour
    for r in (second, third):
        f = next(f for f in r["judgment"]["flags"] if f["code"] == "DUP.ROW.COPY")
        assert f["points_to"] == "dev#r1" and r["judgment"]["recommendation"] == "HUMAN_REVIEW"
    # ROW copies are not counted again at INVOICE level
    assert not any("DUP.INVOICE.SAME_CHARGE" in codes(r) for r in res)


def test_row_negative_one_feature_differs():
    a = record("DETENTION $50.00", "50", rid="dev#r1")
    b = record("DETENTION $50.00", "55", rid="dev#r2"); b.row_number = 2     # same text, different Delta
    res = duplicates.apply([a, b], [fake_result(x, ["DETENTION_STORAGE.DRIVER_DETENTION"]) for x in (a, b)])
    assert not any(c.startswith("DUP.ROW") for r in res for c in codes(r))


def test_invoice_same_charge_later_dispute_flagged_first_not():
    a = record("LIFTGATE $15.00", "15", rid="dev#r1")
    b = record("LIFTGATE AGAIN $15.00", "15", rid="dev#r2"); b.row_number = 2
    res = duplicates.apply([a, b], [fake_result(a, ["ACCESSORIAL.LIFTGATE"]), fake_result(b, ["ACCESSORIAL.LIFTGATE"])])
    assert "DUP.INVOICE.SAME_CHARGE" not in codes(res[0])
    f = next(f for f in res[1]["judgment"]["flags"] if f["code"] == "DUP.INVOICE.SAME_CHARGE")
    assert f["points_to"] == "dev#r1"


def test_invoice_negative_other_invoice_or_other_code_or_tax():
    a = record("LIFTGATE $15.00", "15", rid="dev#r1", invoice="I1")
    b = record("LIFTGATE $15.00 AGAIN", "15", rid="dev#r2", invoice="I2"); b.row_number = 2
    res = duplicates.apply([a, b], [fake_result(a, ["ACCESSORIAL.LIFTGATE"]), fake_result(b, ["ACCESSORIAL.LIFTGATE"])])
    assert not any("DUP.INVOICE.SAME_CHARGE" in codes(r) for r in res)
    a = record("LIFTGATE $15.00 + GST", "15", rid="dev#r1")
    b = record("INSIDE DELIVERY $13.00 + GST", "13", rid="dev#r2"); b.row_number = 2
    res = duplicates.apply([a, b], [fake_result(a, ["ACCESSORIAL.LIFTGATE", "TAX.GST"]),
                                    fake_result(b, ["ACCESSORIAL.INSIDE_DELIVERY", "TAX.GST"])])
    assert not any("DUP.INVOICE.SAME_CHARGE" in codes(r) for r in res)


def test_same_charge_twice_within_one_dispute():
    a = record("LIFTGATE $15.00 LIFTGATE $15.00", "30", rid="dev#r1")
    res = duplicates.apply([a], [fake_result(a, ["ACCESSORIAL.LIFTGATE", "ACCESSORIAL.LIFTGATE"])])
    f = next(f for f in res[0]["judgment"]["flags"] if f["code"] == "DUP.INVOICE.SAME_CHARGE")
    assert f["evidence"][0]["same_dispute"] is True


def test_different_other_charges_are_not_duplicates_and_unchecked_readings_are_marked():
    """Audit M5."""
    a = record("YARD ESCORT $50", "50", rid="dev#r1")
    b = record("GATE PASS $50", "50", rid="dev#r2"); b.row_number = 2
    ra, rb = fake_result(a, ["OTHER"]), fake_result(b, ["OTHER"])
    ra["facts"]["reading"]["numbers"][0]["other_phrase"] = "YARD ESCORT"
    rb["facts"]["reading"]["numbers"][0]["other_phrase"] = "GATE PASS"
    res = duplicates.apply([a, b], [ra, rb])
    assert not any("DUP.INVOICE.SAME_CHARGE" in codes(r) for r in res)
    c = record("LIFTGATE $15", "15", rid="dev#r3"); c.row_number = 3
    rc = fake_result(c, ["ACCESSORIAL.LIFTGATE"]); rc["facts"]["parse_status"] = "FAILED_CHECKS"
    res = duplicates.apply([c], [rc])
    assert "DUP.INVOICE.NOT_CHECKED" in codes(res[0])


def test_missing_event_date_does_not_crash():
    """Audit M2."""
    a = record("LIFTGATE $15.00", "15", rid="dev#r1")
    b = record("LIFTGATE AGAIN $15.00", "15", rid="dev#r2"); b.row_number = 2; b.event_date = None
    duplicates.apply([a, b], [fake_result(a, ["ACCESSORIAL.LIFTGATE"]), fake_result(b, ["ACCESSORIAL.LIFTGATE"])])
