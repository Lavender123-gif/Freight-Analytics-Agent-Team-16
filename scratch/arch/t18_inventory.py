"""Task 18 section 3: inventory statistics from stored runs only (no model call, no test split, no held-out or round-4 mock).

Runs: dev full `devFullV12-5d09` and mock round 3 `mockR3V12-f0d3`. 'Sent' = the system as frozen at t17: stored flags,
copy flags and roll-up recomputed by today's code, plus the task-17 reading checks and the fuzzy injection layer.
Prints aggregates only; per-explanation rows (with record keys) go to data/interim/eval/t18/ (git-ignored).
Usage: uv run python scratch/arch/t18_inventory.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "autorun")]
import compare_variants as cv  # noqa: E402
import confusion as C  # noqa: E402

from freight_lineitems.reading_checks import reading_diagnostics  # noqa: E402
from freight_lineitems.records import MOCK_R3_DIR  # noqa: E402
from freight_lineitems.textprep import fuzzy_injection_hits, injection_hits, normalize  # noqa: E402

OUT = ROOT / "data" / "interim" / "eval" / "t18"
TOOLS = ["submit_line_items", "report_uncertainty", "calculate", "find_similar_examples", "lookup_charge_code", "lookup_tax_rule"]

# Feature groups (task 18 §3.4). Generic English only; matched on the redacted text, upper-cased.
GROUPS = {
    "tax": r"\b(GST|HST|PST|QST|TAX|TAXES)\b",
    "balance_paid_billed": r"\b(BALANCE|BAL|PAID|PD|SHORT ?PAID|SHORTPAY|BILLED|INVOICED|OWED|OUTSTANDING|REMAINING)\b",
    "unit_rate": r"@|\b(PER|EACH|DAYS?|HRS?|HOURS?)\b|\d\s*X\s*\$?\d",
    "rate_correction": r"\bSHOULD (APPLY|BE|HAVE)\b|\bPER (THE )?CONTRACT\b|\bCONTRACT(ED)? RATE\b|\bTARIFF\b|\bRE-?RATE\b|"
                       r"\b(WRONG|INCORRECT) (RATE|FSC|FUEL)\b|\bRATE (CORRECTION|DIFFERENCE)\b",
    # a dash followed by a space is a separator ('FUEL SURCHARGE - $12.34', 329 dev texts), not a minus sign
    "credit_negative": r"\bCREDIT(ED|S)?\b|(?<![\w/.-])-\$?\d|\$-\d|\(\s*\$?\d[\d,.]*\s*\)",
    "history": r"\b(EARLIER|PRIOR|PREVIOUS(LY)?|REVISED|REBILL(ED)?|RE-BILL(ED)?|ORIGINAL(LY)?|RESUBMIT(TED)?|ALREADY)\b",
}
GROUPS_RE = {k: re.compile(v) for k, v in GROUPS.items()}
ROLLUP_RULE = {   # roll-up flag -> rule number in rollup.py
    "SHIP.ROLLUP.ORDER_TIED": "1", "SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE": "2", "SHIP.ROLLUP.TAX_PARTLY_ORPHANED": "3",
    "SHIP.ROLLUP.SAME_AMOUNT_EARLIER": "5", "SHIP.ROLLUP.RATIO_SUPERSEDED": "6ab", "SHIP.ROLLUP.BALANCE_DUE_READING_DIFFERS": "6a",
    "SHIP.ROLLUP.BALANCE_DUE_UNRESOLVED": "6c", "SHIP.ROLLUP.RELATION_UNDECIDED": "7", "SHIP.ROLLUP.INCOMPLETE": "8",
    "SHIP.ROLLUP.ECHO_OF_HISTORY_AMOUNT": "9",
}
# mock failure modes whose expected handling needs another explanation of the same shipment
CROSS_MODES = {m for m in ["rollup_balance_due_small_increase", "rollup_same_charge_supersede", "rollup_same_charge_restate",
                           "rollup_distinct_charges_add", "rollup_same_amount_different_charge", "rollup_tax_follows_note",
                           "rollup_same_timestamp_order", "suggested_balance_due_chain", "suggested_tax_basis_after_partial_supersede",
                           "suggested_fee_synonym_supersede", "rollup_credit_negative", "history_resubmission", "history_restate",
                           "history_105_multiplier", "history_same_delta_new_text", "history_week_gap", "distinct_later_event"]}


def groups_of(text: str, injected: bool) -> list[str]:
    t = (text or "").upper()
    g = [k for k, rx in GROUPS_RE.items() if rx.search(t)]
    if injected:
        g.append("injection")
    return g


def tool_stats(e: dict) -> dict:
    """Per explanation: tool -> {calls, errors, invalid}; plus n_model_calls and whether it was submit-only."""
    calls = e["process"].get("transcript", {}).get("calls", []) if e["process"].get("model_ran") else []
    out = {t: {"calls": 0, "errors": 0, "invalid": 0} for t in TOOLS}
    out["_other"] = {"calls": 0, "errors": 0, "invalid": 0}
    prov = {e["facts"]["source"].get("origin_state"), e["facts"]["source"].get("destination_state")}
    for c in calls:
        res = {r["tool_use_id"]: json.loads(r["content"]) for r in c.get("tool_results", [])}
        for b in c["content"]:
            if b["type"] != "tool_use":
                continue
            name = b["name"] if b["name"] in TOOLS else "_other"
            s = out[name]
            s["calls"] += 1
            r = res.get(b["id"], {})
            a = b.get("input", {})
            if name == "submit_line_items":
                if not r.get("accepted"):
                    s["errors"] += 1
                    if any(x.get("code") == "RUN.SUBMIT.SCHEMA_INVALID" for x in r.get("errors", [])):
                        s["invalid"] += 1
            elif name == "report_uncertainty":
                if not r.get("recorded"):
                    s["errors"] += 1
                if not re.fullmatch(r"(numbers|line_items|relations|unrecognized_reads)/#?\w+|text|run|[\w/#\[\].]+", a.get("target_path", "")):
                    s["invalid"] += 1
            elif "error" in r:
                s["errors"] += 1
            if name == "lookup_tax_rule" and a.get("province") not in prov:
                s["invalid"] += 1
            if name == "find_similar_examples" and not 1 <= int(a.get("k", 0)) <= 3:
                s["invalid"] += 1
            if name == "lookup_charge_code" and not (r.get("matches") or []):
                s["invalid"] += 1
    n_uses = sum(v["calls"] for v in out.values())
    out["_n_model_calls"] = len(calls)
    out["_submit_only"] = n_uses > 0 and out["submit_line_items"]["calls"] == n_uses
    return out


def load(run: str) -> tuple[dict, dict, dict]:
    ex, ships = C.system_view(run)
    recs = cv.records_for(next(iter(ex.values()))["facts"]["source"]["source"])
    view = {}
    for rid, e in ex.items():
        ship = ships[e["facts"]["source"]["shipment_key"]]
        rd = {d.code for d in reading_diagnostics(e["facts"]["number_table"], e["facts"].get("reading"))}
        raw = normalize(recs[rid].text_raw)
        inj = bool(injection_hits(raw)) or bool(fuzzy_injection_hits(raw))
        sent = C.sent(e, ship) or bool(rd & {"CLAIM.NOTHING_COUNTED", "ITEM.AMOUNT.LEADING_DOT_COUNTED"}) or bool(fuzzy_injection_hits(raw))
        diags = {d["code"] for d in e["judgment"]["diagnostics"]}
        view[rid] = {"shipment": e["facts"]["source"]["shipment_key"], "sent": sent,
                     "self_doubt": "RUN.AGENT.UNCERTAINTY_REPORTED" in diags,
                     "groups": groups_of(e["facts"].get("text_redacted"), inj), "tools": tool_stats(e),
                     "ship_flags": sorted({f["code"] for f in ship["flags"] if f["severity"] == "attention"}),
                     "expl_flags": sorted({f["code"] for f in e["judgment"]["flags"] if f["severity"] in ("attention", "return")} | rd)}
    return ex, ships, view


def tool_table(view: dict, misread: dict | None) -> dict:
    n = len(view)
    out = {}
    for t in TOOLS + ["_other"]:
        users = [rid for rid, v in view.items() if v["tools"][t]["calls"]]
        calls = sum(v["tools"][t]["calls"] for v in view.values())
        row = {"calls": calls, "records": len(users), "records_pct": round(100 * len(users) / n, 1),
               "per_using_record": round(calls / len(users), 2) if users else None,
               "errors": sum(v["tools"][t]["errors"] for v in view.values()),
               "invalid": sum(v["tools"][t]["invalid"] for v in view.values())}
        non = [rid for rid in view if rid not in set(users)]
        for lab, key in (("sent", "sent"), ("self_doubt", "self_doubt")):
            row[f"{lab}_with"] = _pct([view[r][key] for r in users])
            row[f"{lab}_without"] = _pct([view[r][key] for r in non])
        if misread is not None:
            row["misread_with"] = _pct([misread[r] for r in users if r in misread])
            row["misread_without"] = _pct([misread[r] for r in non if r in misread])
        out[t] = row
    out["_summary"] = {"explanations": n, "submit_only": sum(v["tools"]["_submit_only"] for v in view.values()),
                       "submit_only_pct": round(100 * sum(v["tools"]["_submit_only"] for v in view.values()) / n, 1),
                       "model_calls": Counter(v["tools"]["_n_model_calls"] for v in view.values()),
                       "resubmitted": sum(v["tools"]["submit_line_items"]["calls"] > 1 for v in view.values())}
    return out


def _pct(xs: list[bool]) -> list:
    return [sum(xs), len(xs), round(100 * sum(xs) / len(xs), 1) if xs else None]


def group_table(view: dict) -> dict:
    keys = list(GROUPS) + ["injection"]
    cnt = Counter(g for v in view.values() for g in v["groups"])
    sent = Counter(g for v in view.values() if v["sent"] for g in v["groups"])
    dist = Counter(min(len(v["groups"]), 4) for v in view.values())
    pairs = Counter(tuple(sorted(v["groups"])) for v in view.values() if len(v["groups"]) >= 2)
    return {"per_group": {k: {"explanations": cnt[k], "sent": sent[k]} for k in keys},
            "n_groups_distribution": {str(k) + ("+" if k == 4 else ""): dist[k] for k in sorted(dist)},
            "top_combinations": [[list(k), n] for k, n in pairs.most_common(8)]}


def multi_table(ex: dict, ships: dict, view: dict) -> dict:
    by_ship = defaultdict(list)
    for rid, v in view.items():
        by_ship[v["shipment"]].append(rid)
    multi = {s: r for s, r in by_ship.items() if len(r) >= 2}
    hist = {s for s, r in multi.items() if any("history" in view[x]["groups"] or "balance_paid_billed" in view[x]["groups"] for x in r)}
    hist_strict = {s for s, r in multi.items() if any("history" in view[x]["groups"] for x in r)}
    fires = Counter(f for s in ships.values() for f in {x["code"] for x in s["flags"]} if f in ROLLUP_RULE)
    fires_multi = Counter(f for k, s in ships.items() if k in multi for f in {x["code"] for x in s["flags"]} if f in ROLLUP_RULE)
    return {"shipments": len(by_ship), "multi_shipments": len(multi),
            "explanations_in_multi": sum(len(r) for r in multi.values()),
            "multi_with_history_or_balance": len(hist), "multi_with_history_words": len(hist_strict),
            "size_distribution": dict(Counter(len(r) for r in by_ship.values())),
            "rule_fires_shipments": {f"{ROLLUP_RULE[f]} {f}": fires[f] for f in ROLLUP_RULE},
            "rule_fires_in_multi": {f"{ROLLUP_RULE[f]} {f}": fires_multi[f] for f in ROLLUP_RULE}}


def mock_rows(ex: dict, ships: dict, view: dict) -> list[dict]:
    t17 = {r["mock_id"]: r for r in json.loads((ROOT / "data" / "interim" / "eval" / "t17" / "mock_rows.json").read_text())}
    t16 = {r["mock_id"]: r for r in json.loads((ROOT / "data" / "interim" / "eval" / "t16" / "mock_rows.json").read_text())}
    by_row = {s["record_id"]: rid for rid, e in ex.items() for s in e["facts"]["source_rows"]}
    rows = []
    for g in (json.loads(x) for x in (MOCK_R3_DIR / "ground_truth_open.jsonl").open()):
        if not g.get("active", True):
            continue
        rid = by_row["mock3#" + g["row_ids"][0]]
        v = view[rid]
        n_in_ship = sum(1 for x in view.values() if x["shipment"] == v["shipment"])
        rows.append({"mock_id": g["mock_id"], "rid": rid, "failure_mode": g["failure_mode"], "A": t17[g["mock_id"]]["A"],
                     "B": t17[g["mock_id"]]["B"], "claim_wrong": t16[g["mock_id"]]["claim_wrong"], "sent": v["sent"],
                     "groups": v["groups"], "ship_flags": v["ship_flags"], "expl_flags": v["expl_flags"],
                     "multi": n_in_ship >= 2, "cross_mode": g["failure_mode"] in CROSS_MODES,
                     "history_relation": g["history_relation"]["relation"]})
    return rows


def rule_eval(rows: list[dict]) -> dict:
    """Per roll-up flag on mock round 3: rows whose shipment carries it, split by truth; and 'sole' = the only reason sent."""
    out = {}
    for f, num in ROLLUP_RULE.items():
        d = {}
        for key in ("A", "B"):
            fired = [r for r in rows if f in r["ship_flags"]]
            sole = [r for r in fired if set(r["ship_flags"]) | set(r["expl_flags"]) == {f}]
            d[key] = {"fired_rows": len(fired), "on_positive": sum(r[key] for r in fired),
                      "on_negative": sum(not r[key] for r in fired), "sole_reason_negative_FP": sum(not r[key] for r in sole)}
        out[f"{num} {f}"] = d
    return out


def shipment_totals(ships: dict) -> dict:
    """Mock round 3: our default change per shipment vs the mock's default change (multi-explanation shipments)."""
    truth = {json.loads(x)["shipment_id"]: json.loads(x) for x in (MOCK_R3_DIR / "shipment_truth_open.jsonl").open()}
    res = Counter()
    wrong_flagged = Counter()
    for k, t in truth.items():
        if k not in ships:
            res["missing"] += 1
            continue
        s = ships[k]
        multi = len(t["event_mock_ids"]) >= 2
        ok = abs(Decimal(s["default_change"]) - Decimal(str(t["default_change"]))) <= Decimal("0.005")
        res[("multi" if multi else "single", ok)] += 1
        if not ok:
            wrong_flagged[("multi" if multi else "single", s["shipment_flags_recommendation"] != "PASSED_CHECKS" or
                           any(e["recommendation"] != "PASSED_CHECKS" for e in s["explanations"]))] += 1
    return {"default_change_correct": {f"{a}_{'ok' if b else 'wrong'}": n for (a, b), n in res.items() if a != "missing"},
            "wrong_and_flagged": {f"{a}_{'flagged' if b else 'not_flagged'}": n for (a, b), n in wrong_flagged.items()}}


def fn_breakdown(rows: list[dict]) -> dict:
    out = {}
    for key in ("A", "B"):
        fn = [r for r in rows if r[key] and not r["sent"]]
        out[key] = {"FN": len(fn), "by_group": Counter(g for r in fn for g in (r["groups"] or ["(none)"])),
                    "by_mode": Counter(r["failure_mode"] for r in fn), "in_multi_shipment": sum(r["multi"] for r in fn),
                    "cross_mode": sum(r["cross_mode"] for r in fn)}
    # positives that need another explanation: what caught them
    pos = [r for r in rows if r["A"] and r["cross_mode"]]
    caught_by = Counter()
    for r in pos:
        if not r["sent"]:
            caught_by["missed"] += 1
        elif r["ship_flags"] and not r["expl_flags"]:
            caught_by["only_shipment_rules"] += 1
        elif r["ship_flags"]:
            caught_by["both"] += 1
        else:
            caught_by["only_explanation_flags"] += 1
    out["cross_positives_A"] = {"n": len(pos), **caught_by}
    # the t17 pre-fix FN that fix 2 (echo of history, a cross-explanation rule) caught
    t17 = json.loads((ROOT / "data" / "interim" / "eval" / "t17" / "mock_rows.json").read_text())
    out["t17_fix2_fired_A_positive"] = sum(1 for r in t17 if r["A"] and 2 in r["v"])
    out["t17_fix2_fired_mode"] = Counter(r["failure_mode"] for r in t17 if 2 in r["v"])
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, run in (("dev", C.DEV_RUN), ("mock", C.MOCK_RUN)):
        ex, ships, view = load(run)
        misread = None
        mrows = None
        if name == "mock":
            mrows = mock_rows(ex, ships, view)
            misread = defaultdict(bool)
            for r in mrows:
                misread[r["rid"]] |= r["claim_wrong"]
        res[name] = {"tools": tool_table(view, misread), "groups": group_table(view), "multi": multi_table(ex, ships, view),
                     "sent_explanations": sum(v["sent"] for v in view.values())}
        if name == "mock":
            res[name]["rule_eval"] = rule_eval(mrows)
            res[name]["shipment_totals"] = shipment_totals(ships)
            res[name]["fn"] = fn_breakdown(mrows)
            (OUT / "mock_rows.json").write_text(json.dumps(mrows, indent=1, ensure_ascii=False, default=str))
        (OUT / f"{name}_view.json").write_text(json.dumps(view, indent=1, ensure_ascii=False, default=str))
    (OUT / "summary.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
