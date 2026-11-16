"""U2: review interface. Synthetic run database (no real rows): listing, filter, detail, recording decisions,
history kept, invalid input rejected, local-only HTTP behaviour. Task 20b: the invoice header reads the stored
shipment result (pipeline.finish_batch), and every text on the page is English."""

import json
import re
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import datetime
from decimal import Decimal

import pytest

from freight_lineitems import db, review_ui
from freight_lineitems.config import RULES
from freight_lineitems.pipeline import assemble, finish_batch, prepare

from helpers import L, N, S, record

RUN = "run-ui"
SECRET = "RAW ONLY MARKER"
CJK = re.compile(r"[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]")


def _number_id(out, value):
    return next(n["id"] for n in out["facts"]["number_table"]["numbers"] if Decimal(str(n["value"])) == Decimal(value))


def _reading(out, items):
    """A hand-written reading: `items` are (value, kind, codes, label); other numbers are references."""
    nums, lis, seen = [], [], set()
    for value, kind, codes, label in items:
        nid = _number_id(out, value)
        nums.append(N(nid, kind=kind, codes=codes, ev=label))
        lis.append(L(nid, label=label))
        seen.add(nid)
    nums += [N(n["id"], kind="REFERENCE", status="NONE", ev="x") for n in out["facts"]["number_table"]["numbers"]
             if n["id"] not in seen]
    return S(nums, lis)


LIFTGATE_READING = [("15.00", "CHARGE_AMOUNT", ["ACCESSORIAL.LIFTGATE"], "LIFTGATE")]


def _result(rec, flags, recommendation, attempts, items=LIFTGATE_READING):
    out = assemble(prepare(rec), None)
    out["facts"]["parse_status"] = "PASSED_CHECKS"
    out["facts"]["text_redacted"] = out["facts"]["text_redacted"].replace(SECRET, "<REDACTED>")
    out["facts"]["reading"] = _reading(out, items)
    out["process"] = {"attempts": attempts, "final": {"attempt_no": len(attempts)},
                      "transcript": {"calls": [], "first_user_message": "u"}}
    out["judgment"] = {"flags": flags, "recommendation": recommendation, "decisive_flags": [f["code"] for f in flags],
                       "diagnostics": [], "return_draft": None}
    return out


def _attempt(no, check, rtype="FIRST", reason=None):
    sub = S([N("#1", codes=["ACCESSORIAL.LIFTGATE"], ev="LIFTGATE")], [L("#1", label="LIFTGATE")], rtype=rtype, reason=reason)
    return {"attempt_no": no, "raw_submission": sub, "repair_errors": [], "checks_passed": check == "MATCH",
            "response_type": rtype, "claim": {"signed_sum": "15.00"}}


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
        _result(b, [_flag("ITEM.TAX.NO_AMOUNT", "attention"), _flag("ITEM.AMOUNT.UNNAMED", "return"),
                    _flag("RUN.AGENT.UNCERTAINTY_REPORTED", "attention", "MODEL_REPORTED", [{"reason_type": "X", "note": "not sure about the total"}])],
                "HUMAN_REVIEW", [_attempt(1, "MISMATCH"), _attempt(2, "MISMATCH", "INSISTED", "the text says fifteen")]),
        _result(c, [], "PASSED_CHECKS", [_attempt(1, "MATCH")]),
    ]
    return _write(tmp_path, [a, b, c], res)


def _write(tmp_path, records, results):
    """Store a run the way pipeline.write_outputs does: explanations, then the shipment results of finish_batch."""
    results, ships = finish_batch(records, results)
    path = tmp_path / "run.sqlite"
    con = db.connect(path)
    db.write_run(con, RUN, "synthetic", records, results, {"model": "m"}, RULES)
    db.write_shipments(con, RUN, ships)
    con.close()
    (tmp_path / "shipments.jsonl").write_text("".join(json.dumps(sh, default=str) + "\n" for sh in ships))
    return path


@pytest.fixture
def con(run_db):
    c = review_ui.open_db(run_db)
    yield c
    c.close()


def _invoice_of(con, dispute_id):
    return con.execute("SELECT carrier_invoice_id FROM dispute WHERE dispute_id = ?", (dispute_id,)).fetchone()[0]


def test_actions_come_from_schema_and_are_the_four_of_decision_6_4():
    assert review_ui.decision_actions() == ("ACCEPT_READING", "RETURN_TO_CARRIER", "CLEAR_FLAG", "HOLD")


def test_listing_shows_colour_and_counts_per_severity(con):
    rows = review_ui.list_invoices(con, RUN)
    assert len(rows) == 2
    first = rows[0]                                             # most reminders first
    assert first["carrier_invoice_id"] == _invoice_of(con, "syn#r2")
    assert first["recommendation"] == "HUMAN_REVIEW" and first["n_disputes"] == 2
    # task 23 (F-02): the two shipment flags of S1 (ORDER_TIED, SUPERSEDED_SAME_CHARGE) count with the disputes' flags
    assert first["dispute_flag_counts"] == {"ATTENTION": 2, "RETURN": 1, "INFO": 1}
    assert first["shipment_flag_counts"] == {"ATTENTION": 2, "RETURN": 0, "INFO": 0}
    assert first["flag_counts"] == {"ATTENTION": 4, "RETURN": 1, "INFO": 1} and first["n_reminders"] == 5
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
    for gid, res in c.execute("SELECT shipment_gid, result FROM shipment_result WHERE run_id = ?", (RUN,)).fetchall():
        r = json.loads(res)
        r["flags"] = [f for f in r["flags"] if f["severity"] == "info"]
        c.execute("UPDATE shipment_result SET result = ? WHERE run_id = ? AND shipment_gid = ?", (json.dumps(r), RUN, gid))
    rows = review_ui.list_invoices(c, RUN, "yes")
    c.close()
    assert rows == []


def test_detail_has_text_reading_statements_flags_and_first_attempt(con):
    inv = review_ui.invoice_detail(con, RUN, _invoice_of(con, "syn#r2"))
    assert inv["shipment"]["shipment_gid"] == "S1" and "reconciliation" not in inv   # task 20b: no sum made by the page
    assert [s["shipment_key"] for s in inv["shipments"]] == ["S1"] and inv["recommendation"] == "HUMAN_REVIEW"
    clean, flagged = inv["disputes"]
    assert not clean["has_reminders"] and "delta" not in clean and "first_attempt_inconsistent" not in clean
    assert flagged["has_reminders"] and flagged["n_attempts"] == 2
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
    second = review_ui.record_decision(con, RUN, "syn#r2", "ACCEPT_READING", None, "rev-2")
    hist = review_ui.decision_history(con, "syn#r2")
    assert [h["action"] for h in hist] == ["HOLD", "ACCEPT_READING"] and [h["reviewer_id"] for h in hist] == ["rev-1", "rev-2"]
    assert hist[0]["reason"] == "waiting for the bill of lading" and hist[0]["decided_at"] and first["decision_id"] != second["decision_id"]
    d = review_ui.invoice_detail(con, RUN, _invoice_of(con, "syn#r2"))["disputes"][1]
    assert d["current_decision"]["action"] == "ACCEPT_READING" and len(d["decisions"]) == 2
    row = next(i for i in review_ui.list_invoices(con, RUN) if i["n_disputes"] == 2)
    assert row["n_disputes_decided"] == 1


def test_decisions_cannot_be_changed_or_deleted(con):
    review_ui.record_decision(con, RUN, "syn#r1", "HOLD", None, "rev-1")
    for stmt in ("UPDATE reviewer_decision SET action = 'ACCEPT_READING'", "DELETE FROM reviewer_decision"):
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


@pytest.mark.parametrize("action", ["PAY", "DENY", "APPROVE", "approve", "", "REJECT"])
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
    for word in ("should be paid", "should not be paid", "payable", "approve", "Approve", "deny", "DENY", "Deny"):
        assert word not in page.replace("they do not say whether a charge should be paid", "")
    assert "APPROVE" not in page                               # task 20 (P-24): the button records a reading, not a payment
    labels = json.loads(_call(server, "/api/run")[1])["labels"]
    assert [labels["action"][a] for a in review_ui.decision_actions()] == ["Accept reading", "Return to carrier", "Clear flag", "Hold"]
    assert not any(re.search(r"approv|deny|pay", v, re.I) for grp in labels.values() for v in grp.values())


def test_http_list_filter_post_and_read_back(server):
    status, raw = _call(server, "/api/invoices?reminders=yes")
    rows = json.loads(raw)
    assert status == 200 and len(rows) == 1 and rows[0]["flag_counts"]["ATTENTION"] == 4   # 2 dispute + 2 shipment flags
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


# ---- task 20b: the header shows the stored shipment result ----

def _pt_records():
    """Synthetic two-explanation shipment shaped like round-4 mock SHP-R4-PT-00: the later explanation names the
    same charge (finest code) and replaces the earlier one. Each explanation on its own is clean."""
    a = record("PURCHASED TRANSPORTATION SURCHARGE $18.00", "18", rid="syn#p1", shipment="SHP-PT", invoice="IPT", pk="PT1")
    b = record("PURCHASED TRANSPORTATION SURCHARGE $25.25 + HST $1.26", "26.51", rid="syn#p2", shipment="SHP-PT",
               invoice="IPT", pk="PT1")
    for i, (r, day) in enumerate(((a, 1), (b, 2))):
        r.row_number, r.event_date, r.shipment_amount = i + 1, datetime(2022, 3, day, 10), Decimal("1530.00")
    code = ["PENDING.PURCHASED_TRANSPORTATION"]
    res = []
    for r, items in ((a, [("18.00", "CHARGE_AMOUNT", code, "PURCHASED TRANSPORTATION SURCHARGE")]),
                     (b, [("25.25", "CHARGE_AMOUNT", code, "PURCHASED TRANSPORTATION SURCHARGE"),
                          ("1.26", "TAX_AMOUNT", ["TAX.HST"], "HST")])):
        res.append(_result(r, [], "PASSED_CHECKS", [_attempt(1, "MATCH")], items))
    return [a, b], res


@pytest.fixture
def pt_db(tmp_path):
    return _write(tmp_path, *_pt_records())


def test_header_reads_the_stored_shipment_result_not_a_page_sum(pt_db, tmp_path):
    ship = json.loads((tmp_path / "shipments.jsonl").read_text().splitlines()[0])      # the main flow's output
    assert ship["recommendation"] == "HUMAN_REVIEW" and ship["new_total"] == "1556.51"  # replacement -> reminder
    assert ship["other_readings"], "the replaced amount gives another reading"
    con = review_ui.open_db(pt_db)
    inv = review_ui.invoice_detail(con, RUN, _invoice_of(con, "syn#p1"))
    row = review_ui.list_invoices(con, RUN)[0]
    con.close()
    assert [d["recommendation"] for d in inv["disputes"]] == ["PASSED_CHECKS", "PASSED_CHECKS"]   # each one is clean
    hdr = inv["shipments"][0]
    assert inv["recommendation"] == row["recommendation"] == hdr["recommendation"] == "HUMAN_REVIEW"
    assert review_ui.LABELS["recommendation"][hdr["recommendation"]] == "Human review"
    for k in review_ui.SHIPMENT_HEADER_FIELDS:
        assert hdr[k] == ship[k], k
    assert hdr["new_total"] == "1556.51" and hdr["default_change"] == ship["default_change"]
    assert [o["new_total"] for o in hdr["other_readings"]] == [o["new_total"] for o in ship["other_readings"]]
    assert [(f["code"], f["severity"]) for f in hdr["flags"]] == [(f["code"], f["severity"].upper()) for f in ship["flags"]]
    assert any(f["severity"] == "ATTENTION" for f in hdr["flags"])
    assert row["shipments"][0]["new_total"] == "1556.51" and "reconciliation" not in inv
    assert hdr["explanation_ids"] == ["syn#p1", "syn#p2"]


def test_page_and_api_have_no_chinese_text(pt_db):
    srv = review_ui.ReviewServer(pt_db, RUN, "rev-en", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        inv_id = json.loads(_call(srv, "/api/invoices")[1])[0]["carrier_invoice_id"]
        bodies = [_call(srv, p)[1].decode() for p in ("/", "/api/run", "/api/invoices",
                                                       "/api/invoice?id=" + urllib.request.quote(inv_id, safe=""))]
    finally:
        srv.shutdown()
        srv.server_close()
    for body in bodies:
        assert not CJK.search(body), CJK.findall(body)[:5]
    assert '<html lang="en">' in bodies[0] and "Human review" in bodies[1]


def test_run_without_stored_shipment_result_shows_none(run_db):
    """A run made before task 20 has no shipment result: the header says so instead of computing one."""
    c = review_ui.open_db(run_db)
    c.execute("DELETE FROM shipment_result")
    rows = review_ui.list_invoices(c, RUN)
    inv = review_ui.invoice_detail(c, RUN, rows[0]["carrier_invoice_id"])
    c.close()
    assert all(r["recommendation"] is None for r in rows) and inv["recommendation"] is None
    assert inv["shipments"] == [{"shipment_key": "S1", "missing": True}] or inv["shipments"][0]["missing"]


def _shipment_only_db(tmp_path):
    """Two invoices, every dispute clean. Invoice IZ's shipment has one attention flag at shipment level only (a later
    explanation replaces an earlier one); invoice IB's shipment has none. IZ sorts after IB by name, so the default
    sort putting IZ first is the reminder sort. Mirrors the audit's F-02 reproduction."""
    a1 = record("LIFTGATE $15.00", "15", rid="syn#s1", shipment="SA", invoice="IZ", pk="P1")
    a2 = record("LIFTGATE CHARGE $15.00", "15", rid="syn#s2", shipment="SA", invoice="IZ", pk="P2")
    b1 = record("LIFTGATE $15.00", "15", rid="syn#s3", shipment="SB", invoice="IB", pk="P3")
    a2.event_date = datetime(2022, 3, 2, 10, 0)
    for i, r in enumerate((a1, a2, b1)):
        r.row_number = i + 1
    res = [_result(r, [], "PASSED_CHECKS", [_attempt(1, "MATCH")]) for r in (a1, a2, b1)]
    return _write(tmp_path, [a1, a2, b1], res)


def test_shipment_only_reminders_count_in_list_filter_and_sort(tmp_path):
    """Task 23 (audit F-02): a shipment whose only reminder is a shipment-level flag is counted, filtered as 'has
    reminders' and sorted first, though every dispute in it passed its checks."""
    con = review_ui.open_db(_shipment_only_db(tmp_path))
    try:
        ia, ib = _invoice_of(con, "syn#s1"), _invoice_of(con, "syn#s3")
        rows = review_ui.list_invoices(con, RUN)
        by = {r["carrier_invoice_id"]: r for r in rows}
        a = by[ia]
        assert a["dispute_flag_counts"]["ATTENTION"] == 0 and a["dispute_flag_counts"]["RETURN"] == 0
        assert [f["code"] for s in a["shipments"] for f in s["flags"] if f["severity"] == "ATTENTION"] == \
            ["SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE"]
        assert a["recommendation"] == "HUMAN_REVIEW"
        assert a["shipment_flag_counts"]["ATTENTION"] == 1 and a["flag_counts"]["ATTENTION"] == 1
        assert a["n_reminders"] == 1 and a["has_reminders"] is True
        assert by[ib]["n_reminders"] == 0 and by[ib]["has_reminders"] is False
        assert [r["carrier_invoice_id"] for r in rows] == [ia, ib]                         # default sort: reminders first
        assert [r["carrier_invoice_id"] for r in review_ui.list_invoices(con, RUN, sort="invoice")] == [ib, ia]
        assert [r["carrier_invoice_id"] for r in review_ui.list_invoices(con, RUN, "yes")] == [ia]
        assert [r["carrier_invoice_id"] for r in review_ui.list_invoices(con, RUN, "no")] == [ib]
    finally:
        con.close()
