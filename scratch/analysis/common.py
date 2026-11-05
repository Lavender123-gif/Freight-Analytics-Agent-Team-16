"""Shared loader and number extraction for the phase-1 problem inventory.

Only reads the dev split. Never reads data/processed/test.csv or the raw Excel.
Run every script from the repo root, e.g. `uv run python scratch/analysis/a1_structure.py`.
"""

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEV_PATH = ROOT / "data" / "processed" / "dev.csv"

MONEY_COLS = ["Invoice Amount", "Invoice Dups Removed", "Shipment Amount", "Delta"]
EPS = 0.005


def load_dev() -> pd.DataFrame:
    df = pd.read_csv(DEV_PATH, dtype=str)
    for c in MONEY_COLS:
        df[c] = df[c].astype(float)
    df["text"] = df["Descritipion"].fillna("")
    df["text_norm"] = df["text"].str.replace(r"\s+", " ", regex=True).str.strip()
    df["carrier"] = df["Carrier"].str.replace("PPGTM.", "", regex=False)
    return df


def redact(s: str) -> str:
    """Mask emails only. Names cannot be masked reliably by regex (they appear
    misspelled), so examples quoted in the report are redacted by hand."""
    return re.sub(r"\S+@\S+", "[EMAIL]", s)


# Spans that look numeric but are not money: dates, times, ranges of dates.
DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"            # 2022-03-14
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b(?!/)"  # 7/23/2021, 06/23/21
    r"|\b\d{1,2}/\d{1,2}(?=\b|/)"        # 05/27, and the malformed 07/18/07/22
)
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?\b")

# A number token: optional $, then either space-grouped thousands (1 684.68),
# plain digits with optional decimals, or a leading-dot decimal (.68).
NUM_RE = re.compile(
    r"(?P<dollar>\$\s?)?"
    r"(?P<num>(?<![\d.])(?:\d{1,3}(?: \d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?![\d]))"
)


def strip_dates_times(s: str) -> str:
    s = DATE_RE.sub(" ", s)
    s = TIME_RE.sub(" ", s)
    return s


def number_tokens(s: str) -> list[dict]:
    """All numeric tokens after removing dates and times.

    Returns dicts with value, raw text, has_dollar, space_thousands, leading_dot.
    This is an analysis helper, not a production parser: it does not decide
    which numbers are money.
    """
    out = []
    for m in NUM_RE.finditer(strip_dates_times(s)):
        raw = m.group("num")
        out.append(
            {
                "raw": raw,
                "value": float(raw.replace(" ", "")),
                "has_dollar": m.group("dollar") is not None,
                "space_thousands": " " in raw,
                "leading_dot": raw.startswith("."),
            }
        )
    return out


# --- Added for task 01b (version pairs) -------------------------------------

EVENT_KEY = ["SHIPMENT_GID", "Event Date", "text_norm", "Invoice Amount", "Delta"]


def load_events() -> pd.DataFrame:
    """Dev split with export repeats collapsed (P1), one row per dispute event."""
    ev = load_dev().drop_duplicates(EVENT_KEY).copy()
    ev["ts"] = pd.to_datetime(ev["Event Date"], format="%Y-%m-%d %H:%M:%S")
    ev["status"] = ev["Dispute Status"].str.replace("PPGTM.PMT_", "", regex=False)
    return ev


# Charge families: an analysis instrument for "did the set of charges change between two versions".
# Built from reading the dev texts; not a pipeline taxonomy and not carrier-specific.
FAMILIES = {
    "purchased_transportation": r"\bPUR?CH?A?R?H?SE?D?\b",
    "tailgate": r"\bTAI\w*G\w*TE\b",
    "inside_delivery": r"\bI?N?SIDE DELIVER",
    "redelivery": r"\bRE ?D[EI]L?I?VE?RY\b|REDILVERY",
    "special_delivery": r"SPECIAL DELV",
    "driver_detention": r"DRIVER DETENTION",
    "equipment_detention": r"EQUIPMENT DETENTION",
    "dwell": r"\bDWELL\b",
    "lumper_sortation": r"LUMPER|SORTATION",
    "hazmat": r"HAZMAT|\bHAMAT\b",
    "storage": r"STORAGE",
    "perdiem_origin": r"ORI?GIN PER ?DIEM",
    "perdiem_destination": r"DESTINATION PER ?DIEM",
    "fuel": r"\bFSC\b|\bFUEL\b|\bFEUL\b",
    "base_rate": r"INCORRECT BASE|BASE COST|MIN FEE|RATED AS|FACTOR|RATE APPROVAL|NOT IN RATE|\bLH\b|LINE ?HAUL",
    "tax": r"\b(?:GST|HST|PST|QST|TAX)\b",
    "reweigh": r"REWEIGH",
    "road_closure": r"ROAD CLOSURE",
    "heat": r"\bHEAT\b",
    "drayage_extras": r"CHASSIS|PORT TERMINATION|CONGESTION|PRE-PULL",
}
FAMILY_RES = {k: re.compile(v) for k, v in FAMILIES.items()}

# Wording about payment state or an outstanding balance.
PAY_RE = re.compile(r"SHORT PAID|\bUNPAID\b|\bPAID\b|STILL OWE|\bOWE\b|OVERPAYMENT|DID NOT PAY|ADJUSTED OFF|AMOUNT APPROVED")
BALANCE_RE = re.compile(r"\bB?ALANCE DUE\b|\bOWE?ING\b")


def families(s: str) -> frozenset[str]:
    return frozenset(k for k, r in FAMILY_RES.items() if r.search(s))


def money_values(s: str) -> list[float]:
    """$-marked numbers; if the text has none, all numbers (texts like '56.56' or 'SHORT PAID 75.27')."""
    toks = number_tokens(s)
    d = [round(t["value"], 2) for t in toks if t["has_dollar"]]
    return d or [round(t["value"], 2) for t in toks]


def adjacent_pairs(ev: pd.DataFrame) -> pd.DataFrame:
    """Consecutive events of the same shipment, ordered by Event Date. Columns suffixed _a (earlier) and _b (later).

    tie=True marks pairs whose two events share the same Event Date (order unknown).
    """
    per = ev.groupby("SHIPMENT_GID").size()
    m = ev[ev.SHIPMENT_GID.isin(per[per > 1].index)].sort_values(["SHIPMENT_GID", "ts", "Invoice Amount"])
    rows = []
    for sid, p in m.groupby("SHIPMENT_GID"):
        p = p.reset_index(drop=True)
        for i in range(1, len(p)):
            a, b = p.iloc[i - 1], p.iloc[i]
            r = {"SHIPMENT_GID": sid, "pos": i, "n_events": len(p), "tie": a.ts == b.ts}
            for c in ["ts", "text_norm", "Delta", "Invoice Amount", "Shipment Amount", "status", "carrier"]:
                r[f"{c}_a"], r[f"{c}_b"] = a[c], b[c]
            rows.append(r)
    return pd.DataFrame(rows)
