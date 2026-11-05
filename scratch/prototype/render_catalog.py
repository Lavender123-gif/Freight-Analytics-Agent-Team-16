"""Render diagnostics_catalog.yaml + rules.yaml as the markdown tables in report section 4.

Run: uv run --with pyyaml python scratch/prototype/render_catalog.py > /tmp/catalog.md
"""

import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
cat = yaml.safe_load((HERE / "diagnostics_catalog.yaml").read_text())
rules = yaml.safe_load((HERE / "rules.yaml").read_text())["flags"]
NAMES = {"REC": "记录（REC）", "NUM": "数字（NUM）", "ITEM": "line item（ITEM）", "CLAIM": "主张汇总（CLAIM）",
         "HIST": "与同一票货其他记录的关系（HIST）", "RUN": "处理过程（RUN）"}

codes = [c for c in cat if c != "version"]
for prefix, title in NAMES.items():
    rows = [c for c in codes if c.startswith(prefix + ".")]
    print(f"\n#### {title}\n")
    print("| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for c in rows:
        d = cat[c]
        r = rules.get(c)
        sev = f"{r['severity']} / {r['role']}{' +' + str(r['points']) if r.get('points') else ''}" if r else "不生成 flag"
        cell = lambda x: (str(x) if x not in (None, "") else "无").replace("|", "\\|")  # noqa: E731
        print(f"| `{c}` | {cell(d['trigger'])} | {cell(d['evidence'])} | {d['step']} | "
              f"{'退回' if d['handling'] == 'return' else '只记录'} | {sev} | {cell(d['reviewer'])} | "
              f"{cell(d['carrier_fix'])} | {cell(d['acceptance'])} |")
print(f"\n共 {len(codes)} 种：退回 {sum(cat[c]['handling'] == 'return' for c in codes)} 种，只记录 "
      f"{sum(cat[c]['handling'] == 'record' for c in codes)} 种。", file=sys.stderr)
missing = [c for c in codes if cat[c]["handling"] == "record" and c not in rules]
assert not missing, missing
