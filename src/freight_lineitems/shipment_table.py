"""The shipment table in the client's format (task 20 section 2.2; the layout of the client's two worked examples).

Input: shipment results of `rollup.rollup` with the client names added (`charge_map.annotate`). Output, per shipment,
one group: the original amount; every line (client name, internal code, amount, status, replaced by), tax on its own
line; the default new total; the change from the original amount; the total under each other reading; the stated
amount due; the gap; the reminders (flags); the recommendation. Pure code: it formats, it decides nothing, and it
never says whether a charge should be paid. Field meanings: docs/shipment_output_contract.md.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

CSV_COLUMNS = ["shipment_key", "sap_bol", "row", "label", "internal_code", "amount", "status", "replaced_by",
               "explanation", "note"]
ROW_ORIGINAL, ROW_LINE, ROW_TAX = "ORIGINAL_AMOUNT", "LINE", "TAX"
ROW_NEW_TOTAL, ROW_CHANGE, ROW_OTHER = "NEW_TOTAL", "CHANGE_FROM_ORIGINAL", "OTHER_READING_TOTAL"
ROW_STATED, ROW_GAP, ROW_REMINDERS, ROW_REC = "STATED_AMOUNT_DUE", "GAP", "REMINDERS", "RECOMMENDATION"


def _code(ln: dict) -> str:
    return "+".join(ln["codes"]) or "(no charge named)"


def shipment_json(sh: dict) -> dict:
    """One shipment in the client's format, as a JSON-ready dict."""
    return {
        "schema_version": sh.get("schema_version"),
        "shipment_key": sh["shipment_key"], "sap_bol": sh.get("sap_bol"),
        "original_amount": sh["original_amount"],
        "lines": [{"client_name": ln.get("client_name") or "", "internal_code": _code(ln), "amount": ln["amount"],
                   "is_tax": ln["is_tax"], "status": ln["status"], "replaced_by": ln["replaced_by"],
                   "explanation": ln["explanation"], "label_in_text": ln["label"], "added_by_code": ln["added_by_code"]}
                  for ln in sh["lines"]],
        "new_total": sh["new_total"], "change_from_original": sh["default_change"],
        "other_reading_totals": [{"flag": o["flag"], "event": o["event"], "new_total": o["new_total"],
                                  "change_from_original": o["change"]} for o in sh["other_readings"]],
        "items_total": sh.get("items_total"),
        "stated_amount_due": sh.get("stated_amount_due"), "gap": sh.get("gap"), "gap_note": sh.get("gap_note"),
        "per_explanation_gap": [{"explanation": e["expl_id"], "items_total": e.get("items_total"),
                                 "stated_amount_due": e.get("stated_amount_due"), "gap": e.get("gap")}
                                for e in sh["explanations"]],
        "reminders": [{"code": f["code"], "severity": f["severity"]} for f in sh["flags"]],
        "recommendation": sh["recommendation"],
        "prior_history": (sh.get("prior_history") or {}).get("status"),
        "relation_undecided": sh.get("relation_undecided"),
        "complete": sh["complete"],
    }


def table_rows(sh: dict) -> list[dict]:
    """The CSV rows of one shipment's group, in the client's order: original amount, the lines (tax rows marked TAX),
    new total, change, other readings, stated amount due, gap, reminders, recommendation."""
    base = {"shipment_key": sh["shipment_key"], "sap_bol": sh.get("sap_bol") or ""}

    def row(kind: str, label: str = "", amount=None, **kw) -> dict:
        r = {c: "" for c in CSV_COLUMNS} | base | {"row": kind, "label": label}
        r["amount"] = "" if amount is None else amount
        return r | {k: ("" if v is None else v) for k, v in kw.items()}

    rows = [row(ROW_ORIGINAL, "Original Amount", sh["original_amount"])]
    for ln in sh["lines"]:
        rows.append(row(ROW_TAX if ln["is_tax"] else ROW_LINE, ln.get("client_name") or "", ln["amount"],
                        internal_code=_code(ln), status=ln["status"], replaced_by=ln["replaced_by"],
                        explanation=ln["explanation"], note="added by code (BALANCE DUE)" if ln["added_by_code"] else ""))
    rows.append(row(ROW_NEW_TOTAL, "New Disputed Total", sh["new_total"]))
    rows.append(row(ROW_CHANGE, "Delta from Original Amount", sh["default_change"]))
    for o in sh["other_readings"]:
        rows.append(row(ROW_OTHER, "Other reading total", o["new_total"], note=f"{o['flag']} {o['event']}; change {o['change']}"))
    rows.append(row(ROW_STATED, "Stated amount due", sh.get("stated_amount_due"), note=sh.get("gap_note")))
    rows.append(row(ROW_GAP, "Gap (stated amount due - line total)", sh.get("gap")))
    rows.append(row(ROW_REMINDERS, "Reminders", None, note="; ".join(f"{f['code']} ({f['severity']})" for f in sh["flags"])))
    rows.append(row(ROW_REC, "Recommendation", None, note=sh["recommendation"]))
    return rows


def to_csv(shipments: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    for sh in shipments:
        w.writerows(table_rows(sh))
    return buf.getvalue()


def write(shipments: list[dict], out_dir: Path) -> None:
    """Write shipment_table.csv and shipment_table.json into out_dir."""
    (out_dir / "shipment_table.csv").write_text(to_csv(shipments))
    (out_dir / "shipment_table.json").write_text(json.dumps([shipment_json(s) for s in shipments], indent=1,
                                                            ensure_ascii=False))
