"""Steps 4-5: checks run inside submit_line_items, plus the step-2 record checks that need the number table.

check_submission() splits findings into
- returnable errors (ReceiptError): the model can fix them by changing its answer;
- record diagnostics: data properties or review hints; never sent back (sending them back invites fitting).
Which side each code is on is fixed in diagnostics_catalog.yaml (`handling`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from config import CATALOG, RULES, TAX, TAXONOMY
from gate import diag
from schemas import (COUNTED_STATUSES, MONEY_KINDS, ClaimSummary, Diagnostic, EvidenceType, Kind, NumberJudgment,
                     ObjectType, ParseResult, ReceiptError, Status, Submission)

TOL = Decimal(str(RULES["tolerances"]["amount_abs"]))
TAX_TOL = Decimal(str(RULES["tolerances"]["tax_abs"]))
CODES = TAXONOMY["codes"]
RATE_CUES = RULES["number_features"]["rate_cues"]
UNIT_CONFLICT = set(RULES["number_features"]["money_unit_conflicts"])
PPG_BASIS = {EvidenceType.PPG_NOTIFIED, EvidenceType.PPG_APPROVED, EvidenceType.PPG_LIST}
DOC_BASIS = {EvidenceType.CONTRACT_OR_TARIFF, EvidenceType.SHIPPING_DOCUMENT}


@dataclass
class Ctx:
    record_id: str
    text: str                 # redacted text
    parse: ParseResult
    delta: Decimal
    origin_state: str | None
    destination_state: str | None
    event_date: datetime


def category(code: str) -> str:
    return CODES[code]["category"] if code in CODES else "UNKNOWN"


def phrase_found(phrase: str, text: str) -> bool:
    """Exact match first; then tolerate whitespace and case differences."""
    if not phrase:
        return False
    if phrase in text:
        return True
    squash = lambda s: re.sub(r"\s+", "", s).upper()  # noqa: E731
    return squash(phrase) in squash(text)


def digits(x) -> str:
    return re.sub(r"\D", "", str(x))


# --------------------------------------------------------------------------------------------- step-2 record checks

def step2_diagnostics(ctx: Ctx) -> list[Diagnostic]:
    d: list[Diagnostic] = []
    t, p = ctx.text, ctx.parse
    if t and not re.search(r"[A-Za-z]", re.sub(r"\[(?:PERSON|EMAIL)_\d+\]", "", t)) and (p.numbers or p.unrecognized):
        d.append(diag("REC.TEXT.NUMBERS_ONLY", ObjectType.RECORD, "text", {"numbers": [n.raw for n in p.numbers]}, "2"))
    if t and re.search(r"[A-Za-z]", t) and not p.numbers and not p.unrecognized:
        d.append(diag("REC.TEXT.NO_NUMBER", ObjectType.RECORD, "text", {}, "2"))
    for u in p.unrecognized:
        d.append(diag("NUM.PARSE.UNRECOGNIZED_REGION", ObjectType.NUMBER, f"unrecognized/{u.id}",
                      {"region_id": u.id, "raw": u.raw, "span": list(u.span)}, "2"))
    for n in p.numbers:
        path = f"numbers/{n.id}"
        if n.space_merged:
            d.append(diag("NUM.PARSE.SPACE_MERGED", ObjectType.NUMBER, path, {"id": n.id, "raw": n.raw, "value": str(n.value)}, "2"))
        if n.decimals not in (0, 1, 2):
            d.append(diag("NUM.PARSE.UNUSUAL_DECIMALS", ObjectType.NUMBER, path, {"id": n.id, "raw": n.raw, "decimals": n.decimals}, "2"))
        if n.leading_dot:
            d.append(diag("NUM.PARSE.LEADING_DOT", ObjectType.NUMBER, path, {"id": n.id, "raw": n.raw}, "2"))
        if n.minus_before == "adjacent":
            d.append(diag("NUM.PARSE.MINUS_ADJACENT", ObjectType.NUMBER, path, {"id": n.id, "raw": n.raw}, "2"))
    latest = None
    for dt in p.dates:
        if not dt.has_year:
            continue
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y", "%m/%d/%y"):
            try:
                v = datetime.strptime(dt.raw, fmt)
                latest = max(latest or v, v)
                break
            except ValueError:
                continue
    if latest is not None:
        days = (latest - ctx.event_date.replace(tzinfo=None)).total_seconds() / 86400
        if days > RULES["tolerances"]["text_date_after_event_days"]:
            d.append(diag("REC.TEXT.DATE_AFTER_EVENT", ObjectType.RECORD, "text",
                          {"latest_text_date": latest.isoformat(), "event_date": ctx.event_date.isoformat(),
                           "days_after": round(days, 1)}, "2"))
    return d


# --------------------------------------------------------------------------------------------- tax

def tax_rate(ctx: Ctx, codes: set[str]) -> tuple[Decimal | None, str | None]:
    prov = ctx.destination_state if TAX["province_basis"] == "destination" else ctx.origin_state
    rule = TAX["provinces"].get(prov or "")
    if rule is None or codes & {"TAX.PST"}:
        return None, prov
    if "hst" in rule:
        return Decimal(str(rule["hst"])), prov
    return Decimal(str(rule["gst"])), prov


# --------------------------------------------------------------------------------------------- submission checks

def _err(code: str, obj: ObjectType, path: str, evidence: dict, fixes: list[str]) -> ReceiptError:
    assert CATALOG[code]["handling"] == "return", code
    return ReceiptError(code=code, object_type=obj, path=path, evidence=evidence, allowed_fixes=fixes)


def check_submission(ctx: Ctx, sub: Submission) -> tuple[list[ReceiptError], list[Diagnostic], ClaimSummary | None]:
    errs: list[ReceiptError] = []
    rec: list[Diagnostic] = []
    table = {n.id: n for n in ctx.parse.numbers}
    regions = {u.id: u for u in ctx.parse.unrecognized}
    values: dict[str, Decimal] = {i: n.value for i, n in table.items()}

    judged: list[NumberJudgment] = list(sub.numbers)
    read_ids = set()
    for r in sub.unrecognized_reads:
        path = f"content/unrecognized_reads/{r.region_id}"
        if r.region_id not in regions:
            errs.append(_err("NUM.REF.UNKNOWN_ID", ObjectType.NUMBER, path, {"given": r.region_id, "valid_ids": list(regions)},
                             ["use an existing unrecognized region id"]))
            continue
        read_ids.add(r.region_id)
        if r.contains_number:
            if r.value is None or digits(r.value) != digits(regions[r.region_id].raw):
                errs.append(_err("NUM.READ.UNRECOGNIZED_MISMATCH", ObjectType.NUMBER, path,
                                 {"region_id": r.region_id, "raw": regions[r.region_id].raw,
                                  "raw_digits": digits(regions[r.region_id].raw), "given_digits": digits(r.value)},
                                 ["give a value whose digits are exactly the digits in the region",
                                  "or set contains_number=false"]))
            elif r.as_number is None or r.as_number.id != r.region_id:
                errs.append(_err("NUM.REF.UNKNOWN_ID", ObjectType.NUMBER, path, {"given": getattr(r.as_number, "id", None)},
                                 ["as_number.id must equal region_id"]))
            else:
                values[r.region_id] = r.value
                judged.append(r.as_number)
    unread = [u for u in regions if u not in read_ids]
    if unread:
        errs.append(_err("NUM.READ.UNRECOGNIZED_UNREAD", ObjectType.NUMBER, "content/unrecognized_reads",
                         {"region_ids": unread}, ["add one read per unrecognized region"]))

    seen: dict[str, int] = {}
    for j in judged:
        seen[j.id] = seen.get(j.id, 0) + 1
    for j in sub.numbers:
        if j.id not in table:
            errs.append(_err("NUM.REF.UNKNOWN_ID", ObjectType.NUMBER, f"content/numbers/{j.id}",
                             {"given": j.id, "valid_ids": list(table)}, ["use an id from the number table", "remove the entry"]))
    for i, c in seen.items():
        if c > 1:
            errs.append(_err("NUM.REF.DUPLICATE_ID", ObjectType.NUMBER, f"content/numbers/{i}", {"id": i, "count": c},
                             ["keep exactly one judgment per id"]))
    missing = [i for i in table if i not in seen]
    if missing:
        errs.append(_err("NUM.REF.MISSING_ID", ObjectType.NUMBER, "content/numbers", {"missing_ids": missing},
                         ["add a judgment for every id; use kind REFERENCE/QUANTITY and status NONE for non-money numbers"]))

    by_id = {j.id: j for j in judged if j.id in values}
    for j in by_id.values():
        path = f"content/numbers/{j.id}"
        tok = table.get(j.id)
        if j.kind not in MONEY_KINDS and j.status != Status.NONE:
            errs.append(_err("NUM.JUDGMENT.STATUS_ON_NON_MONEY", ObjectType.NUMBER, path,
                             {"id": j.id, "kind": j.kind.value, "status": j.status.value},
                             ["set status NONE", "or change kind if the number is money"]))
        if tok and j.kind in MONEY_KINDS and tok.unit_hint in UNIT_CONFLICT:
            errs.append(_err("NUM.JUDGMENT.UNIT_CONFLICT", ObjectType.NUMBER, path,
                             {"id": j.id, "kind": j.kind.value, "unit_hint": tok.unit_hint},
                             ["change kind (QUANTITY / RATE)", "or report_uncertainty if the unit word does not belong to this number"]))
        if not phrase_found(j.evidence_phrase, ctx.text):
            errs.append(_err("NUM.JUDGMENT.EVIDENCE_NOT_FOUND", ObjectType.NUMBER, path, {"id": j.id, "phrase": j.evidence_phrase},
                             ["quote a phrase that appears verbatim in redacted_text"]))
        for c in j.charge_codes:
            if c not in CODES:
                errs.append(_err("ITEM.CODE.UNKNOWN", ObjectType.LINE_ITEM, path, {"path": path, "code": c},
                                 ["use a code from the taxonomy", "or OTHER with other_phrase"]))
        if "OTHER" in j.charge_codes and not (j.other_phrase and phrase_found(j.other_phrase, ctx.text)):
            errs.append(_err("ITEM.CODE.OTHER_PHRASE_MISSING", ObjectType.LINE_ITEM, path, {"path": path, "other_phrase": j.other_phrase},
                             ["set other_phrase to the verbatim phrase naming the charge"]))

    counted = [j for j in by_id.values() if j.status in COUNTED_STATUSES and j.kind in MONEY_KINDS and j.kind != Kind.TOTAL]
    refs: dict[str, int] = {}
    for k, li in enumerate(sub.line_items):
        path = f"content/line_items/{k}"
        if li.amount_ref is not None:
            refs[li.amount_ref] = refs.get(li.amount_ref, 0) + 1
            j = by_id.get(li.amount_ref)
            reason = None
            if j is None:
                reason = "unknown id"
            elif j.kind not in MONEY_KINDS or j.kind == Kind.TOTAL:
                reason = f"kind {j.kind.value} is not an item amount"
            elif j.status not in COUNTED_STATUSES:
                reason = f"status {j.status.value} is not counted in this dispute"
            elif refs[li.amount_ref] > 1:
                reason = "amount already used by another line item"
            if reason:
                errs.append(_err("ITEM.REF.INVALID", ObjectType.LINE_ITEM, path, {"path": path, "amount_ref": li.amount_ref, "reason": reason},
                                 ["reference a CLAIMED/UNPAID money number", "or change that number's status"]))
        else:
            if not li.charge_codes:
                errs.append(_err("ITEM.REF.INVALID", ObjectType.LINE_ITEM, path, {"path": path, "amount_ref": None, "reason": "no amount and no charge code"},
                                 ["give charge_codes for a charge named without an amount", "or remove the item"]))
            for c in li.charge_codes:
                if c not in CODES:
                    errs.append(_err("ITEM.CODE.UNKNOWN", ObjectType.LINE_ITEM, path, {"path": path, "code": c}, ["use a code from the taxonomy"]))
        for field in ("carrier_stated_reason", "carrier_stated_basis"):
            v = getattr(li, field)
            if v is not None and not phrase_found(v, ctx.text):
                errs.append(_err("ITEM.PHRASE.NOT_FOUND", ObjectType.LINE_ITEM, path, {"path": path, "field": field, "phrase": v},
                                 ["quote verbatim from redacted_text", "or set the field to null"]))
        if li.carrier_stated_basis_type != EvidenceType.NONE and not li.carrier_stated_basis:
            errs.append(_err("ITEM.PHRASE.NOT_FOUND", ObjectType.LINE_ITEM, path, {"path": path, "field": "carrier_stated_basis", "phrase": None},
                             ["quote the basis phrase", "or set carrier_stated_basis_type NONE"]))
    not_itemized = [j.id for j in counted if j.id not in refs]
    if not_itemized:
        errs.append(_err("ITEM.REF.CLAIM_NOT_ITEMIZED", ObjectType.LINE_ITEM, "content/line_items", {"ids": not_itemized},
                         ["add a line item for each CLAIMED/UNPAID amount", "or change the number's status"]))

    if any(e.code.startswith("NUM.REF") for e in errs):
        return errs, rec, None     # cannot reconcile on broken references

    # ---- reconciliation (single rule) ----
    delta = ctx.delta
    anchor = abs(delta)
    claimed_sum = sum((values[j.id] for j in counted), Decimal("0"))
    tax_items_no_amt = [(k, li) for k, li in enumerate(sub.line_items) if li.amount_ref is None and any(category(c) == "TAX" for c in li.charge_codes)]
    tax_nums = [j for j in counted if j.kind == Kind.TAX_AMOUNT]
    base = sum((values[j.id] for j in counted if j.kind != Kind.TAX_AMOUNT), Decimal("0"))
    all_tax_codes = {c for li in sub.line_items for c in li.charge_codes} | {c for j in counted for c in j.charge_codes}
    rate, prov = tax_rate(ctx, all_tax_codes)
    expected_tax = (base * rate).quantize(Decimal("0.01")) if rate is not None else None
    totals = [j for j in by_id.values() if j.kind == Kind.TOTAL]
    implied = None
    reconciles: bool | None
    if delta == 0:
        reconciles = None
    elif abs(claimed_sum - anchor) <= TOL:
        reconciles = True
        if tax_items_no_amt:
            implied = Decimal("0.00")
    elif tax_items_no_amt and expected_tax is not None and abs((anchor - claimed_sum) - expected_tax) <= TAX_TOL:
        reconciles = True
        implied = anchor - claimed_sum
    else:
        reconciles = False
    # data pattern: Delta counts the stated total twice (items + total)
    twice = [t for t in totals if reconciles is False and abs(claimed_sum + values[t.id] - anchor) <= TOL]
    if twice:
        rec.append(diag("CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE", ObjectType.CLAIM, "claim",
                        {"claimed_sum": str(claimed_sum), "total": str(values[twice[0].id]), "delta": str(delta)}, "4-5"))
    elif reconciles is False:
        errs.append(_err("CLAIM.RECON.SUM_MISMATCH", ObjectType.CLAIM, "claim",
                         {"counted_ids": [j.id for j in counted], "claimed_sum": str(claimed_sum), "delta": str(delta),
                          "difference": str(anchor - claimed_sum)},
                         ["re-read kind/status of the counted numbers and of the numbers you did not count",
                          "if your reading is right, resubmit it unchanged and call report_uncertainty"]))
    for t in totals:
        target = claimed_sum + (implied if implied is not None else Decimal("0"))
        alt = claimed_sum + expected_tax if (tax_items_no_amt and expected_tax is not None) else None
        if abs(values[t.id] - target) > TAX_TOL and not (alt is not None and abs(values[t.id] - alt) <= TAX_TOL):
            rec.append(diag("CLAIM.RECON.TOTAL_MISMATCH", ObjectType.CLAIM, f"numbers/{t.id}",
                            {"total_id": t.id, "total": str(values[t.id]), "claimed_sum": str(claimed_sum),
                             "implied_tax": str(implied) if implied is not None else None}, "4-5"))

    # ---- tax ----
    for j in tax_nums:
        path = f"numbers/{j.id}"
        if rate is None:
            rec.append(diag("ITEM.TAX.NO_RULE", ObjectType.LINE_ITEM, path, {"path": path, "province": prov, "tax_codes": j.charge_codes}, "4-5"))
        elif abs(values[j.id] - expected_tax) > TAX_TOL:
            rec.append(diag("ITEM.TAX.RATE_MISMATCH", ObjectType.LINE_ITEM, path,
                            {"path": path, "base": str(base), "tax": str(values[j.id]),
                             "implied_rate": str((values[j.id] / base).quantize(Decimal("0.0001"))) if base else None,
                             "expected_rate": str(rate), "province": prov}, "4-5"))
    for k, li in tax_items_no_amt:
        path = f"content/line_items/{k}"
        if rate is None:
            rec.append(diag("ITEM.TAX.NO_RULE", ObjectType.LINE_ITEM, path, {"path": path, "province": prov, "tax_codes": li.charge_codes}, "4-5"))
        rec.append(diag("ITEM.TAX.NO_AMOUNT", ObjectType.LINE_ITEM, path,
                        {"path": path, "implied_tax": str(implied) if implied is not None else None,
                         "expected_tax": str(expected_tax) if expected_tax is not None else None, "province": prov}, "4-5"))

    # ---- numbers ----
    for j in by_id.values():
        tok = table.get(j.id)
        rate_cue = tok is not None and (tok.prev_symbol in RATE_CUES["prev_symbols"] or tok.prev_word in RATE_CUES["prev_words"]
                                        or tok.next_word in RATE_CUES["next_words"])
        if tok and tok.has_dollar and (j.kind not in MONEY_KINDS or j.status == Status.NONE) and not (j.kind == Kind.RATE and rate_cue):
            rec.append(diag("NUM.JUDGMENT.DOLLAR_EXCLUDED", ObjectType.NUMBER, f"numbers/{j.id}",
                            {"id": j.id, "raw": tok.raw, "kind": j.kind.value, "status": j.status.value}, "4-5"))
        if tok and tok.space_merged and j in counted:
            rec.append(diag("NUM.JUDGMENT.SPACE_MERGED_IN_CLAIM", ObjectType.NUMBER, f"numbers/{j.id}",
                            {"id": j.id, "raw": tok.raw, "value": str(tok.value)}, "4-5"))

    # ---- line items ----
    for k, li in enumerate(sub.line_items):
        path = f"content/line_items/{k}"
        j = by_id.get(li.amount_ref) if li.amount_ref else None
        codes = j.charge_codes if j else li.charge_codes
        if "OTHER" in codes:
            rec.append(diag("ITEM.CODE.OTHER", ObjectType.LINE_ITEM, path, {"path": path, "other_phrase": j.other_phrase if j else None}, "4-5"))
        if any(category(c) == "PENDING" for c in codes):
            rec.append(diag("ITEM.CODE.PENDING_MEANING", ObjectType.LINE_ITEM, path, {"path": path, "code": [c for c in codes if category(c) == "PENDING"]}, "4-5"))
        if len(codes) > 1:
            rec.append(diag("ITEM.CODE.COMBINED", ObjectType.LINE_ITEM, path, {"path": path, "codes": codes, "amount": str(values[j.id]) if j else None}, "4-5"))
        if j is None and not any(category(c) == "TAX" for c in codes):
            rec.append(diag("ITEM.AMOUNT.MISSING", ObjectType.LINE_ITEM, path, {"path": path, "codes": codes}, "4-5"))
        if j is not None and not codes:
            rec.append(diag("ITEM.AMOUNT.UNNAMED", ObjectType.LINE_ITEM, path, {"path": path, "amount_ref": j.id, "amount": str(values[j.id])}, "4-5"))
        if li.carrier_stated_basis_type in PPG_BASIS:
            rec.append(diag("ITEM.BASIS.PPG_CLAIMED", ObjectType.LINE_ITEM, path, {"path": path, "basis_type": li.carrier_stated_basis_type.value, "basis": li.carrier_stated_basis}, "4-5"))
        if li.carrier_stated_basis_type in DOC_BASIS:
            rec.append(diag("ITEM.BASIS.CONTRACT_CLAIMED", ObjectType.LINE_ITEM, path, {"path": path, "basis_type": li.carrier_stated_basis_type.value, "basis": li.carrier_stated_basis}, "4-5"))
        if any(category(c) == "RATE_CORRECTION" for c in codes):
            rec.append(diag("ITEM.NATURE.RATE_CORRECTION", ObjectType.LINE_ITEM, path, {"path": path, "code": codes}, "4-5"))
        if j is not None and li.quantity_ref and li.unit_rate_ref and li.quantity_ref in values and li.unit_rate_ref in values:
            q, r = values[li.quantity_ref], values[li.unit_rate_ref]
            if abs(q * r - values[j.id]) > TOL:
                rec.append(diag("ITEM.ARITH.QTY_RATE_MISMATCH", ObjectType.LINE_ITEM, path,
                                {"path": path, "quantity": str(q), "unit_rate": str(r), "amount": str(values[j.id])}, "4-5"))

    claim = ClaimSummary(counted_ids=[j.id for j in counted], claimed_sum=claimed_sum, implied_tax=implied, delta=delta,
                         reconciles=reconciles, totals=[{"id": t.id, "value": str(values[t.id])} for t in totals],
                         history_relations=[])
    return errs, rec, claim
