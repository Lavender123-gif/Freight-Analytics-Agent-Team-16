# T12 摸底：Jake 回复之后，仓库现在是什么情况

日期：2026-11-13。分支 `autorun-leg2`。本轮没有调用模型，没有读测试集和预留 mock，没有改 `src/`、规则、SKILL.md、测试、cards.yaml。

本文的数字都来自 `scripts/` 下的五个只读脚本，统计范围是开发集（953 行）和已留存的运行结果。行级明细只写在 git 忽略的 `data/interim/deliverables/T12/`。

| 脚本 | 回答哪一节 |
|---|---|
| `scripts/s1_dev_facts.py` | 第 6、7 节 |
| `scripts/s2_bol_replay.py` | 第 5 节（用留存读法按票货汇总） |
| `scripts/s3_delta_inventory.py` | 第 4、9 节 |
| `scripts/s4_annotation_integrity.py` | 第 8 节 |
| `scripts/s5_recolour_replay.py` | 第 4 节（撤掉 Delta 后颜色怎么变） |

## 0. 任务书与仓库对不上的地方

按任务书第 0 节，以仓库为准，这里只记录，不调和。

| # | 任务书的说法 | 仓库的实际情况 |
|---|---|---|
| 1 | 上一个交付目录是 `T09-autorun-leg1` | 之后还有 `T10-autorun-leg2`、`T10-redaction-comparison`、`U1`、`U2`、`V3a`，以及任务 11（团队导出，没有交付目录）。所以本轮编号是 T12 |
| 2 | 待决清单要标 P-07 和 P-09 到 P-19 | 清单已到 P-25。P-09、P-15、P-18、P-19 在第二段已经做完 |
| 3 | C1 要撤掉 `CLAIM.RECON.SUM_MISMATCH` | 运行时没有这个标识。它是原型和 88 个边界用例里的名字。现在的对应物是 `CLAIM.DELTA.*` 六个标识，在 `agent.py` 的 `DeltaJudge` 里 |
| 4 | C3 说 `reconcile` 工具保留一半，工具数仍为 5 | 运行时没有 `reconcile` 工具（任务 09 按决定 3.1 删了）。现在是 6 个工具。“各项对合计、税额对税率”已经在 `checks.py` 里由代码做，不是工具 |
| 5 | C1 说“用 Delta 反推税额” | 没有反推。现有的是：原文写了税但没写税额时，`DeltaJudge` 允许“各项加按税表算出的税”也算与 Delta 一致（`agent.py:50`） |
| 6 | C1 说“历史比对里依赖 Delta 的项” | `src/` 里没有历史比对（R1c 没做）。依赖 Delta 的历史规则只存在于原型和 8 条边界用例 |
| 7 | C1 说重试 69 次、0 次改口 | 这是第一段 A 加 B2 加 mock 的数。第二段开发集全量是 44 条首次不一致、4 条修改后一致 |
| 8 | 1.2 第 1 条：Delta 是文本里每个 `$` 金额之和 | 开发集上 886 行带 `$` 的记录里 853 行成立，33 行不成立（见第 6 节） |
| 9 | 1.4：P3 有 2 行计入没选类别、1 行标成单价又标了计入 | 我数到的是 3 行和 2 行（见第 8 节） |

## 1. 仓库现状

- **分支**：`autorun-leg2`，没有推送。工作区有一处不是本轮产生的未提交改动：`scratch/annotation/build_packs.py`（把标注包的说明页改成只有英文）。本轮没有碰它，也没有提交它。
- **第一段验收节点之后的提交**：第一段的末端是 `1bde08d`。之后 16 个提交，全部在 2026-11-10：任务 10 第 1 到 7 节 13 个，任务 11（团队导出和清理）3 个，末端 `299c79e`。
- **测试**：`uv run pytest` 160 通过，2 跳过，0 失败。
- **预算账本**：46 次运行，累计 **71.67 美元**，上限 110 美元，剩 38.33 美元。时间范围 2026-11-10 21:58 到 2026-11-11 01:32（UTC）。四类 token：input 101,345；output 4,771,551；5 分钟缓存写入 4,035,708；1 小时缓存写入 0；缓存读取 136,579,661。金额是按 Sonnet 5.5 官方单价折算的 API 价格代理值，不是账单。其中第一段 24 次运行 32.86 美元。

## 2. 验收节点之后那组指令做了没有

| 指令 | 状态 | 结果 |
|---|---|---|
| 开发集全量运行 | 做了（任务 10 第 3 节），运行 `devFull-4823` | 953 条全部有结果：解析通过 760 / 建议人工 188 / 建议退回 5。首次与 Delta 不一致 44 条，其中 4 条修改后一致、38 条坚持、1 条用完重试、1 条强制检查最终不通过。花费 7.67 美元。注意它是在 SKILL.md v1.1 加旧脱敏下跑的，最终版本（v1.2 加白名单脱敏）没有跑全量（待决 P-23） |
| 公开 mock 的运行间波动 | 做了，同一版本三遍 | 主张金额正确 329 / 327 / 330（宽度 3）；解析通过 142 / 140 / 140；建议人工 228 / 230 / 229；建议退回 5 / 5 / 6；三遍颜色完全相同的行 357 / 375。见 `docs/autorun/tuning_log.zh.md` 后半 |
| 进度文件和计算脚本 | 做了 | `docs/status/progress.yaml`、`progress.zh.md`，脚本 `scratch/plan/progress.py`，有测试 |
| 验收包 README 的两点补充说明 | **没做** | `docs/autorun/acceptance/README.zh.md` 最后一次改动是第一段末端 `1bde08d`，之后没有动过。仓库里也找不到这两点是什么（任务 10 的任务书没有这一条）。停在：需要你告诉我是哪两点 |

## 3. 待决清单逐条

依据：`docs/autorun/pending.zh.md`。“失效”指问题本身不再存在；“已有答案”指第 1.3 节或 Jake 的回复给了结论，但代码还没跟上。

| 编号 | 问题 | 现在的状态 | 依据 |
|---|---|---|---|
| P-07 | Delta 为 0 的读法进不进下游导出 | **失效** | B1：Delta 不再是核对依据，“无锚点”这个概念没有了 |
| P-09 | 先量 mock 波动再调优 | 已在第二段做完 | 任务 10 第 3 节 |
| P-10 | mock 的 `control_clean` 里那类对照答案对不对 | **仍然有效**，归 Codex | 并入 mock 更新 |
| P-11 | Delta 把各项加合计算了两次 | **已有答案** | Jake Q2 和 1.2 第 1 条：这是 Delta 的算法造成的，不是读法的问题。对应标识随 C1 撤掉 |
| P-12 | “不一致”回馈几乎不改变读法 | **已有答案**（如果你确认 C1） | C1 把回馈整个撤掉 |
| P-13 | 模型自报疑问单独送人工 | 仍然有效，维持 | 第二段按事先规则维持。Jake Q1 把“措辞不清”列为审核员最关心的两类之一，方向一致 |
| P-14 | 三档取代计分 | 仍然有效，维持 | C6 说“上调权重”，但三档下没有权重，见调整计划 |
| P-15 | 带 `$` 不计入的依据检查 | 已在第二段做完 | |
| P-16 | 例子数据来自具体承运商 | 仍然有效，维持 | |
| P-17 | 脱敏豁免词取自代码表 | 仍然有效，维持 | |
| P-18 | 读取层硬检查和 deny 规则 | 已在第二段做完 | |
| P-19 | “有金额无费用名”由模型触发 | 已在第二段定下并做完 | |
| P-20 | 白名单脱敏的两个副作用 | 仍然有效，等你定 | |
| P-21 | 护栏对比里注入一项没到门槛 | 仍然有效，等你定 | |
| P-22 | 护栏的作用是让错误被看见 | 仍然有效。结论用的是 mock 上的主张金额正确数，不依赖 Delta | |
| P-23 | 用最终版本重跑开发集全量 | **被取代**：撤掉 Delta 回馈后提示词会变，全量必须重跑一次，和这一项合并 | C1 |
| P-24 | 审核界面的 APPROVE 按钮名 | 仍然有效，等你定 | |
| P-25 | 标注包的模板上限 | 仍然有效。标注已经回来，现在改不了抽样，只能在报告里写明 | |

此前已定、现在与新信息冲突的三项（P-01 重试次数、P-02 仍不一致的不进下游、P-04 Delta 为 0 送人工），列在调整计划第 3 节。

## 4. Delta 影响清单

### 4.1 运行时代码（`src/freight_lineitems/`）

| 位置 | 现在的作用 | 撤掉后什么跟着失效 |
|---|---|---|
| `agent.py:41-53` `DeltaJudge.judge` | 拿计入金额之和比 Delta，给出 MATCH / MISMATCH / NO_ANCHOR | `delta_check`、`delta_consistency` 两个字段没有来源 |
| `agent.py:32-37` `INCONSISTENT_MESSAGE`，`agent.py:116-126` | 不一致时回给模型一次，让它坚持或修改 | 回馈轮没有了；`response_type` 的 INSISTED 不再有用途，REVISED 只用于强制检查退回之后 |
| `agent.py:55-78` `explain_mismatch` | 给审核员的两条解释：差额等于原文某几个金额、Delta 等于各项加合计 | 两个提示标识没有了 |
| `agent.py:157-167`、`196-205` | 生成 `CLAIM.DELTA.*` 四个结果标识 | 同上 |
| `pipeline.py:70-75` | `REC.FIELD.DELTA_ZERO / MISSING / NEGATIVE` 三个标识，都是送人工 | 开发集全量上 11 条只因 “Delta 为 0” 送人工的记录会变色（见 4.5） |
| `pipeline.py:105`、`147-158` | 把 Delta 交给 `DeltaJudge`；输出里写 `delta_consistency`、`first_check` | 下游脚本读这两个字段的地方都要改 |
| `duplicates.py:28-32` `content_key` | 行层面查重的键里含 Delta | 开发集上去掉 Delta 后分组数不变（都是 908），见第 5 节 |
| `db.py:27` `DOWNSTREAM_OK`，`db.py:221-237` `export_facts` | 下游导出只收“通过检查、与 Delta 一致、没有送人工标识”的记录 | 导出条件要重写；现在的 760 条这个数作废 |
| `db.py:121` | 行指纹里排除 `Invoice Dups Removed` 和 `Dispute Status` | 不受影响，保留 |
| `db.py:140`、`159`、`171` | 把 `invoice_amount`、`delta`、`delta_consistency`、`delta_check` 写进库 | 表里这几列要么停写，要么改成“Excel 基线”含义 |
| `review_ui.py:201-228`、`263-264` | 争议一层显示 Delta 和各次尝试的比较结果；发票一层显示“模型读数合计对 Delta 合计” | 界面上这一块要换成 Jake 的表 |
| `records.py:33-34`、`57`、`72` | 读入 `Delta`、`Invoice Amount`，并要求这两列存在 | 保留读入（C2 要当基线）；“必须存在”可以放宽 |
| `schemas.py`、`checks.py`、`tools.py` | 只在注释里提到“这里没有 Delta” | 注释要改，逻辑不动 |

`Invoice Dups Removed` 在运行时只出现在 `db.py:121` 一处，没有任何逻辑读它（决定 5.5）。

### 4.2 规则和配置

| 位置 | 内容 |
|---|---|
| `config/rules.yaml:23-25` | `REC.FIELD.DELTA_ZERO / MISSING / NEGATIVE`，三个都是 attention |
| `config/rules.yaml:55-61` | `CLAIM.DELTA.*` 六个：FIRST_MISMATCH（info）、MATCH_AFTER_REVISION、MISMATCH_INSISTED、MISMATCH_UNRESOLVED（attention）、TOTAL_COUNTED_TWICE_PATTERN、DIFFERENCE_MATCHES_AMOUNTS（info） |
| `config/rules.yaml:83-85` | 上位关系里三条与空文本配对的 `CLAIM.DELTA.*` |
| `config/rules.yaml:105` | `agent.max_delta_feedback_rounds: 1` |
| `config/rules.yaml` `number_features.difference_explanation` | 只给 `explain_mismatch` 用 |
| `config/schema_v1.yaml` | `dispute.delta`、`dispute.invoice_amount`、`parse_run.delta_consistency`、`parse_attempt.delta_check`、`pipeline_run.max_delta_feedback_rounds` |

`taxonomy.yaml`、`tax_rules.yaml` 不含 Delta。

### 4.3 SKILL.md

- 第 33 行：告诉模型它拿不到发票金额。保留。
- 第 70 到 71 行：告诉模型代码会把计入金额之和与“记录在案的调整额”比较。要删。
- 第 128 到 134 行：`inconsistent` 这个结果的处理办法（坚持或修改）。要删。
- 测试 `test_skill_and_tools_never_mention_delta` 保证 SKILL.md 和工具里没有 “delta” 字样，这一条继续成立。

### 4.4 测试、边界用例、状态卡片

- **测试**：7 个文件 39 行提到 Delta。`tests/test_agent.py` 24 行，其中直接测 `DeltaJudge` 和回馈轮的测试要删或改写；`tests/test_db.py`、`tests/test_review_ui.py` 各 4 行，是造数据时填的字段；`tests/test_tools_and_rules.py` 2 行测上位关系；`tests/helpers.py` 的 `record()` 把 Delta 当必填参数；`tests/test_duplicates.py` 1 行测“文字相同、Delta 不同不算副本”，这条在 C4 下结论要反过来。
- **88 个边界用例**：18 条的目标规则或期望诊断依赖 Delta 或历史：BC003、BC013、BC014、BC020、BC041、BC054、BC055、BC056、BC059 到 BC064、BC066、BC068、BC069、BC070。其中期望 `CLAIM.RECON.SUM_MISMATCH` 的 3 条，期望 `REC.FIELD.DELTA_ZERO` 的 2 条，期望 `REC.FIELD.DELTA_NEGATIVE` 的 2 条，历史规则 8 条（里面 `HIST.REPEAT.SAME_DELTA`、`HIST.AMOUNT.EQUALS_EARLIER_DELTA` 直接拿 Delta 做比较）。另有 1 条 `REC.FIELD.CURRENCY_MISSING` 受 B4 影响。
- **状态卡片**：34 张里 6 张的文字提到 Delta：B01、B03、B04、B05、B08、V3。受影响的不止这 6 张，完整方案见调整计划第 5 节。

### 4.5 撤掉之后颜色怎么变（留存的开发集全量重算，没有调模型）

| 方案 | 解析通过 / 建议人工 / 建议退回 |
|---|---|
| 现行规则 | 760 / 188 / 5 |
| 撤掉全部 Delta 标识（C1） | 766 / 177 / 10 |
| 再把“提到税”降为提示（C6） | 781 / 162 / 10 |
| 再把“写了税没写税额”升为送人工 | 778 / 165 / 10 |

- 只因 Delta 标识送人工的有 11 条，全部是 “Delta 为 0”。撤掉后 6 条变成解析通过，5 条变成建议退回（它们是空文本或只有数字，原来被 “Delta 为 0” 盖住）。
- 与 Delta 不一致的 39 条（38 条坚持、1 条用完重试）撤掉标识后颜色不变，它们都另有送人工的理由。
- 只因“提到税”送人工的有 6 条；带税标识的共 22 条，其中 5 条写了税没写税额。
- 回馈轮的成本：全量 1028 次模型调用里，64 次发生在首次不一致之后。

### 4.6 脚本和文档

`scratch/analysis/`（13 个文件 190 行）、`scratch/prototype/`（12 个文件 137 行）、`scratch/deliverables/`（7 个文件 55 行）、`scratch/autorun/`（9 个文件 27 行）都有按 Delta 统计的逻辑，多数是历史分析，不在运行路径上。仍在使用、需要跟着改的是 `scratch/autorun/` 下的 `acceptance_summary.py`、`analyze_run.py`、`build_results_page.py`、`compare_rounds.py`、`mock_eval.py`，以及 `scratch/eval/v3a_off_arm.py`。

## 5. “一条记录”的假设

**现在以什么为单位**

| 部件 | 单位 |
|---|---|
| 读入（`records.py`） | Excel 的一行是一条记录，副本不合并（决定 5.3） |
| 模型调用（`pipeline.py`） | 一行调一次模型。开发集 953 行调 953 次 |
| schema（`config/schema_v1.yaml`） | `dispute` 一行一条；另有 `shipment`、`carrier_invoice`、`bill_record` 三张维表和 `dispute_source_row` 关联表 |
| 行层面查重（`duplicates.py`） | 键是（票货、承运商发票号、文字、Delta、Event Date），第二份起打 `DUP.ROW.COPY` 送人工 |
| 发票内查重（`duplicates.py`） | 同一承运商发票里同一个费用代码第二次计入，打 `DUP.INVOICE.SAME_CHARGE` 送人工。税代码跳过（决定日志 D-27） |
| 两种导出（`db.py`） | 一条争议一个对象 |
| 只读结果页、审核界面 | 按承运商发票分组，展开到每条争议 |

**已有什么**

- 开发集里承运商发票号和 SHIPMENT_GID 一一对应（813 对 813），所以现在的“发票”这一层实际上就是票货这一层。按发票分组的界面、发票内查重，改个名字就是按票货。
- `shipment` 表已有 `sap_bol`、`shipment_amount`、起讫地。同一票货的 Shipment Amount、承运商、起讫地在开发集上没有一处不一致。
- `DUP.INVOICE.SAME_CHARGE` 已经做了 A4 的一半：同一票货上更早出现过同一个费用代码就打标识，并指向更早的那一项。
- `dispute_source_row` 表已经留了“一条争议对应多行原始记录”的位置。
- 用留存的开发集全量读法做最简单的按票货汇总（`s2_bol_replay.py`），Jake 的两个例子都精确复现（变化额和新总额都与 Jake 的答案相同）。

**缺什么**

- 没有“票货汇总”这个对象：没有原始金额加各项费用加新总额的表，没有默认总额，没有另一种读法的总额。
- 没有取代逻辑。现在同一费用出现第二次只打标识，两项都算。
- 订单副本没有合并，每份都单独调模型、单独送人工。没有“订单数”字段。
- 没有票货一层的颜色。
- 同一说明内部的 BALANCE DUE 取代（A5）完全靠模型读，没有代码规则。

**规模（开发集，留存读法）**

- 813 票货，908 条不同的说明（按票货、Event Date、文字合并后），953 行。
- 722 票货只有一条说明，91 票货有两条以上。
- 91 票里，57 票出现“后一条说明里有与前面相同的非税费用代码”，也就是 A3 的取代会触发；37 票出现跨说明的相同金额。
- 91 票里，现在每条说明都是“解析通过”的只有 15 票。
- 有 10 票货存在 Event Date 完全相同的不同说明，其中包括 Jake 的例 1。
- 1 票货有一条说明的读法没通过强制检查。

## 6. 第 1.2 节在开发集上的复核

开发集：953 行，813 个 SHIPMENT_GID，811 个非空 SAP BOL。

| # | 任务书的说法（全量 1347 行） | 开发集上的数字 | 是否对得上 |
|---|---|---|---|
| 1 | Delta 是文本里每个 `$` 金额之和 | 带 `$` 的 886 行里 853 行相等；有两个以上 `$` 金额的 151 行里 121 行相等。例 1 两行的 Delta 与任务书一致（都是合计被算了两次） | **不完全**。33 行不相等：20 行 Delta 等于其中一个 `$` 金额；9 行 Delta 小于总和；2 行大于；1 行是空格千分位；1 行等于全部数字之和。规律不统一，所以“Excel 基线”只能直接用这一列，不能用公式重算 |
| 2 | Invoice Amount 逐行算 | 953 行全部满足 Invoice Amount = Shipment Amount + 本行 Delta。例 2 三条说明的数字与任务书一致 | 对得上 |
| 3 | Invoice Dups Removed 每票只留一行 | 813 票里 812 票恰好一行非零，1 票全为零，0 票多于一行。非零的 812 行都等于该行的 Invoice Amount。有多条说明的 89 票全部只留了一行。例 2 的 24 行里只有 1 行非零 | 对得上 |
| 4 | SAP BOL 与 SHIPMENT_GID 一一对应；SAP BOL 6 行为空 | 一一对应成立。空 SAP BOL 6 行，分属 2 个 SHIPMENT_GID（全量的 6 行都在开发集）。SHIPMENT_GID 无空值。Shipment Number 的前 7 位等于 SAP BOL 的第 6 到 12 位，947 行全部成立；263 个值对应 811 个 BOL | 对得上。补充：Shipment Number 这一列读出来是 9 个字符，后面带 `.0` |
| 5 | 每个 BOL 一个起点、一个终点、一家承运商 | 承运商、起讫的州、城市、地址，以及 Shipment Amount，不一致的票货都是 0 | 对得上 |
| 6 | 37 条说明出现在不止一行（多 59 行）；32 条每个 PK 一行（54 行）；5 条 PK 相同或为空（5 行） | 按（票货、Event Date、文字）分组：27 条（多 45 行）；22 条每个 PK 一行（40 行）；5 条 PK 相同或为空（5 行，其中 4 条 PK 全空、1 条 PK 相同） | 对得上。全量里那 5 条都在开发集。补充：如果键里不带 Event Date，是 27 条多 49 行，有 4 条是同一文字隔了时间再出现一次，那不是副本 |
| 7 | 417 个 BOL 没有 PK，722 个一个，15 个多个 | 290 / 513 / 10 | 对得上（量级相符） |
| 8 | 1154 个 BOL 里 124 个有不止一条不同说明 | 813 票里 89 票（87 票两条、2 票三条）。如果把“同一文字隔了时间再出现”也算不同说明，是 91 票 | 对得上 |
| 9 | 53 条文本在其他 `$` 金额后写 BALANCE DUE：0 / 32 / 21 | 99 条不同文本含 BALANCE DUE，其中 35 条前后都有 `$` 金额：等于前面金额之和 0 条；约等于前面某个金额的 1.03 到 1.07 倍 20 条；两者都不是 15 条 | 对得上 |
| 10 | 不重写旧金额的替换 21 对 | 19 对 | 对得上 |
| 11 | Purchased transportation 804 条，全部一家承运商，第一个金额 20 美元的 341 条 | 563 行（占开发集 59.1%），303 种不同文字，510 票货，1 家承运商；第一个 `$` 金额是 20 的 241 行；写作 SURCHARGE 的 262 行，写作 FEE 的 165 行 | 对得上 |
| 12 | Shipment Amount 中位数 131.70，809 个 BOL 低于 300 | 按票货中位数 137.81，813 票里 558 票低于 300 | 对得上 |

## 7. Jake 的两个例子在哪个集合

查法：只在开发集里按 SAP BOL 查，没有打开测试集。

| 例子 | 所在集合 | 开发集里的行 |
|---|---|---|
| 例 1 | **开发集** | 2 行，2 条不同说明，1 个 PK，两条说明的 Event Date 相同 |
| 例 2 | **开发集** | 24 行，3 条不同说明，8 个 PK，3 个不同的 Event Date |

三点需要你知道：

- 开发过程已经见过这两票货。代码表 `taxonomy.yaml` 的写法示例里就有例 1 两条说明的开头词；三个标注包里有 4 条记录属于这两票货。所以“复现这两个例子”是合理性检查，不能当作独立样本上的证据。
- 5 条运行时例子（SKILL.md 的例子库）不包含这两票货，也不包含与它们文字相同的记录。
- 例 2 用 Excel 的口径（Delta 按不同说明相加）与 Jake 的答案相同；例 1 用 Excel 的口径正好是 Jake 答案的 2 倍。

## 8. 标注文件的完整性

对照对象：本地留存的发出版本 `data/interim/annotation/packs/`，以及对照表 `key_dev.json`（135 个条目，105 条不同记录）。只核对结构，没有拿系统输出去比。

| | P1 | P2 | P3 |
|---|---|---|---|
| 条目数（收回 / 发出） | 45 / 45 | 45 / 45 | 45 / 45 |
| 行数（收回 / 发出） | 88 / 88 | 88 / 88 | 89 / 89 |
| 增加的行、删除的行、重复的行 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 条目顺序、行顺序 | 未变 | 未变 | 未变 |
| 原文、数字、上下文三列被改动 | 0 | 0 | 0 |
| 能对回开发集原始记录的条目 | 45 | 45 | 45 |
| 第 1 项（这个数字是什么）没填 | 0 | 0 | 0 |
| 标成金额但没填“是否计入” | 0 | 0 | **4** |
| 标成非金额却填了“是否计入” | 0 | 0 | **2** |
| 标了计入但没选类别 | 0 | 0 | **3** |
| 没填“有没有把握”的条目 | 0 | 0 | 0 |
| 写了备注的行 | 12 | 15 | 17 |
| 标注人编号 | 没填 | 没填 | 没填 |

- 三个文件与发出的包一致：没有增删行、没有改顺序、没有改文本，135 个条目都能对回原始记录。三包共有的记录 15 条，合并后 105 条。
- P3 有 9 行结构上不合规，P1、P2 为 0。任务书说的“数量和单价标反”属于内容问题，结构检查看不出来，我没有逐行判断。
- **票货层面的覆盖很薄**：105 条记录落在 95 个票货上，其中 73 票的全部说明都被标了；这 73 票里有两条以上说明的只有 8 票。也就是说，现有标注能评“单条说明读得对不对”，几乎评不了 A3 的取代逻辑。

## 9. 公开 mock 里已经过时的期望

范围：公开 mock（375 行、360 个事件、327 个票货），没有读预留 mock。只列清单，不改。

**依赖 Delta 的**

| 项 | 数量 | 说明 |
|---|---|---|
| 标准答案字段 `claim.sum_equals_delta` | 360 个事件都有（321 真、39 假） | 整个字段的含义作废 |
| `arithmetic_*` 六类 | 30 个事件 | 这一族是按“各项之和与 Delta 的关系”造的。`arithmetic_large_gap`、`arithmetic_total_double_count` 期望“建议退回”，`arithmetic_rounding_gap` 期望“建议人工”，理由都是与 Delta 的差额 |
| `understanding_balance_in_delta`、`understanding_balance_not_in_delta` | 10 个事件 | 用 Delta 来判定 BALANCE DUE 算不算 |
| `dedup_same_text_delta_conflict` | 5 个事件 | 文字相同、Delta 不同。C4 把 Delta 从合并键里去掉后，这一类的期望要重写 |
| `history_same_delta_new_text`、`history_105_multiplier` | 10 个事件 | 历史关系是按 Delta 定义的（“Delta 相同”“Delta 是前一条的 1.05 倍”） |
| 描述或问题说明里写到 Delta 的事件 | 65 个 | 上面几类加 `understanding_blank`、`number_mixed_currency` 等 |
| Delta 为 0 的行 | 5 行 | 期望“无锚点送人工”，随 C1 作废 |

**依赖“逐条记录”口径的**

| 项 | 数量 | 说明 |
|---|---|---|
| 有前一条事件的（`history_relation.has_prior`） | 29 个事件 | 只有逐条的期望，没有“这票货汇总后应该是多少”。A3 下 `history_restate`、`history_resubmission`、`history_105_multiplier` 应该是取代，`distinct_later_event` 应该是相加 |
| 有两行以上的票货 | 42 个 | 全部缺票货一层的期望总额和颜色 |
| 副本类 `dedup_exact`、`dedup_whitespace_case`、`suggested_duplicate_export_metadata_shift` | 15 个事件 | 期望“合并为一个事件”，与 C4 方向一致，但没有区分“每个 PK 一行”（正常）和“PK 相同或为空”（打标识） |

**受 B3、B4 影响的**

| 项 | 数量 | 说明 |
|---|---|---|
| 币种字段为 CAD 的行 | 51 行 | B4：全部按 USD |
| `number_no_currency`、`number_mixed_currency`、`suggested_currency_context_switch` | 15 个事件 | 币种类的期望要按 B4 重定 |
| `arithmetic_tax_no_amount` | 5 个事件 | 期望“建议人工”。C6 下理由要从“涉及税”改成“税额没写” |

**此前已经列过、仍然过时的**：`docs/autorun/mock_deterministic_review.zh.md` 里的清单（“建议退回”的范围、三档颜色等），以及 P-10 那类对照。

**仍然可用的**：每个事件的 `claim.items` 和 `current_claim_total`（单条说明读出来应该是多少），不依赖 Delta。所以“主张金额正确数”这个指标继续有效。
