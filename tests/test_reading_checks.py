"""Task 17: checks on a final reading (synthetic text only)."""

from freight_lineitems.numbers import parse
from freight_lineitems.reading_checks import reading_diagnostics

from helpers import N, S


def table(text):
    return parse(text).model_dump(mode="json")


def codes(text, numbers):
    return {d.code for d in reading_diagnostics(table(text), S(numbers, []))}


def test_nothing_counted_when_every_money_amount_is_history():
    assert "CLAIM.NOTHING_COUNTED" in codes("EARLIER CLAIM $90.00 FOR PRIOR SERVICE",
                                           [N("#1", status="BILLED", ev="EARLIER CLAIM", excl="EARLIER")])
    # no '$' but read as a money amount: still a money amount
    assert "CLAIM.NOTHING_COUNTED" in codes("EARLIER CLAIM 90.00 FOR PRIOR SERVICE",
                                           [N("#1", status="BILLED", ev="EARLIER CLAIM", excl="EARLIER")])


def test_not_raised_when_something_is_counted_or_there_is_no_money():
    assert "CLAIM.NOTHING_COUNTED" not in codes("LIFTGATE $45.00 PAID $10.00",
                                               [N("#1", ev="LIFTGATE"), N("#2", status="PAID", ev="PAID", excl="PAID")])
    assert "CLAIM.NOTHING_COUNTED" not in codes("SEE BOL 12345", [N("#1", kind="REFERENCE", status="NONE", ev="BOL")])
    assert reading_diagnostics(table("LIFTGATE $45.00"), None) == []


def test_leading_dot_amount_counted():
    assert "ITEM.AMOUNT.LEADING_DOT_COUNTED" in codes(".62 FSC", [N("#1", codes=["FUEL.SURCHARGE"], ev="FSC")])
    assert "ITEM.AMOUNT.LEADING_DOT_COUNTED" not in codes(".62 FSC", [N("#1", kind="RATE", status="NONE", ev="FSC")])
    assert "ITEM.AMOUNT.LEADING_DOT_COUNTED" not in codes("FSC $0.62", [N("#1", codes=["FUEL.SURCHARGE"], ev="FSC")])
