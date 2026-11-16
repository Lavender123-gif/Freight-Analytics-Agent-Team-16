"""The one implementation of 'counted' and 'history' (task 19, T18 design 4.5; definitions in config/rules.yaml
`concepts.counted`, `concepts.history`, `concepts.credit`).

Every other module asks these functions; no other file in src/ spells out which statuses or kinds are counted
(tests/test_concepts.py checks this). They accept enum members or plain strings, so they work on a validated
`Submission` and on a stored reading (plain dicts) alike.
"""

from __future__ import annotations

from decimal import Decimal

from freight_lineitems.schemas import ITEM_KINDS, MONEY_KINDS, Status

COUNTED_STATUSES: frozenset[str] = frozenset({Status.CLAIMED.value, Status.UNPAID.value})
HISTORY_STATUSES: frozenset[str] = frozenset({Status.BILLED.value, Status.PAID.value, Status.DEDUCTED.value})
COUNTED_KINDS: frozenset[str] = frozenset(k.value for k in ITEM_KINDS)
MONEY_KIND_VALUES: frozenset[str] = frozenset(k.value for k in MONEY_KINDS)


def _v(x) -> str:
    return getattr(x, "value", x)


def status_counted(status) -> bool:
    """True when the status asks for the amount in this dispute (CLAIMED or UNPAID), whatever the kind."""
    return _v(status) in COUNTED_STATUSES


def is_counted(kind, status) -> bool:
    """concepts.counted: status CLAIMED or UNPAID and kind CHARGE_AMOUNT, UNSPECIFIED_AMOUNT or TAX_AMOUNT."""
    return status_counted(status) and _v(kind) in COUNTED_KINDS


def is_history(status) -> bool:
    """concepts.history: status BILLED, PAID or DEDUCTED."""
    return _v(status) in HISTORY_STATUSES


def is_money_kind(kind) -> bool:
    return _v(kind) in MONEY_KIND_VALUES


def signed_amount(value: Decimal, is_credit: bool | None) -> Decimal:
    """concepts.credit: a counted credit enters the claim as a negative amount."""
    return -value if is_credit else value


def judgments(reading: dict) -> list[dict]:
    """Every judgment of a stored reading: the number judgments and the reads of unrecognized regions (id = region id)."""
    return list(reading.get("numbers", [])) + [u["as_number"] | {"id": u["region_id"]}
                                               for u in reading.get("unrecognized_reads", [])]


def counted_ids(reading: dict | None) -> set[str]:
    """Ids of the counted numbers of a stored reading (plain dict)."""
    if not reading:
        return set()
    return {j["id"] for j in judgments(reading) if is_counted(j["kind"], j["status"])}
