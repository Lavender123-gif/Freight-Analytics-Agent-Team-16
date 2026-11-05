"""Number formats in the free text (aggregates only)."""

import re

from common import DATE_RE, TIME_RE, load_dev, number_tokens

df = load_dev()
t = df.text_norm
n = len(df)

toks = [tok for s in t for tok in number_tokens(s)]
print(f"number tokens (dates and times removed): {len(toks)}")
print(f"  with $ before: {sum(x['has_dollar'] for x in toks)} ({sum(x['has_dollar'] for x in toks) / len(toks):.1%})")
print(f"  space thousands (1 684.68): {sum(x['space_thousands'] for x in toks)}")
print(f"  leading dot (.68): {sum(x['leading_dot'] for x in toks)}")


def rows(pattern: str, flags: int = 0) -> int:
    return int(t.str.contains(pattern, regex=True, flags=flags).sum())


print(f"rows: {n}")
print(f"rows with no $ amount but some number: {sum(1 for s in t if number_tokens(s) and not any(x['has_dollar'] for x in number_tokens(s)))}")
print(f"rows with '$ ' (space after $): {rows(r'\$ \d')}")
print(f"rows with space-thousands number: {sum(1 for s in t if any(x['space_thousands'] for x in number_tokens(s)))}")
print(f"  of which the number is a weight (LBS/KG follows): {rows(r'\b\d{1,3}(?: \d{3})+\s*(?:LBS|KG)')}")
print(f"  of which the number has a $ (money): {rows(r'\$\s?\d{1,3}(?: \d{3})+')}")
print(f"rows with leading-dot decimal: {rows(r'(?<![\d$])\.\d')}")
print(f"rows with dot used as thousands in a weight (e.g. 33.744 LBS): {rows(r'\b\d{1,3}\.\d{3}\s*LBS')}")
print(f"rows with trailing-dot amount ($20.): {rows(r'\$\d+\.(?!\d)')}")
print(f"rows with a minus sign directly before a number: {rows(r'(?<![\w])-\s?\$?\s?\d')}")
print(f"  of which minus is used as a separator after a charge name ('FEE - $20'): {rows(r'[A-Z] - \$?\s?\d')}")
print(f"rows with dates: {int(t.map(lambda s: bool(DATE_RE.search(s))).sum())}")
print(f"  ISO dates (2022-03-14): {rows(r'\d{4}-\d{2}-\d{2}')}; M/D/YYYY: {rows(r'\b\d{1,2}/\d{1,2}/\d{4}')}; M/D/YY: {rows(r'\b\d{1,2}/\d{1,2}/\d{2}\b(?!/)')}; M/D without year: {rows(r'(?<![/\d])\d{1,2}/\d{1,2}(?![/\d])')}")
print(f"rows with times: {int(t.map(lambda s: bool(TIME_RE.search(s))).sum())}; with AM/PM: {rows(r'\d:\d{2}(?::\d{2})?\s?[AP]M')}")
print(f"rows with percent: {rows(r'\d%')}")
print(f"rows with weight unit (LBS/KG): {rows(r'\d\s*(?:LBS|KG)\b')}; mixing KG and a bare number: {rows(r'KG NOT \d')}")
print(f"rows with quantity x rate (DAYS @/AT $): {rows(r'DAY(?:S|\(S\))?(?: DWELL)?\s*(?:@|AT)\s*\$?\s?\d')}")
print(f"rows with long ID-like numbers (>=7 digits, no $): {rows(r'(?<![\d$])\d{7,}')}")
print(f"rows with ZIP code: {rows(r'ZIP \d{5}')}")
print(f"rows with '=' arithmetic: {rows(r'=')}")
print(f"rows with '+' arithmetic: {rows(r'\+')}")
