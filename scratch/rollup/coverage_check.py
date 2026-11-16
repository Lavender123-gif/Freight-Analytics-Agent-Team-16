"""T14-05 check: the deterministic charge-code mapping (src/freight_lineitems/charge_map.py, config/charge_map.yaml)
replayed on a stored run must reproduce T13 section 3.2's five classes (250 / 63 / 620 / 66 / 3 on devFull-4823).

Unit as in T13: one counted amount (CLAIMED/UNPAID; charge, unspecified or tax amount) of one distinct explanation
(shipment, Event Date, text), the model's reading as stored, before any roll-up rule. Amounts with no code are
reported apart. Prints counts only. Run: uv run python scratch/rollup/coverage_check.py [--run devFull-4823]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay  # noqa: E402

from freight_lineitems.charge_map import coverage_class  # noqa: E402
from freight_lineitems.config import RUNS_DIR  # noqa: E402
from freight_lineitems.rollup import explanation_from_result  # noqa: E402

T13_EXPECTED = {1: 250, 2: 63, 3: 620, 4: 66, 5: 3}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="devFull-4823")
    run = replay.find_run(ap.parse_args().run)
    stored = [json.loads(x) for x in (RUNS_DIR / run / "records.jsonl").open()]
    seen, n, money, unnamed = set(), Counter(), Counter(), 0
    for r in stored:
        f, s = r["facts"], r["facts"]["source"]
        k = (s["shipment_key"], s["event_date"], f["text_sha256"])
        if k in seen:
            continue
        seen.add(k)
        for ln in explanation_from_result(r).lines:
            c = coverage_class(ln.codes)
            if c is None:
                unnamed += 1
                continue
            n[c] += 1
            money[c] += abs(ln.amount)
    tot = sum(n.values())
    print(f"run {run}: {len(seen)} distinct explanations, {tot} counted amounts with a code, {unnamed} without")
    for c in range(1, 6):
        print(f"  class {c}: {n[c]:4d} ({n[c] / tot:.1%})  money {money[c]:,.2f}   T13: {T13_EXPECTED[c]}")
    same = all(n[c] == T13_EXPECTED[c] for c in T13_EXPECTED)
    print("reproduces T13 3.2 (250 / 63 / 620 / 66 / 3):", "yes" if same else "NO")
    if run.endswith("devFull-4823") and not same:
        sys.exit(1)


if __name__ == "__main__":
    main()
