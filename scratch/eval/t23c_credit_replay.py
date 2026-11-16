"""Task 23c section 3 item 2: rerun the T23b replay (scratch/eval/t23b_credit_replay.py) with money-like local-scope
boundaries and compare with the stored T23b result (data/interim/eval/t23b/credit_replay.json). No model call.

Lists every flagged number that appears or disappears per run, by (record_id, id, outcome). "newly to a person" =
the reading had no sign flag under T23b and its stored recommendation was PASSED_CHECKS.
Output: data/interim/eval/t23c/credit_replay.json (git-ignored). Rows hold ids and amounts, no text.
Usage: uv run python scratch/eval/t23c_credit_replay.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t23b_credit_replay import RUNS, replay  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "data" / "interim" / "eval" / "t23b" / "credit_replay.json"
OUT = ROOT / "data" / "interim" / "eval" / "t23c"
KINDS = ("refused", "minus", "mark")


def keys(o: dict) -> dict:
    return {(x["record_id"], x["id"], k): x for k in KINDS for x in o[k]}


def main() -> None:
    old = json.loads(OLD.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, run in RUNS.items():
        new = replay(run) | {"run": run}
        ko, kn = keys(old[name]), keys(new)
        added = [kn[k] | {"outcome": k[2]} for k in sorted(kn.keys() - ko.keys())]
        removed = [ko[k] | {"outcome": k[2]} for k in sorted(ko.keys() - kn.keys())]
        old_recs = {k[0] for k in ko}
        newly = sorted({x["record_id"] for x in added if x["record_id"] not in old_recs
                        and x["recommendation_before"] == "PASSED_CHECKS" and x["outcome"] in KINDS})
        res[name] = new | {"added": added, "removed": removed, "newly_to_person": newly}
        counts = lambda o: " / ".join(str(len(o[k])) for k in KINDS)  # noqa: E731
        print(f"{name}: readings {new['readings']}; refused/minus/mark T23b {counts(old[name])} -> T23c {counts(new)}; "
              f"added {len(added)}, removed {len(removed)}, readings newly to a person {len(newly)}")
        for x in added:
            print("  +", x)
        for x in removed:
            print("  -", x)
    (OUT / "credit_replay.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
