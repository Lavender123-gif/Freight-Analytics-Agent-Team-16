"""The agent loop (L1) and the submission controller (P3 blind parsing).

One record = one Session. The model sees the blind input and calls tools. `submit_line_items` runs the mandatory
checks; a submission that passes them ends the session. A submission that fails them is returned to the model with
the errors, at most `agent.max_repair_rounds` times. Every attempt is kept, the first included, and nothing is
overwritten.

The model is never told how its reading compares with any amount from the Excel row (task 14, C1: the Excel
amount columns are the client's own estimates and are used only as a baseline in evaluation).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import anthropic
from pydantic import ValidationError

from freight_lineitems.budget import UsageBook
from freight_lineitems.checks import Ctx, attempt_changes, check_submission, diag, reading_key
from freight_lineitems.config import RULES
from freight_lineitems.schemas import Diagnostic, LLMInput, RepairError, Submission
from freight_lineitems import tools as T

AG = RULES["agent"]


@dataclass
class Session:
    ctx: Ctx
    llm_input: LLMInput
    attempts: list[dict] = field(default_factory=list)
    uncertainty: list[Diagnostic] = field(default_factory=list)
    refused_reports: list[dict] = field(default_factory=list)   # over the limit; still shown to the reviewer (audit L2)
    repair_rounds: int = 0
    final: dict | None = None    # {"status", "attempt_no"}

    # ---------------------------------------------------------------- submit_line_items
    def submit(self, payload: dict) -> dict:
        n = len(self.attempts) + 1
        att = {"attempt_no": n, "raw_submission": payload, "repair_errors": [], "checks_passed": False,
               "response_type": payload.get("response_type"), "record_diagnostics": [],
               "claim": None}
        self.attempts.append(att)
        try:
            sub = Submission.model_validate(payload)
        except ValidationError as e:
            errs = [RepairError(code="RUN.SUBMIT.SCHEMA_INVALID", path=".".join(map(str, x["loc"])), evidence={"msg": x["msg"]},
                                allowed_fixes=["follow the tool schema"]) for x in e.errors()[:10]]
            return self._repair(att, errs)
        errs = self._protocol_errors(sub, n)
        cerrs, rec, claim = check_submission(self.ctx, sub)
        errs += cerrs
        att["record_diagnostics"] = [d.model_dump() for d in rec]
        att["reading_key"] = reading_key(sub)
        if claim is not None:
            att["claim"] = {"counted_ids": claim.counted_ids, "signed_sum": str(claim.signed_sum),
                            "expected_tax": str(claim.expected_tax) if claim.expected_tax is not None else None}
        if errs:
            return self._repair(att, errs)
        att["checks_passed"] = True
        att["_sub"], att["_claim"], att["_rec"] = sub, claim, rec
        return self._finish("PASSED_CHECKS", att)

    def _protocol_errors(self, sub: Submission, n: int) -> list[RepairError]:
        errs = []
        # audit L1: attempt 1 is FIRST; every later attempt is REVISED or INSISTED with a reason
        if n == 1 and sub.response_type != "FIRST":
            errs.append(RepairError(code="RUN.SUBMIT.RESPONSE_TYPE_INVALID", path="response_type", evidence={"attempt": n,
                                    "given": sub.response_type}, allowed_fixes=["use response_type FIRST on the first submission"]))
        if n > 1 and sub.response_type == "FIRST":
            errs.append(RepairError(code="RUN.SUBMIT.RESPONSE_TYPE_INVALID", path="response_type", evidence={"attempt": n,
                                    "given": "FIRST"}, allowed_fixes=["use REVISED (changed reading) or INSISTED (unchanged) with a reason"]))
        if n > 1 and sub.response_type in ("REVISED", "INSISTED") and not (sub.reason or "").strip():
            errs.append(RepairError(code="RUN.SUBMIT.REASON_MISSING", path="reason", evidence={"response_type": sub.response_type},
                                    allowed_fixes=["say in reason what you misread (REVISED) or why the reading stands (INSISTED)"]))
        prev = next((a for a in reversed(self.attempts[:-1]) if a.get("reading_key")), None)
        if sub.response_type == "INSISTED" and prev is not None and prev["reading_key"] != reading_key(sub):
            errs.append(RepairError(code="RUN.SUBMIT.INSISTED_BUT_CHANGED", path="response_type", evidence={},
                                    allowed_fixes=["resubmit the previous reading unchanged", "or use response_type REVISED"]))
        if sub.response_type == "REVISED" and prev is not None and prev["reading_key"] == reading_key(sub):
            errs.append(RepairError(code="RUN.SUBMIT.REVISED_BUT_UNCHANGED", path="response_type", evidence={},
                                    allowed_fixes=["use response_type INSISTED if the reading stands", "or change the reading"]))
        return errs

    def _repair(self, att: dict, errs: list[RepairError]) -> dict:
        att["repair_errors"] = [e.model_dump() for e in errs]
        if self.repair_rounds >= AG["max_repair_rounds"]:
            return self._finish("FAILED_CHECKS", att)
        self.repair_rounds += 1
        return {"accepted": False, "result": "checks_failed", "errors": att["repair_errors"],
                "resubmissions_left": AG["max_repair_rounds"] - self.repair_rounds + 1}

    def _finish(self, status: str, att: dict) -> dict:
        self.final = {"status": status, "attempt_no": att["attempt_no"]}
        if status == "PASSED_CHECKS":
            return {"accepted": True}
        return {"accepted": False, "final": True,
                "message": "Processing has ended; your last reading goes to a human reviewer. Stop here."}

    # ---------------------------------------------------------------- other tools
    def report_uncertainty(self, target_path: str, reason_type: str, note: str) -> dict:
        if len(self.uncertainty) >= AG["max_uncertainty_reports"]:
            self.refused_reports.append({"target_path": target_path, "reason_type": reason_type, "note": note})
            return {"recorded": False, "error": "report limit reached; combine doubts into one earlier note"}
        self.uncertainty.append(diag("RUN.AGENT.UNCERTAINTY_REPORTED", target_path,
                                     {"reason_type": reason_type, "note": note}, "3", origin="MODEL_REPORTED"))
        return {"recorded": True}

    # ---------------------------------------------------------------- outcome
    def outcome_diagnostics(self) -> list[Diagnostic]:
        """Diagnostics about the run itself, for the reviewer (first attempt, revisions, final state)."""
        out: list[Diagnostic] = list(self.uncertainty)
        if self.refused_reports:
            out.append(diag("RUN.AGENT.UNCERTAINTY_OVER_LIMIT", "run", {"refused": self.refused_reports}, "3", origin="MODEL_REPORTED"))
        if self.final is None:
            out.append(diag("RUN.SUBMIT.NONE", "run", {"attempts": len(self.attempts)}, "3"))
            return out
        last = self.attempts[self.final["attempt_no"] - 1]
        if self.final["status"] == "FAILED_CHECKS":
            out.append(diag("RUN.SUBMIT.FAILED_CHECKS", "run", {"attempts": len(self.attempts),
                            "last_errors": [{"code": e["code"], "path": e["path"]} for e in last["repair_errors"]]}, "4"))
            return out
        valid = [a for a in self.attempts if a.get("checks_passed")]
        if len(valid) > 1:
            ch = attempt_changes(valid[0]["_sub"], last["_sub"])
            if ch:
                out.append(diag("CLAIM.ATTEMPT.STATUS_CHANGED", "attempts", {"changes": ch,
                                "from_attempt": valid[0]["attempt_no"], "to_attempt": last["attempt_no"]}, "4"))
        return out


# ------------------------------------------------------------------------------------------------ the loop

def _block_dump(b) -> dict:
    return b.model_dump(mode="json", exclude_none=True)


def run_agent(session: Session, system_prompt: str, client: anthropic.Anthropic, req_kw: dict, book: UsageBook,
              examples: list[dict], exclude_record_ids: set[str], shipment_key: str | None, preamble: str = "") -> dict:
    """Drive one record. Returns the transcript (every request's new messages and every response, with usage).
    `preamble` is what code chose for this record in the routed layout (topic notes, similar examples); it goes
    before the record in the first user message. `examples`, `exclude_record_ids` and `shipment_key` are no longer
    read by any tool (task 19 removed find_similar_examples); they stay in the signature for existing callers."""
    user_text = ("Here is one dispute record. Read it and submit your reading with submit_line_items.\n\n" + preamble +
                 "<dispute_record>\n" + session.llm_input.model_dump_json(indent=1) + "\n</dispute_record>")
    messages: list[dict] = [{"role": "user", "content": [{"type": "text", "text": user_text}]}]
    system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    calls: list[dict] = []
    events: list[Diagnostic] = []
    try:
        _loop(session, system, client, req_kw, book, examples, exclude_record_ids, shipment_key, messages, calls, events)
    except Exception as e:  # noqa: BLE001 - audit M1: keep attempts and calls made so far; flag explicitly
        events.append(diag("RUN.MODEL.ERROR", "run", {"error": type(e).__name__, "message": str(e)[:300],
                                                      "calls_before_error": len(calls)}, "3"))
    return {"calls": calls, "events": events, "first_user_message": user_text}


def _loop(session, system, client, req_kw, book, examples, exclude_record_ids, shipment_key, messages, calls, events):
    nudged = False
    for turn in range(AG["max_turns"]):
        t0 = time.time()
        try:
            resp = client.messages.create(system=system, tools=T.TOOLS, messages=messages,
                                          cache_control={"type": "ephemeral"}, **req_kw)
        except anthropic.APIError as e:
            events.append(diag("RUN.MODEL.ERROR", "run", {"turn": turn, "error": type(e).__name__,
                                                          "message": str(e)[:300]}, "3"))
            break
        book.add(resp.model, resp.usage)
        calls.append({"turn": turn, "model": resp.model, "stop_reason": resp.stop_reason, "seconds": round(time.time() - t0, 2),
                      "usage": resp.usage.model_dump(mode="json"), "content": [_block_dump(b) for b in resp.content],
                      "request_id": getattr(resp, "_request_id", None)})
        if resp.stop_reason in ("max_tokens", "pause_turn"):     # audit L2
            events.append(diag("RUN.MODEL.TRUNCATED", "run", {"turn": turn, "stop_reason": resp.stop_reason}, "3"))
        if resp.stop_reason == "refusal":
            events.append(diag("RUN.MODEL.REFUSAL", "run", {"turn": turn, "stop_details": getattr(resp, "stop_details", None) and
                                                            resp.stop_details.model_dump(mode="json")}, "3"))
            break
        messages.append({"role": "assistant", "content": resp.content})
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            if session.final is not None or nudged:
                break
            nudged = True
            nudge = "You have not called submit_line_items yet. Your reading is only recorded through that tool."
            messages.append({"role": "user", "content": [{"type": "text", "text": nudge}]})
            calls[-1]["nudge_after"] = nudge
            continue
        results = []
        for b in uses:
            res = dispatch(session, b.name, b.input, examples, exclude_record_ids, shipment_key)
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(res, default=str)})
        calls[-1]["tool_results"] = [{"tool_use_id": r["tool_use_id"], "content": r["content"]} for r in results]
        messages.append({"role": "user", "content": results})
        if session.final is not None:
            break
    else:
        events.append(diag("RUN.MODEL.ERROR", "run", {"error": "max_turns reached", "max_turns": AG["max_turns"]}, "3"))


def dispatch(session: Session, name: str, args: dict, examples: list[dict], exclude_record_ids: set[str],
             shipment_key: str | None) -> dict:
    if session.final is not None and name == "submit_line_items":
        return {"accepted": False, "final": True, "message": "Processing has already ended. Stop here."}
    if name == "submit_line_items":
        return session.submit(args)
    if name == "lookup_charge_code":
        return T.lookup_charge_code(args.get("phrase", ""))
    if name == "calculate":
        return T.calculate(args.get("expression", ""))
    if name == "report_uncertainty":
        return session.report_uncertainty(args.get("target_path", ""), args.get("reason_type", "other"), args.get("note", ""))
    return {"error": f"unknown tool {name}"}
