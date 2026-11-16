"""T13 step 2.5: a DRAFT of 'the client's list plus our definitions'. It does not replace config/taxonomy.yaml
and nothing in src/ reads it.

One row per entry:
  - every name on the client's list (root), with all its EDI codes, the codes of ours that map to it, and the
    definition and phrasings carried over from our taxonomy
  - our sub-items (CHILD) and extensions (NONE), marked as such, with the entry they hang under
Definitions of client-only entries are left empty: the task allows a drafted definition only for entries that
took a phrasing out of OTHER, and step 2.3 found none.

Needs the outputs of s1 and s2 in data/interim/deliverables/T13/ (git-ignored); writes there as well.
Run: uv run python docs/deliverables/T13-taxonomy-mapping/scripts/s3_draft.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t13_mapping as m  # noqa: E402

from freight_lineitems.config import CODES, ROOT  # noqa: E402

OUT = ROOT / "data" / "interim" / "deliverables" / "T13"
COLS = ["role", "name", "hangs_under", "edi_codes", "our_codes", "relation", "definition", "definition_source",
        "phrasings", "relevance", "dev_amounts"]
GROUP_ZH = {"ROAD_POSSIBLE": "公路运输可能用得上"}


def main() -> None:
    with (OUT / "addenda_b_names.csv").open() as f:
        names = {r["name"]: r["edi_codes"] for r in csv.DictReader(f)}
    with (OUT / "unused_names.csv").open() as f:
        group = {r["name"]: r["group"] for r in csv.DictReader(f)}
    per_code = json.loads((OUT / "coverage.json").read_text())["per_code"]

    on_name = defaultdict(list)                       # client name -> [(our code, type)]
    for code, (typ, ns, _p, _w) in m.MAPPING.items():
        if typ in (m.EXACT, m.APPROX, m.ONE_TO_MANY):
            for n in ns:
                on_name[n].append((code, typ))
    rows = []
    for n in sorted(names, key=str.upper):
        hits = on_name.get(n, [])
        if n in m.used_names():
            rel = "被我们的代码用到" if hits or any(n in v[1] for v in m.MAPPING.values()) else "被我们的代码用到（仅作为扩展项的上级）"
        else:
            rel = GROUP_ZH.get(group[n], "与这批数据无关")
        # a definition is carried over only where the entry and our code mean the same charge
        same = [c for c, t in hits if t in (m.EXACT, m.APPROX)]
        many = [c for c, t in hits if t == m.ONE_TO_MANY]
        if same:
            definition, src = "; ".join(CODES[c]["definition"] for c in same), "我们的单子"
        elif many:
            definition, src = "; ".join(CODES[c]["definition"] for c in many), "我们的单子（一对多：这条定义同时挂在其他候选条目上，需要拆细）"
        else:
            definition, src = "", ""
        rows.append({"role": "清单原有", "name": n, "hangs_under": "", "edi_codes": names[n],
                     "our_codes": " ".join(c for c, _ in hits), "relation": " ".join(m.TYPE_ZH[t] for _, t in hits),
                     "definition": definition, "definition_source": src,
                     "phrasings": "; ".join(p for c, _ in hits for p in CODES[c]["phrasings"]),
                     "relevance": rel, "dev_amounts": sum(per_code[c]["n"] for c, _ in hits) if hits else ""})
    for code, (typ, ns, ext_parent, _w) in m.MAPPING.items():
        if typ not in (m.CHILD, m.NONE):
            continue
        parent = ns[0] if typ == m.CHILD else (ext_parent or "")
        rows.append({"role": "子项" if typ == m.CHILD else "扩展项（非清单原有）", "name": code, "hangs_under": parent or "（不挂，放在顶层）",
                     "edi_codes": "", "our_codes": code, "relation": m.TYPE_ZH[typ], "definition": CODES[code]["definition"],
                     "definition_source": "我们的单子", "phrasings": "; ".join(CODES[code]["phrasings"]),
                     "relevance": "被我们的代码用到", "dev_amounts": per_code[code]["n"]})

    with (OUT / "jake_rooted_draft.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    md = ["# 草稿：以 Jake 的清单为根，挂上我们的定义和写法示例（T13，不替换 taxonomy.yaml）", "",
          "| 角色 | 名称 | 挂在 | EDI 代码 | 我们的代码 | 关系 | 定义 | 写法示例 | 相关度 | 开发集次数 |", "|---|---|---|---|---|---|---|---|---|---|"]
    md += ["| " + " | ".join(str(r[c]).replace("|", "/") for c in
                             ["role", "name", "hangs_under", "edi_codes", "our_codes", "relation", "definition", "phrasings", "relevance", "dev_amounts"]) + " |"
           for r in rows]
    (OUT / "jake_rooted_draft.md").write_text("\n".join(md) + "\n")
    summary = {"rows": len(rows), "by_role": dict(Counter(r["role"] for r in rows)),
               "list_entries_by_relevance": dict(Counter(r["relevance"] for r in rows if r["role"] == "清单原有")),
               "list_entries_with_definition": sum(1 for r in rows if r["role"] == "清单原有" and r["definition"]),
               "list_entries_without_definition": sum(1 for r in rows if r["role"] == "清单原有" and not r["definition"]),
               "drafted_by_cc": 0}
    (OUT / "draft_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
