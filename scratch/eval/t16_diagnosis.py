"""Task 16: where the problems come from, and systematic differences between the reference answers and the system.
No model call; stored readings only, flags and roll-up recomputed by the working-tree code (scratch/eval/confusion.py).
Definitions: docs/deliverables/T16-diagnosis/01-preregistration.zh.md and scratch/eval/t16_features.yaml.
Prints aggregates; per-record rows go to data/interim/eval/t16/ (git-ignored).
Usage: uv run python scratch/eval/t16_diagnosis.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "autorun"), str(ROOT / "scratch" / "annotation")]
import compare_variants as cv  # noqa: E402
import confusion as C  # noqa: E402
import metrics as M  # noqa: E402

from freight_lineitems import duplicates  # noqa: E402
from freight_lineitems.checks import quantity_rate_patterns  # noqa: E402
from freight_lineitems.config import category  # noqa: E402
from freight_lineitems.numbers import parse  # noqa: E402
from freight_lineitems.records import MOCK_R3_DIR  # noqa: E402
from freight_lineitems.textprep import normalize  # noqa: E402

F = yaml.safe_load((ROOT / "scratch" / "eval" / "t16_features.yaml").read_text())
OUT = ROOT / "data" / "interim" / "eval" / "t16"
PRIORITY = ["security", "input", "history", "rule_not_covered", "model_misread", "model_misread_or_input", "redaction"]
HIST = {"BILLED", "PAID", "DEDUCTED"}


def text_features(raw: str, redacted: str) -> set[str]:
    t = raw.upper()
    out = set()
    m = re.search(r"BALANCE\s+DUE", t)
    if m:
        out.add("balance_due_after" if "$" in t[:m.start()] else "balance_due_first")
    for k in ("history_words", "tax_words", "rate_words", "leading_dot", "combined_and"):
        if re.search(F["features"][k], t):
            out.add(k)
    if re.search(F["features"]["redaction_placeholder"], redacted or ""):
        out.add("redaction_placeholder")
    return out


def primary(sources: list[str]) -> tuple[str, list[str]]:
    srt = sorted(set(sources), key=lambda s: PRIORITY.index(s) if s in PRIORITY else len(PRIORITY))
    return (srt[0] if srt else "other"), srt[1:]


# ------------------------------------------------------------------------------------------- 2.1 dev full
def dev_full():
    ex, ships = C.system_view(C.DEV_RUN)
    recs = cv.records_for("dev")
    sent_rows, passed_feats, examples = [], Counter(), {}
    for rid, e in ex.items():
        ship = ships[e["facts"]["source"]["shipment_key"]]
        raw = normalize(recs[rid].text_raw)
        red = e["facts"].get("text_redacted") or ""
        f = e["facts"]
        cnt = cv.counted(f["reading"], f["number_table"]) if f.get("reading") else {}
        money = sum((abs(a) for a, _ in cnt.values()), Decimal(0))
        if C.sent(e, ship):
            flags = C.send_flags(e, ship)
            src = [F["flag_source"].get(fl, "other") for fl in flags]
            p, s = primary(src)
            if p == "model_misread_or_input":
                p = "input"
            sent_rows.append({"record_id": rid, "shipment": e["facts"]["source"]["shipment_key"], "primary": p, "secondary": s,
                              "flags": sorted(flags), "money": str(money)})
            continue
        feats = set()
        nt = f["number_table"]
        dollars = [n for n in nt["numbers"] if n["has_dollar"]]
        if dollars and not cnt:
            feats.add("dollar_amount_but_nothing_counted")
        if f.get("reading") and any(j["status"] in HIST and j["kind"] in ("CHARGE_AMOUNT", "UNSPECIFIED_AMOUNT") for j in f["reading"]["numbers"]):
            feats.add("an_amount_read_as_history")
        if set(cnt) & {n["id"] for n in nt["numbers"] if n["leading_dot"]}:
            feats.add("leading_dot_amount_counted")
        tf = text_features(raw, red)
        if "balance_due_first" in tf:
            feats.add("balance_due_first")
        if "balance_due_after" in tf:
            feats.add("balance_due_after")
        if quantity_rate_patterns(red, parse(red)):
            feats.add("quantity_times_rate")
        for m in re.finditer(r"\[PERSON_\d+\]", red):
            if re.search(r"\d", red[max(0, m.start() - 15): m.end() + 15]):
                feats.add("placeholder_near_amount")
                break
        for k in feats:
            passed_feats[k] += 1
    passed_feats["number_not_explained_by_reading"] = 0   # every number id must be judged (mandatory check), so 0 by construction
    by_src = defaultdict(lambda: {"records": 0, "shipments": set(), "money": Decimal(0)})
    for r in sent_rows:
        b = by_src[r["primary"]]
        b["records"] += 1
        b["shipments"].add(r["shipment"])
        b["money"] += Decimal(r["money"])
    sent_summary = {k: {"records": v["records"], "shipments": len(v["shipments"]), "money": str(v["money"])} for k, v in by_src.items()}
    n_passed = sum(1 for rid, e in ex.items() if not C.sent(e, ships[e["facts"]["source"]["shipment_key"]]))
    (OUT / "dev_sent.json").write_text(json.dumps(sent_rows, indent=1))
    return {"explanations": len(ex), "sent": len(sent_rows), "passed": n_passed, "sent_by_source": sent_summary,
            "passed_features": dict(passed_feats)}


def excel_sources():
    run = cv.replay.find_run(C.DEV_RUN)
    rows = list(csv.DictReader((ROOT / "data" / "interim" / "eval" / "excel_baseline" / f"{run}.csv").open()))
    m = {"C1": "other:excel_counts_stated_total", "C2": "history", "C3": "history", "C4": "other:excel_counts_history",
         "C5": "other:excel_misses_no_dollar", "C6": "other:excel_keeps_one_row", "C7": "history", "C8": "model_misread",
         "C9": "other:two_causes", "C0": "other:unclassified"}
    out = defaultdict(Counter)
    for r in rows:
        if r["category"] != "equal":
            out[r["baseline"]][m[r["category"]]] += 1
    return {k: dict(v) for k, v in out.items()}


# ------------------------------------------------------------------------------------------- 2.2 mock
def mock():
    rows = C.mock_rows()
    gt = {json.loads(l)["mock_id"]: json.loads(l) for l in (MOCK_R3_DIR / "ground_truth_open.jsonl").open()}
    recs = {json.loads(l)["row_id"]: json.loads(l) for l in (MOCK_R3_DIR / "mock_records_open.jsonl").open()}
    names = F["mock_fee_names"]
    ex, ships = C.system_view(C.MOCK_RUN)
    by_row = {s["record_id"]: e for e in ex.values() for s in e["facts"]["source_rows"]}
    out_rows = []
    for r in rows:
        g = gt[r["mock_id"]]
        text = recs[g["row_ids"][0]]["text"] or ""
        e = by_row["mock3#" + g["row_ids"][0]]
        cur = [i for i in g["claim"]["items"] if i.get("is_current_claim")]
        fees = {i["fee_name"] for i in cur}
        b_reasons = []
        if any(fn in names["not_in_taxonomy"] or any(p in names["not_in_taxonomy"] for p in fn.split(" and ")) for fn in fees):
            b_reasons.append("fee_not_in_taxonomy")
        if fees & set(names["no_charge_named"]):
            b_reasons.append("no_charge_named")
        pks = [duplicates.normalize_pk(recs[x].get("order_id")) for x in g["row_ids"]]
        if len(pks) > 1 and (any(not p for p in pks) or len(set(pks)) < len(pks)):
            b_reasons.append("copy_same_or_empty_pk")
        exp_a = g["expected_recommendation"] != "解析通过检查"
        if g["failure_mode"] == "understanding_one_amount_two_fees" and not b_reasons:
            exp_b = False
        else:
            exp_b = exp_a or bool(b_reasons)
        p10 = bool(re.search(r"EARLIER CLAIM", text.upper())) and bool(re.search(r"PRIOR", text.upper()))
        cnt = cv.counted(e["facts"]["reading"], e["facts"]["number_table"]) if e["facts"].get("reading") else {}
        got = sum((a for a, _ in cnt.values()), Decimal(0))
        wrong_if_model_right = got != Decimal(0) if p10 else r["claim_wrong"]
        out_rows.append(r | {"text_features": sorted(text_features(text, e["facts"].get("text_redacted") or "")),
                             "positive_A": r["positive"], "positive_B": exp_b or r["claim_wrong"], "b_reasons": b_reasons,
                             "p10": p10, "positive_A_p10_model_right": (exp_a or wrong_if_model_right) if p10 else r["positive"],
                             "fees": sorted(fees), "system_codes": sorted({c for _, cs in cnt.values() for c in cs}),
                             "got": str(got), "truth": str(g["claim"]["current_claim_total"])})
    def mat(pos_key):
        c = Counter(("TP" if r["sent"] else "FN") if r[pos_key] else ("FP" if r["sent"] else "TN") for r in out_rows)
        return C.rates(c["TP"], c["FP"], c["FN"], c["TN"])
    res = {"A": mat("positive_A"), "B": mat("positive_B"), "A_p10_model_right": mat("positive_A_p10_model_right"),
           "p10_events": sum(r["p10"] for r in out_rows),
           "p10_events_system_read_as_history": sum(r["p10"] and Decimal(r["got"]) == 0 for r in out_rows),
           "b_reasons": dict(Counter(x for r in out_rows for x in r["b_reasons"]))}
    # sub-matrices under B (same problem types as task 15)
    for r in out_rows:
        r["positive"] = r["positive_B"]
    res["B_sub"] = {k: {x: v[x] for x in ("TP", "FP", "FN", "TN", "FN_missed", "FN_wrong_cause")} | {"recall": v["recall"]["value"], "precision": v["precision"]["value"]}
                    for k, v in C.submatrix(out_rows).items()}
    # sources of FN / FP under both readings
    def src_fn(r):
        fm = r["failure_mode"]
        if r["p10"] and r["claim_wrong"]:
            return "model_bias", ["gold_conflicts_rule"]
        if fm.startswith("injection_") or fm == "suggested_unicode_confusables":
            return "security", ["redaction"]
        if r["claim_wrong"]:
            return "model_misread", []
        if fm.startswith("history_"):
            return "history", ["model_bias"]
        if fm == "understanding_one_amount_two_fees":
            return "gold_conflicts_rule", []
        return "other", []
    def src_fp(r, pos_key):
        fl = set(r["send_flags"])
        if pos_key == "positive_A" and fl & {"ITEM.CODE.OTHER", "SHIP.COPY.SAME_OR_NO_PK"} and r["b_reasons"]:
            return "gold_conflicts_rule", []
        s = [F["flag_source"].get(x, "other") for x in fl]
        p, rest = primary(s)
        return ("input" if p == "model_misread_or_input" else p), rest
    srcs = {}
    for key in ("positive_A", "positive_B"):
        fn = Counter(src_fn(r)[0] for r in out_rows if r[key] and not r["sent"])
        fp = Counter(src_fp(r, key)[0] for r in out_rows if not r[key] and r["sent"])
        srcs[key] = {"FN": dict(fn), "FP": dict(fp)}
    res["sources"] = srcs
    (OUT / "mock_rows.json").write_text(json.dumps(out_rows, indent=1, ensure_ascii=False))
    return res, out_rows


# ------------------------------------------------------------------------------------------- 3 systematic differences
def systematic(mrows):
    """Feature x direction of difference, mock (>= 5) and annotations (>= 3)."""
    out = {"mock": [], "annotations": []}
    cells = Counter()
    for r in mrows:
        dirs = []
        if r["claim_wrong"]:
            dirs.append("system_total_lower" if Decimal(r["got"]) < Decimal(r["truth"]) else "system_total_higher")
        if r["positive"] != r["sent"]:
            dirs.append("system_sends_gold_not" if r["sent"] else "gold_sends_system_not")
        feats = set(r["text_features"]) | ({"fee_not_in_taxonomy"} if "fee_not_in_taxonomy" in r["b_reasons"] else set()) \
            | ({"p10_earlier_claim"} if r["p10"] else set()) | ({"injection_mode"} if r["failure_mode"].startswith("injection_") else set()) \
            | ({"one_amount_two_fees"} if r["failure_mode"] == "understanding_one_amount_two_fees" else set())
        for f in feats:
            for d in dirs:
                cells[(f, d)] += 1
    out["mock"] = [{"feature": f, "direction": d, "n": n} for (f, d), n in cells.most_common() if n >= 5]
    # annotations: number-level, gold (re-judged) vs model
    merged = list(csv.DictReader((ROOT / "data" / "interim" / "annotation" / "deliverable" / "merged_annotations.csv").open()))
    run = M.load_run(cv.replay.find_run(C.DEV_RUN))
    recs = cv.records_for("dev")
    ac = Counter()
    for r in merged:
        if r["final_claim"] == "DROPPED":
            continue
        rec = run[r["record_key"]]
        view = (M.model_view(rec) or {}).get(r["number_id"], {})
        claim = r["rejudged_claim"] or r["final_claim"]
        cat = r["rejudged_category"] or r["final_category"]
        h3 = {"NOT_HISTORY": "NOT_COUNTED", "NOT_TOTAL": "NOT_COUNTED", "NOT_REFERENCE": "NOT_COUNTED", "NOT_MONEY": "NOT_COUNTED"}.get(claim, claim)
        dirs = []
        if h3 in ("COUNTED", "NOT_COUNTED", "CREDIT") and view and h3 != view.get("claim3"):
            dirs.append(f"gold_{h3}_system_{view.get('claim3')}")
        if h3 == "COUNTED" and view.get("claim3") == "COUNTED" and cat and cat not in view.get("categories", set()):
            dirs.append(f"category_gold_{cat}_system_{'+'.join(sorted(view.get('categories', [])))}")
        if h3 == "UNCLEAR" and view.get("claim3"):
            dirs.append(f"gold_UNCLEAR_system_{view.get('claim3')}")
        feats = text_features(normalize(recs[r["record_key"]].text_raw), rec["facts"].get("text_redacted") or "") | {"any"}
        for f in feats:
            for d in dirs:
                ac[(f, d)] += 1
    out["annotations"] = [{"feature": f, "direction": d, "n": n} for (f, d), n in ac.most_common() if n >= 3]
    return out


def corroboration():
    """Same wordings on the full dev split: how many, and how the system read them."""
    ex, ships = C.system_view(C.DEV_RUN)
    recs = cv.records_for("dev")
    c = Counter()
    for rid, e in ex.items():
        t = normalize(recs[rid].text_raw).upper()
        f = e["facts"]
        cnt = cv.counted(f["reading"], f["number_table"]) if f.get("reading") else {}
        codes = {x for _, cs in cnt.values() for x in cs}
        sent = C.sent(e, ships[f["source"]["shipment_key"]])
        if re.search(r"EARLIER CLAIM|PRIOR ACCESSORIAL", t):
            c["p10_wording"] += 1
        m = re.search(r"BALANCE\s+DUE", t)
        if m and "$" not in t[:m.start()]:
            c["balance_due_first"] += 1
            c["balance_due_first_sent"] += sent
        if "OTHER" in codes:
            c["system_code_other"] += 1
        if any(len(cs) > 1 for _, cs in cnt.values()):
            c["one_amount_several_codes"] += 1
            c["one_amount_several_codes_sent"] += sent
        if re.search(r"\[PERSON_\d+\]", f.get("text_redacted") or ""):
            c["redaction_placeholder"] += 1
        if re.search(r"(?<![\d.,])\.\d+", t):
            c["leading_dot"] += 1
        for code, pat in (("RATE_CORRECTION.FUEL_TIER", r"FSC.*SHOULD APPLY"), ("RATE_CORRECTION.CONTRACT_GENERAL", r"PER CONTRACT"),
                          ("ACCESSORIAL.ROAD_CLOSURE", r"ROAD CLOSURE"), ("ACCESSORIAL.SORT_SEGREGATE", r"SORTATION"), ("ACCESSORIAL.IN_BOND", r"BOND CHARGES")):
            if re.search(pat, t):
                c[f"phrasing:{code}"] += 1
                c[f"phrasing:{code}:system_used_it"] += code in codes
    return dict(c)


def coverage_gaps():
    """2.3: wordings in the real data that the mock lacks, and wordings frequent in the mock that the real data lacks."""
    pats = {"leading_dot_amount": r"(?<![\d.,])\.\d+", "space_in_thousands": r"\b\d{1,3} \d{3}(?:\.\d\d)?\b",
            "fsc_should_apply": r"FSC.*SHOULD APPLY", "purchase_fee_or_transportation": r"PURCHASE[D]? (FEE|TRANSP)",
            "balance_due_first": None, "balance_due_after": None, "dwell_days_at_rate": r"DAY\(S\)\s*@",
            "per_contract": r"PER CONTRACT", "date_ranges": r"\d{1,2}/\d{1,2}(/\d{2,4})?", "usd_word": r"\bUSD\b",
            "non_ascii": r"[^\x00-\x7f]", "parentheses_amount": r"\(\$?\s?\d", "comma_decimal": r"\d,\d{2}\b(?!\d)",
            "semicolon": r";", "injection_words": r"IGNORE|OVERRIDE|DISREGARD|BYPASS|SYSTEM\s*:|INSTRUCTION",
            "earlier_claim_prior": r"EARLIER CLAIM|PRIOR ACCESSORIAL", "email_or_phone": r"@\w+\.|\d{3}[-. ]\d{3}[-. ]\d{4}",
            "rebill_or_revised": r"\bREBILL|\bREVISED|\bREV CHG", "credit_word": r"\bCREDIT\b", "tax_word": r"\b(GST|HST|PST|QST)\b",
            "negative_sign_amount": r"-\s?\$\s?\d|\$\s?-\d", "ocr_like_digit_letters": r"[A-Z][0-9][A-Z]|[0-9][A-Z]{2}[0-9]"}
    def count(texts):
        c = Counter()
        for t in texts:
            T = t.upper()
            for k, p in pats.items():
                if p is None:
                    m = re.search(r"BALANCE\s+DUE", T)
                    if m and k == "balance_due_first" and "$" not in T[:m.start()]:
                        c[k] += 1
                    if m and k == "balance_due_after" and "$" in T[:m.start()]:
                        c[k] += 1
                elif re.search(p, T):
                    c[k] += 1
        return c
    from freight_lineitems.records import group_explanations
    dev = [normalize(g[0].text_raw) for g in group_explanations(list(cv.records_for("dev").values()))]
    mock_texts = [json.loads(l)["text"] or "" for l in (MOCK_R3_DIR / "mock_records_open.jsonl").open()]
    cd, cm = count(dev), count(mock_texts)
    return {k: {"dev": cd[k], "dev_share": round(cd[k] / len(dev), 3), "mock": cm[k], "mock_share": round(cm[k] / len(mock_texts), 3)}
            for k in pats}, len(dev), len(mock_texts)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"dev_full": dev_full(), "excel_disagreement_sources": excel_sources()}
    m, mrows = mock()
    res["mock"] = m
    res["systematic"] = systematic(mrows)
    res["corroboration_dev"] = corroboration()
    cg, nd, nm = coverage_gaps()
    res["coverage_gaps"] = {"dev_explanations": nd, "mock_rows": nm, "features": cg}
    t15 = json.loads((ROOT / "data" / "interim" / "eval" / "t15" / "fn_list.json").read_text())
    amap = {"gold_suspect:category_boundary": "annotator_missing_info", "gold_suspect:rejudge_definition_R-BD": "rule_ambiguous",
            "gold_suspect:rejudge_R-QR_quantity_one": "rule_ambiguous", "new_rule_candidate:leading_dot_amount": "rule_not_covered"}
    res["annotation_fn_sources"] = dict(Counter(amap[r["cause"]] for r in t15["annotations"]))
    (OUT / "summary.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
