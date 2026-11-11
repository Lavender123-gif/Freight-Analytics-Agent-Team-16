"""Data model for the pipeline (task 09: P3 blind parsing, P4a submission checks).

Conventions
- Money is `Decimal` in code and a string in JSON; never float.
- Spans are [start, end) offsets into the redacted text.
- The model never writes an amount. It refers to numbers by id ('#3'); code takes the value from the number table.
  The only digits the model writes are `digits_read` for unrecognized regions, checked digit-for-digit.
- `LLMInput` has no Delta field and nothing derived from Delta (decision 3.1). This is enforced by
  the blind-parsing tests in `tests/test_agent.py`, which inspect the schema, the prompt, the tools and every request.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------------------------- step 2: number table

class NumberToken(Strict):
    id: str = Field(description="'#1', '#2', ... in text order")
    raw: str = Field(description="Exact source text of the token including a leading '$' and its space, e.g. '$ 8 400.00'")
    span: tuple[int, int]
    value: Decimal = Field(description="Normalised value: spaces removed, leading dot -> 0.xx")
    digits: str = Field(description="Digit characters only")
    has_dollar: bool
    dollar_space: bool
    space_merged: bool = Field(description="Digit groups joined across spaces ('1 684.68'); a parsing heuristic, may be wrong")
    leading_dot: bool
    trailing_dot: bool
    decimals: int
    minus_before: Literal["none", "adjacent", "spaced"]
    prev_symbol: str | None
    prev_word: str | None
    next_word: str | None
    unit_hint: str | None


class DateToken(Strict):
    id: str
    raw: str
    span: tuple[int, int]
    kind: Literal["iso_datetime", "mdy", "md", "time"]
    has_year: bool


class UnrecognizedRegion(Strict):
    id: str = Field(description="'?1', '?2', ...")
    raw: str
    span: tuple[int, int]


class ParseResult(Strict):
    numbers: list[NumberToken]
    dates: list[DateToken]
    unrecognized: list[UnrecognizedRegion]
    marked_text: str
    coverage_ok: bool


# --------------------------------------------------------------------------------------------- model input (blind)

class LLMNumberView(Strict):
    id: str
    raw: str
    value: str
    has_dollar: bool
    space_merged: bool
    leading_dot: bool
    trailing_dot: bool
    decimals: int
    minus_before: Literal["none", "adjacent", "spaced"]
    prev_symbol: str | None
    unit_hint: str | None


class LLMInput(Strict):
    """The only data the model sees about a record. No Delta, no invoice/shipment amounts, no carrier, no reason code,
    no dispute status (decision 3.1; task 06 C)."""
    schema_version: Literal["llm-input-v2"] = "llm-input-v2"
    redacted_text: str
    marked_text: str
    numbers: list[LLMNumberView]
    unrecognized: list[UnrecognizedRegion]
    origin_province: str | None
    destination_province: str | None


# --------------------------------------------------------------------------------------------- model output

class Kind(str, Enum):
    CHARGE_AMOUNT = "CHARGE_AMOUNT"
    UNSPECIFIED_AMOUNT = "UNSPECIFIED_AMOUNT"
    TAX_AMOUNT = "TAX_AMOUNT"
    TOTAL = "TOTAL"
    RATE = "RATE"
    QUANTITY = "QUANTITY"
    REFERENCE = "REFERENCE"


MONEY_KINDS = {Kind.CHARGE_AMOUNT, Kind.UNSPECIFIED_AMOUNT, Kind.TAX_AMOUNT, Kind.TOTAL}
ITEM_KINDS = {Kind.CHARGE_AMOUNT, Kind.UNSPECIFIED_AMOUNT, Kind.TAX_AMOUNT}


class Status(str, Enum):
    CLAIMED = "CLAIMED"
    UNPAID = "UNPAID"
    BILLED = "BILLED"
    PAID = "PAID"
    DEDUCTED = "DEDUCTED"
    NONE = "NONE"


COUNTED_STATUSES = {Status.CLAIMED, Status.UNPAID}


class BasisType(str, Enum):
    PPG_NOTIFIED = "PPG_NOTIFIED"
    PPG_APPROVED = "PPG_APPROVED"
    PPG_LIST = "PPG_LIST"
    CONTRACT_OR_TARIFF = "CONTRACT_OR_TARIFF"
    SHIPPING_DOCUMENT = "SHIPPING_DOCUMENT"
    OTHER = "OTHER"
    NONE = "NONE"


class NumberJudgment(Strict):
    id: str = Field(description="Number id from the table ('#3'), or an unrecognized region id ('?1') inside unrecognized_reads")
    kind: Kind
    status: Status = Field(description="CLAIMED/UNPAID are counted in this dispute; BILLED/PAID/DEDUCTED are history; NONE for non-money")
    is_credit: bool = Field(description="True only when the text presents this amount as a credit/reduction (e.g. 'CREDIT', '-$20', '($45.00)')")
    charge_codes: list[str] = Field(description="Taxonomy codes; empty, one, or several (several = one amount for several charges)")
    other_phrase: str | None = Field(description="Required when charge_codes contains OTHER: the verbatim phrase naming the charge")
    evidence_phrase: str = Field(description="Verbatim phrase from redacted_text that supports kind/status/codes")
    exclusion_phrase: str | None = Field(description="Required for a '$' number that is not counted (status not CLAIMED/UNPAID) and is not a TOTAL: the verbatim words that show it is not part of this claim, e.g. 'PAID', 'PREVIOUSLY BILLED', 'EACH'")


class LineItem(Strict):
    amount_ref: str | None = Field(description="Id of the CLAIMED/UNPAID number holding this item's amount; null when the text names a charge without an amount")
    charge_codes: list[str] = Field(description="Only when amount_ref is null; otherwise leave empty (codes come from the number)")
    raw_charge_label: str | None = Field(description="Verbatim phrase in the text that names this charge, or null if the text names none")
    carrier_stated_reason: str | None = Field(description="Verbatim fragment giving the carrier's reason (not verified), or null")
    carrier_stated_basis_type: BasisType
    carrier_stated_basis: str | None = Field(description="Verbatim fragment of the basis the carrier cites; null when type is NONE")


class Relation(Strict):
    relation_type: Literal["PRODUCT", "SUM", "TAX"] = Field(
        description="PRODUCT: operands multiplied give the result (quantity x rate). SUM: operands added give the result "
                    "(items = total). TAX: result is a tax amount on the operands (the tax base)")
    operand_ids: list[str] = Field(description="Number ids of the operands")
    result_id: str | None = Field(description="Number id of the stated result; null if the text does not state it")


class UnrecognizedRead(Strict):
    region_id: str
    digits_read: str = Field(description="Every digit in the region, in order, exactly as written (letters dropped)")
    as_number: NumberJudgment = Field(description="Your judgment of what the region is; id must equal region_id")


class Submission(Strict):
    response_type: Literal["FIRST", "REVISED", "INSISTED"] = Field(
        description="FIRST on the first submission. After a check result: REVISED if you changed your reading, INSISTED "
                    "if you resubmit the same reading")
    reason: str | None = Field(description="Required for REVISED (what you misread) and INSISTED (why the reading stands); null for FIRST")
    numbers: list[NumberJudgment]
    line_items: list[LineItem]
    relations: list[Relation]
    unrecognized_reads: list[UnrecognizedRead]


# --------------------------------------------------------------------------------------------- diagnostics

class Diagnostic(Strict):
    code: str
    path: str = Field(description="What it points at: 'text', 'numbers/#3', 'line_items/1', 'claim', 'run', 'attempts'")
    evidence: dict
    step: str
    origin: Literal["CODE_RULE", "MODEL_REPORTED"] = "CODE_RULE"


class RepairError(Strict):
    """A mandatory-check failure returned to the model. Built from the text and the submission only; never from Delta."""
    code: str
    path: str
    evidence: dict
    allowed_fixes: list[str]
