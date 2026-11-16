"""Task 17 section 4: recompute on stored readings with the four fixes, each alone and all together. No model call.

base  = the system before task 17: stored flags, copy flags and roll-up recomputed, without the task-17 flags.
fixes = 1 CLAIM.NOTHING_COUNTED, 2 SHIP.ROLLUP.ECHO_OF_HISTORY_AMOUNT, 3 ITEM.AMOUNT.LEADING_DOT_COUNTED,
        4 REC.TEXT.INJECTION_SUSPECT from the fuzzy layer on the original text. All four are attention-level, so a fix
        can only move a passed record to 'sent'.
Truth: mock round 3 under reading A (mock answers) and B (our standard: fee names outside the code table without
'inside placement' (D-79); the 'earlier claim / prior charge' wording needs a person (D-80)); annotations with the
task-17 corrections (D-77, D-78). Prints aggregates; per-record rows in data/interim/eval/t17/ (git-ignored).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "autorun")]
import compare_variants as cv  # noqa: E402
import confusion as C  # noqa: E402

from freight_lineitems import duplicates  # noqa: E402
from freight_lineitems.reading_checks import reading_diagnostics  # noqa: E402
from freight_lineitems.records import MOCK_R3_DIR  # noqa: E402
from freight_lineitems.textprep import fuzzy_injection_hits, normalize  # noqa: E402

OUT = ROOT / "data" / "interim" / "eval" / "t17"
FIXES = {1: "CLAIM.NOTHING_COUNTED", 2: "SHIP.ROLLUP.ECHO_OF_HISTORY_AMOUNT", 3: "ITEM.AMOUNT.LEADING_DOT_COUNTED", 4: "fuzzy_injection"}
F16 = yaml.safe_load((ROOT / "scratch" / "eval" / "t16_features.yaml").read_text())
NOT_IN_TAX = [n for n in F16["mock_fee_names"]["not_in_taxonomy"] if n != "inside placement"]      # D-79


def view(run: str) -> dict:
    """explanation id -> {base_sent, fires (set of fix numbers), shipment}."""
    ex, ships = C.system_view(run)
    recs = cv.records_for(next(iter(ex.values()))["facts"]["source"]["source"])
    out = {}
    for rid, e in ex.items():
        ship = ships[e["facts"]["source"]["shipment_key"]]
        ship_flags = {f["code"] for f in ship["flags"] if f["severity"] == "attention"}
        base_ship = ship_flags - {FIXES[2]}
        base_sent = e["judgment"]["recommendation"] != "PASSED_CHECKS" or bool(base_ship)
        fires = set()
        codes = {d.code for d in reading_diagnostics(e["facts"]["number_table"], e["facts"].get("reading"))}
        if FIXES[1] in codes:
            fires.add(1)
        if FIXES[3] in codes:
            fires.add(3)
        if FIXES[2] in ship_flags:
            fires.add(2)
        if fuzzy_injection_hits(normalize(recs[rid].text_raw)):
            fires.add(4)
        out[rid] = {"base_sent": base_sent, "fires": fires, "shipment": e["facts"]["source"]["shipment_key"],
                    "source_rows": [s["record_id"] for s in e["facts"]["source_rows"]]}
    return out


def sent(v: dict, active: set[int]) -> bool:
    return v["base_sent"] or bool(v["fires"] & active)


def matrix(rows: list[dict], key: str, active: set[int]) -> dict:
    c = Counter(("TP" if sent(r["v"], active) else "FN") if r[key] else ("FP" if sent(r["v"], active) else "TN") for r in rows)
    m = C.rates(c["TP"], c["FP"], c["FN"], c["TN"])
    return {k: (m[k]["value"], m[k]["ci95"]) if isinstance(m[k], dict) else m[k] for k in ("TP", "FP", "FN", "TN", "recall", "FOR", "precision")}


def per_fix(rows: list[dict], key: str) -> dict:
    out = {}
    for k in FIXES:
        caught = sum(1 for r in rows if r[key] and not r["v"]["base_sent"] and k in r["v"]["fires"])
        added_fp = sum(1 for r in rows if not r[key] and not r["v"]["base_sent"] and k in r["v"]["fires"])
        out[k] = {"fn_caught": caught, "fp_added": added_fp}
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    # ---------------- dev full
    dv = view(C.DEV_RUN)
    dev = {"explanations": len(dv), "base_sent": sum(v["base_sent"] for v in dv.values()),
           "base_sent_shipments": len({v["shipment"] for v in dv.values() if v["base_sent"]})}
    for k in list(FIXES) + ["all"]:
        act = set(FIXES) if k == "all" else {k}
        new = [v for v in dv.values() if not v["base_sent"] and v["fires"] & act]
        dev[f"new_sent_fix_{k}"] = {"explanations": len(new), "shipments": len({v["shipment"] for v in new})}
    res["dev"] = dev
    # ---------------- mock round 3
    mv = view(C.MOCK_RUN)
    by_row = {r: (eid, v) for eid, v in mv.items() for r in v["source_rows"]}
    gt = [json.loads(x) for x in (MOCK_R3_DIR / "ground_truth_open.jsonl").open()]
    recs = {json.loads(x)["row_id"]: json.loads(x) for x in (MOCK_R3_DIR / "mock_records_open.jsonl").open()}
    old = {r["mock_id"]: r for r in json.loads((ROOT / "data" / "interim" / "eval" / "t16" / "mock_rows.json").read_text())}
    mrows = []
    for g in gt:
        if not g.get("active", True):
            continue
        eid, v = by_row["mock3#" + g["row_ids"][0]]
        o = old[g["mock_id"]]
        text = (recs[g["row_ids"][0]]["text"] or "").upper()
        fees = set(o["fees"])
        reasons = []
        if any(any(p in NOT_IN_TAX for p in fn.split(" and ")) for fn in fees):
            reasons.append("fee_not_in_taxonomy")
        if fees & set(F16["mock_fee_names"]["no_charge_named"]):
            reasons.append("no_charge_named")
        if "copy_same_or_empty_pk" in o["b_reasons"]:
            reasons.append("copy_same_or_empty_pk")
        p40 = bool(re.search(r"EARLIER CLAIM", text)) and bool(re.search(r"PRIOR", text))
        if p40:
            reasons.append("p40_earlier_claim_prior")
        exp_a = g["expected_recommendation"] != "解析通过检查"
        exp_b = False if (g["failure_mode"] == "understanding_one_amount_two_fees" and not reasons) else (exp_a or bool(reasons))
        # under B, P-40 wording is 'unclear': the claim total is not judged on it
        wrong_b = o["claim_wrong"] and not p40
        mrows.append({"mock_id": g["mock_id"], "failure_mode": g["failure_mode"], "A": o["positive_A"], "B": exp_b or wrong_b,
                      "v": v, "reasons": reasons})
    res["mock"] = {"A_before": matrix(mrows, "A", set()), "A_after": matrix(mrows, "A", set(FIXES)),
                   "B_before": matrix(mrows, "B", set()), "B_after": matrix(mrows, "B", set(FIXES)),
                   "per_fix_A": per_fix(mrows, "A"), "per_fix_B": per_fix(mrows, "B")}
    # ---------------- annotations (task-17 corrections)
    corr = json.loads((ROOT / "data" / "interim" / "annotation" / "deliverable" / "t17_corrections.json").read_text())
    arows = []
    for r in C.annotation_rows(corrections=corr):
        arows.append(r | {"v": dv[r["explanation"]]})
    res["annotations"] = {"before": matrix(arows, "positive", set()), "after": matrix(arows, "positive", set(FIXES)),
                          "per_fix": per_fix(arows, "positive"),
                          "fn_after": [{"gates": r["gates"], "types": r["types"]} for r in arows if r["positive"] and not sent(r["v"], set(FIXES))]}
    for name, rows in (("mock_rows", mrows), ("annotation_rows", arows)):
        (OUT / f"{name}.json").write_text(json.dumps([{k: (sorted(v["fires"]) if k == "v" else v) for k, v in r.items()} for r in rows],
                                                    indent=1, ensure_ascii=False, default=str))
    (OUT / "summary.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
