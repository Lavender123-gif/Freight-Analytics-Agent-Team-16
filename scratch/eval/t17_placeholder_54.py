"""Task 17 section 3: the passed dev explanations with a redaction placeholder near an amount. Compare the two stored full
runs (devFull-4823: old redaction, prompt v1.1; devFullV12-5d09: allow-list redaction, v1.2) on amounts, counted or not,
and charge category. Cause per difference: the redacted texts are the same -> version; they differ near the number or
the charge words that changed -> redaction; otherwise -> cannot tell. Report only; nothing changes.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scratch" / "eval"), str(ROOT / "scratch" / "autorun")]
import compare_variants as cv  # noqa: E402
import confusion as C  # noqa: E402
import metrics as M  # noqa: E402

OUT = ROOT / "data" / "interim" / "eval" / "t17"


def main() -> None:
    ex, ships = C.system_view(C.DEV_RUN)
    old = M.load_run(cv.replay.find_run("devFull-4823"))
    picked = []
    for rid, e in ex.items():
        if C.sent(e, ships[e["facts"]["source"]["shipment_key"]]):
            continue
        red = e["facts"].get("text_redacted") or ""
        if any(re.search(r"\d", red[max(0, m.start() - 15): m.end() + 15]) for m in re.finditer(r"\[PERSON_\d+\]", red)):
            picked.append(rid)
    rows, c = [], Counter()
    for rid in picked:
        new_e, old_e = ex[rid], old[rid]
        nv, ov = M.model_view(new_e) or {}, M.model_view(old_e) or {}
        same_table = [n["raw"] for n in new_e["facts"]["number_table"]["numbers"]] == [n["raw"] for n in old_e["facts"]["number_table"]["numbers"]]
        diffs = []
        for nid in sorted(set(nv) | set(ov)):
            a, b = ov.get(nid, {}), nv.get(nid, {})
            for field, x, y in (("is_money", a.get("is_money"), b.get("is_money")), ("claim", a.get("claim3"), b.get("claim3")),
                                ("category", sorted(a.get("categories", [])), sorted(b.get("categories", [])))):
                if x != y:
                    diffs.append({"number_id": nid, "field": field, "old": x, "new": y})
        t_old, t_new = old_e["facts"].get("text_redacted") or "", new_e["facts"].get("text_redacted") or ""
        if not diffs:
            cause = "no_difference"
        elif t_old == t_new:
            cause = "version"
        else:
            changed = [(i1, i2) for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, t_new, t_old).get_opcodes() if tag != "equal"]
            spans = {n["id"]: n["span"] for n in new_e["facts"]["number_table"]["numbers"]}
            near = any(nid in spans and any(abs(spans[nid][0] - i1) <= 25 or abs(spans[nid][1] - i2) <= 25 for i1, i2 in changed)
                       for nid in {d["number_id"] for d in diffs})
            cause = "redaction" if near else "cannot_tell"
        c[cause] += 1
        for d in diffs:
            c[f"field:{d['field']}"] += 1
        rows.append({"record_id": rid, "cause": cause, "same_number_table": same_table, "diffs": diffs,
                     "redacted_text_changed": t_old != t_new})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "placeholder_54.json").write_text(json.dumps(rows, indent=1, default=str))
    print(json.dumps({"records": len(picked), **dict(c), "redacted_text_changed": sum(r["redacted_text_changed"] for r in rows)}, indent=1))


if __name__ == "__main__":
    main()
