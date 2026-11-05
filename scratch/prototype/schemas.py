"""Data model for the v3 pipeline prototype (task 02).

Every object here is written to the record JSON or the event log, except
`LLMInput` (archived verbatim per call) and `RepairReceipt` (returned to the model, logged, not stored).

Conventions
- Money is `Decimal`, serialised as a string, never float.
- Spans are [start, end) character offsets into `Record.text.redacted`.
- Diagnostics and flags point at an object through `Location.path`, a JSON-pointer-like path into the record
  (e.g. `numbers/#3`, `content/line_items/1`, `claim`, `history/<record_id>`).

Run with: uv run --with pydantic --with pyyaml python scratch/prototype/schemas.py  (prints the JSON schemas)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------------------------------------------
# Step 2: number table (code-produced, objective features only, no identity judgement)

class NumberToken(Strict):
    id: str = Field(description="'#1', '#2', ... in text order")
    raw: str = Field(description="Exact source text of the token including a leading '$' and its space, e.g. '$ 8 400.00'")
    span: tuple[int, int]
    value: Decimal = Field(description="Normalised value: spaces removed, leading dot -> 0.xx")
    digits: str = Field(description="Digit characters only; used for exact matching ('8 400.00' -> '840000')")
    has_dollar: bool
    dollar_space: bool = Field(description="'$ 20.00' rather than '$20.00'")
    space_merged: bool = Field(description="Digit groups joined across spaces ('1 684.68'); a parsing heuristic, may be wrong")
    leading_dot: bool
    trailing_dot: bool = Field(description="Followed by '.' that is not a decimal point ('$20.' / '$400. PAID')")
    decimals: int
    minus_before: Literal["none", "adjacent", "spaced"] = Field(
        description="A '-' right before the token (adjacent: '-$ 400.00', '-250'); usually a separator, sometimes a sign")
    prev_symbol: str | None = Field(description="Nearest non-space character before the token if it is not a letter or digit ('@', '=', '+', '#')")
    prev_word: str | None
    next_word: str | None
    unit_hint: str | None = Field(description="next_word if it is in the configured unit lexicon (LBS, KG, %, DAYS ...)")


class DateToken(Strict):
    id: str = Field(description="'D1', 'D2', ...")
    raw: str
    span: tuple[int, int]
    kind: Literal["iso_datetime", "mdy", "md", "time"]
    has_year: bool


class UnrecognizedRegion(Strict):
    id: str = Field(description="'?1', '?2', ...")
    raw: str = Field(description="Whole whitespace-delimited chunk containing unclaimed digit characters, e.g. 'CV19'")
    span: tuple[int, int]


class ParseResult(Strict):
    numbers: list[NumberToken]
    dates: list[DateToken]
    unrecognized: list[UnrecognizedRegion]
    marked_text: str = Field(description="Text with every token replaced by '[#2 $15]', '[D1 6/22/2021]', '[?1 CV19]'")
    coverage_ok: bool = Field(description="True when every digit character is inside a number, date or unrecognized token")


# ---------------------------------------------------------------------------------------------------------------
# Step 3 input: the whitelist. Anything not declared here cannot reach the model.

class LLMNumberView(Strict):
    id: str
    raw: str
    value: Decimal
    has_dollar: bool
    space_merged: bool
    leading_dot: bool
    trailing_dot: bool
    decimals: int
    minus_before: Literal["none", "adjacent", "spaced"]
    prev_symbol: str | None
    unit_hint: str | None


class LLMInput(Strict):
    """Fixed-structure input. Dispute Status must never appear; Reason Code and Carrier are not included."""
    schema_version: Literal["llm-input-v1"] = "llm-input-v1"
    redacted_text: str
    marked_text: str
    numbers: list[LLMNumberView]
    unrecognized: list[UnrecognizedRegion]
    delta: Decimal
    delta_sign: Literal["positive", "zero", "negative"]
    origin_province: str | None
    destination_province: str | None


# ---------------------------------------------------------------------------------------------------------------
# Step 3 output: what submit_line_items accepts. The model writes no amounts except unrecognized_reads.

class Kind(str, Enum):
    CHARGE_AMOUNT = "CHARGE_AMOUNT"            # money for a named charge
    UNSPECIFIED_AMOUNT = "UNSPECIFIED_AMOUNT"  # money whose purpose the text does not state (bare 'BALANCE DUE $21')
    TAX_AMOUNT = "TAX_AMOUNT"
    TOTAL = "TOTAL"                            # a stated total of other numbers in the text ('= $63.00')
    RATE = "RATE"                              # unit price, percentage, factor, per-mile rate
    QUANTITY = "QUANTITY"                      # days, weight, hours, pieces
    REFERENCE = "REFERENCE"                    # document numbers, ZIP codes, addresses


MONEY_KINDS = {Kind.CHARGE_AMOUNT, Kind.UNSPECIFIED_AMOUNT, Kind.TAX_AMOUNT, Kind.TOTAL}


class Status(str, Enum):
    CLAIMED = "CLAIMED"    # asked for in this dispute
    BILLED = "BILLED"      # previously invoiced (history)
    PAID = "PAID"
    UNPAID = "UNPAID"      # outstanding, asked for again
    DEDUCTED = "DEDUCTED"  # adjusted off / short-paid deduction described as history
    NONE = "NONE"          # not money in this dispute (quantities, references, rates)


COUNTED_STATUSES = {Status.CLAIMED, Status.UNPAID}


class EvidenceType(str, Enum):
    PPG_NOTIFIED = "PPG_NOTIFIED"            # carrier says it notified PPG
    PPG_APPROVED = "PPG_APPROVED"            # carrier says a PPG person approved      (added, see report 1.3)
    PPG_LIST = "PPG_LIST"                    # carrier cites a PPG list / requirement
    CONTRACT_OR_TARIFF = "CONTRACT_OR_TARIFF"  # contract, rate, tariff, terms and conditions
    SHIPPING_DOCUMENT = "SHIPPING_DOCUMENT"  # BOL, delivery receipt, weight ticket    (added)
    OTHER = "OTHER"                          # some other stated basis                 (added)
    NONE = "NONE"


class NumberJudgment(Strict):
    id: str
    kind: Kind
    status: Status
    charge_codes: list[str] = Field(description="Taxonomy codes; empty, one, or several (several = combined amount)")
    other_phrase: str | None = Field(description="Required when charge_codes contains OTHER: the source phrase naming the charge")
    evidence_phrase: str = Field(description="Verbatim source phrase supporting kind/status/codes, e.g. 'SHORT PAID'")


class LineItem(Strict):
    amount_ref: str | None = Field(description="Number id holding this item's amount; null when the text names a charge without an amount ('+ HST')")
    charge_codes: list[str] = Field(description="Only when amount_ref is null; otherwise leave empty, codes come from the number")
    quantity_ref: str | None = Field(description="Optional: number id of the quantity when the text states quantity x rate")
    unit_rate_ref: str | None = Field(description="Optional: number id of the unit rate")
    carrier_stated_reason: str | None = Field(description="Verbatim source fragment giving the reason (carrier's claim, not verified)")
    carrier_stated_basis_type: EvidenceType
    carrier_stated_basis: str | None = Field(description="Verbatim source fragment of the basis ('AS PER LIST FROM PPG'); null when type is NONE")


class UnrecognizedRead(Strict):
    region_id: str
    contains_number: bool
    value: Decimal | None = Field(description="The ONLY place the model writes a number; must match the region's digits exactly")
    as_number: NumberJudgment | None = Field(description="Judgment for the read value; id must equal region_id")


class Submission(Strict):
    numbers: list[NumberJudgment]
    line_items: list[LineItem]
    unrecognized_reads: list[UnrecognizedRead]


# ---------------------------------------------------------------------------------------------------------------
# Diagnostics, flags, receipts

class ObjectType(str, Enum):
    RECORD = "REC"      # input text and structured fields
    NUMBER = "NUM"      # one entry of the number table and its judgment
    LINE_ITEM = "ITEM"
    CLAIM = "CLAIM"     # claim summary: claimed sum vs Delta, totals
    HISTORY = "HIST"    # relation to earlier records of the same shipment
    RUN = "RUN"         # the processing run (agent loop, submissions)


class Handling(str, Enum):
    RETURN = "return"   # sent back to the model in a repair receipt
    RECORD = "record"   # stored, never sent back


class Location(Strict):
    object_type: ObjectType
    path: str


class Diagnostic(Strict):
    code: str = Field(description="Dotted, object-first: 'NUM.PARSE.SPACE_MERGED'")
    location: Location
    evidence: dict
    step: str = Field(description="Where it was found: '1', '2', '4-5', '5.5', '3' ... an attribute, not the class")
    handling: Handling
    created_at: datetime


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Flag(Strict):
    code: str
    object_type: ObjectType
    severity: Severity
    locations: list[str]
    evidence: list[dict]
    n_diagnostics: int
    escalation_role: Literal["alone", "score", "none"]
    points: int


class ReceiptError(Strict):
    code: str
    object_type: ObjectType
    path: str
    evidence: dict
    allowed_fixes: list[str]


class RepairReceipt(Strict):
    """Returned by submit_line_items when a returnable check fails. Facts only, no suggested values."""
    receipt_version: Literal["receipt-v1"] = "receipt-v1"
    accepted: Literal[False] = False
    attempt: int
    retries_left: int
    errors: list[ReceiptError]
    never_allowed: list[str] = Field(default_factory=lambda: [
        "change the number table, add numbers, or write amounts outside unrecognized_reads",
        "change a status or kind only to make the sum match Delta",
    ])
    if_you_believe_your_reading_is_correct: str = (
        "Resubmit the same reading unchanged and call report_uncertainty with what does not fit. "
        "The record will be passed to a human with your reading; this is an acceptable outcome."
    )


# ---------------------------------------------------------------------------------------------------------------
# The record object

class SourceInfo(Strict):
    record_id: str
    shipment_id: str
    invoice_pks: list[str] = Field(description="PK values of collapsed export rows; may be empty")
    source_rows: list[int]
    event_date: datetime
    invoice_amount: Decimal
    shipment_amount: Decimal
    delta: Decimal
    origin_state: str | None
    destination_state: str | None
    origin_country: Literal["CA", "US", "other", "unknown"]
    destination_country: Literal["CA", "US", "other", "unknown"]
    reason_code: str | None = Field(description="Stored for the conflict check and analytics; never sent to the LLM")
    carrier: str = Field(description="Stored for evaluation and carrier analytics; never sent to the LLM")
    # Dispute Status is deliberately absent: it is joined back by record_id only at export time.


class TextInfo(Strict):
    original_sha1: str = Field(description="Hash only; original text stays in the source file")
    redacted: str
    n_person_placeholders: int
    n_email_placeholders: int
    injection_hits: list[str]


class ClaimSummary(Strict):
    """Answer to question 1, computed by code from the accepted submission."""
    counted_ids: list[str]
    claimed_sum: Decimal
    implied_tax: Decimal | None
    delta: Decimal
    reconciles: bool | None = Field(description="None when Delta is zero (no anchor)")
    totals: list[dict]
    history_relations: list[str] = Field(description="HIST.* codes that fired, with the earlier record ids in the diagnostics")


class RunInfo(Strict):
    status: Literal["passed", "failed", "not_run_auto_reject", "not_run"]
    submissions: int
    reconcile_calls: int
    tool_calls: list[str]
    model: str | None
    prompt_version: str | None


class Disposition(Strict):
    outcome: Literal["AUTO_REJECT", "HUMAN_REVIEW", "SPLIT_TRUSTED"]
    reasons: list[str] = Field(description="Rule ids and flag codes that decided the outcome")
    score: int
    rules_version: str


class RejectDraft(Strict):
    automatic: bool
    template_codes: list[str]
    reasons: list[str]
    required_changes: list[str]
    acceptance_criteria: list[str]


class Record(Strict):
    source: SourceInfo
    text: TextInfo
    parse: ParseResult
    llm_input: LLMInput | None
    run: RunInfo
    content: Submission | None
    claim: ClaimSummary | None
    diagnostics: list[Diagnostic]
    flags: list[Flag]
    disposition: Disposition
    reject_draft: RejectDraft | None
    versions: dict[str, str] = Field(description="taxonomy, rules, catalog, prompt, model")


# ---------------------------------------------------------------------------------------------------------------
# Event log (append-only). Carrier-management data lives here even though v1 has no feature built on it.

class ReviewerDecision(Strict):
    """What a reviewer records after looking at an escalated record. No payment fields by design."""
    decision: Literal["split_confirmed", "split_corrected", "returned_to_carrier", "cannot_determine"]
    attribution: Literal["carrier_text", "carrier_billing", "system_parse", "system_llm", "ppg_data", "unknown"]
    flag_verdicts: dict[str, Literal["useful", "noise", "wrong"]] = Field(description="Per flag code, for tuning rules.yaml")
    corrected_content: Submission | None
    note: str | None


class Event(Strict):
    event_id: str
    record_id: str
    ts: datetime
    actor: Literal["system", "reviewer", "carrier"]
    type: Literal["ingested", "diagnostic", "flag", "disposition", "auto_reject_sent",
                  "reject_draft_created", "reviewer_decision", "carrier_resubmission_linked"]
    payload: dict


if __name__ == "__main__":
    import json
    for m in (LLMInput, Submission, RepairReceipt, Diagnostic, Flag, Record, Event):
        print(f"--- {m.__name__}")
        print(json.dumps(m.model_json_schema(), indent=1)[:1500])
