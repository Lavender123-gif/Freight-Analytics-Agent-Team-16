"""Step 2: find every number, number it, record objective features. No identity judgement (ported from the prototype, B02).

Order: dates/times are claimed first (so '2022-05-23 12:15:00' is not split into numbers), then numbers.
Coverage check: any digit character left unclaimed becomes an unrecognized region (the whole
whitespace-delimited chunk), which the model must read; its read is checked digit-for-digit.
"""

from __future__ import annotations

import re
from decimal import Decimal

from freight_lineitems.config import RULES
from freight_lineitems.schemas import DateToken, NumberToken, ParseResult, UnrecognizedRegion

DATE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("md", re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}/\d{1,2}/\d{1,2}(?![\d/])")),  # range written '07/18/07/22'
    ("iso_datetime", re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}(?::\d{2})?)?(?!\d)")),
    ("mdy", re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})(?![\d/])(?: \d{1,2}:\d{2}(?::\d{2})?(?: ?[AP]M)?)?")),
    ("md", re.compile(r"(?<![\d/.])\d{1,2}/\d{1,2}(?![\d])")),   # '05/27'; also both halves of '07/18/07/22'
    ("time", re.compile(r"(?<![\d:])\d{1,2}:\d{2}(?::\d{2})?(?: ?[AP]M)?(?![\d:])")),
]

NUM_RE = re.compile(
    r"(?P<dollar>\$\s?)?"
    r"(?P<num>(?<![\w.])(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{1,3}(?: \d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?![\d,]\d))"
)
WORD_RE = re.compile(r"[A-Z%]+(?:\(S\))?")
MASK = "\x00"
PLACEHOLDER_RE = re.compile(r"\[(?:PERSON|EMAIL|PHONE)_\d+\]")

UNIT_WORDS = set(RULES["number_features"]["unit_words"])


def _mask(s: str, spans: list[tuple[int, int]]) -> str:
    chars = list(s)
    for a, b in spans:
        chars[a:b] = MASK * (b - a)
    return "".join(chars)


def _prev_word(s: str, i: int) -> str | None:
    m = list(WORD_RE.finditer(s[:i]))
    return m[-1].group(0) if m else None


def _next_word(s: str, j: int) -> str | None:
    rest = s[j:]
    if rest.startswith("%"):
        return "%"
    m = WORD_RE.search(rest)
    return m.group(0) if m and rest[: m.start()].strip(" -.,:;") == "" else None


def parse(text: str) -> ParseResult:
    s = text
    dates: list[DateToken] = []
    # redaction placeholders ('[PERSON_1]') are claimed up front and never become tokens
    claimed: list[tuple[int, int]] = [m.span() for m in PLACEHOLDER_RE.finditer(s)]
    for kind, rx in DATE_PATTERNS:
        for m in rx.finditer(_mask(s, claimed)):
            claimed.append(m.span())
            dates.append(DateToken(id="", raw=m.group(0), span=m.span(), kind=kind,
                                   has_year=kind in ("iso_datetime", "mdy")))
    dates.sort(key=lambda d: d.span)
    for i, d in enumerate(dates, 1):
        d.id = f"D{i}"

    numbers: list[NumberToken] = []
    masked = _mask(s, claimed)
    for m in NUM_RE.finditer(masked):
        raw_num = m.group("num")
        start = m.start("dollar") if m.group("dollar") else m.start("num")
        end = m.end("num")
        before = s[:start].rstrip(" ")
        minus = "none"
        if s[:start].endswith("-"):
            minus = "adjacent"
        elif before.endswith("-"):
            minus = "spaced"
        trailing_dot = end < len(s) and s[end] == "." and not (end + 1 < len(s) and s[end + 1].isdigit())
        decimals = len(raw_num.split(".")[1]) if "." in raw_num else 0
        nw = _next_word(s, end)
        ps = before[-1:] if before and not before[-1].isalnum() and before[-1] != MASK else None
        numbers.append(NumberToken(
            id=f"#{len(numbers) + 1}", raw=s[start:end], span=(start, end),
            value=Decimal(raw_num.replace(" ", "").replace(",", "")), digits=re.sub(r"\D", "", raw_num),
            has_dollar=bool(m.group("dollar")), dollar_space=bool(m.group("dollar")) and m.group("dollar").endswith(" "),
            space_merged=" " in raw_num, leading_dot=raw_num.startswith("."), trailing_dot=trailing_dot,
            decimals=decimals, minus_before=minus, prev_symbol=ps, prev_word=_prev_word(s, start), next_word=nw,
            unit_hint=nw if nw in UNIT_WORDS else None,
        ))
        claimed.append((start, end))

    # Coverage: every digit must be claimed
    rest = _mask(s, claimed)
    unrec: list[UnrecognizedRegion] = []
    for m in re.finditer(r"\S*\d\S*", rest):
        a, b = m.span()
        # extend to the full chunk of the original text
        while a > 0 and not s[a - 1].isspace():
            a -= 1
        while b < len(s) and not s[b].isspace():
            b += 1
        if unrec and unrec[-1].span[1] >= a:
            continue
        unrec.append(UnrecognizedRegion(id=f"?{len(unrec) + 1}", raw=s[a:b], span=(a, b)))
    # numbers inside an unrecognized chunk are dropped from the table (the model reads the chunk)
    if unrec:
        inside = lambda sp: any(u.span[0] <= sp[0] and sp[1] <= u.span[1] for u in unrec)  # noqa: E731
        numbers = [n for n in numbers if not inside(n.span)]
        dates = [d for d in dates if not inside(d.span)]
        for i, n in enumerate(numbers, 1):
            n.id = f"#{i}"

    tokens = [(n.span, f"[{n.id} {n.raw}]") for n in numbers] + [(d.span, f"[{d.id} {d.raw}]") for d in dates] + \
             [(u.span, f"[{u.id} {u.raw}]") for u in unrec]
    out, pos = [], 0
    for (a, b), rep in sorted(tokens):
        out.append(s[pos:a])
        out.append(rep)
        pos = b
    out.append(s[pos:])
    covered = _mask(s, [m.span() for m in PLACEHOLDER_RE.finditer(s)] + [n.span for n in numbers] + [d.span for d in dates] + [u.span for u in unrec])
    return ParseResult(numbers=numbers, dates=dates, unrecognized=unrec, marked_text="".join(out),
                       coverage_ok=not re.search(r"\d", covered))


