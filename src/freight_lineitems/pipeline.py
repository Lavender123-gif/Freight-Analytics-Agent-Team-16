"""One record through the whole pipeline, and the batch runner.

Every record goes through the model; there is no branch that skips or rejects a record before it (decision 2.1).
Output per record has three layers (decision 3.9 / task 06 C; P5 finalises the shape):
- facts: source fields as read, redacted text, number table, the final reading and line items, claim arithmetic;
- judgment: flags and the recommendation (rules only);
- process: every attempt (the first included), the full model transcript and usage.
Row-level output is written only under data/interim/runs/ (git-ignored).
"""

from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal

from freight_lineitems import budget, duplicates
from freight_lineitems.agent import DeltaJudge, Session, run_agent
from freight_lineitems.checks import Ctx, diag, reason_code_conflict, step2_diagnostics
from freight_lineitems.config import RUNS_DIR, SKILL_PATH, country, currency, versions
from freight_lineitems.disposition import flags_from, recommend
from freight_lineitems.numbers import parse
from freight_lineitems.records import InputRecord
from freight_lineitems.schemas import Diagnostic, LLMInput, LLMNumberView
from freight_lineitems.textprep import injection_hits, normalize, redact, redaction_altered_digits, sha256
from freight_lineitems.tools import load_examples, taxonomy_for_prompt


_PROMPT_SHA: dict = {}


def render_examples(examples: list[dict]) -> str:
    parts = []
    for e in examples:
        parts.append(f"### {e['example_id']}\nmarked_text: {e['marked_text']}\nreading: "
                     f"{json.dumps(e['reading'], separators=(',', ':'))}\nwhy: {e['note']}")
    return "\n\n".join(parts)


def system_prompt(examples: list[dict] | None = None) -> str:
    """SKILL.md with the taxonomy and the worked examples filled in. The examples are real dev-split text (redacted)
    and live in a git-ignored file; a missing file is an error, not an empty section."""
    ex = load_examples() if examples is None else examples
    if not ex:
        raise FileNotFoundError("worked examples missing: run data/interim/skill/build_examples.py")
    out = SKILL_PATH.read_text().replace("{{TAXONOMY}}", taxonomy_for_prompt()).replace("{{EXAMPLES}}", render_examples(ex))
    _PROMPT_SHA["sha"] = sha256(out)[:16]
    return out


def prepare(rec: InputRecord) -> dict:
    """Steps 1-2 (deterministic). Returns the prepared record; nothing here rejects a record."""
    t = normalize(rec.text_raw)
    red, n_p, n_e = redact(t)
    d: list[Diagnostic] = []
    if n_p or n_e:
        d.append(diag("REC.TEXT.PII_REDACTED", "text", {"n_person": n_p, "n_email": n_e}, "1"))
    if redaction_altered_digits(t, red):
        d.append(diag("REC.TEXT.REDACTION_ALTERED_DIGITS", "text", {}, "1"))
    if t == "":
        d.append(diag("REC.TEXT.EMPTY", "text", {}, "1"))
    if any(ord(c) > 126 for c in t):
        d.append(diag("REC.TEXT.NON_ASCII", "text", {"chars": sorted({c for c in t if ord(c) > 126})[:10]}, "1"))
    hits = injection_hits(t)
    if hits:
        d.append(diag("REC.TEXT.INJECTION_SUSPECT", "text", {"patterns_hit": hits}, "1"))
    if rec.delta is None:                       # audit M2: a missing Delta is flagged, never a crash
        d.append(diag("REC.FIELD.DELTA_MISSING", "source/delta", {}, "1"))
    elif rec.delta == 0:
        d.append(diag("REC.FIELD.DELTA_ZERO", "source/delta", {}, "1"))
    elif rec.delta < 0:
        d.append(diag("REC.FIELD.DELTA_NEGATIVE", "source/delta", {}, "1"))
    oc, dc = country(rec.origin_state), country(rec.destination_state)
    if oc != dc:
        d.append(diag("REC.FIELD.CROSS_BORDER", "source", {"origin_country": oc, "destination_country": dc}, "1"))
    cur = currency(oc, dc)
    if cur == "UNKNOWN":
        d.append(diag("REC.FIELD.CURRENCY_UNDETERMINED", "source", {"origin_country": oc, "destination_country": dc}, "1"))
    p = parse(red)
    ctx = Ctx(record_id=rec.record_id, text=red, parse=p, origin_state=rec.origin_state,
              destination_state=rec.destination_state, event_date=rec.event_date)
    d += step2_diagnostics(ctx)
    llm_input = LLMInput(
        redacted_text=red, marked_text=p.marked_text,
        numbers=[LLMNumberView(id=n.id, raw=n.raw, value=str(n.value), has_dollar=n.has_dollar, space_merged=n.space_merged,
                               leading_dot=n.leading_dot, trailing_dot=n.trailing_dot, decimals=n.decimals,
                               minus_before=n.minus_before, prev_symbol=n.prev_symbol, unit_hint=n.unit_hint)
                 for n in p.numbers],
        unrecognized=p.unrecognized, origin_province=rec.origin_state, destination_province=rec.destination_state)
    return {"rec": rec, "text_norm": t, "redacted": red, "n_person": n_p, "n_email": n_e, "parse": p, "ctx": ctx,
            "pre_diags": d, "llm_input": llm_input, "origin_country": oc, "destination_country": dc,
            "currency": currency(oc, dc)}


def _clean_attempt(a: dict) -> dict:
    return {k: v for k, v in a.items() if not k.startswith("_")}


def run_model(prep: dict, client, req_kw: dict, book: budget.UsageBook, sys_prompt: str, examples: list[dict],
              exclude_record_ids: set[str]) -> dict:
    rec: InputRecord = prep["rec"]
    sess = Session(ctx=prep["ctx"], judge=DeltaJudge(rec.delta if rec.delta is not None else Decimal("0")),
                   llm_input=prep["llm_input"])
    tr = run_agent(sess, sys_prompt, client, req_kw, book, examples, exclude_record_ids | {rec.record_id}, rec.shipment_key)
    return {"session": sess, "transcript": tr}


def assemble(prep: dict, model_out: dict | None, extra_diags: list[Diagnostic] | None = None) -> dict:
    """Build the output record (facts / judgment / process) from the prepared record and the model run."""
    rec: InputRecord = prep["rec"]
    p = prep["parse"]
    diags: list[Diagnostic] = list(prep["pre_diags"]) + list(extra_diags or [])
    process: dict = {"model_ran": model_out is not None}
    final_reading = None
    claim = None
    status, dc = "NOT_RUN", "NOT_EVALUATED"
    if model_out is not None:
        sess: Session = model_out["session"]
        tr = model_out["transcript"]
        diags += sess.outcome_diagnostics() + list(tr["events"])
        if sess.final is not None:
            status, dc = sess.final["status"], sess.final["delta_consistency"]
            last = sess.attempts[sess.final["attempt_no"] - 1]
            diags += [Diagnostic(**x) for x in last["record_diagnostics"]]
            if last.get("_sub") is not None:
                diags += reason_code_conflict(rec.reason_code, last["_sub"])
            final_reading = last["raw_submission"]
            claim = last["claim"]
        elif sess.attempts:
            status = "NO_FINAL_SUBMISSION"
            final_reading = sess.attempts[-1]["raw_submission"]
        else:
            status = "NO_SUBMISSION"
        if any(d.code in ("RUN.MODEL.ERROR", "RUN.MODEL.REFUSAL") for d in tr["events"]) and sess.final is None:
            status = "ERROR"
        process |= {"attempts": [_clean_attempt(a) for a in sess.attempts], "final": sess.final,
                    "n_model_calls": len(tr["calls"]), "transcript": tr}
    else:
        diags.append(diag("RUN.SUBMIT.NONE", "run", {"reason": "model not run"}, "3"))
    flags = flags_from(diags)
    judgment = recommend(flags)
    first_valid = None
    if model_out is not None:
        fv = [a for a in model_out["session"].attempts if a.get("delta_check")]
        first_valid = fv[0]["delta_check"] if fv else None
    return {
        "record_id": rec.record_id,
        "facts": {
            "source": {k: (str(v) if isinstance(v, (Decimal, datetime)) else v) for k, v in asdict(rec).items() if k != "text_raw"},
            "invoice_key": rec.invoice_key,
            "origin_country": prep["origin_country"], "destination_country": prep["destination_country"],
            "currency": prep["currency"], "currency_basis": "DERIVED_FROM_COUNTRY",
            "text_sha256": sha256(prep["text_norm"]), "text_redacted": prep["redacted"],
            "number_table": json.loads(p.model_dump_json()),
            "parse_status": status, "delta_consistency": dc, "first_check": first_valid,
            "reading": final_reading, "claim": claim,
        },
        "judgment": {"flags": flags, **judgment, "diagnostics": [d.model_dump() for d in diags]},
        "process": process,
        "versions": versions() | {"system_prompt_sha": _PROMPT_SHA.get("sha")},
    }


def run_batch(records: list[InputRecord], run_name: str, estimate_per_record: float, workers: int = 6,
              exclude_record_ids: set[str] | None = None, note: str = "") -> tuple[str, list[dict]]:
    """Prepare all records, check the budget, run the model in parallel, write outputs and the ledger entry."""
    from freight_lineitems.llm_client import client as make_client, request_kwargs

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    est = round(estimate_per_record * len(records), 4)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + run_name + "-" + uuid.uuid4().hex[:4]
    ok, msg = budget.reserve(run_id, est)      # audit M6: check and reserve atomically across processes
    if not ok:
        raise RuntimeError("budget: " + msg)
    out_dir = RUNS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    preps = [prepare(r) for r in records]          # Presidio sequentially (not thread-safe)
    cl, kw, book = make_client(), request_kwargs(), budget.UsageBook()
    ex = load_examples()
    sp = system_prompt(ex)
    excl = set(exclude_record_ids or set()) | {e["record_id"] for e in ex}

    def one(prep):
        try:
            return assemble(prep, run_model(prep, cl, kw, book, sp, ex, excl))
        except Exception as e:  # noqa: BLE001 - any crash becomes an explicit flag, never a silent drop
            return assemble(prep, None, [diag("RUN.MODEL.ERROR", "run", {"error": type(e).__name__, "message": str(e)[:300]}, "3")])

    # the first record runs alone so it writes the shared prompt cache; the rest then read it in parallel
    results = [one(preps[0])] if preps else []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results += list(pool.map(one, preps[1:]))
    def dump(name):
        with (out_dir / name).open("w") as f:
            for r in results:
                f.write(json.dumps(r, default=str, ensure_ascii=False) + "\n")

    # audit M2: model output and the ledger are saved before any post-processing that could crash
    dump("records_before_duplicates.jsonl")
    budget.append_entry(run_id, book.usages(), note=note or msg, started_at=started, n_records=len(records), estimate_usd=est)
    budget.release(run_id)
    entry = budget.read_ledger()[-1] if budget.read_ledger() and budget.read_ledger()[-1]["run"] == run_id else None
    results = duplicates.apply(records, results)
    dump("records.jsonl")
    from freight_lineitems import db
    from freight_lineitems.config import RULES
    con = db.connect(out_dir / "run.sqlite")
    db.write_run(con, run_id, run_name, records, results, kw, RULES)
    (out_dir / "export_facts.json").write_text(json.dumps(db.export_facts(con, run_id), indent=1, default=str))
    (out_dir / "export_review.json").write_text(json.dumps(db.export_review(con, run_id), indent=1, default=str, ensure_ascii=False))
    con.close()
    (out_dir / "run_info.json").write_text(json.dumps({"run_id": run_id, "n_records": len(records), "ledger_entry": entry,
                                                       "versions": versions(), "model_settings": kw}, default=str, indent=1))
    return run_id, results
