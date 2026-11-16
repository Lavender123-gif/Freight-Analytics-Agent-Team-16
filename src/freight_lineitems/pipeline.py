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
from freight_lineitems.agent import Session, run_agent
from freight_lineitems.checks import Ctx, diag, reason_code_conflict, step2_diagnostics
from freight_lineitems.config import RULES, RUNS_DIR, country, versions
from freight_lineitems.disposition import flags_from, recommend
from freight_lineitems.numbers import parse
from freight_lineitems.records import InputRecord, group_explanations
from freight_lineitems.schemas import Diagnostic, LLMInput, LLMNumberView
from freight_lineitems import features, screen, skilltext
from freight_lineitems.skilltext import render_examples  # noqa: F401  (kept importable from here)
from freight_lineitems.textprep import injection_hits, normalize, redact, redaction_altered_digits, sha256
from freight_lineitems.tools import load_examples


_PROMPT_SHA: dict = {}
READING_SCHEMA_VERSION = "reading-output-1.0"      # docs/reading_output_contract.md


def system_prompt(examples: list[dict] | None = None, lay: str | None = None) -> str:
    """The reading skill's system prompt for a layout (task 19; skilltext.py). `single`: the core with every topic
    reference and the fixed example set (the real dev examples, git-ignored; synthetic ones when absent). `routed`:
    the core with the generic examples of rules.yaml `features.examples.generic_ids`. `examples` replaces the default
    fixed examples (tests). A missing example set is an error, not an empty section."""
    lay = lay or skilltext.layout()
    if examples is not None:
        ex = examples
    elif lay == "routed":
        ex = features.generic_examples(features.example_library())
    else:
        ex = load_examples()
    if not ex:
        raise FileNotFoundError("worked examples missing: run data/interim/skill/build_examples.py")
    out = skilltext.system_prompt(lay, ex)
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
    oc, dc = country(rec.origin_state), country(rec.destination_state)
    if oc != dc:
        d.append(diag("REC.FIELD.CROSS_BORDER", "source", {"origin_country": oc, "destination_country": dc}, "1"))
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
            "currency": RULES["currency"]["fixed"]}


def _clean_attempt(a: dict) -> dict:
    return {k: v for k, v in a.items() if not k.startswith("_")}


def run_model(prep: dict, client, req_kw: dict, book: budget.UsageBook, sys_prompt: str, examples: list[dict],
              exclude_record_ids: set[str], lay: str = "single", library: list[dict] | None = None) -> dict:
    """One explanation through the model. In the routed layout code first picks the topic references and similar
    examples for its input (features.routing); what was picked is kept in the output (process.routing)."""
    rec: InputRecord = prep["rec"]
    sess = Session(ctx=prep["ctx"], llm_input=prep["llm_input"])
    excl = exclude_record_ids | {rec.record_id}
    route = {"layout": lay}
    preamble = ""
    if lay == "routed":
        r = features.routing(prep["redacted"], prep["parse"].marked_text, library or [], excl, rec.shipment_key)
        preamble = r.pop("preamble")
        route |= r
    tr = run_agent(sess, sys_prompt, client, req_kw, book, examples, excl, rec.shipment_key, preamble=preamble)
    return {"session": sess, "transcript": tr, "routing": route}


def stated_amount_due(p, reading: dict | None) -> dict | None:
    """Task 19 addendum: the amount the text presents as owed now, as the reading gives it, with its value from the
    number table. Stored and counted in reports only; no rule reads it (concepts.stated_amount_due)."""
    sid = (reading or {}).get("stated_amount_due_id")
    if not sid:
        return None
    from freight_lineitems.checks import region_value
    vals = {n.id: str(n.value) for n in p.numbers} | {u.id: str(region_value(u.raw)) for u in p.unrecognized}
    return {"number_id": sid, "value": vals.get(sid), "evidence_phrase": reading.get("stated_amount_due_evidence")}


def assemble(prep: dict, model_out: dict | None, extra_diags: list[Diagnostic] | None = None) -> dict:
    """Build the output record (facts / judgment / process) from the prepared record and the model run."""
    rec: InputRecord = prep["rec"]
    p = prep["parse"]
    diags: list[Diagnostic] = list(prep["pre_diags"]) + list(extra_diags or [])
    process: dict = {"model_ran": model_out is not None}
    if model_out is not None and model_out.get("routing"):
        process["routing"] = model_out["routing"]
    if model_out is not None and "screening" in model_out:      # task 19: the screening call's answer and its flag
        diags += screen.diagnostics(model_out["screening"])
        process["screening"] = screen.summary(model_out["screening"])
    final_reading = None
    claim = None
    status = "NOT_RUN"
    if model_out is not None:
        sess: Session = model_out["session"]
        tr = model_out["transcript"]
        diags += sess.outcome_diagnostics() + list(tr["events"])
        if sess.final is not None:
            status = sess.final["status"]
            last = sess.attempts[sess.final["attempt_no"] - 1]
            diags += [Diagnostic(**x) for x in last["record_diagnostics"]]
            if last.get("_sub") is not None:
                diags += reason_code_conflict(rec.reason_code, last["_sub"])
            final_reading = last["raw_submission"]
            claim = last["claim"]
            from freight_lineitems.reading_checks import reading_diagnostics
            diags += reading_diagnostics(json.loads(p.model_dump_json()), final_reading)
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
    return {
        "schema_version": READING_SCHEMA_VERSION,
        "record_id": rec.record_id,
        "facts": {
            "source": {k: (str(v) if isinstance(v, (Decimal, datetime)) else v) for k, v in asdict(rec).items() if k != "text_raw"},
            "invoice_key": rec.invoice_key,
            "origin_country": prep["origin_country"], "destination_country": prep["destination_country"],
            "currency": prep["currency"], "currency_basis": "FIXED_USD",
            "text_sha256": sha256(prep["text_norm"]), "text_redacted": prep["redacted"],
            "number_table": json.loads(p.model_dump_json()),
            "parse_status": status,
            "reading": final_reading, "claim": claim,
            "stated_amount_due": stated_amount_due(p, final_reading),
        },
        "judgment": {"flags": flags, **judgment, "diagnostics": [d.model_dump() for d in diags]},
        "process": process,
        "versions": versions() | {"system_prompt_sha": _PROMPT_SHA.get("sha")},
    }


def finish_batch(records: list[InputRecord], results: list[dict], prior_history=None,
                 relation_suggestions: dict[str, list[dict]] | None = None) -> tuple[list[dict], list[dict]]:
    """Everything after the model, for one batch (task 20 section 2.1): order-copy facts and flags on each
    explanation's result (duplicates.apply), then the shipment roll-up (rollup.rollup_results, with the cross-batch
    history source and the relation suggestions; defaults: not provided, none) and the client names of every line
    (charge_map.annotate). `results` are one per explanation, keyed by the representative row's record id. Returns
    (results, shipments). run_batch and every evaluation script call this one function, so production and
    evaluation compute the shipment results the same way."""
    results = duplicates.apply(records, results)
    return results, shipments_of(results, prior_history, relation_suggestions)


def shipments_of(results: list[dict], prior_history=None, relation_suggestions: dict[str, list[dict]] | None = None) -> list[dict]:
    """The shipment half of finish_batch, for results that already carry their order-copy facts (stored runs): the
    roll-up and the client names. Evaluation scripts that start from stored explanations call this, never
    rollup.rollup_results directly."""
    from freight_lineitems import charge_map, rollup
    ships = rollup.rollup_results(results, prior_history, relation_suggestions)
    for sh in ships:
        charge_map.annotate(sh)
    return ships


def run_record(model_settings: dict) -> dict:
    """What a run must record to be reproduced (task 20 section 2.6): code version (git commit and whether the tree
    had uncommitted changes), redaction method, skill layout, skill / rules / taxonomy / example versions, model."""
    import os
    import subprocess
    from freight_lineitems.config import ROOT
    from freight_lineitems.textprep import redaction_engine

    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    status = git("status", "--porcelain", "--untracked-files=no")
    return {"git_commit": git("rev-parse", "HEAD") or "unknown", "git_dirty": bool(status) if status is not None else None,
            "redaction_engine": redaction_engine(), "screening_enabled": screen.enabled(),
            "model": model_settings.get("model"), "reading_schema_version": READING_SCHEMA_VERSION,
            "shipment_schema_version": __import__("freight_lineitems.rollup", fromlist=["x"]).SHIPMENT_SCHEMA_VERSION,
            "env_overrides": {k: os.environ[k] for k in ("FL_SKILL_LAYOUT", "FL_REDACTION_ENGINE", "FL_SCREENING",
                                                         "FL_TAXONOMY_LAYOUT") if k in os.environ},
            **versions()}


def write_outputs(out_dir, run_id: str, run_name: str, records: list[InputRecord], results: list[dict],
                  ships: list[dict], model_settings: dict) -> None:
    """Write a finished batch: records.jsonl, shipments.jsonl, the shipment table (CSV, JSON), run.sqlite and the
    two exports. Shared by run_batch and the offline replay (python -m freight_lineitems.offline)."""
    from freight_lineitems import db, shipment_table
    with (out_dir / "records.jsonl").open("w") as f:
        for r in results:
            f.write(json.dumps(r, default=str, ensure_ascii=False) + "\n")
    with (out_dir / "shipments.jsonl").open("w") as f:
        for sh in ships:
            f.write(json.dumps(sh, default=str, ensure_ascii=False) + "\n")
    shipment_table.write(ships, out_dir)
    con = db.connect(out_dir / "run.sqlite")
    db.write_run(con, run_id, run_name, records, results, model_settings, RULES)
    db.write_shipments(con, run_id, ships)
    (out_dir / "export_facts.json").write_text(json.dumps(db.export_facts(con, run_id), indent=1, default=str))
    (out_dir / "export_review.json").write_text(json.dumps(db.export_review(con, run_id), indent=1, default=str, ensure_ascii=False))
    con.close()


def run_batch(records: list[InputRecord], run_name: str, estimate_per_record: float, workers: int = 6,
              exclude_record_ids: set[str] | None = None, note: str = "") -> tuple[str, list[dict]]:
    """Merge order copies into explanations, prepare one record per explanation (its first row), check the budget,
    run the model in parallel, write outputs and the ledger entry. The estimate is per explanation."""
    from freight_lineitems.llm_client import client as make_client, request_kwargs

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reps = [g[0] for g in group_explanations(records)]      # task 14 / T12-02: one model reading per explanation
    est = round(estimate_per_record * len(reps), 4)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + run_name + "-" + uuid.uuid4().hex[:4]
    ok, msg = budget.reserve(run_id, est)      # audit M6: check and reserve atomically across processes
    if not ok:
        raise RuntimeError("budget: " + msg)
    out_dir = RUNS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    preps = [prepare(r) for r in reps]             # Presidio sequentially (not thread-safe)
    cl, kw, book = make_client(), request_kwargs(), budget.UsageBook()
    lay = skilltext.layout()
    ex = load_examples()
    library = features.example_library() if lay == "routed" else None
    sp = system_prompt(None, lay)
    # routed: an example may be chosen for any other explanation (the generic ones are excluded by id in features.py);
    # an explanation never gets itself or its shipment as an example (run_model adds its own id, features its shipment)
    excl = set(exclude_record_ids or set())

    use_screen = screen.enabled()

    def one(prep):
        scr = None
        if use_screen:     # task 19: the screening call runs on every explanation, before the reading; it skips nothing
            try:
                scr = screen.screen(prep["redacted"], cl, kw, book)
            except Exception as e:  # noqa: BLE001
                scr = {"result": None, "quote_found": None, "calls": [], "error": f"{type(e).__name__}: {str(e)[:200]}"}
        try:
            mo = run_model(prep, cl, kw, book, sp, ex, excl, lay, library)
            if use_screen:
                mo["screening"] = scr
            return assemble(prep, mo)
        except Exception as e:  # noqa: BLE001 - any crash becomes an explicit flag, never a silent drop
            return assemble(prep, None, [diag("RUN.MODEL.ERROR", "run", {"error": type(e).__name__, "message": str(e)[:300]}, "3")]
                            + screen.diagnostics(scr))

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
    budget.append_entry(run_id, book.usages(), note=note or msg, started_at=started, n_records=len(reps), estimate_usd=est)
    budget.release(run_id)
    entry = budget.read_ledger()[-1] if budget.read_ledger() and budget.read_ledger()[-1]["run"] == run_id else None
    results, ships = finish_batch(records, results)
    write_outputs(out_dir, run_id, run_name, records, results, ships, kw)
    (out_dir / "run_info.json").write_text(json.dumps({"run_id": run_id, "n_records": len(records), "n_explanations": len(reps),
                                                       "n_shipments": len(ships), "ledger_entry": entry,
                                                       "run_record": run_record(kw), "versions": versions(),
                                                       "model_settings": kw}, default=str, indent=1))
    return run_id, results
