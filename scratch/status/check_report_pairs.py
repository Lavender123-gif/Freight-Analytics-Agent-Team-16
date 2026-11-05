"""Check that every test_report.zh.md and its test_report.en.md under docs/deliverables/ match in
structure and facts: same number of headings, table rows, bullets and code blocks; the same
multiset of numbers; the same set of backticked tokens.

  uv run --no-project python scratch/status/check_report_pairs.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NUM = re.compile(r"(?<![A-Za-z_#./])\d+(?:\.\d+)?")
TICK = re.compile(r"`([^`]+)`")
LINK = re.compile(r"\]\([^)]*\)")


FENCE = re.compile(r"^```.*?^```", re.S | re.M)


def profile(text: str) -> dict:
    lines = text.splitlines()
    code = [l.split("#")[0].rstrip() for blk in FENCE.findall(text) for l in blk.splitlines()]
    body = LINK.sub("]", FENCE.sub("", text))  # link targets differ by language (.zh/.en)
    ticks = Counter(t.replace("test_report.zh.md", "X").replace("test_report.en.md", "X")
                    .replace("README.zh.md", "R").replace("README.en.md", "R")
                    .replace("project_status.zh.md", "P").replace("project_status.en.md", "P")
                    for t in TICK.findall(body)
                    if "建议" not in t and "suggestion" not in t)
    return {
        "headings": sum(1 for l in lines if l.startswith("#")),
        "table_rows": sum(1 for l in lines if l.startswith("|")),
        "bullets": sum(1 for l in lines if re.match(r"^\s*(-|\d+\.) ", l)),
        "code_fences": sum(1 for l in lines if l.startswith("```")),
        "numbers": Counter(NUM.findall(TICK.sub("", body))),
        "ticks": ticks,
        "code": code,
    }


def main() -> int:
    bad = 0
    pairs = sorted(ROOT.glob("docs/deliverables/*/test_report.zh.md"))
    for zh in pairs:
        en = zh.with_name("test_report.en.md")
        name = zh.parent.name
        if not en.exists():
            print(f"{name}: MISSING test_report.en.md")
            bad += 1
            continue
        a, b = profile(zh.read_text(encoding="utf-8")), profile(en.read_text(encoding="utf-8"))
        problems = []
        for k in ("headings", "table_rows", "bullets", "code_fences", "code"):
            if a[k] != b[k]:
                problems.append(f"{k} zh={a[k]} en={b[k]}")
        for k in ("numbers", "ticks"):
            only_zh, only_en = a[k] - b[k], b[k] - a[k]
            if only_zh or only_en:
                problems.append(f"{k} only-zh={dict(only_zh)} only-en={dict(only_en)}")
        print(f"{name}: {'OK' if not problems else 'DIFF'}")
        for p in problems:
            print("   ", p)
        bad += bool(problems)
    print(f"{len(pairs)} pairs, {bad} with differences")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
