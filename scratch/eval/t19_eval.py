"""Task 19 section 3/4: the pre-written gates, computed the same way for the task-17 baseline (stored runs) and for a
new run pair. No model call.

'Sent to a person' for an explanation = today's system on the stored reading: the stored flags (copy flags and the
shipment roll-up recomputed by today's code, confusion.system_view) plus the task-17 reading checks and the fuzzy
injection layer, which the v1.2 runs predate (for new runs they are already in the stored flags, so adding them again
changes nothing). This is the task-17 recompute (t17_recompute.py) written once for any run.

Truth:
- annotations: confusion.annotation_rows with the task-17 corrections (G8 = the system misread, so it is per run);
- mock round 3, reading A (mock answers): expected recommendation is not 'passed', or the counted sum is wrong;
  reading B (our standard): as t17_recompute.py (D-79, D-80), with the counted sum of this run;
- dev full: no truth; the number of explanations sent.
Groups (task 19 section 3): the six feature groups of rules.yaml `features.groups` on the redacted text, 'no_group',
and the injection events in two groups by mock failure mode: written like ordinary data (direct, system prompt,
embedded, change amount) and deliberately disguised (obfuscated, unicode confusables).

Usage: uv run python scratch/eval/t19_eval.py --tag base --dev devFullV12-5d09 --mock mockR3V12-f0d3
Per-record rows: data/interim/eval/t19/ (git-ignored). Prints aggregates only.
"""

from __future__ import annotations

import argparse
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

from freight_lineitems.config import RULES  # noqa: E402
from freight_lineitems.features import groups_of  # noqa: E402
from freight_lineitems.reading_checks import reading_diagnostics  # noqa: E402
from freight_lineitems.records import MOCK_R3_DIR  # noqa: E402
from freight_lineitems.textprep import fuzzy_injection_hits, normalize  # noqa: E402

OUT = ROOT / "data" / "interim" / "eval" / "t19"
F16 = yaml.safe_load((ROOT / "scratch" / "eval" / "t16_features.yaml").read_text())
NOT_IN_TAX = [n for n in F16["mock_fee_names"]["not_in_taxonomy"] if n != "inside placement"]      # D-79
SEV = {k: v["severity"] for k, v in RULES["flags"].items()}
INJ_PLAIN = {"injection_direct", "injection_system_prompt", "injection_embedded", "injection_change_amount"}
INJ_DISGUISED = {"injection_obfuscated", "suggested_unicode_confusables"}
GROUP_KEYS = list(RULES["features"]["groups"]) + ["no_group", "injection_plain", "injection_disguised"]


def supplement(e: dict, recs: dict) -> bool:
    """Task-17 checks a v1.2 run predates: attention-level reading checks, the fuzzy injection layer."""
    if any(SEV.get(d.code) == "attention" for d in reading_diagnostics(e["facts"]["number_table"], e["facts"].get("reading"))):
        return True
    return bool(fuzzy_injection_hits(normalize(recs[e["record_id"]].text_raw)))


def views(run: str) -> tuple[dict, dict, dict]:
    ex, ships = C.system_view(run)
    recs = cv.records_for(next(iter(ex.values()))["facts"]["source"]["source"])
    sent = {rid: C.sent(e, ships[e["facts"]["source"]["shipment_key"]]) or supplement(e, recs) for rid, e in ex.items()}
    return ex, ships, sent


def groups(e: dict, failure_mode: str | None = None) -> list[str]:
    g = groups_of(e["facts"].get("text_redacted") or "")
    out = g or ["no_group"]
    if failure_mode in INJ_PLAIN:
        out.append("injection_plain")
    if failure_mode in INJ_DISGUISED:
        out.append("injection_disguised")
    return out


def matrix(rows: list[dict], key: str) -> dict:
    c = Counter(("TP" if r["sent"] else "FN") if r[key] else ("FP" if r["sent"] else "TN") for r in rows)
    m = C.rates(c["TP"], c["FP"], c["FN"], c["TN"])
    return {k: (m[k]["value"], m[k]["ci95"], m[k]["k"], m[k]["n"]) if isinstance(m[k], dict) else m[k]
            for k in ("TP", "FP", "FN", "TN", "recall", "FOR", "precision")}


def per_group(rows: list[dict], key: str) -> dict:
    out = {}
    for g in GROUP_KEYS:
        rs = [r for r in rows if g in r["groups"]]
        pos = [r for r in rs if r[key]]
        tp = sum(r["sent"] for r in pos)
        out[g] = {"events": len(rs), "positives": len(pos), "TP": tp, "FN": len(pos) - tp,
                  "recall": round(100 * tp / len(pos), 1) if pos else None}
    return out


def mock_rows(mock_run: str) -> list[dict]:
    C.MOCK_RUN = mock_run
    ex, ships, sent = views(mock_run)
    by_row = {s["record_id"]: e for e in ex.values() for s in e["facts"]["source_rows"]}
    base = {r["mock_id"]: r for r in C.mock_rows()}        # positive (A) and claim_wrong of this run's readings
    t16 = {r["mock_id"]: r for r in json.loads((ROOT / "data" / "interim" / "eval" / "t16" / "mock_rows.json").read_text())}
    recs = {json.loads(x)["row_id"]: json.loads(x) for x in (MOCK_R3_DIR / "mock_records_open.jsonl").open()}
    rows = []
    for g in (json.loads(x) for x in (MOCK_R3_DIR / "ground_truth_open.jsonl").open()):
        if not g.get("active", True):
            continue
        e = by_row["mock3#" + g["row_ids"][0]]
        b, o = base[g["mock_id"]], t16[g["mock_id"]]
        text = (recs[g["row_ids"][0]]["text"] or "").upper()
        reasons = []                                       # truth-only reasons (task 17 reading B)
        if any(any(p in NOT_IN_TAX for p in fn.split(" and ")) for fn in o["fees"]):
            reasons.append("fee_not_in_taxonomy")
        if set(o["fees"]) & set(F16["mock_fee_names"]["no_charge_named"]):
            reasons.append("no_charge_named")
        if "copy_same_or_empty_pk" in o["b_reasons"]:
            reasons.append("copy_same_or_empty_pk")
        p40 = bool(re.search(r"EARLIER CLAIM", text)) and bool(re.search(r"PRIOR", text))
        if p40:
            reasons.append("p40_earlier_claim_prior")
        exp_a = g["expected_recommendation"] != "解析通过检查"
        exp_b = False if (g["failure_mode"] == "understanding_one_amount_two_fees" and not reasons) else (exp_a or bool(reasons))
        rows.append({"mock_id": g["mock_id"], "failure_mode": g["failure_mode"], "explanation": e["record_id"],
                     "A": b["positive"], "B": exp_b or (b["claim_wrong"] and not p40), "claim_wrong": b["claim_wrong"],
                     "sent": sent[e["record_id"]], "groups": groups(e, g["failure_mode"])})
    return rows


CORRECTIONS = "t17_corrections.json"      # task 20 (P-43, D-97): --corrections t20_corrections.json


def annotation_rows(dev_run: str) -> list[dict]:
    C.DEV_RUN = dev_run
    ex, ships, sent = views(dev_run)
    corr = json.loads((ROOT / "data" / "interim" / "annotation" / "deliverable" / CORRECTIONS).read_text())
    return [r | {"sent": sent[r["explanation"]]} for r in C.annotation_rows(corrections=corr)]


# ------------------------------------------------------------------------------------------- new fields (addendum)

def sad_pattern(e: dict) -> str | None:
    """Which wording the stated amount due follows (addendum section 'impact'): payment_history, amount_tax_total,
    balance_due_after_other_amounts, only_balance_due, other. None when the field is empty."""
    r = e["facts"].get("reading") or {}
    sad = {"number_id": r.get("stated_amount_due_id")}
    if not sad["number_id"]:
        return None
    nums = e["facts"]["number_table"]["numbers"]
    dollars = [n for n in nums if n["has_dollar"]]
    target = next((n for n in nums if n["id"] == sad.get("number_id")), None)
    js = r.get("numbers", [])
    kinds = {j["id"]: j["kind"] for j in js}
    if any(j["status"] in ("BILLED", "PAID", "DEDUCTED") for j in js):
        return "payment_history"
    if any(rel["relation_type"] == "SUM" and rel.get("result_id") == sad.get("number_id")
           and any(kinds.get(i) == "TAX_AMOUNT" for i in rel["operand_ids"]) for rel in r.get("relations", [])) \
            or (re.search(r"\b(GST|HST|PST|QST|TAX)\b", (e["facts"].get("text_redacted") or "").upper())
                and any(rel["relation_type"] == "SUM" and rel.get("result_id") == sad.get("number_id") for rel in r.get("relations", []))):
        return "amount_tax_total"
    if target is not None and any(n["span"][1] <= target["span"][0] for n in dollars if n["id"] != target["id"]):
        return "balance_due_after_other_amounts"
    if target is not None and [n["id"] for n in dollars] in ([target["id"]], []):
        return "only_balance_due"
    return "other"


def field_stats(ex: dict) -> dict:
    pats = Counter(sad_pattern(e) for e in ex.values())
    filled = sum(v for k, v in pats.items() if k)
    ecm = [e for e in ex.values() if (e["facts"].get("reading") or {}).get("earlier_claim_quote")]
    return {"stated_amount_due_filled": filled, "patterns": {k: v for k, v in pats.items() if k},
            "earlier_claim_mentioned": len(ecm)}


def screening_stats(ex: dict) -> dict:
    hits = [e for e in ex.values() if any(d["code"] == "REC.TEXT.SCREEN_ADDRESSED_TO_SYSTEM" for d in e["judgment"]["diagnostics"])]
    failed = [e for e in ex.values() if any(d["code"] == "RUN.SCREEN.FAILED" for d in e["judgment"]["diagnostics"])]
    ran = [e for e in ex.values() if e["process"].get("screening")]
    return {"ran": len(ran), "hits": len(hits), "failed": len(failed),
            "kinds": dict(Counter((e["process"].get("screening") or {}).get("result", {}).get("kind") for e in hits))}


def routing_stats(ex: dict) -> dict:
    refs = Counter(r for e in ex.values() for r in (e["process"].get("routing") or {}).get("references", []))
    nex = Counter(len((e["process"].get("routing") or {}).get("examples", [])) for e in ex.values())
    return {"references": dict(refs), "examples_per_explanation": dict(nex),
            "layout": dict(Counter((e["process"].get("routing") or {}).get("layout", "single(v1.2)") for e in ex.values()))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dev", required=True)
    ap.add_argument("--mock", required=True)
    ap.add_argument("--corrections", default=CORRECTIONS)
    a = ap.parse_args()
    globals()["CORRECTIONS"] = a.corrections
    OUT.mkdir(parents=True, exist_ok=True)
    dex, _ships, dsent = views(a.dev)
    arows = annotation_rows(a.dev)
    mrows = mock_rows(a.mock)
    mex, _, _ = views(a.mock)
    res = {
        "tag": a.tag, "dev_run": a.dev, "mock_run": a.mock,
        "dev": {"explanations": len(dsent), "sent": sum(dsent.values()),
                "sent_shipments": len({dex[r]["facts"]["source"]["shipment_key"] for r, s in dsent.items() if s}),
                "fields": field_stats(dex), "screening": screening_stats(dex), "routing": routing_stats(dex)},
        "annotations": matrix(arows, "positive"),
        "annotations_fn": [{"explanation": r["explanation"], "gates": r["gates"], "types": r["types"]}
                           for r in arows if r["positive"] and not r["sent"]],
        "mock": {"A": matrix(mrows, "A"), "B": matrix(mrows, "B"), "A_groups": per_group(mrows, "A"),
                 "B_groups": per_group(mrows, "B"), "fields": field_stats(mex), "screening": screening_stats(mex),
                 "routing": routing_stats(mex),
                 "fn_A_modes": dict(Counter(r["failure_mode"] for r in mrows if r["A"] and not r["sent"])),
                 "fn_B_modes": dict(Counter(r["failure_mode"] for r in mrows if r["B"] and not r["sent"]))},
    }
    (OUT / f"eval_{a.tag}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    (OUT / f"rows_mock_{a.tag}.json").write_text(json.dumps(mrows, indent=1, ensure_ascii=False, default=str))
    (OUT / f"rows_annotations_{a.tag}.json").write_text(json.dumps(arows, indent=1, ensure_ascii=False, default=str))
    (OUT / f"sent_dev_{a.tag}.json").write_text(json.dumps(dsent, indent=0))
    short = {"dev_sent": res["dev"]["sent"], "annotations": res["annotations"], "mock_A": res["mock"]["A"], "mock_B": res["mock"]["B"],
             "A_groups": {k: (v["recall"], v["TP"], v["positives"]) for k, v in res["mock"]["A_groups"].items()},
             "B_groups": {k: (v["recall"], v["TP"], v["positives"]) for k, v in res["mock"]["B_groups"].items()},
             "dev_fields": res["dev"]["fields"], "mock_fields": res["mock"]["fields"],
             "dev_screen": res["dev"]["screening"], "mock_screen": res["mock"]["screening"]}
    print(json.dumps(short, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
