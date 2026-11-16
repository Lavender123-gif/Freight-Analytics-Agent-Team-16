"""Task 15 section 7: for each candidate rule, how many current FNs it would catch and how many records that are now
passed it would newly send (possible extra FP). Query only on stored readings; nothing in the system changes.
Usage: uv run python scratch/eval/t15_proposals.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "autorun")]
import compare_variants as cv  # noqa: E402
import confusion as C  # noqa: E402

LEET = str.maketrans("013457@$", "OIEASTAS")
VERBS = ["OVERRIDE", "DISREGARD", "BYPASS", "IGNORE", "REPLACE", "SKIP"]
OBJECTS = ["CHECK", "CHECKS", "RULE", "RULES", "REVIEW", "POLICY", "CLAIM", "INSTRUCTIONS", "VALIDATION"]


def lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFKC", text).upper().translate(LEET)
    raw = re.findall(r"[A-Z]+", t)
    out = []
    for i, w in enumerate(raw):          # also try joining a token with the next (split words: 'BYPA SS', 'POL ICY')
        out.append(w)
        if i + 1 < len(raw):
            out.append(w + raw[i + 1])
    return out


def near(w: str, vocab: list[str]) -> bool:
    return any(lev(w, v) <= (1 if len(v) <= 5 else 2) for v in vocab if abs(len(w) - len(v)) <= 2)


RAW: dict[str, str] = {}


def p1_injection(e: dict) -> bool:
    """Runs on the text before redaction, like the existing injection check (redaction masks misspelled words)."""
    ts = tokens(RAW.get(e["record_id"]) or e["facts"].get("text_redacted") or "")
    vs = [i for i, w in enumerate(ts) if len(w) >= 4 and near(w, VERBS)]
    return any(any(len(w) >= 4 and near(w, OBJECTS) for w in ts[i + 1:i + 7]) for i in vs)


def counted_and_excluded(e: dict) -> tuple[Decimal, int, int]:
    f = e["facts"]
    if not f.get("reading"):
        return Decimal(0), 0, 0
    dollars = {n["id"] for n in f["number_table"]["numbers"] if n["has_dollar"]}
    cnt = cv.counted(f["reading"], f["number_table"])
    excl = [j for j in f["reading"]["numbers"] if j["status"] in ("BILLED", "PAID", "DEDUCTED") and j["kind"] in ("CHARGE_AMOUNT", "UNSPECIFIED_AMOUNT")]
    return sum((a for a, _ in cnt.values()), Decimal(0)), len(cnt), len(excl)


def p2_history_only(e: dict) -> bool:
    """Every money amount is read as history and nothing is counted."""
    s, n_cnt, n_excl = counted_and_excluded(e)
    return n_cnt == 0 and n_excl >= 1


def p4_combined(e: dict) -> bool:
    return any(f["code"] == "ITEM.CODE.COMBINED" for f in e["judgment"]["flags"])


def p5_leading_dot_counted(e: dict) -> bool:
    f = e["facts"]
    if not f.get("reading"):
        return False
    ld = {n["id"] for n in f["number_table"]["numbers"] if n["leading_dot"]}
    return bool(ld & set(cv.counted(f["reading"], f["number_table"])))


def p3_echo_of_history(ex: dict, ships_expl: dict) -> set[str]:
    """In one shipment, a counted amount equal to (or 1.03-1.07x) an amount an earlier explanation read as history."""
    hits = set()
    for key, es in ships_expl.items():
        es = sorted(es, key=lambda e: (e["facts"]["source"]["event_date"] or "", min(s["row_number"] for s in e["facts"]["source_rows"])))
        hist = []
        for e in es:
            f = e["facts"]
            if f.get("reading"):
                vals = {n["id"]: Decimal(n["value"]) for n in f["number_table"]["numbers"]}
                for a, _ in cv.counted(f["reading"], f["number_table"]).values():
                    if any(h > 0 and (a == h or Decimal("1.03") <= a / h <= Decimal("1.07")) for h in hist):
                        hits.add(e["record_id"])
                hist += [vals[j["id"]] for j in f["reading"]["numbers"] if j["status"] in ("BILLED", "PAID", "DEDUCTED") and j["id"] in vals]
    return hits


def main() -> None:
    out = {}
    for name, run, rows_file, key in (("dev", C.DEV_RUN, "rows_annotations_after.json", "explanation"),
                                      ("mock", C.MOCK_RUN, "rows_mock_after.json", "mock_id")):
        ex, ships = C.system_view(run)
        from freight_lineitems.textprep import normalize
        recs = cv.records_for(next(iter(ex.values()))["facts"]["source"]["source"])
        RAW.update({rid: normalize(recs[rid].text_raw) for rid in ex})
        by_ship = {}
        for e in ex.values():
            by_ship.setdefault(e["facts"]["source"]["shipment_key"], []).append(e)
        echo = p3_echo_of_history(ex, by_ship)
        passed = {rid for rid, e in ex.items() if not C.sent(e, ships[e["facts"]["source"]["shipment_key"]])}
        rules = {"P1_obfuscated_injection": lambda e: p1_injection(e), "P2_history_only_claim": p2_history_only,
                 "P3_echo_of_earlier_history_amount": lambda e: e["record_id"] in echo, "P4_combined_amount_to_person": p4_combined,
                 "P5_leading_dot_amount_counted": p5_leading_dot_counted}
        rows = json.loads((ROOT / "data" / "interim" / "eval" / "t15" / rows_file).read_text())
        if name == "mock":
            gt = {json.loads(l)["mock_id"]: json.loads(l) for l in (ROOT / "data" / "external" / "mock_public_r3" / "ground_truth_open.jsonl").open()}
            row_to = {s["record_id"]: e["record_id"] for e in ex.values() for s in e["facts"]["source_rows"]}
            expl_of = {r["mock_id"]: row_to["mock3#" + gt[r["mock_id"]]["row_ids"][0]] for r in rows}
        else:
            expl_of = {r["record_id"]: r["explanation"] for r in rows}
        res = {}
        for rn, fn in rules.items():
            fires = {rid for rid in passed if fn(ex[rid])}
            caught = sum(1 for r in rows if r["positive"] and not r["sent"] and expl_of[r[key] if key == "mock_id" else r["record_id"]] in fires)
            new_fp = sum(1 for r in rows if not r["positive"] and not r["sent"] and expl_of[r[key] if key == "mock_id" else r["record_id"]] in fires)
            res[rn] = {"fn_caught_in_matrix": caught, "new_fp_in_matrix": new_fp, "now_passed_explanations_that_would_be_sent": len(fires),
                       "of_passed": len(passed)}
        out[name] = res
    (ROOT / "data" / "interim" / "eval" / "t15" / "proposals.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
