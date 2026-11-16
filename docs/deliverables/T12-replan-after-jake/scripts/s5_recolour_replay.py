"""T12 stocktake 2.1(4): what happens to the three recommendations on the stored full dev run when the
Delta-based flags are withdrawn (proposal C1) and a tax mention no longer sends a record to a person (C6).

Read-only replay on stored diagnostics. No model call, no rule file is changed: the severity changes are applied
in memory only. Prints counts only.

Run: uv run python docs/deliverables/T12-replan-after-jake/scripts/s5_recolour_replay.py [run_dir_name]
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from freight_lineitems.config import RULES, RUNS_DIR

RUN = sys.argv[1] if len(sys.argv) > 1 else "20261110-195411-devFull-4823"
DELTA = lambda c: c.startswith("CLAIM.DELTA.") or c.startswith("REC.FIELD.DELTA_")  # noqa: E731
SEV = {k: v["severity"] for k, v in RULES["flags"].items()}
SUB = RULES.get("subsumption", {})


def colour(codes: set[str], drop=lambda c: False, override: dict | None = None) -> tuple[str, list[str]]:
    codes = {c for c in codes if not drop(c)}
    sev = {c: (override or {}).get(c, SEV.get(c, "attention")) for c in codes}
    for c in codes:
        if any(s in codes for s in SUB.get(c, [])) and sev[c] != "info":
            sev[c] = "info"
    att = sorted(c for c in codes if sev[c] == "attention")
    ret = sorted(c for c in codes if sev[c] == "return")
    return ("HUMAN_REVIEW", att) if att else (("RETURN_SUGGESTED", ret) if ret else ("PASSED_CHECKS", []))


def main() -> None:
    recs = [json.loads(line) for line in (RUNS_DIR / RUN / "records.jsonl").open()]
    variants = {
        "V0 current rules": dict(),
        "V1 Delta flags withdrawn (C1)": dict(drop=DELTA),
        "V2 = V1 + tax mention -> info (C6)": dict(drop=DELTA, override={"ITEM.TAX.PRESENT": "info"}),
        "V3 = V2 + tax named without amount -> attention": dict(drop=DELTA, override={"ITEM.TAX.PRESENT": "info", "ITEM.TAX.NO_AMOUNT": "attention"}),
        "V4 = V3 + currency flag removed (B4)": dict(drop=lambda c: DELTA(c) or c == "REC.FIELD.CURRENCY_UNDETERMINED",
                                                    override={"ITEM.TAX.PRESENT": "info", "ITEM.TAX.NO_AMOUNT": "attention"}),
    }
    code_sets = [{d["code"] for d in r["judgment"]["diagnostics"]} for r in recs]
    base = [colour(cs)[0] for cs in code_sets]
    print("run", RUN, "| records", len(recs))
    for name, kw in variants.items():
        res = [colour(cs, **kw) for cs in code_sets]
        dist = Counter(c for c, _ in res)
        moved = Counter((b, c) for b, (c, _) in zip(base, res) if b != c)
        print(f"\n{name}: passed {dist['PASSED_CHECKS']} / human {dist['HUMAN_REVIEW']} / return {dist['RETURN_SUGGESTED']}")
        for (a, b), n in moved.items():
            print(f"    {a} -> {b}: {n}")
    # what the Delta flags decide today
    c = Counter()
    sole = Counter()
    for cs in code_sets:
        col, att = colour(cs)
        for code in cs:
            if DELTA(code):
                c[code] += 1
        if col == "HUMAN_REVIEW" and att and all(DELTA(a) for a in att):
            sole["human review only because of Delta flags"] += 1
            sole["   of which: " + "+".join(att)] += 1
        if col == "HUMAN_REVIEW" and att == ["ITEM.TAX.PRESENT"]:
            sole["human review only because a tax is mentioned"] += 1
    print("\nDelta-based flags on this run:", dict(c))
    for k, v in sole.items():
        print(f"{k}: {v}")
    dc = Counter(r["facts"]["delta_consistency"] for r in recs)
    fc = Counter(str(r["facts"]["first_check"]) for r in recs)
    print("delta_consistency:", dict(dc))
    print("first_check:", dict(fc))
    print("currency field:", dict(Counter(r["facts"]["currency"] for r in recs)))
    print("records with a tax flag:", sum(1 for cs in code_sets if "ITEM.TAX.PRESENT" in cs),
          "| tax named without amount:", sum(1 for cs in code_sets if "ITEM.TAX.NO_AMOUNT" in cs))
    facts = json.loads((RUNS_DIR / RUN / "export_facts.json").read_text())
    print("downstream fact export today (passed, Delta-consistent, no attention flag):", len(facts), "of", len(recs))
    extra_calls = sum(max(0, r["process"].get("n_model_calls", 0) - 1) for r in recs if str(r["facts"]["first_check"]) == "MISMATCH")
    print("model calls after a first 'inconsistent' (what the retry costs):", extra_calls,
          "| all model calls:", sum(r["process"].get("n_model_calls", 0) for r in recs))


if __name__ == "__main__":
    main()
