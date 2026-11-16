"""Shipment roll-up (task 14 / T12-03; T12 adjustment plan section 4.3, option A). Pure code, no model call.

One shipment (SHIPMENT_GID, shown with its SAP BOL) can have several explanations; each explanation was read once by
the model. This module turns the stored readings into the client's table: the original amount (Shipment Amount),
each charge line (tax on its own line), the new total and the change from the original amount. It always gives a
default total, and for every 'possible duplicate' it also gives the total under the other reading (client decision
A4). It never decides whether a charge should be paid.

Rules, in order (numbers as in the adjustment plan):
 1. Order: Event Date, then the first source row number. A replacement whose direction rests on that row order
    (equal Event Dates) raises SHIP.ROLLUP.ORDER_TIED.
 2. Same charge, later explanation: a later explanation's non-tax line with the same charge as an earlier counted
    line replaces it (A3). "Same charge" compares the finest internal code (OTHER also compares its phrase), never
    the client name a code maps to: purchased transportation, a base-rate correction, a weight correction and a
    minimum charge all sit under the client's Freight and must not replace each other. SUPERSEDED_SAME_CHARGE.
 3. Tax follows its explanation and never takes part in rule 2: when every non-tax line of an explanation is
    replaced, its tax lines go with them; when only some are, the tax stays and TAX_PARTLY_ORPHANED is raised.
 4. Different charges add up.
 5. Same amount as an earlier still-counted line with another code: added by default, SAME_AMOUNT_EARLIER carries
    the total with the amount counted once.
 6. Ratio 1.03-1.07 (A5, thresholds in rules.yaml `rollup`):
    a. In one explanation, the first '$' amount after BALANCE DUE at ratio x an earlier '$' amount of the same text:
       only the BALANCE DUE amount counts. Code decides this default; the model's reading is kept, and when the
       two count different amounts BALANCE_DUE_READING_DIFFERS is raised. RATIO_SUPERSEDED.
    b. Two adjacent explanations with one counted amount each, the later at ratio x the earlier: the later
       replaces the earlier even when the codes differ or the later names no charge. RATIO_SUPERSEDED. (When both
       name the same charge, rule 2 already applies and raises SUPERSEDED_SAME_CHARGE instead.)
    c. (task 20, decision D-95) Otherwise, wherever BALANCE DUE is written, the first '$' amount after it is compared
       with the explanation's other '$' amounts: no other amount -> it is the amount asked for, no flag; 'amount +
       tax' (every other amount is a tax the reading names, or the total of the amount and those taxes, and it adds
       up) -> amount and taxes count separately, BALANCE_DUE_READING_DIFFERS when the reading counts something else;
       the BALANCE DUE amount is 1.03-1.07x another amount, or one amount is the sum of all the others -> a decided
       relation, the model's reading stands; none of these -> BALANCE_DUE_UNRESOLVED (the model's reading stands).
 7. Undecidable relation (OTHER with a different phrase on either side, an amount with no charge name, one amount
    for several overlapping codes): added by default, RELATION_UNDECIDED.
 8. An explanation without a usable reading: the default total leaves it out, the shipment is incomplete, INCOMPLETE.
 9. (task 17) A later counted amount equal to, or 1.03-1.07x, an amount an earlier explanation read as history:
    ECHO_OF_HISTORY_AMOUNT (the earlier reading may have missed a claim the later one restates). No total changes.
Credits are negative lines and add up like any other line. Every SHIP.ROLLUP.* severity is in rules.yaml.
The shipment's recommendation is the worst of its explanations' recommendations and its own flags.

Gap (task 20, concepts.gap): per explanation and per shipment three numbers: the line total (the counted amounts),
the stated amount due (facts.stated_amount_due, or empty) and gap = stated amount due - line total (empty, not 0,
when nothing is stated). A shipment with one explanation takes that explanation's numbers; with several, the
shipment-level stated amount and gap stay empty and SHIP.GAP.MULTI_EXPLANATION (info) is raised when any
explanation states an amount. A gap other than 0 raises SHIP.GAP.NONZERO (info). The gap is never a line and never
enters a total or a per-charge count; the default total is unchanged.

Extension points (task 20 section 2.5), each with a default implementation:
- prior_history: a `PriorHistory` source (cross-batch history). The default `NoPriorHistory` answers NOT_PROVIDED;
  the output shows that state as is, which never means "no earlier claim".
- relation_suggestions: suggestions for rule-7 relations (a possible history-reading skill). Default empty; they
  are copied into the output next to the undecided relations and change no total.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from freight_lineitems.checks import diag, region_value
from freight_lineitems.claim import is_counted, is_history, is_money_kind, signed_amount
from freight_lineitems.claim import judgments as _judgments
from freight_lineitems.config import RULES, category
from freight_lineitems.disposition import flags_from, recommend
from freight_lineitems.schemas import Diagnostic

CFG = RULES["rollup"]
RATIO_MIN, RATIO_MAX = Decimal(str(CFG["ratio_min"])), Decimal(str(CFG["ratio_max"]))
BALANCE_DUE = re.compile(CFG["balance_due_pattern"])
TOL = Decimal(str(RULES["tolerances"]["amount_abs"]))
REL_TOL = Decimal(str(RULES["tolerances"]["relation_abs"]))
REC_ORDER = ["HUMAN_REVIEW", "RETURN_SUGGESTED", "PASSED_CHECKS"]

COUNTED, SUPERSEDED, NOT_COUNTED = "COUNTED", "SUPERSEDED", "NOT_COUNTED"
SHIPMENT_SCHEMA_VERSION = "shipment-output-1.0"     # docs/shipment_output_contract.md

# ------------------------------------------------------------------ extension point: cross-batch history (task 20)
HISTORY_FOUND, HISTORY_NONE, HISTORY_NOT_PROVIDED = "FOUND", "CHECKED_NONE", "NOT_PROVIDED"


class PriorHistory:
    """Cross-batch history of a shipment (earlier batches' explanations). Three states, never collapsed:
    FOUND (earlier items exist; `items` lists them), CHECKED_NONE (a history source was asked and has nothing for this
    shipment), NOT_PROVIDED (no history source was given; nothing is known). Subclass and override `lookup`."""

    def lookup(self, shipment_key: str) -> dict:
        raise NotImplementedError


class NoPriorHistory(PriorHistory):
    """Default: no history source. Every shipment is NOT_PROVIDED, which must never be read as 'no earlier claim'."""

    def lookup(self, shipment_key: str) -> dict:
        return {"status": HISTORY_NOT_PROVIDED, "items": [], "source": None}


class DictPriorHistory(PriorHistory):
    """A history source backed by a dict shipment key -> earlier items (tests, or an export of earlier runs). A
    shipment missing from the dict was checked and has none."""

    def __init__(self, items: dict[str, list[dict]], source: str = "dict"):
        self.items, self.source = items, source

    def lookup(self, shipment_key: str) -> dict:
        found = list(self.items.get(shipment_key, []))
        return {"status": HISTORY_FOUND if found else HISTORY_NONE, "items": found, "source": self.source}


@dataclass
class Line:
    """One amount of one explanation's reading. `status` is the roll-up's verdict, not the model's."""
    line_id: str
    expl: int                       # index of the explanation in roll-up order
    number_id: str
    amount: Decimal                 # signed: credits are negative
    codes: tuple[str, ...]
    label: str                      # the text's charge name (raw_charge_label, or the OTHER phrase), '' if none
    is_tax: bool
    status: str = COUNTED
    replaced_by: str | None = None  # line_id that replaces this one
    event: str | None = None        # id of the replacement event (one per flag that carries another reading)
    added_by_code: bool = False     # rule 6a: the BALANCE DUE amount, counted by code although the model did not

    @property
    def key(self) -> str | None:
        """Finest-level charge identity, or None when it cannot be compared (no charge name, several codes)."""
        if len(self.codes) != 1:
            return None
        c = self.codes[0]
        return "OTHER:" + " ".join(self.label.upper().split()) if c == "OTHER" else c


@dataclass
class Explanation:
    expl_id: str                    # the representative record id
    event_date: datetime | None
    first_row: int
    text: str                       # redacted text (number spans point into it)
    numbers: list[dict]             # number table: id, value, span, has_dollar
    usable: bool                    # the reading passed the mandatory checks
    lines: list[Line] = field(default_factory=list)
    recommendation: str = "PASSED_CHECKS"
    n_rows: int = 1
    n_orders: int = 0
    pks: set = field(default_factory=set)
    model_counted: dict[str, Decimal] = field(default_factory=dict)   # number id -> amount the model counted
    history_amounts: list[tuple[str, Decimal]] = field(default_factory=list)   # (number id, amount) read as history
    judged: dict[str, dict] = field(default_factory=dict)             # number id -> the model's judgment
    stated_due: Decimal | None = None   # facts.stated_amount_due value (concepts.stated_amount_due), None if not stated


def explanation_from_result(res: dict) -> Explanation:
    """Build an Explanation from a pipeline result (stored records.jsonl or a fresh run). Lines are the counted
    money amounts of the final reading (status CLAIMED/UNPAID, kind charge/unspecified/tax)."""
    f = res["facts"]
    s = f["source"]
    ed = s.get("event_date")
    ed = datetime.fromisoformat(ed) if isinstance(ed, str) and ed not in ("", "None") else (ed if isinstance(ed, datetime) else None)
    rows = f.get("source_rows") or [{"record_id": res["record_id"], "row_number": s["row_number"], "pk": s.get("pk")}]
    nt = f["number_table"]
    numbers = [{"id": n["id"], "value": Decimal(str(n["value"])), "span": tuple(n["span"]), "has_dollar": n["has_dollar"]}
               for n in nt["numbers"]]
    e = Explanation(expl_id=res["record_id"], event_date=ed, first_row=min(r["row_number"] for r in rows),
                    text=f.get("text_redacted") or "", numbers=numbers,
                    usable=f["parse_status"] == "PASSED_CHECKS" and bool(f.get("reading")),
                    recommendation=res["judgment"]["recommendation"], n_rows=f.get("n_rows", len(rows)),
                    n_orders=f.get("n_orders", len({r["pk"] for r in rows if r.get("pk")})),
                    pks={r["pk"] for r in rows if r.get("pk")})
    sad = f.get("stated_amount_due") or {}
    if sad.get("value") not in (None, "", "None"):
        e.stated_due = Decimal(str(sad["value"]))
    if not e.usable:
        return e
    reading = f["reading"]
    val = {n["id"]: n["value"] for n in numbers} | {u["id"]: region_value(u["raw"]) for u in nt["unrecognized"]}
    labels = {li["amount_ref"]: li.get("raw_charge_label") for li in reading.get("line_items", []) if li.get("amount_ref")}
    for j in _judgments(reading):
        e.judged[j["id"]] = j
        if is_history(j["status"]) and is_money_kind(j["kind"]) and j["id"] in val:
            e.history_amounts.append((j["id"], val[j["id"]]))
        if not is_counted(j["kind"], j["status"]):
            continue
        amt = signed_amount(val[j["id"]], j.get("is_credit"))
        codes = tuple(j.get("charge_codes") or ())
        label = (j.get("other_phrase") if "OTHER" in codes else None) or labels.get(j["id"]) or ""
        e.lines.append(Line(line_id="", expl=-1, number_id=j["id"], amount=amt, codes=codes, label=label,
                            is_tax=j["kind"] == "TAX_AMOUNT" or any(category(c) == "TAX" for c in codes)))
        e.model_counted[j["id"]] = amt
    return e


def _ratio_ok(later: Decimal, earlier: Decimal) -> bool:
    return earlier > 0 and later > 0 and RATIO_MIN <= later / earlier <= RATIO_MAX


def _same_amount(a: Decimal, b: Decimal) -> bool:
    return abs(abs(a) - abs(b)) <= TOL


def _undecidable(a: Line, b: Line) -> str | None:
    """Rule 7: why lines a and b of different explanations cannot be compared by code, or None."""
    if not a.codes or not b.codes:
        return "no charge name"
    if (len(a.codes) > 1 or len(b.codes) > 1) and set(a.codes) & set(b.codes):
        return "one amount for several codes"
    if ("OTHER" in a.codes or "OTHER" in b.codes) and a.key != b.key:
        return "OTHER with a different phrase"
    return None


def _ev(line: Line) -> dict:
    return {"line_id": line.line_id, "number_id": line.number_id, "amount": str(line.amount), "codes": list(line.codes),
            "label": line.label}


def balance_due_relation(due: dict, others: list[dict], judged: dict[str, dict]) -> tuple[str | None, list[str]]:
    """Task 20 (D-95): how the first '$' amount after BALANCE DUE relates to the explanation's other '$' amounts.
    Returns (relation, tax number ids). Relations, in order: 'single_amount' (no other '$' amount), 'ratio' (the
    BALANCE DUE amount is ratio_min..ratio_max times another amount), 'amount_plus_tax' (every other amount is a tax
    the reading names, or the total of the BALANCE DUE amount and those taxes), 'total' (one of the amounts is the
    sum of all the others); None when none holds."""
    if not others:
        return "single_amount", []
    if any(_ratio_ok(due["value"], o["value"]) for o in others):
        return "ratio", []
    taxes = [o for o in others if (judged.get(o["id"]) or {}).get("kind") == "TAX_AMOUNT"]
    rest = [o for o in others if o not in taxes]
    with_tax = due["value"] + sum((t["value"] for t in taxes), Decimal(0))
    if taxes and len(rest) <= 1 and all(abs(o["value"] - with_tax) <= REL_TOL for o in rest):
        return "amount_plus_tax", [t["id"] for t in taxes]
    allv = [due] + others
    for t in allv:
        if abs(t["value"] - sum((o["value"] for o in allv if o["id"] != t["id"]), Decimal(0))) <= REL_TOL * len(allv):
            return "total", []
    return None, []


def _balance_due(e: Explanation, diags: list[Diagnostic], events: list[dict], k: int) -> None:
    """Rule 6a / 6c inside one explanation."""
    m = BALANCE_DUE.search(e.text.upper())
    if not m:
        return
    dollars = [n for n in e.numbers if n["has_dollar"]]
    before = [n for n in dollars if n["span"][1] <= m.start()]
    after = [n for n in dollars if n["span"][0] >= m.end()]
    if not after:
        return
    due = after[0]
    match = next((b for b in reversed(before) if _ratio_ok(due["value"], b["value"])), None)
    if match is None:                 # rule 6c (D-95): wherever BALANCE DUE is written
        others = [n for n in dollars if n["id"] != due["id"]]
        rel, tax_ids = balance_due_relation(due, others, e.judged)
        where = "after_other_amounts" if before else "first"
        if rel is None:
            diags.append(diag("SHIP.ROLLUP.BALANCE_DUE_UNRESOLVED", f"explanations/{e.expl_id}", {
                "explanation": e.expl_id, "position": where, "balance_due_number": due["id"],
                "other_dollar_numbers": [o["id"] for o in others],
                "earlier_dollar_numbers": [b["id"] for b in before],
                "checked": ["ratio", "amount_plus_tax", "total"], "default": "the model's reading"}, "6"))
        elif rel == "amount_plus_tax":
            want = {due["id"], *tax_ids}
            if want != set(e.model_counted):
                diags.append(diag("SHIP.ROLLUP.BALANCE_DUE_READING_DIFFERS", f"explanations/{e.expl_id}", {
                    "explanation": e.expl_id, "case": "amount_plus_tax", "position": where,
                    "model_counted": sorted(e.model_counted), "code_expects": sorted(want)}, "6"))
        return
    by_num = {ln.number_id: ln for ln in e.lines}
    earlier_line, due_line = by_num.get(match["id"]), by_num.get(due["id"])
    codes = (earlier_line.codes if earlier_line else tuple(e.judged.get(match["id"], {}).get("charge_codes") or ()))
    if due_line is None:              # code counts the BALANCE DUE amount although the model did not
        due_line = Line(line_id=f"{e.expl_id}:{due['id']}", expl=k, number_id=due["id"], amount=due["value"], codes=codes,
                        label=earlier_line.label if earlier_line else "", is_tax=False, added_by_code=True)
        e.lines.append(due_line)
    ev_id = f"E{len(events) + 1}"
    alt = Decimal(0)
    if earlier_line is not None and earlier_line.status == COUNTED:
        earlier_line.status, earlier_line.replaced_by, earlier_line.event = NOT_COUNTED, due_line.line_id, ev_id
        alt = earlier_line.amount
    else:
        alt = match["value"]          # the other reading counts the earlier amount as well
    events.append({"event": ev_id, "flag": "SHIP.ROLLUP.RATIO_SUPERSEDED", "alt_change": alt})
    diags.append(diag("SHIP.ROLLUP.RATIO_SUPERSEDED", f"explanations/{e.expl_id}", {
        "case": "balance_due_in_one_explanation", "event": ev_id, "explanation": e.expl_id,
        "replaced_number": match["id"], "replaced_amount": str(match["value"]), "balance_due_number": due["id"],
        "balance_due_amount": str(due["value"]), "ratio": str((due["value"] / match["value"]).quantize(Decimal("0.0001"))),
        "default": "count only the BALANCE DUE amount", "other_reading_change": str(alt)}, "6"))
    code_ids = {ln.number_id for ln in e.lines if ln.status == COUNTED}
    if code_ids != set(e.model_counted):
        diags.append(diag("SHIP.ROLLUP.BALANCE_DUE_READING_DIFFERS", f"explanations/{e.expl_id}", {
            "explanation": e.expl_id, "model_counted": sorted(e.model_counted), "code_counted": sorted(code_ids)}, "6"))


def gap_fields(exps: list[Explanation], lines: list[Line]) -> dict:
    """concepts.gap (task 20, D-96): line total, stated amount due and gap = stated - line total, per explanation and
    for the shipment. The line total of an explanation is the sum of its lines its own reading and rule 6a count
    (lines a later explanation replaced still belong to this one's total); the shipment's line total is the default
    change. Returns the shipment fields, 'per_explanation' (one dict per explanation, in roll-up order) and '_diags'
    (the info flags)."""
    per, diags = [], []
    for k, e in enumerate(exps):
        tot = sum((ln.amount for ln in lines if ln.expl == k and ln.status != NOT_COUNTED), Decimal(0)) if e.usable else None
        gap = (e.stated_due - tot) if (e.stated_due is not None and tot is not None) else None
        per.append({"items_total": str(tot) if tot is not None else None,
                    "stated_amount_due": str(e.stated_due) if e.stated_due is not None else None,
                    "gap": str(gap) if gap is not None else None})
    stated_any = [p for p in per if p["stated_amount_due"] is not None]
    nonzero = [(e.expl_id, p) for e, p in zip(exps, per) if p["gap"] is not None and abs(Decimal(p["gap"])) > TOL]
    if nonzero:
        diags.append(diag("SHIP.GAP.NONZERO", "shipment", {"explanations": [
            {"explanation": x, "items_total": p["items_total"], "stated_amount_due": p["stated_amount_due"],
             "gap": p["gap"]} for x, p in nonzero], "default": "the default total is unchanged"}, "6"))
    if len(exps) == 1:
        ship = {"stated_amount_due": per[0]["stated_amount_due"], "gap": per[0]["gap"], "gap_note": None}
    else:
        ship = {"stated_amount_due": None, "gap": None,
                "gap_note": "MULTI_EXPLANATION_NO_SHIPMENT_GAP" if stated_any else None}
        if stated_any:
            diags.append(diag("SHIP.GAP.MULTI_EXPLANATION", "shipment", {
                "explanations_with_stated_amount": [e.expl_id for e, p in zip(exps, per) if p["stated_amount_due"] is not None],
                "why": "which charges one explanation's stated amount covers is not known (cross-explanation work)"}, "6"))
    items = sum((ln.amount for ln in lines if ln.status == COUNTED), Decimal(0))
    return {"items_total": str(items), **ship, "per_explanation": per, "_diags": diags}


def rollup(shipment_key: str, shipment_amount: Decimal | None, explanations: list[Explanation],
           display: dict | None = None, prior_history: "PriorHistory | None" = None,
           relation_suggestions: list[dict] | None = None) -> dict:
    """Roll one shipment's explanations up into the client's table. Returns a dict with the ordered explanations,
    every line and its status, the default change and new total, the other-reading totals, the gap columns, flags
    and the shipment's recommendation. `display` is copied into the result unchanged (e.g. the SAP BOL).
    `prior_history` (default: not provided) and `relation_suggestions` (default: none) are the extension points of
    task 20; neither changes a total today."""
    exps = sorted(explanations, key=lambda e: (e.event_date is None, e.event_date or datetime.min, e.first_row))
    diags: list[Diagnostic] = []
    events: list[dict] = []
    for k, e in enumerate(exps):
        for ln in e.lines:
            ln.expl, ln.line_id = k, f"{e.expl_id}:{ln.number_id}"
    # rule 8
    unusable = [e.expl_id for e in exps if not e.usable]
    if unusable:
        diags.append(diag("SHIP.ROLLUP.INCOMPLETE", "shipment", {"explanations_without_reading": unusable,
                                                                 "default": "sum of the other explanations"}, "6"))
    # rule 6a / 6c (within each explanation)
    for k, e in enumerate(exps):
        if e.usable:
            _balance_due(e, diags, events, k)

    def tied(a: int, b: int) -> bool:
        return exps[a].event_date == exps[b].event_date

    def counted_nontax(upto: int) -> list[Line]:
        return [ln for e in exps[:upto] for ln in e.lines if ln.status == COUNTED and not ln.is_tax]

    for n in range(1, len(exps)):
        e = exps[n]
        if not e.usable:
            continue
        mine = [ln for ln in e.lines if ln.status == COUNTED and not ln.is_tax]
        # rule 6b: adjacent explanations, one counted amount each, ratio 1.03-1.07
        prev = exps[n - 1]
        pc = [ln for ln in prev.lines if ln.status == COUNTED]
        cc = [ln for ln in e.lines if ln.status == COUNTED]
        ratio_done: set[str] = set()
        if prev.usable and len(pc) == 1 and len(cc) == 1 and not pc[0].is_tax and not cc[0].is_tax \
                and not (pc[0].key is not None and pc[0].key == cc[0].key) and _ratio_ok(cc[0].amount, pc[0].amount):
            ev_id = f"E{len(events) + 1}"
            pc[0].status, pc[0].replaced_by, pc[0].event = SUPERSEDED, cc[0].line_id, ev_id
            events.append({"event": ev_id, "flag": "SHIP.ROLLUP.RATIO_SUPERSEDED", "alt_change": pc[0].amount})
            diags.append(diag("SHIP.ROLLUP.RATIO_SUPERSEDED", "shipment", {
                "case": "adjacent_explanations", "event": ev_id, "replaced": _ev(pc[0]), "by": _ev(cc[0]),
                "ratio": str((cc[0].amount / pc[0].amount).quantize(Decimal("0.0001"))),
                "default": "the later amount replaces the earlier one"}, "6"))
            if tied(n - 1, n):
                diags.append(diag("SHIP.ROLLUP.ORDER_TIED", "shipment", {"event": ev_id, "explanations": [prev.expl_id, e.expl_id]}, "6"))
            ratio_done.add(cc[0].line_id)
        # rule 2: same charge (finest internal code) replaces earlier counted lines
        for ln in mine:
            if ln.line_id in ratio_done or ln.key is None:
                continue
            earlier = [x for x in counted_nontax(n) if x.key == ln.key]
            if not earlier:
                continue
            ev_id = f"E{len(events) + 1}"
            for x in earlier:
                x.status, x.replaced_by, x.event = SUPERSEDED, ln.line_id, ev_id
            events.append({"event": ev_id, "flag": "SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE", "alt_change": None})
            diags.append(diag("SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE", "shipment", {
                "event": ev_id, "charge": ln.key, "replaced": [_ev(x) for x in earlier], "by": _ev(ln),
                "default": "the later explanation's amount counts once"}, "6"))
            if any(tied(x.expl, n) for x in earlier):
                diags.append(diag("SHIP.ROLLUP.ORDER_TIED", "shipment", {
                    "event": ev_id, "explanations": sorted({exps[x.expl].expl_id for x in earlier} | {e.expl_id})}, "6"))
        # rules 7 and 5 against what is still counted
        for ln in mine:
            if ln.status != COUNTED:
                continue
            earlier = counted_nontax(n)
            why = [(x, r) for x in earlier if (r := _undecidable(ln, x))]
            if why:
                diags.append(diag("SHIP.ROLLUP.RELATION_UNDECIDED", "shipment", {
                    "line": _ev(ln), "earlier": [_ev(x) | {"why": r} for x, r in why],
                    "default": "added to the earlier lines"}, "6"))
            same = [x for x in earlier if _same_amount(x.amount, ln.amount)]
            if same:
                ev_id = f"E{len(events) + 1}"
                events.append({"event": ev_id, "flag": "SHIP.ROLLUP.SAME_AMOUNT_EARLIER", "alt_change": -ln.amount})
                diags.append(diag("SHIP.ROLLUP.SAME_AMOUNT_EARLIER", "shipment", {
                    "event": ev_id, "line": _ev(ln), "earlier": [_ev(x) for x in same],
                    "default": "added", "other_reading": "count the amount once"}, "6"))
    # rule 9 (task 17, D-76): a later counted amount that equals, or is ratio_min..ratio_max times, an amount an earlier
    # explanation read as history. The earlier reading may have missed a claim that the later one restates.
    for n in range(1, len(exps)):
        e = exps[n]
        hist = [(exps[k].expl_id, nid, v) for k in range(n) for nid, v in exps[k].history_amounts if v > 0]
        for ln in e.lines:
            if ln.status != COUNTED or ln.amount <= 0:
                continue
            hits = [(x, nid, str(v)) for x, nid, v in hist if _same_amount(ln.amount, v) or _ratio_ok(ln.amount, v)]
            if hits:
                diags.append(diag("SHIP.ROLLUP.ECHO_OF_HISTORY_AMOUNT", "shipment", {
                    "line": _ev(ln), "earlier_history_amounts": [{"explanation": x, "number_id": i, "amount": a} for x, i, a in hits]}, "6"))
    # rule 3: tax follows its explanation
    for e in exps:
        nontax = [ln for ln in e.lines if not ln.is_tax and ln.status != NOT_COUNTED]
        taxes = [ln for ln in e.lines if ln.is_tax and ln.status == COUNTED]
        gone = [ln for ln in nontax if ln.status == SUPERSEDED]
        if not taxes or not gone:
            continue
        if len(gone) == len(nontax):
            for t in taxes:
                t.status, t.replaced_by, t.event = SUPERSEDED, gone[0].replaced_by, gone[0].event
        else:
            diags.append(diag("SHIP.ROLLUP.TAX_PARTLY_ORPHANED", "shipment", {
                "explanation": e.expl_id, "taxes_kept": [_ev(t) for t in taxes], "replaced": [_ev(x) for x in gone]}, "6"))
    lines = [ln for e in exps for ln in e.lines]
    change = sum((ln.amount for ln in lines if ln.status == COUNTED), Decimal(0))
    for ev in events:                 # the other reading of a replacement adds back everything that event replaced
        hit = [ln.amount for ln in lines if ln.event == ev["event"]]
        if ev["flag"] != "SHIP.ROLLUP.SAME_AMOUNT_EARLIER" and hit:
            ev["alt_change"] = sum(hit, Decimal(0))
    original = shipment_amount
    alternatives = [{"event": ev["event"], "flag": ev["flag"], "change": str(change + ev["alt_change"]),
                     "new_total": str(original + change + ev["alt_change"]) if original is not None else None}
                    for ev in events]
    lo = change + sum((ev["alt_change"] for ev in events if ev["alt_change"] < 0), Decimal(0))
    hi = change + sum((ev["alt_change"] for ev in events if ev["alt_change"] > 0), Decimal(0))
    for d in diags:                   # every flag that has another reading names its total
        evid = d.evidence.get("event")
        alt = next((a for a in alternatives if a["event"] == evid), None)
        if alt:
            d.evidence["other_reading_change"], d.evidence["other_reading_new_total"] = alt["change"], alt["new_total"]
    gaps = gap_fields(exps, lines)
    diags += gaps.pop("_diags")
    hist = (prior_history or NoPriorHistory()).lookup(shipment_key)
    undecided = [d.evidence for d in diags if d.code == "SHIP.ROLLUP.RELATION_UNDECIDED"]
    flags = flags_from(diags)
    own = recommend(flags)
    worst = min([own["recommendation"]] + [e.recommendation for e in exps], key=REC_ORDER.index)
    return {
        "schema_version": SHIPMENT_SCHEMA_VERSION,
        "shipment_key": shipment_key, **(display or {}),
        "original_amount": str(original) if original is not None else None,
        "explanations": [{"expl_id": e.expl_id, "event_date": e.event_date.isoformat() if e.event_date else None,
                          "first_row": e.first_row, "n_rows": e.n_rows, "n_orders": e.n_orders, "usable": e.usable,
                          "recommendation": e.recommendation} | g for e, g in zip(exps, gaps.pop("per_explanation"))],
        "n_orders": len(set().union(*[e.pks for e in exps])) if exps else 0,
        "lines": [{"line_id": ln.line_id, "explanation": exps[ln.expl].expl_id, "number_id": ln.number_id,
                   "amount": str(ln.amount), "codes": list(ln.codes), "label": ln.label, "is_tax": ln.is_tax,
                   "status": ln.status, "replaced_by": ln.replaced_by, "event": ln.event,
                   "added_by_code": ln.added_by_code} for ln in lines],
        "default_change": str(change),
        "new_total": str(original + change) if original is not None else None,
        "complete": not unusable,
        "other_readings": alternatives,
        "other_readings_range": ({"min_change": str(lo), "max_change": str(hi),
                                  "min_new_total": str(original + lo) if original is not None else None,
                                  "max_new_total": str(original + hi) if original is not None else None}
                                 if events else None),
        **gaps,
        "prior_history": hist,
        "relation_undecided": bool(undecided),
        "relation_suggestions": list(relation_suggestions or []),
        "flags": flags,
        "shipment_flags_recommendation": own["recommendation"],
        "recommendation": worst,
    }


def rollup_results(results: list[dict], prior_history: "PriorHistory | None" = None,
                   relation_suggestions: dict[str, list[dict]] | None = None) -> list[dict]:
    """Group pipeline results (one per explanation) by shipment and roll each shipment up. Display fields: SAP BOL
    (from the raw row when present). Returns one roll-up per shipment, in order of first appearance.
    `relation_suggestions` maps a shipment key to its suggestions (default: none for every shipment)."""
    by_ship: dict[str, list[dict]] = {}
    for r in results:
        by_ship.setdefault(r["facts"]["source"]["shipment_key"], []).append(r)
    out = []
    for key, rs in by_ship.items():
        s = rs[0]["facts"]["source"]
        amt = s.get("shipment_amount")
        amt = Decimal(str(amt)) if amt not in (None, "", "None") else None
        bol = (s.get("raw") or {}).get("SAP BOL")
        out.append(rollup(key, amt, [explanation_from_result(r) for r in rs], {"sap_bol": bol}, prior_history,
                          (relation_suggestions or {}).get(key)))
    return out
