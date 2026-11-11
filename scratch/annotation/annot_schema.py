"""Shared definitions for the annotation packs (task 10 section 6): dropdown options, sheet layout, import format.

Everything an annotator can choose is defined here once, so the workbook, the guide, the import script, the
agreement computation and the metric script (scratch/eval/metrics.py) cannot drift apart.
Nothing here decides whether a charge should be paid; the options only describe what the text says.
"""

from __future__ import annotations

from freight_lineitems.config import TAXONOMY

# ---- item 1: what is this number --------------------------------------------------------------------------------
WHAT = {   # code -> (English label shown in the dropdown, Chinese label used in the Chinese guide)
    "MONEY": ("Money amount", "金额"),
    "WEIGHT": ("Not money: weight", "不是金额：重量"),
    "DATE": ("Not money: date", "不是金额：日期"),
    "ID": ("Not money: ZIP or ID number", "不是金额：邮编或编号"),
    "QUANTITY": ("Not money: quantity", "不是金额：数量"),
    "RATE": ("Not money: rate or unit price", "不是金额：费率或单价"),
    "PERCENT": ("Not money: percentage", "不是金额：百分比"),
}

# ---- item 2: is the money amount part of this claim -------------------------------------------------------------
CLAIM = {
    "COUNTED": ("Counted in this claim", "计入"),
    "NOT_HISTORY": ("Not counted: already paid or billed (history)", "不计入：已付或已开票的历史"),
    "NOT_TOTAL": ("Not counted: total or subtotal", "不计入：合计或小计"),
    "NOT_REFERENCE": ("Not counted: approved amount or other reference", "不计入：批准额或其他引用"),
    "CREDIT": ("Credit (carrier gives back to PPG)", "贷记（承运商退给 PPG）"),
    "UNCLEAR": ("Unclear", "说不清"),
}
CLAIM_COARSE = {"COUNTED": "COUNTED", "NOT_HISTORY": "NOT_COUNTED", "NOT_TOTAL": "NOT_COUNTED",
                "NOT_REFERENCE": "NOT_COUNTED", "CREDIT": "CREDIT", "UNCLEAR": "UNCLEAR"}
NOT_MONEY = "NOT_MONEY"      # filled in by code for the claim field of a number that is not money

# ---- item 3: coarse charge category (taxonomy categories + two extra answers) -----------------------------------
_CATEGORY_LABELS = {   # taxonomy category -> labels; the list of categories itself comes from config/taxonomy.yaml
    "LINEHAUL": ("Linehaul (the transportation charge itself)", "干线运费（运输本身的费用）"),
    "FUEL": ("Fuel surcharge", "燃油附加费"),
    "RATE_CORRECTION": ("Rate correction (rate, tier, weight or factor applied wrongly)", "费率更正（费率、档位、重量或系数用错）"),
    "ACCESSORIAL": ("Accessorial (extra service at pickup or delivery)", "附加服务费（提货或送货时的额外服务）"),
    "DETENTION_STORAGE": ("Detention, storage, per diem (time-based)", "滞留、仓储、按日计费（按时间收的费）"),
    "DRAYAGE": ("Drayage (port or rail container moves)", "短驳（港口或铁路集装箱相关）"),
    "TAX": ("Tax", "税"),
    "OTHER": ("Other named charge", "其他有名称的费用"),
    "PENDING": ("Meaning pending confirmation", "含义待确认"),
}
NO_CHARGE_NAMED = "NO_CHARGE_NAMED"
_missing = set(TAXONOMY["categories"]) ^ set(_CATEGORY_LABELS)
if _missing:   # a taxonomy change must be followed here, loudly
    raise RuntimeError(f"annotation categories out of step with config/taxonomy.yaml: {sorted(_missing)}")
CATEGORY = {c: _CATEGORY_LABELS[c] for c in TAXONOMY["categories"] if c not in ("OTHER", "PENDING")}
CATEGORY["OTHER"] = _CATEGORY_LABELS["OTHER"]
CATEGORY[NO_CHARGE_NAMED] = ("Text names no charge", "原文没写费用名")
CATEGORY["PENDING"] = _CATEGORY_LABELS["PENDING"]

# ---- item 4: one cell per record ---------------------------------------------------------------------------------
CONFIDENT = {"YES": ("Yes", "有"), "NO": ("No", "没有")}

FIELDS = {"what": WHAT, "claim": CLAIM, "category": CATEGORY, "confident": CONFIDENT}
LABEL_TO_CODE = {f: {v[0]: k for k, v in opts.items()} for f, opts in FIELDS.items()}


def label(field: str, code: str, lang: str = "en") -> str:
    en, zh = FIELDS[field][code]
    return en if lang == "en" else f"{en}（{zh}）"


# ---- workbook layout ---------------------------------------------------------------------------------------------
SHEETS = ["Instructions", "Examples", "Glossary", "Annotation"]
ANNOTATION_COLUMNS = [   # (header, key, width)
    ("Item", "item_id", 10),
    ("Text of the item", "text", 70),
    ("No.", "number_id", 6),
    ("Number as written", "number_raw", 16),
    ("Where it is (number between » «)", "context", 46),
    ("1. What is this number?", "what", 28),
    ("2. Money only: part of this claim?", "claim", 40),
    ("3. Counted only: charge category", "category", 44),
    ("4. Confident about this item? (first row)", "confident", 16),
    ("Note (optional)", "note", 40),
]
COL = {key: i + 1 for i, (_, key, _) in enumerate(ANNOTATION_COLUMNS)}
PACK_ID_CELL = "B2"         # on the Instructions sheet
ANNOTATOR_CELL = "B3"       # on the Instructions sheet, filled in by the annotator

# ---- import (long) format: one row per annotator x number -------------------------------------------------------
IMPORT_COLUMNS = ["annotator", "pack", "item_id", "record_id", "is_common", "number_id", "number_raw",
                  "what", "claim", "category", "confident", "note", "source_file", "source_row"]
