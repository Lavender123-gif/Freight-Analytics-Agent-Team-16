"""S2 / P5: SQLite store built from config/schema_v1.yaml, and the two exports.

- Tables are created from the YAML (column names and types), so the schema file stays the single definition.
- `write_run` stores one pipeline run: source rows as read (raw layer), our facts, every attempt (process layer),
  flags and assessments (judgment layer). Nothing is updated in place; a new run adds rows.
- `export_facts` is the downstream export: only disputes whose parse passed the mandatory checks, agrees with Delta
  (MATCH_FIRST / MATCH_AFTER_REVISION) AND carries no attention or return flag (recommendation PASSED_CHECKS).
  Anything a reviewer still has to look at (copies, injection suspects, inconsistencies, no anchor) stays in the
  review view until a reviewer clears it (decisions 3.9, 5.4; user decision 11-10; audit H2).
- `export_review` is the reviewer's view: every dispute, every attempt, every flag.
The database lives under data/ (git-ignored).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

import yaml

from freight_lineitems.checks import region_value
from freight_lineitems.config import CONFIG_DIR, ROOT, versions
from freight_lineitems.duplicates import content_key
from freight_lineitems.textprep import normalize

SCHEMA_PATH = CONFIG_DIR / "schema_v1.yaml"
DB_PATH = ROOT / "data" / "interim" / "freight.sqlite"
DOWNSTREAM_OK = ("MATCH_FIRST", "MATCH_AFTER_REVISION")
SHARED_TABLES = {"import_batch", "shipment", "carrier_invoice", "bill_record"}
SQL_TYPES = {"TEXT": "TEXT", "INTEGER": "INTEGER", "DECIMAL": "TEXT", "BOOLEAN": "INTEGER", "TIMESTAMP": "TEXT",
             "DATE": "TEXT", "JSON": "TEXT"}


@lru_cache(maxsize=1)
def schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text())


def ddl() -> list[str]:
    out = []
    for name, t in schema()["tables"].items():
        cols = []
        for c, spec in t["columns"].items():
            typ = spec["type"]
            cols.append(f'"{c}" {SQL_TYPES.get(typ.split("[")[0], "TEXT")}')
        pk = ", ".join(f'"{c}"' for c in t["primary_key"])
        out.append(f'CREATE TABLE IF NOT EXISTS "{name}" ({", ".join(cols)}, PRIMARY KEY ({pk}))')
    return out


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    for s in ddl():
        con.execute(s)
    return con


@lru_cache(maxsize=None)
def _cols(table: str) -> list[str]:
    return list(schema()["tables"][table]["columns"])


def _ins(con, table: str, row: dict) -> None:
    cols = _cols(table)
    unknown = set(row) - set(cols)
    if unknown:
        raise KeyError(f"{table}: columns not in schema v1: {sorted(unknown)}")
    vals = [json.dumps(row[c], default=str, ensure_ascii=False) if isinstance(row.get(c), (dict, list)) else row.get(c)
            for c in cols]
    # shared entities repeat within a batch with identical values; every other table must never collide (audit L8)
    verb = "INSERT OR IGNORE" if table in SHARED_TABLES else "INSERT"
    con.execute(f'{verb} INTO "{table}" VALUES ({", ".join("?" * len(cols))})', vals)


def _span(text: str, phrase: str | None):
    if not phrase:
        return None
    i = text.find(phrase)
    return [i, i + len(phrase)] if i >= 0 else None


def _git() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return "unknown"


def write_run(con, run_id: str, source_name: str, records: list, results: list[dict], model_settings: dict,
              rules_cfg: dict) -> None:
    """Store one run. `records` are the InputRecords, `results` the pipeline outputs (same record ids)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    content_sha = hashlib.sha256(json.dumps([r.raw for r in records], default=str).encode()).hexdigest()
    batch_id = "batch-" + hashlib.sha256((source_name + content_sha).encode()).hexdigest()[:10]
    _ins(con, "import_batch", {"batch_id": batch_id, "source_file_name": source_name, "source_file_sha256": content_sha,
         "sheet_name": None, "imported_at": now, "row_count": len(records), "loader_version": _git()})
    v = versions()
    _ins(con, "pipeline_run", {"run_id": run_id, "batch_id": batch_id, "started_at": now, "finished_at": now,
         "code_version": _git(), "taxonomy_version": v["taxonomy"], "rules_version": v["rules"],
         "diagnostics_catalog_version": v["rules"], "prompt_version": v["skill_sha"], "model_id": model_settings.get("model"),
         "experiment_arm": "MAIN", "max_repair_rounds": rules_cfg["agent"]["max_repair_rounds"],
         "max_delta_feedback_rounds": rules_cfg["agent"]["max_delta_feedback_rounds"], "model_settings": model_settings})
    res = {r["record_id"]: r for r in results}
    ranks: dict[str, int] = {}
    for r in sorted(records, key=lambda r: r.row_number):
        k = content_key(r)
        ranks[r.record_id] = ranks.get(k, 0) + 1
        ranks[k] = ranks[r.record_id]
    for r in records:
        out = res.get(r.record_id)
        if out is None:
            continue
        f, j, p = out["facts"], out["judgment"], out["process"]
        srid = f"{batch_id}:{r.row_number}"
        rf = hashlib.sha256(json.dumps({k: v for k, v in r.raw.items() if k not in ("Dispute Status", "Invoice Dups Removed")},
                                       sort_keys=True, default=str).encode()).hexdigest()[:16]
        _ins(con, "source_row", {"source_row_id": srid, "batch_id": batch_id, "row_number": r.row_number,
             "raw_columns": r.raw, "row_fingerprint": rf})
        _ins(con, "shipment", {"shipment_gid": r.shipment_key, "carrier_id": r.carrier, "sap_bol": r.raw.get("SAP BOL"),
             "origin_city": r.raw.get("Source City"), "origin_state": r.origin_state,
             "destination_city": r.raw.get("Destination City"), "destination_state": r.destination_state,
             "origin_country": f["origin_country"], "destination_country": f["destination_country"],
             "shipment_amount": str(r.shipment_amount), "planned_distance": None, "straight_line_km": None,
             "first_seen_batch_id": batch_id})
        _ins(con, "carrier_invoice", {"carrier_invoice_id": r.invoice_key, "carrier_id": r.carrier,
             "carrier_invoice_no": r.carrier_invoice, "shipment_gid": r.shipment_key})
        if r.pk:
            _ins(con, "bill_record", {"pk": r.pk, "invoice_bill_id": r.raw.get("Invoice/Bill ID"), "pk_date": None,
                 "carrier_invoice_id": r.invoice_key, "shipment_gid": r.shipment_key})
        did = r.record_id
        _ins(con, "dispute", {"dispute_id": did, "first_source_row_id": srid, "shipment_gid": r.shipment_key,
             "carrier_invoice_id": r.invoice_key, "pk": r.pk, "event_time": str(r.event_date),
             "description_sha256": f["text_sha256"], "description_redacted": f["text_redacted"],
             "n_redactions": None, "invoice_amount": str(r.invoice_amount), "delta": str(r.delta),
             "currency": f["currency"], "currency_basis": f["currency_basis"], "reason_code": r.reason_code,
             "content_key": content_key(r), "copy_rank": ranks[did], "created_in_batch_id": batch_id,
             "row_number": r.row_number})
        _ins(con, "dispute_source_row", {"dispute_id": did, "source_row_id": srid, "link_type": "FIRST_SEEN"})
        nt = f["number_table"]
        for n in nt["numbers"]:
            _ins(con, "number_token", {"dispute_id": did, "token_id": n["id"], "token_type": "NUMBER", "raw": n["raw"],
                 "span_start": n["span"][0], "span_end": n["span"][1], "value": n["value"],
                 "features": {k: n[k] for k in ("has_dollar", "space_merged", "leading_dot", "trailing_dot", "decimals",
                                                 "minus_before", "prev_symbol", "unit_hint")}})
        for kind, key in (("DATE", "dates"), ("UNRECOGNIZED", "unrecognized")):
            for n in nt[key]:
                _ins(con, "number_token", {"dispute_id": did, "token_id": n["id"], "token_type": kind, "raw": n["raw"],
                     "span_start": n["span"][0], "span_end": n["span"][1], "value": None, "features": {}})
        prid = f"{run_id}:{did}"
        attempts = p.get("attempts", [])
        fin = (p.get("final") or {}).get("attempt_no")
        _ins(con, "parse_run", {"parse_run_id": prid, "run_id": run_id, "dispute_id": did, "status": f["parse_status"],
             "delta_consistency": f["delta_consistency"], "n_attempts": len(attempts),
             "first_attempt_id": f"{prid}:1" if attempts else None,
             "final_attempt_id": f"{prid}:{fin}" if fin else None, "reused_from_parse_run_id": None})
        text = f["text_redacted"]
        calls = p.get("transcript", {}).get("calls", [])
        for a in attempts:
            aid = f"{prid}:{a['attempt_no']}"
            sub = a["raw_submission"] or {}
            _ins(con, "parse_attempt", {"attempt_id": aid, "parse_run_id": prid, "attempt_no": a["attempt_no"],
                 "llm_input": p["transcript"]["first_user_message"] if a["attempt_no"] == 1 else None,
                 "feedback_given": a.get("feedback_given"), "raw_submission": sub,
                 "response_type": a.get("response_type"), "claimed_total": a["claim"]["signed_sum"] if a.get("claim") else None,
                 "counted_sum": a["claim"]["signed_sum"] if a.get("claim") else None, "delta_check": a.get("delta_check"),
                 "failed_checks": [e["code"] for e in a["repair_errors"]], "model_id": model_settings.get("model"),
                 "started_at": now, "usage": [c["usage"] for c in calls] if a["attempt_no"] == 1 else [],
                 "reason": sub.get("reason"), "repair_errors": a["repair_errors"]})
            if sub.get("reason"):
                _ins(con, "model_statement", {"statement_id": f"{aid}:reason", "attempt_id": aid,
                     "type": "INSIST_REASON" if sub.get("response_type") == "INSISTED" else "REVISION_REASON",
                     "target_ref": None, "text": sub["reason"]})
            judged = list(sub.get("numbers", [])) + [dict(x["as_number"], digits_read=x["digits_read"])
                                                     for x in sub.get("unrecognized_reads", [])]
            for jn in judged:
                _ins(con, "number_reading", {"attempt_id": aid, "token_id": jn["id"], "digits_read": jn.get("digits_read"),
                     "kind": jn["kind"], "status": jn["status"], "counted_in_claim": jn["status"] in ("CLAIMED", "UNPAID"),
                     "evidence_span": _span(text, jn.get("evidence_phrase")), "exclusion_reason_span": _span(text, jn.get("exclusion_phrase")),
                     "is_credit": jn.get("is_credit"), "evidence_phrase": jn.get("evidence_phrase"),
                     "exclusion_phrase": jn.get("exclusion_phrase")})
            byid = {x["id"]: x for x in judged}
            vals = {n["id"]: n["value"] for n in nt["numbers"]} | {     # region reads too (audit L10)
                u["id"]: str(region_value(u["raw"])) for u in nt["unrecognized"]}
            for k, li in enumerate(sub.get("line_items", [])):
                jn = byid.get(li["amount_ref"]) if li["amount_ref"] else None
                codes = (jn["charge_codes"] if jn else li["charge_codes"]) or [None]
                for ci, code in enumerate(codes):
                    _ins(con, "line_item", {"line_item_id": f"{aid}:{k}" + (f".{ci}" if len(codes) > 1 else ""),
                         "attempt_id": aid, "amount_token_id": li["amount_ref"], "amount": vals.get(li["amount_ref"]),
                         "combined_group": f"{aid}:{k}" if len(codes) > 1 else None, "charge_code": code,
                         "raw_charge_label": li.get("raw_charge_label"), "code_evidence_span": _span(text, li.get("raw_charge_label")),
                         "mapping_status": "OTHER" if code == "OTHER" else "PENDING_MEANING" if (code or "").startswith("PENDING")
                         else "NOT_CHECKED", "carrier_stated_reason_span": _span(text, li.get("carrier_stated_reason")),
                         "carrier_stated_basis_type": li.get("carrier_stated_basis_type"),
                         "carrier_stated_basis_span": _span(text, li.get("carrier_stated_basis")),
                         "is_credit": bool(jn and jn.get("is_credit"))})
            for k, rel in enumerate(sub.get("relations", [])):
                _ins(con, "arithmetic_relation", {"relation_id": f"{aid}:r{k}", "attempt_id": aid,
                     "relation_type": rel["relation_type"], "operands": rel["operand_ids"], "result_token_id": rel["result_id"],
                     "computed_value": None, "holds": None})
        for k, fl in enumerate(j["flags"]):
            _ins(con, "flag", {"flag_id": f"{prid}:f{k}", "run_id": run_id, "code": fl["code"],
                 "level": "ROW" if fl["code"].startswith("DUP.ROW") else "INVOICE" if fl["code"].startswith("DUP.INVOICE")
                 else "PARSE", "target_type": "DISPUTE", "target_id": did, "dispute_id": did,
                 "severity": fl["severity"].upper(), "origin": fl["origin"], "points_to_dispute_id": fl.get("points_to"),
                 "points_to_line_item_id": None,
                 "n_later_copies": next((e.get("n_later_copies") for e in fl["evidence"] if e.get("n_later_copies")), None),
                 "evidence": fl["evidence"], "explanation": None, "rules_version": j.get("rules_version")})
        _ins(con, "dispute_assessment", {"run_id": run_id, "dispute_id": did, "recommendation": j["recommendation"],
             "decisive_flag_ids": j["decisive_flags"], "history_status": "HISTORY_NOT_AVAILABLE",
             "return_draft": j.get("return_draft")})
    con.commit()


def export_facts(con, run_id: str) -> list[dict]:
    """Downstream export (fact layer only): consistent, passed disputes; their final line items with currency."""
    q = """SELECT d.dispute_id, d.shipment_gid, d.carrier_invoice_id, d.currency, d.currency_basis, pr.final_attempt_id,
                  pr.delta_consistency
           FROM parse_run pr JOIN dispute d ON d.dispute_id = pr.dispute_id
           JOIN dispute_assessment a ON a.dispute_id = pr.dispute_id AND a.run_id = pr.run_id
           WHERE pr.run_id = ? AND pr.status = 'PASSED_CHECKS' AND pr.delta_consistency IN (?, ?)
             AND a.recommendation = 'PASSED_CHECKS'"""
    out = []
    for row in con.execute(q, (run_id, *DOWNSTREAM_OK)).fetchall():
        items = con.execute("""SELECT line_item_id, amount, is_credit, charge_code, combined_group, raw_charge_label,
                               carrier_stated_basis_type FROM line_item WHERE attempt_id = ?""", (row[5],)).fetchall()
        out.append({"dispute_id": row[0], "shipment_gid": row[1], "carrier_invoice_id": row[2], "currency": row[3],
                    "currency_basis": row[4], "delta_consistency": row[6],
                    "line_items": [dict(zip(["line_item_id", "amount", "is_credit", "charge_code", "combined_group",
                                             "raw_charge_label", "carrier_stated_basis_type"], it)) for it in items]})
    return out


def export_review(con, run_id: str) -> list[dict]:
    """Reviewer view: every dispute with its assessment and flags (attempts are in parse_attempt)."""
    q = """SELECT d.dispute_id, d.carrier_invoice_id, d.description_redacted, pr.status, pr.delta_consistency,
                  a.recommendation FROM dispute d JOIN parse_run pr ON pr.dispute_id = d.dispute_id
                  JOIN dispute_assessment a ON a.dispute_id = d.dispute_id AND a.run_id = pr.run_id WHERE pr.run_id = ?"""
    out = []
    for r in con.execute(q, (run_id,)).fetchall():
        fl = con.execute("SELECT code, severity, points_to_dispute_id FROM flag WHERE run_id = ? AND dispute_id = ?",
                         (run_id, r[0])).fetchall()
        out.append({"dispute_id": r[0], "carrier_invoice_id": r[1], "text_redacted": r[2], "parse_status": r[3],
                    "delta_consistency": r[4], "recommendation": r[5],
                    "flags": [{"code": c, "severity": s, "points_to": p} for c, s, p in fl]})
    return out


def ingest_only(con, records: list, source_name: str) -> int:
    """Deterministic ingest without the model (S2 check): raw rows, shipments, invoices, bill records, disputes."""
    from freight_lineitems.pipeline import assemble, prepare
    results = [assemble(prepare(r), None) for r in records]
    write_run(con, f"ingest-{source_name}", source_name, records, results, {"model": None},
              yaml.safe_load((CONFIG_DIR / "rules.yaml").read_text()))
    return len(results)


_ = normalize  # re-exported for callers that build content keys
