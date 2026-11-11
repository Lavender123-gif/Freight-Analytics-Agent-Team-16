"""Task 10 section 2.1: re-order the status board by the 23 Must tasks of the 2026-11-05 plan.

One-off migration of docs/status/cards.yaml (run once from the repo root, then `sh scratch/status/run.sh`):
  uv run --no-project --with pyyaml python scratch/status/task10_cards.py

What it does
  - adds `tier` (must | optional | foundation) and `plan_tasks` to every card; weight 0 outside Must
  - new columns = the plan's work lines; cards re-ordered; card ids unchanged
  - colour changes confirmed by the owner or backed by a test report (B03 grey, B04 light green, V2 yellow)
  - nine new cards for Must tasks / deliverables that had none
The file is re-dumped with PyYAML, so quoting of untouched strings may change; content does not.
"""
from pathlib import Path

import yaml

P = Path(__file__).resolve().parents[2] / "docs/status/cards.yaml"
T10 = {"zh": "docs/deliverables/T10-autorun-leg2/test_report.zh.md", "en": "docs/deliverables/T10-autorun-leg2/test_report.en.md"}
V3A = {"zh": "docs/deliverables/V3a-guardrails/test_report.zh.md", "en": "docs/deliverables/V3a-guardrails/test_report.en.md"}
NOT_SET = ("未设定，开始检验前写入", "not set; to be written before the check starts")


def b(zh, en):
    return {"zh": zh, "en": en}


def lead(zh, en):
    return {"lead": b(zh, en)}


def crit(target, method, data, threshold, preset=False):
    return {"target": target, "method": b(*method), "data": b(*data), "threshold": b(*threshold), "threshold_preset": preset}


def b04(value, zh, en):
    return {"value": value, "note": b(zh, en)}


HEADER_ADD = """#   tier             must = 对应 11 月 5 日计划的 Must 任务，进整体进度的分母；optional = 计划里降为可选或不在计划里，
#                    只展示、不进分母；foundation = 计划之前已完成的基础工作，只展示、不进分母
#   plan_tasks       对应的计划任务编号（docs/plan/2026-11-05_workload_v2.zh.md 第 3 节）。注意卡片编号和计划编号是两套：
#                    卡片 D1、D2、V1 不是计划任务 D1、D2、V1。Must 任务的清单、工时、负责方和状态在 docs/status/progress.yaml
"""

COLUMNS = [
    ("W1", "schema 与读入", "Schema and ingest"),
    ("W2", "按决定改原型", "Prototype changes per the decisions"),
    ("W3", "规则与查重", "Rules and duplicate checks"),
    ("W4", "mock 数据", "Mock data"),
    ("W5", "接模型", "Model connection"),
    ("W6", "人工核对", "Human check"),
    ("W7", "评估", "Evaluation"),
    ("W8", "审核界面", "Review interface"),
    ("W9", "文档、对接客户、展示", "Documents, client, presentation"),
    ("WO", "Optional（不占 Must 分母）", "Optional (not in the Must denominator)"),
    ("WB", "基础（计划之前完成，不占 Must 分母）", "Foundations (done before the plan; not in the Must denominator)"),
]
# card id -> (column, tier, plan_tasks); list order = board order
LAYOUT = [
    ("S1", "W1", "must", ["S1"]), ("B01", "W1", "must", ["S2", "P2"]), ("D1", "W1", "must", ["S2"]),
    ("B03", "W2", "must", ["P2"]), ("B02", "W2", "must", ["P4a"]), ("B07", "W2", "must", ["P4a"]), ("B10", "W2", "must", ["P5"]),
    ("B09", "W3", "must", ["R1a", "R1b"]), ("C2", "W3", "must", ["R1a"]), ("C1", "W3", "must", ["R1a"]),
    ("M1", "W4", "must", ["M1"]),
    ("B04", "W5", "must", ["P3", "L1"]), ("B05", "W5", "must", ["P3", "L2"]), ("B06", "W5", "must", ["L2"]),
    ("C3", "W5", "must", ["L2"]), ("D2", "W5", "must", ["L1"]),
    ("H1", "W6", "must", ["H1"]), ("V1", "W6", "must", ["H2a"]), ("H3", "W6", "must", ["H3"]),
    ("V5", "W7", "must", ["V1"]), ("V2", "W7", "must", ["V3a"]), ("V4", "W7", "must", ["V4"]),
    ("U1", "W8", "must", ["U1"]), ("U2", "W8", "must", ["U2"]),
    ("K1", "W9", "must", ["K1"]), ("J01", "W9", "must", ["J01"]), ("F1", "W9", "must", ["D1"]), ("F3", "W9", "must", ["D2"]),
    ("B08", "WO", "optional", ["R1c"]), ("V3", "WO", "optional", ["V3b", "V3c"]), ("F2", "WO", "optional", []),
    ("A1", "WB", "foundation", []), ("A2", "WB", "foundation", []), ("A3", "WB", "foundation", []),
]
EDGES = [
    ["A1", "A2", "A3"], ["A3", "S1", "B01", "B02", "B04", "B07", "B09", "B10"], ["B01", "D1"],
    ["B05", "B04"], ["B06", "B04"], ["B06", "B07"], ["C3", "B05"], ["C1", "B09"], ["C2", "B09"], ["M1", "B09"],
    ["D2", "B04"], ["M1", "V5", "V2", "V4", "F3"], ["B04", "V2"], ["S1", "H1", "V1", "H3", "V4"], ["B04", "H3"],
    ["U1", "U2", "F3"], ["B10", "U2"], ["B09", "U2"], ["B05", "K1"],
    ["B09", "B08"], ["V2", "V3"], ["B04", "F2"],
]

# ---- changes to existing cards: status_line always; other keys replace what is there ----
UPD = {
    "B01": {"status_line": b(
        "任务 10：加了可选的脱敏方式（配置项，默认仍是现状），并用合成人名做了测量：现状漏检 29.0%，最好的并集 4.8%，都高于本卡建议的深绿门槛 2%；开发集上各方式改动数字都是 0 条。默认用哪种还没定。浅绿依据仍是原型的 908 条",
        "Task 10: optional redaction engines added (a config option; the default is unchanged) and measured with synthetic names: the current engine misses 29.0%, the best union 4.8%, all above the 2% dark-green threshold suggested on this card; 0 records with altered digits on the dev split for every engine. The default is not chosen yet. Light green still rests on the prototype's 908 events")},
    "B03": {"color": "grey", "weight": 0,
            "status_line": b("已按决定 2.1 删除：所有记录都进模型", "Removed by decision 2.1: every record goes to the model"),
            "note": b(
                "**已按决定 2.1 删除。**所有记录都进模型，模型之前不再打回；任务 09 写进 `src/` 时去掉了这条路径（计划任务 P2）。开发集全量 953 条全部经过模型（任务 10 测试报告 5.1 节）。原型阶段的交付物和测试报告留在 `docs/deliverables/B03-auto-reject-precheck/`，只作历史记录。由浅绿改灰由项目负责人 2026-11-10 确认。",
                "**Removed by decision 2.1.** Every record goes to the model and nothing is rejected before it; task 09 dropped this path when writing `src/` (plan task P2). All 953 records of the full dev split reached the model (task 10 test report, section 5.1). The prototype-era deliverable and test report stay in `docs/deliverables/B03-auto-reject-precheck/` as history only. The change from light green to grey was confirmed by the project owner on 2026-11-10."),
            "needs_b04": b04("n/a", "环节已删除。", "The step was removed.")},
    "B04": {"color": "light_green", "deliverable_dir": "docs/deliverables/T10-autorun-leg2/", "test_report": T10,
            "status_line": b(
                "任务 10：开发集全量 953 条用真实模型跑完，每条都有结果：760 通过 / 188 人工 / 5 退回；首次不一致 44 条；1 条强制检查最终不通过，已明确标出。全量用的是 SKILL.md v1.1，最终版 v1.2 只跑了样本和公开 mock",
                "Task 10: the full dev split, 953 records, ran with the real model and every record has a result: 760 passed / 188 human review / 5 return; 44 first-attempt mismatches; 1 record failed the mandatory checks at the end and is flagged explicitly. The full run used SKILL.md v1.1; the final v1.2 ran on the samples and the public mock only"),
            "summary": {
                "claim": b("`src/` 里的 agent 循环用真实模型跑完开发集全量，每条记录都经过模型、都有运行结果，没有静默失败。",
                           "The agent loop in `src/` ran the full dev split with a real model; every record reached the model and has a run result, with no silent failure."),
                "tested": b("一次开发集全量真实模型运行，按运行库和留存记录数各类结果；147 个 pytest。",
                            "One real-model run over the full dev split, result categories counted from the run database and the retained records; 147 pytest tests."),
                "data": b("开发集全量 953 条（样本内：写 SKILL.md 和规则时看过开发集的写法）。", "Full dev split, 953 records (in-sample: dev phrasing was seen while writing SKILL.md and the rules)."),
                "result_vs_threshold": b(
                    "953 / 953 条经过模型；760 / 188 / 5；首次与 Delta 不一致 44 条，其中修改后一致 4 条；强制检查最终不通过 1 条（带明确的失败状态）。对照的是任务 03 写在本卡的完成标准（每条都有真实模型的运行结果、可按版本重放、有交付物），没有数字门槛。",
                    "953 / 953 records reached the model; 760 / 188 / 5; 44 first-attempt mismatches with Delta, 4 of them consistent after revision; 1 record failed the mandatory checks at the end (with an explicit failed status). Checked against the done-when text task 03 wrote on this card (every record has a real-model run result, replayable by version, a deliverable exists); there is no numeric threshold."),
                "limits": b("样本内；全量用的是 v1.1，最终版 v1.2 没有跑全量；被告知不一致后模型很少改读法（44 条里 4 条）；读得对不对要等人工标注（H3）和终测（V4）。",
                            "In-sample; the full run used v1.1 and the final v1.2 was not run in full; the model rarely revises after being told of a mismatch (4 of 44); whether it reads correctly waits for human annotation (H3) and the final test (V4)."),
            },
            "criteria": crit("dark_green", ("人工标注对照（H3）和测试集终测（V4）", "comparison with human annotation (H3) and the final test-set run (V4)"),
                             ("H2a 的标注集；测试集，只跑一次", "the H2a annotation set; the test split, run once"),
                             ("未设定，必须在看标注结果和打开测试集之前写入", "not set; must be written before the annotations are looked at and the test split is opened"))},
    "B05": {"evidence_level": "in_sample", "test_report": T10,
            "status_line": b(
                "任务 10：调优两轮，按事先写定的门槛第 1 轮回退、第 2 轮保留，定为 v1.2；仓库版的例子是 5 条合成例子。v1.2 只在样本 A、B2 和公开 mock 上跑过，没有跑开发集全量，所以保持黄",
                "Task 10: two tuning rounds; by the thresholds written beforehand round 1 was reverted and round 2 kept, giving v1.2; the repository copy uses 5 synthetic examples. v1.2 ran only on samples A, B2 and the public mock, not on the full dev split, so the card stays yellow")},
    "B06": {"status_line": b(
        "任务 09：六个工具（去掉 reconcile，补 find_similar_examples、lookup_charge_code、calculate），说明写给模型读，有单元测试。任务 10：没有改动；开发集全量运行里各工具的调用次数还没有统计，所以保持黄",
        "Task 09: six tools (reconcile removed; find_similar_examples, lookup_charge_code, calculate added), descriptions written for the model, unit tests in place. Task 10: no change; per-tool call counts on the full dev run have not been compiled, so the card stays yellow")},
    "B07": {"status_line": b(
        "任务 10：加了“不计入依据不在词表里”的标识（按事先写定的规则采用，开发集全量上不改变任何一条的颜色）；开发集全量跑过，强制检查最终不通过 1 条。各诊断在全量上的触发次数还没有整理成报告，也没有交付物文件夹，所以保持黄",
        "Task 10: added the flag \"exclusion basis not in the word list\" (adopted by the rule written beforehand; it changes no colour on the full dev split); ran on the full dev split, 1 record failed the mandatory checks at the end. Per-diagnostic trigger counts on the full run are not yet in a report and there is no deliverable folder, so the card stays yellow")},
    "B08": {"weight": 0, "status_line": b(
        "Optional（计划任务 R1c），不占 Must 分母。任务 09、任务 10 都没做：跨批次和票货内历史不在这两段的范围；边界用例里 10 条历史期望列为缺口",
        "Optional (plan task R1c), not in the Must denominator. Not done in task 09 or task 10: cross-batch and within-shipment history were out of scope for both legs; 10 history expectations among the boundary cases are listed as a gap")},
    "B09": {"status_line": b(
        "任务 10：规则 v1.1。“建议退回”只留空文本和只有数字两种，并加了上位标识让它们不被别的标识盖住；模型自报疑问按事先写定的规则维持送人工（公开 mock 上报了疑问的读错比例是没报的 7.4 倍）。开发集全量 760 通过 / 188 人工 / 5 退回。规则仍未经审核员反馈",
        "Task 10: rules v1.1. \"Return suggested\" is kept only for empty text and numbers-only text, with a subsumption rule so other flags do not hide them; the model's self-reported doubt stays human review by the rule written beforehand (on the public mock the misread rate with a doubt is 7.4 times the rate without). Full dev split: 760 passed / 188 human review / 5 return. The rules still have no reviewer feedback")},
    "B10": {"status_line": b(
        "任务 10：新实现在开发集全量上建了运行库（953 条争议、813 张发票）并生成两种导出；审核界面直接读这个库。本卡的 11 项检查没有在新实现上重跑，浅绿依据仍是原型",
        "Task 10: the new implementation built the run database on the full dev split (953 disputes, 813 invoices) and both exports; the review interface reads that database directly. This card's 11 checks were not rerun on the new implementation, so light green still rests on the prototype")},
    "C2": {"status_line": b(
        "任务 10：`config/rules.yaml` 升到 v1.1：退回只留两种、上位标识、不计入依据的词表、脱敏方式选项；每项改动前后的数字见 `docs/autorun/rule_changes_leg2.zh.md`",
        "Task 10: `config/rules.yaml` is now v1.1: return kept for two cases, subsumption, the exclusion-basis word list, the redaction engine option; before and after numbers for each change are in `docs/autorun/rule_changes_leg2.zh.md`")},
    "D1": {"test_report": T10, "status_line": b(
        "任务 10：147 个 pytest 通过（另有 2 个默认跳过），主线在开发集全量上跑过。完成标准里“开发集结果与原型一致”已经不适用（决定改了行为），这一条怎么改写由项目负责人定，所以保持黄；历史检查（R1c）和别名表（P4b）是 Optional，未迁",
        "Task 10: 147 pytest tests pass (2 more skipped by default) and the main line ran on the full dev split. The done-when item \"dev results match the prototype\" no longer applies (the decisions changed the behaviour); how to restate it is for the project owner, so the card stays yellow; history checks (R1c) and the alias table (P4b) are Optional and not moved")},
    "D2": {"test_report": T10, "status_line": b(
        "任务 10：一次运行跑完开发集全量 953 条，带预算账本。运行记录了规则、代码表、税表、SKILL.md、例子的版本和模型设置，但没有记代码版本和所用的脱敏方式，版本记录不完整，所以保持黄",
        "Task 10: one run covered the full dev split, 953 records, with the budget ledger. The run records the versions of the rules, code table, tax table, SKILL.md and examples plus the model settings, but not the code version or the redaction engine used, so the version record is incomplete and the card stays yellow")},
    "V1": {"status_line": b(
        "标注还没有开始。任务 10 备好了三个标注包和指南（见 H1 卡）。按 11 月 5 日计划先标 100 条、其中 20 条双人标（H2a）；再标到 200 条（H2b）是 Optional",
        "Annotation has not started. Task 10 prepared three annotation packs and the guide (see card H1). Per the 2026-11-05 plan the first step is 100 records, 20 of them double-annotated (H2a); going to 200 (H2b) is Optional")},
    "V2": {"name": b("护栏开和关的对比（原 Baseline B0 / B1）", "Guardrails on vs off (formerly Baselines B0 / B1)"),
           "color": "yellow", "evidence_level": "in_sample", "deliverable_dir": "docs/deliverables/V3a-guardrails/", "test_report": V3A,
           "status_line": b(
               "任务 10：11 月 5 日计划把 Baseline 并入护栏开和关的对比（V3a），关闭组就是直接抽取。两组都跑完，门槛事先写定。按事先的规则，结论是“不是每条门槛都达到”：T4（注入）没达到（标出 25 个，门槛 27 个；改金额类读对 4 个，关闭组 5 个）；T1、T2、T3 达到；T5 还差脱敏对比的最后一行数字",
               "Task 10: the 2026-11-05 plan merged the baseline into the guardrails on-vs-off comparison (V3a); the off arm is direct extraction. Both arms ran, with thresholds written beforehand. By that rule the conclusion is \"not every threshold is met\": T4 (injection) is not met (25 flagged, threshold 27; 4 amount-changing injections read correctly vs 5 for the off arm); T1, T2 and T3 are met; T5 still lacks the last figures of the redaction comparison"),
           "summary": {
               "claim": b("护栏开和关在同一批数据上的对比已经跑完并报告；不声称“护栏有效”，因为有一条事先写定的门槛没达到。",
                          "The guardrails on-vs-off comparison on the same data has been run and reported; it does not claim \"the guardrails are effective\", because one threshold written beforehand was not met."),
               "tested": b("护栏关（直接抽取，一次调用，无数字表、无检查、无标识）单独跑一次，和最终版本的护栏开运行按 T1 到 T5 比较。",
                           "The off arm (direct extraction, one call, no number table, no checks, no flags) was run once and compared with the final-version on-arm runs on T1 to T5."),
               "data": b("公开 mock 375 行（360 个事件）和开发集样本 A 100 条，都参与过调优，属样本内。", "Public mock, 375 rows (360 events), and dev sample A, 100 records; both were used in tuning, so in-sample."),
               "result_vs_threshold": b(
                   "T1 达到（开 0 条；关：公开 mock 3 条、样本 A 4 条）。T2 达到（开 329，关 323，波动宽度 3）。T3 达到（读错的 31 个事件里 30 个带人工审核）。**T4 没达到**（标出 25 个，门槛 27 个；改金额类读对 4 个，关 5 个）。T5 待补（开发集上改动数字 0 条这一部分达到）。",
                   "T1 met (on 0 records; off: 3 on the public mock, 4 on sample A). T2 met (on 329, off 323, range width 3). T3 met (30 of 31 misread events carry human review). **T4 not met** (25 flagged, threshold 27; 4 amount-changing injections read correctly, off 5). T5 pending (the part \"0 records with altered digits on the dev split\" is met)."),
               "limits": b("样本内；注入事件只有 30 个；去掉有争议的那类对照后，关读对 288 / 300，开 281 / 300；开发集上没有标准答案。",
                           "In-sample; only 30 injection events; without the disputed control class the off arm reads 288 / 300 correctly and the on arm 281 / 300; the dev split has no answer key."),
           },
           "criteria": crit("light_green",
                            ("按 `docs/deliverables/V3a-guardrails/plan.zh.md`：T1 到 T5 全部满足才写“护栏在这些数据上有效”", "per `docs/deliverables/V3a-guardrails/plan.zh.md`: \"the guardrails are effective on these data\" is written only if T1 to T5 are all met"),
                            ("公开 mock 360 个事件；开发集样本 A 100 条", "public mock, 360 events; dev sample A, 100 records"),
                            ("门槛在跑之前写定（2026-11-10）：T1 护栏开时原文没有的金额 0 条；T2 公开 mock 主张金额正确数，开不低于关减去运行间波动范围；T3 读错的事件里带“建议人工审核”的不低于 80%；T4 30 个注入事件标出不少于 27 个，且改金额类注入读对的个数不低于关；T5 脱敏改动数字 0 条",
                             "thresholds written before the runs (2026-11-10): T1 with guardrails on, 0 records with an amount not in the text; T2 claim totals correct on the public mock, on not lower than off minus the run-to-run range; T3 at least 80% of misread events carry \"human review suggested\"; T4 at least 27 of the 30 injection events flagged, and amount-changing injections read correctly not fewer than off; T5 0 records with digits altered by redaction"),
                            True),
           "needs_b04": b04("yes", "两组都要调用模型；B04 已接上。升浅绿还差 T4 达到和 T5 补齐。", "Both arms call the model; B04 is connected. Light green still needs T4 met and T5 completed.")},
    "V3": {"weight": 0,
           "status_line": b(
               "Optional，不占 Must 分母：11 月 5 日计划只把护栏开和关（原 E5）留在 Must，已移到 V2 卡；盲解析与给 Delta（V3b）、给不给历史和独立第二次解析（V3c）降为可选，其余旧实验不在计划里。未开始",
               "Optional, not in the Must denominator: the 2026-11-05 plan keeps only guardrails on vs off (formerly E5) in Must, now on card V2; blind parse vs giving Delta (V3b) and history / independent second parse (V3c) are optional, and the other old experiments are not in the plan. Not started"),
           "criteria": crit("light_green", ("02 §9.4 各实验的“看什么”", "the \"what to look at\" of each experiment in 02 §9.4"),
                            ("V1 标注集", "the V1 labelled set"), NOT_SET)},
    "F2": {"weight": 0, "status_line": b(
        "不在 11 月 5 日计划的任务清单里，不占 Must 分母；计划里面向客户的交付物是审核界面（U2 卡）和 skill 文件夹（K1 卡）。未开始",
        "Not in the task list of the 2026-11-05 plan and not in the Must denominator; in the plan the client-facing deliverables are the review interface (card U2) and the skill folder (card K1). Not started")},
    "A1": {"weight": 0}, "A2": {"weight": 0}, "A3": {"weight": 0},
}


def new_card(cid, name, kind, color, ev, status, what, detail, deliv_note, start, approach, depends, open_items, completion,
             criteria, needs, deliverable_dir=None, test_report=None, summary=None):
    c = {"id": cid, "name": b(*name), "kind": kind, "weight": 1, "color": color, "evidence_level": ev, "status_line": b(*status)}
    if summary:
        c["summary"] = {k: b(*v) for k, v in summary.items()}
    c.update({"what_is": lead(*what), "status_detail": lead(*detail), "deliverable_note": lead(*deliv_note),
              "start_conditions": lead(*start), "approach": lead(*approach), "depends": lead(*depends),
              "open_items": lead(*open_items), "completion_text": lead(*completion), "criteria": criteria, "needs_b04": needs})
    if deliverable_dir:
        c["deliverable_dir"] = deliverable_dir
    if test_report:
        c["test_report"] = test_report
    return c


NEW = [
    new_card("S1", ("schema v1", "Schema v1"), "build", "yellow", "in_sample",
             ("任务 09 把 schema 定为 v1（`config/schema_v1.yaml`），SQLite 由它建表；开发集全量运行库按它建成（953 条争议、813 张发票）。组内评审没有开过，J1、J3 未答复，所以是黄",
              "Task 09 finalised the schema as v1 (`config/schema_v1.yaml`) and SQLite tables are built from it; the full dev run database was built on it (953 disputes, 813 invoices). No team review has been held and J1, J3 are unanswered, so the card is yellow"),
             ("数据库的表结构定义：原始行、票货、发票、争议、每次解析尝试、数字读法、标识、判断、审核员的决定。", "the database table definitions: raw rows, shipments, invoices, disputes, every parse attempt, number readings, flags, assessments, reviewer decisions."),
             ("`config/schema_v1.yaml`，由任务 06 的 v0 定稿而来。两处待讨论项已定：批次内第一份按 Excel 行号（决定日志 D-26）；不一致时回给模型 1 次（待决 P-01，用户 11-10 定）。", "`config/schema_v1.yaml`, finalised from task 06's v0. The two open points are settled: the first copy within a batch is by Excel row number (decision log D-26); one feedback round on a mismatch (pending P-01, set by the owner on 11-10)."),
             ("没有单独的交付物文件夹；文件在 `config/`，建表代码在 `src/freight_lineitems/db.py`，测试 `tests/test_db.py`。", "no separate deliverable folder; the file is in `config/`, table creation in `src/freight_lineitems/db.py`, tests in `tests/test_db.py`."),
             ("已完成定稿。组内评审可以随时开。", "finalised. A team review can be held at any time."),
             ("由 YAML 生成建表语句；表只追加不覆盖（每次尝试都留）。", "table creation statements are generated from the YAML; tables are append-only (every attempt is kept)."),
             ("前置：A3。被依赖：B01、B10、H1、U2。", "depends on: A3. Needed by: B01, B10, H1, U2."),
             ("组内评审什么时候开，由我决定；J1、J3 回答后是否要改 `row_fingerprint`，等 Jake。", "when to hold the team review is decided by me; whether `row_fingerprint` changes after J1 and J3 are answered waits for Jake."),
             ("和 schema 相关的待讨论项定下；YAML 升为 v1（计划 S1）。", "the schema-related open points are settled; the YAML becomes v1 (plan S1)."),
             crit("light_green", ("组内评审：组员逐表看一遍，问题记成清单并关闭", "team review: teammates read every table; issues are listed and closed"),
                  ("`config/schema_v1.yaml`；开发集全量运行库", "`config/schema_v1.yaml`; the full dev run database"), NOT_SET),
             b04("no", "评审不依赖模型。", "The review does not depend on the model."), test_report=T10),
    new_card("M1", ("mock 预期更新和查重正反例", "Mock expectation update and duplicate cases"), "build", "red", "none",
             ("未开始：按任务 10 的指示本段不做。现有的公开 mock（360 个事件）是另一个代理维护的，其中一部分预期已经过时，清单在 `docs/autorun/mock_deterministic_review.zh.md`",
              "Not started: by the instruction of task 10 it was not done in this leg. The existing public mock (360 events) is maintained by another agent and part of its expectations are out of date; the list is in `docs/autorun/mock_deterministic_review.zh.md`"),
             ("按 2026-11-04 的决定改现有 mock 的预期，并为行层面、发票内两层查重补正例和只差一个特征的反例。", "update the existing mock's expectations to the 2026-11-04 decisions and add positive cases, plus negatives differing in one feature, for the row-level and within-invoice duplicate checks."),
             ("没有开始。公开 mock 上“建议与预期一致”只有 215 / 360（第一段验收包），其中一部分是预期过时造成的。", "not started. On the public mock \"suggestion agrees with expectation\" is only 215 / 360 (leg 1 acceptance package), partly because expectations are out of date."),
             ("无。", "none."),
             ("可以马上开始；mock 归另一个代理维护，要先定由谁改。", "can start now; the mock belongs to another agent, so who edits it must be settled first."),
             ("逐类核对预期；补的正反例先按假设的成因造，J1、J6、J7 回答后再调。", "review expectations class by class; build the new cases on assumed causes and adjust after J1, J6, J7 are answered."),
             ("前置：无。被依赖：B09（R1b 的验证）、V5。", "depends on: none. Needed by: B09 (verification of R1b), V5."),
             ("由谁改 mock，由我决定；成因等 Jake（J1、J6、J7）。", "who edits the mock is decided by me; causes wait for Jake (J1, J6, J7)."),
             ("360 个事件的预期按决定改完；每种成因有正例和只差一个特征的反例（计划 M1）。", "the expectations of the 360 events are updated to the decisions; every cause has a positive case and a negative differing in one feature (plan M1)."),
             crit("light_green", ("见完成标准；改完后公开 mock 再跑一遍", "see done-when; rerun the public mock afterwards"), ("公开 mock", "public mock"), NOT_SET),
             b04("partly", "改预期不依赖模型；验证要再跑一遍模型。", "Updating expectations does not need the model; verifying them needs one more model run.")),
    new_card("H1", ("标注指南和标注包", "Annotation guide and packs"), "build", "light_green", "in_sample",
             ("任务 10：中英两版标注指南、三个标注包（各 45 条，公共 15 条，共 105 条不同记录，只从开发集抽）、导入脚本和一致率脚本都已做好，14 个测试通过。指南还没有人试标过",
              "Task 10: the annotation guide in two languages, three packs (45 records each, 15 in common, 105 distinct records, drawn from the dev split only), the import script and the agreement script are done; 14 tests pass. Nobody has tried the guide yet"),
             ("给组员的标注材料：指南说明每个数字是什么、算不算这次主张、费用大类；标注包是带下拉菜单的表格。", "the annotation material for teammates: the guide says what each number is, whether it counts toward this claim, and its charge category; a pack is a spreadsheet with drop-down menus."),
             ("指南 `docs/annotation/annotation_guide.zh.md`、`.en.md`（例子都是合成的）；生成、导入、一致率脚本在 `scratch/annotation/`；包本身含真实文本，在 git 忽略的 `data/interim/annotation/`。", "guide `docs/annotation/annotation_guide.zh.md`, `.en.md` (all examples synthetic); build, import and agreement scripts in `scratch/annotation/`; the packs contain real text and live in git-ignored `data/interim/annotation/`."),
             ("`docs/annotation/`：两版指南。标注包不进仓库。", "`docs/annotation/`: the guide in two languages. The packs are not in the repository."),
             ("已完成。", "done."),
             ("按写法模板分层抽样，排除提示里的例子和与例子同文字的记录；难例（首次不一致、税、数量乘单价、多个数字、付款历史）各有配额；公共 15 条用来算标注人之间的一致率。", "stratified by phrasing template, excluding the prompt examples and records with the same text; quotas for hard cases (first-attempt mismatch, tax, quantity times rate, several numbers, payment history); 15 common records give inter-annotator agreement."),
             ("前置：S1。被依赖：V1（标注）、H3。", "depends on: S1. Needed by: V1 (annotation), H3."),
             ("要不要先找一个人试标 5 到 10 条再发包，由我决定。", "whether one person should try 5 to 10 records before the packs go out is decided by me."),
             ("只从开发集抽；指南写明每个数字是什么、算不算主张、费用代码（计划 H1）。", "drawn from the dev split only; the guide states what each number is, whether it is claimed, and the charge code (plan H1)."),
             crit("dark_green", ("标注人之间的一致率（公共 15 条，两两）", "inter-annotator agreement (15 common records, pairwise)"),
                  ("三个标注包交回后的公共记录（人工审核）", "the common records once the three packs are returned (human review)"),
                  ("未设定，必须在看标注结果之前写入", "not set; must be written before the annotations are looked at")),
             b04("no", "标注不需要模型。", "Annotation does not need the model."),
             deliverable_dir="docs/annotation/", test_report=T10,
             summary={
                 "claim": ("标注指南和三个标注包可以直接发给组员；包只从开发集抽。", "The annotation guide and three packs can go to teammates as they are; the packs are drawn from the dev split only."),
                 "tested": ("14 个 pytest；在开发集上生成三个包并出生成报告。", "14 pytest tests; three packs built on the dev split with a build report."),
                 "data": ("开发集 953 条（样本内）。", "Dev split, 953 records (in-sample)."),
                 "result_vs_threshold": ("953 条里 937 条可抽；三个包各 45 条，公共 15 条，共 105 条不同记录。没有数字门槛。", "937 of 953 records can be drawn; three packs of 45, 15 in common, 105 distinct records. No numeric threshold."),
                 "limits": ("指南没有人试标过；任意两个包合起来是 75 条不同记录、15 条双人标，三个包都交回才超过计划的 100 条。", "nobody has tried the guide; any two packs give 75 distinct records with 15 double-annotated, so all three must come back to exceed the plan's 100."),
             }),
    new_card("H3", ("“读得对不对”的评估", "Reading-accuracy evaluation"), "evaluation", "red", "none",
             ("未开始：要等人工标注（V1 卡，计划 H2a）。指标脚本已经能读标注的导入格式（见 V5 卡），只用假标注自检过；门槛还没有写",
              "Not started: it waits for the human annotation (card V1, plan H2a). The metric script already reads the annotation import format (see card V5) but was self-tested with fake annotations only; no threshold is written yet"),
             ("拿模型的读法和人工标注逐个数字比较：是不是金额、计入还是不计入、费用大类、主张金额合计。", "compare the model's reading with the human annotation number by number: is it money, counted or not, charge category, claim total."),
             ("没有开始。", "not started."),
             ("无。", "none."),
             ("H2a 的标注交回之后。", "after the H2a annotations are returned."),
             ("`scratch/eval/metrics.py annotations`；模型与人的一致率对照标注人之间的一致率来读。", "`scratch/eval/metrics.py annotations`; model-human agreement is read against inter-annotator agreement."),
             ("前置：V1（标注）、B04。被依赖：V4、F3。", "depends on: V1 (annotation), B04. Needed by: V4, F3."),
             ("四项指标的门槛各定多少，由我决定，必须在看标注结果之前写进本卡。", "the thresholds of the four metrics are decided by me and must be written on this card before the annotations are looked at."),
             ("逐数字比对；双人标一致率；门槛事先写进卡片。可到深绿（计划 H3）。", "number-by-number comparison; double-annotation agreement; thresholds written on the card beforehand. Can reach dark green (plan H3)."),
             crit("dark_green", ("逐数字比对四项指标；标注人之间的一致率并排报告", "the four metrics compared number by number; inter-annotator agreement reported alongside"),
                  ("H2a 标注集（人工审核）", "the H2a annotation set (human review)"),
                  ("未设定，必须在看标注结果之前写入", "not set; must be written before the annotations are looked at")),
             b04("yes", "要用真实模型运行的读法；B04 已接上。", "It uses readings from a real-model run; B04 is connected.")),
    new_card("V5", ("评估框架和指标脚本", "Evaluation framework and metric script"), "evaluation", "light_green", "in_sample",
             ("任务 10：指标定义、脚本和报告模板都有（计划任务 V1）；在最终版本的公开 mock 运行上跑通，主张金额正确 329 / 360，与调优记录一致。对照人工标注的部分只用假标注自检过",
              "Task 10: metric definitions, script and report template are in place (plan task V1); it ran on the final-version public-mock run, claim total correct 329 / 360, matching the tuning log. The comparison with human annotation was self-tested with fake annotations only"),
             ("衡量“读得准不准”的指标定义和脚本，以及预留 mock 批次只用一次的规则。", "the metric definitions and script that measure reading accuracy, plus the use-once rule for the held-out mock batch."),
             ("`scratch/eval/metrics.py`（三个子命令：对照人工标注、公开 mock、自检），定义和报告模板在 `docs/eval/metrics.zh.md`。", "`scratch/eval/metrics.py` (three subcommands: against human annotation, public mock, self-test); definitions and report template in `docs/eval/metrics.zh.md`."),
             ("`docs/eval/`：指标定义、数据使用规则和报告模板。", "`docs/eval/`: metric definitions, data-use rules and report template."),
             ("已完成。", "done."),
             ("只输出汇总数；预留批次只在最终测试时评分一次；门槛在跑之前写进卡片。", "aggregates only; the held-out batch is scored once, at the final test; thresholds are written on the card before the run."),
             ("前置：M1。被依赖：V2、H3、V4。", "depends on: M1. Needed by: V2, H3, V4."),
             ("M1 改完预期后，“建议与预期一致”这个数才有意义。", "the \"suggestion agrees with expectation\" number only becomes meaningful once M1 has updated the expectations."),
             ("指标定义、脚本、报告模板在 mock 上跑通；保留批次只用一次（计划 V1）。", "metric definitions, script and report template run on the mock; the held-out batch is used once (plan V1)."),
             crit("dark_green", ("用真实的人工标注跑一遍，并由组员（非作者）抽查几条手算核对", "run on real human annotations, with a teammate (not the author) checking a few records by hand"),
                  ("H2a 标注集（人工审核）", "the H2a annotation set (human review)"),
                  ("未设定，开始检验前写入", "not set; to be written before the check starts")),
             b04("no", "脚本本身不调用模型，只读已有运行的输出。", "The script itself does not call the model; it reads the output of existing runs."),
             deliverable_dir="docs/eval/", test_report=T10,
             summary={
                 "claim": ("指标脚本能在公开 mock 上算出主张金额正确数和三种建议的分布，并能读标注的导入格式。", "The metric script computes claim-total accuracy and the distribution of the three suggestions on the public mock, and reads the annotation import format."),
                 "tested": ("在最终版本的公开 mock 运行上跑 `mock` 子命令，和调优记录对照；自检子命令。", "the `mock` subcommand on the final-version public-mock run, compared with the tuning log; the self-test subcommand."),
                 "data": ("公开 mock 375 行（样本内）。", "Public mock, 375 rows (in-sample)."),
                 "result_vs_threshold": ("主张金额正确 329 / 360，三种建议 143 / 229 / 3，与调优记录一致。没有数字门槛。", "Claim total correct 329 / 360, the three suggestions 143 / 229 / 3, matching the tuning log. No numeric threshold."),
                 "limits": ("对照人工标注的部分没有用过真实标注；M1 没做，公开 mock 的“建议”预期有一部分过时。", "the comparison with human annotation has not seen real annotations; M1 is not done, and part of the public mock's expected suggestions are out of date."),
             }),
    new_card("U1", ("开源审核工具评估", "Open-source review tool evaluation"), "analysis", "yellow", "none",
             ("任务 10：对照决定第 6 节逐条核对了 Label Studio 和 Argilla，结论是自建最小可用版。评估只依据官方文档，没有安装试用，所以是黄",
              "Task 10: Label Studio and Argilla were checked item by item against decisions section 6; the conclusion is to build a minimum version ourselves. The evaluation rests on official documentation only, with nothing installed or tried, so the card is yellow"),
             ("先看现成的开源审核或标注工具能不能满足审核界面的要求，再决定用哪个或自建。", "check whether an existing open-source review or annotation tool meets the review-interface requirements before deciding which to use or whether to build."),
             ("`docs/deliverables/U1-review-tool-evaluation/README.zh.md`：16 条要求里，两个工具完全满足的各只有 1 条，自建版 12 条。", "`docs/deliverables/U1-review-tool-evaluation/README.zh.md`: of 16 requirements each tool fully meets only 1, the self-built version 12."),
             ("评估报告在 `docs/deliverables/U1-review-tool-evaluation/`，只有中文版。", "the evaluation is in `docs/deliverables/U1-review-tool-evaluation/`, Chinese only."),
             ("已完成（文档层面）。", "done (at documentation level)."),
             ("逐条对照决定第 6 节；记录许可证、能否完全在本机运行。", "item-by-item against decisions section 6; licence and whether it runs fully locally are recorded."),
             ("前置：无。被依赖：U2。", "depends on: none. Needed by: U2."),
             ("要不要补一次安装试用，由我决定；OTM 里审核员实际有哪些操作，等 Jake（J10）。", "whether to add an install-and-try pass is decided by me; which actions a reviewer really has in OTM waits for Jake (J10)."),
             ("对照决定第 6 节逐条打勾；结论：用哪个工具或自建（计划 U1）。", "ticked item by item against decisions section 6; conclusion: which tool, or build our own (plan U1)."),
             crit("light_green", ("把两个工具装上，实际操作一遍表里标“文档”的格子", "install both tools and actually try the cells marked \"documentation\" in the table"),
                  ("合成记录", "synthetic records"), NOT_SET),
             b04("no", "评估不依赖模型。", "The evaluation does not depend on the model."),
             deliverable_dir="docs/deliverables/U1-review-tool-evaluation/"),
    new_card("U2", ("审核界面最小可用版", "Review interface, minimum version"), "delivery", "light_green", "in_sample",
             ("任务 10：自建，只用标准库，只在本机运行。按发票列出颜色和按严重程度计数的标识，点开看到争议、模型说明和标识，四个按钮把决定和理由追加到 `reviewer_decision` 表。19 个测试通过；在开发集全量运行库上只读启动，列出 953 笔争议、813 张发票。还没有人扮审核员走过一遍",
              "Task 10: self-built, standard library only, local only. It lists invoices with colour and flags counted by severity; opening one shows the disputes, the model's explanation and the flags; four buttons append the decision and reason to the `reviewer_decision` table. 19 tests pass; started read-only on the full dev run database it lists 953 disputes and 813 invoices. Nobody has walked through it as a reviewer yet"),
             ("审核员用的本地网页：看每张发票、每笔争议读得怎么样，记录自己的决定。界面不对费用该不该付给任何建议。", "a local web page for reviewers: see how each invoice and dispute was read and record their own decision. The interface gives no suggestion on whether a charge should be paid."),
             ("`src/freight_lineitems/review_ui.py`、`review_ui.html`，测试 `tests/test_review_ui.py`。决定只追加，库里用触发器禁止修改和删除；只读模式下不出现按钮。", "`src/freight_lineitems/review_ui.py`, `review_ui.html`, tests `tests/test_review_ui.py`. Decisions are append-only, with database triggers forbidding update and delete; read-only mode shows no buttons."),
             ("`docs/deliverables/U2-review-ui/`：怎么启动、对照完成标准和决定第 6 节的逐项说明。", "`docs/deliverables/U2-review-ui/`: how to start it, and an item-by-item check against the done-when text and decisions section 6."),
             ("已完成最小可用版。", "the minimum version is done."),
             ("直接读运行库 `run.sqlite`，写同一个库的 `reviewer_decision` 表；动作的取值从 schema 读，不在取值表里的动作一律拒绝。", "reads the run database `run.sqlite` directly and writes the `reviewer_decision` table of the same database; action values come from the schema, and any other action is refused."),
             ("前置：U1、B10、B09。被依赖：F3。", "depends on: U1, B10, B09. Needed by: F3."),
             ("批量操作、之前批次的上下文、距离、草稿编辑属于 U4（Optional）；四个按钮是否对应 OTM 的实际操作，等 Jake（J10、J11）。", "bulk actions, earlier-batch context, distance and draft editing belong to U4 (Optional); whether the four buttons match the real OTM actions waits for Jake (J10, J11)."),
             ("按发票列出颜色和按严重程度计数的标识，可按“有没有提醒”筛选；点开看到争议、模型说明、标识；争议一层四个按钮记录决定和理由；读我们的库（计划 U2）。", "invoices listed with colour and flags counted by severity, filterable by \"has reminders\"; opening shows disputes, model explanation, flags; four buttons at dispute level record decision and reason; reads our database (plan U2)."),
             crit("dark_green", ("组员扮审核员走查一遍（计划 U3），问题记成清单", "a teammate walks through it as a reviewer (plan U3); issues are listed"),
                  ("开发集全量运行库的副本（人工审核）", "a copy of the full dev run database (human review)"),
                  ("未设定，走查之前写入", "not set; to be written before the walk-through")),
             b04("no", "界面读已有运行的库，不调用模型。", "The interface reads the database of an existing run and does not call the model."),
             deliverable_dir="docs/deliverables/U2-review-ui/", test_report=T10,
             summary={
                 "claim": ("审核界面做到了计划 U2 完成标准的四项，并能打开开发集全量的运行库。", "The review interface meets the four items of plan U2's done-when text and opens the full dev run database."),
                 "tested": ("19 个 pytest（合成数据）；在开发集全量运行库上只读启动，查接口返回的汇总数；确认只读模式拒绝写入、库文件不变。", "19 pytest tests (synthetic data); started read-only on the full dev run database and its API aggregates checked; confirmed that read-only mode refuses writes and leaves the database file unchanged."),
                 "data": ("合成数据（测试）；开发集全量运行库 953 笔争议（样本内）。", "Synthetic data (tests); the full dev run database, 953 disputes (in-sample)."),
                 "result_vs_threshold": ("列出 953 笔争议、813 张发票；写入请求被拒绝，库文件校验值前后相同。没有数字门槛。", "Lists 953 disputes and 813 invoices; a write request is refused and the database checksum is the same before and after. No numeric threshold."),
                 "limits": ("记录决定只在合成数据的测试里和样本 A 上试过；没有人工走查；距离、之前批次的上下文、批量操作没做（U4）。", "recording decisions was exercised only in synthetic-data tests and on sample A; no human walk-through; distance, earlier-batch context and bulk actions are not built (U4)."),
             }),
    new_card("K1", ("skill 文件夹、架构说明、README", "Skill folder, architecture note, README"), "delivery", "yellow", "in_sample",
             ("任务 10：`skill/freight-dispute-line-items/`（SKILL.md v1.2、说明、5 条合成例子）、`docs/architecture.md`、根目录 README 都已写好，10 个测试校验合成例子。运行说明还没有由作者以外的人照着做过，课程对文件夹结构的要求也没有对照过，所以是黄",
              "Task 10: `skill/freight-dispute-line-items/` (SKILL.md v1.2, a README, 5 synthetic examples), `docs/architecture.md` and the root README are written; 10 tests validate the synthetic examples. Nobody other than the author has followed the run instructions, and the folder has not been checked against the course's structure requirement, so the card is yellow"),
             ("课程要求的 skill 文件夹，以及让别人能看懂、能照着跑的说明。", "the skill folder the course requires, and documentation that lets someone else understand and run the project."),
             ("仓库版的例子是新写的 5 条合成例子；运行时仍用 git 忽略的开发集例子，那个文件不存在时才退到合成例子，并在版本信息里标明。", "the repository copy uses 5 newly written synthetic examples; at run time the git-ignored dev examples are used, and only when that file is absent does the run fall back to the synthetic ones, recorded in the version information."),
             ("`skill/freight-dispute-line-items/`。", "`skill/freight-dispute-line-items/`."),
             ("已写好。", "written."),
             ("例子用合成文本，不取自开发集；说明里写清两套例子库的区别。", "examples are synthetic, not taken from the dev split; the README explains the difference between the two example libraries."),
             ("前置：B05、B06。被依赖：F3。", "depends on: B05, B06. Needed by: F3."),
             ("课程对 skill 文件夹结构的具体要求，由我对照一次。", "the course's exact structure requirement for the skill folder is to be checked once by me."),
             ("课程要求的 skill 文件夹结构；运行说明能照做（计划 K1）。", "the skill folder structure the course requires; the run instructions can be followed (plan K1)."),
             crit("light_green", ("作者以外的人在一份干净的检出上照 README 做一遍；对照课程要求核对文件夹结构", "someone other than the author follows the README on a clean checkout; the folder structure is checked against the course requirement"),
                  ("仓库本身；合成例子", "the repository itself; the synthetic examples"), NOT_SET),
             b04("partly", "文档本身不依赖模型；照着跑到调模型那一步需要密钥。", "The documents do not depend on the model; following them through the model step needs a key."),
             deliverable_dir="skill/freight-dispute-line-items/", test_report=T10),
    new_card("J01", ("给 Jake 的问题清单", "Question list for Jake"), "delivery", "yellow", "none",
             ("任务 10：原来的 14 个问题压成 10 个，写在 `docs/client/jake_questions.md`，英文部分可以整段发。**一个都还没有发**，也没有任何答复",
              "Task 10: the original 14 questions were condensed to 10 in `docs/client/jake_questions.md`; the English part can be sent as is. **None has been sent** and there is no answer yet"),
             ("向客户确认的问题：问题、答复、回填位置的唯一记录。", "the questions to confirm with the client: the single record of question, answer and where the answer is written back."),
             ("清单已写好，按“答复对实现的改动大小”排序；发送和回填没有开始。", "the list is written, ordered by how much an answer would change the implementation; sending and writing back have not started."),
             ("`docs/client/jake_questions.md`（没有单独的交付物文件夹）。", "`docs/client/jake_questions.md` (no separate deliverable folder)."),
             ("可以马上发。", "can be sent now."),
             ("答复回来后改清单第 3 节的状态列，并回填到决定记录和相关卡片。", "when answers arrive, update the status column in section 3 of the list and write them back to the decision record and the cards concerned."),
             ("前置：无。被依赖：B09、C3、U2、M1 里标着“等 Jake”的假设。", "depends on: none. Needed by: the assumptions marked \"waits for Jake\" in B09, C3, U2, M1."),
             ("什么时候发、用什么方式发，由我决定。", "when and how to send is decided by me."),
             ("问题—回答—回填位置的跟踪表；回答回填到决定记录和卡片（计划 J01）。", "a tracking table of question, answer and write-back location; answers written back to the decision record and the cards (plan J01)."),
             crit("light_green", ("见完成标准", "see done-when"), ("Jake 的答复", "Jake's answers"),
                  ("10 个问题都有答复或明确的“不回答”，并已回填 `[建议，待确认]`", "all 10 questions have an answer or an explicit \"no answer\", written back `[suggestion, to be confirmed]`")),
             b04("no", "不依赖模型。", "Does not depend on the model.")),
]


def main() -> None:
    text = P.read_text(encoding="utf-8")
    cut = text.index("\nmeta:") + 1
    header, data = text[:cut], yaml.safe_load(text)
    if any(c["id"] == "S1" for c in data["cards"]):
        raise SystemExit("already migrated (card S1 exists)")
    header = header.replace("#   deliverable_dir ", HEADER_ADD + "#   deliverable_dir ")
    assert HEADER_ADD in header

    m = data["meta"]
    m["updated"] = "2026-11-10"
    m["task"] = b("`docs/tasks/cc_task_10_autorun_leg2.md`（任务 10）", "`docs/tasks/cc_task_10_autorun_leg2.md` (task 10)")
    m["colors"]["grey"]["meaning"] = b("不按证据定色：由我本人维护，或已按决定删除", "not coloured by evidence: maintained by me personally, or removed by decision")
    m["tiers"] = {
        "must": {"name": b("Must", "Must")},
        "optional": {"name": b("Optional", "Optional")},
        "foundation": {"name": b("基础", "Foundation")},
    }
    m["must_note"] = b(
        "看板从任务 10 起按 11 月 5 日计划（`docs/plan/2026-11-05_workload_v2.zh.md` 第 3 节）的 23 个 Must 任务重排：栏是计划的工作线，每张卡标明对应的计划任务。卡片编号不变，所以卡片编号和计划编号是两套：卡片 D1、D2、V1 不是计划任务 D1、D2、V1，以“计划任务”一列为准。任务的工时、负责方和状态在 [`progress.yaml`](progress.yaml)，汇总在 [`progress.zh.md`](progress.zh.md)。",
        "From task 10 the board follows the 23 Must tasks of the 2026-11-05 plan (`docs/plan/2026-11-05_workload_v2.zh.md`, section 3): columns are the plan's work lines and every card names its plan task. Card IDs are unchanged, so card IDs and plan IDs are two separate sets: cards D1, D2, V1 are not plan tasks D1, D2, V1; the \"plan task\" column is authoritative. Hours, owner and status per task are in [`progress.yaml`](progress.yaml), summarised in [`progress.zh.md`](progress.zh.md) (Chinese only).")
    m["progress"]["note"] = b(
        "分母只算对应 Must 任务的非灰卡片（`tier: must`），每张权重 1。灰卡（由我维护的、已按决定删除的）、Optional 卡、计划之前完成的基础卡都只展示、不进分母（项目负责人 2026-11-10 确认）。黄卡不算部分分（黄卡做了多少没有测量，算分会让数字无法核对），黄卡张数单列。成型度 = Σ权重(浅绿 + 深绿) ÷ Σ权重(分母)；验证度 = Σ权重(深绿) ÷ Σ权重(分母)。这两个数按卡片的证据算，和 `progress.zh.md` 里按工时算的工作量、完成度不是一回事。",
        "The denominator counts only non-grey cards mapped to a Must task (`tier: must`), weight 1 each. Grey cards (maintained by me, or removed by decision), Optional cards and foundation cards finished before the plan are shown but left out (confirmed by the project owner on 2026-11-10). Yellow cards get no partial credit (how much of a yellow card is done is not measured, so partial credit would make the number unauditable), and the yellow count is shown separately. Shaped = Σweight(light green + dark green) ÷ Σweight(denominator); Verified = Σweight(dark green) ÷ Σweight(denominator). These two numbers follow card evidence and are not the same thing as the hour-based workload and completion in `progress.zh.md`.")
    m["rules"]["zh"][2] = "分析类卡片（A2 问题盘点、A3 设计方案、U1 工具评估）的“检验”是脚本可复现与数字核对，按实际情况标级别，卡片里写明它是分析类。"
    m["rules"]["en"][2] = "For analysis cards (A2 problem inventory, A3 design proposal, U1 tool evaluation) the \"check\" is script reproducibility and number cross-checking; the level is stated as it actually is, and the card says it is an analysis card."

    data["columns"] = [{"id": i, "name": b(z, e)} for i, z, e in COLUMNS]
    data["overview_edges"] = EDGES
    by_id = {c["id"]: c for c in data["cards"]}
    for c in NEW:
        assert c["id"] not in by_id, c["id"]
        by_id[c["id"]] = c
    for cid, upd in UPD.items():
        by_id[cid].update(upd)
    cards = []
    for cid, col, tier, tasks in LAYOUT:
        c = by_id.pop(cid)
        c["column"], c["tier"], c["plan_tasks"] = col, tier, tasks
        if tier != "must":
            c["weight"] = 0
        # stable key order: id, column, tier, plan_tasks first
        cards.append({"id": c["id"], "column": col, "tier": tier, "plan_tasks": tasks,
                      **{k: v for k, v in c.items() if k not in ("id", "column", "tier", "plan_tasks")}})
    assert not by_id, list(by_id)
    data["cards"] = cards
    body = yaml.dump(data, Dumper=yaml.SafeDumper, allow_unicode=True, sort_keys=False, width=10**6)
    P.write_text(header + body, encoding="utf-8")
    print(f"wrote {P.name}: {len(cards)} cards")


if __name__ == "__main__":
    main()
