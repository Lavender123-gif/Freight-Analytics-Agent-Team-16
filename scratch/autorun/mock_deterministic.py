"""Public mock (360 events, 375 rows) through the deterministic layer only: duplicates, redaction, injection, number
recognition, text checks. No model. Compares with the mock's ground truth and writes mismatches (synthetic data, so
the summary can be tracked; the row list stays in data/interim/).

Run: uv run python scratch/autorun/mock_deterministic.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal

from freight_lineitems import duplicates
from freight_lineitems.config import ROOT
from freight_lineitems.pipeline import assemble, prepare
from freight_lineitems.records import MOCK_DIR, load_mock

GT = [json.loads(x) for x in (MOCK_DIR / "ground_truth.jsonl").read_text().splitlines()]
OUT = ROOT / "data" / "interim" / "autorun" / "mock_deterministic.json"


def main():
    recs = load_mock()
    by_row = {r.raw["row_id"]: r for r in recs}
    preps = {r.record_id: prepare(r) for r in recs}
    results = [assemble(preps[r.record_id], None) for r in recs]
    results = duplicates.apply(recs, results)
    res = {x["record_id"]: x for x in results}
    codes = lambda rid: {f["code"] for f in res[rid]["judgment"]["flags"]}  # noqa: E731
    checks = defaultdict(Counter)
    misses = []

    def record(check, ok, ev, detail):
        checks[check]["pass" if ok else "fail"] += 1
        if not ok:
            misses.append({"check": check, "mock_id": ev["mock_id"], "failure_mode": ev["failure_mode"], **detail})

    for ev in GT:
        rows = [by_row[r] for r in ev["row_ids"]]
        rids = [r.record_id for r in rows]
        p = preps[rids[0]]
        red = p["redacted"]
        # duplicates: the mock expects merging into expected_dedup events; we flag copies instead (decision 5.3)
        if len(rows) > 1:
            flagged = sum("DUP.ROW.COPY" in codes(x) for x in rids)
            merge_expected = len(rows) - ev["expected_dedup"]
            record("duplicates: later copies flagged (mock expects merge)", flagged == merge_expected, ev,
                   {"rows": len(rows), "expected_merged_away": merge_expected, "flagged_copies": flagged})
        # PII
        for pii in ev["pii"]:
            sub = pii.get("substring") or pii.get("text") or ""
            record("redaction: PII substring removed", sub not in red, ev, {"pii_type": pii.get("type"), "left_in_text": sub in red})
        # injection
        if ev["injection"]["present"]:
            record("injection: flagged", "REC.TEXT.INJECTION_SUSPECT" in codes(rids[0]), ev, {})
        elif ev["is_control"]:
            record("injection: no false flag on controls", "REC.TEXT.INJECTION_SUSPECT" not in codes(rids[0]), ev, {})
        # numbers
        table = [(n.raw, n.value) for n in p["parse"].numbers]
        unrec = [u.raw for u in p["parse"].unrecognized]
        for n in ev["numbers"]:
            sub = n["substring"]
            try:
                val = Decimal(str(n["value"]))
            except Exception:  # noqa: BLE001 - dates, times, references are strings in the mock
                val = None
            hit = any(sub.replace("$", "").strip() in raw or raw.replace("$", "").strip() in sub for raw, _ in table)
            good = any(abs(abs(v) - abs(val)) < Decimal("0.005") for raw, v in table if sub.replace("$", "").strip() in raw
                       or raw.replace("$", "").strip() in sub)
            in_unrec = any(sub.strip("$ ") in u or u.strip(";,.:") in sub for u in unrec)
            redacted_away = sub not in red
            if n.get("is_money") and val is not None:
                record("numbers: money value read correctly", good, ev, {"substring": sub, "value": str(val),
                       "found_tokens": [r for r, _ in table], "in_unrecognized": in_unrec})
            else:
                record("numbers: non-money digits covered (number, date, region or redacted)", hit or in_unrec or redacted_away or
                       any(sub in d.raw or d.raw in sub for d in p["parse"].dates), ev, {"substring": sub})
        # text checks
        if ev["failure_mode"] == "understanding_blank":
            record("text: empty text flagged", "REC.TEXT.EMPTY" in codes(rids[0]), ev, {})
        if ev["failure_mode"] == "understanding_only_number":
            record("text: numbers-only flagged", "REC.TEXT.NUMBERS_ONLY" in codes(rids[0]), ev, {})
        if ev["is_control"] and len(rows) == 1:
            bad = [c for c in codes(rids[0]) if c.startswith(("REC.TEXT", "DUP."))]
            record("controls: no text or duplicate flag", not bad, ev, {"flags": bad})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"checks": {k: dict(v) for k, v in checks.items()}, "misses": misses}, indent=1, default=str))
    for k, v in checks.items():
        print(f"{k:62s} pass {v['pass']:4d}  fail {v['fail']:3d}")
    print("misses by failure_mode:", dict(Counter(m["failure_mode"] for m in misses)))


if __name__ == "__main__":
    main()
