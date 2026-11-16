"""CSV exports of a run, for people who work in Excel (TP1 deliverable "Structured output": array, CSV or Excel table).

Two flat files are written next to the JSON exports of the same run. They carry exactly the same content as the JSON
exports (`db.export_facts` and `db.export_review`); nothing is recomputed here, so the CSV can never disagree with them.

- `export_facts.csv`: downstream table, one row per line item. Only disputes whose reading passed the mandatory checks
  and has the recommendation PASSED_CHECKS (the same filter as `export_facts.json`).
  `signed_amount` is the amount with a minus sign for credits, so a column sum in Excel is the claimed total.
  A tax named without an amount has an empty amount (it is a line item with no number in the text).
- `export_review.csv`: reviewer table, one row per dispute (every dispute, whatever its recommendation), with the number
  of flags per severity and the flag codes.

Safety: carrier text is untrusted. A text cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return would be
run as a formula by Excel, so such cells get a leading apostrophe. The numeric columns are written as they are.
The files are UTF-8 with a byte order mark so that Excel opens them correctly.
"""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from freight_lineitems.config import category

FACTS_COLUMNS = ["dispute_id", "shipment_gid", "carrier_invoice_id", "currency", "currency_basis",
                 "line_item_id", "amount", "is_credit", "signed_amount", "charge_code", "charge_category",
                 "combined_group", "raw_charge_label", "carrier_stated_basis_type"]
REVIEW_COLUMNS = ["dispute_id", "carrier_invoice_id", "recommendation", "parse_status",
                  "n_attention", "n_return", "n_info", "flag_codes", "text_redacted"]
NUMERIC = {"amount", "signed_amount", "is_credit", "n_attention", "n_return", "n_info"}
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_text(value) -> str:
    """Text cell as a string, neutralised so that a spreadsheet never runs it as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_STARTS) else text


def _signed(amount, is_credit) -> str:
    """Amount with the sign of its role (credit = negative); empty when the line item has no amount."""
    if amount in (None, ""):
        return ""
    try:
        value = Decimal(str(amount))
    except InvalidOperation:
        return ""
    return str(-abs(value) if is_credit else abs(value))


def facts_rows(facts: list[dict]) -> list[dict]:
    """One row per line item of `db.export_facts` output."""
    rows = []
    for d in facts:
        for it in d["line_items"]:
            credit = bool(it["is_credit"])
            rows.append({
                "dispute_id": d["dispute_id"], "shipment_gid": d["shipment_gid"], "carrier_invoice_id": d["carrier_invoice_id"],
                "currency": d["currency"], "currency_basis": d["currency_basis"],
                "line_item_id": it["line_item_id"], "amount": "" if it["amount"] is None else str(it["amount"]),
                "is_credit": int(credit), "signed_amount": _signed(it["amount"], credit),
                "charge_code": it["charge_code"], "charge_category": category(it["charge_code"]) if it["charge_code"] else "",
                "combined_group": it["combined_group"], "raw_charge_label": it["raw_charge_label"],
                "carrier_stated_basis_type": it["carrier_stated_basis_type"]})
    return rows


def review_rows(review: list[dict]) -> list[dict]:
    """One row per dispute of `db.export_review` output."""
    rows = []
    for d in review:
        sev = [str(f["severity"]).upper() for f in d["flags"]]
        rows.append({
            "dispute_id": d["dispute_id"], "carrier_invoice_id": d["carrier_invoice_id"], "recommendation": d["recommendation"],
            "parse_status": d["parse_status"],
            "n_attention": sev.count("ATTENTION"), "n_return": sev.count("RETURN"), "n_info": sev.count("INFO"),
            "flag_codes": ";".join(f["code"] for f in d["flags"]), "text_redacted": d["text_redacted"]})
    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> Path:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for r in rows:
            w.writerow([r[c] if c in NUMERIC else safe_text(r[c]) for c in columns])
    return path


def write_run_csvs(out_dir: Path, facts: list[dict], review: list[dict]) -> list[Path]:
    """Write `export_facts.csv` and `export_review.csv` into `out_dir` from the two JSON-export structures."""
    out_dir = Path(out_dir)
    return [write_csv(out_dir / "export_facts.csv", FACTS_COLUMNS, facts_rows(facts)),
            write_csv(out_dir / "export_review.csv", REVIEW_COLUMNS, review_rows(review))]
