"""The five agent tools: definitions written for the model, implementations, and the submission controller.

The agent gets these tools only (no shell, files, or network). Definitions follow the Anthropic tool format;
`strict: true` makes the API guarantee schema-valid inputs (claude-opus-5 supports it). Business checks are ours.
This prototype never calls an API: step 3 is played by hand in walkthrough.py.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import ValidationError

from checks import TAX_TOL, Ctx, check_submission, tax_rate
from config import CATALOG, RULES, TAX, country
from gate import diag
from schemas import (Diagnostic, Handling, ObjectType, ReceiptError, RepairReceipt, Submission)

# ------------------------------------------------------------------------------------------------ definitions

UNCERTAINTY_TYPES = ["number_parse_suspect", "kind_or_status_ambiguous", "charge_not_in_taxonomy",
                     "delta_does_not_match_text", "text_contradicts_itself", "other"]


def _strictify(schema: dict) -> dict:
    """Pydantic schema -> strict tool schema: every object closed, every property required."""
    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "object" or "properties" in n:
                n["additionalProperties"] = False
                n["required"] = list(n.get("properties", {}))
            for k in ("title", "default"):
                n.pop(k, None)
            for v in list(n.values()):
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(schema)
    return schema


TOOLS = [
    {
        "name": "submit_line_items",
        "strict": True,
        "description": (
            "Submit your reading of this dispute. This is the ONLY way to give an answer; nothing you write in plain "
            "text is recorded.\n\n"
            "What it does: checks your submission against the source text, the number table and Delta, and either "
            "accepts it or returns a repair receipt.\n"
            "When to use: once you have judged every number id and listed the line items. Call reconcile first if you "
            "want to test arithmetic; that does not use up an attempt.\n"
            "Arguments: numbers (one judgment per id in the number table: kind, status, charge_codes, other_phrase, "
            "evidence_phrase), line_items (one per CLAIMED/UNPAID amount, plus charges named without an amount, e.g. "
            "'+ HST'), unrecognized_reads (one per unrecognized region). You never write amounts except in "
            "unrecognized_reads.value, whose digits must equal the region's digits exactly. Every phrase field must be "
            "copied from redacted_text.\n"
            "Returns: {accepted: true} or a repair receipt {accepted: false, attempt, retries_left, errors[{code, path, "
            "evidence, allowed_fixes}], never_allowed, if_you_believe_your_reading_is_correct}.\n"
            "Failure modes: up to 2 retries after the first submission. If the same submission is sent again unchanged, "
            "processing stops and the record goes to a human with your answer marked as not passed; do this, together "
            "with report_uncertainty, when you believe your reading is right and the numbers still do not fit. Never "
            "change a status or kind only to make the sum equal Delta."),
        "input_schema": _strictify(Submission.model_json_schema()),
    },
    {
        "name": "reconcile",
        "strict": True,
        "description": (
            "Trial arithmetic for a reading you are considering. Not a submission; does not count as an attempt.\n\n"
            "When to use: before submitting, to see whether the amounts you would count add up to Delta, whether a "
            "stated total equals them, and what tax the table implies for a charge mentioned without a tax amount.\n"
            "Arguments: counted_ids (ids you would mark CLAIMED or UNPAID, excluding totals), total_ids (ids you would "
            "mark TOTAL), tax_named_without_amount (true if the text names a tax but gives no tax amount).\n"
            "Returns: claimed_sum, delta, difference, matches_delta, expected_tax (from the tax table for the "
            "destination province, or null), totals [{id, value, consistent_with_items}], calls_left.\n"
            "Failure modes: unknown ids are reported back. Limited to 3 calls per record; every call is logged and "
            "trying many combinations is itself flagged for the reviewer. A reading that only works after trying many "
            "combinations is not evidence."),
        "input_schema": {
            "type": "object", "additionalProperties": False,
            "properties": {"counted_ids": {"type": "array", "items": {"type": "string"}},
                           "total_ids": {"type": "array", "items": {"type": "string"}},
                           "tax_named_without_amount": {"type": "boolean"}},
            "required": ["counted_ids", "total_ids", "tax_named_without_amount"],
        },
    },
    {
        "name": "lookup_tax_rule",
        "strict": True,
        "description": (
            "Look up the sales tax rate for a Canadian province on a date.\n\n"
            "When to use: the text mentions GST, HST, PST, QST or TAX and you need to know whether a number is a tax "
            "amount, or what tax a '+ HST' implies.\n"
            "Arguments: province (two-letter code from the input, e.g. 'AB'), date (YYYY-MM-DD; use the Event Date if "
            "the text gives none).\n"
            "Returns: {province, country, components [{name, rate}], provincial_tax_applies_to_freight "
            "('unknown' where unsettled), note}. For non-Canadian codes, components is empty.\n"
            "Failure modes: unknown or US codes return an empty rule with a reason; the table covers 2021-2022 only. "
            "Which province applies (origin or destination) is not settled; the checks use the destination."),
        "input_schema": {"type": "object", "additionalProperties": False,
                         "properties": {"province": {"type": "string"}, "date": {"type": "string", "format": "date"}},
                         "required": ["province", "date"]},
    },
    {
        "name": "find_similar_examples",
        "strict": True,
        "description": (
            "Retrieve up to k worked examples whose wording resembles this text, each with its marked text and a "
            "reviewed submission.\n\n"
            "When to use: the wording is unusual for you (payment history, BALANCE DUE written several ways, rate "
            "arguments, abbreviations) and you want to see how similar texts were read. Examples illustrate the "
            "conventions; they are not rules and never override what this text says.\n"
            "Arguments: query (paste marked_text or a phrase from it), k (1-5).\n"
            "Returns: [{example_id, marked_text, submission, note}]. Examples come from the development split only, "
            "with names redacted; the same shipment is never returned.\n"
            "Failure modes: may return nothing; may return examples that look similar but differ in meaning."),
        "input_schema": {"type": "object", "additionalProperties": False,
                         "properties": {"query": {"type": "string"}, "k": {"type": "integer"}},
                         "required": ["query", "k"]},
    },
    {
        "name": "report_uncertainty",
        "strict": True,
        "description": (
            "Tell the reviewer that you are not sure about one specific object. Creates a diagnostic; it does not stop "
            "processing and does not decide where the record goes (rules do).\n\n"
            "When to use: a number may have been split or merged wrongly by the parser; a kind/status is genuinely "
            "ambiguous; no taxonomy code fits; the text's own amounts cannot match Delta; the text contradicts itself. "
            "Use it instead of guessing. Call it once per issue.\n"
            "Arguments: target_path (e.g. 'numbers/#3', 'line_items/1', 'claim'), reason_type (one of the enum), "
            "note (one sentence, quote the words that cause the doubt).\n"
            "Returns: {recorded: true}.\n"
            "Failure modes: none; paths that do not exist are recorded as given."),
        "input_schema": {"type": "object", "additionalProperties": False,
                         "properties": {"target_path": {"type": "string"},
                                        "reason_type": {"type": "string", "enum": UNCERTAINTY_TYPES},
                                        "note": {"type": "string"}},
                         "required": ["target_path", "reason_type", "note"]},
    },
]


# ------------------------------------------------------------------------------------------------ implementations

def lookup_tax_rule(province: str, date: str) -> dict:
    rule = TAX["provinces"].get(province)
    if rule is None:
        return {"province": province, "country": country(province), "components": [],
                "note": TAX["non_canadian"] if country(province) != "CA" else "no rule"}
    comps = [{"name": k.upper(), "rate": v} for k, v in rule.items() if k in ("gst", "hst", "pst", "qst")]
    in_window = TAX["effective"]["from"] <= date <= TAX["effective"]["to"]
    return {"province": province, "country": "CA", "components": comps,
            "provincial_tax_applies_to_freight": rule.get("pst_applies_to_freight", "n/a"),
            "note": "" if in_window else "date outside the table's window"}


@dataclass
class Example:
    example_id: str
    shipment_id: str
    carrier: str
    marked_text: str
    submission: dict
    note: str = ""


def _template(s: str) -> set[str]:
    s = re.sub(r"\[[#D?]\d+ [^\]]*\]", " N ", s)
    return set(re.findall(r"[A-Z]+", s.upper()))


def find_similar_examples(query: str, k: int, library: list[Example], exclude_shipment: str,
                          exclude_carrier: str | None = None) -> list[dict]:
    """Jaccard over word sets with numbers masked. exclude_carrier is set in leave-one-carrier-out runs only."""
    q = _template(query)
    pool = [e for e in library if e.shipment_id != exclude_shipment and e.carrier != exclude_carrier]
    scored = sorted(pool, key=lambda e: -len(q & _template(e.marked_text)) / max(len(q | _template(e.marked_text)), 1))
    return [{"example_id": e.example_id, "marked_text": e.marked_text, "submission": e.submission, "note": e.note}
            for e in scored[: max(1, min(k, 5))]]


# ------------------------------------------------------------------------------------------------ controller

@dataclass
class Session:
    """State of one record's agent run. Tool results are logged; only accepted/failed answers go to the record."""
    ctx: Ctx
    max_retries: int = RULES["retry"]["max_retries"]
    attempts: list[dict] = field(default_factory=list)
    reconcile_calls: list[tuple] = field(default_factory=list)
    tool_log: list[dict] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    final: dict | None = None     # {"status": passed|failed, "submission", "claim", "record_diags"}

    # -- reconcile
    def reconcile(self, counted_ids: list[str], total_ids: list[str], tax_named_without_amount: bool) -> dict:
        self.reconcile_calls.append((tuple(sorted(counted_ids)), tuple(sorted(total_ids)), tax_named_without_amount))
        left = RULES["agent"]["reconcile_max_calls"] - len(self.reconcile_calls)
        if left < 0:
            res = {"error": "reconcile limit reached", "calls_left": 0}
        else:
            vals = {n.id: n.value for n in self.ctx.parse.numbers}
            unknown = [i for i in counted_ids + total_ids if i not in vals]
            s = sum((vals[i] for i in counted_ids if i in vals), Decimal("0"))
            rate, prov = tax_rate(self.ctx, set())
            exp = (s * rate).quantize(Decimal("0.01")) if (rate is not None and tax_named_without_amount) else None
            target = s + (exp or 0)
            res = {"claimed_sum": str(s), "delta": str(self.ctx.delta), "difference": str(abs(self.ctx.delta) - s),
                   "matches_delta": abs(abs(self.ctx.delta) - s) <= Decimal("0.005") or (exp is not None and abs(abs(self.ctx.delta) - target) <= TAX_TOL),
                   "expected_tax": str(exp) if exp is not None else None,
                   "totals": [{"id": t, "value": str(vals[t]), "consistent_with_items": abs(vals[t] - s) <= TAX_TOL or abs(vals[t] - target) <= TAX_TOL}
                              for t in total_ids if t in vals],
                   "unknown_ids": unknown, "calls_left": left}
        self.tool_log.append({"tool": "reconcile", "input": [counted_ids, total_ids, tax_named_without_amount], "result": res})
        return res

    # -- report_uncertainty
    def report_uncertainty(self, target_path: str, reason_type: str, note: str) -> dict:
        self.diagnostics.append(diag("RUN.AGENT.UNCERTAINTY_REPORTED", ObjectType.RUN, target_path,
                                     {"target_path": target_path, "reason_type": reason_type, "note": note}, "3"))
        self.tool_log.append({"tool": "report_uncertainty", "input": [target_path, reason_type, note]})
        return {"recorded": True}

    # -- submit
    def submit(self, payload: dict) -> dict:
        n = len(self.attempts) + 1
        try:
            sub = Submission.model_validate(payload)
        except ValidationError as e:
            errs = [ReceiptError(code="RUN.SUBMIT.SCHEMA_INVALID", object_type=ObjectType.RUN, path=".".join(map(str, x["loc"])),
                                 evidence={"msg": x["msg"]}, allowed_fixes=["follow the tool schema"]) for x in e.errors()[:10]]
            return self._reject(n, payload, None, errs, [], None)
        errs, rec, claim = check_submission(self.ctx, sub)
        unchanged = bool(self.attempts) and json.dumps(payload, sort_keys=True, default=str) == \
            json.dumps(self.attempts[-1]["payload"], sort_keys=True, default=str)
        if not errs:
            if n > 1:
                rec.append(diag("CLAIM.RECON.PASSED_AFTER_RETURN", ObjectType.CLAIM, "claim",
                                {"attempt": n, "changed_fields": diff(self.attempts[0]["payload"], payload)}, "4-5"))
            self.attempts.append({"payload": payload, "errors": []})
            self.final = {"status": "passed", "submission": sub, "claim": claim, "record_diags": rec}
            self.tool_log.append({"tool": "submit_line_items", "attempt": n, "result": "accepted"})
            return {"accepted": True}
        if unchanged and RULES["retry"]["stop_on_unchanged_resubmission"]:
            return self._fail(n, payload, sub, errs, rec, claim, reason="unchanged resubmission")
        return self._reject(n, payload, sub, errs, rec, claim)

    def _reject(self, n, payload, sub, errs, rec, claim) -> dict:
        self.attempts.append({"payload": payload, "errors": [e.model_dump() for e in errs]})
        retries_left = self.max_retries - (n - 1)
        if retries_left <= 0:
            return self._fail(n, payload, sub, errs, rec, claim, reason="retries exhausted", append=False)
        receipt = RepairReceipt(attempt=n, retries_left=retries_left, errors=errs)
        self.tool_log.append({"tool": "submit_line_items", "attempt": n, "result": "receipt", "receipt": receipt.model_dump(mode="json")})
        return receipt.model_dump(mode="json")

    def _fail(self, n, payload, sub, errs, rec, claim, reason, append=True) -> dict:
        if append:
            self.attempts.append({"payload": payload, "errors": [e.model_dump() for e in errs]})
        rec = list(rec) + [diag("RUN.SUBMIT.FAILED", ObjectType.RUN, "run",
                                {"attempts": n, "reason": reason, "last_errors": [{"code": e.code, "path": e.path, "evidence": e.evidence} for e in errs]}, "4-5")]
        self.final = {"status": "failed", "submission": sub, "claim": claim, "record_diags": rec}
        self.tool_log.append({"tool": "submit_line_items", "attempt": n, "result": "failed", "reason": reason})
        return {"accepted": False, "final": True, "message": "Processing stopped; the record goes to a human reviewer with your last answer."}

    def finish(self) -> tuple[str, Submission | None, object, list[Diagnostic]]:
        d = list(self.diagnostics)
        if len(self.reconcile_calls) > RULES["agent"]["reconcile_max_calls"] or len(set(self.reconcile_calls)) >= RULES["agent"]["reconcile_max_calls"]:
            d.append(diag("RUN.TOOL.RECONCILE_OVERUSE", ObjectType.RUN, "run",
                          {"calls": len(self.reconcile_calls), "distinct_hypotheses": len(set(self.reconcile_calls))}, "3"))
        if self.final is None:
            d.append(diag("RUN.SUBMIT.NONE", ObjectType.RUN, "run", {"turns": RULES["agent"]["max_turns"]}, "3"))
            return "failed", None, None, d
        return self.final["status"], self.final["submission"], self.final["claim"], d + self.final["record_diags"]


def diff(a: dict, b: dict) -> list[dict]:
    """Field-level changes between two submissions, keyed by number id / line item index."""
    out = []
    na = {x["id"]: x for x in a.get("numbers", [])}
    for x in b.get("numbers", []):
        y = na.get(x["id"])
        if y is None:
            out.append({"id": x["id"], "change": "added"})
            continue
        for f in ("kind", "status", "charge_codes"):
            if x.get(f) != y.get(f):
                out.append({"id": x["id"], "field": f, "from": y.get(f), "to": x.get(f)})
    if len(a.get("line_items", [])) != len(b.get("line_items", [])):
        out.append({"line_items": f"{len(a.get('line_items', []))} -> {len(b.get('line_items', []))}"})
    return out


assert all(CATALOG[c]["handling"] in ("return", "record") for c in CATALOG if c != "version")
assert Handling.RETURN.value == "return"
