"""Order copies within one batch (task 14 / T12-02, proposal C4).

Rows with the same shipment, Event Date and normalised text are one explanation: the model reads it once, and the
explanation keeps every source row (row numbers, PKs) and the number of orders (distinct non-empty PKs).

- Every copy on its own PK is the normal structure (several orders on one truck, client answer of 2026-11-13): no
  flag, only the order count.
- A copy whose PK is empty or repeats another copy's PK (compared after `normalize_pk`: case, spaces, leading zeros;
  P-35) is not explained by that structure: the explanation gets
  SHIP.COPY.SAME_OR_NO_PK (attention, the level the earlier DUP.ROW.COPY had).
- Text repeated on another Event Date is a separate explanation; the shipment roll-up (rollup.py) decides how it
  relates to the earlier one. The earlier per-invoice check DUP.INVOICE.SAME_CHARGE is replaced by the roll-up's
  SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE.
A flag can be cleared only by evidence named in rules.yaml `duplicates.clear_rules` (empty: only a reviewer clears).
"""

from __future__ import annotations

import hashlib
import re

from freight_lineitems.checks import diag
from freight_lineitems.config import RULES
from freight_lineitems.disposition import flags_from, recommend
from freight_lineitems.records import explanation_key, group_explanations
from freight_lineitems.schemas import Diagnostic


def normalize_pk(pk: str | None) -> str:
    """PK as compared for copies (pending P-35, decided 2026-11-15): case, spaces and leading zeros of every digit
    run are ignored, so 'ORD-00123' and 'ord-123' are the same order. Empty or missing -> ''."""
    if pk is None:
        return ""
    s = re.sub(r"\s+", "", str(pk)).upper()
    return re.sub(r"\d+", lambda m: m.group(0).lstrip("0") or "0", s)


def content_key(rec) -> str:
    """Stable hash of the explanation key (shipment, Event Date, normalised text); no PK, no Delta."""
    return hashlib.sha256("\x1f".join(explanation_key(rec)).encode()).hexdigest()[:16]


def source_rows(group: list) -> dict:
    """The facts every explanation carries about its rows: row numbers, record ids, PKs and the order count."""
    pks = [normalize_pk(r.pk) for r in group]
    return {"source_rows": [{"record_id": r.record_id, "row_number": r.row_number, "pk": r.pk} for r in group],
            "n_rows": len(group), "n_orders": len({p for p in pks if p})}


def copy_diagnostics(group: list) -> list[Diagnostic]:
    """SHIP.COPY.SAME_OR_NO_PK when an explanation has more than one row and some copy has no PK or repeats a PK."""
    if len(group) < 2:
        return []
    pks = [normalize_pk(r.pk) for r in group]
    empty = [r.record_id for r, p in zip(group, pks) if not p]
    seen, repeated = set(), []
    for r, p in zip(group, pks):
        if p and p in seen:
            repeated.append(r.record_id)
        seen.add(p)
    if not empty and not repeated:
        return []
    return [diag("SHIP.COPY.SAME_OR_NO_PK", "record", {
        "content_key": content_key(group[0]), "n_rows": len(group), "n_distinct_pks": len({p for p in pks if p}),
        "rows_without_pk": empty, "rows_repeating_a_pk": repeated}, "5")]


def apply(records: list, results: list[dict]) -> list[dict]:
    """Attach the source-row facts and copy flags to each explanation's result and recompute its flags and
    recommendation (rules only). `results` hold one result per explanation, keyed by the representative's record id
    (the first row of the group); rows of the batch without a result are copies of some representative."""
    by_id = {res["record_id"]: res for res in results}
    clear_rules = (RULES.get("duplicates") or {}).get("clear_rules") or []
    for group in group_explanations([r for r in records]):
        res = by_id.get(group[0].record_id)
        if res is None:
            continue
        res["facts"] |= source_rows(group)
        new = copy_diagnostics(group)
        if not new:
            continue
        diags = [Diagnostic(**d) for d in res["judgment"]["diagnostics"]] + new
        flags = flags_from(diags)
        res["judgment"] = {"flags": flags, **recommend(flags), "diagnostics": [d.model_dump() for d in diags],
                           "duplicate_clear_rules_applied": clear_rules}
    return results
