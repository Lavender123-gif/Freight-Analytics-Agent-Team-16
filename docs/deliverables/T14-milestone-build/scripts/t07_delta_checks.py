"""T14-07: the two checks on withdrawing the runtime Delta comparison (task 14 section 2).

1. For each of the nine withdrawn flags: on the stored full dev run, how many rows carried it, and which flags that do
   not depend on Delta (rules v1.2) are present on those same rows. Also confirms that the signal 'a $ amount in the
   text was left out of the claim' still exists (NUM.JUDGMENT.DOLLAR_EXCLUDED / EXCLUSION_BASIS_UNLISTED).
2. The rows whose recommendation becomes 'return' only because the Delta flags are withdrawn: key, return flag,
   withdrawn flags, and whether the text is empty or numbers-only (the only two cases code may return).
Read-only, no model call. Prints counts and record keys (dev#rN) only, never text.
Run: uv run python docs/deliverables/T14-milestone-build/scripts/t07_delta_checks.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from freight_lineitems.config import ROOT, RULES, RUNS_DIR

sys.path.insert(0, str(ROOT / "scratch" / "rollup"))
import replay  # noqa: E402

RUN = "20261110-195411-devFull-4823"
NINE = ["CLAIM.DELTA.FIRST_MISMATCH", "CLAIM.DELTA.MATCH_AFTER_REVISION", "CLAIM.DELTA.MISMATCH_INSISTED",
        "CLAIM.DELTA.MISMATCH_UNRESOLVED", "CLAIM.DELTA.TOTAL_COUNTED_TWICE_PATTERN", "CLAIM.DELTA.DIFFERENCE_MATCHES_AMOUNTS",
        "REC.FIELD.DELTA_ZERO", "REC.FIELD.DELTA_MISSING", "REC.FIELD.DELTA_NEGATIVE"]


def main() -> None:
    recs = [json.loads(x) for x in (RUNS_DIR / RUN / "records.jsonl").open()]
    out = {"run": RUN, "rows": len(recs), "per_flag": {}}
    sev = {k: v["severity"] for k, v in RULES["flags"].items()}
    for code in NINE:
        rows = [r for r in recs if any(d["code"] == code for d in r["judgment"]["diagnostics"])]
        co = Counter()
        still_attention = 0
        for r in rows:
            j = replay.recolour(r)
            att = [f["code"] for f in j["flags"] if f["severity"] == "attention"]
            still_attention += bool(att) or j["recommendation"] == "RETURN_SUGGESTED"
            for f in j["flags"]:
                if f["severity"] in ("attention", "return"):
                    co[f["code"]] += 1
        out["per_flag"][code] = {"rows": len(rows), "rows_still_human_or_return_v12": still_attention,
                                 "co_flags_v12": dict(co.most_common(8))}
    present = Counter(d["code"] for r in recs for d in r["judgment"]["diagnostics"])
    out["dollar_excluded_signal"] = {c: {"rules_v12_severity": sev.get(c), "rows_on_run": present.get(c, 0)}
                                     for c in ("NUM.JUDGMENT.DOLLAR_EXCLUDED", "NUM.JUDGMENT.EXCLUSION_BASIS_UNLISTED",
                                               "CLAIM.RECON.TOTAL_MISMATCH")}
    # check 2
    text = {r.record_id: r.text_raw for r in replay.load_dev()}
    extra = []
    for r in recs:
        before = r["judgment"]["recommendation"]
        after = replay.row_colour(r, replay.DELTA, True)
        if after == "RETURN_SUGGESTED" and before != "RETURN_SUGGESTED":
            t = (text[r["record_id"]] or "").strip()
            extra.append({"record": r["record_id"], "before": before,
                          "return_flags": sorted({d["code"] for d in r["judgment"]["diagnostics"] if sev.get(d["code"]) == "return"}),
                          "withdrawn_flags": sorted({d["code"] for d in r["judgment"]["diagnostics"] if d["code"].startswith(replay.DELTA)}),
                          "text_empty": t == "", "numbers_only": bool(t) and not re.search(r"[A-Za-z]", t)})
    out["returns_before"] = sum(r["judgment"]["recommendation"] == "RETURN_SUGGESTED" for r in recs)
    out["returns_after_C1"] = out["returns_before"] + len(extra)
    out["extra_returns"] = extra
    out["all_extra_are_empty_or_numbers_only"] = all(e["text_empty"] or e["numbers_only"] for e in extra)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
