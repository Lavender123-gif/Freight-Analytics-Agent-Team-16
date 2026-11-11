"""U2: minimal local review interface over one run database (decision section 6, workload v2 row U2).

What it is: a small web page served from this machine only (127.0.0.1). It lists the carrier invoices of one run with
the rule-computed colour and the flag counts per severity, opens an invoice into its disputes (redacted text, the
model's reading, the model's statements, flags, first-attempt marker), and records what the reviewer decided.

What it is not: it never suggests whether a charge should be paid. Colours and flags come from the run (rules.yaml);
the buttons only append the reviewer's own action to the `reviewer_decision` table defined in config/schema_v1.yaml.
Nothing is sent anywhere and nothing in the run's other tables is changed.

Only the standard library is used (http.server + sqlite3 + one HTML file with inline script and style, no external
resources). The raw text column is never read: the page shows `dispute.description_redacted` only.

Run:  uv run python -m freight_lineitems.review_ui --run <run_id> [--reviewer R1] [--port 8765] [--read-only]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from freight_lineitems import db
from freight_lineitems.config import RUNS_DIR

HOST = "127.0.0.1"                      # never bind anything else: the page shows row-level data
PAGE_PATH = Path(__file__).with_name("review_ui.html")
DECISION_TABLE = "reviewer_decision"
SEVERITIES = ("ATTENTION", "RETURN", "INFO")
REMINDER_SEVERITIES = ("ATTENTION", "RETURN")      # "has reminders" = at least one flag a person should look at
# decision 2.3: first whether a person has to look, then whether it can be returned, else passed
RECOMMENDATION_ORDER = ("HUMAN_REVIEW", "RETURN_SUGGESTED", "PASSED_CHECKS")
REVIEWER_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")
MAX_REASON_CHARS = 2000
MAX_BODY_BYTES = 20_000


def decision_actions() -> tuple[str, ...]:
    """The actions a reviewer can record, read from schema_v1.yaml (`reviewer_decision.action`, decision 6.4)."""
    typ = db.schema()["tables"][DECISION_TABLE]["columns"]["action"]["type"]
    return tuple(a.strip() for a in typ[typ.index("[") + 1:typ.rindex("]")].split(","))


def run_db_path(run_id: str) -> Path:
    """Path of the SQLite file the pipeline wrote for `run_id` (data/interim/runs/<run_id>/run.sqlite)."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise ValueError(f"not a run id: {run_id!r}")
    return RUNS_DIR / run_id / "run.sqlite"


def open_db(path: Path, read_only: bool = False) -> sqlite3.Connection:
    """Open an existing run database. Unless `read_only`, make sure the decision table exists and is append-only.

    Raises FileNotFoundError when the file is missing (a new empty database is never created here).
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"run database not found: {path}")
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode={'ro' if read_only else 'rw'}", uri=True)
    con.row_factory = sqlite3.Row
    if not read_only:
        ensure_decision_table(con)
    return con


def ensure_decision_table(con: sqlite3.Connection) -> None:
    """Create `reviewer_decision` from the schema file if an older database lacks it, and forbid UPDATE and DELETE
    on it, so every recorded decision stays (schema: "只追加")."""
    for stmt in db.ddl():
        if f'"{DECISION_TABLE}"' in stmt.split("(")[0]:
            con.execute(stmt)
    for verb in ("UPDATE", "DELETE"):
        con.execute(f"""CREATE TRIGGER IF NOT EXISTS {DECISION_TABLE}_no_{verb.lower()} BEFORE {verb} ON {DECISION_TABLE}
                        BEGIN SELECT RAISE(ABORT, '{DECISION_TABLE} is append-only'); END""")
    con.commit()


def run_ids(con: sqlite3.Connection) -> list[str]:
    """Run ids stored in this database, oldest first."""
    return [r[0] for r in con.execute("SELECT run_id FROM pipeline_run ORDER BY started_at, run_id")]


def _json(value, default=None):
    if value is None:
        return default
    try:
        out = json.loads(value)
    except (TypeError, ValueError):
        return default
    return default if out is None else out


def _dec(value) -> Decimal | None:
    try:
        return None if value is None else Decimal(str(value))
    except InvalidOperation:
        return None


def _sum(values) -> str | None:
    """Sum of the values that are numbers; None when none is."""
    nums = [d for d in map(_dec, values) if d is not None]
    return str(sum(nums, Decimal(0))) if nums else None


def _worst(recommendations: list[str]) -> str:
    return min(recommendations, key=lambda r: RECOMMENDATION_ORDER.index(r) if r in RECOMMENDATION_ORDER else -1)


def list_invoices(con: sqlite3.Connection, run_id: str, reminders: str = "all", sort: str = "reminders") -> list[dict]:
    """Invoice list for one run (decision 6.1).

    Each entry carries the invoice colour (the most pressing recommendation among its disputes, in the order of
    decision 2.3), the number of flags per severity, and how many disputes already have a recorded decision.
    `reminders`: "all", "yes" (at least one ATTENTION or RETURN flag) or "no". `sort`: "reminders" (most first) or
    "invoice". Raises ValueError for other values.
    """
    if reminders not in ("all", "yes", "no") or sort not in ("reminders", "invoice"):
        raise ValueError("reminders must be all|yes|no and sort must be reminders|invoice")
    out: dict[str, dict] = {}
    q = """SELECT d.dispute_id, d.carrier_invoice_id, ci.carrier_invoice_no, ci.carrier_id, d.shipment_gid, a.recommendation
           FROM parse_run pr JOIN dispute d ON d.dispute_id = pr.dispute_id
           JOIN dispute_assessment a ON a.dispute_id = d.dispute_id AND a.run_id = pr.run_id
           LEFT JOIN carrier_invoice ci ON ci.carrier_invoice_id = d.carrier_invoice_id
           WHERE pr.run_id = ? ORDER BY d.row_number, d.dispute_id"""
    by_dispute: dict[str, dict] = {}
    recs: dict[str, list[str]] = {}
    for r in con.execute(q, (run_id,)):
        inv = out.setdefault(r["carrier_invoice_id"], {
            "carrier_invoice_id": r["carrier_invoice_id"], "carrier_invoice_no": r["carrier_invoice_no"],
            "carrier_id": r["carrier_id"], "shipment_gid": r["shipment_gid"], "n_disputes": 0,
            "flag_counts": dict.fromkeys(SEVERITIES, 0), "n_flags_cleared": 0, "n_disputes_decided": 0})
        inv["n_disputes"] += 1
        recs.setdefault(r["carrier_invoice_id"], []).append(r["recommendation"])
        by_dispute[r["dispute_id"]] = inv
    for r in con.execute("SELECT dispute_id, severity, COUNT(*) AS n FROM flag WHERE run_id = ? GROUP BY 1, 2", (run_id,)):
        if r["dispute_id"] in by_dispute:
            counts = by_dispute[r["dispute_id"]]["flag_counts"]
            counts[r["severity"]] = counts.get(r["severity"], 0) + r["n"]
    cleared = """SELECT f.dispute_id, COUNT(DISTINCT f.flag_id) AS n FROM flag f JOIN reviewer_decision rd
                 ON rd.flag_id = f.flag_id AND rd.action = 'CLEAR_FLAG' WHERE f.run_id = ? GROUP BY 1"""
    for r in con.execute(cleared, (run_id,)):
        if r["dispute_id"] in by_dispute:
            by_dispute[r["dispute_id"]]["n_flags_cleared"] += r["n"]
    for r in con.execute("SELECT DISTINCT dispute_id FROM reviewer_decision WHERE action != 'CLEAR_FLAG'"):
        if r["dispute_id"] in by_dispute:
            by_dispute[r["dispute_id"]]["n_disputes_decided"] += 1
    rows = []
    for key, inv in out.items():
        inv["recommendation"] = _worst(recs[key])
        inv["n_reminders"] = sum(inv["flag_counts"][s] for s in REMINDER_SEVERITIES)
        inv["has_reminders"] = inv["n_reminders"] > 0
        if reminders == "all" or (reminders == "yes") == inv["has_reminders"]:
            rows.append(inv)
    if sort == "reminders":
        rows.sort(key=lambda i: (-i["flag_counts"]["ATTENTION"], -i["flag_counts"]["RETURN"], str(i["carrier_invoice_id"])))
    else:
        rows.sort(key=lambda i: str(i["carrier_invoice_id"]))
    return rows


def _readings(con: sqlite3.Connection, dispute_id: str, attempt_id: str | None) -> dict:
    """The model's reading in one attempt: every number it judged and the line items."""
    if not attempt_id:
        return {"attempt_id": None, "numbers": [], "line_items": []}
    tokens = {t["token_id"]: t for t in con.execute(
        "SELECT token_id, token_type, raw, value FROM number_token WHERE dispute_id = ?", (dispute_id,))}
    numbers = []
    for r in con.execute("""SELECT token_id, digits_read, kind, status, counted_in_claim, is_credit, evidence_phrase,
                            exclusion_phrase FROM number_reading WHERE attempt_id = ? ORDER BY rowid""", (attempt_id,)):
        t = tokens.get(r["token_id"])
        numbers.append({"token_id": r["token_id"], "raw": t["raw"] if t else None, "value": t["value"] if t else None,
                        "digits_read": r["digits_read"], "kind": r["kind"], "status": r["status"],
                        "counted_in_claim": bool(r["counted_in_claim"]), "is_credit": bool(r["is_credit"]),
                        "evidence_phrase": r["evidence_phrase"], "exclusion_phrase": r["exclusion_phrase"]})
    items = [dict(r) | {"is_credit": bool(r["is_credit"])} for r in con.execute(
        """SELECT line_item_id, amount_token_id, amount, charge_code, raw_charge_label, mapping_status,
           carrier_stated_basis_type, combined_group, is_credit FROM line_item WHERE attempt_id = ? ORDER BY rowid""",
        (attempt_id,))]
    return {"attempt_id": attempt_id, "numbers": numbers, "line_items": items}


def decision_history(con: sqlite3.Connection, dispute_id: str) -> list[dict]:
    """Every decision recorded for one dispute, oldest first. Nothing is ever removed from this list."""
    return [dict(r) for r in con.execute(
        """SELECT decision_id, dispute_id, flag_id, action, reason, reviewer_id, decided_at FROM reviewer_decision
           WHERE dispute_id = ? ORDER BY decided_at, rowid""", (dispute_id,))]


def _dispute_detail(con: sqlite3.Connection, run_id: str, row: sqlite3.Row) -> dict:
    did = row["dispute_id"]
    attempts = [dict(a) | {"failed_checks": _json(a["failed_checks"], [])} for a in con.execute(
        """SELECT attempt_id, attempt_no, response_type, delta_check, feedback_given, claimed_total, failed_checks, reason
           FROM parse_attempt WHERE parse_run_id = ? ORDER BY attempt_no""", (row["parse_run_id"],))]
    statements = [dict(s) for s in con.execute(
        """SELECT ms.type, ms.text, pa.attempt_no FROM model_statement ms JOIN parse_attempt pa
           ON pa.attempt_id = ms.attempt_id WHERE pa.parse_run_id = ? ORDER BY pa.attempt_no, ms.rowid""",
        (row["parse_run_id"],))]
    history = decision_history(con, did)
    cleared = {h["flag_id"] for h in history if h["action"] == "CLEAR_FLAG"}
    flags = []
    for f in con.execute("""SELECT flag_id, code, severity, origin, level, points_to_dispute_id, n_later_copies, evidence
                            FROM flag WHERE run_id = ? AND dispute_id = ? ORDER BY rowid""", (run_id, did)):
        evidence = _json(f["evidence"], [])
        flags.append(dict(f) | {"evidence": evidence, "cleared": f["flag_id"] in cleared})
        if f["origin"] == "MODEL_REPORTED":            # the model's own doubts are part of its explanation
            statements += [{"type": "UNCERTAINTY", "text": e["note"], "attempt_no": None}
                           for e in evidence if isinstance(e, dict) and e.get("note")]
    flags.sort(key=lambda f: SEVERITIES.index(f["severity"]) if f["severity"] in SEVERITIES else len(SEVERITIES))
    final = next((a for a in attempts if a["attempt_id"] == row["final_attempt_id"]), None)
    first = attempts[0] if attempts else None
    current = [h for h in history if h["action"] != "CLEAR_FLAG"]
    return {
        "dispute_id": did, "pk": row["pk"], "row_number": row["row_number"], "event_time": row["event_time"],
        "text_redacted": row["description_redacted"], "delta": row["delta"], "currency": row["currency"],
        "currency_basis": row["currency_basis"], "reason_code": row["reason_code"], "copy_rank": row["copy_rank"],
        "parse_status": row["status"], "delta_consistency": row["delta_consistency"], "n_attempts": row["n_attempts"],
        "recommendation": row["recommendation"], "return_draft": _json(row["return_draft"]),
        "first_attempt_check": first["delta_check"] if first else None,
        "first_attempt_inconsistent": bool(first and first["delta_check"] == "MISMATCH"),
        "claimed_total": final["claimed_total"] if final else None,
        "attempts": attempts, "statements": statements, "flags": flags,
        "has_reminders": any(f["severity"] in REMINDER_SEVERITIES for f in flags),
        "reading": _readings(con, did, row["final_attempt_id"]),
        "first_reading": (_readings(con, did, row["first_attempt_id"])
                          if row["first_attempt_id"] and row["first_attempt_id"] != row["final_attempt_id"] else None),
        "decisions": history, "current_decision": current[-1] if current else None}


def invoice_detail(con: sqlite3.Connection, run_id: str, carrier_invoice_id: str) -> dict | None:
    """One invoice opened (decisions 6.2 and 6.3): basic information, the reconciliation of the model's reading
    against Delta summed over the invoice, and every dispute with its text (redacted), reading, model statements,
    flags sorted by severity, attempts and decision history. Returns None when the invoice is not in this run."""
    q = """SELECT d.*, pr.parse_run_id, pr.status, pr.delta_consistency, pr.n_attempts, pr.first_attempt_id,
                  pr.final_attempt_id, a.recommendation, a.return_draft
           FROM parse_run pr JOIN dispute d ON d.dispute_id = pr.dispute_id
           JOIN dispute_assessment a ON a.dispute_id = d.dispute_id AND a.run_id = pr.run_id
           WHERE pr.run_id = ? AND d.carrier_invoice_id = ? ORDER BY d.row_number, d.dispute_id"""
    rows = con.execute(q, (run_id, carrier_invoice_id)).fetchall()
    if not rows:
        return None
    disputes = [_dispute_detail(con, run_id, r) for r in rows]
    ci = con.execute("SELECT carrier_invoice_no, carrier_id FROM carrier_invoice WHERE carrier_invoice_id = ?",
                     (carrier_invoice_id,)).fetchone()
    sh = con.execute("""SELECT shipment_gid, carrier_id, sap_bol, origin_city, origin_state, origin_country,
                        destination_city, destination_state, destination_country, shipment_amount, planned_distance,
                        straight_line_km FROM shipment WHERE shipment_gid = ?""", (rows[0]["shipment_gid"],)).fetchone()
    counts = dict.fromkeys(SEVERITIES, 0)
    for d in disputes:
        for f in d["flags"]:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    return {"carrier_invoice_id": carrier_invoice_id, "carrier_invoice_no": ci["carrier_invoice_no"] if ci else None,
            "carrier_id": ci["carrier_id"] if ci else None, "shipment": dict(sh) if sh else None,
            "recommendation": _worst([d["recommendation"] for d in disputes]), "flag_counts": counts,
            "reconciliation": {"sum_model_claimed": _sum(d["claimed_total"] for d in disputes),
                               "sum_delta": _sum(d["delta"] for d in disputes),
                               "n_without_reading": sum(d["claimed_total"] is None for d in disputes)},
            "disputes": disputes}


def record_decision(con: sqlite3.Connection, run_id: str, dispute_id: str, action: str, reason: str | None,
                    reviewer_id: str, flag_id: str | None = None) -> dict:
    """Append one reviewer decision and return the stored row.

    `action` must be one of `decision_actions()`. CLEAR_FLAG needs the `flag_id` of a flag on this dispute in this
    run and a non-empty reason (decision 6.4); the other actions take no flag and an optional reason. Earlier
    decisions are never changed: a new decision is a new row. Raises ValueError with a readable message on any
    invalid input (unknown action, unknown dispute or flag, missing reason, bad reviewer id).
    """
    if action not in decision_actions():
        raise ValueError(f"unknown action {action!r}; allowed: {', '.join(decision_actions())}")
    if not isinstance(reviewer_id, str) or not REVIEWER_ID_RE.fullmatch(reviewer_id):
        raise ValueError("reviewer_id must be an internal id of letters, digits, '-' or '_' (no names or emails)")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("reason must be text")
    reason = (reason or "").strip() or None
    if reason and len(reason) > MAX_REASON_CHARS:
        raise ValueError(f"reason is longer than {MAX_REASON_CHARS} characters")
    if not con.execute("SELECT 1 FROM parse_run WHERE run_id = ? AND dispute_id = ?", (run_id, dispute_id)).fetchone():
        raise ValueError(f"dispute {dispute_id!r} is not in run {run_id!r}")
    if action == "CLEAR_FLAG":
        if not reason:
            raise ValueError("CLEAR_FLAG needs a reason")
        if not flag_id or not con.execute("SELECT 1 FROM flag WHERE flag_id = ? AND run_id = ? AND dispute_id = ?",
                                          (flag_id, run_id, dispute_id)).fetchone():
            raise ValueError("CLEAR_FLAG needs the flag_id of a flag on this dispute in this run")
    elif flag_id:
        raise ValueError("flag_id is only used with CLEAR_FLAG")
    row = {"decision_id": uuid.uuid4().hex, "dispute_id": dispute_id, "flag_id": flag_id, "action": action,
           "reason": reason, "bulk_action_id": None, "edited_return_draft": None, "flag_feedback": None,
           "corrected_readings": None, "reviewer_id": reviewer_id,
           "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    cols = list(db.schema()["tables"][DECISION_TABLE]["columns"])
    con.execute(f'INSERT INTO {DECISION_TABLE} ({", ".join(cols)}) VALUES ({", ".join("?" * len(cols))})',
                [row[c] for c in cols])
    con.commit()
    return {k: row[k] for k in ("decision_id", "dispute_id", "flag_id", "action", "reason", "reviewer_id", "decided_at")}


def run_summary(con: sqlite3.Connection, run_id: str) -> dict:
    """Aggregates for the page header: disputes per recommendation and flags per severity."""
    rec = dict(con.execute("SELECT recommendation, COUNT(*) FROM dispute_assessment WHERE run_id = ? GROUP BY 1", (run_id,)).fetchall())
    sev = dict(con.execute("SELECT severity, COUNT(*) FROM flag WHERE run_id = ? GROUP BY 1", (run_id,)).fetchall())
    return {"run_id": run_id, "n_disputes": sum(rec.values()), "recommendations": rec, "flag_counts": sev}


class ReviewServer(ThreadingHTTPServer):
    """HTTP server bound to 127.0.0.1 that serves the review page for one run of one database file."""

    daemon_threads = True

    def __init__(self, db_path: Path, run_id: str | None = None, reviewer_id: str = "reviewer-1", port: int = 0,
                 read_only: bool = False):
        if not REVIEWER_ID_RE.fullmatch(reviewer_id):
            raise ValueError("reviewer id: letters, digits, '-' or '_' only (an internal id, not a name or email)")
        self.db_path, self.reviewer_id, self.read_only = Path(db_path), reviewer_id, read_only
        con = open_db(self.db_path, read_only)
        try:
            ids = run_ids(con)
        finally:
            con.close()
        if run_id is None and len(ids) == 1:
            run_id = ids[0]
        if run_id not in ids:
            raise ValueError(f"run {run_id!r} is not in {self.db_path} (found: {ids})")
        self.run_id = run_id
        super().__init__((HOST, port), _Handler)

    def connection(self) -> sqlite3.Connection:
        """A fresh connection for one request (requests are short and local)."""
        return open_db(self.db_path, self.read_only)


class _Handler(BaseHTTPRequestHandler):
    server: ReviewServer
    server_version = "freight-review-ui"

    def log_message(self, fmt, *args):        # request lines carry ids; keep the terminal quiet
        pass

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; "
                         "style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _local(self) -> bool:
        """Only answer requests addressed to this machine by its loopback name (blocks DNS-rebinding pages)."""
        port = self.server.server_address[1]
        if self.headers.get("Host") in (f"{HOST}:{port}", f"localhost:{port}"):
            return True
        self._json(HTTPStatus.FORBIDDEN, {"error": "local requests only"})
        return False

    def do_GET(self):  # noqa: N802
        if not self._local():
            return
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        srv = self.server
        if url.path == "/":
            return self._send(HTTPStatus.OK, PAGE_PATH.read_bytes(), "text/html; charset=utf-8")
        con = srv.connection()
        try:
            if url.path == "/api/run":
                return self._json(HTTPStatus.OK, run_summary(con, srv.run_id) | {
                    "reviewer_id": srv.reviewer_id, "read_only": srv.read_only, "actions": list(decision_actions())})
            if url.path == "/api/invoices":
                try:
                    return self._json(HTTPStatus.OK, list_invoices(con, srv.run_id, q.get("reminders", "all"),
                                                                   q.get("sort", "reminders")))
                except ValueError as err:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": str(err)})
            if url.path == "/api/invoice":
                detail = invoice_detail(con, srv.run_id, q.get("id", ""))
                if detail is None:
                    return self._json(HTTPStatus.NOT_FOUND, {"error": "invoice not in this run"})
                return self._json(HTTPStatus.OK, detail)
            if url.path == "/api/decisions":
                return self._json(HTTPStatus.OK, decision_history(con, q.get("dispute_id", "")))
        finally:
            con.close()
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if not self._local():
            return
        srv = self.server
        if urlparse(self.path).path != "/api/decision":
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        if srv.read_only:
            return self._json(HTTPStatus.FORBIDDEN, {"error": "started with --read-only: decisions are not recorded"})
        # a JSON content type cannot be sent by another site's plain form, so other pages cannot post decisions
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            return self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Content-Type must be application/json"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY_BYTES:
                raise ValueError("missing or oversized body")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or not isinstance(body.get("dispute_id"), str) or not isinstance(body.get("action"), str):
                raise ValueError("body must be an object with dispute_id and action")
            con = srv.connection()
            try:
                saved = record_decision(con, srv.run_id, body["dispute_id"], body["action"], body.get("reason"),
                                        srv.reviewer_id, body.get("flag_id") or None)
            finally:
                con.close()
        except ValueError as err:              # includes json.JSONDecodeError
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(err)})
        self._json(HTTPStatus.CREATED, saved)


def main(argv: list[str] | None = None) -> None:
    """Command line entry: serve the review page for one run until interrupted (Ctrl-C)."""
    ap = argparse.ArgumentParser(description="Local review page for one run (binds to 127.0.0.1 only).")
    ap.add_argument("--run", help="run id; opens data/interim/runs/<run>/run.sqlite")
    ap.add_argument("--db", type=Path, help="path of a run database, instead of the one that belongs to --run")
    ap.add_argument("--reviewer", default="reviewer-1", help="internal reviewer id stored with each decision (no names)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--read-only", action="store_true", help="open the database read-only; nothing can be recorded")
    args = ap.parse_args(argv)
    if not args.run and not args.db:
        ap.error("give --run <run_id> or --db <path>")
    try:
        srv = ReviewServer(args.db or run_db_path(args.run), args.run, args.reviewer, args.port, args.read_only)
    except (ValueError, FileNotFoundError) as err:
        ap.error(str(err))
    print(f"review page: http://{HOST}:{srv.server_address[1]}/   run {srv.run_id}   reviewer {srv.reviewer_id}"
          f"{'   READ-ONLY' if srv.read_only else ''}\nCtrl-C to stop", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
