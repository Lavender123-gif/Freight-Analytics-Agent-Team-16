"""One-off check (task 04): no information from the task-03 boards was lost in the migration.

Every non-empty line of the legacy boards (data/interim/status_legacy/, git-ignored copies) is
looked up, after stripping Markdown list / heading markers, as a substring of the newly generated
board. Lines that were replaced on purpose are listed in EXPECTED_REPLACED with the reason; any
other line that is not found is reported as a failure.

  uv run --offline --no-project --with pyyaml python scratch/status/migration/check_migration.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
from migrate_from_md import CARD_RE, ITEM_RE, ROW_RE, clean_lead, rename  # noqa: E402

# Legacy lines that were replaced on purpose (prefix match) -> reason.
EXPECTED_REPLACED = {
    "zh": {
        "# 项目状态看板": "标题保留，后面跟生成说明",
        "- **最后更新**": "改为任务 04 的日期",
        "- **更新它的任务**": "改为任务 04",
        "- **中文版为准**": "改写：两版由同一份数据生成",
        "- 流程图（按": "同一句，文件名改为可点击的链接",
        "## 颜色标准": "按任务书第 2 节替换为五色和证据级别",
        "- 🟩 **绿**": "旧颜色标准，已替换",
        "- 🟨 **黄**": "旧颜色标准，已替换",
        "- 🟥 **红**": "旧颜色标准，已替换",
        "- ⬜ **灰**": "旧颜色标准，已替换",
        "来源标注：": "加上\"或任务 04\"",
        "## 总览图": "保留，由 cards.yaml 重新生成",
        "```": "Mermaid 代码块由 cards.yaml 重新生成，连线逐条迁入 overview_edges",
        "| 编号 | 卡片 | 颜色 | 一句话现状 |": "总表加了证据级别和三个链接列",
        "|---|---|---|---|": "总表表头分隔线",
    },
    "en": {
        "# Project status board": "title kept, followed by the generated-file note",
        "- **Last updated**": "task-04 date",
        "- **Updated by task**": "task 04",
        "- **The Chinese version": "rewritten: both generated from the same data",
        "- Pipeline flow (swimlanes": "same sentence, file names are now links",
        "## Colour standard": "replaced by the five colours and evidence levels",
        "- 🟩 **Green**": "old colour standard, replaced",
        "- 🟨 **Yellow**": "old colour standard, replaced",
        "- 🟥 **Red**": "old colour standard, replaced",
        "- ⬜ **Grey**": "old colour standard, replaced",
        "Source tags:": "adds \"or task-04\"",
        "## Overview": "kept, regenerated from cards.yaml",
        "```": "Mermaid block regenerated; edges migrated into overview_edges",
        "| ID | Card | Colour | Status in one line |": "table gained evidence and link columns",
        "|---|---|---|---|": "table header separator",
    },
}
MERMAID_LINE = re.compile(r"^\s*(flowchart|subgraph|end$|[A-Z]\d*\b.*-->|[A-Z]\d+\[|classDef|class )")


def needles(line: str, lang: str) -> list[str]:
    """What must appear in the new board for this legacy line."""
    if m := CARD_RE.match(line):
        return [f"### {m.group(1)} {m.group(2)}"]
    if m := ITEM_RE.match(line):
        lead = rename(clean_lead(m.group(3)), lang)
        return [lead] if lead else []
    if m := ROW_RE.match(line):
        return [f"| {m.group(1)} | {m.group(2)} |", m.group(4)]
    if line.startswith("   - "):
        return [rename(line[5:], lang)]
    return [rename(line.lstrip("#").strip(), lang)]


def main() -> int:
    failures = 0
    for lang in ("zh", "en"):
        old = (ROOT / f"data/interim/status_legacy/project_status.{lang}.md").read_text(encoding="utf-8")
        new = (ROOT / f"docs/status/project_status.{lang}.md").read_text(encoding="utf-8")
        found = replaced = mermaid = 0
        in_mermaid = False
        for line in old.splitlines():
            if not line.strip() or line.strip() == "---":
                continue
            if line.startswith("```"):
                in_mermaid = not in_mermaid
                replaced += 1
                continue
            if in_mermaid:
                if not MERMAID_LINE.match(line):
                    print(f"[{lang}] unexpected line in mermaid block: {line}")
                    failures += 1
                mermaid += 1
                continue
            if any(line.startswith(p) for p in EXPECTED_REPLACED[lang]):
                replaced += 1
                continue
            for n in needles(line, lang):
                if n and n not in new:
                    print(f"[{lang}] NOT FOUND: {n[:120]}")
                    failures += 1
                else:
                    found += 1
        print(f"[{lang}] found {found}, replaced on purpose {replaced}, mermaid lines {mermaid} (checked separately)")
    print("migration check:", "no information lost" if not failures else f"{failures} lines missing")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
