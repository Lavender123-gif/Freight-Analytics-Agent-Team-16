"""Task 19 step 4 and addendum: the reading's `earlier_claim_quote` and `stated_amount_due_id` /
`stated_amount_due_evidence` fields (concepts earlier_claim_mention and stated_amount_due; flat nullable strings).

The stated amount due only describes what the text writes: it is checked against the text, stored, and changes no
claim total and no flag. An earlier-claim quote raises CLAIM.EARLIER_CLAIM_MENTIONED (attention).
Synthetic texts only."""

from __future__ import annotations

import pytest

from freight_lineitems.checks import check_submission
from freight_lineitems.disposition import flags_from, recommend
from freight_lineitems.pipeline import assemble, prepare, stated_amount_due
from freight_lineitems.reading_checks import reading_diagnostics
from helpers import L, N, S, ctx, record, sub


def _with(reading: dict, sad=None, quote=None) -> dict:
    return reading | {"stated_amount_due_id": sad["number_id"] if sad else None,
                      "stated_amount_due_evidence": sad["evidence_phrase"] if sad else None, "earlier_claim_quote": quote}


# the five wordings the addendum names; (text, reading, stated id, evidence, counted sum)
CASES = {
    "only_balance_due": ("TL FSC SHOULD APPLY. BALANCE DUE IS $55.42",
                         S([N("#1", codes=["RATE_CORRECTION.FUEL_TIER"], ev="BALANCE DUE IS $55.42")], [L("#1")]),
                         "#1", "BALANCE DUE IS $55.42", "55.42"),
    "amount_tax_total": ("LIFTGATE $100.00 + HST $13.00 = $113.00",
                         S([N("#1", codes=["ACCESSORIAL.LIFTGATE"], ev="LIFTGATE $100.00"),
                            N("#2", kind="TAX_AMOUNT", codes=["TAX.HST"], ev="HST $13.00"),
                            N("#3", kind="TOTAL", status="NONE", ev="= $113.00")], [L("#1"), L("#2")],
                           relations=[{"relation_type": "SUM", "operand_ids": ["#1", "#2"], "result_id": "#3"}]),
                         "#3", "= $113.00", "113.00"),
    "balance_due_after_other_amounts": ("DETENTION BILLED $200.00 PAID $150.00 BALANCE DUE $50.00",
                         S([N("#1", status="BILLED", codes=["DETENTION_STORAGE.DRIVER_DETENTION"], ev="DETENTION BILLED $200.00", excl="BILLED"),
                            N("#2", status="PAID", codes=["DETENTION_STORAGE.DRIVER_DETENTION"], ev="PAID $150.00", excl="PAID"),
                            N("#3", status="UNPAID", codes=["DETENTION_STORAGE.DRIVER_DETENTION"], ev="BALANCE DUE $50.00")], [L("#3")]),
                         "#3", "BALANCE DUE $50.00", "50.00"),
    "payment_history": ("INVOICED $940.00 RECEIVED $865.00 $75.00 STILL OWED FOR LUMPER",
                         S([N("#1", kind="UNSPECIFIED_AMOUNT", status="BILLED", ev="INVOICED $940.00", excl="INVOICED"),
                            N("#2", kind="UNSPECIFIED_AMOUNT", status="PAID", ev="RECEIVED $865.00", excl="RECEIVED"),
                            N("#3", status="UNPAID", codes=["ACCESSORIAL.LUMPER"], ev="$75.00 STILL OWED FOR LUMPER")], [L("#3")]),
                         "#3", "STILL OWED", "75.00"),
    "none": ("INSIDE DELIVERY $85.00", S([N("#1", codes=["ACCESSORIAL.INSIDE_DELIVERY"], ev="INSIDE DELIVERY $85.00")], [L("#1")]),
             None, None, "85.00"),
}


@pytest.mark.parametrize("name", list(CASES))
def test_stated_amount_due_is_checked_and_changes_nothing(name):
    text, reading, sid, ev, total = CASES[name]
    sad = {"number_id": sid, "evidence_phrase": ev} if sid else None
    errs, rec, claim = check_submission(ctx(text), sub(_with(reading, sad)))
    assert errs == [] and str(claim.signed_sum) == total
    # the field changes no total and no diagnostic: the same reading without it gives the same result
    errs0, rec0, claim0 = check_submission(ctx(text), sub(_with(reading, None)))
    assert claim0.signed_sum == claim.signed_sum and [d.code for d in rec0] == [d.code for d in rec]
    assert reading_diagnostics({"numbers": []}, _with(reading, sad)) == reading_diagnostics({"numbers": []}, _with(reading, None))


def test_stated_amount_due_must_point_at_a_number_and_quote_the_text():
    text, reading, *_ = CASES["only_balance_due"]
    errs, _, _ = check_submission(ctx(text), sub(_with(reading, {"number_id": "#9", "evidence_phrase": "BALANCE DUE"})))
    assert [(e.code, e.path) for e in errs] == [("NUM.REF.UNKNOWN_ID", "stated_amount_due_id")]
    errs, _, _ = check_submission(ctx(text), sub(_with(reading, {"number_id": "#1", "evidence_phrase": "AMOUNT OWING"})))
    assert [(e.code, e.path) for e in errs] == [("ITEM.PHRASE.NOT_FOUND", "stated_amount_due_evidence")]
    half = _with(reading) | {"stated_amount_due_id": "#1"}          # an id without its evidence
    errs, _, _ = check_submission(ctx(text), sub(half))
    assert [(e.code, e.path) for e in errs] == [("ITEM.PHRASE.NOT_FOUND", "stated_amount_due_evidence")]


def test_stated_amount_due_is_stored_with_its_value():
    text, reading, sid, ev, _ = CASES["balance_due_after_other_amounts"]
    p = prepare(record(text, "50"))
    assert stated_amount_due(p["parse"], _with(reading, {"number_id": sid, "evidence_phrase": ev})) == \
        {"number_id": "#3", "value": "50.00", "evidence_phrase": "BALANCE DUE $50.00"}
    assert stated_amount_due(p["parse"], _with(reading, None)) is None
    assert stated_amount_due(p["parse"], None) is None


def test_earlier_claim_mention_needs_a_quote_from_the_text():
    text = "EARLIER CLAIM $100.00 FOR PRIOR ACCESSORIAL"
    reading = S([N("#1", kind="UNSPECIFIED_AMOUNT", status="CLAIMED", ev="EARLIER CLAIM $100.00")], [L("#1")])
    errs, _, _ = check_submission(ctx(text), sub(_with(reading, quote="EARLIER CLAIM")))
    assert errs == []
    errs, _, _ = check_submission(ctx(text), sub(_with(reading, quote="SECOND REQUEST")))
    assert [(e.code, e.path) for e in errs] == [("ITEM.PHRASE.NOT_FOUND", "earlier_claim_quote")]


def test_earlier_claim_mention_sends_to_a_person():
    reading = _with(S([N("#1")], [L("#1")]), quote="EARLIER CLAIM")
    d = reading_diagnostics({"numbers": [{"id": "#1", "has_dollar": True}]}, reading)
    assert [x.code for x in d] == ["CLAIM.EARLIER_CLAIM_MENTIONED"] and d[0].evidence == {"quote": "EARLIER CLAIM"}
    assert recommend(flags_from(d))["recommendation"] == "HUMAN_REVIEW"
    plain = _with(S([N("#1")], [L("#1")]))
    assert reading_diagnostics({"numbers": [{"id": "#1", "has_dollar": True}]}, plain) == []


def test_old_readings_without_the_fields_still_validate():
    old = S([N("#1")], [L("#1")])
    s = sub(old)
    assert s.earlier_claim_quote is None and s.stated_amount_due_id is None and s.stated_amount_due_evidence is None
    assert reading_diagnostics({"numbers": [{"id": "#1", "has_dollar": True}]}, old) == []


def test_tool_schema_requires_the_fields_as_flat_nullable_strings():
    """Nested objects made the strict grammar too large for the API (smoke run, task 19); the fields stay flat."""
    from freight_lineitems.tools import TOOLS
    sch = next(t for t in TOOLS if t["name"] == "submit_line_items")["input_schema"]
    for f in ("earlier_claim_quote", "stated_amount_due_id", "stated_amount_due_evidence"):
        assert f in sch["required"] and "default" not in str(sch["properties"][f])
        assert {x.get("type") for x in sch["properties"][f]["anyOf"]} == {"string", "null"}
