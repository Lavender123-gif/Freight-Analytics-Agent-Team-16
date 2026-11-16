"""Steps 2 and 4: record checks on the number table, and the mandatory checks inside submit_line_items (P4a).

Two kinds of findings:
- RepairError: a mandatory check failed; the model is told what and where, and may resubmit. These are facts about
  the text and the submission only. `Ctx` deliberately has no Delta, so nothing here can leak it (decision 3.1).
- Diagnostic: stored for the reviewer and turned into flags by rules.yaml. Never sent back to the model.

There is no comparison with the Excel Delta column anywhere at run time (task 14 C1: Delta is the client's own
estimate, used only as a baseline in evaluation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from freight_lineitems.config import CODES, RULES, TAX, category
from freight_lineitems.claim import is_counted, signed_amount, status_counted
from freight_lineitems.schemas import (ITEM_KINDS, MONEY_KINDS, BasisType, Diagnostic, Kind, NumberJudgment, ParseResult,
                                       RepairError, Status, Submission)

TOL = Decimal(str(RULES["tolerances"]["amount_abs"]))
TAX_TOL = Decimal(str(RULES["tolerances"]["tax_abs"]))
REL_TOL = Decimal(str(RULES["tolerances"]["relation_abs"]))
UNIT_CONFLICT = set(RULES["number_features"]["money_unit_conflicts"])
CUES = RULES["number_features"]["arithmetic_cues"]
QR = RULES["number_features"]["quantity_rate"]
PPG_BASIS = {BasisType.PPG_NOTIFIED, BasisType.PPG_APPROVED, BasisType.PPG_LIST}
DOC_BASIS = {BasisType.CONTRACT_OR_TARIFF, BasisType.SHIPPING_DOCUMENT}
PLACEHOLDER_RE = re.compile(r"\[(?:PERSON|EMAIL|PHONE)_\d+\]")


@dataclass
class Ctx:
    """What the checks may see. No Delta, no amounts from the Excel row."""
    record_id: str
    text: str                 # redacted text
    parse: ParseResult
    origin_state: str | None
    destination_state: str | None
    event_date: datetime | None


@dataclass
class ClaimCalc:
    """Code's arithmetic on an accepted-format submission. Delta is not involved."""
    counted_ids: list[str]
    signed_sum: Decimal
    base_sum: Decimal               # counted amounts that are not tax
    tax_items_without_amount: int
    expected_tax: Decimal | None    # base x table rate, when a tax is named without an amount
    totals: dict[str, Decimal]


def diag(code: str, path: str, evidence: dict, step: str, origin: str = "CODE_RULE") -> Diagnostic:
    return Diagnostic(code=code, path=path, evidence=evidence, step=step, origin=origin)


def phrase_found(phrase: str | None, text: str) -> bool:
    """Exact match first; then tolerate whitespace and case differences."""
    if not phrase:
        return False
    if phrase in text:
        return True
    squash = lambda s: re.sub(r"\s+", "", s).upper()  # noqa: E731
    return squash(phrase) in squash(text)


def exclusion_basis_category(phrase: str | None) -> str | None:
    """Which accepted 'not counted' category (rules.yaml exclusion_basis.categories) the phrase names, or None.
    Whole-word match on the upper-cased phrase; symbols such as '@' match as substrings. Pending P-15 / audit M3:
    a phrase that merely occurs in the text but names no reason for leaving a '$' amount out is not a basis."""
    if not phrase:
        return None
    up = " ".join(phrase.upper().split())
    for cat, words in RULES["exclusion_basis"]["categories"].items():
        for w in words:
            w = str(w).upper()
            if (re.search(r"(?<![A-Z])" + re.escape(w) + r"(?![A-Z])", up) if re.search(r"[A-Z]", w) else w in up):
                return cat
    return None


CREDIT_WORDS = [str(w).upper() for w in RULES["exclusion_basis"]["categories"]["credit"]]


def credit_words_in(phrase: str | None) -> list[str]:
    """Credit words (rules.yaml exclusion_basis.categories.credit) found as whole words in a phrase, upper-cased."""
    up = " ".join((phrase or "").upper().split())
    return [w for w in CREDIT_WORDS if re.search(r"(?<![A-Z])" + re.escape(w) + r"(?![A-Z])", up)]


def credit_marks(text: str, span: tuple[int, int]) -> dict:
    """Sign marks written around one number (task 23, audit F-01). `minus`: a '-' directly before the number or its
    '$' ('-$20', '-20', '$-20'), with nothing in between. `parentheses`: the number, with its '$', is enclosed in
    '(' and ')' ('($45.00)', '( 45.00 )'). A dash after a charge name is usually a separator ('LIFTGATE-$69.00'), so
    `minus` alone is never treated as evidence against a positive reading; see check_submission."""
    a, b = span
    raw = text[a:b]
    m = re.search(r"\d", raw)
    lead = raw[: m.start()] if m else ""
    minus = text[:a].endswith("-") or lead.replace("$", "").replace(" ", "").endswith("-")
    opened = text[:a].rstrip().endswith("(") or lead.lstrip().startswith("(")
    closed = text[b:].lstrip().startswith(")") or raw.rstrip().endswith(")")
    return {"minus": minus, "parentheses": opened and closed}


def digits(x) -> str:
    return re.sub(r"\D", "", str(x))


def region_value(raw: str) -> Decimal:
    """Value of an unrecognized region, from its digits. The LAST '.' or ',' counts as a decimal point only if one or
    two digits follow it and nothing numeric comes after ('1.234,56' -> 1234.56, '12.50' -> 12.50, '1,234' -> 1234,
    'CV19' -> 19). Bug found by the audit (H1): only '.' was considered, so '1.234,56' became 123456."""
    core = re.sub(r"[^\d.,]", "", raw).strip(".,")
    m = re.search(r"[.,](\d{1,2})$", core)
    if m:
        whole = digits(core[: m.start()])
        return Decimal((whole or "0") + "." + m.group(1))
    return Decimal(digits(core) or "0")


# --------------------------------------------------------------------------------------------- quantity x rate (text only)

def quantity_rate_patterns(text: str, p: ParseResult) -> list[dict]:
    """Find 'N <unit> @ X' / 'N <unit> AT X EACH' in the text, independent of the model (user requirement b).
    For each pattern report the product and whether another number in the text equals it (a stated result)."""
    units = "|".join(re.escape(u) for u in QR["quantity_units"])
    out = []
    nums = p.numbers
    for qi, q in enumerate(nums):
        if q.has_dollar or q.value <= 0 or q.value > QR["max_quantity"]:
            continue
        after = text[q.span[1]: q.span[1] + QR["unit_window_chars"]]
        if not re.search(rf"(?<![A-Z])(?:{units})(?![A-Z])", after):
            continue
        for r in nums[qi + 1:]:
            if r.span[0] - q.span[1] > QR["rate_window_chars"]:
                break
            before = text[max(0, r.span[0] - 6): r.span[0]]
            is_rate = (r.prev_symbol == "@" or re.search(r"(?:@|\bAT)\s*\$?\s*$", before)
                       or (r.next_word or "") in QR["rate_next_words"])
            if not is_rate:
                continue
            product = q.value * r.value
            stated = [n.id for n in nums if n.id not in (q.id, r.id) and abs(n.value - product) <= REL_TOL]
            if abs(product - r.value) <= REL_TOL:      # quantity 1: per-unit and whole charge are the same amount
                stated = stated or [r.id]
            out.append({"quantity_id": q.id, "rate_id": r.id, "quantity": str(q.value), "rate": str(r.value),
                        "product": str(product), "stated_result_ids": stated})
            break
    return out


# --------------------------------------------------------------------------------------------- step-2 record checks

def step2_diagnostics(ctx: Ctx) -> list[Diagnostic]:
    d: list[Diagnostic] = []
    t, p = ctx.text, ctx.parse
    letters = re.search(r"[A-Za-z]", PLACEHOLDER_RE.sub("", t))
    if t and not letters and (p.numbers or p.unrecognized):
        d.append(diag("REC.TEXT.NUMBERS_ONLY", "text", {"numbers": [n.raw for n in p.numbers]}, "2"))
    if t and letters and not p.numbers and not p.unrecognized:
        d.append(diag("REC.TEXT.NO_NUMBER", "text", {}, "2"))
    for u in p.unrecognized:
        d.append(diag("NUM.PARSE.UNRECOGNIZED_REGION", f"unrecognized/{u.id}", {"region_id": u.id, "raw": u.raw}, "2"))
    for n in p.numbers:
        path = f"numbers/{n.id}"
        if n.space_merged:
            d.append(diag("NUM.PARSE.SPACE_MERGED", path, {"id": n.id, "raw": n.raw, "value": str(n.value)}, "2"))
        if n.decimals not in (0, 1, 2):
            d.append(diag("NUM.PARSE.UNUSUAL_DECIMALS", path, {"id": n.id, "raw": n.raw}, "2"))
        if n.leading_dot:
            d.append(diag("NUM.PARSE.LEADING_DOT", path, {"id": n.id, "raw": n.raw}, "2"))
        if n.minus_before == "adjacent":
            d.append(diag("NUM.PARSE.MINUS_ADJACENT", path, {"id": n.id, "raw": n.raw}, "2"))
    for pat in quantity_rate_patterns(t, p):
        if not pat["stated_result_ids"]:
            d.append(diag("ITEM.ARITH.QTY_RATE_NO_RESULT", f"numbers/{pat['rate_id']}", pat, "2"))
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
    if latest is not None and ctx.event_date is not None:
        days = (latest - ctx.event_date.replace(tzinfo=None)).total_seconds() / 86400
        if days > RULES["tolerances"]["text_date_after_event_days"]:
            d.append(diag("REC.TEXT.DATE_AFTER_EVENT", "text", {"latest_text_date": latest.isoformat(),
                                                                 "days_after": round(days, 1)}, "2"))
    return d


# --------------------------------------------------------------------------------------------- tax table

def tax_rate(ctx: Ctx, codes: set[str]) -> tuple[Decimal | None, str | None]:
    """Federal-level rate (GST or HST) for the configured province basis; None when no rule applies."""
    prov = ctx.destination_state if TAX["province_basis"] == "destination" else ctx.origin_state
    rule = TAX["provinces"].get(prov or "")
    if rule is None or "TAX.PST" in codes:
        return None, prov
    return Decimal(str(rule.get("hst", rule.get("gst")))), prov


# --------------------------------------------------------------------------------------------- submission checks

def _err(code: str, path: str, evidence: dict, fixes: list[str]) -> RepairError:
    return RepairError(code=code, path=path, evidence=evidence, allowed_fixes=fixes)


def check_submission(ctx: Ctx, sub: Submission) -> tuple[list[RepairError], list[Diagnostic], ClaimCalc | None]:
    """Mandatory checks (returned to the model) and reviewer diagnostics for one submission."""
    errs: list[RepairError] = []
    rec: list[Diagnostic] = []
    table = {n.id: n for n in ctx.parse.numbers}
    regions = {u.id: u for u in ctx.parse.unrecognized}
    values: dict[str, Decimal] = {i: n.value for i, n in table.items()}

    # ---- unrecognized regions: every region read digit for digit; no "there is no number here" option (decision 3.8)
    judged: list[NumberJudgment] = list(sub.numbers)
    read_ids: set[str] = set()
    for r in sub.unrecognized_reads:
        path = f"unrecognized_reads/{r.region_id}"
        if r.region_id not in regions:
            errs.append(_err("NUM.REF.UNKNOWN_ID", path, {"given": r.region_id, "valid_ids": list(regions)},
                             ["use an existing unrecognized region id"]))
            continue
        read_ids.add(r.region_id)
        if digits(r.digits_read) != digits(regions[r.region_id].raw) or not digits(r.digits_read):
            errs.append(_err("NUM.READ.UNRECOGNIZED_MISMATCH", path,
                             {"region_id": r.region_id, "raw": regions[r.region_id].raw, "given_digits": r.digits_read},
                             ["write every digit of the region, in order, exactly as written"]))
        elif r.as_number.id != r.region_id:
            errs.append(_err("NUM.REF.UNKNOWN_ID", path, {"given": r.as_number.id}, ["as_number.id must equal region_id"]))
        else:
            values[r.region_id] = region_value(regions[r.region_id].raw)
            rec.append(diag("NUM.READ.REGION_VALUE_DERIVED", f"unrecognized/{r.region_id}", {
                "region_id": r.region_id, "raw": regions[r.region_id].raw, "value_used": str(values[r.region_id])}, "4"))
            judged.append(r.as_number)
    unread = [u for u in regions if u not in read_ids]
    if unread:
        errs.append(_err("NUM.READ.UNRECOGNIZED_UNREAD", "unrecognized_reads", {"region_ids": unread},
                         ["add one read per unrecognized region"]))

    # ---- every number judged exactly once
    seen: dict[str, int] = {}
    for j in judged:
        seen[j.id] = seen.get(j.id, 0) + 1
    for j in sub.numbers:
        if j.id not in table:
            errs.append(_err("NUM.REF.UNKNOWN_ID", f"numbers/{j.id}", {"given": j.id, "valid_ids": list(table)},
                             ["use an id from the number table", "remove the entry"]))
    for i, c in seen.items():
        if c > 1:
            errs.append(_err("NUM.REF.DUPLICATE_ID", f"numbers/{i}", {"id": i, "count": c}, ["keep exactly one judgment per id"]))
    missing = [i for i in table if i not in seen]
    if missing:
        errs.append(_err("NUM.REF.MISSING_ID", "numbers", {"missing_ids": missing},
                         ["add a judgment for every id; use kind REFERENCE/QUANTITY and status NONE for non-money numbers"]))

    by_id = {j.id: j for j in judged if j.id in values}
    for j in by_id.values():
        path = f"numbers/{j.id}"
        tok = table.get(j.id)
        if j.kind not in MONEY_KINDS and j.status != Status.NONE:
            errs.append(_err("NUM.JUDGMENT.STATUS_ON_NON_MONEY", path, {"id": j.id, "kind": j.kind.value, "status": j.status.value},
                             ["set status NONE", "or change kind if the number is money"]))
        if tok and j.kind in MONEY_KINDS and tok.unit_hint in UNIT_CONFLICT:
            errs.append(_err("NUM.JUDGMENT.UNIT_CONFLICT", path, {"id": j.id, "kind": j.kind.value, "unit_word": tok.unit_hint},
                             ["change kind (QUANTITY / RATE)", "or report_uncertainty if the unit word belongs to another number"]))
        if not phrase_found(j.evidence_phrase, ctx.text):
            errs.append(_err("NUM.JUDGMENT.EVIDENCE_NOT_FOUND", path, {"id": j.id, "phrase": j.evidence_phrase},
                             ["quote a phrase that appears verbatim in redacted_text"]))
        for c in j.charge_codes:
            if c not in CODES:
                errs.append(_err("ITEM.CODE.UNKNOWN", path, {"code": c}, ["use a code from the taxonomy", "or OTHER with other_phrase"]))
        if "OTHER" in j.charge_codes and not phrase_found(j.other_phrase, ctx.text):
            errs.append(_err("ITEM.CODE.OTHER_PHRASE_MISSING", path, {"other_phrase": j.other_phrase},
                             ["set other_phrase to the verbatim phrase naming the charge"]))
        # decision 3.5: a '$' amount left out of the claim needs a source phrase that says why
        dollar = tok.has_dollar if tok else "$" in (regions[j.id].raw if j.id in regions else "")
        if dollar and j.kind != Kind.TOTAL and not is_counted(j.kind, j.status):
            if not phrase_found(j.exclusion_phrase, ctx.text):
                errs.append(_err("NUM.JUDGMENT.EXCLUSION_UNSUPPORTED", path, {"id": j.id, "exclusion_phrase": j.exclusion_phrase},
                                 ["quote the words in the text that show this amount is not part of this claim",
                                  "or count it (CLAIMED/UNPAID) if the text asks for it"]))
            else:
                cat = exclusion_basis_category(j.exclusion_phrase)
                rec.append(diag("NUM.JUDGMENT.DOLLAR_EXCLUDED", path, {"id": j.id, "raw": tok.raw if tok else regions[j.id].raw,
                                "kind": j.kind.value, "status": j.status.value, "exclusion_phrase": j.exclusion_phrase,
                                "basis_category": cat}, "4"))
                if cat is None:   # P-15: the quoted words name none of the accepted reasons (severity in rules.yaml)
                    rec.append(diag("NUM.JUDGMENT.EXCLUSION_BASIS_UNLISTED", path,
                                    {"id": j.id, "exclusion_phrase": j.exclusion_phrase}, "4"))
        if j.is_credit and j.kind not in ITEM_KINDS:
            errs.append(_err("NUM.JUDGMENT.CREDIT_ON_NON_ITEM", path, {"id": j.id, "kind": j.kind.value},
                             ["is_credit applies to CHARGE_AMOUNT / UNSPECIFIED_AMOUNT / TAX_AMOUNT only"]))
        # task 23 (audit F-01): the sign must have support in the text. Code checks the model's is_credit; it does not
        # derive the sign itself, because most dashes before amounts are separators ('PLACEMENT-[PERSON_1]-$69.00').
        span = tok.span if tok else (regions[j.id].span if j.id in regions else None)
        if span is not None:
            marks = credit_marks(ctx.text, span)
            words = credit_words_in(j.evidence_phrase)
            if j.is_credit and not (words or marks["parentheses"] or marks["minus"]):
                errs.append(_err("NUM.JUDGMENT.CREDIT_UNSUPPORTED", path,
                                 {"id": j.id, "evidence_phrase": j.evidence_phrase},
                                 ["set is_credit false: the text shows no credit for this amount (no credit word such as "
                                  "CREDIT or REFUND in evidence_phrase, no parentheses around it, no minus sign directly "
                                  "before it)",
                                  "or quote in evidence_phrase the words of the text that present it as a credit"]))
            elif not j.is_credit and (words or marks["parentheses"]) and j.kind in ITEM_KINDS and is_counted(j.kind, j.status):
                rec.append(diag("NUM.JUDGMENT.CREDIT_MARK_NOT_CREDIT", path, {
                    "id": j.id, "raw": tok.raw if tok else regions[j.id].raw, "credit_words": words,
                    "parentheses": marks["parentheses"], "evidence_phrase": j.evidence_phrase}, "4"))

    counted = [j for j in by_id.values() if is_counted(j.kind, j.status)]

    # ---- line items
    refs: dict[str, int] = {}
    for k, li in enumerate(sub.line_items):
        path = f"line_items/{k}"
        if li.amount_ref is not None:
            refs[li.amount_ref] = refs.get(li.amount_ref, 0) + 1
            j = by_id.get(li.amount_ref)
            reason = None
            if j is None:
                reason = "unknown id"
            elif j.kind not in ITEM_KINDS:
                reason = f"kind {j.kind.value} is not an item amount"
            elif not status_counted(j.status):
                reason = f"status {j.status.value} is not counted in this dispute"
            elif refs[li.amount_ref] > 1:
                reason = "amount already used by another line item"
            if reason:
                errs.append(_err("ITEM.REF.INVALID", path, {"amount_ref": li.amount_ref, "reason": reason},
                                 ["reference a CLAIMED/UNPAID amount", "or change that number's status"]))
            if li.charge_codes:
                errs.append(_err("ITEM.REF.INVALID", path, {"reason": "charge_codes must be empty when amount_ref is set"},
                                 ["put the codes on the number judgment"]))
        else:
            if not li.charge_codes:
                errs.append(_err("ITEM.REF.INVALID", path, {"amount_ref": None, "reason": "no amount and no charge code"},
                                 ["give charge_codes for a charge named without an amount", "or remove the item"]))
            for c in li.charge_codes:
                if c not in CODES:
                    errs.append(_err("ITEM.CODE.UNKNOWN", path, {"code": c}, ["use a code from the taxonomy"]))
        for field in ("raw_charge_label", "carrier_stated_reason", "carrier_stated_basis"):
            v = getattr(li, field)
            if v is not None and not phrase_found(v, ctx.text):
                errs.append(_err("ITEM.PHRASE.NOT_FOUND", path, {"field": field, "phrase": v},
                                 ["quote verbatim from redacted_text", "or set the field to null"]))
        if li.carrier_stated_basis_type != BasisType.NONE and not li.carrier_stated_basis:
            errs.append(_err("ITEM.PHRASE.NOT_FOUND", path, {"field": "carrier_stated_basis", "phrase": None},
                             ["quote the basis phrase", "or set carrier_stated_basis_type NONE"]))
    not_itemized = [j.id for j in counted if j.id not in refs]
    if not_itemized:
        errs.append(_err("ITEM.REF.CLAIM_NOT_ITEMIZED", "line_items", {"ids": not_itemized},
                         ["add a line item for each CLAIMED/UNPAID amount", "or change the number's status"]))

    # ---- arithmetic relations: ids must exist (mandatory); whether they hold is recomputed every time (decision 3.3)
    for k, rel in enumerate(sub.relations):
        ids = rel.operand_ids + ([rel.result_id] if rel.result_id else [])
        bad = [i for i in ids if i not in values]
        if bad or not rel.operand_ids:
            errs.append(_err("REL.REF.INVALID", f"relations/{k}", {"unknown_ids": bad, "n_operands": len(rel.operand_ids)},
                             ["use number ids from the table", "give at least one operand"]))

    # ---- task 19: the two description fields. Quotes must be in the text; the stated amount due must be a number id.
    if sub.earlier_claim_quote is not None and not phrase_found(sub.earlier_claim_quote, ctx.text):
        errs.append(_err("ITEM.PHRASE.NOT_FOUND", "earlier_claim_quote", {"phrase": sub.earlier_claim_quote},
                         ["quote verbatim from redacted_text the words that mention the earlier claim",
                          "or set earlier_claim_quote null"]))
    sid, sev = sub.stated_amount_due_id, sub.stated_amount_due_evidence
    if (sid is None) != (sev is None):
        errs.append(_err("ITEM.PHRASE.NOT_FOUND", "stated_amount_due_evidence", {"stated_amount_due_id": sid, "evidence": sev},
                         ["give both stated_amount_due_id and stated_amount_due_evidence, or set both null"]))
    elif sid is not None:
        if sid not in values:
            errs.append(_err("NUM.REF.UNKNOWN_ID", "stated_amount_due_id", {"given": sid, "valid_ids": list(values)},
                             ["use a number id from the table", "or set stated_amount_due_id and its evidence null"]))
        elif not phrase_found(sev, ctx.text):
            errs.append(_err("ITEM.PHRASE.NOT_FOUND", "stated_amount_due_evidence", {"phrase": sev},
                             ["quote verbatim from redacted_text"]))

    if any(e.code.startswith(("NUM.REF", "REL.REF")) for e in errs):
        return errs, rec, None

    # ---- claim arithmetic (no Delta here)
    signed_sum = sum((signed_amount(values[j.id], j.is_credit) for j in counted), Decimal("0"))
    base_sum = sum((signed_amount(values[j.id], j.is_credit) for j in counted if j.kind != Kind.TAX_AMOUNT), Decimal("0"))
    tax_items_no_amt = [(k, li) for k, li in enumerate(sub.line_items) if li.amount_ref is None and any(category(c) == "TAX" for c in li.charge_codes)]
    all_codes = {c for li in sub.line_items for c in li.charge_codes} | {c for j in by_id.values() for c in j.charge_codes}
    rate, prov = tax_rate(ctx, all_codes)
    expected_tax = (base_sum * rate).quantize(Decimal("0.01")) if (rate is not None and tax_items_no_amt) else None
    totals = {j.id: values[j.id] for j in by_id.values() if j.kind == Kind.TOTAL}
    claim = ClaimCalc(counted_ids=[j.id for j in counted], signed_sum=signed_sum, base_sum=base_sum,
                      tax_items_without_amount=len(tax_items_no_amt), expected_tax=expected_tax, totals=totals)

    for tid, tv in totals.items():
        alt = signed_sum + expected_tax if expected_tax is not None else None
        if abs(abs(tv) - abs(signed_sum)) > TAX_TOL and not (alt is not None and abs(abs(tv) - abs(alt)) <= TAX_TOL):
            rec.append(diag("CLAIM.RECON.TOTAL_MISMATCH", f"numbers/{tid}", {"total_id": tid, "total": str(tv),
                            "counted_sum": str(signed_sum)}, "4"))

    for k, rel in enumerate(sub.relations):
        ops = [values[i] for i in rel.operand_ids]
        ev = {"relation_type": rel.relation_type, "operand_ids": rel.operand_ids, "result_id": rel.result_id}
        if rel.relation_type == "TAX":
            continue   # tax relations are reported through ITEM.TAX.* below, never judged as an error (decision 4.4)
        computed = Decimal("1") if rel.relation_type == "PRODUCT" else Decimal("0")
        for v in ops:
            computed = computed * v if rel.relation_type == "PRODUCT" else computed + v
        ev["computed"] = str(computed)
        if rel.result_id is not None:
            ev["stated"] = str(values[rel.result_id])
            if abs(computed - values[rel.result_id]) > REL_TOL:
                rec.append(diag("ITEM.ARITH.RELATION_FAILS", f"relations/{k}", ev, "4"))

    # decision 3.3: arithmetic cues in the text but no relation written -> hint for the reviewer
    if not sub.relations:
        cue_ids = [n.id for n in ctx.parse.numbers if n.prev_symbol in CUES["prev_symbols"]
                   or (n.prev_word or "") in CUES["words"] or (n.next_word or "") in CUES["words"]]
        if cue_ids and len(ctx.parse.numbers) >= 2:
            rec.append(diag("NUM.ARITH.CUE_WITHOUT_RELATION", "relations", {"ids_with_cues": cue_ids}, "4"))

    # ---- tax: every tax question goes to a human (decision 4.4); facts only
    tax_nums = [j for j in counted if j.kind == Kind.TAX_AMOUNT]
    tax_named = tax_nums or tax_items_no_amt or any(category(c) == "TAX" for c in all_codes)
    if tax_named:
        rec.append(diag("ITEM.TAX.PRESENT", "claim", {"tax_ids": [j.id for j in tax_nums], "province": prov,
                        "tax_items_without_amount": len(tax_items_no_amt)}, "4"))
    for j in tax_nums:
        if rate is None:
            rec.append(diag("ITEM.TAX.NO_RULE", f"numbers/{j.id}", {"province": prov}, "4"))
        else:
            exp = (base_sum * rate).quantize(Decimal("0.01"))
            if abs(values[j.id] - exp) > TAX_TOL:
                rec.append(diag("ITEM.TAX.RATE_MISMATCH", f"numbers/{j.id}", {"base": str(base_sum), "tax": str(values[j.id]),
                                "table_rate": str(rate), "province": prov}, "4"))
    for k, _li in tax_items_no_amt:
        rec.append(diag("ITEM.TAX.NO_AMOUNT", f"line_items/{k}", {"expected_tax_from_table": str(expected_tax) if expected_tax is not None else None,
                        "province": prov}, "4"))

    # ---- numbers and line items: reviewer hints
    for j in counted:
        tok = table.get(j.id)
        if tok and tok.space_merged:
            rec.append(diag("NUM.JUDGMENT.SPACE_MERGED_IN_CLAIM", f"numbers/{j.id}", {"id": j.id, "raw": tok.raw}, "4"))
    for k, li in enumerate(sub.line_items):
        path = f"line_items/{k}"
        j = by_id.get(li.amount_ref) if li.amount_ref else None
        codes = j.charge_codes if j else li.charge_codes
        if "OTHER" in codes:
            rec.append(diag("ITEM.CODE.OTHER", path, {"other_phrase": j.other_phrase if j else li.raw_charge_label}, "4"))
        if any(category(c) == "PENDING" for c in codes):
            rec.append(diag("ITEM.CODE.PENDING_MEANING", path, {"codes": codes}, "4"))
        if len(codes) > 1:
            rec.append(diag("ITEM.CODE.COMBINED", path, {"codes": codes}, "4"))
        if j is None and not any(category(c) == "TAX" for c in codes):
            rec.append(diag("ITEM.AMOUNT.MISSING", path, {"codes": codes}, "4"))
        if j is not None and not codes:
            rec.append(diag("ITEM.AMOUNT.UNNAMED", path, {"amount_ref": j.id}, "4"))
        if li.carrier_stated_basis_type in PPG_BASIS:
            rec.append(diag("ITEM.BASIS.PPG_CLAIMED", path, {"basis_type": li.carrier_stated_basis_type.value, "basis": li.carrier_stated_basis}, "4"))
        if li.carrier_stated_basis_type in DOC_BASIS:
            rec.append(diag("ITEM.BASIS.CONTRACT_CLAIMED", path, {"basis_type": li.carrier_stated_basis_type.value, "basis": li.carrier_stated_basis}, "4"))
        if any(category(c) == "RATE_CORRECTION" for c in codes):
            rec.append(diag("ITEM.NATURE.RATE_CORRECTION", path, {"codes": codes}, "4"))
    return errs, rec, claim


def reading_key(sub: Submission) -> str:
    """Canonical form of a reading (everything except response_type/reason) to detect 'resubmitted unchanged'."""
    d = sub.model_dump(mode="json", exclude={"response_type", "reason"})
    d["numbers"] = sorted(d["numbers"], key=lambda x: x["id"])
    return repr(d)


def attempt_changes(prev: Submission, cur: Submission) -> list[dict]:
    """Numbers whose kind / status / credit sign / codes changed between two attempts (decision 3.5)."""
    pa = {j.id: j for j in prev.numbers} | {r.region_id: r.as_number for r in prev.unrecognized_reads}
    out = []
    for j in list(cur.numbers) + [r.as_number for r in cur.unrecognized_reads]:
        p = pa.get(j.id)
        if p is None:
            continue
        for f in ("kind", "status", "is_credit", "charge_codes"):
            a, b = getattr(p, f), getattr(j, f)
            if a != b:
                out.append({"id": j.id, "field": f, "from": getattr(a, "value", a), "to": getattr(b, "value", b)})
    return out


def reason_code_conflict(reason_code: str | None, sub: Submission) -> list[Diagnostic]:
    """Info only (prototype behaviour): the Excel Reason Code names a specific category the reading does not have.
    Reason Code is never sent to the model; this compares after the fact."""
    cats = RULES.get("reason_code_categories", {}).get(reason_code or "")
    if not cats:
        return []
    codes = {c for j in sub.numbers for c in j.charge_codes} | {c for li in sub.line_items for c in li.charge_codes}
    model_cats = {category(c) for c in codes if c in CODES} - {"OTHER", "PENDING", "TAX"}
    if not model_cats:
        return []
    specific = RULES.get("reason_code_specific_codes", {}).get(reason_code)
    if not (model_cats & set(cats)) or (specific is not None and not (codes & set(specific))):
        return [diag("REC.FIELD.REASON_CODE_CONFLICT", "source/reason_code",
                     {"reason_code": reason_code, "reason_category": cats, "model_categories": sorted(model_cats)}, "6")]
    return []
