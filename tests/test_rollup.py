"""T14-03: shipment roll-up rules (T12 adjustment plan 4.3). Synthetic text and amounts only; each rule has at least
one case where it applies and one where it does not."""

from decimal import Decimal

from rollup_helpers import C, DAY1, DAY2, DAY3, T, X, codes, expl, roll, status

LIFT, FUEL, PT = "ACCESSORIAL.LIFTGATE", "FUEL.SURCHARGE", "PENDING.PURCHASED_TRANSPORTATION"
BASE, WEIGHT, MINIMUM = "RATE_CORRECTION.BASE_RATE", "RATE_CORRECTION.WEIGHT", "LINEHAUL.MINIMUM"


def test_single_explanation_sums_its_lines_and_tax():
    sh = roll(expl("LIFTGATE $50.00 GST $2.50", [C("#1", [LIFT], "LIFTGATE"), T("#2")], 1))
    assert sh["default_change"] == "52.50" and sh["new_total"] == "152.50" and sh["original_amount"] == "100.00"
    assert codes(sh) == set() and sh["recommendation"] == "PASSED_CHECKS" and sh["other_readings_range"] is None


def test_rule1_order_is_event_date_then_row():
    later_by_date = expl("LIFTGATE $60.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY2, rid="a")
    earlier_by_date = expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 2, DAY1, rid="b")
    sh = roll(later_by_date, earlier_by_date)
    assert [e["expl_id"] for e in sh["explanations"]] == ["b", "a"]
    assert sh["default_change"] == "60.00" and "SHIP.ROLLUP.ORDER_TIED" not in codes(sh)


def test_rule1_tied_dates_fall_back_to_row_and_raise_order_tied():
    a = expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 5, DAY1, rid="a")
    b = expl("LIFTGATE $60.00", [C("#1", [LIFT], "LIFTGATE")], 3, DAY1, rid="b")
    sh = roll(a, b)
    assert [e["expl_id"] for e in sh["explanations"]] == ["b", "a"] and sh["default_change"] == "50.00"
    assert {"SHIP.ROLLUP.ORDER_TIED", "SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE"} <= codes(sh)


def test_rule2_same_charge_later_replaces_earlier_with_other_reading():
    sh = roll(expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY1, rid="a"),
              expl("LIFTGATE $75.00", [C("#1", [LIFT], "LIFTGATE")], 2, DAY2, rid="b"))
    assert status(sh) == {"a#1": "SUPERSEDED", "b#1": "COUNTED"}
    assert sh["default_change"] == "75.00" and sh["recommendation"] == "HUMAN_REVIEW"
    f = next(f for f in sh["flags"] if f["code"] == "SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE")
    assert f["evidence"][0]["other_reading_new_total"] == "225.00"
    assert sh["other_readings_range"] == {"min_change": "75.00", "max_change": "125.00",
                                          "min_new_total": "175.00", "max_new_total": "225.00"}


def test_rule2_compares_finest_internal_code_not_client_name():
    """Purchased transportation, base-rate and weight corrections and a minimum charge all map to the client's
    Freight; they are different charges and must add up, not replace each other."""
    sh = roll(expl("PURCHASED TRANSPORTATION SURCHARGE $20.00", [C("#1", [PT], "PURCHASED TRANSPORTATION SURCHARGE")], 1, DAY1, rid="a"),
              expl("BASE RATE CORRECTION $35.00", [C("#1", [BASE], "BASE RATE")], 2, DAY2, rid="b"),
              expl("WEIGHT CORRECTION $12.00", [C("#1", [WEIGHT], "WEIGHT CORRECTION")], 3, DAY3, rid="c"),
              expl("MINIMUM CHARGE $90.00", [C("#1", [MINIMUM], "MINIMUM CHARGE")], 4, DAY3, rid="d"))
    assert set(status(sh).values()) == {"COUNTED"} and sh["default_change"] == "157.00"
    assert "SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE" not in codes(sh)
    assert {ln["client_name"].split(" / ")[0] for ln in __import__("freight_lineitems.charge_map", fromlist=["x"]).annotate(sh)["lines"]} == {"Freight"}


def test_rule2_other_compares_its_phrase():
    same = roll(expl("CV FEE $15.00", [C("#1", ["OTHER"], "CV FEE")], 1, DAY1, rid="a"),
                expl("CV FEE $18.00", [C("#1", ["OTHER"], "CV FEE")], 2, DAY2, rid="b"))
    assert same["default_change"] == "18.00" and "SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE" in codes(same)
    diff = roll(expl("CV FEE $15.00", [C("#1", ["OTHER"], "CV FEE")], 1, DAY1, rid="a"),
                expl("BOOKING FEE $18.00", [C("#1", ["OTHER"], "BOOKING FEE")], 2, DAY2, rid="b"))
    assert diff["default_change"] == "33.00" and "SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE" not in codes(diff)
    assert "SHIP.ROLLUP.RELATION_UNDECIDED" in codes(diff)                       # rule 7


def test_rule3_tax_follows_its_explanation():
    """The client's first example has this shape: two explanations, each a charge plus its tax, different charges."""
    sh = roll(expl("SORT FEE $40.00 + GST $2.00 = $42.00", [C("#1", ["ACCESSORIAL.SORT_SEGREGATE"], "SORT FEE"), T("#2"), X("#3")], 1, DAY1, rid="a"),
              expl("FSC $18.10 + GST $0.91 = $19.01", [C("#1", [FUEL], "FSC"), T("#2"), X("#3")], 2, DAY1, rid="b"))
    assert sh["default_change"] == "61.01" and codes(sh) == set()           # taxes are never compared with each other
    whole = roll(expl("LIFTGATE $50.00 GST $2.50", [C("#1", [LIFT], "LIFTGATE"), T("#2")], 1, DAY1, rid="a"),
                 expl("LIFTGATE $60.00 GST $3.00", [C("#1", [LIFT], "LIFTGATE"), T("#2")], 2, DAY2, rid="b"))
    assert status(whole) == {"a#1": "SUPERSEDED", "a#2": "SUPERSEDED", "b#1": "COUNTED", "b#2": "COUNTED"}
    assert whole["default_change"] == "63.00" and "SHIP.ROLLUP.TAX_PARTLY_ORPHANED" not in codes(whole)
    assert whole["other_readings"][0]["change"] == "115.50"                 # the other reading restores the tax too


def test_rule3_partial_replacement_keeps_tax_and_flags_it():
    sh = roll(expl("LIFTGATE $50.00 FSC $10.00 GST $3.00", [C("#1", [LIFT], "LIFTGATE"), C("#2", [FUEL], "FSC"), T("#3")], 1, DAY1, rid="a"),
              expl("LIFTGATE $55.00", [C("#1", [LIFT], "LIFTGATE")], 2, DAY2, rid="b"))
    assert status(sh)["a#3"] == "COUNTED" and status(sh)["a#1"] == "SUPERSEDED"
    assert "SHIP.ROLLUP.TAX_PARTLY_ORPHANED" in codes(sh) and sh["default_change"] == "68.00"


def test_rule4_different_charges_add_and_credits_are_negative():
    sh = roll(expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY1, rid="a"),
              expl("FSC CREDIT $8.00", [C("#1", [FUEL], "FSC", credit=True)], 2, DAY2, rid="b"))
    assert sh["default_change"] == "42.00" and sh["new_total"] == "142.00" and codes(sh) == set()


def test_rule5_same_amount_different_code_added_with_other_reading():
    sh = roll(expl("LIFTGATE $45.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY1, rid="a"),
              expl("INSIDE DELIVERY $45.00", [C("#1", ["ACCESSORIAL.INSIDE_DELIVERY"], "INSIDE DELIVERY")], 2, DAY2, rid="b"))
    assert sh["default_change"] == "90.00" and "SHIP.ROLLUP.SAME_AMOUNT_EARLIER" in codes(sh)
    assert sh["other_readings"] == [{"event": "E1", "flag": "SHIP.ROLLUP.SAME_AMOUNT_EARLIER", "change": "45.00", "new_total": "145.00"}]
    no = roll(expl("LIFTGATE $45.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY1, rid="a"),
              expl("INSIDE DELIVERY $46.00", [C("#1", ["ACCESSORIAL.INSIDE_DELIVERY"], "INSIDE DELIVERY")], 2, DAY2, rid="b"))
    assert "SHIP.ROLLUP.SAME_AMOUNT_EARLIER" not in codes(no)


def test_rule6a_balance_due_at_ratio_counts_only_the_balance():
    text = "SURCHARGE $20.00 BALANCE DUE $20.95"
    both = roll(expl(text, [C("#1", [PT], "SURCHARGE"), C("#2", [PT], "SURCHARGE")], 1))
    assert status(both) == {"syn#r1#1": "NOT_COUNTED", "syn#r1#2": "COUNTED"} and both["default_change"] == "20.95"
    assert {"SHIP.ROLLUP.RATIO_SUPERSEDED", "SHIP.ROLLUP.BALANCE_DUE_READING_DIFFERS"} <= codes(both)
    agreed = roll(expl(text, [X("#1", "CHARGE_AMOUNT", "BILLED", [PT]), C("#2", [PT], "SURCHARGE")], 1))
    assert agreed["default_change"] == "20.95" and "SHIP.ROLLUP.BALANCE_DUE_READING_DIFFERS" not in codes(agreed)
    model_only_first = roll(expl(text, [C("#1", [PT], "SURCHARGE"), X("#2")], 1))
    assert model_only_first["default_change"] == "20.95"                    # code counts the balance it found
    assert next(ln for ln in model_only_first["lines"] if ln["number_id"] == "#2")["added_by_code"]


def test_rule6a_does_not_fire_outside_the_ratio_and_6c_flags_it():
    sh = roll(expl("SURCHARGE $20.00 BALANCE DUE $40.00", [C("#1", [PT], "SURCHARGE"), C("#2", [PT], "SURCHARGE")], 1))
    assert sh["default_change"] == "60.00" and "SHIP.ROLLUP.RATIO_SUPERSEDED" not in codes(sh)
    assert "SHIP.ROLLUP.BALANCE_DUE_UNRESOLVED" in codes(sh)
    alone = roll(expl("BALANCE DUE IS $18.10 + GST $0.91 = $19.01", [C("#1", [FUEL], "FSC"), T("#2"), X("#3")], 1))
    assert codes(alone) == set()                                            # nothing before BALANCE DUE: an ordinary reading


def test_rule6b_adjacent_single_amounts_at_ratio_replace_even_across_codes():
    sh = roll(expl("TRANSPORTATION FEE - $44.00", [C("#1", [PT], "TRANSPORTATION FEE")], 1, DAY1, rid="a"),
              expl("BALANCE DUE $46.20", [C("#1", [], "")], 2, DAY2, rid="b"))
    assert status(sh) == {"a#1": "SUPERSEDED", "b#1": "COUNTED"} and sh["default_change"] == "46.20"
    assert "SHIP.ROLLUP.RATIO_SUPERSEDED" in codes(sh)
    no = roll(expl("TRANSPORTATION FEE - $44.00", [C("#1", [PT], "TRANSPORTATION FEE")], 1, DAY1, rid="a"),
              expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 2, DAY2, rid="b"))
    assert no["default_change"] == "94.00" and "SHIP.ROLLUP.RATIO_SUPERSEDED" not in codes(no)


def test_rule7_unnamed_or_overlapping_combined_amounts_are_added_and_flagged():
    sh = roll(expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY1, rid="a"),
              expl("PLEASE PAY $80.00", [C("#1", [], "")], 2, DAY2, rid="b"))
    assert sh["default_change"] == "130.00" and "SHIP.ROLLUP.RELATION_UNDECIDED" in codes(sh)
    combo = roll(expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY1, rid="a"),
                 expl("LIFTGATE AND INSIDE $90.00", [C("#1", [LIFT, "ACCESSORIAL.INSIDE_DELIVERY"], "LIFTGATE AND INSIDE")], 2, DAY2, rid="b"))
    assert combo["default_change"] == "140.00" and "SHIP.ROLLUP.RELATION_UNDECIDED" in codes(combo)
    apart = roll(expl("FSC $10.00", [C("#1", [FUEL], "FSC")], 1, DAY1, rid="a"),
                 expl("LIFTGATE AND INSIDE $90.00", [C("#1", [LIFT, "ACCESSORIAL.INSIDE_DELIVERY"], "LIFTGATE AND INSIDE")], 2, DAY2, rid="b"))
    assert codes(apart) == set() and apart["default_change"] == "100.00"


def test_rule8_unusable_explanation_leaves_a_default_and_marks_incomplete():
    sh = roll(expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY1, rid="a"),
              expl("GARBLED $9.00", [], 2, DAY2, rid="b", usable=False, recommendation="HUMAN_REVIEW"))
    assert sh["default_change"] == "50.00" and not sh["complete"] and "SHIP.ROLLUP.INCOMPLETE" in codes(sh)
    assert sh["recommendation"] == "HUMAN_REVIEW"


def test_shipment_colour_is_the_worst_of_explanations_and_its_flags():
    sh = roll(expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY1, rid="a"),
              expl("", [], 2, DAY2, rid="b", recommendation="RETURN_SUGGESTED"))
    assert sh["recommendation"] == "RETURN_SUGGESTED" and sh["shipment_flags_recommendation"] == "PASSED_CHECKS"


def test_order_count_is_distinct_pks_over_the_shipment():
    sh = roll(expl("LIFTGATE $50.00", [C("#1", [LIFT], "LIFTGATE")], 1, DAY1, rid="a", pks=("P1", "P2")),
              expl("FSC $5.00", [C("#1", [FUEL], "FSC")], 3, DAY2, rid="b", pks=("P2", "P3")))
    assert sh["n_orders"] == 3 and Decimal(sh["default_change"]) == Decimal("55.00")


def test_t15_balance_due_rules_on_the_shapes_of_the_passed_unclear_records():
    """T15 section 6.2 (synthetic): rule 6c covers BALANCE DUE written after other '$' amounts (A5's class); a text that
    starts with BALANCE DUE and then itemises 'charge + tax = total' is an ordinary reading and gets no roll-up flag."""
    first = roll(expl("FSC SHOULD APPLY. BALANCE DUE IS $18.10 + GST $0.91 = $19.01", [C("#1", [FUEL], "FSC"), T("#2"), X("#3")], 1))
    assert codes(first) == set()
    after = roll(expl("LIFTGATE $15 REDELIVERY $150 BALANCE DUE $199.40",
                      [C("#1", [LIFT], "LIFTGATE"), C("#2", ["ACCESSORIAL.REDELIVERY"], "REDELIVERY"), X("#3")], 1))
    assert "SHIP.ROLLUP.BALANCE_DUE_UNRESOLVED" in codes(after)


def test_t17_rule9_echo_of_an_earlier_history_amount():
    hist = expl("EARLIER CLAIM $160.00 FOR PRIOR SERVICE", [X("#1", "CHARGE_AMOUNT", "BILLED", [])], 1, DAY1, rid="a")
    same = roll(hist, expl("DETENTION $160.00 REBILL", [C("#1", ["DETENTION_STORAGE.DRIVER_DETENTION"], "DETENTION")], 2, DAY2, rid="b"))
    assert "SHIP.ROLLUP.ECHO_OF_HISTORY_AMOUNT" in codes(same) and same["default_change"] == "160.00"
    ratio = roll(hist, expl("DETENTION $168.00 REV CHG", [C("#1", ["DETENTION_STORAGE.DRIVER_DETENTION"], "DETENTION")], 2, DAY2, rid="b"))
    assert "SHIP.ROLLUP.ECHO_OF_HISTORY_AMOUNT" in codes(ratio)
    other = roll(hist, expl("DETENTION $90.00", [C("#1", ["DETENTION_STORAGE.DRIVER_DETENTION"], "DETENTION")], 2, DAY2, rid="b"))
    assert "SHIP.ROLLUP.ECHO_OF_HISTORY_AMOUNT" not in codes(other)
    # an earlier counted amount is rule 2 / rule 5 territory, not rule 9
    counted = roll(expl("DETENTION $160.00", [C("#1", ["DETENTION_STORAGE.DRIVER_DETENTION"], "DETENTION")], 1, DAY1, rid="a"),
                   expl("LIFTGATE $160.00", [C("#1", [LIFT], "LIFTGATE")], 2, DAY2, rid="b"))
    assert "SHIP.ROLLUP.ECHO_OF_HISTORY_AMOUNT" not in codes(counted)
