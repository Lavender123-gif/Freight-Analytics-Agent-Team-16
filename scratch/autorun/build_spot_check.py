"""Write docs/autorun/acceptance/spot_check.zh.md from summary.json (record ids and flag codes only, no text)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_run import load  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
s = json.load(open(ROOT / "data/interim/autorun/acceptance/summary.json"))
runs = {"A": s["runs"]["A"], "B2": s["runs"]["B"], "第一批": "20261110-171337-stage1-1cc1"}
data = {k: {r["record_id"]: r for r in load(v)} for k, v in runs.items()}
ZH = {"PASSED_CHECKS": "解析通过检查", "HUMAN_REVIEW": "建议人工审核", "RETURN_SUGGESTED": "建议退回承运商"}
rows = []
for n, it in enumerate(s["spot_check"]["records"], 1):
    rid, why = it["record_id"], "；".join(it["why"])
    k = "第一批" if why.startswith("stage-1") else ("A" if rid in data["A"] else "B2")
    r = data[k][rid]
    anchor = f"{runs[k]}__{rid.replace('#', '-')}"
    why = (why.replace("recommendation ", "推荐 ").replace("flag ", "标识 ")
           .replace("stage-1 RETURN_SUGGESTED (user req. e)", "第一批建议退回（用户要求 e）"))
    for e, z in ZH.items():
        why = why.replace(e, z)
    rows.append(f"| {n} | `{rid}` | 样本 {k} | {ZH[r['judgment']['recommendation']]} | "
                f"{', '.join(r['judgment']['decisive_flags']) or '—'} | {why} | `results.html#{anchor}` |")
txt = f"""# 抽查清单（任务 09 验收包第 3 项）

**抽样规则**（事先定、按规则抽，不是挑表现好的；随机种子 20261110，脚本 `scratch/autorun/acceptance_summary.py`）：
1. 从样本 A ∪ B2 的最终运行里，每种建议各随机抽 4 条（不足 4 条时全取）；
2. 在 A ∪ B2 里出现最多的 7 种非提示类标识，每种随机抽 1 条（不重复已抽到的）；
3. 第一批（停点一）里 2 条建议退回的记录全部放进来（用户 11-10 要求 e；其中 1 条第 1 步已经抽到）。

共 {len(rows)} 条。定位：用浏览器打开 `data/interim/autorun/acceptance/results.html`，在地址后加最后一列的锚点，或在页面里搜索 record_id。页面显示脱敏原文、模型每次尝试的读法、标识、首次是否不一致。

看的时候请记下：模型读法对不对（每个数字）、颜色是否合理、标识有没有误报或漏报。不需要判断该不该付。

| # | 记录 | 所在运行 | 推荐 | 决定颜色的标识 | 为什么被抽到 | 结果页锚点 |
|---|---|---|---|---|---|---|
""" + "\n".join(rows) + "\n"
(ROOT / "docs/autorun/acceptance/spot_check.zh.md").write_text(txt)
print(len(rows))
