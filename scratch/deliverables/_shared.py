"""Shared helpers for the status-board deliverables (task 03).

Imports the prototype in scratch/prototype/ read-only (nothing there is modified) and runs the code-only part
of the pipeline on the dev split. Never reads data/processed/test.csv or the raw Excel. No LLM calls.

Tracked outputs (docs/deliverables/<card>/results/) get aggregates and a few screened examples only.
Row-level outputs go to the git-ignored data/interim/deliverables/<card>/.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / "scratch" / "prototype"
sys.path.insert(0, str(PROTO))

DEV_CSV = ROOT / "data" / "processed" / "dev.csv"
DOCS_DELIV = ROOT / "docs" / "deliverables"
ROWLEVEL = ROOT / "data" / "interim" / "deliverables"

# Columns whose values must never appear in a tracked file.
ID_COLS = ["SHIPMENT_GID", "PK", "Invoice/Bill ID", "SAP BOL", "Shipment Number", "Carrier Invoice", "Carrier",
           "Source Address", "Destination Address"]
PLACEHOLDER = re.compile(r"\[(PERSON|EMAIL)_\d+\]")


def results_dir(folder: str) -> Path:
    p = DOCS_DELIV / folder / "results"
    p.mkdir(parents=True, exist_ok=True)
    return p


def rowlevel_dir(card: str) -> Path:
    p = ROWLEVEL / card
    p.mkdir(parents=True, exist_ok=True)
    return p


_BLACKLIST: set[str] | None = None


def _blacklist() -> set[str]:
    global _BLACKLIST
    if _BLACKLIST is None:
        import pandas as pd
        df = pd.read_csv(DEV_CSV, dtype=str, usecols=ID_COLS)
        vals: set[str] = set()
        for c in ID_COLS:
            for v in df[c].dropna():
                v = v.strip().upper()
                if len(v) >= 4:
                    vals.add(v)
                    if v.startswith("PPGTM."):
                        vals.add(v[len("PPGTM."):])
        _BLACKLIST = vals
    return _BLACKLIST


def unify_placeholders(text: str) -> str:
    """[PERSON_1] -> [PERSON], [EMAIL_2] -> [EMAIL] (report convention)."""
    return PLACEHOLDER.sub(lambda m: f"[{m.group(1)}]", text)


def safe_for_docs(text: str) -> bool:
    """True when a redacted text may go into a tracked file: no long digit runs (shipment, invoice, PK numbers),
    no value from an ID / carrier / address column, no '@'."""
    t = text.upper()
    if "@" in t or re.search(r"\d{6,}", t):
        return False
    words = set(re.findall(r"[A-Z0-9][A-Z0-9._-]{3,}", t))
    bl = _blacklist()
    return not (words & bl) and not any(v in t for v in bl if len(v) >= 8)


def run_code_only():
    """Steps 0-2, auto-reject pre-check, 5.5 (pre-check mode) and 6 on all 908 dev events, without step 3.
    Same loop as scratch/prototype/run_dev.py, without writing to its output folder."""
    from gate import collapse, load_rows
    from history import HistEntry
    from pipeline import process

    rows = load_rows()
    ev = collapse(rows).sort_values(["SHIPMENT_GID", "ts", "Invoice Amount"]).reset_index(drop=True)
    records = []
    by_ship: dict[str, list] = defaultdict(list)
    for _, r in ev.iterrows():
        rec, _ = process(r, list(by_ship[r.SHIPMENT_GID]))
        records.append(rec)
        by_ship[r.SHIPMENT_GID].append(HistEntry(rec.source.record_id, r.ts, rec.source.delta, rec.text.redacted))
    return rows, ev, records


def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"
