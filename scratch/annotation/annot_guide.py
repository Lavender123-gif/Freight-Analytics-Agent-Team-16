"""Content of the annotation guide: instructions, worked examples, glossary (English primary, Chinese alongside).

One source for the Markdown guides (docs/annotation/annotation_guide.{en,zh}.md) and for the Instructions / Examples /
Glossary sheets of every pack. The example texts are SYNTHETIC: written for the guide in the style of carrier notes,
not taken from any data file, so they can live in tracked files and can never be a pack record. Each example text is
run through the real `prepare()` when the guide is rendered, so the number rows shown are exactly what the code cuts.

Usage: uv run python scratch/annotation/annot_guide.py      (rewrites the two Markdown guides)
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from annot_schema import CATEGORY, CLAIM, CONFIDENT, WHAT, label  # noqa: E402

from freight_lineitems.config import ROOT  # noqa: E402
from freight_lineitems.records import InputRecord  # noqa: E402

DOCS_DIR = ROOT / "docs" / "annotation"

# ------------------------------------------------------------------------------------------------- instructions

TASK = {
    "en": [
        "Carriers explain invoice adjustments in short free-text notes. For each note you get the text (personal names "
        "already replaced by placeholders) and a list of the numbers our code found in it, one row per number. "
        "You tell us what each number is. Your answers are the reference we use to measure whether the software reads "
        "these notes correctly.",
        "You are **not** asked whether a charge is justified or should be paid. Never judge that. You only record what "
        "the text says.",
        "One pack has 45 items and takes about 2 hours. Work alone; do not discuss items with other annotators until "
        "everyone has handed in. Fill in your annotator ID on the Instructions sheet (cell B3), then work on the "
        "Annotation sheet. Every answer is a dropdown; do not type other values. Do not sort, insert or delete rows.",
    ],
    "zh": [
        "承运商用很短的自由文本解释发票调整。每条记录给你原文（人名已换成占位符）和代码在原文里找到的数字，一行一个数字。"
        "你来说明每个数字是什么。你的答案是参照答案，用来衡量软件读这些文本读得准不准。",
        "**不**需要判断费用有没有道理、该不该付，任何时候都不要做这个判断。只记录原文怎么写。",
        "一个包 45 条，大约 2 小时。独立完成；所有人交回之前，不要和其他标注人讨论具体条目。先在 Instructions 表的 B3 格填上你的"
        "标注人编号，然后在 Annotation 表里填。每一格都是下拉菜单，不要手打其他内容。不要排序，不要插入或删除行。",
    ],
}

ITEMS = {
    "en": [
        ("1. What is this number? (every row)",
         "Choose **Money amount** for any sum of money: a charge, a tax amount, a total, an amount paid, a credit. "
         "Otherwise choose what it is: weight; date; ZIP or ID number (BOL, PRO, invoice, reference numbers); quantity "
         "(days, hours, pallets, pieces); rate or unit price (`$75 EACH`, `@ $50 A DAY`: a price per unit, not the sum "
         "asked for); percentage. If you cannot tell whether a number is money, choose Money amount and answer "
         "Unclear in item 2."),
        ("2. Is it part of this claim? (only rows you marked Money amount)",
         "**Counted**: an amount the carrier is asking for now (also amounts described as still owed or short paid). "
         "**Not counted: already paid or billed (history)**: what was invoiced, paid or deducted before. "
         "**Not counted: total or subtotal**: the sum of other amounts listed in the same text; count the parts, not "
         "the total. **Not counted: approved amount or other reference**: an amount quoted for context (approved, "
         "quoted, per contract) that is not itself asked for. **Credit**: the carrier gives money back to PPG "
         "(credit, refund, overpayment, a minus sign). **Unclear**: two readings are both defensible."),
        ("3. Charge category (only rows you marked Counted)",
         "Pick the category of the charge the text names for this amount; the Glossary sheet says which category "
         "common charge words belong to. **Text names no charge**: the text gives an amount but no charge name. "
         "**Meaning pending confirmation**: the charge word is one we have not confirmed with the client (listed in "
         "the Glossary); choose this and do not guess. **Other named charge**: a charge is named but fits no "
         "category. If one amount covers charges from two categories, pick the first one named and say so in the note."),
        ("4. Confident about this item? (first row of each item) and Note",
         "**Yes** if you would give the same answers again tomorrow; **No** if any answer for this item was a close "
         "call. The note is optional: use it to say what was ambiguous, or that a number looks wrongly cut."),
    ],
    "zh": [
        ("1. 这个数字是什么？（每一行都填）",
         "凡是一笔钱都选 **Money amount（金额）**：费用、税额、合计、已付金额、贷记都算。不是钱就选它是什么：重量；日期；"
         "邮编或编号（BOL、PRO、发票号、参考号）；数量（天数、小时、托盘数、件数）；费率或单价（`$75 EACH`、`@ $50 A DAY`，"
         "是每单位的价格，不是要收的总额）；百分比。分不清是不是钱时，选 Money amount，并在第 2 项选 Unclear。"),
        ("2. 是否属于这次主张？（只填第 1 项选了 Money amount 的行）",
         "**Counted（计入）**：承运商现在要收的金额（写明仍欠、少付的也算）。"
         "**Not counted: already paid or billed（不计入：历史）**：以前开过票、付过或扣过的金额。"
         "**Not counted: total or subtotal（不计入：合计或小计）**：同一段文字里其他金额加起来的数；计入的是各个分项，不是合计。"
         "**Not counted: approved amount or other reference（不计入：批准额或其他引用）**：只是拿来说明情况的金额（批准额、报价、合同价），本身不是要收的钱。"
         "**Credit（贷记）**：承运商退给 PPG 的钱（credit、refund、overpayment、负号）。"
         "**Unclear（说不清）**：两种读法都说得通。"),
        ("3. 费用大类（只填第 2 项选了 Counted 的行）",
         "按原文给这笔金额写的费用名选大类；常见费用词属于哪一类见 Glossary 表。"
         "**Text names no charge（原文没写费用名）**：只有金额，没有费用名。"
         "**Meaning pending confirmation（含义待确认）**：费用词的含义还没向客户确认（术语表里列出）；选这一项，不要猜。"
         "**Other named charge（其他有名称的费用）**：写了费用名，但哪一类都不合适。"
         "一笔金额对应两个大类的费用时，选先写的那个，并在备注里说明。"),
        ("4. 这条有没有把握？（每条的第一行）以及备注",
         "**Yes（有）**：明天再做一遍会给出同样的答案；**No（没有）**：这条里有任何一格是勉强选的。"
         "备注可不填：用来写哪里有歧义，或者某个数字看起来切错了。"),
    ],
}

RULES = {
    "en": [
        "Judge from the text only. Do not guess, and do not use what you think the carrier probably meant.",
        "If two readings are both defensible, choose **Unclear** (for every number whose role depends on which "
        "reading is right) and say why in the note. Unclear is a valid answer, not a failure.",
        "Fill every row. Leave item 2 empty for numbers that are not money, and item 3 empty for amounts that are "
        "not Counted.",
        "Dates and times the code recognised (such as `06/03`) have no row; you do not annotate them. A row whose "
        "number is `?1` is a chunk the code could not cut (letters and digits mixed): judge the number inside it.",
        "The examples below are synthetic: written for this guide in the style of the data. None of them is an item "
        "in a pack.",
    ],
    "zh": [
        "只按原文判断。不猜，也不要按“承运商大概是这个意思”来填。",
        "两种读法都说得通时，选 **Unclear（说不清）**（凡是角色取决于哪种读法的数字都选），并在备注里写原因。“说不清”是正常答案，不算没做好。",
        "每一行都要填。不是金额的数字，第 2 项留空；没有选 Counted 的金额，第 3 项留空。",
        "代码已经认出的日期和时间（如 `06/03`）没有行，不用标。编号是 `?1` 的行是代码切不开的一段（字母和数字混在一起）：判断里面的那个数字。",
        "下面的例子都是合成的：按数据的写法专门为本指南写的，不是任何包里的条目。",
    ],
}

# ------------------------------------------------------------------------------------------------- worked examples
# answers: number id -> (what, claim or None, category or None, why_en, why_zh)

EXAMPLES = [
    {
        "title": {"en": "A single charge", "zh": "单笔费用"},
        "text": "LIFTGATE DELIVERY REQUIRED PER BOL 88213 - $45.00",
        "look": {"en": "The word next to each number: `BOL` before 88213, the charge name `LIFTGATE DELIVERY` and the `$` on 45.00.",
                 "zh": "看每个数字旁边的词：88213 前面是 `BOL`；45.00 带 `$`，对应的费用名是 `LIFTGATE DELIVERY`。"},
        "criterion": {"en": "A number introduced by a document word (BOL, PRO, INVOICE, REF) is an ID. One charge name with one amount and no history words: the amount is counted.",
                      "zh": "跟在单据词（BOL、PRO、INVOICE、REF）后面的数字是编号。一个费用名配一个金额、没有任何历史用词：这个金额计入。"},
        "answers": {
            "#1": ("ID", None, None, "Follows `BOL`: a bill of lading number, not money. Items 2 and 3 stay empty.",
                   "跟在 `BOL` 后面，是提单号，不是钱。第 2、3 项留空。"),
            "#2": ("MONEY", "COUNTED", "ACCESSORIAL", "The only amount, asked for a liftgate delivery; liftgate is an extra delivery service, so Accessorial.",
                   "唯一的金额，为 liftgate 送货而收；liftgate 是送货时的额外服务，属于附加服务费。"),
        },
        "confident": ("YES", "Nothing in the text allows a second reading.", "原文没有第二种读法。"),
    },
    {
        "title": {"en": "Several charges plus a total (BALANCE DUE)", "zh": "多项费用加合计（BALANCE DUE）"},
        "text": "INSIDE DELIVERY $25 LIFTGATE $18.50 FUEL SURCHARGE $31.20 BALANCE DUE $74.70",
        "look": {"en": "Each charge name with the amount right after it, then check the last amount: 25 + 18.50 + 31.20 = 74.70.",
                 "zh": "每个费用名和紧跟其后的金额；再核对最后一个金额：25 + 18.50 + 31.20 = 74.70。"},
        "criterion": {"en": "When the listed amounts add up to the BALANCE DUE, the BALANCE DUE is their total: count the parts, mark the total Not counted. Do the addition yourself. "
                            "If it does not add up, you cannot tell from the text whether the BALANCE DUE is a total or a separate amount: choose Unclear for the numbers whose role depends on it and say so in the note.",
                      "zh": "列出的金额加起来正好等于 BALANCE DUE 时，BALANCE DUE 就是合计：分项计入，合计选不计入。加法要自己算一遍。"
                            "加不上时，光看原文分不出 BALANCE DUE 是合计还是另外一笔：角色取决于此的数字都选 Unclear，并在备注里说明。"},
        "answers": {
            "#1": ("MONEY", "COUNTED", "ACCESSORIAL", "Amount for inside delivery, an extra delivery service.", "inside delivery 的金额，送货时的额外服务。"),
            "#2": ("MONEY", "COUNTED", "ACCESSORIAL", "Amount for liftgate, an extra delivery service.", "liftgate 的金额，送货时的额外服务。"),
            "#3": ("MONEY", "COUNTED", "FUEL", "Amount for the fuel surcharge.", "燃油附加费的金额。"),
            "#4": ("MONEY", "NOT_TOTAL", None, "Equals #1 + #2 + #3, so it is their total. Counting it too would double the claim. Item 3 stays empty.",
                   "等于 #1 + #2 + #3，是它们的合计。再计入一次就重复了。第 3 项留空。"),
        },
        "confident": ("YES", "The sum checks out exactly.", "加法完全对得上。"),
    },
    {
        "title": {"en": "Payment history: paid and still owed in one note", "zh": "付款历史：已付和仍欠写在一起"},
        "text": "BILLED LINE HAUL $ 1 250.00 AND FSC 187.50 PAID 1 250.00 SHORT PAID 187.50 PLEASE PAY BALANCE",
        "look": {"en": "The status word in front of each amount: `BILLED`, `PAID`, `SHORT PAID`. Note that `$ 1 250.00` is one number (1,250.00) written with a space.",
                 "zh": "每个金额前面的状态词：`BILLED`、`PAID`、`SHORT PAID`。注意 `$ 1 250.00` 是一个数（1,250.00），千位用空格隔开。"},
        "criterion": {"en": "Billed and paid amounts are history. Only the amount described as short paid or still owed is counted. The same value can appear twice with different roles: judge each occurrence by the words around it.",
                      "zh": "已开票、已付的金额是历史。只有写明少付或仍欠的金额计入。同一个数值可以出现两次、角色不同：每一处按它周围的词判断。"},
        "answers": {
            "#1": ("MONEY", "NOT_HISTORY", None, "What was billed for line haul: history.", "line haul 的开票金额，是历史。"),
            "#2": ("MONEY", "NOT_HISTORY", None, "What was billed for the fuel surcharge (FSC): history. No `$`, but it is clearly money.", "燃油附加费（FSC）的开票金额，是历史。没有 `$`，但显然是钱。"),
            "#3": ("MONEY", "NOT_HISTORY", None, "Follows `PAID`: already paid.", "跟在 `PAID` 后面，已经付了。"),
            "#4": ("MONEY", "COUNTED", "FUEL", "Follows `SHORT PAID`: still owed and asked for now. It is the unpaid 187.50 billed as FSC, so Fuel surcharge.",
                   "跟在 `SHORT PAID` 后面：仍欠、现在要收。它就是没付的那笔 FSC 187.50，所以选燃油附加费。"),
        },
        "confident": ("YES", "Each amount has its own status word.", "每个金额都有自己的状态词。"),
    },
    {
        "title": {"en": "Quantity times rate, with a weight and dates in between", "zh": "数量乘单价，中间夹着重量和日期"},
        "text": "ADD $225 DESTINATION PER DIEM - CONTAINER 18 450 LBS DELIVERED 06/03 RETURNED 06/08 - 2 DAYS FREE - 3 DAYS @ $75 EACH",
        "look": {"en": "Unit words after the numbers (`LBS`, `DAYS`) and price words (`@`, `EACH`); then check 3 x 75 = 225. The dates 06/03 and 06/08 have no rows.",
                 "zh": "数字后面的单位词（`LBS`、`DAYS`）和单价用词（`@`、`EACH`）；再核对 3 x 75 = 225。日期 06/03、06/08 没有行。"},
        "criterion": {"en": "In `quantity @ price = amount`, only the amount is counted. The price per unit is Rate or unit price even with a `$`; the quantity is Quantity. If the text gave only `3 DAYS @ $75` with no result, whether $75 is the unit price or the whole charge is not stated: Money amount, Unclear.",
                      "zh": "“数量 @ 单价 = 金额”里只有金额计入。单价即使带 `$` 也选费率或单价；数量选数量。如果原文只写 `3 DAYS @ $75`、没写结果，$75 是单价还是整笔费用原文没说：选 Money amount，第 2 项选 Unclear。"},
        "answers": {
            "#1": ("MONEY", "COUNTED", "DETENTION_STORAGE", "`ADD $225` is the amount asked for; per diem is a daily charge for keeping a container, a time-based charge.",
                   "`ADD $225` 是要收的金额；per diem 是占用集装箱按日收的费，属于按时间收的费。"),
            "#2": ("WEIGHT", None, None, "Followed by `LBS`. `18 450` is one number (18,450) written with a space.", "后面是 `LBS`。`18 450` 是一个数（18,450），千位用空格隔开。"),
            "#3": ("QUANTITY", None, None, "A number of days (the free days).", "天数（免费的天数）。"),
            "#4": ("QUANTITY", None, None, "A number of days (the days charged).", "天数（收费的天数）。"),
            "#5": ("RATE", None, None, "`@ $75 EACH` is the price per day. 3 x 75 = 225 is already in #1, so this is not a second amount.",
                   "`@ $75 EACH` 是每天的价格。3 x 75 = 225 已经是 #1，所以这不是另一笔金额。"),
        },
        "confident": ("YES", "The product matches the amount asked for.", "乘积和要收的金额对得上。"),
    },
    {
        "title": {"en": "Tax mentioned without a tax amount, and a credit", "zh": "写了税但没有税额，以及贷记"},
        "text": "REDELIVERY $150.00 + HST. LESS CREDIT $20.00 FOR OVERPAYMENT ON PRIOR INVOICE AS CONFIRMED BY [PERSON_1]",
        "look": {"en": "`+ HST` has no number after it. `LESS CREDIT` and `OVERPAYMENT` in front of $20.00. `[PERSON_1]` stands for a removed name.",
                 "zh": "`+ HST` 后面没有数字。$20.00 前面有 `LESS CREDIT` 和 `OVERPAYMENT`。`[PERSON_1]` 是被去掉的人名。"},
        "criterion": {"en": "You annotate only the numbers that are there. A tax that is named without an amount gets no row and you do not work one out. (A tax amount that is written, such as `GST $7.50`, is an ordinary Money amount: Counted when it is asked for, category Tax.) An amount the carrier gives back (credit, refund, overpayment, minus sign) is Credit, not Counted.",
                      "zh": "只标原文里有的数字。只写了税名、没写税额的，没有行，也不要自己去算。（写出来的税额，如 `GST $7.50`，就是普通的金额：是要收的就计入，大类选税。）承运商退回的金额（credit、refund、overpayment、负号）选贷记，不选计入。"},
        "answers": {
            "#1": ("MONEY", "COUNTED", "ACCESSORIAL", "Amount for redelivery, a second delivery attempt. The category is Accessorial, not Tax: HST is only mentioned.",
                   "redelivery（再次送货）的金额。大类选附加服务费，不选税：HST 只是提了一下。"),
            "#2": ("MONEY", "CREDIT", None, "`LESS CREDIT ... FOR OVERPAYMENT`: money going back to PPG. Item 3 stays empty because it is not Counted.",
                   "`LESS CREDIT ... FOR OVERPAYMENT`：退给 PPG 的钱。没有选 Counted，所以第 3 项留空。"),
        },
        "confident": ("YES", "Optional note: \"HST mentioned, no amount\".", "备注可写：“提到 HST，没有税额”。"),
    },
]

# ------------------------------------------------------------------------------------------------- glossary
# (term, English sentence, Chinese sentence)

GLOSSARY = [
    ("BALANCE DUE", "The amount the carrier says is still owed; if it equals the sum of amounts listed beside it, it is their total (Not counted: total), otherwise judge from the text or choose Unclear.",
     "承运商说还欠的金额；等于旁边各金额之和时是合计（不计入：合计），否则按原文判断或选说不清。"),
    ("SHORT PAID", "PPG paid less than the invoice; the amount after it is the unpaid part and is normally Counted.", "PPG 付的比发票少；后面的金额是没付的部分，通常计入。"),
    ("ADJUSTED OFF", "An amount that was removed or deducted from an earlier invoice or payment; history, Not counted.", "以前从发票或付款里减掉的金额；是历史，不计入。"),
    ("OVERPAYMENT", "PPG paid more than was owed; an amount described this way goes back to PPG, so Credit.", "PPG 多付了；这样描述的金额要退给 PPG，选贷记。"),
    ("AMOUNT APPROVED", "An amount someone agreed to earlier; quoted as a reference, Not counted (approved amount) unless the text also asks for it.", "以前有人同意过的金额；作为引用出现，选不计入（批准额），除非原文同时在要这笔钱。"),
    ("LINE HAUL (LH, LINEHAUL)", "The basic charge for moving the freight from origin to destination; category Linehaul.", "把货从起点运到终点的基本运费；大类选干线运费。"),
    ("FSC (FUEL SURCHARGE)", "Fuel surcharge, an add-on that follows fuel prices; category Fuel surcharge.", "燃油附加费，随油价变动的附加收费；大类选燃油附加费。"),
    ("ACCESSORIAL", "Any extra service beyond plain transportation at pickup or delivery (liftgate, inside delivery, redelivery, appointment, hazmat, lumper); category Accessorial.", "提货或送货时运输以外的额外服务（liftgate、inside delivery、redelivery、预约、危险品、lumper）；大类选附加服务费。"),
    ("DETENTION", "Charge for a driver or equipment kept waiting beyond the free time; category Detention, storage, per diem.", "司机或设备等待超过免费时间而收的费；大类选滞留、仓储、按日计费。"),
    ("DWELL", "Days a container sits between arriving at the rail ramp and being delivered; category Detention, storage, per diem.", "集装箱从到达铁路场站到送达之间停留的天数；大类选滞留、仓储、按日计费。"),
    ("PER DIEM (PERDIEM)", "A daily charge for keeping a container or chassis beyond the free days; category Detention, storage, per diem.", "占用集装箱或底盘车超过免费天数后按日收的费；大类选滞留、仓储、按日计费。"),
    ("STORAGE", "Charge for freight or a container kept at a terminal or rail ramp; category Detention, storage, per diem.", "货物或集装箱存放在场站或铁路场站的费用；大类选滞留、仓储、按日计费。"),
    ("LUMPER", "Third-party labour paid to unload the truck; category Accessorial.", "请第三方卸货的人工费；大类选附加服务费。"),
    ("LIFTGATE / TAILGATE", "A lift on the back of the truck used where there is no dock; the two words mean the same; category Accessorial.", "车尾升降板，在没有装卸平台的地方使用；两个词是一个意思；大类选附加服务费。"),
    ("TONU", "Truck ordered, not used: a fee when a truck is sent and the load is cancelled; category Accessorial.", "Truck ordered, not used：派了车但货取消时收的费；大类选附加服务费。"),
    ("CHASSIS", "The wheeled frame a shipping container rides on; a chassis charge is category Drayage.", "运集装箱用的带轮底盘车；底盘车费用的大类选短驳。"),
    ("PRE-PULL (YARD PULL)", "Moving a container out of the port or rail yard to another yard before delivery; category Drayage.", "送货前先把集装箱从港口或铁路场站拖到另一个场地；大类选短驳。"),
    ("BOL", "Bill of lading, the shipping document; a number after BOL is an ID, and a weight quoted \"per BOL\" is a weight.", "提单，即运输单据；BOL 后面的数字是编号，“per BOL”引用的重量是重量。"),
    ("GST", "Canadian federal Goods and Services Tax; a GST amount is category Tax.", "加拿大联邦商品及服务税；GST 税额的大类选税。"),
    ("HST", "Harmonized Sales Tax, used in some Canadian provinces in place of GST plus provincial tax; category Tax.", "合并销售税，加拿大部分省份用它代替 GST 加省税；大类选税。"),
    ("PST", "Provincial sales tax in Canada; category Tax.", "加拿大的省销售税；大类选税。"),
    ("QST", "Quebec Sales Tax, the provincial tax of Quebec; category Tax.", "魁北克销售税，魁北克省的省税；大类选税。"),
    ("[PERSON_1], [EMAIL_1], [PHONE_1]", "Placeholders put in by our code where a personal name, an email address or a phone number was removed; the digit only tells people apart, it is not a number to annotate.", "代码把人名、邮箱、电话去掉后放的占位符；里面的数字只用来区分不同的人，不是要标的数字。"),
    ("Space as thousands separator (`$ 8 400.00`)", "Some carriers write thousands with a space, so this is one number, 8,400.00; if the row looks like two different numbers glued together, annotate it as best you can and say so in the note.", "有的承运商用空格分千位，所以这是一个数 8,400.00；如果这一行看起来是两个不同的数被拼在了一起，尽量标，并在备注里说明。"),
    ("Leading-dot decimal (`.69`)", "A decimal written without the zero: `.69` is 0.69, i.e. 69 cents.", "省略了 0 的小数：`.69` 就是 0.69，即 69 美分。"),
    ("PURCHASED TRANSPORTATION (PURCHASE FEE, PURCHASED TRANSP SURCHARGE, any spelling)", "Meaning not yet confirmed with the client: choose \"Meaning pending confirmation\", do not guess.", "含义还没向客户确认：选“含义待确认”，不要猜。"),
    ("Other charge words you do not know", "If a charge is clearly named but you cannot place it in a category, choose \"Other named charge\" and copy the word into the note; do not guess a category.", "写了费用名但你归不了类时，选“其他有名称的费用”，把这个词抄进备注；不要猜大类。"),
]


# ------------------------------------------------------------------------------------------------- rendering

def example_rows(ex: dict) -> dict:
    """Run the synthetic example text through the real prepare(); the answers must cover exactly the numbers found."""
    from build_packs import item_from_prepared  # local import: build_packs imports this module for the sheets
    from freight_lineitems.pipeline import prepare
    rec = InputRecord(record_id="guide#example", source="synthetic", row_number=0, shipment_key="", carrier="",
                      carrier_invoice=None, pk=None, event_date=None, text_raw=ex["text"], delta=Decimal("0"),
                      invoice_amount=None, shipment_amount=None, origin_state=None, destination_state=None, reason_code=None)
    item = item_from_prepared(prepare(rec))
    ids = [n["number_id"] for n in item["numbers"]]
    if ids != list(ex["answers"]):
        raise RuntimeError(f"guide example '{ex['title']['en']}': answers {list(ex['answers'])} do not match the numbers "
                           f"the code finds {ids}; fix the example")
    if item["text"] != ex["text"]:
        raise RuntimeError(f"guide example '{ex['title']['en']}' was changed by redaction; write it with placeholders")
    for nid, (what, claim, cat, _, _) in ex["answers"].items():   # the examples must obey the fill-in rules themselves
        assert what in WHAT and (claim in CLAIM) == (what == "MONEY") and (cat in CATEGORY) == (claim == "COUNTED"), nid
    return item


def _cell(field: str, code: str | None, lang: str) -> str:
    return label(field, code, lang) if code else ("(leave empty)" if lang == "en" else "（留空）")


def render_markdown(lang: str) -> str:
    en = lang == "en"
    out = ["# Annotation guide: what is each number in a carrier note?" if en else "# 标注指南：承运商说明里的每个数字是什么",
           "", ("Chinese version: `annotation_guide.zh.md`. If the two differ, this English version is the reference."
                if en else "英文版：`annotation_guide.en.md`。两版不一致时以英文版为准。下拉菜单是英文的，本文在括号里给出中文。"),
           "", "## The task" if en else "## 任务", ""]
    out += [p + "\n" for p in TASK[lang]]
    out += ["## What you fill in" if en else "## 要填的四项", ""]
    for head, body in ITEMS[lang]:
        out += [f"**{head}** {body}", ""]
    out += ["## Rules" if en else "## 规则", ""] + [f"- {r}" for r in RULES[lang]] + [""]
    out += ["## Worked examples" if en else "## 完整例子", ""]
    for i, ex in enumerate(EXAMPLES, 1):
        item = example_rows(ex)
        out += [f"### {'Example' if en else '例'} {i}: {ex['title'][lang]}", "",
                ("**Text shown to you:**" if en else "**给你看的原文：**"), "", f"> {item['text']}", "",
                f"**{'Where to look' if en else '看哪里'}:** {ex['look'][lang]}", "",
                f"**{'Criterion' if en else '判断标准'}:** {ex['criterion'][lang]}", "",
                ("| No. | Number as written | 1. What is it | 2. Part of this claim | 3. Charge category | Why |" if en else
                 "| 编号 | 原文里的数字 | 1. 是什么 | 2. 是否属于这次主张 | 3. 费用大类 | 为什么 |"),
                "|---|---|---|---|---|---|"]
        for n in item["numbers"]:
            what, claim, cat, why_en, why_zh = ex["answers"][n["number_id"]]
            out.append(f"| {n['number_id']} | `{n['number_raw']}` | {label('what', what, lang)} | {_cell('claim', claim, lang)} | "
                       f"{_cell('category', cat, lang)} | {why_en if en else why_zh} |")
        conf, c_en, c_zh = ex["confident"]
        out += ["", f"**{'4. Confident' if en else '4. 有没有把握'}:** {label('confident', conf, lang)}. {c_en if en else c_zh}", ""]
    out += ["## Glossary" if en else "## 术语表", "", "| Term | Meaning |" if en else "| 术语 | 含义 |", "|---|---|"]
    out += [f"| {t} | {e if en else z} |" for t, e, z in GLOSSARY]
    out += ["", "## Dropdown options" if en else "## 下拉选项一览", ""]
    for n, (field, opts) in enumerate((("what", WHAT), ("claim", CLAIM), ("category", CATEGORY), ("confident", CONFIDENT)), 1):
        out.append(f"- **{n}**: " + "; ".join(label(field, c, lang) for c in opts))
    return "\n".join(out) + "\n"


def write_guides() -> list[Path]:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for lang in ("en", "zh"):
        p = DOCS_DIR / f"annotation_guide.{lang}.md"
        p.write_text(render_markdown(lang), encoding="utf-8")
        paths.append(p)
    return paths


if __name__ == "__main__":
    for p in write_guides():
        print("wrote", p.relative_to(ROOT))
