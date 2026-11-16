"""Task 14 stage 3 item 2: compare two shipment roll-ups (replay outputs) and say why each changed shipment changed.

Reads data/interim/rollup/<run>/shipments.jsonl for both runs (run scratch/rollup/replay.py on each first).
Reasons, per changed shipment (more than one can apply):
  amounts      the set of counted (number id, amount) pairs of the model's readings differs
  codes        same counted amounts, but some charge code differs
  roll_up      same readings, different roll-up result (statuses or flags)
  colour_only  same total, only the recommendation differs (flags of the explanations differ)
Prints counts; the per-shipment list goes to data/interim/rollup/compare_<a>__<b>.json (git-ignored).
Usage: uv run python scratch/rollup/compare_replays.py <run_a> <run_b>
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay  # noqa: E402

OUT = replay.OUT_ROOT


def load(run: str) -> dict[str, dict]:
    return {s["shipment_key"]: s for s in (json.loads(x) for x in (OUT / replay.find_run(run) / "shipments.jsonl").open())}


def main() -> None:
    a_name, b_name = replay.find_run(sys.argv[1]), replay.find_run(sys.argv[2])
    a, b = load(a_name), load(b_name)
    c, detail = Counter(), []
    for k in sorted(a.keys() & b.keys()):
        x, y = a[k], b[k]
        same_total = x["default_change"] == y["default_change"]
        same_rec = x["recommendation"] == y["recommendation"]
        if same_total and same_rec:
            c["unchanged"] += 1
            continue
        la = {(l["explanation"], l["number_id"], l["amount"]) for l in x["lines"] if not l["added_by_code"]}
        lb = {(l["explanation"], l["number_id"], l["amount"]) for l in y["lines"] if not l["added_by_code"]}
        ca = {(l["explanation"], l["number_id"]): tuple(l["codes"]) for l in x["lines"]}
        cb = {(l["explanation"], l["number_id"]): tuple(l["codes"]) for l in y["lines"]}
        why = []
        if la != lb:
            why.append("amounts")
        elif ca != cb:
            why.append("codes")
        elif not same_total:
            why.append("roll_up")
        if same_total:
            why.append("colour_only")
        c["total_changed"] += not same_total
        c["recommendation_changed"] += not same_rec
        c[f"{x['recommendation']}->{y['recommendation']}"] += not same_rec
        for w in why:
            c["reason:" + w] += 1
        detail.append({"shipment": k, "a_change": x["default_change"], "b_change": y["default_change"],
                       "a_rec": x["recommendation"], "b_rec": y["recommendation"], "why": why,
                       "a_flags": [f["code"] for f in x["flags"]], "b_flags": [f["code"] for f in y["flags"]]})
    c["only_in_a"], c["only_in_b"] = len(a.keys() - b.keys()), len(a.keys() & b.keys()) and len(b.keys() - a.keys())
    (OUT / f"compare_{a_name}__{b_name}.json").write_text(json.dumps(detail, indent=1))
    print(json.dumps({"a": a_name, "b": b_name, "shipments": len(a.keys() & b.keys()), **dict(c)}, indent=1))


if __name__ == "__main__":
    main()
