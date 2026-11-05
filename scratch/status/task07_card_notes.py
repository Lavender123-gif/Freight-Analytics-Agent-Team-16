"""Task 07: mark cards whose current implementation conflicts with the 2026-11-04 decisions.
No colour changes. Line-level edit so comments and layout in cards.yaml stay intact.
Run once from repo root: uv run --no-project --with pyyaml python scratch/status/task07_card_notes.py
"""
from pathlib import Path

import yaml

P = Path(__file__).resolve().parents[2] / "docs/status/cards.yaml"
PRE = ("待改（与 2026-11-04 决定不一致）；", "To revise (conflicts with the 2026-11-04 decisions); ")
HEAD = ("与 2026-11-04 决定不一致，待改：", "Conflicts with the 2026-11-04 decisions, to revise: ")
N = {
    "B01": ("现在按五个字段合并重复行，决定 5.3 要求每份副本独立；没有按 schema v0 存原始行和币种（决定 4.3）。颜色调整 `[建议，待确认]`：改黄，直到按 schema 重做。",
            "rows are merged on five fields, while decision 5.3 keeps every copy as its own record; raw rows and currency are not stored per schema v0 (decision 4.3). Colour `[suggestion, to be confirmed]`: yellow until rebuilt on the schema."),
    "B03": ("整个环节按决定 2.1 删除，所有记录都进模型。颜色调整 `[建议，待确认]`：改灰，注明已按决定删除。",
            "the whole step is removed by decision 2.1; every record goes to the model. Colour `[suggestion, to be confirmed]`: grey, noting it was removed by decision."),
    "B05": ("输入里有 `delta`、`delta_sign`，工具表里有 `reconcile`（决定 3.1）。颜色保持黄。",
            "the input still has `delta` and `delta_sign`, and the tool table has `reconcile` (decision 3.1). Colour stays yellow."),
    "B06": ("`reconcile` 要去掉，可另给计算器（决定 3.3）。颜色保持黄。",
            "`reconcile` goes; a calculator may be added instead (decision 3.3). Colour stays yellow."),
    "B07": ("合计算两次仍是门槛（决定 3.4）；算式引用可选（3.3）；防凑数没覆盖全部状态（3.5）；`contains_number` 仍在（3.8）；费用代码依据没有别名核对（3.6）。颜色保持黄。",
            "total-counted-twice is still a gate (decision 3.4); arithmetic references are optional (3.3); anti-padding does not cover every status (3.5); `contains_number` is still there (3.8); charge-code evidence has no alias check (3.6). Colour stays yellow."),
    "B08": ("历史在批次运行器的内存里累积，没有存解析结果的库，也没有四层查重（决定 4.1、5.2）。颜色保持黄。",
            "history is accumulated in the batch runner's memory; there is no store of parse results and no four-level duplicate check (decisions 4.1, 5.2). Colour stays yellow."),
    "B09": ("推荐仍是 `AUTO_REJECT / HUMAN_REVIEW / SPLIT_TRUSTED`，按分数算（决定 2.3）。颜色保持黄。",
            "outcomes are still `AUTO_REJECT / HUMAN_REVIEW / SPLIT_TRUSTED`, computed by score (decision 2.3). Colour stays yellow."),
    "B10": ("失败提交仍写进内容（决定 3.9）；有自动通知事件（2.2）；没有币种和解析结果库（4.1、4.3）。颜色调整 `[建议，待确认]`：改黄。",
            "failed submissions still land in the content (decision 3.9); there are auto-notice events (2.2); no currency and no parse store (4.1, 4.3). Colour `[suggestion, to be confirmed]`: yellow."),
    "C1": ("有自动通知用的文字（决定 2.2）；`REC.INPUT.EXPORT_DUPLICATE` 要改成行层面查重标识（5.3）。颜色 `[建议，待确认]`：保持浅绿，改完文字后重跑检查。",
           "it has wording for automatic notices (decision 2.2); `REC.INPUT.EXPORT_DUPLICATE` becomes a row-level duplicate flag (5.3). Colour `[suggestion, to be confirmed]`: stays light green; rerun the checks after the wording changes."),
    "C2": ("有 `auto_reject` 段，推荐按分数（决定 2.1、2.3）；缺多层查重规则（5.2）。颜色保持黄。",
           "it has an `auto_reject` section and score-based outcomes (decisions 2.1, 2.3); multi-level duplicate rules are missing (5.2). Colour stays yellow."),
}
A3 = (("部分被 2026-11-04 决定取代；", "Partly superseded by the 2026-11-04 decisions; "),
      ("部分结论被 2026-11-04 决定记录取代（例如 D4 模型前打回、推荐枚举）；本卡记录的是当时的方案，颜色保持浅绿。",
       "Some conclusions are superseded by the 2026-11-04 decision record (for example D4's pre-model auto-reject and the outcome names); this card records the proposal as it was, so it stays light green."))


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


lines = P.read_text(encoding="utf-8").split("\n")
targets = {**{k: (PRE, (HEAD[0] + v[0], HEAD[1] + v[1])) for k, v in N.items()}, "A3": A3}
done = set()
i = 0
out = []
cur = None
state = None
while i < len(lines):
    ln = lines[i]
    if ln.startswith("- id: "):
        cur = ln[6:].strip()
        state = None
    if cur in targets:
        pre, note = targets[cur]
        if ln == "  status_line:":
            state = "status"
        elif state == "status" and ln.startswith("    zh: ") or state == "status" and ln.startswith("    en: "):
            lang = 0 if ln.startswith("    zh: ") else 1
            val = yaml.safe_load(ln[8:])
            ln = ln[:8] + q(pre[lang] + str(val))
            if lang == 1:
                state = None
        elif ln == "  open_items:":
            state = "open"
        elif state == "open" and ln == "    bullets:":
            out.append(ln)
            out.append("    - zh: " + q(note[0]))
            out.append("      en: " + q(note[1]))
            done.add(cur)
            state = None
            i += 1
            continue
        elif state == "open" and ln.startswith("    bullets: []"):
            out += ["    bullets:", "    - zh: " + q(note[0]), "      en: " + q(note[1])]
            done.add(cur)
            state = None
            i += 1
            continue
    if ln.startswith("  updated: "):
        ln = "  updated: '2026-11-04'"
    out.append(ln)
    i += 1
assert done == set(targets), set(targets) - done
text = "\n".join(out)
text = text.replace("    zh: '`docs/tasks/cc_task_04_status_hub.md`（任务 04）'\n    en: '`docs/tasks/cc_task_04_status_hub.md` (task 04)'",
                    "    zh: '`docs/tasks/cc_task_07_status_plan.md`（任务 07）'\n    en: '`docs/tasks/cc_task_07_status_plan.md` (task 07)'")
yaml.safe_load(text)
P.write_text(text, encoding="utf-8")
print("updated", sorted(done))
