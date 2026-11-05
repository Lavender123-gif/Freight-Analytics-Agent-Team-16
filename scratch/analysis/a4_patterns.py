"""Semantic patterns in the free text (aggregates only).

These regexes are analysis instruments, not pipeline rules. Each was checked
against a full reading of all 528 distinct non-empty dev texts; known gaps are
noted next to the pattern. Counts are rows (953) unless stated otherwise.
"""

import re
from datetime import datetime

from common import EPS, ROOT, load_dev, number_tokens

df = load_dev()
t = df.text_norm
n = len(df)


def has(p: str) -> "pd.Series":  # noqa: F821
    return t.str.contains(re.sub(r"\((?!\?)", "(?:", p), regex=True)


def show(label: str, mask) -> None:
    print(f"{label}: {int(mask.sum())} rows ({mask.mean():.1%}), {t[mask].nunique()} distinct texts")


# --- Charge-name variation -------------------------------------------------
PT = r"\bPUR?CH?A?R?H?SE?D?\b"  # PURCHASE / PURCHASED / PURCAHSE / PURCHARSED
show("purchase(d)-transportation family", has(PT))
print("  by carrier:", df[has(PT)].carrier.value_counts().to_dict())
phr = t.str.extractall(r"(PUR?CH?A?R?H?SE?D?(?:\s+(?:TRANSPORTATION|TRANSP|DELIVERY))?(?:\s+(?:SURCHARGE|SURCHARG|FEE))?)")[0]
print(f"  distinct surface forms of the charge name: {phr.nunique()} -> {sorted(phr.unique())}")
tg = t.str.extractall(r"\b(TAI\w*G\w*TE)\b")[0]
print(f"  distinct spellings of tailgate: {sorted(tg.unique())}")
TYPOS = r"TAILAGTE|TAILAGATE|PURCAHSE|PURCHARSED|FEUL|REDILVERY|^NSIDE|\bALANCE|ORGIN|\bHAMAT\b|WAHT|ENTERD|OWEING|INSIDE DELIVER CHARGE"
show("rows with at least one misspelling (list in script)", has(TYPOS))

# --- Tax -------------------------------------------------------------------
TAX = r"\b(?:GST|HST|PST|QST|TAX)\b"
show("mentions tax", has(TAX))
tax_amt = has(r"(?:GST|HST|PST|QST|TAX)\W{0,4}\$?\s?\d")
show("  tax with its own amount", tax_amt)
show("  tax named without an amount (e.g. '+ HST')", has(TAX) & ~tax_amt & ~has(r"TAX WAS PAID|MUST PAY TAX"))
show("  tax as the subject of the dispute (paid / must pay)", has(r"TAX WAS PAID|MUST PAY TAX"))
print("  tax keyword x destination province:")
for kw in ["GST", "HST", "TAX"]:
    m = has(rf"\b{kw}\b")
    print(f"    {kw}: {df[m]['Destination State'].value_counts().to_dict()}")
# explicit base + tax pairs: check implied rate
pairs = []
for s, dest in zip(t, df["Destination State"]):
    m = re.search(r"\$?(\d+\.\d{2})\s*\+\s*(?:GST|HST)\s*\$(\d+\.\d{2})", s)
    if m:
        base, tax = float(m.group(1)), float(m.group(2))
        pairs.append((round(tax / base, 4), dest))
    m = re.search(r"\$(\d+\.\d{2}) PLUS TAX \$(\d+\.\d{2})", s)
    if m:
        pairs.append((round(float(m.group(2)) / float(m.group(1)), 4), dest))
print(f"  explicit base+tax pairs: {len(pairs)}; implied rates and destination: {sorted(set(pairs))}")
# implicit tax: Delta not stated but the text's total is base*(1+r)
eqs = []
for s in t:
    m = re.search(r"\$(\d+\.\d{2}) (?:DETENTION TIME )?AND \$(\d+\.\d{2}) .*?\+ HST = \$(\d+\.\d{2})", s)
    if m:
        b = float(m.group(1)) + float(m.group(2))
        eqs.append(round(float(m.group(3)) / b, 4))
print(f"  '+ HST = total' without a tax amount, implied rate: {eqs}")
# itemised 'FEUL $x TAX $y' rows: tax / (sum of amounts before TAX)
for s, dest in zip(t, df["Destination State"]):
    m = re.search(r"^(.*?)TAX \$(\d+\.\d{2})", s)
    if m and "FEUL" in s:
        pre = [x["value"] for x in number_tokens(m.group(1)) if x["has_dollar"]]
        print(f"  itemised tax row, dest {dest}: tax / sum(before) = {float(m.group(2)) / sum(pre):.4f}")

# --- Stated arithmetic ------------------------------------------------------
ok = bad = 0
for s in t:
    for m in re.finditer(r"((?:\$\d+(?:\.\d+)?[A-Z \.]*?(?:\+|AND)\s*(?:[A-Z ]*?)?)+\$\d+(?:\.\d+)?)\s*=\s*\$(\d+(?:\.\d+)?)", s):
        nums = [float(x) for x in re.findall(r"\$(\d+(?:\.\d+)?)", m.group(1))]
        if abs(sum(nums) - float(m.group(2))) <= EPS:
            ok += 1
        else:
            bad += 1
print(f"stated sums 'a + b = c' found: {ok + bad}; consistent {ok}; inconsistent {bad}")

# quantity x rate
qr_ok = qr_rate_is_total = qr_other = 0
for s in t:
    m = re.search(r"(\d+)\s*(?:DWELL\s+)?DAY(?:S|\(S\))?(?:\s+DWELL)?\s*(?:@|AT)\s*\$?\s?(\d+(?:\.\d+)?)", s)
    if not m:
        continue
    q, r = int(m.group(1)), float(m.group(2))
    vals = [x["value"] for x in number_tokens(s) if x["has_dollar"]]
    total = vals[0] if vals else None
    if total is not None and abs(q * r - total) <= EPS and q > 1:
        qr_ok += 1
    elif total is not None and abs(r - total) <= EPS and q > 1:
        qr_rate_is_total += 1
    else:
        qr_other += 1
print(f"quantity x rate rows: q>1 and q*rate = first $ amount: {qr_ok}; q>1 and '@ $X' is already the total: {qr_rate_is_total}; q=1 or other: {qr_other}")

# Detention time windows: duration vs amount
win = []
for s, d in zip(t, df.Delta):
    m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})-(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", s)
    f = "%Y-%m-%d %H:%M:%S"
    if not m:
        m = re.search(r"(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [AP]M)-(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [AP]M)", s)
        f = "%m/%d/%Y %I:%M:%S %p"
    if m and "DETENTION" in s:
        h = (datetime.strptime(m.group(2), f) - datetime.strptime(m.group(1), f)).total_seconds() / 3600
        win.append((("EQUIP" if "EQUIPMENT" in s else "DRIVER"), round(h, 2), d))
drv = sorted(w for w in win if w[0] == "DRIVER")
print(f"detention rows with a start-end window: {len(win)}; driver: {len(drv)}")
print("  driver (hours, amount):", [(w[1], w[2]) for w in drv])
print("  equipment (hours, amount):", [(w[1], w[2]) for w in win if w[0] == "EQUIP"])

# --- Payment history and balance semantics ----------------------------------
PAY = r"SHORT PAID|\bUNPAID\b|STILL OWE|\bOWE\b|OVERPAYMENT|ADJUSTED OFF|DID NOT PAY|TAX WAS PAID|\bPAID\b|AMOUNT APPROVED"
show("payment-history language (paid / unpaid / owe / overpayment / approved amount)", has(PAY))
show("'BALANCE DUE' or 'OWING'", has(r"BALANCE DUE|ALANCE DUE|OWEING"))
bal_multi = has(r"BALANCE DUE|ALANCE DUE") & t.map(lambda s: len([x for x in number_tokens(s) if x["has_dollar"]]) >= 2)
rel = {"Delta = balance (last)": 0, "Delta = sum incl. balance": 0, "other": 0}
for s, d in zip(t[bal_multi], df.Delta[bal_multi]):
    v = [x["value"] for x in number_tokens(s) if x["has_dollar"]] or [x["value"] for x in number_tokens(s)]
    if abs(v[-1] - d) <= EPS:
        rel["Delta = balance (last)"] += 1
    elif abs(sum(v) - d) <= EPS:
        rel["Delta = sum incl. balance"] += 1
    else:
        rel["other"] += 1
print(f"  'BALANCE DUE' with >=2 $ amounts: {int(bal_multi.sum())} rows -> {rel}")

# --- One amount, several charges -------------------------------------------
one_amt = t.map(lambda s: len([x for x in number_tokens(s) if x["has_dollar"]]) == 1)
combo = one_amt & has(r"\b(?:AND|&)\b") & ~has(r"TERMS AND CONDITIONS|\$\d+(?:\.\d+)? AND")
show("one $ amount covering two named charges ('X AND Y ... $35')", combo)
print("   texts:", sorted(t[combo].unique()))

# --- Amounts with no charge name --------------------------------------------
bare = has(r"^\$?\s?[\d .]+$")
generic = has(r"^(?:SHORT PAID|DISPUTE - UNPAID|TOTAL|MUST PAY TAX|\$[\d.]+ - PR SHIPMENT|[\d.]+ BALANCE DUE PER CONTRACT|\$[\d.]+ BALANCE DUE (?:PER|FOR) CONTRACT RATES)")
show("text is only a number", bare)
show("text names no charge (only payment/total words)", generic & ~bare)
show("text has no number at all (empty or truncated)", t.map(lambda s: not number_tokens(s)))
show("FSC-rate-only rows ('.73 FSC', Delta 0)", has(r"^\.\d+( FSC)?$"))

# --- Rating / contract arguments -------------------------------------------
RATE = r"PER CONTRACT|CONTRACT RATE|SHOULD APPLY|RATED AS|\bRA \d|FACTOR|RATE APPROVAL|NOT IN RATE|INCORRECT BASE|MIN FEE|REWEIGH|BOL WEIGHT|TERMS AND CONDITIONS"
show("argues rating / contract / weight rather than a discrete accessorial", has(RATE))
AUTH = r"NOTIFIED|APPROVED BY|AS PER .*(?:OF|FROM) PPG|EMAILED|NOTIFICATION|PER LIST|APPROVAL"
show("cites a PPG person, list, notification or approval as authority", has(AUTH))

# --- Personal data ----------------------------------------------------------
names = [x.strip() for x in (ROOT / "data" / "interim" / "person_tokens.txt").read_text().split() if x.strip()]
name_re = r"\b(?:" + "|".join(names) + r")\b"
show("contains a person's name (token list kept in git-ignored data/interim)", has(name_re))
show("contains an email address", has(r"\S+@\S+"))
show("  of which the name is misspelled relative to the majority form", has(r"\bLOURIE\b"))
print(f"  distinct person-name tokens seen: {len(names)}")

# --- Reason code vs text ----------------------------------------------------
print("\nreason code vs text topic (rows):")
topics = {
    "HAZMAT": r"HAZMAT|HAMAT",
    "DETENTION/DWELL": r"DETENTION|DWELL|DETN|DTN",
    "FSC/FUEL": r"\bFSC\b|FUEL|FEUL",
    "LUMPER/SORTATION": r"LUMPER|SORTATION",
    "BASE/RATE": r"INCORRECT BASE|MIN FEE|PER CONTRACT|RATED AS|\bRA \d|FACTOR",
    "STORAGE/PERDIEM": r"STORAGE|PERDIEM",
}
rc = df["Reason Code"].str.replace("PPGTM.", "", regex=False)
for k, p in topics.items():
    m = has(p)
    print(f"  {k:18s} {int(m.sum()):4d} rows; reason codes: {rc[m].value_counts().to_dict()}")

# --- Template concentration --------------------------------------------------
tmpl = t.str.replace(r"\d", "9", regex=True).str.replace(r"\s+", " ", regex=True)
vc = tmpl.value_counts()
print(f"\ndistinct templates (digits masked): {len(vc)}; top 10 cover {vc.iloc[:10].sum() / n:.1%}; top 30 cover {vc.iloc[:30].sum() / n:.1%}")
print(f"carrier rows in templates used by only one carrier: {sum(df.groupby(tmpl).carrier.nunique() == 1)} of {len(vc)} templates")
