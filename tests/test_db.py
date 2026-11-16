"""S2 / P5: tables from schema v1, Excel ingest, fact export holds only passed records with no flag to look at."""

import json

import pandas as pd
import pytest

from freight_lineitems import db
from freight_lineitems.config import DEV_PATH, RULES
from freight_lineitems.pipeline import assemble, prepare
from freight_lineitems.records import EXPECTED_COLUMNS, load_excel

from helpers import record


def test_every_schema_table_is_created(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(db.schema()["tables"]) <= names


def _result(rec, status, _dc=None):
    out = assemble(prepare(rec), None)
    out["facts"]["parse_status"] = status
    sub = {"response_type": "FIRST", "reason": None, "relations": [], "unrecognized_reads": [],
           "numbers": [{"id": "#1", "kind": "CHARGE_AMOUNT", "status": "CLAIMED", "is_credit": False,
                        "charge_codes": ["ACCESSORIAL.LIFTGATE"], "other_phrase": None, "evidence_phrase": "LIFTGATE",
                        "exclusion_phrase": None}],
           "line_items": [{"amount_ref": "#1", "charge_codes": [], "raw_charge_label": "LIFTGATE", "carrier_stated_reason": None,
                           "carrier_stated_basis_type": "NONE", "carrier_stated_basis": None}]}
    out["process"] = {"attempts": [{"attempt_no": 1, "raw_submission": sub, "repair_errors": [], "delta_check": "MATCH",
                                    "feedback_given": None, "response_type": "FIRST", "claim": {"signed_sum": "15.00"}}],
                      "final": {"attempt_no": 1}, "transcript": {"calls": [], "first_user_message": "u"}}
    return out


def test_fact_export_does_not_depend_on_delta(tmp_path):
    """Task 14 C1: a passed reading is exported whatever the Excel Delta column says (differs, or zero)."""
    recs = [record("LIFTGATE $15.00", "15", rid="dev#r1"), record("LIFTGATE $15.00 X", "16", rid="dev#r2"),
            record("LIFTGATE $15.00 Y", "0", rid="dev#r3")]
    for i, r in enumerate(recs):
        r.row_number = i
    res = [_result(recs[0], "PASSED_CHECKS", "MATCH_FIRST"), _result(recs[1], "PASSED_CHECKS", "MISMATCH_MODEL_INSISTED"),
           _result(recs[2], "PASSED_CHECKS", "NO_ANCHOR")]
    for r in res:      # these records carry no flags in this test
        r["judgment"] = {"flags": [], "recommendation": "PASSED_CHECKS", "decisive_flags": [], "diagnostics": []}
    con = db.connect(tmp_path / "t.sqlite")
    db.write_run(con, "run1", "test", recs, res, {"model": "m"}, RULES)
    facts = db.export_facts(con, "run1")
    assert [f["dispute_id"] for f in facts] == ["dev#r1", "dev#r2", "dev#r3"]
    assert facts[0]["line_items"][0]["charge_code"] == "ACCESSORIAL.LIFTGATE" and facts[0]["currency"] == "USD"
    assert "delta" not in json.dumps(facts).lower()
    blob = json.dumps(facts)
    assert "flag" not in blob and "recommendation" not in blob            # fact layer carries no judgment
    review = db.export_review(con, "run1")
    assert {r["dispute_id"] for r in review} == {"dev#r1", "dev#r2", "dev#r3"}


def test_excel_ingest_reads_text_cells_unchanged(tmp_path):
    row = {c: "" for c in EXPECTED_COLUMNS} | {"SHIPMENT_GID": "S9", "PK": "P9", "Carrier Invoice": "0012", "Descritipion": "LIFTGATE $15.00",
                                               "Invoice Amount": "115.00", "Shipment Amount": "100.00", "Delta": "15.000000000000002",
                                               "Carrier": "C9", "Source State": "ON", "Destination State": "ON",
                                               "Event Date": "2022-01-01 10:00:00", "Reason Code": "R"}
    p = tmp_path / "x.xlsx"
    pd.DataFrame([row]).to_excel(p, index=False)
    before = p.read_bytes()
    recs = load_excel(p)
    assert p.read_bytes() == before                                      # source never modified
    assert recs[0].carrier_invoice == "0012" and str(recs[0].delta) == "15.00"
    with pytest.raises(ValueError):
        pd.DataFrame([{"A": 1}]).to_excel(tmp_path / "bad.xlsx", index=False)
        load_excel(tmp_path / "bad.xlsx")


@pytest.mark.skipif(not DEV_PATH.exists(), reason="dev split not present")
def test_dev_ingest_matches_task06_b1(tmp_path):
    """S2 completion: 953 rows read, copies not merged, ID relations as in task 06 B1."""
    from freight_lineitems.records import load_dev
    recs = load_dev()
    con = db.connect(tmp_path / "dev.sqlite")
    assert db.ingest_only(con, recs, "dev") == 953
    one = lambda q: con.execute(q).fetchone()[0]  # noqa: E731
    assert one("SELECT COUNT(*) FROM dispute") == 953
    assert one("SELECT COUNT(*) FROM shipment") == 813
    assert one("SELECT COUNT(*) FROM carrier_invoice") == 813
    assert one("SELECT COUNT(DISTINCT shipment_gid) FROM carrier_invoice") == 813      # one invoice per shipment
    assert one("SELECT COUNT(*) FROM bill_record") == one("SELECT COUNT(DISTINCT invoice_bill_id) FROM bill_record")
    per_inv = {r[0] for r in con.execute("SELECT COUNT(*) FROM bill_record GROUP BY carrier_invoice_id")}
    assert per_inv <= {1, 2, 8}


def test_fact_export_excludes_flagged_records_even_if_consistent(tmp_path):
    """Audit H2: a passed record that still needs a reviewer (e.g. a copy without its own PK) must not reach downstream."""
    a, b = record("LIFTGATE $15.00", "15", rid="dev#r1"), record("LIFTGATE $15.00", "15", rid="dev#r2", pk="P2")
    b.row_number = 2
    res = [_result(a, "PASSED_CHECKS", "MATCH_FIRST"), _result(b, "PASSED_CHECKS", "MATCH_FIRST")]
    res[0]["judgment"] = {"flags": [], "recommendation": "PASSED_CHECKS", "decisive_flags": [], "diagnostics": []}
    b.text_raw = "LIFTGATE $15.00 AGAIN"
    res[1]["judgment"] = {"flags": [{"code": "SHIP.COPY.SAME_OR_NO_PK", "severity": "attention", "origin": "CODE_RULE", "paths": [],
                                     "evidence": [{}], "points_to": None}],
                          "recommendation": "HUMAN_REVIEW", "decisive_flags": ["SHIP.COPY.SAME_OR_NO_PK"], "diagnostics": []}
    con = db.connect(tmp_path / "t.sqlite")
    db.write_run(con, "run1", "test", [a, b], res, {"model": "m"}, RULES)
    assert [f["dispute_id"] for f in db.export_facts(con, "run1")] == ["dev#r1"]


def test_per_record_rows_never_silently_dropped(tmp_path):
    """Audit L8: writing the same run twice must fail loudly, not ignore rows."""
    import sqlite3
    a = record("LIFTGATE $15.00", "15", rid="dev#r1")
    res = [_result(a, "PASSED_CHECKS", "MATCH_FIRST")]
    con = db.connect(tmp_path / "t.sqlite")
    db.write_run(con, "run1", "test", [a], res, {"model": "m"}, RULES)
    with pytest.raises(sqlite3.IntegrityError):
        db.write_run(con, "run1", "test", [a], res, {"model": "m"}, RULES)
