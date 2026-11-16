"""Task 20b sections 1 and 2: two extra views of the round-4 public mock, both DEFINED AFTER the task-20 results
were seen (post hoc, synthetic data). No model call, no rule or screening change; it re-reads the same stored runs
as scratch/eval/t20_r4_eval.py and goes through the same pipeline.finish_batch path.

1. "Passed but total wrong": a shipment whose recommendation is PASSED_CHECKS (and none of whose explanations is
   sent by the evaluation's supplement checks) while its default new total differs from the mock's shipment new
   total, compared in cents. Also: shipments whose total differs, and how many of those were sent to a human.
   Over all 561 shipments, split round-3 part / round-4 new part and single / multi explanation.
2. Injection events grouped by the written text instead of the mock category label: plain English, the category's
   own misspelling / look-alike wording, and the 5 templates repeated across the 6 injection categories. Counted per
   event and per distinct injected text. Lists the templates of the missed events and whether a missed event's
   amount was changed (its counted total and its shipment new total against the mock answer).

Usage: uv run python scratch/eval/t20b_midterm_eval.py [--new 20261115-192714-mockR4newT20-ab8a]
Writes data/interim/eval/t20b/t20b_eval.json (git-ignored); prints aggregates only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "autorun")]
import compare_variants as cv  # noqa: E402
import confusion as C  # noqa: E402
import t19_eval as T19  # noqa: E402
import t20_r4_eval as R4  # noqa: E402

from freight_lineitems.records import MOCK_R4_DIR  # noqa: E402
from freight_lineitems.textprep import fuzzy_injection_hits, normalize  # noqa: E402

OUT = ROOT / "data" / "interim" / "eval" / "t20b"
NEW_RUN = "20261115-192714-mockR4newT20-ab8a"
CENT = Decimal("0.01")
INJ_MODES = T19.INJ_PLAIN | T19.INJ_DISGUISED
OWN_MISSPELLING_MODES = T19.INJ_DISGUISED       # obfuscated, unicode confusables: their own non-repeated wording


def cents(x) -> Decimal | None:
    return None if x is None else Decimal(str(x)).quantize(CENT)


def load_views(new_run: str) -> dict:
    views = {}
    for part, run, prefix in (("r3", R4.R3_RUN, "mock3#"), ("new", new_run, "mock4#")):
        ex, ships, sent = T19.views(run)
        views[part] = (ex, ships, sent, prefix)
    return views


def shipment_rows(rows: list[dict], views: dict) -> list[dict]:
    """One row per mock shipment: our recommendation, whether it was sent, and whether our new total matches."""
    part_of = {r["mock_id"]: r["part"] for r in rows}
    ev = {r["mock_id"]: r for r in rows}
    out = []
    for t in (json.loads(x) for x in (MOCK_R4_DIR / "shipment_truth_open.jsonl").open()):
        part = part_of[t["event_mock_ids"][0]]
        ex, ships, sent, _ = views[part]
        s = ships.get(t["shipment_id"])
        ours, truth = cents(s and s["new_total"]), cents(t.get("new_total"))
        expl = [x["expl_id"] for x in s["explanations"]] if s else []
        supplement = any(sent.get(x) for x in expl)          # the evaluation's per-explanation "sent" (incl. task-17 checks)
        out.append({
            "shipment_id": t["shipment_id"], "part": part,
            "kind": "multi" if len(t["event_mock_ids"]) > 1 else "single",
            "events": t["event_mock_ids"], "injection_events": [m for m in t["event_mock_ids"] if ev[m]["failure_mode"] in INJ_MODES],
            "recommendation": s["recommendation"] if s else None,
            "sent": (s is None) or s["recommendation"] != "PASSED_CHECKS" or supplement,
            "sent_by_recommendation_only": (s is None) or s["recommendation"] != "PASSED_CHECKS",
            "truth_has_total": truth is not None,
            "total_wrong": truth is not None and ours != truth,
            "ours": str(ours) if ours is not None else None, "truth": str(truth) if truth is not None else None,
        })
    return out


def section1(srows: list[dict]) -> dict:
    def agg(rs):
        wrong = [r for r in rs if r["total_wrong"]]
        return {"shipments": len(rs), "truth_without_total": sum(not r["truth_has_total"] for r in rs),
                "total_wrong": len(wrong), "total_wrong_sent": sum(r["sent"] for r in wrong),
                "passed_but_total_wrong": sum(not r["sent"] for r in wrong),
                "passed_but_total_wrong_by_recommendation_only": sum(not r["sent_by_recommendation_only"] for r in wrong),
                "passed": sum(not r["sent"] for r in rs)}
    out = {"all": agg(srows)}
    for p in ("r3", "new"):
        out[p] = agg([r for r in srows if r["part"] == p])
        for k in ("single", "multi"):
            out[f"{p}/{k}"] = agg([r for r in srows if r["part"] == p and r["kind"] == k])
    out["passed_but_total_wrong_ids"] = [r["shipment_id"] for r in srows if r["total_wrong"] and not r["sent"]]
    return out


def injected_text(g: dict) -> str:
    return " | ".join(g["injection"]["substrings"])


def section2(rows: list[dict], views: dict, srows: list[dict]) -> dict:
    gt = {g["mock_id"]: g for g in (json.loads(x) for x in (MOCK_R4_DIR / "ground_truth_open.jsonl").open())}
    recs4 = {json.loads(x)["row_id"]: json.loads(x) for x in (MOCK_R4_DIR / "mock_records_open.jsonl").open()}
    inj = [r for r in rows if r["failure_mode"] in INJ_MODES]
    # a template is an injected text that recurs in more than one injection category
    cats_of = {}
    for r in inj:
        cats_of.setdefault(injected_text(gt[r["mock_id"]]), set()).add(r["failure_mode"])
    repeated = {t for t, c in cats_of.items() if len(c) > 1}
    ship_of = {m: s for s in srows for m in s["events"]}

    def group(r):
        t = injected_text(gt[r["mock_id"]])
        if t in repeated:
            return "3_repeated_templates"
        return "2_own_misspelling" if r["failure_mode"] in OWN_MISSPELLING_MODES else "1_plain_english"

    detail = []
    for r in inj:
        g = gt[r["mock_id"]]
        ex, ships, _sent, _ = views[r["part"]]
        e = ex[r["explanation"]]
        ship = ships[e["facts"]["source"]["shipment_key"]]
        detail.append({"mock_id": r["mock_id"], "part": r["part"], "category": r["failure_mode"], "group": group(r),
                       "injected_text": injected_text(g), "sent": r["sent"],
                       "send_flags": sorted(C.send_flags(e, ship)),
                       "fuzzy_layer_hit": bool(fuzzy_injection_hits(normalize(recs4[g["row_ids"][0]]["text"] or ""))),
                       "counted_total_wrong": r["claim_wrong"],
                       "shipment_total_wrong": ship_of[r["mock_id"]]["total_wrong"]})
    groups = {}
    for name in sorted({d["group"] for d in detail}):
        ds = [d for d in detail if d["group"] == name]
        texts = {}
        for d in ds:
            texts.setdefault(d["injected_text"], []).append(d["sent"])
        groups[name] = {"events": len(ds), "events_sent": sum(d["sent"] for d in ds),
                        "distinct_texts": len(texts), "distinct_texts_always_sent": sum(all(v) for v in texts.values()),
                        "distinct_texts_never_sent": sum(not any(v) for v in texts.values()),
                        "distinct_texts_mixed": sum(any(v) and not all(v) for v in texts.values()),
                        "categories": sorted({d["category"] for d in ds}),
                        "per_text": {t: f"{sum(v)}/{len(v)}" for t, v in sorted(texts.items())}}
    missed = [d for d in detail if not d["sent"]]
    return {"groups": groups, "repeated_templates": sorted(repeated),
            "missed": {"events": len(missed), "templates": dict(Counter(d["injected_text"] for d in missed)),
                       "categories": dict(Counter(d["category"] for d in missed)),
                       "counted_total_wrong": sum(d["counted_total_wrong"] for d in missed),
                       "shipment_total_wrong": sum(d["shipment_total_wrong"] for d in missed)},
            "sent_with_injection_flag": {f"{g}/{'injection_flag' if h else 'other_flags_only'}": n for (g, h), n in Counter(
                (d["group"], any("INJECTION" in f or "SCREEN" in f for f in d["send_flags"])) for d in detail if d["sent"]).items()},
            "detail": detail}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", default=NEW_RUN)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    views = load_views(a.new)
    rows = R4.event_rows(views)
    srows = shipment_rows(rows, views)
    res = {"definition": "post hoc (defined after the task-20 results), synthetic data", "r3_run": R4.R3_RUN,
           "new_run": a.new, "section1": section1(srows), "section2": section2(rows, views, srows)}
    (OUT / "t20b_eval.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    (OUT / "t20b_shipments.json").write_text(json.dumps(srows, indent=1, ensure_ascii=False, default=str))
    short = {"section1": res["section1"],
             "section2": {k: v for k, v in res["section2"].items() if k != "detail"}}
    print(json.dumps(short, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
