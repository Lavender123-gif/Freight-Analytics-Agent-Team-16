"""Steps 0-7 for one record. Step 3 is pluggable: `play` receives (session, llm_input) and drives the tools.
In this prototype `play` is either None (code-only run) or a hand-written role-play (walkthrough.py).
"""

from __future__ import annotations

from typing import Callable

from checks import Ctx, step2_diagnostics
from config import VERSIONS
from disposition import aggregate, decide, reason_code_conflict, reject_draft
from gate import gate
from history import HistEntry, history_diagnostics
from number_parse import parse
from schemas import (COUNTED_STATUSES, LLMInput, LLMNumberView, Kind, Record, RunInfo, Submission)
from tools import Session

Play = Callable[[Session, LLMInput], None]


def build_llm_input(rec: dict, p) -> LLMInput:
    s = rec["source"]
    d = s["delta"]
    return LLMInput(
        redacted_text=rec["text"]["redacted"], marked_text=p.marked_text,
        numbers=[LLMNumberView(**{k: getattr(n, k) for k in LLMNumberView.model_fields}) for n in p.numbers],
        unrecognized=p.unrecognized, delta=d,
        delta_sign="positive" if d > 0 else "zero" if d == 0 else "negative",
        origin_province=s["origin_state"], destination_province=s["destination_state"])


def claimed_codes(sub: Submission | None) -> set[str] | None:
    """Charge codes of the amounts this dispute asks for (history numbers excluded)."""
    if sub is None:
        return None
    return {c for j in sub.numbers if j.status in COUNTED_STATUSES for c in j.charge_codes} | \
           {c for li in sub.line_items for c in li.charge_codes}


def process(ev_row, earlier: list[HistEntry], play: Play | None = None) -> tuple[Record, dict]:
    rec, diags = gate(ev_row)
    s = rec["source"]
    text = rec["text"]["redacted"]
    p = parse(text)
    ctx = Ctx(record_id=s["record_id"], text=text, parse=p, delta=s["delta"], origin_state=s["origin_state"],
              destination_state=s["destination_state"], event_date=s["event_date"])
    diags += step2_diagnostics(ctx)
    hist_pre = history_diagnostics(s["record_id"], ev_row.ts, s["delta"], text, p, earlier)
    trace: dict = {"rounds": []}

    pre_flags = aggregate(diags + hist_pre)
    pre = decide(pre_flags)
    llm_input = None
    content = claim = None
    if pre.outcome == "AUTO_REJECT":
        run = RunInfo(status="not_run_auto_reject", submissions=0, reconcile_calls=0, tool_calls=[], model=None, prompt_version=None)
        diags += hist_pre
    elif play is None:
        run = RunInfo(status="not_run", submissions=0, reconcile_calls=0, tool_calls=[], model=None, prompt_version=None)
        diags += hist_pre
    else:
        llm_input = build_llm_input(rec, p)
        sess = Session(ctx)
        play(sess, llm_input)
        status, content, claim, run_diags = sess.finish()
        trace["rounds"] = sess.tool_log
        run = RunInfo(status=status, submissions=len(sess.attempts), reconcile_calls=len(sess.reconcile_calls),
                      tool_calls=[t["tool"] for t in sess.tool_log], model="role-played (not a model run)",
                      prompt_version="SKILL.md draft v0.1")
        diags += run_diags
        if content is not None and claim is not None:
            values = {n.id: n.value for n in p.numbers} | {r.region_id: r.value for r in content.unrecognized_reads if r.value is not None}
            claimed = [(j.id, values[j.id]) for j in content.numbers if j.status in COUNTED_STATUSES and j.kind != Kind.TOTAL]
            hist_post = history_diagnostics(s["record_id"], ev_row.ts, s["delta"], text, p, earlier, claimed=claimed,
                                            codes=claimed_codes(content))
            diags += hist_post
            claim.history_relations = sorted({d.code for d in hist_post})
        else:
            diags += hist_pre
        diags += reason_code_conflict(s["reason_code"], content)

    flags = aggregate(diags)
    disp = decide(flags)
    record = Record(source=s, text=rec["text"], parse=p, llm_input=llm_input, run=run, content=content, claim=claim,
                    diagnostics=diags, flags=flags, disposition=disp, reject_draft=reject_draft(flags, disp),
                    versions=VERSIONS | {"prompt": run.prompt_version or "", "model": run.model or ""})
    return record, trace
