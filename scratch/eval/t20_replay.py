"""Task 20 section 2.1/2.3: replay the shipment results on the stored task-19 readings, before and after the roll-up was
wired into the main flow, and list every difference. No model call.

`run --tag base` (run on the commit before the change): the evaluation path of task 19 (confusion.system_view).
`run --tag main` (after the change): confusion.system_view now calls pipeline.finish_batch, the same function
run_batch calls, so this is the production path.
`diff base main`: per shipment, every field that differs; per explanation, whether 'sent to a person' changed. The
only allowed differences are those of task 20 section 1 items 1 (BALANCE DUE) and 2 (gap); they are listed by flag.

Per-shipment output: data/interim/eval/t20/ (git-ignored). Prints aggregates only.
Usage: uv run python scratch/eval/t20_replay.py run --tag base
       uv run python scratch/eval/t20_replay.py diff base main
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
import confusion as C  # noqa: E402

OUT = ROOT / "data" / "interim" / "eval" / "t20"
RUNS = {"dev": "devFullT19routed-055d", "mock3": "mockR3T19routed-4079"}
NEW_FIELDS = {"gap", "schema_version", "prior_history", "relation_suggestions", "relation_undecided", "items_total",
              "stated_amount_due", "per_explanation_gap", "lines_display"}


def fingerprint(run: str) -> dict:
    ex, ships = C.system_view(run)
    sent = {rid: C.sent(e, ships[e["facts"]["source"]["shipment_key"]]) for rid, e in ex.items()}
    return {"ships": ships, "sent": sent,
            "expl_rec": {rid: e["judgment"]["recommendation"] for rid, e in ex.items()}}


def run(tag: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, r in RUNS.items():
        fp = fingerprint(r)
        (OUT / f"ships_{tag}_{name}.json").write_text(json.dumps(fp, indent=0, default=str, sort_keys=True))
        print(name, len(fp["ships"]), "shipments", sum(fp["sent"].values()), "explanations sent")


def _flags(s: dict) -> dict:
    return {f["code"]: f["severity"] for f in s.get("flags", [])}


def diff(a: str, b: str) -> None:
    res = {}
    for name in RUNS:
        A = json.loads((OUT / f"ships_{a}_{name}.json").read_text())
        B = json.loads((OUT / f"ships_{b}_{name}.json").read_text())
        fields, flag_changes, unexplained = Counter(), Counter(), []
        rec_changed = []
        for k, sa in A["ships"].items():
            sb = B["ships"][k]
            # charge_map display columns (client name, EDI candidates) are added by finish_batch; compare the rest
            sb = sb | {"lines": [{k: ln.get(k) for k in la} for la, ln in zip(sa["lines"], sb["lines"])]
                       if len(sa["lines"]) == len(sb["lines"]) else sb["lines"],
                       "explanations": [{k: x.get(k) for k in xa} for xa, x in zip(sa["explanations"], sb["explanations"])]}
            changed = sorted(f for f in set(sa) | set(sb) if f not in NEW_FIELDS and sa.get(f) != sb.get(f))
            fa, fb = _flags(sa), _flags(sb)
            for c in set(fa) | set(fb):
                if fa.get(c) != fb.get(c):
                    flag_changes[f"{c}: {fa.get(c)} -> {fb.get(c)}"] += 1
            for f in changed:
                fields[f] += 1
            # every change must come from a BALANCE DUE flag or a gap flag (task 20 section 1 items 1, 2)
            bd = {c for c in set(fa) ^ set(fb)} | {c for c in set(fa) & set(fb) if fa[c] != fb[c]}
            allowed = all(c.startswith(("SHIP.ROLLUP.BALANCE_DUE", "SHIP.GAP.")) for c in bd)
            money = [f for f in changed if f in ("default_change", "new_total", "lines", "other_readings", "other_readings_range")]
            if (changed and not allowed) or money:
                unexplained.append({"shipment": k, "fields": changed, "flag_diff": sorted(bd)})
            if sa["recommendation"] != sb["recommendation"]:
                rec_changed.append((k, sa["recommendation"], sb["recommendation"], sorted(bd)))
        sent_a, sent_b = A["sent"], B["sent"]
        flips = Counter(f"{sent_a[r]}->{sent_b[r]}" for r in sent_a if sent_a[r] != sent_b[r])
        gaps = [s for s in B["ships"].values() if s.get("gap") is not None]
        res[name] = {"shipments": len(A["ships"]), "fields_changed": dict(fields), "flag_changes": dict(flag_changes),
                     "unexplained": unexplained, "shipment_recommendation_changed": len(rec_changed),
                     "explanations_sent_flips": dict(flips), "sent_before": sum(sent_a.values()),
                     "sent_after": sum(sent_b.values())}
        (OUT / f"diff_{a}_{b}_{name}.json").write_text(json.dumps(res[name] | {"rec_changed": rec_changed}, indent=1, default=str))
    print(json.dumps({k: {x: y for x, y in v.items() if x != "unexplained"} | {"n_unexplained": len(v["unexplained"])}
                      for k, v in res.items()}, indent=1, default=str))


def stats(tag: str) -> None:
    """Gap numbers (task 20 section 2.3) on the shipment results of one tag: explanations and shipments with a gap,
    how many are 0, and the distribution of the others (sign, size, and gap / line total)."""
    out = {}
    for name in RUNS:
        B = json.loads((OUT / f"ships_{tag}_{name}.json").read_text())
        ex = [e for s in B["ships"].values() for e in s["explanations"]]
        stated = [e for e in ex if e.get("stated_amount_due") is not None]
        g = [Decimal(e["gap"]) for e in ex if e.get("gap") is not None]
        nz = [(Decimal(e["gap"]), Decimal(e["items_total"])) for e in ex if e.get("gap") is not None and abs(Decimal(e["gap"])) > Decimal("0.005")]

        def bucket(x: Decimal, tot: Decimal) -> str:
            if tot == 0:
                return "line total 0 (nothing counted)"
            r = abs(x / tot)
            if x == -tot:
                return "stated 0"
            return ("stated > lines" if x > 0 else "stated < lines") + (
                ", |gap| <= 1% of lines" if r <= Decimal("0.01") else ", |gap| 1-10%" if r <= Decimal("0.10")
                else ", |gap| 10-100%" if r <= 1 else ", |gap| > 100%")
        ships = list(B["ships"].values())
        single = [s for s in ships if len(s["explanations"]) == 1]
        out[name] = {
            "explanations": len(ex), "with_stated_amount_due": len(stated), "with_gap": len(g),
            "gap_zero": sum(1 for x in g if abs(x) <= Decimal("0.005")), "gap_nonzero": len(nz),
            "nonzero_distribution": dict(Counter(bucket(x, t) for x, t in nz)),
            "nonzero_abs_median": str(sorted(abs(x) for x, _ in nz)[len(nz) // 2]) if nz else None,
            "shipments": len(ships), "single_explanation_shipments": len(single),
            "shipments_with_gap": sum(1 for s in ships if s.get("gap") is not None),
            "shipments_gap_nonzero": sum(1 for s in ships if s.get("gap") is not None and abs(Decimal(s["gap"])) > Decimal("0.005")),
            "multi_explanation_shipments_with_note": sum(1 for s in ships if s.get("gap_note")),
            "shipments_with_SHIP.GAP.NONZERO": sum(1 for s in ships if any(f["code"] == "SHIP.GAP.NONZERO" for f in s["flags"])),
        }
    (OUT / f"gap_stats_{tag}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--tag", required=True)
    st = sp.add_parser("stats")
    st.add_argument("--tag", required=True)
    d = sp.add_parser("diff")
    d.add_argument("a")
    d.add_argument("b")
    x = ap.parse_args()
    run(x.tag) if x.cmd == "run" else stats(x.tag) if x.cmd == "stats" else diff(x.a, x.b)


_ = Decimal
if __name__ == "__main__":
    main()
