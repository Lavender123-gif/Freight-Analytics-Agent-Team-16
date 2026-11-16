# T16 先写后算：问题来源分类、系统性差异的定义和分组特征（2026-11-15）

本文件和 `scratch/eval/t16_features.yaml` 在看任何新的逐条结果之前提交。之后补的特征在报告里标“事后加”。没有调模型。

## 1. 问题来源（每处归一个主来源，可另记一个次来源）

| 代号 | 来源 | 含义 |
|---|---|---|
| input | 输入本身的问题 | 承运商文字有缺陷：空、只有数字、有金额没写费用名、写了税种没写税额、按标准确实说不清 |
| history | 历史关系 | 同一票货里的重复、取代、相同金额、BALANCE DUE |
| model_misread | 模型读错 | 文字按标准是清楚的，读法和标准不同 |
| model_bias | 模型读法偏差 | 同一类写法，模型一贯读成某一种，和标准不同 |
| rule_not_covered | 规则没覆盖 | 现有规则和阅读约定都没说怎么处理 |
| impl_not_triggered | 实现没触发 | 规则要求提醒，代码没有触发 |
| rule_ambiguous | 规则文字有歧义 | 规则文字有两种读法，实现选了一种 |
| gold_conflicts_rule | 标准答案和我们的规则冲突 | 人工标注或 mock 答案与我们写下的决定不一致 |
| annotator_missing_info | 标注一方缺信息 | 标注人当时没有某项信息（代码表、后来才定的规则） |
| redaction | 脱敏影响 | 遮挡改变了模型看到的文字 |
| security | 安全 | 注入 |
| other | 其他 | 写明是什么 |

**送人工的记录**：按它的送人工级别标识归来源，对照表在 `t16_features.yaml` 的 `flag_source`。一条记录有多个标识时，主来源按这个先后取第一个出现的：security、input、history、rule_not_covered、model_misread、redaction；其余记为次来源。`RUN.AGENT.UNCERTAINTY_REPORTED`（模型自报疑问）归 input。

## 2. mock 的“我们的标准”口径（口径 B）

只用 mock 标准答案和原文判断，不看系统输出。从 mock 的期望出发，下面几处改成按我们的决定判断：

| 情形 | mock 期望 | 口径 B | 依据 |
|---|---|---|---|
| 本次计入的费用名不在代码表里（`t16_features.yaml` 的 `not_in_taxonomy`） | 多数“解析通过” | 需要人看 | 决定 3.7：代码表外的费用记“其他”，送人工 |
| 本次计入的金额没写费用名（`no_charge_named`） | 不一定 | 需要人看 | `ITEM.AMOUNT.UNNAMED` 送人工 |
| 订单副本里订单号为空或相同（规范化后） | 打副本标识但“解析通过” | 需要人看 | 任务 14 第 1 节、T12 4.5：`SHIP.COPY.SAME_OR_NO_PK` 送人工 |
| 一个金额对应多项费用（`understanding_one_amount_two_fees`），没有别的理由 | 需要人看 | 不需要 | 边界用例 BC039：`ITEM.CODE.COMBINED` 是提示 |
| 其余 | 照 mock | 照 mock | |

两种口径下，系统读出的主张金额与 mock 答案不同都算需要人看（与任务 15 相同）。

**P-10**（“EARLIER CLAIM … FOR PRIOR ACCESSORIAL”这类写法）：口径 A 下按 mock（算本次主张）；另按“模型对”（这是历史，本次主张 0）再算一次 Recall。

## 3. 系统性差异

**定义**：同一类写法上，标准答案和系统一贯朝同一个方向不同。门槛：mock 上同一组至少 5 条，人工标注上至少 3 条。偶发的单条不同不算。

**比较的字段**：是不是金额；计入、不计入、贷记；费用大类；说明合计；需不需要人看。

**分组特征**（正则在 `t16_features.yaml`，在脱敏前的文字上匹配）：BALANCE DUE 写在最前面；BALANCE DUE 写在其他 `$` 金额之后；表示历史的词（EARLIER、PRIOR、PREVIOUS、PAID、BILLED、ALREADY、ORIGINAL）；税种词；`@`、PER、EACH；以点开头的小数；代码表里没有的费用名（mock 用上面的名单，人工标注用标注类别“其他”）；一个金额对应多项费用（“A AND B 金额”）；脱敏占位符（在脱敏后的文字上）；另加人工标注上“标注类别与代码表例子写法不同”一组。

**每组要写**：数据、条数、方向；发生在哪一步（模型读法、代码规则、票货汇总）；原因（第 1 节来源）；按标准哪边对，标准没说的写“需要用户定”；按对的一边纠正后对 Recall、FOR、Precision 的影响。mock 上的每组到开发集全量找同样写法做旁证。
