"""Agreement of the same records across repeated runs (task 09 stage 3 item 3; user requirement e: by flag type).

Usage: uv run python scratch/autorun/repeat_consistency.py <run_id> <run_id> <run_id> [--json out.json]
- all_same: share of records whose value is identical in every run
- per flag code: among records where the code appeared in at least one run, the share where it appeared in all runs
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from freight_lineitems.config import RUNS_DIR


def load(rid):
    return {json.loads(x)["record_id"]: json.loads(x) for x in (RUNS_DIR / rid / "records.jsonl").read_text().splitlines()}


def reading_key(r):
    rd = r["facts"]["reading"] or {}
    return json.dumps(sorted((j["id"], j["kind"], j["status"], j.get("is_credit"), tuple(j["charge_codes"]))
                             for j in rd.get("numbers", [])))


def main(run_ids, out=None):
    runs = [load(r) for r in run_ids]
    ids = sorted(set.intersection(*[set(r) for r in runs]))
    fields = {
        "recommendation": lambda r: r["judgment"]["recommendation"],
        "first_check": lambda r: r["facts"]["first_check"],
        "final_consistency": lambda r: r["facts"]["delta_consistency"],
        "counted_sum": lambda r: (r["facts"]["claim"] or {}).get("signed_sum"),
        "full_reading (kind/status/credit/codes per number)": reading_key,
        "non_info_flag_set": lambda r: tuple(sorted(f["code"] for f in r["judgment"]["flags"] if f["severity"] != "info")),
    }
    res = {"n_records": len(ids), "runs": run_ids, "all_same": {}}
    for name, fn in fields.items():
        same = sum(len({json.dumps(fn(run[i]), default=str) for run in runs}) == 1 for i in ids)
        res["all_same"][name] = f"{same}/{len(ids)} ({same / len(ids):.0%})"
    per = defaultdict(lambda: [0, 0])
    for i in ids:
        sets = [{f["code"] for f in run[i]["judgment"]["flags"]} for run in runs]
        for code in set().union(*sets):
            per[code][0] += 1
            per[code][1] += all(code in s for s in sets)
    res["flag_stability"] = {c: f"{b}/{a} ({b / a:.0%})" for c, (a, b) in sorted(per.items(), key=lambda x: -x[1][0])}
    print(json.dumps(res, indent=1))
    if out:
        open(out, "w").write(json.dumps(res, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs=3)
    ap.add_argument("--json")
    a = ap.parse_args()
    main(a.runs, a.json)
