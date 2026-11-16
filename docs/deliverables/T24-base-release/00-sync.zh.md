# T24 汇报：Base v1 发布包
**`base-v1` = `685cd52`**（分支 `mvp-v1`，此前标签都保留；本汇报提交在标签之后，同 T23c 做法）。没推送，没改代码、规则、skill、给模型看的文字，没调模型。测试 296 通过、2 跳过（读测试集编号的两个）。

**改了哪些文件**（4 个提交）：
- 新增 `docs/flow.md`、`docs/reports/README.md`；`docs/reports/midterm_report.md` 由 `docs/status/2026-11-16_midterm_report.md` 移来并更新；`docs/reports/team_update.md` 重写，替代 `docs/status/2026-11-16_team_update.md`；`docs/reports/case_study_memo.md` 加入跟踪。两处旧位置各留一行指向新位置（中文中期汇报和进度文件里的链接不坏）。改动文件的相对链接和路径检查：0 个坏链。
- 改：`README.md` 顶部加 Base v1 小节（Base v1 = `mvp-v1.4` + 本任务文档，链接报告目录和流程图）；项目总结中英（版本名、数字、审计一句、第 24 轮一行）；中文中期汇报（同样的数字和链接）；任务书。
- 中期汇报数字：开发集送人工 226/908（运行时 225，存档读法按现行检查重放后贷记核对多送 1 条）；放行但总额错 0/561；注入按文字去重 33/35；独立审计 1 个阻断 + 3 个重要，全部修好并经复查；下一步只写到方向。

**流程图里的计划板块**（半透明、虚线框、标 planned，各带一行说明接在哪）：跨批次历史（`prior_history`）、读历史的 skill（关系建议入口）、取代用词如 REVISED（接票货汇总）、按票货查看的审核界面（接客户表）、审核反馈回流到规则调整（接审核决定导出）、更强的注入筛查（开源检测模型，接注入筛查）。用本机 Mermaid 11.16 在无头 Chrome 里渲染核对：流程图和备忘录的图都能解析出图，没有 "Unsupported markdown"。

**案例备忘录核对**（对照 11 月 15 日第四轮运行、第三轮运行和 mock 源文件）：行号、订单、金额、文字、数字表、路由、模型原话、检查、标识、建议、汇总、字段名都一致；没有 markdown 链接，引用的两份接口说明路径存在。只改一处：客户表税行标签原写 `HST - Harmonized Sales Tax`，实际输出是 `HST - HARMONIZED SALES TAX`。

**扫描**（任务 11 脚本，`base-v1` 全部 411 个被跟踪文件；导出分支结果逐处相同）：比 `mvp-v1.4` 只多 2 处，都是合成或测试邮箱（备忘录里 mock 的 `.invalid` 地址、T23c 汇报转述的 `someone@example.com`）；无密钥，`.env`、`data/` 不在跟踪里。人工过 `docs/reports/`、`docs/flow.md`：没有真实原文、真实编号、人名（备忘录里的人名、承运商、编号都是 mock 合成的）。

**⚠ 要你先定**：用 `gh` 查到团队仓库是 **PUBLIC**。整棵树里有从 11 月 5 日基线 `5497fd2` 继承来的命中：真实原文整句 135 处（14 个文件：`docs/analysis/01_problem_inventory.md`、`01b_version_pairs.md`、`02_design_proposal.md`，它们在 `docs/deliverables/A2-*`、`A3-*` 的副本，`scratch/prototype/` 几个文件等），人名候选 26 处，承运商代码 2 处。不是本任务带进来的，基线已在团队仓库 `main` 的历史里，也就是现在已经公开。按“推上去的每个文件都要能公开”这些不合格。我没有动：清理要删文件，团队仓库上已有的还得重写历史。建议先定怎么处理，再推送。

**导出**：`team-update-base-v1` = `d946fd9`，父提交是已推送的 `39010ba`，树和 `base-v1` 完全相同。推送命令（上面那件事定了再执行）：
`git push team team-update-base-v1`
删除团队仓库旧分支（删不删由你定；新分支包含它的历史）：`git push team --delete team-update-mvp-v1`

**状态板**：状态文件已检查，无变化（只动了文档，没有新测试报告）；流程结构没变，没重新生成 Archify 图。
