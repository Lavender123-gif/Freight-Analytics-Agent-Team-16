"""Task 15: confusion matrices on 'needs a person' (definitions in docs/deliverables/T15-confusion-matrix/01-preregistration.zh.md).

Truth side: finalised annotations plus the section-2 re-judging (data/interim/annotation/), or the mock round-3 ground
truth. System side: stored readings of the chosen version, with the copy flags and the shipment roll-up recomputed by the
code in the working tree (so a code fix can be replayed without any model call).
Prints aggregates only; per-record rows (with record keys) go to data/interim/eval/t15/ (git-ignored).
Usage: uv run python scratch/eval/confusion.py [--tag before|after]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "annotation"), str(ROOT / "scratch" / "autorun")]
import compare_variants as cv  # noqa: E402
import metrics as M  # noqa: E402
from agreement import derive, number_value  # noqa: E402
from import_annotations import load_long  # noqa: E402

from freight_lineitems import duplicates  # noqa: E402
from freight_lineitems.config import RULES, category  # noqa: E402
from freight_lineitems.disposition import flags_from, recommend  # noqa: E402
from freight_lineitems.records import group_explanations  # noqa: E402
from freight_lineitems.pipeline import finish_batch  # noqa: E402
from freight_lineitems.schemas import Diagnostic  # noqa: E402
from freight_lineitems.textprep import normalize  # noqa: E402

DEV_RUN, MOCK_RUN = "devFullV12-5d09", "mockR3V12-f0d3"
GOLD = ROOT / "data" / "interim" / "annotation"
OUT = ROOT / "data" / "interim" / "eval" / "t15"
TYPES = yaml.safe_load((ROOT / "scratch" / "eval" / "t15_problem_types.yaml").read_text())
SEV = {k: v["severity"] for k, v in RULES["flags"].items()}
TAXWORD = re.compile(r"\b(GST|HST|PST|QST|TAX)\b")


def wilson(k: int, n: int) -> list | None:
    if n == 0:
        return None
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def rates(tp, fp, fn, tn) -> dict:
    n = tp + fp + fn + tn
    def r(k, m):
        return {"value": round(100 * k / m, 1) if m else None, "ci95": wilson(k, m), "k": k, "n": m}
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "recall": r(tp, tp + fn), "precision": r(tp, tp + fp),
            "specificity": r(tn, tn + fp), "FOR": r(fn, fn + tn), "coverage": r(tn + fn, n)}


def system_view(run: str) -> tuple[dict, dict]:
    """Explanations with copy flags and the shipment roll-up recomputed by today's code. Task 20: everything after
    the model goes through pipeline.finish_batch, the function run_batch calls, so the evaluation and production
    compute shipments the same way (the stored copy flags are dropped first; finish_batch adds them again)."""
    ex = cv.explanations(run)
    recs = cv.records_for(ex[0]["facts"]["source"]["source"])
    rows = []
    for e in ex:
        rows += [recs[s["record_id"]] for s in e["facts"]["source_rows"]]
        diags = [Diagnostic(**d) for d in e["judgment"]["diagnostics"] if d["code"] != "SHIP.COPY.SAME_OR_NO_PK"]
        fl = flags_from(diags)
        e["judgment"] = {"flags": fl, **recommend(fl), "diagnostics": [d.model_dump() for d in diags]}
    ex, ships = finish_batch(rows, ex)
    return {e["record_id"]: e for e in ex}, {s["shipment_key"]: s for s in ships}


def send_flags(e: dict, ship: dict) -> set[str]:
    out = {f["code"] for f in e["judgment"]["flags"] if f["severity"] in ("attention", "return")}
    out |= {f["code"] for f in ship["flags"] if f["severity"] == "attention"}
    return out


def sent(e: dict, ship: dict) -> bool:
    return e["judgment"]["recommendation"] != "PASSED_CHECKS" or ship["shipment_flags_recommendation"] != "PASSED_CHECKS"


def all_types() -> dict[str, list[str]]:
    return {k: v["flags"] for grp in ("system_errors", "input_problems") for k, v in TYPES[grp].items()}


def submatrix(rows: list[dict]) -> dict:
    out = {}
    for k, flags in all_types().items():
        fl = set(flags)
        tp = fp = tn = 0
        fn_missed = fn_wrong = 0
        for r in rows:
            has = bool(fl & set(r["send_flags"]))
            if k in r["types"] and r["positive"]:
                if r["sent"] and has:
                    tp += 1
                elif not r["sent"]:
                    fn_missed += 1
                else:
                    fn_wrong += 1
            elif has and r["sent"]:
                fp += 1
            else:
                tn += 1
        m = rates(tp, fp, fn_missed + fn_wrong, tn)
        m["FN_missed"], m["FN_wrong_cause"] = fn_missed, fn_wrong
        out[k] = m
    return out


# ---------------------------------------------------------------------------------------------------- annotations

def annotation_rows(adjusted_rejudge: bool = True, corrections: dict | None = None) -> list[dict]:
    """`corrections` (task 17, D-77/D-78): category corrections, restored records and quantity-1 records, applied on top
    of the finalised gold and the task-15 re-judging."""
    gold = derive(load_long(GOLD / "final" / "final_gold.csv"))
    rej = json.loads((GOLD / "deliverable" / "rejudge.json").read_text())
    if corrections:
        for rid in corrections.get("drop_rejudge", []):
            rej.pop(rid, None)
        def put(rid, nid, claim, cat):
            idx = gold[(gold.record_id == rid) & (gold.number_id == nid)].index
            gold.loc[idx, "claim"] = claim
            gold.loc[idx, "claim_coarse"] = {"COUNTED": "COUNTED", "NOT_TOTAL": "NOT_COUNTED", "NOT_HISTORY": "NOT_COUNTED",
                                             "NOT_REFERENCE": "NOT_COUNTED"}.get(claim, claim)
            gold.loc[idx, "category"] = cat
        for rid, nums in corrections.get("restore", {}).items():
            for nid, v in nums.items():
                put(rid, nid, v["claim"], v["category"])
        for rid, nums in corrections.get("quantity_one", {}).items():
            for nid, v in nums.items():
                put(rid, nid, v["claim"], v["category"])
    for rid, j in rej.items():                               # overrides of section 2
        for nid, o in j["gold_overrides"].items():
            idx = gold[(gold.record_id == rid) & (gold.number_id == nid)].index
            gold.loc[idx, "claim"] = o["claim"]
            gold.loc[idx, "claim_coarse"] = {"COUNTED": "COUNTED", "NOT_REFERENCE": "NOT_COUNTED"}.get(o["claim"], o["claim"])
            gold.loc[idx, "category"] = o["category"]
    if corrections:
        for rid, v in corrections.get("category", {}).items():
            gold.loc[(gold.record_id == rid) & (gold.number_id == v["number_id"]), "category"] = v["category"]
    expl, ships = system_view(DEV_RUN)
    run = M.load_run(cv.replay.find_run(DEV_RUN))
    by_row = {s["record_id"]: e for e in expl.values() for s in e["facts"]["source_rows"]}
    recs = cv.records_for("dev")
    groups = {g[0].record_id: g for g in group_explanations(list(recs.values()))}
    rows = []
    for rid, g in gold.groupby("record_id"):
        e = by_row[rid]
        ship = ships[e["facts"]["source"]["shipment_key"]]
        text = normalize(recs[rid].text_raw)
        view = M.model_view(e) or {}
        gates, types = [], set()
        j = rej.get(rid)
        if j:
            if j["class"] in ("R-NONE",):
                gates.append("G1"); types.add("unclear_wording")
            elif j["class"] == "R-QR":
                gates.append("G2"); types.add("unclear_wording")
            elif j["class"] in ("R-BD", "R-A5"):
                gates.append("G2"); types.add("supersede_same_amount_balance_due")
        counted = g[g.claim_coarse == "COUNTED"]
        if (counted.category == "NO_CHARGE_NAMED").any():
            gates.append("G3"); types.add("empty_numbers_only_unnamed")
        if (counted.category == "OTHER").any():
            gates.append("G4"); types.add("unclear_wording")
        if not text or not re.search(r"[A-Za-z]", text):
            gates.append("G5"); types.add("empty_numbers_only_unnamed")
        if TAXWORD.search(text.upper()) and not (counted.category == "TAX").any():
            gates.append("G6"); types.add("tax_without_amount")
        grp = groups.get(e["record_id"], [recs[rid]])
        pks = [duplicates.normalize_pk(r.pk) if hasattr(duplicates, "normalize_pk") else r.pk for r in grp]
        if len(grp) > 1 and (any(not p for p in pks) or len(set(pks)) < len(pks)):
            gates.append("G7"); types.add("duplicate_export")
        # G8: system misread, against the truth
        hs = Decimal(0); unclear = False
        errs = set()
        for nid, gn in g.groupby("number_id", sort=False):
            h = gn.iloc[0]
            m = view.get(nid) or {"is_money": None, "claim3": "MISSING", "categories": set()}
            if h["claim_coarse"] == "UNCLEAR" or h["claim_coarse"] == "":
                unclear = True
                continue
            v = number_value(nid, h["number_raw"])
            hs += v if h["claim_coarse"] == "COUNTED" else -v if h["claim_coarse"] == "CREDIT" else 0
            h3 = {"NOT_MONEY": "NOT_COUNTED"}.get(h["claim_coarse"], h["claim_coarse"])
            if h["is_money"] and (h["is_money"] == "MONEY") != bool(m["is_money"]):
                errs.add("misread_amount")
            if h3 != m["claim3"]:
                errs.add("misread_amount")
                if h3 in ("COUNTED", "CREDIT") and m["claim3"] not in ("COUNTED", "CREDIT"):
                    errs.add("missed_amount")
                if m["claim3"] in ("COUNTED", "CREDIT") and h3 not in ("COUNTED", "CREDIT"):
                    errs.add("extra_amount")
            if h3 == "COUNTED" and m["claim3"] == "COUNTED" and h["category"] and h["category"] not in m["categories"]:
                errs.add("category_wrong")
        ms = M.signed_sum(e["facts"]["reading"], e["facts"]["number_table"]) if e["facts"]["reading"] else None
        if not unclear and ms != hs:
            errs.add("misread_amount")
        if errs:
            gates.append("G8"); types |= errs
        sf = send_flags(e, ship)
        rows.append({"record_id": rid, "explanation": e["record_id"], "positive": bool(gates), "gates": gates,
                     "types": sorted(types), "sent": sent(e, ship), "send_flags": sorted(sf),
                     "recommendation": e["judgment"]["recommendation"], "ship_rec": ship["shipment_flags_recommendation"],
                     "rejudge": j["class"] if j else None})
    return rows


def main_matrix(rows: list[dict]) -> dict:
    c = Counter(("TP" if r["sent"] else "FN") if r["positive"] else ("FP" if r["sent"] else "TN") for r in rows)
    return rates(c["TP"], c["FP"], c["FN"], c["TN"])


RULE_ALERTS = {f for f in SEV if f.startswith("SHIP.")} | {"ITEM.TAX.NO_AMOUNT"}


def annotation_report() -> tuple[dict, list[dict]]:
    rows = annotation_rows()
    strict = main_matrix(rows)
    maybe = [r for r in rows if not r["positive"] and r["sent"] and r["send_flags"] and set(r["send_flags"]) <= RULE_ALERTS]
    adj = dict(strict)
    adj["FP_maybe_TP_rule_alerts"] = len(maybe)
    adj["FP_other"] = strict["FP"] - len(maybe)
    adj["precision_if_maybe_counted_as_TP"] = rates(strict["TP"] + len(maybe), strict["FP"] - len(maybe), strict["FN"], strict["TN"])["precision"]
    # sensitivity of section 2: the two R-BD records that were unanimous before R-5
    return {"n": len(rows), "strict": strict, "adjusted": adj, "sub": submatrix(rows),
            "fp_by_flag": fp_by_flag(rows), "gates": dict(Counter(gt for r in rows for gt in r["gates"]))}, rows


def fp_by_flag(rows: list[dict]) -> dict:
    c = Counter()
    for r in rows:
        if r["sent"] and not r["positive"]:
            for f in r["send_flags"]:
                c[f] += 1
    trig = Counter(f for r in rows for f in r["send_flags"])
    return {f: {"fp": n, "fires": trig[f]} for f, n in c.most_common()}


# ---------------------------------------------------------------------------------------------------- mock

def mock_rows() -> list[dict]:
    from freight_lineitems.records import MOCK_R3_DIR
    expl, ships = system_view(MOCK_RUN)
    by_row = {s["record_id"]: e for e in expl.values() for s in e["facts"]["source_rows"]}
    mode_type = {m: k for k, v in TYPES["input_problems"].items() for m in v.get("mock_modes", [])}
    rows = []
    for g in (json.loads(x) for x in (MOCK_R3_DIR / "ground_truth_open.jsonl").open()):
        if not g.get("active", True):
            continue
        e = by_row["mock3#" + g["row_ids"][0]]
        ship = ships[e["facts"]["source"]["shipment_key"]]
        truth = Decimal(str(g["claim"]["current_claim_total"]))
        cnt = cv.counted(e["facts"]["reading"], e["facts"]["number_table"]) if e["facts"]["reading"] else {}
        got = sum((a for a, _ in cnt.values()), Decimal(0))
        types = set()
        if mode_type.get(g["failure_mode"]):
            types.add(mode_type[g["failure_mode"]])
        wrong = got != truth
        if wrong:
            types.add("misread_amount")
            tv = Counter(Decimal(str(i["amount"])).copy_abs() for i in g["claim"]["items"] if i.get("is_current_claim"))
            sv = Counter(a.copy_abs() for a, _ in cnt.values())
            if tv - sv:
                types.add("missed_amount")
            if sv - tv:
                types.add("extra_amount")
        positive = g["expected_recommendation"] != "解析通过检查" or wrong
        rows.append({"mock_id": g["mock_id"], "failure_mode": g["failure_mode"], "positive": positive, "types": sorted(types),
                     "claim_wrong": wrong, "expected": g["expected_recommendation"], "sent": sent(e, ship),
                     "send_flags": sorted(send_flags(e, ship)), "recommendation": e["judgment"]["recommendation"]})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="before")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ann, arows = annotation_report()
    mrows = mock_rows()
    mock = {"n": len(mrows), "main": main_matrix(mrows), "sub": submatrix(mrows), "fp_by_flag": fp_by_flag(mrows)}
    res = {"tag": a.tag, "annotations": ann, "mock": mock}
    (OUT / f"rows_annotations_{a.tag}.json").write_text(json.dumps(arows, indent=1))
    (OUT / f"rows_mock_{a.tag}.json").write_text(json.dumps(mrows, indent=1, ensure_ascii=False))
    (OUT / f"summary_{a.tag}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps({"annotations": {"n": ann["n"], "strict": {k: ann["strict"][k] for k in ("TP", "FP", "FN", "TN")},
                                      "recall": ann["strict"]["recall"]["value"], "FOR": ann["strict"]["FOR"]["value"],
                                      "precision": ann["strict"]["precision"]["value"], "gates": ann["gates"]},
                      "mock": {k: mock["main"][k] for k in ("TP", "FP", "FN", "TN")} | {"recall": mock["main"]["recall"]["value"],
                               "FOR": mock["main"]["FOR"]["value"], "precision": mock["main"]["precision"]["value"]}}, indent=1))


if __name__ == "__main__":
    main()
