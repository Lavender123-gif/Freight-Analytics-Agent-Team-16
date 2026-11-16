"""T12 stocktake 2.1(5): what a shipment-level (SAP BOL) roll-up would give from readings that are ALREADY stored.

Read-only replay of one stored dev run (default: the full dev run of leg 2). No model calls, nothing is re-read
by a model, no source file is changed. It answers: with today's per-row readings, how far is a simple roll-up
from Jake's two worked examples, and how often would the 'later explanation replaces the earlier one' rule fire.

Roll-up variants (planning estimates, NOT the final design):
  SUM_ALL    add the counted amounts of every distinct explanation of the shipment
  SUPERSEDE  decision A3: for each non-tax charge code, only the latest explanation naming it is kept; a tax line
             stays only while a non-tax line of its own explanation stays (or its explanation has only tax lines)
  EXCEL      the client's current approach rolled up: the sum of Delta over the distinct explanations
A 'distinct explanation' = one (SHIPMENT_GID, Event Date, text) group (proposal C4); order = Event Date, then row.

Prints aggregates only; row-level detail goes to data/interim/deliverables/T12/bol_replay.json (git-ignored).
Run: uv run python docs/deliverables/T12-replan-after-jake/scripts/s2_bol_replay.py [run_dir_name]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal

from freight_lineitems.checks import region_value
from freight_lineitems.config import ROOT, RUNS_DIR, category

OUT = ROOT / "data" / "interim" / "deliverables" / "T12"
BRIEF = ROOT / "data" / "incoming" / "2026-11-13" / "cc_task_replan_after_jake.md"
RUN = sys.argv[1] if len(sys.argv) > 1 else "20261110-195411-devFull-4823"
COUNTED = {"CLAIMED", "UNPAID"}
TOL = Decimal("0.005")


def items(rec: dict) -> list[dict] | None:
    """Counted amounts of the final reading: [{code, amount, tax}]. None when the reading did not pass the checks."""
    f = rec["facts"]
    if f["parse_status"] != "PASSED_CHECKS" or not f["reading"]:
        return None
    val = {n["id"]: Decimal(n["value"]) for n in f["number_table"]["numbers"]}
    val |= {u["id"]: region_value(u["raw"]) for u in f["number_table"]["unrecognized"]}
    js = list(f["reading"]["numbers"]) + [u["as_number"] | {"id": u["region_id"]} for u in f["reading"].get("unrecognized_reads", [])]
    out = []
    for j in js:
        if j["status"] not in COUNTED or j["kind"] not in ("CHARGE_AMOUNT", "UNSPECIFIED_AMOUNT", "TAX_AMOUNT"):
            continue
        amt = val[j["id"]] * (-1 if j["is_credit"] else 1)
        codes = j["charge_codes"] or ["(unnamed)"]
        key = "+".join(sorted(codes))
        if "OTHER" in codes:
            key += ":" + " ".join((j.get("other_phrase") or "").upper().split())
        out.append({"code": key, "amount": amt, "tax": j["kind"] == "TAX_AMOUNT" or any(category(c) == "TAX" for c in codes)})
    return out


def main() -> None:
    recs = [json.loads(line) for line in (RUNS_DIR / RUN / "records.jsonl").open()]
    by_gid: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        by_gid[r["facts"]["source"]["shipment_key"]].append(r)
    c: Counter = Counter()
    detail = {}
    for gid, rs in by_gid.items():
        units: dict[tuple, dict] = {}
        for r in sorted(rs, key=lambda r: (r["facts"]["source"]["event_date"] or "", r["facts"]["source"]["row_number"])):
            s = r["facts"]["source"]
            k = (s["event_date"], r["facts"]["text_sha256"])
            u = units.setdefault(k, {"rows": 0, "pks": set(), "rec": r, "delta": Decimal(s["delta"])})
            u["rows"] += 1
            u["pks"].add(s["pk"])
        us = list(units.values())
        c["shipments"] += 1
        c["explanations"] += len(us)
        c["rows"] += len(rs)
        c["shipments_1_explanation" if len(us) == 1 else "shipments_2plus_explanations"] += 1
        if len({u["rec"]["facts"]["source"]["event_date"] for u in us}) < len(us):
            c["shipments_with_tied_event_dates"] += 1
        its = [items(u["rec"]) for u in us]
        recs_colour = [u["rec"]["judgment"]["recommendation"] for u in us]
        d = {"n_units": len(us), "n_rows": len(rs), "ship": rs[0]["facts"]["source"]["shipment_amount"],
             "bol": rs[0]["facts"]["source"]["raw"].get("SAP BOL"), "excel": str(sum(u["delta"] for u in us)),
             "unit_colours": recs_colour}
        if any(i is None for i in its):
            c["shipments_with_a_reading_not_passed"] += 1
            d["status"] = "NOT_ALL_PASSED"
            detail[gid] = d
            continue
        sum_all = sum((x["amount"] for i in its for x in i), Decimal(0))
        last_unit_of_code = {}
        for n, i in enumerate(its):
            for x in i:
                if not x["tax"]:
                    last_unit_of_code[x["code"]] = n
        sup = Decimal(0)
        replaced = False
        for n, i in enumerate(its):
            nontax = [x for x in i if not x["tax"]]
            kept = [x for x in nontax if last_unit_of_code[x["code"]] == n]
            replaced |= len(kept) < len(nontax)
            sup += sum((x["amount"] for x in kept), Decimal(0))
            if kept or not nontax:
                sup += sum((x["amount"] for x in i if x["tax"]), Decimal(0))
        amounts = [abs(x["amount"]) for i in its for x in i]
        same_amount_across = len(us) > 1 and any(
            set(abs(x["amount"]) for x in its[a]) & set(abs(x["amount"]) for x in its[b])
            for a in range(len(its)) for b in range(a + 1, len(its)))
        excel = sum(u["delta"] for u in us)
        d |= {"status": "OK", "sum_all": str(sum_all), "supersede": str(sup), "replaced": replaced,
              "same_amount_across": same_amount_across, "n_items": len(amounts)}
        detail[gid] = d
        if len(us) > 1:
            c["multi: same non-tax code recurs (A3 replace fires)"] += replaced
            c["multi: same amount recurs across explanations"] += same_amount_across
            c["multi: SUM_ALL != SUPERSEDE"] += abs(sum_all - sup) > TOL
            c["multi: all explanations coloured PASSED_CHECKS"] += all(x == "PASSED_CHECKS" for x in recs_colour)
            c["multi: SUPERSEDE == EXCEL"] += abs(sup - excel) <= TOL
            c["multi: SUM_ALL == EXCEL"] += abs(sum_all - excel) <= TOL
        else:
            c["single: reading == EXCEL"] += abs(sum_all - excel) <= TOL
            c["single: coloured PASSED_CHECKS"] += recs_colour[0] == "PASSED_CHECKS"
        c["all: SUPERSEDE == EXCEL"] += abs(sup - excel) <= TOL
        c["all: readings passed"] += 1
    print(json.dumps({"run": RUN} | dict(c), indent=1))

    # Jake's two worked examples (keys and expected numbers are taken from the git-ignored brief)
    brief = BRIEF.read_text()
    by_bol = {d["bol"]: d for d in detail.values()}
    for k in re.findall(r"\b\d{17}\b", brief)[:2]:
        seg = brief[brief.index(k):][:900]
        exp_total = re.search(r"New Disputed Total \| ([\d.]+)", seg).group(1)
        exp_delta = re.search(r"Delta from Original Amount \| ([\d.]+)", seg).group(1)
        d = by_bol.get(k)
        if not d or d["status"] != "OK":
            print("example: not available", d and d["status"])
            continue
        row = {"explanations": d["n_units"], "rows": d["n_rows"], "expected_delta": exp_delta, "expected_total": exp_total,
               "SUM_ALL": d["sum_all"], "SUPERSEDE": d["supersede"], "EXCEL_sum_of_delta": d["excel"],
               "new_total_from_SUPERSEDE": str(Decimal(d["ship"]) + Decimal(d["supersede"])),
               "SUM_ALL_matches": abs(Decimal(d["sum_all"]) - Decimal(exp_delta)) <= TOL,
               "SUPERSEDE_matches": abs(Decimal(d["supersede"]) - Decimal(exp_delta)) <= TOL,
               "unit_colours": d["unit_colours"]}
        print(json.dumps(row, indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bol_replay.json").write_text(json.dumps(detail, indent=1, default=str))


if __name__ == "__main__":
    main()
