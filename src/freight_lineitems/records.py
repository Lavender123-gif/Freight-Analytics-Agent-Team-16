"""Input records. The source file is never modified; everything derived lives in our own outputs (decision 8).

Each source row is its own record (decision 5.3: copies are not merged). Excel/CSV reading is concentrated here
(decision 1.3). Only the dev split and the public mock are readable; the test split is never opened here.
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
    delta: Decimal               # never sent to the model
    invoice_amount: Decimal | None
    shipment_amount: Decimal | None
    origin_state: str | None
    destination_state: str | None
    reason_code: str | None      # never sent to the model
    raw: dict = field(default_factory=dict, repr=False)   # the source row as read, all values as strings

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


EXPECTED_COLUMNS = ["SHIPMENT_GID", "PK", "Carrier Invoice", "Descritipion", "Invoice Amount", "Shipment Amount", "Delta",
                    "Carrier", "Source State", "Destination State", "Event Date", "Reason Code"]


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
            text_raw=_s(r["Descritipion"]) or "", delta=_dec(r["Delta"]), invoice_amount=_dec(r["Invoice Amount"]),
            shipment_amount=_dec(r["Shipment Amount"]), origin_state=_s(r["Source State"]),
            destination_state=_s(r["Destination State"]), reason_code=_s(r["Reason Code"]),
            raw={k: _s(v) for k, v in r.items()}))
    return out


def load_dev() -> list[InputRecord]:
    """The dev split (CSV written by data_split.py from the Excel export; same columns)."""
    return _from_frame(pd.read_csv(assert_readable(DEV_PATH), dtype=str), "dev", "dev")


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
            text_raw=r["text"] or "", delta=_dec(r["delta"]), invoice_amount=_dec(r["invoice_amount"]),
            shipment_amount=_dec(r["shipment_amount"]), origin_state=r.get("origin_state"),
            destination_state=r.get("destination_state"), reason_code=r.get("reason_code"), raw=r))
    return out
