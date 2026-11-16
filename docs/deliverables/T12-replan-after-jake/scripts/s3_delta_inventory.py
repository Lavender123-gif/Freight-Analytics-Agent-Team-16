"""T12 stocktake 2.1(4)(9): where Delta / Invoice Amount / Invoice Dups Removed are used today.

Read-only. Counts only. Covers: tracked source, config, skill, tests, scripts, status cards; the 88 boundary cases
(git-ignored copy under data/external/codex_boundary/); the PUBLIC mock and its ground truth (data/external/mock_public/).
The held-out mock is not read.

Run: uv run python docs/deliverables/T12-replan-after-jake/scripts/s3_delta_inventory.py
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict

import yaml

from freight_lineitems.config import ROOT

PAT = re.compile(r"delta|invoice[ _]amount|invoice_amt|dups[ _]removed|invoice dups", re.I)
DELTA_CODES = re.compile(r"^(CLAIM\.DELTA\.|CLAIM\.RECON\.SUM_MISMATCH|REC\.FIELD\.DELTA_|HIST\.)")


def tracked_hits() -> None:
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    by_area: dict[str, Counter] = defaultdict(Counter)
    for f in files:
        if not f or f.endswith((".png", ".pptx", ".lock", ".txt", ".html")) or f.startswith("docs/deliverables/T12-"):
            continue
        try:
            n = sum(1 for line in (ROOT / f).read_text(errors="ignore").splitlines() if PAT.search(line))
        except (IsADirectoryError, FileNotFoundError):
            continue
        if n:
            area = f.split("/")[0] if "/" in f else "(root)"
            if area in ("docs", "scratch"):
                area = "/".join(f.split("/")[:2])
            by_area[area][f] = n
    print("== tracked files: lines mentioning Delta / Invoice Amount / Invoice Dups Removed")
    for area in sorted(by_area):
        c = by_area[area]
        print(f"{area}: {sum(c.values())} lines in {len(c)} files")
        for f, n in c.most_common(40):
            print(f"    {n:4d}  {f}")


def boundary() -> None:
    p = ROOT / "data" / "external" / "codex_boundary" / "rules_and_diagnostics.jsonl"
    cases = [json.loads(line) for line in p.read_text().splitlines()]
    dep = [c for c in cases if any(DELTA_CODES.match(d) for d in c["expected_diagnostics"]) or DELTA_CODES.match(c["target_rule"])
           or "delta" in c["target_rule"].lower()]
    codes = Counter(d for c in cases for d in c["expected_diagnostics"] if DELTA_CODES.match(d))
    zero = [c for c in cases if c["input_record"].get("Delta") in ("0", "0.00", "0.0")]
    print(f"\n== boundary cases: {len(cases)} total; {len(dep)} target or expect a Delta-dependent / history diagnostic")
    print("   expected Delta-dependent codes:", dict(codes))
    print("   target rules of those cases:", dict(Counter(c["target_rule"] for c in dep)))
    print("   ids:", " ".join(c["case_id"] for c in dep))
    print("   cases whose input Delta is 0:", len(zero))
    hist = [c for c in cases if c["target_rule"].startswith("HIST") or "history" in c["target_rule"].lower()]
    print("   history-rule cases:", len(hist), dict(Counter(c["target_rule"] for c in hist)))
    dup = [c for c in cases if "DUP" in c["target_rule"] or "DUPLICATE" in c["target_rule"]]
    print("   duplicate-rule cases:", len(dup), dict(Counter(c["target_rule"] for c in dup)))
    cur = [c for c in cases if "CURRENCY" in json.dumps(c) or "TAX" in c["target_rule"]]
    print("   tax / currency cases:", len(cur), dict(Counter(c["target_rule"] for c in cur)))


def mock() -> None:
    d = ROOT / "data" / "external" / "mock_public"
    rows = [json.loads(line) for line in (d / "mock_records.jsonl").read_text().splitlines()]
    gt = [json.loads(line) for line in (d / "ground_truth.jsonl").read_text().splitlines()]
    print(f"\n== public mock: {len(rows)} rows, {len(gt)} events")
    print("   claim.sum_equals_delta:", dict(Counter(str(g["claim"].get("sum_equals_delta")) for g in gt)))
    not_eq = Counter(g["failure_mode"] for g in gt if g["claim"].get("sum_equals_delta") is False)
    print("   failure modes with sum_equals_delta = false:", dict(not_eq))
    print("   events with more than one row (expected_dedup or row_ids):", sum(1 for g in gt if len(g["row_ids"]) > 1),
          dict(Counter(g["failure_mode"] for g in gt if len(g["row_ids"]) > 1)))
    print("   events with a prior event (history_relation.has_prior):", sum(1 for g in gt if g["history_relation"]["has_prior"]),
          dict(Counter(g["history_relation"]["relation"] for g in gt)))
    ship = Counter(r["shipment_id"] for r in rows)
    print("   shipments:", len(ship), "| shipments with 2+ rows:", sum(1 for v in ship.values() if v > 1))
    print("   row currency values:", dict(Counter(r.get("currency") for r in rows)))
    print("   rows with delta == 0:", sum(1 for r in rows if float(r["delta"]) == 0),
          "| rows where invoice_amount - shipment_amount != delta:",
          sum(1 for r in rows if abs(float(r["invoice_amount"]) - float(r["shipment_amount"]) - float(r["delta"])) > 0.005))
    kw = re.compile(r"delta|arithmetic|history|dedup|currency|tax", re.I)
    fam = Counter(g["failure_mode"] for g in gt if kw.search(g["failure_mode"]))
    print("   failure modes named after Delta arithmetic / history / dedup / currency / tax:", sum(fam.values()), dict(fam))
    rec = defaultdict(Counter)
    for g in gt:
        if kw.search(g["failure_mode"]):
            rec[g["failure_mode"]][g["expected_recommendation"]] += 1
    for k in sorted(rec):
        print(f"      {k}: {dict(rec[k])}")
    txt = Counter()
    for g in gt:
        s = json.dumps(g["ground_truth_issue"], ensure_ascii=False) + g["failure_mode_description"]
        if re.search(r"delta", s, re.I):
            txt[g["failure_mode"]] += 1
    print("   events whose description or ground-truth issue text mentions Delta:", sum(txt.values()), dict(txt))


def cards() -> None:
    doc = yaml.safe_load((ROOT / "docs" / "status" / "cards.yaml").read_text())
    items = doc["cards"] if isinstance(doc, dict) and "cards" in doc else doc
    if isinstance(items, dict):
        items = [{"id": k} | (v if isinstance(v, dict) else {"value": v}) for k, v in items.items()]
    print(f"\n== status cards: {len(items)}")
    for c in items:
        s = json.dumps(c, ensure_ascii=False)
        n = len(PAT.findall(s))
        if n:
            print(f"   {c.get('id')}  mentions={n}  status={c.get('status') or c.get('color')}  title={str(c.get('title') or c.get('name'))[:50]}")


if __name__ == "__main__":
    tracked_hits()
    boundary()
    mock()
    cards()
