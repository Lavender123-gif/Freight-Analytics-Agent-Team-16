"""P3 blind parsing and L1 agent loop, with a scripted fake client (no API calls).

Checks: Delta never reaches the model (schema, prompt, tools, every request actually built); a submission that passes
the mandatory checks ends the session whatever the Excel columns say (task 14 C1: no comparison with Delta, no
'inconsistent' feedback); a failed check is returned for repair; every attempt is kept, the first included."""

import json
from decimal import Decimal

import anthropic

from freight_lineitems import budget
from freight_lineitems import agent as agent_module
from freight_lineitems.agent import Session, run_agent
from freight_lineitems.pipeline import assemble, prepare, render_examples
from freight_lineitems.schemas import LLMInput
from freight_lineitems.tools import TOOLS

from helpers import L, N, S, record

SKILL_TEXT = (__import__("freight_lineitems.config", fromlist=["SKILL_PATH"]).SKILL_PATH).read_text()


class FakeClient:
    """Plays a fixed list of tool calls, one per model turn; records every request it receives."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.messages = self

    def create(self, **kw):
        self.requests.append(json.loads(json.dumps(kw, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o))))
        if not self.script:
            content, stop = [{"type": "text", "text": "done"}], "end_turn"
        else:
            name, inp = self.script.pop(0)
            content, stop = [{"type": "tool_use", "id": f"tu{len(self.requests)}", "name": name, "input": inp}], "tool_use"
        return anthropic.types.Message.model_validate({
            "id": f"m{len(self.requests)}", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
            "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}})


def run(text, delta, script):
    rec = record(text, delta)
    prep = prepare(rec)
    sess = Session(ctx=prep["ctx"], llm_input=prep["llm_input"])
    fc = FakeClient(script)
    tr = run_agent(sess, "SYSTEM", fc, {"model": "claude-sonnet-5-5", "max_tokens": 100}, budget.UsageBook(), [], set(), None)
    return prep, sess, tr, fc


GOOD = S([N("#1", codes=["DETENTION_STORAGE.DRIVER_DETENTION"], ev="DRIVER DETENTION")], [L("#1")])


def test_llm_input_schema_has_no_delta_or_amount_fields():
    fields = set(LLMInput.model_fields)
    assert not {f for f in fields if "delta" in f or "amount" in f or "carrier" in f or "reason" in f}


def test_skill_and_tools_never_mention_delta():
    assert "delta" not in SKILL_TEXT.lower()
    assert "delta" not in json.dumps(TOOLS).lower()


def test_delta_value_never_appears_in_any_request():
    _, sess, tr, fc = run("DRIVER DETENTION CHG $41.20", "987.65", [("submit_line_items", GOOD)])
    blob = json.dumps(fc.requests)
    assert "987.65" not in blob and "987" not in blob.replace("987.65", "")
    assert sess.final == {"status": "PASSED_CHECKS", "attempt_no": 1}


def test_passing_checks_ends_the_session_whatever_delta_says():
    """Task 14 C1: a reading that differs from the Excel Delta is accepted; nothing is fed back to the model."""
    for delta in ("41.20", "50.00", "0"):
        _, sess, tr, fc = run("DRIVER DETENTION CHG $41.20", delta, [("submit_line_items", GOOD), ("submit_line_items", GOOD)])
        assert sess.final == {"status": "PASSED_CHECKS", "attempt_no": 1}
        assert len(fc.requests) == 1
        assert json.loads(tr["calls"][0]["tool_results"][0]["content"]) == {"accepted": True}
        assert "inconsistent" not in json.dumps([c.get("tool_results") for c in tr["calls"]]).lower()


def test_no_delta_machinery_left():
    from freight_lineitems.config import RULES
    assert not hasattr(agent_module, "DeltaJudge") and not hasattr(agent_module, "INCONSISTENT_MESSAGE")
    assert not [c for c in RULES["flags"] if c.startswith("CLAIM.DELTA.") or c.startswith("REC.FIELD.DELTA_")]
    assert "max_delta_feedback_rounds" not in RULES["agent"]


def test_revision_after_a_failed_check_keeps_the_first_attempt():
    text = "FEE $10.00 AND FEE $12.00"
    bad = S([N("#1", ev="NOT IN TEXT"), N("#2", ev="FEE")], [L("#1"), L("#2")])
    good = S([N("#1", ev="FEE"), N("#2", ev="FEE")], [L("#1"), L("#2")], rtype="REVISED", reason="evidence fixed")
    prep, sess, tr, _ = run(text, "10.00", [("submit_line_items", bad), ("submit_line_items", good)])
    assert sess.final == {"status": "PASSED_CHECKS", "attempt_no": 2}
    assert sess.attempts[0]["raw_submission"] == bad and not sess.attempts[0]["checks_passed"]
    out = assemble(prep, {"session": sess, "transcript": tr})
    assert not [f for f in out["judgment"]["flags"] if f["code"].startswith("CLAIM.DELTA")]
    assert "delta_consistency" not in out["facts"] and "first_check" not in out["facts"]


def test_insisted_must_be_unchanged_and_reason_required():
    text = "FEE $10.00 AND FEE $12.00"
    first = S([N("#1", ev="FEE"), N("#2", ev="FEE")], [L("#1"), L("#2")])
    changed = S([N("#1", ev="FEE"), N("#2", status="PAID", ev="FEE", excl="FEE")], [L("#1")], rtype="INSISTED", reason="x")
    bad = S([N("#1", ev="NOT IN TEXT"), N("#2", ev="FEE")], [L("#1"), L("#2")])
    first_changed = dict(changed, numbers=[N("#1", ev="FEE"), N("#2", ev="FEE")], line_items=[L("#1"), L("#2")])
    _, sess, tr, _ = run(text, "10.00", [("submit_line_items", bad), ("submit_line_items", first_changed)])
    res = json.loads(tr["calls"][1]["tool_results"][0]["content"])
    assert res["result"] == "checks_failed" and res["errors"][0]["code"] == "RUN.SUBMIT.INSISTED_BUT_CHANGED"
    _, sess, tr, _ = run(text, "10.00", [("submit_line_items", bad), ("submit_line_items", dict(bad, response_type="INSISTED"))])
    res = json.loads(tr["calls"][1]["tool_results"][0]["content"])
    assert "RUN.SUBMIT.REASON_MISSING" in {e["code"] for e in res["errors"]}


def test_repairs_exhausted_fail_explicitly():
    bad = S([N("#1", ev="NOT IN TEXT")], [L("#1")])
    prep, sess, tr, _ = run("DRIVER DETENTION CHG $41.20", "41.20", [("submit_line_items", bad)] * 3)
    assert sess.final["status"] == "FAILED_CHECKS" and len(sess.attempts) == 3
    out = assemble(prep, {"session": sess, "transcript": tr})
    assert "RUN.SUBMIT.FAILED_CHECKS" in {f["code"] for f in out["judgment"]["flags"]}
    assert out["judgment"]["recommendation"] == "HUMAN_REVIEW"


def test_no_submission_is_flagged_not_dropped():
    prep, sess, tr, fc = run("DRIVER DETENTION CHG $41.20", "41.20", [])
    out = assemble(prep, {"session": sess, "transcript": tr})
    assert "RUN.SUBMIT.NONE" in {f["code"] for f in out["judgment"]["flags"]}
    assert len(fc.requests) == 2      # one nudge, then stop


def test_empty_text_still_reaches_the_model_and_zero_delta_is_not_a_flag():
    prep, sess, tr, fc = run("", "0", [("submit_line_items", S([], []))])
    assert len(fc.requests) == 1 and sess.final["status"] == "PASSED_CHECKS"
    out = assemble(prep, {"session": sess, "transcript": tr})
    assert out["judgment"]["recommendation"] == "RETURN_SUGGESTED"       # REC.TEXT.EMPTY decides, not Delta
    assert not [f for f in out["judgment"]["flags"] if "DELTA" in f["code"]]


def test_tool_calls_dispatch():
    _, sess, tr, _ = run("DRIVER DETENTION CHG $41.20", "41.20",
                         [("calculate", {"expression": "2 * 20.6"}), ("lookup_charge_code", {"phrase": "DRIVER DETENTION"}),
                          ("report_uncertainty", {"target_path": "numbers/#1", "reason_type": "other", "note": "n"}),
                          ("submit_line_items", GOOD)])
    assert json.loads(tr["calls"][0]["tool_results"][0]["content"]) == {"result": "41.2"}
    assert json.loads(tr["calls"][1]["tool_results"][0]["content"])["matches"][0]["code"] == "DETENTION_STORAGE.DRIVER_DETENTION"
    assert sess.uncertainty and sess.uncertainty[0].origin == "MODEL_REPORTED"


def test_render_examples_contains_no_delta():
    ex = [{"example_id": "E1", "record_id": "x", "marked_text": "FEE [#1 $5]", "reading": {"a": 1}, "note": "n"}]
    assert "delta" not in render_examples(ex).lower()


def test_schema_invalid_submission_is_returned_then_fails_explicitly():
    bad = {"response_type": "FIRST", "numbers": "not a list"}
    prep, sess, tr, _ = run("DRIVER DETENTION CHG $41.20", "41.20", [("submit_line_items", bad)] * 3)
    assert sess.attempts[0]["repair_errors"][0]["code"] == "RUN.SUBMIT.SCHEMA_INVALID"
    assert sess.final["status"] == "FAILED_CHECKS"


def test_exception_mid_session_keeps_attempts():
    """Audit M1: a crash after a submission keeps that attempt and the calls, and is flagged."""
    class Boom(FakeClient):
        def create(self, **kw):
            if len(self.requests) >= 1:
                raise ValueError("boom")
            return super().create(**kw)
    rec = record("FEE $10.00 AND FEE $12.00", "10.00")
    prep = prepare(rec)
    sess = Session(ctx=prep["ctx"], llm_input=prep["llm_input"])
    first = S([N("#1", ev="NOT IN TEXT"), N("#2", ev="FEE")], [L("#1"), L("#2")])   # fails a check: a second call follows
    tr = run_agent(sess, "S", Boom([("submit_line_items", first)]), {"model": "m", "max_tokens": 10}, budget.UsageBook(), [], set(), None)
    assert len(sess.attempts) == 1 and len(tr["calls"]) == 1
    out = assemble(prep, {"session": sess, "transcript": tr})
    assert out["process"]["attempts"][0]["raw_submission"] == first
    assert "RUN.MODEL.ERROR" in {f["code"] for f in out["judgment"]["flags"]}


def test_response_type_protocol():
    """Audit L1."""
    _, sess, tr, _ = run("DRIVER DETENTION CHG $41.20", "41.20", [("submit_line_items", dict(GOOD, response_type="INSISTED", reason="x"))])
    assert json.loads(tr["calls"][0]["tool_results"][0]["content"])["errors"][0]["code"] == "RUN.SUBMIT.RESPONSE_TYPE_INVALID"
    text = "FEE $10.00 AND FEE $12.00"
    first = S([N("#1", ev="FEE"), N("#2", ev="FEE")], [L("#1"), L("#2")])
    bad = S([N("#1", ev="NOT IN TEXT"), N("#2", ev="FEE")], [L("#1"), L("#2")])
    _, sess, tr, _ = run(text, "10.00", [("submit_line_items", bad), ("submit_line_items", dict(bad, response_type="REVISED", reason="r"))])
    assert "RUN.SUBMIT.REVISED_BUT_UNCHANGED" in {e["code"] for e in json.loads(tr["calls"][1]["tool_results"][0]["content"])["errors"]}
    _, sess, tr, _ = run(text, "10.00", [("submit_line_items", bad), ("submit_line_items", first)])
    assert json.loads(tr["calls"][1]["tool_results"][0]["content"])["errors"][0]["code"] == "RUN.SUBMIT.RESPONSE_TYPE_INVALID"
