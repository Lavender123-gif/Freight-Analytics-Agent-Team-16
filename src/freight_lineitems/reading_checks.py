"""Checks on a final reading that need no model call (task 14 / T15-T17 recall fixes, user decisions D-76, D-80).

They run in `pipeline.assemble` on every reading, and on stored readings when a run is replayed, so a stored run can be
re-coloured without calling the model. Inputs are the number table and the reading as stored (plain dicts).
Each finding is a Diagnostic; its severity is in config/rules.yaml.

- CLAIM.NOTHING_COUNTED: the text has at least one money amount (a number written with '$', or a number the reading
  classes as a money kind) and the reading counts none of them. Covers wording that mentions an earlier claim or a
  prior charge without saying whether it is still asked for (D-80): a person decides.
- ITEM.AMOUNT.LEADING_DOT_COUNTED: a counted amount written with a leading dot ('.74'); such a number may be a rate
  (per mile, per pound) rather than an amount, and no rule decides which (D-76).
- CLAIM.EARLIER_CLAIM_MENTIONED (task 19, T18 M2, D-80): the reading says the text mentions an earlier claim for this
  shipment (concepts.earlier_claim_mention); a person decides whether it is still asked for. Whether the shipment has
  an earlier explanation is a cross-explanation check, implemented next week.
"""

from __future__ import annotations

from freight_lineitems.checks import diag
from freight_lineitems.claim import counted_ids, is_money_kind
from freight_lineitems.claim import judgments as _judgments
from freight_lineitems.schemas import Diagnostic


def reading_diagnostics(number_table: dict, reading: dict | None) -> list[Diagnostic]:
    """Diagnostics on one final reading. Returns [] when there is no reading."""
    if not reading:
        return []
    out: list[Diagnostic] = []
    js = _judgments(reading)
    money = {n["id"] for n in number_table.get("numbers", []) if n.get("has_dollar")} | {j["id"] for j in js if is_money_kind(j["kind"])}
    counted = counted_ids(reading)
    if money and not counted:
        out.append(diag("CLAIM.NOTHING_COUNTED", "claim", {"money_ids": sorted(money),
                        "statuses": {j["id"]: j["status"] for j in js if j["id"] in money}}, "4"))
    dots = {n["id"] for n in number_table.get("numbers", []) if n.get("leading_dot")}
    if dots & counted:
        out.append(diag("ITEM.AMOUNT.LEADING_DOT_COUNTED", "claim", {"ids": sorted(dots & counted)}, "4"))
    if reading.get("earlier_claim_quote"):
        out.append(diag("CLAIM.EARLIER_CLAIM_MENTIONED", "earlier_claim_quote", {"quote": reading["earlier_claim_quote"]}, "4"))
    return out
