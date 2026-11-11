# 期望值和阈值改动记录（任务 09，分支 `autorun-leg1`）

规则：为了通过测试而改期望值、阈值或检查逻辑是不允许的。确有理由的改动逐条记在这里，理由对应决定记录（"决定 x.y"）、任务书第 1 节（"第1节第n条"）或已确认的 bug。

## 1. 阈值（`config/rules.yaml` 对原型 `scratch/prototype/rules.yaml` rules-v0.1）

| 项 | 原型 | 现在 | 理由 |
|---|---|---|---|
| `tolerances.amount_abs` | 0.005 | 0.005 | 不变 |
| `tolerances.tax_abs` | 0.011 | 0.011 | 不变 |
| `tolerances.relation_abs`（新） | 数量×单价用 amount_abs 0.005 | 0.005 | 曾在实现时放宽到 0.011，边界用例 BC051 发现，无决定支持，已改回 |
| `tolerances.near_105` | [1.03, 1.07] | 删除 | 只用于历史比对（R1c，本段不做） |
| `escalation.score_threshold` 和各标识的 `points` | 3 / 1–2 分 | 删除，改为三档 | 决定日志 D-13；第1节第5条（颜色由规则算）。哪些记录颜色因此变化，见验收包 f |
| `auto_reject.*` | 空文本、只有数字在模型前自动打回 | 删除 | 决定 2.1、第1节第3条：每条记录都经过模型，模型前没有打回分支 |
| `retry.max_retries` | 2 | 拆成 `agent.max_repair_rounds` 2、`agent.max_delta_feedback_rounds` 1 | 决定 3.2；用户 11-10 确认 |
| `retry.stop_on_unchanged_resubmission` | true | 删除 | 决定 3.2：原样重提就是"坚持"，是正常结果，以 `INSISTED` 显式表达 |
| `agent.reconcile_max_calls` | 3 | 删除 | 决定 3.1：去掉试算工具 |
| `injection.patterns` | 7 条 | 加 4 条通用写法（忽略/绕过规则或指令、`SYSTEM:`、系统/管理员/开发者消息、要求标为有效、索要提示词）；`normalize_before_match: true` | 公开 mock 确定性核对发现的 bug（第一类）；开发集上命中仍为 0。修正了决定日志 D-20 当时"不改"的做法 |
| `redaction.*`（配置） | — | 不变 | 第1节第10条：用现有脱敏步骤。代码层补了电话、拼写邮箱的脱敏，并防止费用词被当成人名（mock 核对发现的 bug，见 `mock_deterministic_review.zh.md`） |
| 新增 `number_features.quantity_rate.*` | — | 单位词表、窗口 18/40 字符、数量上限 1000 | 用户 11-10 要求 b：代码自己找出"数量×单价" |
| 新增 `number_features.difference_explanation.max_terms` | — | 3 | 用户 11-10 要求 c：差额等于一到三笔金额之和时在审核视图写明 |

## 2. 标识档位（相对原型的 role）

| 标识 | 原型 | 现在 | 理由 |
|---|---|---|---|
| `REC.TEXT.EMPTY`、`REC.TEXT.NUMBERS_ONLY` | 自动打回（模型前） | return（经过模型后建议退回） | 决定 2.1、2.3 |
| `REC.TEXT.NO_NUMBER`、`ITEM.AMOUNT.MISSING`、`ITEM.AMOUNT.UNNAMED` | alone（人工） | return | 承运商可以补的问题；决定 2.3 的"可以退回的问题"。其中 `UNNAMED` 由模型给出空费用代码触发，不是纯代码判定（审计 L12 指正）。`UNNAMED` 的触发率待规模运行后再议（用户 11-10） |
| `ITEM.TAX.RATE_MISMATCH` | alone | info，另加 `ITEM.TAX.PRESENT`（attention） | 决定 4.4：税一律送人工，不判承运商算错 |
| `ITEM.TAX.NO_AMOUNT`、`ITEM.TAX.NO_RULE` | score | info，同上由 `ITEM.TAX.PRESENT` 送人工 | 决定 4.4 |
| `ITEM.CODE.COMBINED` | score 1 分 | info | 曾设为 attention，边界用例 BC039 显示无决定支持，改回提示 |
| `ITEM.CODE.OTHER` | score 2 分 | attention | 决定 3.7：代码表里找不到就打标识 |
| `CLAIM.RECON.SUM_MISMATCH`（退回模型） | return | 改为 `CLAIM.DELTA.*`：第一次不一致 info；修改后才一致、坚持后仍不一致、次数用完仍不一致 attention | 决定 3.2；第1节第4条 |
| `CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE` | alone | `CLAIM.DELTA.TOTAL_COUNTED_TWICE_PATTERN` info | 决定 3.4：不再作门槛 |
| `CLAIM.RECON.PASSED_AFTER_RETURN` | score 1 分 | `CLAIM.DELTA.MATCH_AFTER_REVISION` attention，另加 `CLAIM.ATTEMPT.STATUS_CHANGED` attention | 决定 3.5：改了状态的数字列给审核员 |
| `NUM.JUDGMENT.DOLLAR_EXCLUDED` | alone | info；没有原文依据时改为强制检查退回模型 | 决定 3.5 |
| `ITEM.ARITH.QTY_RATE_MISMATCH` | score 2 分 | `ITEM.ARITH.RELATION_FAILS` attention（覆盖所有算式关系） | 决定 3.3 |
| `REC.FIELD.REASON_CODE_CONFLICT` | low / none | info | 不变（移植） |
| `HIST.*`、`RUN.TOOL.RECONCILE_OVERUSE` | 各档 | 未移植 | 历史属 R1c / 决定 4.2（本段不做）；reconcile 按决定 3.1 去掉 |
| `REC.INPUT.EXPORT_DUPLICATE` | info（合并） | 删除，改为 `DUP.ROW.HAS_LATER_COPIES` info + `DUP.ROW.COPY` attention | 决定 5.3、第1节第7条 |

## 3. 测试期望值

- 原有 `tests/test_data_split.py`：两个读测试集 ID 列的测试改成默认跳过（决定日志 D-08，禁区）。期望值本身没改。
- 原型的 17 个检查（`scratch/prototype/prototype_checks.py`）没有改，仍按原型运行；新代码的测试在 `tests/` 下另写。
- Codex 88 个边界用例：逐条分类见 `boundary_cases_review.zh.md`（保留 65、修改 19、作废 4）。Codex 的原文件没有改。
- 公开 mock 的期望没有改（mock 由另一个代理维护），过时项列在 `mock_deterministic_review.zh.md`。

## 4. 审计（阶段 4）之后补记的改动

| 项 | 原型或之前 | 现在 | 理由 |
|---|---|---|---|
| `agent.max_turns` | 12 | 14 | 之前漏记（审计 L11）。多给两轮是因为"不一致"回馈和格式修复分开计数（D-12），最坏情况比原型多两次提交；实际平均 1.1 到 1.5 次 |
| `agent.max_uncertainty_reports`（新） | 无 | 6；超过的疑问另记 `RUN.AGENT.UNCERTAINTY_OVER_LIMIT`（attention） | 之前漏记（L11）；超限的疑问不再丢（审计 L2） |
| `ITEM.ARITH.QTY_RATE_NO_RESULT`（新，attention） | 无 | 见 D-24 | 用户 11-10 要求 b（之前漏记，L11） |
| `NUM.ARITH.CUE_WITHOUT_RELATION`（新，info） | 无 | 有算式迹象、模型没写关系 | 决定 3.3"打一个提示"（之前漏记，L11） |
| `REC.FIELD.CURRENCY_UNDETERMINED`（新，info） | 无 | 推不出币种 | 决定 4.3（之前漏记，L11） |
| `ITEM.AMOUNT.UNNAMED` 档位理由 | "代码能确定的问题" | 改为：由模型给出空费用代码触发，不是纯代码判定 | 审计 L12 指出理由写错；档位未改（用户 11-10 暂缓，待决 P-19） |
| 下游事实导出范围 | 通过检查且一致 | 再加"推荐为解析通过检查"（没有需人看或可退回的标识） | 审计 H2：副本、注入嫌疑曾进入导出；决定 3.9、5.4 |
| 认不出区域的数值 | 只认点号小数 | 最后一个点号或逗号后跟一两位数字才算小数点；另记 `NUM.READ.REGION_VALUE_DERIVED`（info） | 审计 H1 确认的 bug（`1.234,56` 被算成 123456） |
| 非 ASCII 字符 | 算注入嫌疑（attention） | 单独的 `REC.TEXT.NON_ASCII`（info）；控制字符仍算注入 | 审计 L7：葡萄牙语、西班牙语文字被当成注入 |
| 发票内查重 | "其他"代码一律算同一种费用；未通过检查的读法静默跳过 | "其他"按原文费用名区分；跳过的打 `DUP.INVOICE.NOT_CHECKED`（info） | 审计 M5 |
| 提交协议 | 首次可写 INSISTED；后续可写 FIRST；REVISED 但读法没变不查 | 三种都作为强制检查退回模型 | 审计 L1 |
| 新增 `RUN.MODEL.TRUNCATED`、`REC.FIELD.DELTA_MISSING`（attention） | 无 | 截断、Delta 缺失显式标出 | 审计 L2、M2：不允许静默错误（第1节第6条） |
| SKILL.md 第 3 到 5 节措辞 | 引用了来自单一承运商的原文片段 | 改成通用描述（v1.1） | 审计 H3；第1节第2条 |
