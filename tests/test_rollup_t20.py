"""Task 20: the BALANCE DUE rule wherever it is written (D-95), the gap columns (concepts.gap, D-96) and the two
roll-up extension points (cross-batch history, relation suggestions). Synthetic text and amounts only."""

from decimal import Decimal

from freight_lineitems import rollup
from freight_lineitems.rollup import DictPriorHistory, explanation_from_result

from rollup_helpers import C, DAY2, T, X, codes, expl, roll

FUEL, LIFT, DET = "RATE_CORRECTION.FUEL_TIER", "ACCESSORIAL.LIFTGATE", "DETENTION_STORAGE.DRIVER_DETENTION"
UNRESOLVED, DIFFERS = "SHIP.ROLLUP.BALANCE_DUE_UNRESOLVED", "SHIP.ROLLUP.BALANCE_DUE_READING_DIFFERS"


def _flag(sh, code):
    return next(f for f in sh["flags"] if f["code"] == code)


# ------------------------------------------------------------------------------------------------ BALANCE DUE (D-95)

def test_balance_due_first_with_one_amount_is_the_amount_asked_for():
    sh = roll(expl("FSC SHOULD APPLY. BALANCE DUE IS $36.40", [C("#1", [FUEL], "FSC")], 1))
    assert codes(sh) == set() and sh["default_change"] == "36.40"


def test_balance_due_first_amount_plus_tax_that_adds_up_counts_both():
    text = "BALANCE DUE IS $18.10 + GST $0.91 = $19.01"
    sh = roll(expl(text, [C("#1", [FUEL], "FSC"), T("#2"), X("#3")], 1))
    assert codes(sh) == set() and sh["default_change"] == "19.01"
    no_total = roll(expl("BALANCE DUE $18.10 + GST $0.91", [C("#1", [FUEL], "FSC"), T("#2")], 1))
    assert codes(no_total) == set()                                      # amount + tax without a written total
    tax_missed = roll(expl(text, [C("#1", [FUEL], "FSC"), X("#2", "TAX_AMOUNT", "NONE"), X("#3")], 1))
    assert DIFFERS in codes(tax_missed) and _flag(tax_missed, DIFFERS)["evidence"][0]["case"] == "amount_plus_tax"


def test_balance_due_first_amount_plus_tax_that_does_not_add_up_goes_to_a_person():
    sh = roll(expl("BALANCE DUE IS $18.10 + GST $0.91 = $21.00", [C("#1", [FUEL], "FSC"), T("#2"), X("#3")], 1))
    ev = _flag(sh, UNRESOLVED)["evidence"][0]
    assert ev["position"] == "first" and sh["shipment_flags_recommendation"] == "HUMAN_REVIEW"


def test_balance_due_first_with_an_unrelated_amount_goes_to_a_person():
    sh = roll(expl("BALANCE DUE $55.00 LIFTGATE ORIGINALLY INVOICED $300.00",
                   [C("#1", [LIFT], "LIFTGATE"), X("#2", "CHARGE_AMOUNT", "BILLED", [LIFT])], 1))
    assert _flag(sh, UNRESOLVED)["evidence"][0]["position"] == "first"
    assert sh["default_change"] == "55.00"                               # the model's reading stands


def test_balance_due_equal_to_the_sum_of_the_other_amounts_is_a_decided_relation_in_any_position():
    first = roll(expl("BALANCE DUE $100.00 FOR LIFTGATE $60.00 AND DETENTION $40.00",
                      [X("#1"), C("#2", [LIFT], "LIFTGATE"), C("#3", [DET], "DETENTION")], 1))
    after = roll(expl("LIFTGATE $60.00 DETENTION $40.00 BALANCE DUE $100.00",
                      [C("#1", [LIFT], "LIFTGATE"), C("#2", [DET], "DETENTION"), X("#3")], 1))
    assert codes(first) == set() and codes(after) == set()
    assert first["default_change"] == after["default_change"] == "100.00"


def test_balance_due_after_other_amounts_with_no_relation_still_goes_to_a_person():
    sh = roll(expl("LIFTGATE $15 REDELIVERY $150 BALANCE DUE $199.40",
                   [C("#1", [LIFT], "LIFTGATE"), C("#2", [LIFT], "REDELIVERY"), C("#3", [], "")], 1))
    assert _flag(sh, UNRESOLVED)["evidence"][0]["position"] == "after_other_amounts"


def test_balance_due_relation_function_order():
    d = {"id": "#1", "value": Decimal("105.00")}
    assert rollup.balance_due_relation(d, [], {}) == ("single_amount", [])
    assert rollup.balance_due_relation(d, [{"id": "#2", "value": Decimal("100.00")}], {}) == ("ratio", [])
    tax = {"id": "#2", "value": Decimal("5.25")}
    assert rollup.balance_due_relation(d, [tax, {"id": "#3", "value": Decimal("110.25")}],
                                       {"#2": {"kind": "TAX_AMOUNT"}}) == ("amount_plus_tax", ["#2"])
    assert rollup.balance_due_relation(d, [{"id": "#2", "value": Decimal("50")}, {"id": "#3", "value": Decimal("55")}], {})[0] == "total"
    assert rollup.balance_due_relation(d, [{"id": "#2", "value": Decimal("300")}], {}) == (None, [])


# --------------------------------------------------------------------------------------------------- gap (D-96)

def test_gap_single_explanation_three_numbers():
    sh = roll(expl("DETENTION $50.00 + HST $6.50 BALANCE DUE $56.50", [C("#1", [DET], "DETENTION"), T("#2", "TAX.HST", "HST"), X("#3")],
                   1, due="#3"))
    assert (sh["items_total"], sh["stated_amount_due"], sh["gap"]) == ("56.50", "56.50", "0.00")
    assert not {"SHIP.GAP.NONZERO", "SHIP.GAP.MULTI_EXPLANATION"} & codes(sh)


def test_gap_not_zero_is_info_only_and_never_a_line():
    base = roll(expl("DETENTION $50.00 AMOUNT DUE $60.00", [C("#1", [DET], "DETENTION"), X("#2")], 1))
    sh = roll(expl("DETENTION $50.00 AMOUNT DUE $60.00", [C("#1", [DET], "DETENTION"), X("#2")], 1, due="#2"))
    assert sh["gap"] == "10.00" and _flag(sh, "SHIP.GAP.NONZERO")["severity"] == "info"
    assert sh["recommendation"] == base["recommendation"] == "PASSED_CHECKS"
    assert sh["default_change"] == base["default_change"] == "50.00" and len(sh["lines"]) == len(base["lines"])


def test_gap_empty_not_zero_when_nothing_is_stated():
    sh = roll(expl("DETENTION $50.00", [C("#1", [DET], "DETENTION")], 1))
    assert sh["stated_amount_due"] is None and sh["gap"] is None and sh["items_total"] == "50.00"
    assert sh["explanations"][0]["gap"] is None


def test_gap_multi_explanation_shipment_lists_each_and_leaves_the_shipment_empty():
    sh = roll(expl("LIFTGATE $75.00", [C("#1", [LIFT], "LIFTGATE")], 1, rid="a"),
              expl("DETENTION $50.00 TOTAL DUE $55.00", [C("#1", [DET], "DETENTION"), X("#2")], 2, DAY2, rid="b", due="#2"))
    assert sh["stated_amount_due"] is None and sh["gap"] is None and sh["gap_note"] == "MULTI_EXPLANATION_NO_SHIPMENT_GAP"
    assert [(e["items_total"], e["stated_amount_due"], e["gap"]) for e in sh["explanations"]] == [
        ("75.00", None, None), ("50.00", "55.00", "5.00")]
    assert _flag(sh, "SHIP.GAP.MULTI_EXPLANATION")["severity"] == "info" and "SHIP.GAP.NONZERO" in codes(sh)
    plain = roll(expl("LIFTGATE $75.00", [C("#1", [LIFT], "LIFTGATE")], 1, rid="a"),
                 expl("DETENTION $50.00", [C("#1", [DET], "DETENTION")], 2, DAY2, rid="b"))
    assert plain["gap_note"] is None and "SHIP.GAP.MULTI_EXPLANATION" not in codes(plain)


def test_gap_of_an_explanation_counts_its_own_lines_even_when_a_later_one_replaces_them():
    sh = roll(expl("LIFTGATE $75.00 BALANCE DUE $75.00", [C("#1", [LIFT], "LIFTGATE"), X("#2")], 1, rid="a", due="#2"),
              expl("LIFTGATE $80.00", [C("#1", [LIFT], "LIFTGATE")], 2, DAY2, rid="b"))
    assert sh["explanations"][0]["gap"] == "0.00" and sh["default_change"] == "80.00"


# ----------------------------------------------------------------------------------------------- extension points

def test_prior_history_default_is_not_provided_never_none():
    sh = roll(expl("LIFTGATE $75.00", [C("#1", [LIFT], "LIFTGATE")], 1))
    assert sh["prior_history"] == {"status": "NOT_PROVIDED", "items": [], "source": None}


def test_prior_history_three_states_from_a_source():
    e = [explanation_from_result(expl("LIFTGATE $75.00", [C("#1", [LIFT], "LIFTGATE")], 1))]
    src = DictPriorHistory({"S1": [{"batch": "earlier", "explanation": "x", "amount": "75.00"}]}, source="test")
    found = rollup.rollup("S1", Decimal("100"), e, prior_history=src)
    e2 = [explanation_from_result(expl("LIFTGATE $75.00", [C("#1", [LIFT], "LIFTGATE")], 1))]
    none = rollup.rollup("S2", Decimal("100"), e2, prior_history=src)
    assert found["prior_history"]["status"] == "FOUND" and len(found["prior_history"]["items"]) == 1
    assert none["prior_history"] == {"status": "CHECKED_NONE", "items": [], "source": "test"}
    assert found["default_change"] == none["default_change"] == "75.00"      # history changes no total today


def test_rule7_shipment_is_marked_and_suggestions_are_carried_but_change_nothing():
    a = expl("LUMPER $40.00", [C("#1", ["OTHER"], "LUMPER")], 1, rid="a")
    b = expl("STOP FEE $40.00", [C("#1", ["OTHER"], "STOP FEE")], 2, DAY2, rid="b")
    plain = roll(a, b)
    assert plain["relation_undecided"] and plain["relation_suggestions"] == []
    sug = [{"line": "b:#1", "relation": "replaces", "of": "a:#1", "source": "history-reading skill (test)"}]
    with_sug = rollup.rollup("S1", Decimal("100"), [explanation_from_result(x) for x in (a, b)], relation_suggestions=sug)
    assert with_sug["relation_suggestions"] == sug and with_sug["default_change"] == plain["default_change"]
    one = roll(expl("LIFTGATE $75.00", [C("#1", [LIFT], "LIFTGATE")], 1))
    assert one["relation_undecided"] is False


def test_shipment_output_carries_its_schema_version():
    assert roll(expl("LIFTGATE $75.00", [C("#1", [LIFT], "LIFTGATE")], 1))["schema_version"] == rollup.SHIPMENT_SCHEMA_VERSION
