"""P4a: mandatory submission checks and reviewer diagnostics (decisions 3.3, 3.5, 3.7, 3.8, 4.4)."""

from decimal import Decimal

from freight_lineitems.checks import attempt_changes, check_submission, step2_diagnostics

from helpers import L, N, S, ctx, sub


def codes(xs):
    return sorted({x.code for x in xs})


def test_simple_reading_passes_and_sums():
    c = ctx("DRIVER DETENTION CHG $41.20")
    errs, rec, claim = check_submission(c, sub(S([N("#1", codes=["DETENTION_STORAGE.DRIVER_DETENTION"], ev="DRIVER DETENTION")],
                                                 [L("#1", label="DRIVER DETENTION CHG")])))
    assert errs == [] and claim.signed_sum == Decimal("41.20")


def test_missing_unknown_and_duplicate_ids_are_returned():
    c = ctx("LIFTGATE $15.00 AND INSIDE DELIVERY $13.00")
    errs, _, claim = check_submission(c, sub(S([N("#1", ev="LIFTGATE"), N("#1", ev="LIFTGATE"), N("#9", ev="LIFTGATE")], [L("#1")])))
    assert {"NUM.REF.MISSING_ID", "NUM.REF.DUPLICATE_ID", "NUM.REF.UNKNOWN_ID"} <= set(codes(errs))
    assert claim is None


def test_evidence_and_phrases_must_be_verbatim():
    c = ctx("REAR GATE DROP OFF - $18.00")
    errs, _, _ = check_submission(c, sub(S([N("#1", codes=["ACCESSORIAL.LIFTGATE"], ev="LIFT GATE FEE")],
                                           [L("#1", label="LIFTGATE", basis="PER CONTRACT", btype="CONTRACT_OR_TARIFF")])))
    assert {"NUM.JUDGMENT.EVIDENCE_NOT_FOUND", "ITEM.PHRASE.NOT_FOUND"} <= set(codes(errs))


def test_dollar_amount_left_out_needs_an_exclusion_phrase():
    """Decision 3.5: a '$' amount not counted must have source words saying why."""
    c = ctx("ONLY $275 CAME THROUGH. FUEL WAS PAID - STILL SHORT $6400.00")
    no_reason = S([N("#1", status="PAID", ev="ONLY $275"), N("#2", status="UNPAID", ev="STILL SHORT")], [L("#2")])
    errs, _, _ = check_submission(c, sub(no_reason))
    assert "NUM.JUDGMENT.EXCLUSION_UNSUPPORTED" in codes(errs)
    with_reason = S([N("#1", status="PAID", ev="ONLY $275", excl="WAS PAID"), N("#2", status="UNPAID", ev="STILL SHORT")], [L("#2")])
    errs, rec, claim = check_submission(c, sub(with_reason))
    assert errs == [] and "NUM.JUDGMENT.DOLLAR_EXCLUDED" in codes(rec) and claim.signed_sum == Decimal("6400.00")


def test_unit_rate_with_each_is_excluded_by_phrase_and_relation_is_verified():
    """Decision 3.3: stated arithmetic is recomputed by code every time."""
    c = ctx("ADD $180 DESTINATION PERDIEM 3 DAYS AT $60 EACH")
    ok = S([N("#1", codes=["DETENTION_STORAGE.CONTAINER_PER_DIEM"], ev="DESTINATION PERDIEM"),
            N("#2", kind="QUANTITY", status="NONE", ev="3 DAYS"), N("#3", kind="RATE", status="NONE", ev="AT $60 EACH", excl="EACH")],
           [L("#1")], relations=[{"relation_type": "PRODUCT", "operand_ids": ["#2", "#3"], "result_id": "#1"}])
    errs, rec, _ = check_submission(c, sub(ok))
    assert errs == [] and "ITEM.ARITH.RELATION_FAILS" not in codes(rec)
    c2 = ctx("ADD $200 DESTINATION PERDIEM 3 DAYS AT $60 EACH")
    errs, rec, _ = check_submission(c2, sub(ok))
    assert errs == [] and "ITEM.ARITH.RELATION_FAILS" in codes(rec)


def test_cue_without_relation_is_a_hint():
    c = ctx("ADD $180 DESTINATION PERDIEM 3 DAYS AT $60 EACH")
    s = S([N("#1", codes=["DETENTION_STORAGE.CONTAINER_PER_DIEM"], ev="DESTINATION PERDIEM"),
           N("#2", kind="QUANTITY", status="NONE", ev="3 DAYS"), N("#3", kind="RATE", status="NONE", ev="EACH", excl="EACH")], [L("#1")])
    _, rec, _ = check_submission(c, sub(s))
    assert "NUM.ARITH.CUE_WITHOUT_RELATION" in codes(rec)


def test_relation_with_unknown_id_is_returned():
    c = ctx("SORT FEE $50.00 + GST $2.50 = $52.50")
    s = S([N("#1", ev="SORT FEE"), N("#2", kind="TAX_AMOUNT", codes=["TAX.GST"], ev="GST"), N("#3", kind="TOTAL", status="NONE", ev="=")],
          [L("#1"), L("#2")], relations=[{"relation_type": "SUM", "operand_ids": ["#1", "#7"], "result_id": "#3"}])
    errs, _, _ = check_submission(c, sub(s))
    assert "REL.REF.INVALID" in codes(errs)


def test_tax_always_goes_to_a_person_and_rate_is_only_a_fact():
    """Decision 4.4: tax is flagged for human review; a rate difference is never judged as a carrier error."""
    c = ctx("SORT FEE $50.00 + GST $2.00 = $52.00", dest="AB")
    s = S([N("#1", codes=["ACCESSORIAL.SORT_SEGREGATE"], ev="SORT FEE"), N("#2", kind="TAX_AMOUNT", codes=["TAX.GST"], ev="GST"),
           N("#3", kind="TOTAL", status="NONE", ev="= $52.00")], [L("#1"), L("#2")],
          relations=[{"relation_type": "SUM", "operand_ids": ["#1", "#2"], "result_id": "#3"}])
    errs, rec, claim = check_submission(c, sub(s))
    assert errs == []
    assert {"ITEM.TAX.PRESENT", "ITEM.TAX.RATE_MISMATCH"} <= set(codes(rec))
    assert claim.signed_sum == Decimal("52.00")


def test_tax_without_amount_gives_expected_tax_from_table():
    c = ctx("MISSING TAILGATE CHARGE OF $20.00 + HST", dest="ON")
    s = S([N("#1", codes=["ACCESSORIAL.LIFTGATE"], ev="TAILGATE")], [L("#1"), L(None, ["TAX.HST"], label="HST")])
    errs, rec, claim = check_submission(c, sub(s))
    assert errs == [] and claim.expected_tax == Decimal("2.60")
    assert {"ITEM.TAX.PRESENT", "ITEM.TAX.NO_AMOUNT"} <= set(codes(rec))


def test_unrecognized_region_must_be_read_digit_for_digit():
    """Decision 3.8: no 'there is no number here' option."""
    c = ctx("MISSING $40.00 DETENTION AND $10.00 CV19 FEE")
    assert c.parse.unrecognized and c.parse.unrecognized[0].raw == "CV19"
    base = [N("#1", codes=["DETENTION_STORAGE.DRIVER_DETENTION"], ev="DETENTION"), N("#2", codes=["OTHER"], other="CV19 FEE", ev="CV19 FEE")]
    read_ok = {"region_id": "?1", "digits_read": "19", "as_number": N("?1", kind="REFERENCE", status="NONE", ev="CV19")}
    errs, _, _ = check_submission(c, sub(S(base, [L("#1"), L("#2")], reads=[read_ok])))
    assert errs == []
    bad = dict(read_ok, digits_read="18")
    errs, _, _ = check_submission(c, sub(S(base, [L("#1"), L("#2")], reads=[bad])))
    assert "NUM.READ.UNRECOGNIZED_MISMATCH" in codes(errs)
    errs, _, _ = check_submission(c, sub(S(base, [L("#1"), L("#2")])))
    assert "NUM.READ.UNRECOGNIZED_UNREAD" in codes(errs)


def test_other_needs_its_phrase_and_is_flagged():
    """Decision 3.7."""
    c = ctx("RESERVATION FEE $35.00")
    errs, _, _ = check_submission(c, sub(S([N("#1", codes=["OTHER"], ev="RESERVATION FEE")], [L("#1")])))
    assert "ITEM.CODE.OTHER_PHRASE_MISSING" in codes(errs)
    errs, rec, _ = check_submission(c, sub(S([N("#1", codes=["OTHER"], other="RESERVATION FEE", ev="RESERVATION FEE")], [L("#1")])))
    assert errs == [] and "ITEM.CODE.OTHER" in codes(rec)


def test_counted_amount_must_be_itemized_and_items_must_point_at_counted_amounts():
    c = ctx("FEE $10.00 AND FEE $12.00")
    errs, _, _ = check_submission(c, sub(S([N("#1", ev="FEE"), N("#2", ev="FEE")], [L("#1")])))
    assert "ITEM.REF.CLAIM_NOT_ITEMIZED" in codes(errs)
    errs, _, _ = check_submission(c, sub(S([N("#1", ev="FEE"), N("#2", status="NONE", kind="REFERENCE", ev="FEE")], [L("#1"), L("#2")])))
    assert "ITEM.REF.INVALID" in codes(errs)


def test_unit_word_conflict_and_status_on_non_money():
    c = ctx("HAZMAT $150 BOL 31 200 LBS")
    s = S([N("#1", codes=["ACCESSORIAL.HAZMAT"], ev="HAZMAT"), N("#2", ev="LBS")], [L("#1"), L("#2")])
    errs, _, _ = check_submission(c, sub(s))
    assert "NUM.JUDGMENT.UNIT_CONFLICT" in codes(errs)
    s = S([N("#1", codes=["ACCESSORIAL.HAZMAT"], ev="HAZMAT"), N("#2", kind="QUANTITY", status="CLAIMED", ev="LBS")], [L("#1")])
    errs, _, _ = check_submission(c, sub(s))
    assert "NUM.JUDGMENT.STATUS_ON_NON_MONEY" in codes(errs)


def test_credit_is_negative_in_the_sum():
    c = ctx("APPLY -$20.00 CREDIT FOR OVERBILLED FUEL")
    s = S([N("#1", codes=["FUEL.SURCHARGE"], ev="CREDIT", credit=True)], [L("#1")])
    errs, _, claim = check_submission(c, sub(s))
    assert errs == [] and claim.signed_sum == Decimal("-20.00")


def test_amount_without_name_and_name_without_amount_are_recorded():
    c = ctx("BALANCE DUE $21.00")
    _, rec, _ = check_submission(c, sub(S([N("#1", kind="UNSPECIFIED_AMOUNT", ev="BALANCE DUE")], [L("#1")])))
    assert "ITEM.AMOUNT.UNNAMED" in codes(rec)
    c = ctx("LIFTGATE FEE --")
    _, rec, _ = check_submission(c, sub(S([], [L(None, ["ACCESSORIAL.LIFTGATE"], label="LIFTGATE FEE")])))
    assert "ITEM.AMOUNT.MISSING" in codes(rec)


def test_step2_numbers_only_and_no_number():
    assert "REC.TEXT.NUMBERS_ONLY" in codes(step2_diagnostics(ctx("57.10")))
    assert "REC.TEXT.NO_NUMBER" in codes(step2_diagnostics(ctx("WAREHOUSE HANDLING ADJUSTMENT PENDING --")))


def test_attempt_changes_lists_changed_numbers():
    a = sub(S([N("#1", ev="X"), N("#2", ev="X")], [L("#1"), L("#2")]))
    b = sub(S([N("#1", ev="X"), N("#2", status="PAID", ev="X", excl="X")], [L("#1")], rtype="REVISED", reason="r"))
    ch = attempt_changes(a, b)
    assert ch == [{"id": "#2", "field": "status", "from": "CLAIMED", "to": "PAID"}]


def test_quantity_rate_without_result_is_flagged_by_code():
    """User requirement b (11-10): '2 DAY(S) @300' is found by code, not left to the model."""
    from freight_lineitems.checks import quantity_rate_patterns
    c = ctx("DWELL DTN- DERAMP 1/20/2022 (+) DELIVERY 1/24/2022= 2 DAY(S) DWELL @300")
    assert "ITEM.ARITH.QTY_RATE_NO_RESULT" in codes(step2_diagnostics(c))
    c = ctx("DERAMP 5/2/2022 (+) DELIVERY 5/6/2022= 3 DWELL DAY(S) @$250")
    assert "ITEM.ARITH.QTY_RATE_NO_RESULT" in codes(step2_diagnostics(c))
    c = ctx("ADD $180 DESTINATION PERDIEM 3 DAYS AT $60 EACH")          # result stated -> no flag
    assert "ITEM.ARITH.QTY_RATE_NO_RESULT" not in codes(step2_diagnostics(c))
    assert quantity_rate_patterns(c.text, c.parse)[0]["stated_result_ids"] == ["#1"]
    c = ctx("ADD $90 FOR ORIGIN PERDIEM 2 DAYS AT $45 A DAY")
    assert "ITEM.ARITH.QTY_RATE_NO_RESULT" not in codes(step2_diagnostics(c))
    c = ctx("STORAGE AT ORIGIN DOCK 85.0")                               # 'AT' without a quantity -> nothing
    assert quantity_rate_patterns(c.text, c.parse) == []
    c = ctx("$140 HAZMAT FEE FOR LOAD REF 7 315 LBS")
    assert quantity_rate_patterns(c.text, c.parse) == []


def test_redaction_digit_check_ignores_placeholders_already_in_text():
    """Bug found by boundary case BC049: a literal '[PERSON_1]' in the source made the check fire."""
    from freight_lineitems.textprep import redaction_altered_digits
    assert not redaction_altered_digits("LIFTGATE $10.00 APPROVED BY [PERSON_1]", "LIFTGATE $10.00 APPROVED BY [PERSON_1]")
    assert redaction_altered_digits("CONTACT X7 ABOUT LIFTGATE $10.00", "CONTACT [PERSON_1] ABOUT LIFTGATE $10.00")


def test_relation_tolerance_is_half_a_cent():
    """BC051: 3 x 10 vs 29.99 must fail."""
    c = ctx("3 DAYS AT $10 EACH STORAGE $29.99")
    s = S([N("#1", kind="QUANTITY", status="NONE", ev="3 DAYS"), N("#2", kind="RATE", status="NONE", ev="AT $10 EACH", excl="EACH"),
           N("#3", codes=["DETENTION_STORAGE.TERMINAL_STORAGE"], ev="STORAGE")], [L("#3")],
          relations=[{"relation_type": "PRODUCT", "operand_ids": ["#1", "#2"], "result_id": "#3"}])
    _, rec, _ = check_submission(c, sub(s))
    assert "ITEM.ARITH.RELATION_FAILS" in codes(rec)


def test_region_value_handles_comma_decimal():
    """Audit H1: '1.234,56' was valued 123456."""
    from freight_lineitems.checks import region_value
    assert region_value("1.234,56") == Decimal("1234.56")
    assert region_value("12.50;") == Decimal("12.50")
    assert region_value("1,234") == Decimal("1234")
    assert region_value("CV19") == Decimal("19")
    c = ctx("EU FORMAT 1.234,56 INSIDE PLACEMENT.")
    read = {"region_id": "?1", "digits_read": "123456", "as_number": N("?1", ev="INSIDE PLACEMENT")}
    errs, rec, claim = check_submission(c, sub(S([], [L("?1")], reads=[read])))
    assert errs == [] and claim.signed_sum == Decimal("1234.56")
    assert "NUM.READ.REGION_VALUE_DERIVED" in codes(rec)
