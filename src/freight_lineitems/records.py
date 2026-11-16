"""Input records. The source file is never modified; everything derived lives in our own outputs (decision 8).

Each source row is read as its own record; `group_explanations` then merges order copies (same shipment, Event Date
and normalised text) into one explanation, which is read once by the model (task 14 / T12-02; the rows are kept).
Excel/CSV reading is concentrated here (decision 1.3). Only the dev split and the public mock are readable; the test
split is never opened here.

Delta, Invoice Amount and Invoice Dups Removed are read and stored only as the client's Excel baseline for evaluation
(task 14 C2). No runtime step uses them and they are optional columns.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from freight_lineitems.config import DEV_PATH, ROOT, assert_readable

MOCK_DIR = ROOT / "data" / "external" / "mock_public"


@dataclass
class InputRecord:
    record_id: str
    source: str                  # 'dev' | 'mock'
    row_number: int
    shipment_key: str
    carrier: str                 # never sent to the model
    carrier_invoice: str | None
    pk: str | None
    event_date: datetime | None
    text_raw: str
    delta: Decimal | None        # Excel baseline only (task 14 C2); never sent to the model, no runtime step reads it
    invoice_amount: Decimal | None   # Excel baseline only
    shipment_amount: Decimal | None
    origin_state: str | None
    destination_state: str | None
    reason_code: str | None      # never sent to the model
    raw: dict = field(default_factory=dict, repr=False)   # the source row as read, all values as strings
    invoice_dups_removed: Decimal | None = None   # Excel baseline only (task 14 C2)

    @property
    def invoice_key(self) -> str:
        """Carrier invoice scope for invoice-level checks: carrier + carrier invoice number (task 06 C)."""
        return f"{self.carrier}|{self.carrier_invoice or self.shipment_key}"


def _dec(x) -> Decimal | None:
    if x is None or (isinstance(x, float) and x != x) or x == "":
        return None
    return Decimal(str(x)).quantize(Decimal("0.01"))


def _s(x) -> str | None:
    return None if x is None or (isinstance(x, float) and x != x) else str(x)


EXPECTED_COLUMNS = ["SHIPMENT_GID", "PK", "Carrier Invoice", "Descritipion", "Shipment Amount",
                    "Carrier", "Source State", "Destination State", "Event Date", "Reason Code"]
BASELINE_COLUMNS = ["Delta", "Invoice Amount", "Invoice Dups Removed"]   # optional; evaluation only


def _from_frame(df: pd.DataFrame, source: str, prefix: str) -> list[InputRecord]:
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"input is missing columns {missing}")
    out = []
    for i, r in df.iterrows():
        ed = _s(r["Event Date"])
        out.append(InputRecord(
            record_id=f"{prefix}#r{i}", source=source, row_number=int(i), shipment_key=r["SHIPMENT_GID"], carrier=r["Carrier"],
            carrier_invoice=_s(r["Carrier Invoice"]), pk=_s(r["PK"]),
            event_date=datetime.strptime(ed, "%Y-%m-%d %H:%M:%S") if ed else None,
            text_raw=_s(r["Descritipion"]) or "", delta=_dec(r.get("Delta")), invoice_amount=_dec(r.get("Invoice Amount")),
            invoice_dups_removed=_dec(r.get("Invoice Dups Removed")),
            shipment_amount=_dec(r["Shipment Amount"]), origin_state=_s(r["Source State"]),
            destination_state=_s(r["Destination State"]), reason_code=_s(r["Reason Code"]),
            raw={k: _s(v) for k, v in r.items()}))
    return out


def load_dev() -> list[InputRecord]:
    """The dev split (CSV written by data_split.py from the Excel export; same columns)."""
    return _from_frame(pd.read_csv(assert_readable(DEV_PATH), dtype=str), "dev", "dev")


def load_csv(path: Path, prefix: str = "csv") -> list[InputRecord]:
    """A CSV in the AutoPay column layout (EXPECTED_COLUMNS; the baseline columns are optional). Record ids are
    `<prefix>#r<row>` (0-based). Used for synthetic batches and the offline run (task 20)."""
    return _from_frame(pd.read_csv(assert_readable(path), dtype=str), "csv", prefix)


def load_excel(path: Path, sheet: str | int = 0, prefix: str = "xlsx") -> list[InputRecord]:
    """An Excel export in the AutoPay layout. The file is only read, never modified (decision 8).
    Every cell is read as text, so amounts and IDs keep their exact spelling; Delta is re-read as Decimal."""
    df = pd.read_excel(assert_readable(path), sheet_name=sheet, dtype=str)
    return _from_frame(df, "excel", prefix)


def load_mock(path: Path = MOCK_DIR / "mock_records.jsonl") -> list[InputRecord]:
    path = assert_readable(path)
    out = []
    for i, line in enumerate(path.read_text().splitlines()):
        r = json.loads(line)
        out.append(InputRecord(
            record_id=f"mock#{r['row_id']}", source="mock", row_number=i, shipment_key=r["shipment_id"], carrier=r["carrier"],
            carrier_invoice=r.get("carrier_invoice"), pk=r["row_id"],
            event_date=datetime.fromisoformat(r["event_date"].replace("Z", "+00:00")).replace(tzinfo=None),
            text_raw=r["text"] or "", delta=_dec(r.get("delta")), invoice_amount=_dec(r.get("invoice_amount")),
            shipment_amount=_dec(r["shipment_amount"]), origin_state=r.get("origin_state"),
            destination_state=r.get("destination_state"), reason_code=r.get("reason_code"), raw=r))
    return out


def explanation_key(rec: InputRecord) -> tuple:
    """Order copies share this key: shipment, Event Date and normalised text (task 14 / T12-02, proposal C4). Delta,
    Invoice Amount and the carrier invoice number are not part of it."""
    from freight_lineitems.textprep import normalize
    return (rec.shipment_key or "", rec.event_date.isoformat() if rec.event_date else "", normalize(rec.text_raw))


def group_explanations(records: list[InputRecord]) -> list[list[InputRecord]]:
    """Merge rows into explanations. Each group is sorted by row number; its first row is the representative that
    the model reads. Groups come back in order of their first row. One shipment can have several explanations (text
    repeated on another Event Date is a separate explanation, not a copy)."""
    groups: dict[tuple, list[InputRecord]] = {}
    for r in sorted(records, key=lambda r: r.row_number):
        groups.setdefault(explanation_key(r), []).append(r)
    return sorted(groups.values(), key=lambda g: g[0].row_number)


MOCK_R3_DIR = ROOT / "data" / "external" / "mock_public_r3"


MOCK_R4_DIR = ROOT / "data" / "external" / "mock_public_r4"


def load_mock_r4(path: Path = MOCK_R4_DIR / "mock_records_open.jsonl", rounds: tuple[str, ...] | None = None) -> list[InputRecord]:
    """The fourth round of the public mock (task 20 section 3), same layout as round 3. `rounds` keeps only rows whose
    `round` is listed (e.g. ('round_04_new',)); record ids are `mock4#<row_id>`. Read-only."""
    out = []
    for r in load_mock_r3(path):
        if rounds is not None and r.raw.get("round") not in rounds:
            continue
        r.record_id, r.source = "mock4#" + r.raw["row_id"], "mock4"
        out.append(r)
    return out


def load_mock_r3(path: Path = MOCK_R3_DIR / "mock_records_open.jsonl") -> list[InputRecord]:
    """The third round of the public mock (task 14 section 4 item 6). Read-only. Differences from round 1: the row's
    `order_id` is the PK (order copies on one truck); only rows with `active: true` are used; Delta and Invoice
    Amount follow the client's spreadsheet method and, as everywhere, are baseline columns only."""
    path = assert_readable(path)
    out = []
    for i, line in enumerate(path.read_text().splitlines()):
        r = json.loads(line)
        if not r.get("active", True):
            continue
        out.append(InputRecord(
            record_id=f"mock3#{r['row_id']}", source="mock3", row_number=i, shipment_key=r["shipment_id"], carrier=r["carrier"],
            carrier_invoice=r.get("carrier_invoice"), pk=r.get("order_id"),
            event_date=datetime.fromisoformat(r["event_date"].replace("Z", "+00:00")).replace(tzinfo=None),
            text_raw=r["text"] or "", delta=_dec(r.get("delta")), invoice_amount=_dec(r.get("invoice_amount")),
            shipment_amount=_dec(r["shipment_amount"]), origin_state=r.get("origin_state"),
            destination_state=r.get("destination_state"), reason_code=r.get("reason_code"), raw=r))
    return out
