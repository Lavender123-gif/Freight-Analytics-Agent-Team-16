"""Run steps 0-2, 5.5 and 6 on the whole dev split, without step 3 (no LLM), and count everything.

Run: sh scratch/prototype/run.sh run_dev.py
Prints aggregates only. Row-level outputs (records.jsonl, events.jsonl, export.xlsx) go to the git-ignored
data/interim/prototype/.

Counting unit: dispute events after collapsing export repeats (908). Rows (953) are shown alongside.
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from itertools import combinations
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUT_DIR, RULES  # noqa: E402
from gate import collapse, load_rows  # noqa: E402
from history import HistEntry, approx_money  # noqa: E402
from pipeline import process  # noqa: E402
from schemas import Event  # noqa: E402

TOL = Decimal("0.005")

rows = load_rows()
ev = collapse(rows).sort_values(["SHIPMENT_GID", "ts", "Invoice Amount"]).reset_index(drop=True)
N_EV, N_ROWS = len(ev), len(rows)
n_rows_of = {r.record_id: len(r.source_rows) for r in ev.itertuples()}

records = []
by_ship: dict[str, list[HistEntry]] = defaultdict(list)
for _, r in ev.iterrows():
    earlier = list(by_ship[r.SHIPMENT_GID])
    rec, _ = process(r, earlier)
    records.append(rec)
    by_ship[r.SHIPMENT_GID].append(HistEntry(rec.source.record_id, r.ts, rec.source.delta, rec.text.redacted))


def pct(k: int, n: int = N_EV) -> str:
    return f"{k} ({k / n:.1%})"


# ---------------------------------------------------------------- 1. diagnostics per code
print(f"events {N_EV}, rows {N_ROWS}, shipments {ev.SHIPMENT_GID.nunique()}")
code_rec: dict[str, set] = defaultdict(set)
code_n: Counter = Counter()
for rec in records:
    for d in rec.diagnostics:
        code_n[d.code] += 1
        code_rec[d.code].add(rec.source.record_id)
print("\n1. code-determinable diagnostics (step 1, 2, 5.5 pre-LLM): code | diagnostics | events (share of 908) | rows")
for code in sorted(code_rec):
    ids = code_rec[code]
    print(f"   {code:36s} {code_n[code]:5d} | {pct(len(ids)):>13s} | {sum(n_rows_of[i] for i in ids):4d}")
CODE_ONLY = [c for c in RULES["flags"] if c.startswith(("REC.INPUT", "REC.TEXT", "NUM.PARSE", "HIST."))
             or c in ("REC.FIELD.DELTA_ZERO", "REC.FIELD.DELTA_NEGATIVE", "REC.FIELD.CROSS_BORDER")]
print("   code-determinable codes that never fired:",
      sorted(c for c in CODE_ONLY if c not in code_rec and c != "HIST.REPEAT.SAME_AMOUNT_NEW_CODES"))

# ---------------------------------------------------------------- 2. disposition (code-only part)
disp = Counter(r.disposition.outcome for r in records)
print("\n2. disposition from code-only flags:", {k: pct(v) for k, v in disp.items()},
      "| rows:", {k: sum(len(r.source.source_rows) for r in records if r.disposition.outcome == k) for k in disp})
reasons = Counter(x for r in records if r.disposition.outcome == "HUMAN_REVIEW" for x in r.disposition.reasons)
print("   HUMAN_REVIEW reasons (a record can have several):", dict(reasons.most_common()))
only = Counter(tuple(r.disposition.reasons) for r in records if r.disposition.outcome == "HUMAN_REVIEW")
print("   HUMAN_REVIEW reason sets:", dict(only.most_common(12)))
print("   AUTO_REJECT reasons:", Counter(tuple(r.disposition.reasons) for r in records if r.disposition.outcome == "AUTO_REJECT"))
exempt = [r for r in records if {"REC.TEXT.EMPTY", "REC.TEXT.NUMBERS_ONLY"} & {f.code for f in r.flags} and r.disposition.outcome != "AUTO_REJECT"]
print(f"   auto-reject candidates exempted by an earlier explained record: {len(exempt)}")
na = [r for r in records if r.disposition.outcome == "AUTO_REJECT"]
print("   auto-rejected events whose shipment has a LATER event with the same Delta and text with letters:",
      sum(any(o.ts > r.source.event_date.replace(tzinfo=None) and abs(o.delta - r.source.delta) <= TOL and re.search("[A-Z]{3,}", o.text)
              for o in by_ship[r.source.shipment_id]) for r in na), "of", len(na))

# ---------------------------------------------------------------- 3. pre-LLM proxy for what steps 4-5 will find
def stated_totals(rec) -> list[Decimal]:
    t = rec.text.redacted
    money_ids = {i for i, _ in approx_money(rec.parse)}
    return [n.value for n in rec.parse.numbers if n.id in money_ids and re.search(r"=\s*$", t[: n.span[0]])]


def proxy(rec) -> str:
    d = abs(rec.source.delta)
    if rec.source.delta == 0:
        return "0 Delta = 0: no anchor (already escalated by REC.FIELD.DELTA_ZERO)"
    money = [v for _, v in approx_money(rec.parse)]
    tots = stated_totals(rec)
    if tots and abs(sum(money) - d) <= TOL and all(abs(t - d) > TOL for t in tots):
        return "C Delta = items + stated total: CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE expected (alone)"
    non_total = [v for v in money if v not in tots]
    if abs(sum(non_total) - d) <= TOL or (tots and any(abs(t - d) <= TOL for t in tots)):
        return "A Delta = sum of the money candidates: reconciles if the model counts them all"
    allv = [n.value for n in rec.parse.numbers]
    for k in range(1, min(len(allv), 5) + 1):
        for c in combinations(allv, k):
            if abs(sum(c) - d) <= TOL:
                return "B Delta = a subset of the numbers: reconciles only if the model leaves some numbers out"
    return "D no subset of the numbers equals Delta: SUM_MISMATCH expected -> RUN.SUBMIT.FAILED (alone)"


would_run = [r for r in records if r.disposition.outcome != "AUTO_REJECT"]
px = Counter(proxy(r) for r in would_run)
print(f"\n3. pre-LLM proxy for reconciliation, over the {len(would_run)} events that would reach step 3:")
for k in sorted(px):
    print(f"   {k:100s} {pct(px[k], len(would_run))}")
trusted = [r for r in records if r.disposition.outcome == "SPLIT_TRUSTED"]
pt = Counter(proxy(r)[0] for r in trusted)
print(f"   among the {len(trusted)} code-only SPLIT_TRUSTED events: {dict(pt)}")
# B: does the subset leave out a '$' amount? (then NUM.JUDGMENT.DOLLAR_EXCLUDED is likely unless the excluded $ is history)
def b_leaves_dollar(rec) -> bool:
    d = abs(rec.source.delta)
    dollars = [n.value for n in rec.parse.numbers if n.has_dollar]
    return bool(dollars) and abs(sum(dollars) - d) > TOL
bset = [r for r in would_run if proxy(r).startswith("B")]
print(f"   B events where reaching Delta means leaving out a '$' amount: {sum(b_leaves_dollar(r) for r in bset)} of {len(bset)}")

# ---------------------------------------------------------------- 4. LLM-dependent flags: rough expectation from analysis regexes
PT = re.compile(r"\bPUR?CH?A?R?H?SE?D?\b")
AUTH = re.compile(r"NOTIFIED|APPROVED BY|AS PER .*(?:OF|FROM) PPG|EMAILED|NOTIFICATION|PER LIST|APPROVAL|LIST FROM PPG")
RATE = re.compile(r"PER CONTRACT|CONTRACT RATE|SHOULD APPLY|RATED AS|\bRA \d|FACTOR|RATE APPROVAL|NOT IN RATE|INCORRECT BASE|MIN FEE|BOL WEIGHT|TERMS AND CONDITIONS")
COMBO = re.compile(r"\b(?:AND|&)\b")
est = {
    "ITEM.CODE.PENDING_MEANING (purchase(d) transportation wording)": sum(bool(PT.search(r.text.redacted)) for r in records),
    "ITEM.BASIS.PPG_CLAIMED (PPG notified/approved/list wording)": sum(bool(AUTH.search(r.text.redacted)) for r in records),
    "ITEM.BASIS.CONTRACT_CLAIMED or RATE_CORRECTION (rate/contract wording)": sum(bool(RATE.search(r.text.redacted)) for r in records),
    "ITEM.CODE.COMBINED candidates (one $ amount, 'AND'/'&' between names)": sum(
        len([n for n in r.parse.numbers if n.has_dollar]) == 1 and bool(COMBO.search(r.text.redacted)) and "TERMS AND" not in r.text.redacted
        for r in records),
}
print("\n4. [estimate] LLM-dependent flags, approximated with the phase-1 analysis regexes (not pipeline rules):")
for k, v in est.items():
    print(f"   {k:75s} {pct(v)}")

# ---------------------------------------------------------------- 5. write row-level outputs (git-ignored)
OUT_DIR.mkdir(parents=True, exist_ok=True)
with open(OUT_DIR / "records.jsonl", "w") as f:
    for r in records:
        f.write(r.model_dump_json() + "\n")
with open(OUT_DIR / "events.jsonl", "w") as f:
    k = 0
    for r in records:
        for typ, payload in [("ingested", {"source_rows": r.source.source_rows})] + \
                [("flag", fl.model_dump(mode="json")) for fl in r.flags] + [("disposition", r.disposition.model_dump(mode="json"))]:
            k += 1
            f.write(Event(event_id=f"e{k}", record_id=r.source.record_id, ts=r.diagnostics[0].created_at if r.diagnostics else r.source.event_date,
                          actor="system", type=typ, payload=payload).model_dump_json() + "\n")
src = rows.set_index("row")
sheet1 = pd.DataFrame([{
    "record_id": r.source.record_id, "outcome": r.disposition.outcome, "reasons": "; ".join(r.disposition.reasons),
    "flags": "; ".join(f.code for f in r.flags), "text_redacted": r.text.redacted, "delta": float(r.source.delta),
    "n_rows": len(r.source.source_rows),
    # Dispute Status joined back only here, at export, by record_id -> first source row
    "Dispute Status": src.loc[r.source.source_rows[0], "Dispute Status"]} for r in records])
sheet2 = pd.DataFrame([{"record_id": r.source.record_id, "code": f.code, "severity": f.severity.value, "role": f.escalation_role,
                        "locations": ", ".join(f.locations)} for r in records for f in r.flags])
with pd.ExcelWriter(OUT_DIR / "export.xlsx") as w:
    sheet1.to_excel(w, sheet_name="records", index=False)
    sheet2.to_excel(w, sheet_name="flags", index=False)
print(f"\nwrote {len(records)} records, events log and export.xlsx to {OUT_DIR.relative_to(OUT_DIR.parents[2])}")
