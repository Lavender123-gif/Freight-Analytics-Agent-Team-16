"""CSV exports: same content as the JSON exports, credits signed, formulas neutralised, readable by csv and Excel.

Synthetic structures only; no model call and no data files."""

import csv
from decimal import Decimal

from freight_lineitems import export_csv

FACTS = [
    {"dispute_id": "x#1", "shipment_gid": "S1", "carrier_invoice_id": "C|I1", "currency": "CAD",
     "currency_basis": "DERIVED_FROM_COUNTRY",
     "line_items": [
         {"line_item_id": "r:x#1:1:0", "amount": "85.00", "is_credit": 0, "charge_code": "ACCESSORIAL.INSIDE_DELIVERY",
          "combined_group": None, "raw_charge_label": "INSIDE DELIVERY", "carrier_stated_basis_type": "NONE"},
         {"line_item_id": "r:x#1:1:1", "amount": "20.00", "is_credit": 1, "charge_code": "FUEL.SURCHARGE",
          "combined_group": None, "raw_charge_label": "=HYPERLINK(\"http://x\")", "carrier_stated_basis_type": "NONE"},
         {"line_item_id": "r:x#1:1:2", "amount": None, "is_credit": 0, "charge_code": "TAX.HST",
          "combined_group": None, "raw_charge_label": "HST", "carrier_stated_basis_type": "NONE"}]},
    {"dispute_id": "x#2", "shipment_gid": "S2", "carrier_invoice_id": "C|I2", "currency": "USD",
     "currency_basis": "DERIVED_FROM_COUNTRY", "line_items": []},
]
REVIEW = [
    {"dispute_id": "x#1", "carrier_invoice_id": "C|I1", "text_redacted": "-$20.00 CREDIT, ÄÖ", "parse_status": "PASSED_CHECKS",
     "recommendation": "HUMAN_REVIEW",
     "flags": [{"code": "ITEM.TAX.PRESENT", "severity": "attention", "points_to": None},
               {"code": "ITEM.CODE.PENDING_MEANING", "severity": "info", "points_to": None},
               {"code": "DUP.ROW.COPY", "severity": "ATTENTION", "points_to": "x#0"}]},
    {"dispute_id": "x#2", "carrier_invoice_id": "C|I2", "text_redacted": "", "parse_status": "PASSED_CHECKS",
     "recommendation": "PASSED_CHECKS", "flags": []},
]


def _read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_facts_csv_has_one_row_per_line_item_with_signed_amounts(tmp_path):
    export_csv.write_run_csvs(tmp_path, FACTS, REVIEW)
    rows = _read(tmp_path / "export_facts.csv")
    assert [r["line_item_id"] for r in rows] == ["r:x#1:1:0", "r:x#1:1:1", "r:x#1:1:2"]      # a dispute with no items adds no row
    assert [r["signed_amount"] for r in rows] == ["85.00", "-20.00", ""]
    assert sum(Decimal(r["signed_amount"]) for r in rows if r["signed_amount"]) == Decimal("65.00")
    assert rows[2]["amount"] == "" and rows[2]["charge_category"] == "TAX"                  # tax named without an amount
    assert rows[0]["charge_category"] == "ACCESSORIAL" and rows[1]["is_credit"] == "1"


def test_csv_does_not_let_carrier_text_run_as_a_formula(tmp_path):
    export_csv.write_run_csvs(tmp_path, FACTS, REVIEW)
    assert _read(tmp_path / "export_facts.csv")[1]["raw_charge_label"] == "'=HYPERLINK(\"http://x\")"
    assert _read(tmp_path / "export_review.csv")[0]["text_redacted"].startswith("'-$20.00")
    assert _read(tmp_path / "export_facts.csv")[1]["signed_amount"] == "-20.00"            # numeric column is not prefixed


def test_review_csv_counts_flags_by_severity_and_keeps_every_dispute(tmp_path):
    export_csv.write_run_csvs(tmp_path, FACTS, REVIEW)
    rows = _read(tmp_path / "export_review.csv")
    assert len(rows) == 2
    assert (rows[0]["n_attention"], rows[0]["n_return"], rows[0]["n_info"]) == ("2", "0", "1")
    assert rows[0]["flag_codes"] == "ITEM.TAX.PRESENT;ITEM.CODE.PENDING_MEANING;DUP.ROW.COPY"
    assert rows[1]["flag_codes"] == "" and rows[1]["recommendation"] == "PASSED_CHECKS"


def test_files_open_in_excel_with_a_byte_order_mark_and_non_ascii_text_survives(tmp_path):
    export_csv.write_run_csvs(tmp_path, FACTS, REVIEW)
    assert (tmp_path / "export_review.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert "ÄÖ" in _read(tmp_path / "export_review.csv")[0]["text_redacted"]


def test_csv_matches_the_json_exports_of_a_real_run(tmp_path):
    """The offline demo goes through the real pipeline, which writes the JSON and the CSV exports; the two must agree."""
    import importlib.util
    import json
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("demo", Path(__file__).parents[1] / "scratch" / "demo" / "build_offline_demo.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    demo.main(["--runs-dir", str(tmp_path)])
    run = tmp_path / demo.RUN_ID
    facts = json.loads((run / "export_facts.json").read_text())
    review = json.loads((run / "export_review.json").read_text())
    assert len(_read(run / "export_facts.csv")) == sum(len(d["line_items"]) for d in facts) > 0
    assert len(_read(run / "export_review.csv")) == len(review) > 0
    assert {r["dispute_id"] for r in _read(run / "export_facts.csv")} == {d["dispute_id"] for d in facts}
    assert (run / "export_review.csv").read_bytes().startswith(b"\xef\xbb\xbf")
