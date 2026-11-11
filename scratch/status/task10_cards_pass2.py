"""Task 10, second pass (final facts): text updates to docs/status/cards.yaml. No colour changes.
Run once after task10_cards.py: uv run --no-project --with pyyaml python scratch/status/task10_cards_pass2.py
"""
from pathlib import Path

import yaml

P = Path(__file__).resolve().parents[2] / "docs/status/cards.yaml"
TAG = ("`[建议，待确认]`", "`[suggestion, to be confirmed]`")


def b(zh, en):
    return {"zh": zh, "en": en}


text = P.read_text(encoding="utf-8")
cut = text.index("\nmeta:") + 1
header, data = text[:cut], yaml.safe_load(text)
c = {x["id"]: x for x in data["cards"]}
assert "P-23" not in text, "already applied"

data["meta"]["progress"]["note"] = b(
    "分母只算对应 Must 任务的非灰卡片（`tier: must`），每张权重 1。灰卡（由我维护的、已按决定删除的）和旧设计里降为 Optional 的评估实验只展示、不进分母（项目负责人 2026-11-10 确认）。另有三处是任务 10 按同一条规则做的，`[建议，待确认]`：计划之前完成的基础卡 A1 到 A3 不进分母；不在计划里的 F2 不进分母；V2 卡复用为计划任务 V3a。黄卡不算部分分（黄卡做了多少没有测量，算分会让数字无法核对），黄卡张数单列。成型度 = Σ权重(浅绿 + 深绿) ÷ Σ权重(分母)；验证度 = Σ权重(深绿) ÷ Σ权重(分母)。这两个数按卡片的证据算，和 `progress.zh.md` 里按工时算的工作量、完成度不是一回事。",
    "The denominator counts only non-grey cards mapped to a Must task (`tier: must`), weight 1 each. Grey cards (maintained by me, or removed by decision) and the old-design evaluation experiments demoted to Optional are shown but left out (confirmed by the project owner on 2026-11-10). Three more choices were made by task 10 under the same rule and are `[suggestion, to be confirmed]`: foundation cards A1 to A3, finished before the plan, are left out; F2, which is not in the plan, is left out; card V2 is reused for plan task V3a. Yellow cards get no partial credit (how much of a yellow card is done is not measured, so partial credit would make the number unauditable), and the yellow count is shown separately. Shaped = Σweight(light green + dark green) ÷ Σweight(denominator); Verified = Σweight(dark green) ÷ Σweight(denominator). These two numbers follow card evidence and are not the same thing as the hour-based workload and completion in `progress.zh.md`.")

for cid in ("A1", "A2", "A3"):
    s = c[cid]["status_line"]
    s["zh"] = f"{TAG[0]} 计划之前完成的基础工作，不占 Must 分母；" + s["zh"]
    s["en"] = f"{TAG[1]} Foundation work finished before the plan, not in the Must denominator; " + s["en"]
c["F2"]["status_line"] = b(
    "`[建议，待确认]` 不在 11 月 5 日计划的任务清单里，不占 Must 分母；计划里面向客户的交付物是审核界面（U2 卡）和 skill 文件夹（K1 卡）。未开始",
    "`[suggestion, to be confirmed]` Not in the task list of the 2026-11-05 plan and not in the Must denominator; in the plan the client-facing deliverables are the review interface (card U2) and the skill folder (card K1). Not started")

c["B01"]["status_line"] = b(
    "任务 10：默认脱敏方式按事先写定的选择规则改为白名单反转（`allowlist`）：合成人名漏检从 29.0% 降到 10.9%，开发集上改动数字 0 条、费用词被遮 0 条，解析不差于波动范围。本卡建议的深绿门槛（漏检不超过 2%）**没有达到**，颜色不变。两个副作用列在待决 P-20：词表里没有的费用词会被遮住；公开 mock 上模型报告注入的次数变少。浅绿依据仍是原型的 908 条",
    "Task 10: the default redaction engine was changed to the inverted allow-list (`allowlist`) by the selection rule written beforehand: the miss rate on synthetic names falls from 29.0% to 10.9%, with 0 records with altered digits and 0 masked charge words on the dev split, and parsing not worse than the run-to-run range. The dark-green threshold suggested on this card (miss rate at most 2%) is **not met**, so the colour does not change. Two side effects are in pending item P-20: charge words missing from the word list get masked, and on the public mock the model reports fewer injections. Light green still rests on the prototype's 908 events")
c["B04"]["status_line"] = b(
    "任务 10：开发集全量 953 条用真实模型跑完，每条都有结果：760 通过 / 188 人工 / 5 退回；首次不一致 44 条；1 条强制检查最终不通过，已明确标出。全量是在 SKILL.md v1.1 加旧脱敏方式下跑的，没有用最终版本（v1.2 加白名单脱敏）重跑（待决 P-23）；最终版本只跑了样本 A、B2 和公开 mock",
    "Task 10: the full dev split, 953 records, ran with the real model and every record has a result: 760 passed / 188 human review / 5 return; 44 first-attempt mismatches; 1 record failed the mandatory checks at the end and is flagged explicitly. The full run used SKILL.md v1.1 with the old redaction engine and was not repeated with the final version (v1.2 plus allow-list redaction; pending item P-23); the final version ran on samples A, B2 and the public mock only")
sm = c["B04"]["summary"]
sm["tested"] = b("一次开发集全量真实模型运行，按运行库和留存记录数各类结果；160 个 pytest。",
                 "One real-model run over the full dev split, result categories counted from the run database and the retained records; 160 pytest tests.")
sm["limits"] = b(
    "样本内；全量用的是 v1.1 加旧脱敏方式，最终版本（v1.2 加白名单脱敏）没有跑全量（待决 P-23）；被告知不一致后模型很少改读法（44 条里 4 条）；读得对不对要等人工标注（H3）和终测（V4）。",
    "In-sample; the full run used v1.1 with the old redaction engine and the final version (v1.2 plus allow-list redaction) was not run in full (pending item P-23); the model rarely revises after being told of a mismatch (4 of 44); whether it reads correctly waits for human annotation (H3) and the final test (V4).")
c["B05"]["status_line"] = b(
    "任务 10：调优两轮，按事先写定的门槛第 1 轮回退、第 2 轮保留，定为 v1.2；仓库版的例子是 5 条合成例子。最终版本（v1.2 加白名单脱敏）在公开 mock 上主张金额正确 333 / 360。v1.2 只在样本 A、B2 和公开 mock 上跑过，没有跑开发集全量（待决 P-23），所以保持黄",
    "Task 10: two tuning rounds; by the thresholds written beforehand round 1 was reverted and round 2 kept, giving v1.2; the repository copy uses 5 synthetic examples. The final version (v1.2 plus allow-list redaction) reads 333 / 360 claim totals correctly on the public mock. v1.2 ran only on samples A, B2 and the public mock, not on the full dev split (pending item P-23), so the card stays yellow")
c["C2"]["status_line"] = b(
    "任务 10：`config/rules.yaml` 升到 v1.1：退回只留两种、上位标识、不计入依据的词表、默认脱敏方式改为白名单反转；每项改动前后的数字见 `docs/autorun/rule_changes_leg2.zh.md` 和 `docs/deliverables/T10-redaction-comparison/README.zh.md`",
    "Task 10: `config/rules.yaml` is now v1.1: return kept for two cases, subsumption, the exclusion-basis word list, default redaction engine changed to the inverted allow-list; before and after numbers are in `docs/autorun/rule_changes_leg2.zh.md` and `docs/deliverables/T10-redaction-comparison/README.zh.md`")
c["D1"]["status_line"] = b(
    "任务 10：160 个 pytest 通过（另有 2 个默认跳过），主线在开发集全量上跑过。完成标准里“开发集结果与原型一致”已经不适用（决定改了行为），这一条怎么改写由项目负责人定，所以保持黄；历史检查（R1c）和别名表（P4b）是 Optional，未迁",
    "Task 10: 160 pytest tests pass (2 more skipped by default) and the main line ran on the full dev split. The done-when item \"dev results match the prototype\" no longer applies (the decisions changed the behaviour); how to restate it is for the project owner, so the card stays yellow; history checks (R1c) and the alias table (P4b) are Optional and not moved")
c["B10"]["status_line"]["zh"] = c["B10"]["status_line"]["zh"].replace("开发集全量上建了运行库", "开发集全量（v1.1 加旧脱敏方式）上建了运行库")
c["B10"]["status_line"]["en"] = c["B10"]["status_line"]["en"].replace("on the full dev split (", "on the full dev split (v1.1 with the old redaction engine; ")
c["B09"]["status_line"]["zh"] = c["B09"]["status_line"]["zh"].replace("开发集全量 760 通过", "开发集全量（v1.1 加旧脱敏方式）760 通过")
c["B09"]["status_line"]["en"] = c["B09"]["status_line"]["en"].replace("Full dev split: 760", "Full dev split (v1.1 with the old redaction engine): 760")
for k in ("B10", "B09"):
    assert "旧脱敏" in c[k]["status_line"]["zh"] and "old redaction" in c[k]["status_line"]["en"], k

h = c["H1"]
h["status_line"] = b(
    "任务 10：中英两版标注指南、三个标注包、导入脚本和一致率脚本都已做好，14 个测试通过。标注包已用最终的脱敏方式重新生成：每包 45 条（公共 15 条，共 105 条不同记录，只从开发集抽），数字个数 88 / 88 / 89，每包 5 条首次不一致的记录。指南还没有人试标过",
    "Task 10: the annotation guide in two languages, three packs, the import script and the agreement script are done; 14 tests pass. The packs were rebuilt with the final redaction engine: 45 records per pack (15 in common, 105 distinct records, drawn from the dev split only), 88 / 88 / 89 numbers, 5 first-attempt-mismatch records per pack. Nobody has tried the guide yet")
h["summary"]["result_vs_threshold"] = b(
    "953 条里 937 条可抽；三个包各 45 条，公共 15 条，共 105 条不同记录；数字个数 88 / 88 / 89；每包 5 条首次不一致的记录（来源含开发集全量运行）。没有数字门槛。",
    "937 of 953 records can be drawn; three packs of 45, 15 in common, 105 distinct records; 88 / 88 / 89 numbers; 5 first-attempt-mismatch records per pack (sources include the full dev run). No numeric threshold.")
h["summary"]["limits"] = b(
    "指南没有人试标过；任意两个包合起来是 75 条不同记录、15 条双人标，三个包都交回才超过计划的 100 条；“按真实频率”的那一半受“同一种模板最多 2 条”限制，不能当作按频率的无偏样本（待决 P-25）。",
    "nobody has tried the guide; any two packs give 75 distinct records with 15 double-annotated, so all three must come back to exceed the plan's 100; the \"by real frequency\" half is capped at 2 records per template and cannot be treated as an unbiased frequency sample (pending item P-25).")

v5 = c["V5"]
v5["status_line"] = b(
    "任务 10：指标定义、脚本和报告模板都有（计划任务 V1）；在调优第 2 轮的公开 mock 运行上跑通，主张金额正确 329 / 360，与调优记录一致。对照人工标注的部分只用假标注自检过",
    "Task 10: metric definitions, script and report template are in place (plan task V1); it ran on the public-mock run of tuning round 2, claim total correct 329 / 360, matching the tuning log. The comparison with human annotation was self-tested with fake annotations only")
v5["summary"]["tested"] = b("在调优第 2 轮的公开 mock 运行上跑 `mock` 子命令，和调优记录对照；自检子命令。",
                            "the `mock` subcommand on the public-mock run of tuning round 2, compared with the tuning log; the self-test subcommand.")

u2 = c["U2"]
u2["open_items"] = {"lead": b(
    "批量操作、之前批次的上下文、距离、草稿编辑属于 U4（Optional）；四个按钮是否对应 OTM 的实际操作，等 Jake（J10、J11）；其中一个按钮叫“批准”（APPROVE），记录的是审核员自己的决定，但字面上接近项目边界禁止的字段，要不要改名由我决定（待决 P-24）。",
    "bulk actions, earlier-batch context, distance and draft editing belong to U4 (Optional); whether the four buttons match the real OTM actions waits for Jake (J10, J11); one button is called APPROVE: it records the reviewer's own decision, but the word is close to the fields the project boundary forbids, and whether to rename it is decided by me (pending item P-24).")}
u2["summary"]["data"] = b("合成数据（测试）；开发集全量运行库 953 笔争议（样本内；v1.1 加旧脱敏方式的那次运行）。",
                          "Synthetic data (tests); the full dev run database, 953 disputes (in-sample; the run made with v1.1 and the old redaction engine).")

v2 = c["V2"]
v2["status_line"] = b(
    "`[建议，待确认]` 本卡复用为计划任务 V3a：11 月 5 日计划把 Baseline 并入护栏开和关的对比，关闭组就是直接抽取。任务 10：两组都跑完，门槛事先写定，护栏开取最终版本（v1.2 加白名单脱敏）。按事先的规则，结论是“不是每条门槛都达到”：T4（注入）没达到（标出 22 个，门槛 27 个；改金额类读对 4 个，关闭组 5 个）；T1、T2、T3、T5 达到。保持黄（待决 P-21、P-22）",
    "`[suggestion, to be confirmed]` This card is reused for plan task V3a: the 2026-11-05 plan merged the baseline into the guardrails on-vs-off comparison; the off arm is direct extraction. Task 10: both arms ran, with thresholds written beforehand; the on arm is the final version (v1.2 plus allow-list redaction). By that rule the conclusion is \"not every threshold is met\": T4 (injection) is not met (22 flagged, threshold 27; 4 amount-changing injections read correctly vs 5 for the off arm); T1, T2, T3 and T5 are met. Stays yellow (pending items P-21, P-22)")
v2["summary"]["result_vs_threshold"] = b(
    "T1 达到（开 0 条；关：公开 mock 3 条、样本 A 4 条）。T2 达到（开 333，关 323，波动宽度 3）。T3 达到（读错的 27 个事件里 26 个带人工审核）。**T4 没达到**（标出 22 个，门槛 27 个；改金额类读对 4 个，关 5 个）。T5 达到（改动数字 0 条；所选脱敏方式的人名漏检率是 10.9%）。",
    "T1 met (on 0 records; off: 3 on the public mock, 4 on sample A). T2 met (on 333, off 323, range width 3). T3 met (26 of 27 misread events carry human review). **T4 not met** (22 flagged, threshold 27; 4 amount-changing injections read correctly, off 5). T5 met (0 records with altered digits; the chosen redaction engine misses 10.9% of names).")
v2["summary"]["limits"] = b(
    "样本内；注入事件只有 30 个；去掉有争议的那类对照后，关读对 288 / 300，开 283 / 300：护栏的作用是让错误被看见、不出现原文没有的金额，不是提高读对率；开发集上没有标准答案。",
    "In-sample; only 30 injection events; without the disputed control class the off arm reads 288 / 300 correctly and the on arm 283 / 300: the guardrails make errors visible and keep out amounts that are not in the text, they do not raise reading accuracy; the dev split has no answer key.")
v2["needs_b04"]["note"] = b("两组都要调用模型；B04 已接上。升浅绿还差 T4 达到。", "Both arms call the model; B04 is connected. Light green still needs T4 met.")

body = yaml.dump(data, Dumper=yaml.SafeDumper, allow_unicode=True, sort_keys=False, width=10**6)
P.write_text(header + body, encoding="utf-8")
print("updated")
