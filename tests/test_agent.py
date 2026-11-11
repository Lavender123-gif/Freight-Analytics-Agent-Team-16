"""P3 blind parsing and L1 agent loop, with a scripted fake client (no API calls).

Checks: Delta never reaches the model (schema, prompt, tools, every request actually built); the model is told only
'inconsistent'; it may insist or revise; every attempt is kept, the first included."""

import json
from decimal import Decimal

import anthropic

from freight_lineitems import budget
from freight_lineitems.agent import INCONSISTENT_MESSAGE, DeltaJudge, Session, run_agent
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
    sess = Session(ctx=prep["ctx"], judge=DeltaJudge(rec.delta), llm_input=prep["llm_input"])
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
    _, sess, tr, fc = run("DRIVER DETENTION CHG $41.20", "987.65", [("submit_line_items", GOOD), ("submit_line_items", dict(GOOD, response_type="INSISTED", reason="text says 41.20"))])
    blob = json.dumps(fc.requests)
    assert "987.65" not in blob and "987" not in blob.replace("987.65", "")
    assert sess.final["delta_consistency"] == "MISMATCH_MODEL_INSISTED"


def test_match_first_passes():
    _, sess, _, fc = run("DRIVER DETENTION CHG $41.20", "41.20", [("submit_line_items", GOOD)])
    assert sess.final == {"status": "PASSED_CHECKS", "delta_consistency": "MATCH_FIRST", "attempt_no": 1}
    assert len(fc.requests) == 1


def test_inconsistent_feedback_is_only_the_fixed_message():
    _, sess, tr, _ = run("DRIVER DETENTION CHG $41.20", "50.00", [("submit_line_items", GOOD)])
    res = json.loads(tr["calls"][0]["tool_results"][0]["content"])
    assert res == {"accepted": False, "result": "inconsistent", "message": INCONSISTENT_MESSAGE, "resubmissions_left": 1}
    assert sess.attempts[0]["feedback_given"] == INCONSISTENT_MESSAGE


def test_revision_after_feedback_keeps_first_attempt_and_flags_changes():
    text = "FEE $10.00 AND FEE $12.00"
    first = S([N("#1", ev="FEE"), N("#2", ev="FEE")], [L("#1"), L("#2")])
    second = S([N("#1", ev="FEE"), N("#2", status="PAID", ev="FEE", excl="FEE")], [L("#1")], rtype="REVISED", reason="#2 is history")
    prep, sess, tr, _ = run(text, "10.00", [("submit_line_items", first), ("submit_line_items", second)])
    assert sess.final["delta_consistency"] == "MATCH_AFTER_REVISION"
    assert [a["delta_check"] for a in sess.attempts] == ["MISMATCH", "MATCH"]
    assert sess.attempts[0]["raw_submission"] == first          # first attempt kept, not overwritten
    out = assemble(prep, {"session": sess, "transcript": tr})
    codes = {f["code"] for f in out["judgment"]["flags"]}
    assert {"CLAIM.DELTA.FIRST_MISMATCH", "CLAIM.DELTA.MATCH_AFTER_REVISION", "CLAIM.ATTEMPT.STATUS_CHANGED"} <= codes
    assert out["judgment"]["recommendation"] == "HUMAN_REVIEW"
    assert out["facts"]["first_check"] == "MISMATCH"


def test_insisted_must_be_unchanged_and_reason_required():
    text = "FEE $10.00 AND FEE $12.00"
    first = S([N("#1", ev="FEE"), N("#2", ev="FEE")], [L("#1"), L("#2")])
    changed = S([N("#1", ev="FEE"), N("#2", status="PAID", ev="FEE", excl="FEE")], [L("#1")], rtype="INSISTED", reason="x")
    _, sess, tr, _ = run(text, "10.00", [("submit_line_items", first), ("submit_line_items", changed)])
    res = json.loads(tr["calls"][1]["tool_results"][0]["content"])
    assert res["result"] == "checks_failed" and res["errors"][0]["code"] == "RUN.SUBMIT.INSISTED_BUT_CHANGED"
    _, sess, tr, _ = run(text, "10.00", [("submit_line_items", first), ("submit_line_items", dict(first, response_type="INSISTED"))])
    res = json.loads(tr["calls"][1]["tool_results"][0]["content"])
    assert res["errors"][0]["code"] == "RUN.SUBMIT.REASON_MISSING"


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


def test_zero_delta_has_no_anchor_and_empty_text_still_reaches_the_model():
    _, sess, _, fc = run("", "0", [("submit_line_items", S([], []))])
    assert len(fc.requests) == 1 and sess.final["delta_consistency"] == "NO_ANCHOR"


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


def test_judge_with_implied_tax():
    from freight_lineitems.checks import ClaimCalc
    c = ClaimCalc(counted_ids=["#1"], signed_sum=Decimal("20.00"), base_sum=Decimal("20.00"), tax_items_without_amount=1,
                  expected_tax=Decimal("2.60"), totals={})
    assert DeltaJudge(Decimal("22.60")).judge(c) == "MATCH"
    assert DeltaJudge(Decimal("23.60")).judge(c) == "MISMATCH"


def test_difference_matching_amounts_goes_to_reviewer_only():
    """User requirement c: the gap equals one amount in the text; shown to the reviewer, never to the model."""
    text = "LINE HAUL $2000 CHASSIS $100 STORAGE $60"
    s = S([N("#1", codes=["LINEHAUL.BASE"], ev="LINE HAUL"), N("#2", codes=["DRAYAGE.CHASSIS"], ev="CHASSIS"),
           N("#3", codes=["DETENTION_STORAGE.TERMINAL_STORAGE"], ev="STORAGE")], [L("#1"), L("#2"), L("#3")])
    prep, sess, tr, fc = run(text, "2100.00", [("submit_line_items", s), ("submit_line_items", dict(s, response_type="INSISTED", reason="all listed"))])
    out = assemble(prep, {"session": sess, "transcript": tr})
    f = next(f for f in out["judgment"]["flags"] if f["code"] == "CLAIM.DELTA.DIFFERENCE_MATCHES_AMOUNTS")
    assert f["evidence"][0]["matching_amounts"][0] == [{"id": "#3", "raw": "$60"}]
    blob = json.dumps(fc.requests) + json.dumps([c.get("tool_results") for c in tr["calls"]])
    assert "MATCHES_AMOUNTS" not in blob and "-60" not in blob and "2100" not in blob


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
    sess = Session(ctx=prep["ctx"], judge=DeltaJudge(rec.delta), llm_input=prep["llm_input"])
    first = S([N("#1", ev="FEE"), N("#2", ev="FEE")], [L("#1"), L("#2")])
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
    _, sess, tr, _ = run(text, "10.00", [("submit_line_items", first), ("submit_line_items", dict(first, response_type="REVISED", reason="r"))])
    assert json.loads(tr["calls"][1]["tool_results"][0]["content"])["errors"][0]["code"] == "RUN.SUBMIT.REVISED_BUT_UNCHANGED"
    _, sess, tr, _ = run(text, "10.00", [("submit_line_items", first), ("submit_line_items", first)])
    assert json.loads(tr["calls"][1]["tool_results"][0]["content"])["errors"][0]["code"] == "RUN.SUBMIT.RESPONSE_TYPE_INVALID"
