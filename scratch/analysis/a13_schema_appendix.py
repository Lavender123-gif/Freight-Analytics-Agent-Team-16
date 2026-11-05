"""Render the schema v0 field tables from docs/analysis/06_schema_v0.yaml into the report appendix.

Run from repo root: uv run --no-project --with pyyaml python scratch/analysis/a13_schema_appendix.py
Replaces everything after the line '<!-- APPENDIX -->' in the report.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "docs/analysis/06_schema_v0.yaml"
REPORT = ROOT / "docs/analysis/06_research_schema_report.zh.md"
READERS = {"reviewer": "审核员", "downstream": "下游", "audit": "审计评估", "model": "模型输入"}
SOURCE = {"excel": "Excel 原样", "code": "代码推算", "model": "模型判断", "reviewer": "审核员决定"}
LAYER = {"raw": "原样", "fact": "事实", "judgment": "判断", "human": "人", "process": "过程"}


def cell(v) -> str:
    s = "可空" if v is True else "不可空" if v is False else str(v)
    return s.replace("|", "\\|").replace("\n", " ")


d = yaml.safe_load(SCHEMA.read_text())
out = ["<!-- APPENDIX -->", "", f"由 `scratch/analysis/a13_schema_appendix.py` 从 `06_schema_v0.yaml` 生成，不手改。", ""]
for name, t in d["tables"].items():
    out += [f"### `{name}`（{LAYER[t['layer']]}）", "", cell(t["purpose"]).strip(), "",
            f"主键：`{', '.join(t['primary_key'])}`" + (f"；外键：{', '.join(f'`{k}` → `{v}`' for k, v in t.get('foreign_keys', {}).items())}" if t.get("foreign_keys") else ""), "",
            "| 字段 | 类型 | 含义 | 读者 | 来源 | 能否为空 | 待定 |", "|---|---|---|---|---|---|---|"]
    for c, f in t["columns"].items():
        out.append(f"| `{c}` | {cell(f['type'])} | {cell(f['meaning']).strip()} | {'、'.join(READERS[r] for r in f['readers'])} | "
                   f"{SOURCE[f['source']]} | {cell(f['nullable'])} | {cell(f.get('pending', ''))} |")
    out.append("")
text = REPORT.read_text()
head = text.split("<!-- APPENDIX -->")[0]
REPORT.write_text(head + "\n".join(out))
print("tables", len(d["tables"]), "columns", sum(len(t["columns"]) for t in d["tables"].values()))
