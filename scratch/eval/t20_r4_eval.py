"""Task 20 section 3: the round-4 public mock, computed exactly as written in
docs/deliverables/T20-mvp/02-r4-preregistration.zh.md (committed before any result). No model call.

Groups: the round-3 part (568 events; stored task-19 readings mockR3T19routed-4079, everything after the model
recomputed by pipeline.finish_batch) and the round-4 new part (122 events; a new main-flow run). Readings A (mock
answers) and B (our written standard). Reports the main matrices, the two injection groups, shipment new totals and
the weighted "close to real" Recall.

Usage: uv run python scratch/eval/t20_r4_eval.py --new <run of the 122 new events>
Per-event rows: data/interim/eval/t20/r4_rows.json (git-ignored). Prints aggregates only.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "autorun")]
import compare_variants as cv  # noqa: E402
import confusion as C  # noqa: E402
import t19_eval as T19  # noqa: E402

from freight_lineitems.duplicates import normalize_pk  # noqa: E402
from freight_lineitems.records import MOCK_R4_DIR, group_explanations  # noqa: E402
from freight_lineitems.textprep import normalize  # noqa: E402

OUT = ROOT / "data" / "interim" / "eval" / "t20"
R3_RUN = "mockR3T19routed-4079"
NOT_IN_TAX = set(T19.NOT_IN_TAX)                       # task-16 list without 'inside placement' (D-79)
NO_CHARGE = set(T19.F16["mock_fee_names"]["no_charge_named"])
TOL = Decimal("0.005")

# wording classes in priority order (pre-registration section 3.4; regexes of task 16 coverage_gaps)
CLASSES = [
    ("purchased_transportation", r"PURCHASE[D]? (FEE|TRANSP)"),
    ("fsc_tier", r"FSC.*SHOULD APPLY"),
    ("per_contract", r"PER CONTRACT"),
    ("balance_due_first", None),
    ("balance_due_after", None),
    ("days_at_rate", r"DAY\(S\)\s*@"),
    ("leading_dot", r"(?<![\d.,])\.\d+"),
    ("space_thousands", r"\b\d{1,3} \d{3}(?:\.\d\d)?\b"),
    ("hyphen_amount", r"-\s?\$\s?\d|\$\s?-\d"),
    ("tax_word", r"\b(GST|HST|PST|QST)\b"),
    ("mock_only", r"\bUSD\b|;|[A-Z][0-9][A-Z]|[0-9][A-Z]{2}[0-9]|\bCREDIT\b|EARLIER CLAIM|PRIOR ACCESSORIAL|\bREBILL|\bREVISED"
                  r"|\bREV CHG|IGNORE|OVERRIDE|DISREGARD|BYPASS|SYSTEM\s*:|INSTRUCTION|[^\x00-\x7f]|\(\$?\s?\d|\d,\d{2}\b(?!\d)"
                  r"|@\w+\.|\d{3}[-. ]\d{3}[-. ]\d{4}"),
]


def wording_class(text: str) -> str:
    T = (text or "").upper()
    for name, pat in CLASSES:
        if pat is None:
            m = re.search(r"BALANCE\s+DUE", T)
            if m and name == "balance_due_first" and "$" not in T[:m.start()]:
                return name
            if m and name == "balance_due_after" and "$" in T[:m.start()]:
                return name
        elif re.search(pat, T):
            return name
    return "other"


def real_shares() -> tuple[dict, int]:
    dev = [normalize(g[0].text_raw) for g in group_explanations(list(cv.records_for("dev").values()))]
    c = Counter(wording_class(t) for t in dev)
    return {k: v / len(dev) for k, v in c.items()}, len(dev)


def wilson(p: float, n: float) -> list | None:
    if n <= 0:
        return None
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def event_rows(views_by_run: dict, dock_slot_outside: bool = False) -> list[dict]:
    recs4 = {json.loads(x)["row_id"]: json.loads(x) for x in (MOCK_R4_DIR / "mock_records_open.jsonl").open()}
    nit = NOT_IN_TAX | ({"dock slot"} if dock_slot_outside else set())
    rows = []
    for g in (json.loads(x) for x in (MOCK_R4_DIR / "ground_truth_open.jsonl").open()):
        if not g.get("active", True):
            continue
        part = "new" if g["round"] == "round_04_new" else "r3"
        ex, ships, sent, prefix = views_by_run[part]
        e = ex[prefix + g["row_ids"][0]] if prefix + g["row_ids"][0] in ex else \
            next(x for x in ex.values() if any(s["record_id"] == prefix + g["row_ids"][0] for s in x["facts"]["source_rows"]))
        text = recs4[g["row_ids"][0]]["text"] or ""
        truth = Decimal(str(g["claim"]["current_claim_total"]))
        cnt = cv.counted(e["facts"]["reading"], e["facts"]["number_table"]) if e["facts"].get("reading") else {}
        wrong = sum((a for a, _ in cnt.values()), Decimal(0)) != truth
        fees = {i["fee_name"] for i in g["claim"]["items"] if i.get("is_current_claim")}
        reasons = []
        if any(fn in nit or any(p in nit for p in fn.split(" and ")) for fn in fees):
            reasons.append("fee_not_in_taxonomy")
        if fees & NO_CHARGE:
            reasons.append("no_charge_named")
        pks = [normalize_pk(recs4[r].get("order_id")) for r in g["row_ids"]]
        if len(pks) > 1 and (any(not p for p in pks) or len(set(pks)) < len(pks)):
            reasons.append("copy_same_or_empty_pk")
        U = text.upper()
        p40 = bool(re.search(r"EARLIER CLAIM", U)) and bool(re.search(r"PRIOR", U))
        if p40:
            reasons.append("p40_earlier_claim_prior")
        exp_a = g["expected_recommendation"] != "解析通过检查"
        exp_b = False if (g["failure_mode"] == "understanding_one_amount_two_fees" and not reasons) else (exp_a or bool(reasons))
        rows.append({"mock_id": g["mock_id"], "part": part, "failure_mode": g["failure_mode"], "explanation": e["record_id"],
                     "A": exp_a or wrong, "B": exp_b or (wrong and not p40), "claim_wrong": wrong, "reasons": reasons,
                     "sent": sent[e["record_id"]], "wording": wording_class(text)})
    return rows


def matrix(rows: list[dict], key: str) -> dict:
    c = Counter(("TP" if r["sent"] else "FN") if r[key] else ("FP" if r["sent"] else "TN") for r in rows)
    m = C.rates(c["TP"], c["FP"], c["FN"], c["TN"])
    out = {k: m[k] for k in ("TP", "FP", "FN", "TN")}
    for k in ("recall", "FOR", "precision"):
        out[k] = [m[k]["value"], m[k]["ci95"], m[k]["k"], m[k]["n"]]
    out["recall_ge_95"] = m["recall"]["value"] is not None and m["recall"]["value"] >= 95
    out["FOR_le_2"] = m["FOR"]["value"] is not None and m["FOR"]["value"] <= 2
    return out


def weighted(rows: list[dict], key: str, real: dict) -> dict:
    n = len(rows)
    mock = Counter(r["wording"] for r in rows)
    w = {c: (real.get(c, 0) / (mock[c] / n)) if mock[c] else None for c in set(real) | set(mock)}
    pos = [r for r in rows if r[key]]
    ws = [w[r["wording"]] for r in pos]
    tp_w = sum(w[r["wording"]] for r in pos if r["sent"])
    tot_w = sum(ws)
    rec = tp_w / tot_w if tot_w else None
    neff = (sum(ws) ** 2 / sum(x * x for x in ws)) if ws and any(ws) else 0
    per = {}
    for c in sorted(set(real) | set(mock)):
        pc = [r for r in pos if r["wording"] == c]
        per[c] = {"real_share": round(100 * real.get(c, 0), 1), "mock_events": mock[c], "mock_share": round(100 * mock[c] / n, 1),
                  "weight": round(w[c], 3) if w[c] is not None else None, "positives": len(pc), "TP": sum(r["sent"] for r in pc)}
    return {"weighted_recall": round(100 * rec, 1) if rec is not None else None, "kish_n_eff": round(neff, 1),
            "wilson95_on_n_eff": wilson(rec, neff) if rec is not None else None,
            "unweighted_recall": round(100 * sum(r["sent"] for r in pos) / len(pos), 1) if pos else None,
            "positives": len(pos),
            "uncovered_real_share": round(100 * sum(v for c, v in real.items() if not mock[c]), 1),
            "uncovered_classes": sorted(c for c, v in real.items() if v and not mock[c]),
            "leaning_classes_lt5_pos_w_gt1": sorted(c for c, v in per.items() if v["positives"] < 5 and (v["weight"] or 0) > 1 and v["positives"] > 0),
            "per_class": per}


def shipments(rows: list[dict], views_by_run: dict) -> dict:
    out = {}
    truth = [json.loads(x) for x in (MOCK_R4_DIR / "shipment_truth_open.jsonl").open()]
    part_of = {r["mock_id"]: r["part"] for r in rows}
    for t in truth:
        part = part_of[t["event_mock_ids"][0]]
        ships = views_by_run[part][1]
        kind = "multi" if len(t["event_mock_ids"]) > 1 else "single"
        k = (part, kind)
        out.setdefault(k, Counter())
        s = ships.get(t["shipment_id"])
        if t.get("new_total") is None:
            out[k]["truth_without_new_total"] += 1
            continue
        out[k]["n"] += 1
        out[k]["equal"] += s is not None and s["new_total"] is not None and abs(Decimal(s["new_total"]) - Decimal(str(t["new_total"]))) <= TOL
    return {f"{p}/{k}": dict(v) | {"share": round(100 * v["equal"] / v["n"], 1) if v["n"] else None} for (p, k), v in out.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    views = {}
    for part, run, prefix in (("r3", R3_RUN, "mock3#"), ("new", a.new, "mock4#")):
        ex, ships, sent = T19.views(run)
        views[part] = (ex, ships, sent, prefix)
    rows = event_rows(views)
    rows_ds = event_rows(views, dock_slot_outside=True)
    real, ndev = real_shares()
    inj = {"plain": T19.INJ_PLAIN, "disguised": T19.INJ_DISGUISED}
    res = {"r3_run": R3_RUN, "new_run": a.new, "events": dict(Counter(r["part"] for r in rows)), "dev_explanations": ndev}
    for key in ("A", "B"):
        res[key] = {p: matrix([r for r in rows if r["part"] == p], key) for p in ("r3", "new")} | {"all": matrix(rows, key)}
        res[key]["injection"] = {g: {"events": len(rs := [r for r in rows if r["failure_mode"] in m]),
                                     "positives": sum(r[key] for r in rs), "sent": sum(r["sent"] for r in rs),
                                     "sent_of_positives": sum(r["sent"] for r in rs if r[key])} for g, m in inj.items()}
        res[key]["weighted"] = weighted(rows, key, real)
        res[key]["fn_modes"] = {p: dict(Counter(r["failure_mode"] for r in rows if r["part"] == p and r[key] and not r["sent"])) for p in ("r3", "new")}
    res["B_dock_slot_outside"] = {p: matrix([r for r in rows_ds if r["part"] == p], "B") for p in ("r3", "new")}
    res["shipments"] = shipments(rows, views)
    ex_new = views["new"][0]
    res["new_screening"] = T19.screening_stats(ex_new)
    (OUT / "r4_eval.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    (OUT / "r4_rows.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False, default=str))
    short = {k: v for k, v in res.items() if k not in ("A", "B")}
    for key in ("A", "B"):
        short[key] = {p: {x: res[key][p][x] for x in ("TP", "FP", "FN", "TN", "recall", "FOR", "recall_ge_95", "FOR_le_2")}
                      for p in ("r3", "new", "all")}
        short[key]["injection"] = res[key]["injection"]
        short[key]["weighted"] = {x: y for x, y in res[key]["weighted"].items() if x != "per_class"}
        short[key]["fn_modes"] = res[key]["fn_modes"]
    print(json.dumps(short, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
