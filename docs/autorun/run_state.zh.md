# 自主运行状态（任务 10，第二段）

新开会话或上下文被压缩后，先读本文件再继续。

- 任务书：`docs/tasks/cc_task_10_autorun_leg2.md`（第一段是 `cc_task_09_autorun_leg1.md`）
- 分支：`autorun-leg2`（从 `autorun-leg1` 开出，不推送）
- 账本：`docs/autorun/budget_ledger.jsonl`（上限 110 美元，含第一段）
- 决定日志：`docs/autorun/decision_log.zh.md`（到 D-49）
- 待决清单：`docs/autorun/pending.zh.md`（到 P-25）
- 规则改动前后数字：`docs/autorun/rule_changes_leg2.zh.md`
- 调优和 mock 波动：`docs/autorun/tuning_log.zh.md` 后半
- 进度文件：`docs/status/progress.yaml`、`progress.zh.md`，脚本 `scratch/plan/progress.py`
- 行级输出：`data/interim/runs/<run_id>/`；本段的日志和汇总 JSON 在 `data/interim/autorun/leg2/`（都是 git 忽略）
- 时间兜底：2026-11-12 12:00 本机时间

## 当前阶段

第二段全部做完，停点：等用户。

## 已完成（第二段）

- 第 1 节：规则改动五项（退回只留两种、P-13 维持、P-15 采用、P-18 读取层加 deny、P-06 合成例子）。
- 第 2 节：状态板按 Must 清单重排；进度文件和脚本；本段测试报告 `docs/deliverables/T10-autorun-leg2/`。
- 第 3 节：开发集全量 `devFull-4823`；mock 波动（三遍）；调优两轮（第 1 轮回退，第 2 轮保留，SKILL.md v1.2）；最终数字 A `rdAallowlist-49dd`、B2 `rdBallowlist-a1fa`、mock `finalMock-1ba4`。
- 第 4 节：脱敏测量工具、四个变体加一个并集、解析影响；默认改为 `allowlist`。
- 第 5 节：U1、U2、V1、V3a、K1。
- 第 6 节：标注包三个（git 忽略的 `data/interim/annotation/packs/`）、中英文指南、导入和一致率脚本。
- 第 7 节：`docs/client/jake_questions.md`。

## 没做（按任务书不做的）

R1c、P4b、其他 Optional、V4、M1、读预留 mock。

## 下一步

等用户回复。候选：发 Jake 清单；安排标注（H2a）后算 H3；定 P-20（白名单脱敏的副作用）后用最终版本重跑开发集全量；M1。

## 任务 11（2026-11-10，团队导出）

- 任务书：`docs/tasks/cc_task_11_team_export.md`。清理提交在 `autorun-leg2`；导出分支 `team-update-2026-11-10` 从基线 `5497fd2` 起，一个提交，内容与清理后的 `autorun-leg2` 相同。不由 CC 推送。
- 英文入口文件只在根目录：`PROGRESS_UPDATE.md`、`STATUS.md`（由 `cards.yaml` 生成）、`WORKFLOW.md`（由 `docs/status/flow_src/build_workflow_md.py` 生成）、`QUESTIONS_FOR_JAKE.md`。
- 扫描脚本和结果在 git 忽略的 `data/interim/prescan/`（`scan.py` 只扫基线之后新增的内容，`scan_tree.py` 扫一个提交的全部文件）。

## 任务 12（2026-11-13，Jake 回复后的摸底与重新规划）

- 任务书只在 git 忽略的 `data/incoming/2026-11-13/cc_task_replan_after_jake.md`（含客户邮件原文，不提交）。同一目录还有三个交回的标注包和 Jake 给的参考文件。
- 性质：只摸底、只规划。没有调模型（账本仍是 71.67 美元），没有读测试集和预留 mock，没有改 `src/`、规则、SKILL.md、测试、cards.yaml、mock。
- 产出：`docs/deliverables/T12-replan-after-jake/`：`00-sync.zh.md`（一屏结论）、`01-stocktake.zh.md`（摸底）、`02-adjustment-plan.zh.md`（调整计划）、`03-dev-plan.zh.md`（开发计划）、`scripts/`（五个只读脚本）。行级明细在 git 忽略的 `data/interim/deliverables/T12/`。
- 当前阶段：停点，等用户。要定的事列在 `00-sync.zh.md`。
- 下一步（用户确认之后）：按 `03-dev-plan.zh.md` 第 1.1 节做 T12-01 到 T12-06，全部不调模型；里程碑是 2026-11-16。
- 工作区里 `scratch/annotation/build_packs.py` 的未提交改动不是任务 12 产生的，没有动。

## 任务 13（2026-11-13，把费用代码表对到 Jake 的清单上）

- 任务书：`docs/tasks/cc_task_13_taxonomy_mapping.md`。客户材料（Addenda B 的 PDF）在 git 忽略的 `data/incoming/2026-11-13/`。
- 性质：只分析。没有调模型（账本仍是 71.67 美元），没有读测试集和预留 mock，没有用人工标注，没有改 `taxonomy.yaml`、`SKILL.md`、`src/`、`rules.yaml`、测试、mock、cards.yaml。
- 产出：`docs/deliverables/T13-taxonomy-mapping/`：`00-sync.zh.md`（一屏结论）、`01-mapping-report.zh.md`（正文，含 37 个代码的对应表）、`scripts/`（抽取、对应关系、覆盖统计、草稿生成）。清单全表、覆盖明细、清单草稿在 git 忽略的 `data/interim/deliverables/T13/`。
- 用的读法：开发集全量 `20261110-195411-devFull-4823`。
- 结果：37 个代码里 17 个直接对上、8 个一对多、6 个子项、6 个没有位置；1002 笔带费用名的金额 93.1% 落在清单之内（直接对上 24.9%，子项 61.9%，扩展项 6.6%，“其他”0.3%）。推荐以 Jake 的名称为根、只留相关条目的折中方案。
- 当前阶段：停点，等用户。要定的事列在 `00-sync.zh.md`。
- 抽取脚本需要 pdfplumber，用 `uv run --with pdfplumber` 临时带上，没有加进 `pyproject.toml`。
- 工作区里 `scratch/annotation/build_packs.py` 的未提交改动不是任务 13 产生的，没有动。

## 任务 14（2026-11-15 起，里程碑交付，然后第二、三段）

- 任务书：`docs/tasks/cc_task_14_milestone_build.md`。分支 `leg3-milestone`（从 `autorun-leg2` 开出，不推送）。交付目录 `docs/deliverables/T14-milestone-build/`。
- 账本沿用 `docs/autorun/budget_ledger.jsonl`，累计到 105 美元就停一切模型调用（上限 110，留 5 美元给终测）。
- 决定日志到 D-75（D-50 到 D-69 是用户 2026-11-15 确认的），待决清单到 P-31。
- 第一段（不调模型）：已做 T14-01 到 T14-09（撤 Delta、副本合并、票货汇总 `rollup.py`、两个例子的回归测试、代码表换算 `charge_map.py`、重放 `scratch/rollup/replay.py`、两项核对、币种和税、回填客户答复）。报告 `01-stage1-report.zh.md`。重放输出在 git 忽略的 `data/interim/rollup/<运行>/`。
- 第一段剩下：T14-10 进展报告（根目录 `PROGRESS_UPDATE.md`，旧版存档在 `docs/status/2026-11-10_PROGRESS_UPDATE.md`）、T14-11 团队导出分支 `team-update-2026-11-16`。
- 第二段：先把门槛写进 `docs/autorun/tuning_log.zh.md` 并提交，再跑 v1.3a、v1.3b。第三段：全量重跑、汇总对比、标注定稿、两组评估、mock 第三轮（看 `data/external/mock_public_r3/` 在不在）、文档。
- **第二、三段已做完（2026-11-15）**：三个提示词变体都没过事先写定的门槛，选定版本保留 v1.2 文字（`tuning_log.zh.md`）；全量重跑 `devFullV12-5d09`；标注定稿 `data/interim/annotation/final/`；评估一 82 / 82（达标），评估二未归类 8.8% / 5.4%（达标）；mock 第三轮 `mockR3V12-f0d3`。报告 `02-stage2-3-report.zh.md`，汇报 `00-sync.zh.md`。账本 98.00 美元，模型调用到此停止。
- 当前阶段：停点，等用户。
- **任务 14 补充（2026-11-15）**：建了本机人读区 `CC-response/`（26 轮、48 份报告副本，git 忽略）和 `00-索引.md`，对照表 `agent/cc_response_map.md`；评估一补了“说不清”19 条的去向（12 人工、2 退回、5 放过）；P-36 完成，生成方 9 处逐条对照写在第二、三段报告第 5 节。没有调模型。

## 任务 15（2026-11-15，混淆矩阵）

- 任务书 `docs/tasks/cc_task_15_confusion_matrix.md`；分支 `leg4-eval`（从 `leg3-milestone` 开出，不推送）；交付目录 `docs/deliverables/T15-confusion-matrix/`。没有调模型。
- 先写后算：`c91bc97`（定义、对照表 `scratch/eval/t15_problem_types.yaml`、目标在 V7 卡）、`7b4ddbc`（19 条重判）。计算 `scratch/eval/confusion.py`，方案查询 `scratch/eval/t15_proposals.py`，逐条结果在 git 忽略的 `data/interim/eval/t15/`。
- 结果：两套数据都没达到 Recall ≥ 95% 和 FOR ≤ 2%；方案五项等用户定（P-37）。P-35 已做。当前阶段：停点，等用户。

## 任务 16（2026-11-15，全量摸底）

- 任务书 `docs/tasks/cc_task_16_diagnosis.md`；分支 `leg5-diagnosis`（从 `leg4-eval` 开出，不推送）；交付目录 `docs/deliverables/T16-diagnosis/`。没有调模型，只分析，没有改系统。
- 先写后算在 `764dd8b`（`01-preregistration.zh.md`、`scratch/eval/t16_features.yaml`）；计算 `scratch/eval/t16_diagnosis.py`；逐条结果在 git 忽略的 `data/interim/eval/t16/`。
- 新增待决 P-39 到 P-41。当前阶段：停点，等用户。

## 任务 17（2026-11-15，落实修改并冻结）

- 任务书 `docs/tasks/cc_task_17_fixes.md`；分支 `leg6-fixes`（从 `leg5-diagnosis` 开出，不推送）；冻结标签 `t17-frozen`；交付目录 `docs/deliverables/T17-fixes/`。没有调模型。
- 规则 v1.3：三个新的送人工标识和脱敏前的模糊注入检测；BALANCE DUE 写在最前面那一项按条件没实施。决定 D-76 到 D-82；待决 P-42、P-43。
- 冻结：在第四轮 mock 和预留 mock 测完之前不改规则和代码（修 bug 除外，单独提交、单独记录）。当前阶段：停点，等第四轮 mock。

## 任务 19（2026-11-15，读一条说明的板块）

- 任务书 `docs/tasks/cc_task_19_reading_module.md` 和补充 `cc_task_19_addendum_interface.md`（都执行了）；分支 `leg8-reading`（从 `leg7-arch` 开出，不推送）；标签 `t19-reading`；交付目录 `docs/deliverables/T19-reading-module/`。
- 用户同意预算上限 145、停线 140（`budget.py` 默认 140）。本任务花 17.94 美元，账本累计 115.95。
- 回归运行：`devFullT19routed-055d`、`mockR3T19routed-4079`（`routed` + 注入筛查）；评分 `scratch/eval/t19_eval.py`，重放 `scratch/eval/t19_replay.py`，逐条结果在 git 忽略的 `data/interim/eval/t19/`。四条门槛全过，开关 `routed`。
- 决定日志到 D-94，待决到 P-48。
- 当前阶段：停点，等用户。下一步（用户定了之后）：跨说明、跨批次的板块；架构全部改完后跑第四轮 mock 和预留 mock。

## 任务 20（2026-11-15，MVP 收敛、第四轮 mock、中期软收尾）

- 任务书 `docs/tasks/cc_task_20_mvp_wrapup.md`。分支 `mvp-v1`（从 `leg8-reading` 开出），标签 `mvp-v1`；团队导出分支 `team-update-mvp-v1`（父提交 `5e28bde`，内容同标签），不由 CC 推送。
- 第 2 节全做：`pipeline.finish_batch` 把副本、票货汇总、客户费用名接进主流程，评估脚本走同一个函数；BALANCE DUE 不论位置（D-95）；gap 栏（D-96）；票货表导出；接口说明 `docs/shipment_output_contract.md`；扩展口；运行记录；离线运行和合成冒烟样例 `tests/fixtures/smoke/`；状态卡 19 张改说法。
- 第 3 节：第四轮 mock 当晚到了；口径先提交（`2d2e05b`），新增 122 条调模型 1.71 美元（`mockR4newT20-ab8a`）；结果 `docs/deliverables/T20-mvp/03-r4-results.zh.md`，没有据此改任何东西。
- 第 5 节：项目总结、中期汇报（中英）、组员更新、进度文件、状态页。第 6 节没做。
- 下一步：等用户定 P-49、P-52 到 P-54，推送导出分支；然后跨批次历史（X1）、审核界面重做（U3）。

## 任务 20b（2026-11-15 晚，中期提交前的补充指标和修正）

- 任务书 `docs/tasks/cc_task_20b_midterm_fix.md`。分支 `mvp-v1`，标签 `mvp-v1.1` = `7ec3637`（`mvp-v1` 保留）。不推送，不更新团队导出分支：等 Codex 审计（`docs/tasks/codex_audit_mvp.md`）和随后的修正完成后一起做。
- 第 1、2 节：`scratch/eval/t20b_midterm_eval.py`（事后定义的两个视图，不调模型）；放行但总额错 0/561，注入按文字分三组，12 个漏报出自两个模板。
- 第 3 节：中期汇报、项目总结（中英）、组员更新。第 4 节：审核页面表头读 `shipment_result.result`，页面全英文。
- 汇报 `docs/deliverables/T20b-midterm-fix/00-sync.zh.md`、正文 `01-results.zh.md`。
