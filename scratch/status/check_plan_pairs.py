"""Task 07: check each docs/plan/*.zh.md against its .en.md (same method as task 04's check_report_pairs.py):
same counts of headings, table rows, bullets, code fences; same multiset of numbers; same backticked tokens.
Mermaid blocks are compared by fence count only (labels are translated).
  uv run --no-project python scratch/status/check_plan_pairs.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_report_pairs import profile  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# Task 08: these plan files are Chinese only by design (no .en.md this round).
ZH_ONLY = {"2026-11-05_workload_v2.zh.md", "2026-11-05_debrief.zh.md"}


def norm_ticks(c):
    from collections import Counter
    tags = {"[to be discussed]": "[待讨论]", "[pending Jake]": "[待 Jake]"}  # tags translated by design
    return Counter({tags.get(k, k).replace(".zh.md", ".X.md").replace(".en.md", ".X.md").replace(".zh.html", ".X.html")
                    .replace(".en.html", ".X.html"): v for k, v in c.items()})


bad = 0
pairs = sorted(ROOT.glob("docs/plan/*.zh.md"))
for zh in pairs:
    en = zh.with_name(zh.name.replace(".zh.md", ".en.md"))
    if zh.name in ZH_ONLY:
        print(f"{zh.name}: zh only (task 08), skipped"); continue
    if not en.exists():
        print(f"{zh.name}: MISSING {en.name}"); bad += 1; continue
    a, b = profile(zh.read_text()), profile(en.read_text())
    a["ticks"], b["ticks"] = norm_ticks(a["ticks"]), norm_ticks(b["ticks"])
    probs = [f"{k} zh={a[k]} en={b[k]}" for k in ("headings", "table_rows", "bullets", "code_fences") if a[k] != b[k]]
    for k in ("numbers", "ticks"):
        oz, oe = a[k] - b[k], b[k] - a[k]
        if oz or oe:
            probs.append(f"{k} only-zh={dict(oz)} only-en={dict(oe)}")
    print(f"{zh.name}: {'OK' if not probs else 'DIFF'}")
    for p in probs:
        print("   ", p)
    bad += bool(probs)
print(f"{len(pairs)} pairs, {bad} with differences")
sys.exit(1 if bad else 0)
