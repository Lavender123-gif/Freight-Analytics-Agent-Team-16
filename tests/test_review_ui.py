"""U2: review interface. Synthetic run database (no real rows): listing, filter, detail, recording decisions,
history kept, invalid input rejected, local-only HTTP behaviour."""

import json
import sqlite3
import threading
import urllib.error
import urllib.request

import pytest

from freight_lineitems import db, review_ui
from freight_lineitems.config import RULES
from freight_lineitems.pipeline import assemble, prepare

from helpers import L, N, S, record

RUN = "run-ui"
SECRET = "RAW ONLY MARKER"


def _result(rec, flags, recommendation, attempts):
    out = assemble(prepare(rec), None)
    out["facts"]["parse_status"] = "PASSED_CHECKS"
    out["facts"]["delta_consistency"] = "MATCH_FIRST" if len(attempts) == 1 else "MISMATCH_MODEL_INSISTED"
    out["facts"]["text_redacted"] = out["facts"]["text_redacted"].replace(SECRET, "<REDACTED>")
    out["process"] = {"attempts": attempts, "final": {"attempt_no": len(attempts)},
                      "transcript": {"calls": [], "first_user_message": "u"}}
    out["judgment"] = {"flags": flags, "recommendation": recommendation, "decisive_flags": [f["code"] for f in flags],
                       "diagnostics": [], "return_draft": None}
    return out


def _attempt(no, check, rtype="FIRST", reason=None):
    sub = S([N("#1", codes=["ACCESSORIAL.LIFTGATE"], ev="LIFTGATE")], [L("#1", label="LIFTGATE")], rtype=rtype, reason=reason)
    return {"attempt_no": no, "raw_submission": sub, "repair_errors": [], "delta_check": check,
            "feedback_given": None if no == 1 else "inconsistent", "response_type": rtype, "claim": {"signed_sum": "15.00"}}


def _flag(code, severity, origin="CODE_RULE", evidence=None):
    return {"code": code, "severity": severity, "origin": origin, "paths": [], "evidence": evidence or [{}]}


@pytest.fixture
def run_db(tmp_path):
    """Two invoices: I1 has a clean dispute and one with reminders (first attempt inconsistent); I2 is clean."""
    a = record("LIFTGATE $15.00", "15", rid="syn#r1", shipment="S1", invoice="I1", pk="P1")
    b = record(f"LIFTGATE $15.00 {SECRET}", "16", rid="syn#r2", shipment="S1", invoice="I1", pk="P2")
    c = record("LIFTGATE $15.00", "15", rid="syn#r3", shipment="S2", invoice="I2", pk="P3")
    for i, r in enumerate((a, b, c)):
        r.row_number = i + 1
    res = [
        _result(a, [_flag("NUM.PARSE.SPACE_MERGED", "info")], "PASSED_CHECKS", [_attempt(1, "MATCH")]),
        _result(b, [_flag("CLAIM.DELTA.MISMATCH_INSISTED", "attention"), _flag("ITEM.AMOUNT.UNNAMED", "return"),
                    _flag("RUN.AGENT.UNCERTAINTY_REPORTED", "attention", "MODEL_REPORTED", [{"reason_type": "X", "note": "not sure about the total"}])],
                "HUMAN_REVIEW", [_attempt(1, "MISMATCH"), _attempt(2, "MISMATCH", "INSISTED", "the text says fifteen")]),
        _result(c, [], "PASSED_CHECKS", [_attempt(1, "MATCH")]),
    ]
    path = tmp_path / "run.sqlite"
    con = db.connect(path)
    db.write_run(con, RUN, "synthetic", [a, b, c], res, {"model": "m"}, RULES)
    con.close()
    return path


@pytest.fixture
def con(run_db):
    c = review_ui.open_db(run_db)
    yield c
    c.close()


def _invoice_of(con, dispute_id):
    return con.execute("SELECT carrier_invoice_id FROM dispute WHERE dispute_id = ?", (dispute_id,)).fetchone()[0]


def test_actions_come_from_schema_and_are_the_four_of_decision_6_4():
    assert review_ui.decision_actions() == ("APPROVE", "RETURN_TO_CARRIER", "CLEAR_FLAG", "HOLD")


def test_listing_shows_colour_and_counts_per_severity(con):
    rows = review_ui.list_invoices(con, RUN)
    assert len(rows) == 2
    first = rows[0]                                             # most reminders first
    assert first["carrier_invoice_id"] == _invoice_of(con, "syn#r2")
    assert first["recommendation"] == "HUMAN_REVIEW" and first["n_disputes"] == 2
    assert first["flag_counts"] == {"ATTENTION": 2, "RETURN": 1, "INFO": 1}
    assert rows[1]["recommendation"] == "PASSED_CHECKS" and rows[1]["flag_counts"] == {"ATTENTION": 0, "RETURN": 0, "INFO": 0}


def test_filter_by_reminders(con):
    yes, no = review_ui.list_invoices(con, RUN, "yes"), review_ui.list_invoices(con, RUN, "no")
    assert [i["carrier_invoice_id"] for i in yes] == [_invoice_of(con, "syn#r2")]
    assert [i["carrier_invoice_id"] for i in no] == [_invoice_of(con, "syn#r3")]
    assert all(i["has_reminders"] for i in yes) and not any(i["has_reminders"] for i in no)
    with pytest.raises(ValueError):
        review_ui.list_invoices(con, RUN, "maybe")


def test_info_only_invoice_counts_as_no_reminders(run_db):
    """An invoice whose only flags are INFO has no reminders (decision 2.3: info flags do not change the colour)."""
    c = review_ui.open_db(run_db)
    c.execute("DELETE FROM flag WHERE severity != 'INFO'")
    rows = review_ui.list_invoices(c, RUN, "yes")
    c.close()
    assert rows == []


def test_detail_has_text_reading_statements_flags_and_first_attempt_marker(con):
    inv = review_ui.invoice_detail(con, RUN, _invoice_of(con, "syn#r2"))
    assert inv["shipment"]["shipment_gid"] == "S1" and inv["reconciliation"] == {
        "sum_model_claimed": "30.00", "sum_delta": "31", "n_without_reading": 0}
    clean, flagged = inv["disputes"]
    assert not clean["first_attempt_inconsistent"] and not clean["has_reminders"]
    assert flagged["first_attempt_inconsistent"] and flagged["has_reminders"] and flagged["n_attempts"] == 2
    assert [f["severity"] for f in flagged["flags"]] == ["ATTENTION", "ATTENTION", "RETURN"]
    assert flagged["reading"]["line_items"][0]["charge_code"] == "ACCESSORIAL.LIFTGATE"
    assert flagged["reading"]["numbers"][0]["raw"] and flagged["first_reading"]["attempt_id"].endswith(":1")
    texts = {s["type"]: s["text"] for s in flagged["statements"]}
    assert texts == {"INSIST_REASON": "the text says fifteen", "UNCERTAINTY": "not sure about the total"}
    assert review_ui.invoice_detail(con, RUN, "no-such-invoice") is None


def test_only_redacted_text_reaches_the_page(con):
    blob = json.dumps(review_ui.invoice_detail(con, RUN, _invoice_of(con, "syn#r2")))
    assert SECRET not in blob and "<REDACTED>" in blob and "raw_columns" not in blob and "llm_input" not in blob


def test_decision_is_recorded_and_history_is_kept(con):
    first = review_ui.record_decision(con, RUN, "syn#r2", "HOLD", "waiting for the bill of lading", "rev-1")
    second = review_ui.record_decision(con, RUN, "syn#r2", "APPROVE", None, "rev-2")
    hist = review_ui.decision_history(con, "syn#r2")
    assert [h["action"] for h in hist] == ["HOLD", "APPROVE"] and [h["reviewer_id"] for h in hist] == ["rev-1", "rev-2"]
    assert hist[0]["reason"] == "waiting for the bill of lading" and hist[0]["decided_at"] and first["decision_id"] != second["decision_id"]
    d = review_ui.invoice_detail(con, RUN, _invoice_of(con, "syn#r2"))["disputes"][1]
    assert d["current_decision"]["action"] == "APPROVE" and len(d["decisions"]) == 2
    row = next(i for i in review_ui.list_invoices(con, RUN) if i["n_disputes"] == 2)
    assert row["n_disputes_decided"] == 1


def test_decisions_cannot_be_changed_or_deleted(con):
    review_ui.record_decision(con, RUN, "syn#r1", "HOLD", None, "rev-1")
    for stmt in ("UPDATE reviewer_decision SET action = 'APPROVE'", "DELETE FROM reviewer_decision"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            con.execute(stmt)
    assert [h["action"] for h in review_ui.decision_history(con, "syn#r1")] == ["HOLD"]


def test_recording_changes_nothing_else_in_the_run(run_db, con):
    tables = [t for t in db.schema()["tables"] if t != "reviewer_decision"]
    before = {t: con.execute(f'SELECT * FROM "{t}" ORDER BY 1, 2').fetchall() for t in tables}
    review_ui.record_decision(con, RUN, "syn#r3", "RETURN_TO_CARRIER", "charge name missing", "rev-1")
    assert {t: con.execute(f'SELECT * FROM "{t}" ORDER BY 1, 2').fetchall() for t in tables} == before
    assert db.export_facts(sqlite3.connect(run_db), RUN)        # downstream export is untouched by a decision


def test_clear_flag_needs_reason_and_a_flag_of_this_dispute(con):
    flags = {f["code"]: f["flag_id"] for f in review_ui.invoice_detail(con, RUN, _invoice_of(con, "syn#r2"))["disputes"][1]["flags"]}
    fid = flags["ITEM.AMOUNT.UNNAMED"]
    for kwargs in ({"reason": None, "flag_id": fid}, {"reason": "  ", "flag_id": fid}, {"reason": "ok", "flag_id": None},
                   {"reason": "ok", "flag_id": "nope"}):
        with pytest.raises(ValueError):
            review_ui.record_decision(con, RUN, "syn#r2", "CLEAR_FLAG", reviewer_id="rev-1", **kwargs)
    with pytest.raises(ValueError):                             # a flag of another dispute
        review_ui.record_decision(con, RUN, "syn#r1", "CLEAR_FLAG", "ok", "rev-1", fid)
    with pytest.raises(ValueError):                             # flag_id only goes with CLEAR_FLAG
        review_ui.record_decision(con, RUN, "syn#r2", "HOLD", "ok", "rev-1", fid)
    review_ui.record_decision(con, RUN, "syn#r2", "CLEAR_FLAG", "checked against the text", "rev-1", fid)
    d = review_ui.invoice_detail(con, RUN, _invoice_of(con, "syn#r2"))["disputes"][1]
    assert {f["code"]: f["cleared"] for f in d["flags"]}["ITEM.AMOUNT.UNNAMED"] is True
    assert d["current_decision"] is None                        # clearing a flag is not a decision on the dispute
    assert sum(f["cleared"] for f in d["flags"]) == 1
    row = next(i for i in review_ui.list_invoices(con, RUN) if i["n_disputes"] == 2)
    assert row["n_flags_cleared"] == 1 and row["flag_counts"]["RETURN"] == 1      # rule counts stay as computed


@pytest.mark.parametrize("action", ["PAY", "DENY", "approve", "", "REJECT"])
def test_unknown_decision_value_is_rejected(con, action):
    with pytest.raises(ValueError):
        review_ui.record_decision(con, RUN, "syn#r1", action, "x", "rev-1")
    assert review_ui.decision_history(con, "syn#r1") == []


def test_unknown_dispute_and_bad_reviewer_are_rejected(con):
    with pytest.raises(ValueError):
        review_ui.record_decision(con, RUN, "syn#r99", "HOLD", None, "rev-1")
    with pytest.raises(ValueError):
        review_ui.record_decision(con, "other-run", "syn#r1", "HOLD", None, "rev-1")
    with pytest.raises(ValueError):
        review_ui.record_decision(con, RUN, "syn#r1", "HOLD", None, "someone@example.com")
    with pytest.raises(ValueError):
        review_ui.record_decision(con, RUN, "syn#r1", "HOLD", "x" * (review_ui.MAX_REASON_CHARS + 1), "rev-1")


def test_missing_database_is_not_created(tmp_path):
    with pytest.raises(FileNotFoundError):
        review_ui.open_db(tmp_path / "absent.sqlite")
    assert not (tmp_path / "absent.sqlite").exists()


# ---- over HTTP ----

@pytest.fixture
def server(run_db):
    srv = review_ui.ReviewServer(run_db, RUN, "rev-http", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _call(srv, path, body=None, headers=None):
    url = f"http://127.0.0.1:{srv.server_address[1]}{path}"
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} | (headers or {}) if data else (headers or {}))
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            raw, status = res.read(), res.status
    except urllib.error.HTTPError as err:
        raw, status = err.read(), err.code
    return status, raw


def test_server_binds_to_loopback_only(server):
    assert server.server_address[0] == "127.0.0.1" and review_ui.HOST == "127.0.0.1"


def test_page_is_self_contained_and_has_no_payment_wording(server):
    status, raw = _call(server, "/")
    page = raw.decode()
    assert status == 200 and "http://" not in page and "https://" not in page and "src=" not in page and "<link" not in page
    for word in ("该付", "应付", "拒付", "不应支付", "建议批准", "建议付款", "deny", "DENY"):
        assert word not in page.replace("不代表这笔费用该不该付", "")
    for label in ("批准", "退回承运商", "清除标识", "暂缓"):                # the four buttons of decision 6.4
        assert label in page


def test_http_list_filter_post_and_read_back(server):
    status, raw = _call(server, "/api/invoices?reminders=yes")
    rows = json.loads(raw)
    assert status == 200 and len(rows) == 1 and rows[0]["flag_counts"]["ATTENTION"] == 2
    status, raw = _call(server, "/api/decision", {"dispute_id": "syn#r2", "action": "HOLD", "reason": "need the POD"})
    saved = json.loads(raw)
    assert status == 201 and saved["reviewer_id"] == "rev-http"
    _call(server, "/api/decision", {"dispute_id": "syn#r2", "action": "RETURN_TO_CARRIER", "reason": ""})
    status, raw = _call(server, "/api/decisions?dispute_id=syn%23r2")
    assert status == 200 and [h["action"] for h in json.loads(raw)] == ["HOLD", "RETURN_TO_CARRIER"]
    status, raw = _call(server, "/api/invoice?id=" + urllib.request.quote(rows[0]["carrier_invoice_id"], safe=""))
    assert status == 200 and json.loads(raw)["disputes"][1]["current_decision"]["action"] == "RETURN_TO_CARRIER"
    assert json.loads(_call(server, "/api/run")[1])["actions"] == list(review_ui.decision_actions())


def test_http_rejects_bad_input(server):
    assert _call(server, "/api/decision", {"dispute_id": "syn#r1", "action": "PAY"})[0] == 400
    assert _call(server, "/api/decision", b"not json")[0] == 400
    assert _call(server, "/api/decision", {"action": "HOLD"})[0] == 400
    assert _call(server, "/api/decision", {"dispute_id": "syn#r1", "action": "HOLD"}, {"Content-Type": "text/plain"})[0] == 415
    assert _call(server, "/api/invoices", headers={"Host": "evil.example"})[0] == 403
    assert _call(server, "/api/invoices?reminders=maybe")[0] == 400
    assert _call(server, "/api/invoice?id=zzz")[0] == 404 and _call(server, "/nope")[0] == 404
    assert json.loads(_call(server, "/api/decisions?dispute_id=syn%23r1")[1]) == []


def test_read_only_mode_records_nothing(run_db):
    review_ui.open_db(run_db).close()                           # decision table and triggers exist
    srv = review_ui.ReviewServer(run_db, None, "rev-ro", port=0, read_only=True)       # single run: id inferred
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert srv.run_id == RUN and _call(srv, "/api/invoices")[0] == 200
        assert _call(srv, "/api/decision", {"dispute_id": "syn#r1", "action": "HOLD"})[0] == 403
    finally:
        srv.shutdown()
        srv.server_close()
    assert sqlite3.connect(run_db).execute("SELECT COUNT(*) FROM reviewer_decision").fetchone()[0] == 0


def test_unknown_run_is_refused(run_db):
    with pytest.raises(ValueError):
        review_ui.ReviewServer(run_db, "other-run", port=0)
