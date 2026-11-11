"""R1b: duplicate flags at two levels, within one batch (decisions 5.1-5.3). Flags only; nothing is merged or judged.

- ROW level: records identical in everything except PK / row number (same shipment, carrier invoice, normalised text,
  Delta and Event Date). Every copy is its own record. The first copy (lowest row number, schema v1) gets an info
  hint "N later copies"; every later copy gets DUP.ROW.COPY (attention) pointing at the first.
- INVOICE level: within one carrier invoice, after setting aside ROW copies, the same charge code counted
  (CLAIMED/UNPAID) a second time, in the same dispute or in a later one. The first occurrence is not flagged; every
  later one gets DUP.INVOICE.SAME_CHARGE (attention) pointing at the earlier line item. Tax codes are skipped: a tax
  follows its charge and repeats legitimately with it (decision log D-27).
A flag can be cleared only by evidence named in rules.yaml `duplicates.clear_rules` (empty in this version: only a
reviewer clears). Lower levels are computed first, so a ROW copy is never counted again at INVOICE level (5.2).
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime

from freight_lineitems.checks import diag
from freight_lineitems.config import RULES, category
from freight_lineitems.disposition import flags_from, recommend
from freight_lineitems.schemas import Diagnostic
from freight_lineitems.textprep import normalize

COUNTED = {"CLAIMED", "UNPAID"}


def content_key(rec) -> str:
    parts = [rec.shipment_key or "", rec.carrier_invoice or "", normalize(rec.text_raw), str(rec.delta),
             rec.event_date.isoformat() if rec.event_date else ""]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


def row_level(records: list) -> dict[str, list[Diagnostic]]:
    groups: dict[str, list] = defaultdict(list)
    for r in records:
        groups[content_key(r)].append(r)
    out: dict[str, list[Diagnostic]] = defaultdict(list)
    for key, rs in groups.items():
        if len(rs) < 2:
            continue
        rs = sorted(rs, key=lambda r: r.row_number)
        first = rs[0]
        out[first.record_id].append(diag("DUP.ROW.HAS_LATER_COPIES", "record", {
            "content_key": key, "n_later_copies": len(rs) - 1, "later_record_ids": [r.record_id for r in rs[1:]]}, "5"))
        for rank, r in enumerate(rs[1:], 2):
            out[r.record_id].append(diag("DUP.ROW.COPY", "record", {
                "content_key": key, "copy_rank": rank, "points_to_record_id": first.record_id,
                "differs_only_in": "PK / row number"}, "5"))
    return out


def _items(result: dict) -> list[tuple[int, str, str | None]]:
    """(line item index, charge code, amount raw) for counted items of a reading that passed the mandatory checks."""
    f = result["facts"]
    if f["parse_status"] != "PASSED_CHECKS" or not f["reading"]:
        return []
    reading = f["reading"]
    nums = {j["id"]: j for j in reading["numbers"]} | {r["region_id"]: r["as_number"] for r in reading.get("unrecognized_reads", [])}
    raw = {n["id"]: n["raw"] for n in f["number_table"]["numbers"]}
    out = []
    for k, li in enumerate(reading["line_items"]):
        j = nums.get(li["amount_ref"]) if li["amount_ref"] else None
        if j is not None and j["status"] not in COUNTED:
            continue
        for c in (j["charge_codes"] if j else li["charge_codes"]):
            if category(c) == "TAX":
                continue
            key = c
            if c == "OTHER":   # audit M5: two different 'other' charges are not the same charge
                label = (j or {}).get("other_phrase") or li.get("raw_charge_label") or ""
                key = "OTHER:" + " ".join(label.upper().split())
            out.append((k, key, raw.get(li["amount_ref"]) if li["amount_ref"] else None))
    return out


def invoice_level(records: list, results: dict[str, dict], row_copies: set[str]) -> dict[str, list[Diagnostic]]:
    by_inv: dict[str, list] = defaultdict(list)
    for r in records:
        if r.record_id not in row_copies and r.record_id in results:
            by_inv[r.invoice_key].append(r)
    out: dict[str, list[Diagnostic]] = defaultdict(list)
    for inv, rs in by_inv.items():
        rs = sorted(rs, key=lambda r: (r.event_date is None, r.event_date or datetime.min, r.row_number))  # audit M2
        seen: dict[str, tuple[str, int, str | None]] = {}
        for r in rs:
            if results[r.record_id]["facts"]["parse_status"] != "PASSED_CHECKS":   # audit M5: say it was not compared
                out[r.record_id].append(diag("DUP.INVOICE.NOT_CHECKED", "record", {
                    "reason": "reading did not pass the mandatory checks", "parse_status": results[r.record_id]["facts"]["parse_status"]}, "5"))
                continue
            for k, code, amt in _items(results[r.record_id]):
                if code in seen:
                    first_rid, first_k, first_amt = seen[code]
                    out[r.record_id].append(diag("DUP.INVOICE.SAME_CHARGE", f"line_items/{k}", {
                        "charge_code": code, "amount": amt, "points_to_record_id": first_rid,
                        "points_to_line_item": first_k, "earlier_amount": first_amt,
                        "same_dispute": first_rid == r.record_id}, "5"))
                else:
                    seen[code] = (r.record_id, k, amt)
    return out


def apply(records: list, results: list[dict]) -> list[dict]:
    """Add duplicate diagnostics to each result and recompute its flags and recommendation (rules only)."""
    by_id = {res["record_id"]: res for res in results}
    batch = [r for r in records if r.record_id in by_id]
    row = row_level(batch)
    copies = {rid for rid, ds in row.items() if any(d.code == "DUP.ROW.COPY" for d in ds)}
    inv = invoice_level(batch, by_id, copies)
    clear_rules = (RULES.get("duplicates") or {}).get("clear_rules") or []
    for rid, res in by_id.items():
        new = row.get(rid, []) + inv.get(rid, [])
        if not new:
            continue
        diags = [Diagnostic(**d) for d in res["judgment"]["diagnostics"]] + new
        flags = flags_from(diags)
        res["judgment"] = {"flags": flags, **recommend(flags), "diagnostics": [d.model_dump() for d in diags],
                           "duplicate_clear_rules_applied": clear_rules}
    return results
