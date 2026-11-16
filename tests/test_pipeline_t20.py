"""Task 20: the shipment roll-up inside the main flow (pipeline.finish_batch), the outputs it writes, the run record,
the schema versions, the reviewer-feedback export and the offline run on the tracked synthetic batch. No model call,
no real data."""

from __future__ import annotations

import csv
import inspect
import io
import json
import sqlite3
from pathlib import Path

from freight_lineitems import db, pipeline, review_ui, rollup
from freight_lineitems.offline import run_offline
from freight_lineitems.records import load_csv

from rollup_helpers import C, DAY1, DAY2, expl

FIX = Path(__file__).parent / "fixtures" / "smoke"


def test_run_batch_and_the_offline_run_use_finish_batch_and_write_outputs():
    """One path for production and evaluation: run_batch calls finish_batch and write_outputs (task 20 section 2.1)."""
    src = inspect.getsource(pipeline.run_batch)
    assert "finish_batch(records, results)" in src and "write_outputs(" in src
    assert "rollup_results" not in src and "duplicates.apply" not in src


def test_finish_batch_rolls_up_and_adds_client_names():
    from helpers import record
    spec = [("LIFTGATE $75.00", "a", 1, DAY1, [C("#1", ["ACCESSORIAL.LIFTGATE"], "LIFTGATE")]),
            ("DETENTION $50.00", "b", 2, DAY2, [C("#1", ["DETENTION_STORAGE.DRIVER_DETENTION"], "DETENTION")])]
    recs, results = [], []
    for text, rid, row, day, items in spec:
        rec = record(text, "0", rid=rid)
        rec.row_number, rec.event_date = row, day
        recs.append(rec)
        results.append(expl(text, items, row, day, rid=rid))
    results, ships = pipeline.finish_batch(recs, results)
    assert len(ships) == 1 and ships[0]["default_change"] == "125.00"
    assert all(ln.get("client_name") for ln in ships[0]["lines"])
    assert ships[0]["schema_version"] == rollup.SHIPMENT_SCHEMA_VERSION
    assert all(r["facts"]["source_rows"] for r in results)


def test_offline_run_on_the_tracked_synthetic_batch(tmp_path):
    records = load_csv(FIX / "batch.csv", prefix="smoke")
    readings = {f"smoke#r{k}": v for k, v in json.loads((FIX / "readings.json").read_text()).items()}
    run_id, results, ships, out = run_offline(records, readings, "smoke", tmp_path)
    assert {p.name for p in out.iterdir()} >= {"records.jsonl", "shipments.jsonl", "shipment_table.csv", "shipment_table.json",
                                               "run.sqlite", "export_facts.json", "export_review.json", "run_info.json"}
    assert len(records) == 7 and len(results) == 6 and len(ships) == 5
    assert all(r["schema_version"] == pipeline.READING_SCHEMA_VERSION for r in results)
    by = {s["shipment_key"]: s for s in ships}
    assert by["SYN-SHIP-A"]["default_change"] == "300.00" and by["SYN-SHIP-A"]["gap_note"] == "MULTI_EXPLANATION_NO_SHIPMENT_GAP"
    assert by["SYN-SHIP-B"]["n_orders"] == 2 and by["SYN-SHIP-B"]["gap"] == "0.00"
    assert by["SYN-SHIP-E"]["new_total"] == "558.22" and by["SYN-SHIP-E"]["gap"] == "0.00"
    assert all(s["prior_history"]["status"] == "NOT_PROVIDED" for s in ships)
    con = sqlite3.connect(out / "run.sqlite")
    assert con.execute("SELECT COUNT(*) FROM shipment_result").fetchone()[0] == 5
    assert con.execute("SELECT COUNT(*) FROM shipment_line").fetchone()[0] == sum(len(s["lines"]) for s in ships)
    assert con.execute("SELECT gap FROM shipment_result WHERE shipment_gid = 'SYN-SHIP-E'").fetchone()[0] == "0.00"
    info = json.loads((out / "run_info.json").read_text())
    rows = list(csv.DictReader(io.StringIO((out / "shipment_table.csv").read_text())))
    assert {r["row"] for r in rows} >= {"ORIGINAL_AMOUNT", "LINE", "TAX", "NEW_TOTAL", "CHANGE_FROM_ORIGINAL", "GAP", "RECOMMENDATION"}
    assert info["run_record"]["screening_enabled"] is False


def test_run_record_has_everything_a_run_needs():
    rr = pipeline.run_record({"model": "m"})
    for k in ("git_commit", "git_dirty", "redaction_engine", "skill_layout", "skill_sha", "skill_folder_sha", "rules",
              "taxonomy", "examples_sha", "model", "reading_schema_version", "shipment_schema_version", "screening_enabled"):
        assert k in rr and rr[k] not in (None, ""), k


def test_reviewer_decisions_export_as_csv(tmp_path):
    con = db.connect(tmp_path / "r.sqlite")
    review_ui.ensure_decision_table(con)
    con.execute("INSERT INTO reviewer_decision (decision_id, dispute_id, action, reviewer_id, decided_at) VALUES "
                "('d1', 'syn#r1', 'ACCEPT_READING', 'rev-1', '2026-11-15T10:00:00Z')")
    text = db.export_reviewer_decisions(con, tmp_path / "decisions.csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert list(rows[0]) == db._cols("reviewer_decision") and rows[0]["action"] == "ACCEPT_READING"
    assert (tmp_path / "decisions.csv").read_text() == text
