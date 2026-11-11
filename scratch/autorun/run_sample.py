"""Run the full pipeline on a stratified dev sample or the public mock.

Usage:
  uv run python scratch/autorun/run_sample.py stage1 --n 24 --seed 9
  uv run python scratch/autorun/run_sample.py devA --n 100 --seed 101 --exclude-runs <run_id> ...
Prints aggregates only. Row-level output: data/interim/runs/<run_id>/records.jsonl (git-ignored).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from freight_lineitems import budget
from freight_lineitems.config import RUNS_DIR
from freight_lineitems.pipeline import run_batch
from freight_lineitems.records import load_dev, load_mock
from freight_lineitems.sampling import stratified, style
from freight_lineitems.tools import load_examples


def used_ids(run_ids: list[str]) -> set[str]:
    ids = set()
    for rid in run_ids:
        for line in (RUNS_DIR / rid / "records.jsonl").read_text().splitlines():
            ids.add(json.loads(line)["record_id"])
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--source", default="dev", choices=["dev", "mock"])
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=9)
    ap.add_argument("--exclude-runs", nargs="*", default=[])
    ap.add_argument("--ids-file", default=None, help="run exactly these record ids (one per line)")
    ap.add_argument("--est", type=float, default=0.04, help="estimated USD per record, for the budget check")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    if a.source == "mock":
        recs = load_mock()
    else:
        dev = load_dev()
        ex = load_examples()
        ex_ids = {e["record_id"] for e in ex}
        ex_ship = {e["shipment_key"] for e in ex}
        if a.ids_file:
            want = [x.strip() for x in open(a.ids_file) if x.strip()]
            byid = {r.record_id: r for r in dev}
            recs = [byid[i] for i in want]
        else:
            recs = stratified(dev, a.n, a.seed, exclude_ids=ex_ids | used_ids(a.exclude_runs), exclude_shipments=ex_ship)
    print(f"records {len(recs)}; spent so far ${budget.spent_usd():.4f}")
    print("styles", dict(Counter(style(r.text_raw) for r in recs)))
    print("carriers", len({r.carrier for r in recs}))
    run_id, res = run_batch(recs, a.name, a.est, workers=a.workers)
    print("run_id", run_id)
    print("recommendation", dict(Counter(r["judgment"]["recommendation"] for r in res)))
    print("parse_status", dict(Counter(r["facts"]["parse_status"] for r in res)))
    print("delta_consistency", dict(Counter(r["facts"]["delta_consistency"] for r in res)))
    print("first_check", dict(Counter(r["facts"]["first_check"] for r in res)))
    print("spent now", f"${budget.spent_usd():.4f}")


if __name__ == "__main__":
    main()
