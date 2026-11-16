"""T14-06 (T12-05): replay the shipment roll-up on a stored run, without any model call.

Reads data/interim/runs/<run>/records.jsonl. Works on both kinds of stored run:
- an old row-level run (before task 14: one result per source row, rules v1.1 diagnostics): rows are merged into
  explanations here (the lowest row's reading represents the explanation), the withdrawn flags (Delta, currency,
  DUP.*) are dropped, and every recommendation is recomputed under the current rules.yaml;
- a new run (one result per explanation, rules v1.2): used as stored.
Then every shipment is rolled up (src/freight_lineitems/rollup.py) and the charge-code mapping adds the client's
names (src/freight_lineitems/charge_map.py).

Prints counts only. Row-level output (the client-format tables) goes to data/interim/rollup/<run>/ (git-ignored):
shipments.jsonl, jake_format.csv, jake_format.md, summary.json.
Run: uv run python scratch/rollup/replay.py --run devFull-4823
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from decimal import Decimal

from freight_lineitems import duplicates
from freight_lineitems.config import ROOT, RULES, RUNS_DIR
from freight_lineitems.disposition import flags_from, recommend
from freight_lineitems.records import group_explanations, load_dev
from freight_lineitems.pipeline import shipments_of as rollup_results  # task 20: one shipment path
from freight_lineitems.schemas import Diagnostic

OUT_ROOT = ROOT / "data" / "interim" / "rollup"
WITHDRAWN = ("CLAIM.DELTA.", "REC.FIELD.DELTA_", "REC.FIELD.CURRENCY_UNDETERMINED", "DUP.ROW.", "DUP.INVOICE.")


def find_run(name: str) -> str:
    hits = sorted(p.name for p in RUNS_DIR.iterdir() if p.is_dir() and (p.name == name or p.name.endswith(name)))
    if len(hits) != 1:
        sys.exit(f"run {name!r}: {len(hits)} matches {hits[:5]}")
    return hits[0]


def recolour(res: dict) -> dict:
    """Current rules on stored diagnostics, withdrawn codes dropped. Returns a copy of the judgment."""
    diags = [Diagnostic(**d) for d in res["judgment"]["diagnostics"] if not d["code"].startswith(WITHDRAWN)]
    flags = flags_from(diags)
    return {"flags": flags, **recommend(flags), "diagnostics": [d.model_dump() for d in diags]}


# severities of rules v1.1 for the codes v1.2 changed or retired, to show the colour steps one at a time
V11 = {"DUP.ROW.HAS_LATER_COPIES": "info", "DUP.ROW.COPY": "attention", "DUP.INVOICE.SAME_CHARGE": "attention",
       "DUP.INVOICE.NOT_CHECKED": "info", "REC.FIELD.CURRENCY_UNDETERMINED": "info", "ITEM.TAX.PRESENT": "attention", "ITEM.TAX.NO_AMOUNT": "info"}
DELTA = ("CLAIM.DELTA.", "REC.FIELD.DELTA_")


def row_colour(res: dict, drop: tuple, tax_v11: bool) -> str:
    """Row-level colour with the given codes dropped; DUP.* keep their v1.1 severity (they are not in v1.2),
    tax flags keep v1.1 when tax_v11."""
    keep = {k: v for k, v in V11.items() if tax_v11 or not k.startswith("ITEM.TAX")}
    diags = [Diagnostic(**d) for d in res["judgment"]["diagnostics"] if not d["code"].startswith(drop)]
    fl = flags_from(diags)
    for f in fl:
        if f["code"] in keep and not f.get("subsumed_by"):
            f["severity"] = keep[f["code"]]
    return recommend(fl)["recommendation"]


def explanations_from_rows(results: list[dict], records_by_id: dict) -> list[dict]:
    """Old row-level run -> one result per explanation (representative = lowest row), with copy flags."""
    recs = [records_by_id[r["record_id"]] for r in results]
    by_id = {r["record_id"]: r for r in results}
    out = []
    for g in group_explanations(recs):
        rep = json.loads(json.dumps(by_id[g[0].record_id]))
        rep["judgment"] = recolour(rep)
        rep["facts"] |= duplicates.source_rows(g)
        cd = duplicates.copy_diagnostics(g)
        if cd:
            diags = [Diagnostic(**d) for d in rep["judgment"]["diagnostics"]] + cd
            fl = flags_from(diags)
            rep["judgment"] = {"flags": fl, **recommend(fl), "diagnostics": [d.model_dump() for d in diags]}
        out.append(rep)
    return out


def excel_baselines(ships: list[dict], expl: list[dict]) -> dict:
    """How many shipments' default change equals each Excel baseline (C8): (1) Delta summed over the distinct
    explanations, (2) Invoice Dups Removed summed over the shipment's rows minus Shipment Amount. Needs the source
    rows (dev split); evaluation only, nothing here feeds back into the roll-up."""
    try:
        rows = {r.record_id: r for r in load_dev()}
    except (FileNotFoundError, OSError):
        return {"available": False}
    by_ship: dict[str, list[dict]] = {}
    for e in expl:
        by_ship.setdefault(e["facts"]["source"]["shipment_key"], []).append(e)
    c = Counter()
    for sh in ships:
        es = by_ship[sh["shipment_key"]]
        if any(e["record_id"] not in rows for e in es):
            c["not_in_dev_split"] += 1
            continue
        b1 = sum((rows[e["record_id"]].delta or Decimal(0)) for e in es)
        all_rows = [rows[x["record_id"]] for e in es for x in e["facts"].get("source_rows", [])]
        idr = sum((r.invoice_dups_removed or Decimal(0)) for r in all_rows)
        b2 = idr - Decimal(sh["original_amount"]) if idr else None
        d = Decimal(sh["default_change"])
        multi = "multi" if len(es) > 1 else "single"
        c["shipments"] += 1
        c[f"{multi}_shipments"] += 1
        c["equal_delta_sum"] += abs(d - b1) <= Decimal("0.005")
        c[f"{multi}_equal_delta_sum"] += abs(d - b1) <= Decimal("0.005")
        c["equal_dups_removed"] += b2 is not None and abs(d - b2) <= Decimal("0.005")
        c[f"{multi}_equal_dups_removed"] += b2 is not None and abs(d - b2) <= Decimal("0.005")
        c["dups_removed_all_zero"] += b2 is None
        c["equal_both"] += abs(d - b1) <= Decimal("0.005") and b2 is not None and abs(d - b2) <= Decimal("0.005")
    return {"available": True, **dict(c)}


def table_rows(sh: dict) -> list[dict]:
    """The client's table for one shipment, one dict per row (superseded lines kept, marked)."""
    rows = [{"shipment": sh["shipment_key"], "sap_bol": sh.get("sap_bol"), "row": "Original Amount", "amount": sh["original_amount"]}]
    for ln in sh["lines"]:
        rows.append({"shipment": sh["shipment_key"], "sap_bol": sh.get("sap_bol"), "row": ln.get("client_name") or "",
                     "amount": ln["amount"], "status": ln["status"], "internal_code": "+".join(ln["codes"]) or "(no charge name)",
                     "edi_candidates": ln.get("edi_candidates", ""), "reference_names": ln.get("reference_names", ""),
                     "label_in_text": ln["label"], "explanation": ln["explanation"], "is_tax": ln["is_tax"]})
    rows.append({"shipment": sh["shipment_key"], "sap_bol": sh.get("sap_bol"), "row": "New Disputed Total", "amount": sh["new_total"]})
    rows.append({"shipment": sh["shipment_key"], "sap_bol": sh.get("sap_bol"), "row": "Delta from Original Amount", "amount": sh["default_change"]})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="devFull-4823")
    a = ap.parse_args()
    run = find_run(a.run)
    stored = [json.loads(x) for x in (RUNS_DIR / run / "records.jsonl").open()]
    old_style = any(d["code"].startswith(WITHDRAWN) for r in stored for d in r["judgment"]["diagnostics"]) or \
        not any("source_rows" in r["facts"] for r in stored)
    colours: dict[str, Counter] = {}
    if old_style:
        colours["rows_stored_rules"] = Counter(r["judgment"]["recommendation"] for r in stored)
        colours["rows_C1_delta_withdrawn"] = Counter(row_colour(r, DELTA, True) for r in stored)
        colours["rows_C1_C6"] = Counter(row_colour(r, DELTA + ("REC.FIELD.CURRENCY_UNDETERMINED",), False) for r in stored)
        colours["rows_rules_v12_copies_not_merged"] = Counter(recolour(r)["recommendation"] for r in stored)
        recs = {r.record_id: r for r in load_dev()} if stored[0]["facts"]["source"]["source"] == "dev" else None
        if recs is None:
            sys.exit("old-style replay needs the source rows; only dev runs are supported")
        expl = explanations_from_rows(stored, recs)
    else:
        expl = stored
    colours["explanations"] = Counter(r["judgment"]["recommendation"] for r in expl)
    from freight_lineitems import charge_map
    ships = rollup_results(expl)
    for sh in ships:
        charge_map.annotate(sh)
    colours["shipments"] = Counter(s["recommendation"] for s in ships)
    baseline = excel_baselines(ships, expl)
    n_default = sum(1 for s in ships if s["new_total"] is not None)
    flags = Counter(f["code"] for s in ships for f in s["flags"])
    expl_flags = Counter(f["code"] for r in expl for f in r["judgment"]["flags"])
    out_dir = OUT_ROOT / run
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "shipments.jsonl").open("w") as f:
        for s in ships:
            f.write(json.dumps(s, default=str) + "\n")
    rows = [r for s in ships for r in table_rows(s)]
    cols = ["shipment", "sap_bol", "row", "amount", "status", "internal_code", "edi_candidates", "reference_names",
            "label_in_text", "explanation", "is_tax"]
    with (out_dir / "jake_format.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    md = []
    for s in ships:
        md.append(f"### {s.get('sap_bol') or s['shipment_key']}  ({s['recommendation']}, orders {s['n_orders']})\n")
        md.append("| | | status | internal code | EDI candidates |\n|---|---|---|---|---|")
        for r in table_rows(s):
            md.append(f"| {r['row']} | {r['amount']} | {r.get('status', '')} | {r.get('internal_code', '')} | {r.get('edi_candidates', '')} |")
        if s["other_readings"]:
            md.append("\nOther readings: " + "; ".join(f"{o['flag'].split('.')[-1]} -> {o['new_total']}" for o in s["other_readings"]))
        if s["flags"]:
            md.append("Flags: " + ", ".join(f["code"] for f in s["flags"]))
        md.append("")
    (out_dir / "jake_format.md").write_text("\n".join(md))
    summary = {"run": run, "old_style_replay": old_style, "rules": RULES["version"], "n_rows": len(stored),
               "n_explanations": len(expl), "n_shipments": len(ships), "n_with_default_total": n_default,
               "n_multi_explanation": sum(1 for s in ships if len(s["explanations"]) > 1),
               "n_incomplete": sum(1 for s in ships if not s["complete"]),
               "colours": {k: dict(v) for k, v in colours.items()}, "excel_baselines": baseline,
               "shipment_flags": dict(flags),
               "explanation_flags": dict(expl_flags)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    if n_default == len(ships):
        print(f"{len(ships)} 票货，每票都有默认总额")
    else:
        print(f"{len(ships)} 票货，{len(ships) - n_default} 票没有默认总额")
        sys.exit(1)


if __name__ == "__main__":
    main()
