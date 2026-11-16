# T14 第一段测试报告：撤掉 Delta、副本合并、票货汇总、代码表换算（不调模型）

日期：2026-11-15。分支 `leg3-milestone`。证据级别：样本内（开发集留存读法，开发时看过的数据）。本段没有调用模型（花费 0，账本仍是 71.67 美元），没有读测试集、预留 mock 和 `ppg-mock-gen` 目录，没有改 SKILL.md 和标注原件。重放用的是开发集全量留存读法 `20261110-195411-devFull-4823`（2026-11-10，SKILL.md v1.1 加旧脱敏）。行级明细只在 git 忽略的 `data/interim/rollup/`。

## 结论

1. **撤掉运行时的 Delta**（T14-01）：`DeltaJudge`、回馈轮、9 个标识、回馈次数配置都删了，`src/` 里 `DeltaJudge` 出现 0 次；规则升到 `rules-v1.2-2026-11-15`。`uv run pytest -q`：184 通过，2 跳过。
2. **两项核对**（T14-07）：多出来的 5 条退回全部是空文本（4 条）或只有数字（1 条），没有第三种情况，不需要停。被撤的 9 个标识里，“读法与 Delta 不一致”这一类没有任何不依赖 Delta 的检查能替代；“文本里有 `$` 金额被排除在外”的信号仍在。
3. **票货汇总**（T14-03、T14-06）：813 票货每票都有默认总额。客户的两个例子精确复现（T14-04），没有触发任何汇总标识。
4. **代码表换算**（T14-05）：在留存读法上复现 T13 第 3.2 节的五类数字 250 / 63 / 620 / 66 / 3，金额也逐类相同。
5. **颜色**：逐行 760 / 188 / 5（撤前）→ 766 / 177 / 10（撤 Delta）→ 778 / 165 / 10（再按 C6 改税）；合并成说明后 807 / 91 / 10（908 条）；加上票货汇总后按票货 684 / 124 / 5（813 票）。顺序都是“解析通过 / 建议人工 / 建议退回”。

## 1. 各编号做了什么、怎么验

| 编号 | 做了什么 | 怎么验 | 结果 |
|---|---|---|---|
| T14-01 | 删 `DeltaJudge`、`INCONSISTENT_MESSAGE`、回馈分支、`explain_mismatch`；删 `CLAIM.DELTA.*` 六个、`REC.FIELD.DELTA_*` 三个、三条上位关系、`max_delta_feedback_rounds`、`difference_explanation`；输出去掉 `delta_consistency`、`first_check`；下游导出不再要求“与 Delta 一致”；审核界面去掉 Delta 对账一行和“首次不一致”标记；三列 Excel 金额改为选读、只存库 | `uv run pytest -q`；`grep -c DeltaJudge src/freight_lineitems/*.py` | 184 过 2 跳；0 处 |
| T14-02 | 按（SHIPMENT_GID、Event Date、规范化文字）合并成说明，模型只读组内行号最小的一行；说明带行号、PK 列表、订单数；只有 PK 相同或为空的副本打 `SHIP.COPY.SAME_OR_NO_PK`；数据库里副本行以 `ORDER_COPY` 链到同一条说明 | `uv run pytest tests/test_duplicates.py -q`（每个 PK 一行、PK 相同、PK 为空三种，加 Delta 不进键、Event Date 进键） | 6 过；开发集 953 行合成 908 条说明，5 条打标识（与 T12 摸底一致） |
| T14-03 | 新文件 `src/freight_lineitems/rollup.py`，T12 调整计划 4.3 的八条规则 | `uv run pytest tests/test_rollup.py -q`，合成用例每条规则至少一正一反；“最细一层比较”的正例是 PT、基础费率更正、重量更正、最低收费同在 Freight 下却各自相加 | 17 过 |
| T14-04 | `tests/test_jake_examples.py`：合成版两个（结构相同、金额编造）；真实版一个，读 git 忽略的开发集、留存运行和期望值文件，数据不在时跳过 | `uv run pytest tests/test_jake_examples.py -q -rs` | 3 过，0 跳过（本机数据在） |
| T14-05 | `config/charge_map.yaml`（由 `scratch/rollup/build_charge_map.py` 从 T13 对应表生成）和 `src/freight_lineitems/charge_map.py`：客户名称、全部 EDI 候选、内部代码三列，一对多的再给参考名称 | `uv run python scratch/rollup/coverage_check.py`；`tests/test_charge_map.py` | 五类 250 / 63 / 620 / 66 / 3，金额 26,148.92 / 8,237.49 / 30,082.81 / 4,014.20 / 42.00，与 T13 相同；5 过 |
| T14-06 | `scratch/rollup/replay.py --run devFull-4823`：旧的逐行运行先合并成说明、按 v1.2 重算颜色，再按票货汇总，写出客户格式的表 | 退出码 0，并打印“813 票货，每票都有默认总额” | 通过；表在 `data/interim/rollup/20261110-195411-devFull-4823/`（`jake_format.csv`、`.md`、`shipments.jsonl`、`summary.json`） |
| T14-08 | 币种固定 USD，删 `REC.FIELD.CURRENCY_UNDETERMINED` 和 `config.currency()`；`ITEM.TAX.PRESENT` 降为提示，`ITEM.TAX.NO_AMOUNT` 升为送人工；`rules.yaml → review_groups` 让内部不一致、措辞不清两组在同一档里排最前，并带 `review_group` 字段供报告单独统计 | `tests/test_tools_and_rules.py` 新增两条 | 通过 |
| T14-09 | 客户 11-13 的答复转述回填进 `docs/client/jake_questions.md` 第 5 节（英文在根目录 `QUESTIONS_FOR_JAKE.md`），每题写对应仓库哪一题、因此改了什么 | 逐题核对：9 题都有“答复”和“因此改了什么” | 9 / 9；仓库原有的 10 题里 Q3、Q7 没有被问到（待决 P-26） |

T14-01、T14-02、T14-08 改的是同一些行，合成一个提交（决定日志 D-70）。

## 2. T14-07 两项核对

脚本：`scripts/t07_delta_checks.py`（只读，只打印计数和记录键）。

### 2.1 被撤的 9 个标识

“还送人工”指这些行按规则 v1.2 重算后仍是建议人工或建议退回（逐行，副本未合并）。

| 标识 | 原来抓什么 | 开发集全量上的行数 | 撤掉后仍送人工的行 | 不依赖 Delta、还能抓到同类问题的检查 |
|---|---|---|---|---|
| `CLAIM.DELTA.FIRST_MISMATCH`（提示） | 第一次提交的计入金额之和与 Delta 不等 | 43 | 30 | 部分：模型自报疑问（25 行同时有）、有金额无费用名（10）、`CLAIM.RECON.TOTAL_MISMATCH`（3）、`ITEM.ARITH.RELATION_FAILS`（2）。**其余 13 行没有任何替代** |
| `CLAIM.DELTA.MATCH_AFTER_REVISION`（送人工） | 被告知不一致后改了读法 | 4 | 4 | 回馈轮已不存在，这类情形不会再发生；4 行都另有自报疑问 |
| `CLAIM.DELTA.MISMATCH_INSISTED`（送人工） | 坚持一个与 Delta 不等的读法 | 38 | 25 | 同第一行；**13 行没有替代** |
| `CLAIM.DELTA.MISMATCH_UNRESOLVED`（送人工） | 重试用完仍不等 | 1 | 1 | 有金额无费用名、自报疑问 |
| `CLAIM.DELTA.TOTAL_COUNTED_TWICE_PATTERN`（提示） | Delta 恰好等于各项加合计（Excel 把合计算了两次） | 13 | 4 | 不需要替代：客户确认这是 Excel 公式本身的算法。评估二的分歧归类里有“文本里的合计被基线重复计入”一类 |
| `CLAIM.DELTA.DIFFERENCE_MATCHES_AMOUNTS`（提示） | 差额恰好等于原文里某几个金额 | 32 | 19 | 部分：`NUM.JUDGMENT.DOLLAR_EXCLUDED`（带 `$` 不计入时显示排除短语）。“差额等于哪几个金额”这句解释没有了 |
| `REC.FIELD.DELTA_ZERO`（送人工） | Delta 为 0，没有可比的值 | 13 | 7 | 不需要替代：Delta 不再是比较依据。13 行里 4 行空文本、1 行只有数字（现在建议退回，见 2.2），其余 2 行另有标识 |
| `REC.FIELD.DELTA_MISSING`（送人工） | Delta 缺失 | 0 | 0 | 不需要替代 |
| `REC.FIELD.DELTA_NEGATIVE`（送人工） | Delta 为负 | 1 | 1 | 贷记由模型标为负数行；这 1 行另有有金额无费用名 |

**仍然存在、不依赖 Delta 的数字信号**：`NUM.JUDGMENT.DOLLAR_EXCLUDED`（带 `$` 的金额没有计入时，显示原文排除短语，提示；开发集全量 50 行）、`NUM.JUDGMENT.EXCLUSION_BASIS_UNLISTED`（排除短语不在依据词表里，送人工；0 行）、`CLAIM.RECON.TOTAL_MISMATCH`（各项之和与原文写的合计不等，送人工；10 行）。“文本里有 `$` 金额被排除在外”这一信号仍在。

**没有替代的那一类**：只有一个金额、或几个金额都被读成计入，但读错了（例如把一个历史金额当成本次主张），而模型又没有自报疑问。以前它会和 Delta 对不上；现在没有任何代码检查能发现。开发集全量上，“与 Delta 不一致、撤掉后变成解析通过”的有 13 行（`FIRST_MISMATCH` 43 行减去仍送人工的 30 行）。这一类只能靠评估一（系统对人工标注）量出来。按任务书，这里只报告，不新增检查。

### 2.2 退回从 5 条变成 10 条

规则：退回只能由代码在“空文本、只有数字”时给出。多出来的 5 条全部符合：

| 记录键 | 触发的退回标识 | 原来为什么不是退回 | 撤 Delta 后为什么变成退回 |
|---|---|---|---|
| `dev#r152` | `REC.TEXT.EMPTY` | `REC.FIELD.DELTA_ZERO`（送人工）盖住了退回 | 盖住它的 Delta 标识没了，剩下的只有代码判定的空文本 |
| `dev#r191` | `REC.TEXT.EMPTY` | 同上 | 同上 |
| `dev#r223` | `REC.TEXT.NUMBERS_ONLY` | 同上 | 同上（文本只有数字） |
| `dev#r608` | `REC.TEXT.EMPTY` | 同上 | 同上 |
| `dev#r609` | `REC.TEXT.EMPTY` | 同上 | 同上 |

脚本输出 `all_extra_are_empty_or_numbers_only: true`。没有第三种情况，不触发任务书第 6 节的停止条件。合并成说明之后，这 10 条退回仍是 10 条说明；按票货是 5 票：另外 5 条各在一票两条说明的票货里，这 5 票都有送人工的票货层面标识，颜色取较重的“建议人工”。

## 3. 重放结果（留存读法，规则 v1.2）

### 3.1 规模

| 项 | 数 |
|---|---|
| 行 / 说明 / 票货 | 953 / 908 / 813 |
| 多说明的票货 | 91 |
| 有默认总额的票货 | 813（全部） |
| 不完整的票货（有说明没有可用读法） | 1 |

### 3.2 颜色（解析通过 / 建议人工 / 建议退回）

| 阶段 | 单位 | 分布 |
|---|---|---|
| 撤 Delta 前（规则 v1.1，留存结果） | 行 953 | 760 / 188 / 5 |
| 撤 Delta 后（C1） | 行 953 | 766 / 177 / 10 |
| 再按 C6 改税（C1 + C6，副本标识仍按 v1.1） | 行 953 | 778 / 165 / 10 |
| 规则 v1.2、副本合并成说明 | 说明 908 | 807 / 91 / 10 |
| 加上票货汇总后（票货颜色 = 说明和票货标识里最重的） | 票货 813 | 684 / 124 / 5 |

前三行与 T12 摸底 4.5 节的数字相同。

### 3.3 汇总标识的触发数（票货层面，一票可触发多种）

| 标识 | 次数 |
|---|---|
| `SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE` | 44 |
| `SHIP.ROLLUP.RATIO_SUPERSEDED` | 32 |
| `SHIP.ROLLUP.RELATION_UNDECIDED` | 18 |
| `SHIP.ROLLUP.BALANCE_DUE_READING_DIFFERS` | 15 |
| `SHIP.ROLLUP.BALANCE_DUE_UNRESOLVED` | 14 |
| `SHIP.ROLLUP.SAME_AMOUNT_EARLIER` | 11 |
| `SHIP.ROLLUP.ORDER_TIED` | 2 |
| `SHIP.ROLLUP.INCOMPLETE` | 1 |
| `SHIP.ROLLUP.TAX_PARTLY_ORPHANED` | 0 |
| `SHIP.COPY.SAME_OR_NO_PK`（说明层面） | 5 |

91 票多说明货里 56 票出现取代（同一费用取代或 1.03 到 1.07 倍取代），与 T12 摸底“57 票会触发”量级相同（T12 的口径把多代码和无费用名的金额也当作同一费用比较）。

### 3.4 与两种 Excel 基线相等的票货数（只作参考，评估二在第三段做）

| 基线 | 全部 813 票 | 单说明 722 票 | 多说明 91 票 |
|---|---|---|---|
| Delta 按不同说明相加 | 722 | 694 | 28 |
| Invoice Dups Removed 减 Shipment Amount | 721 | 694 | 27 |

1 票货的 Invoice Dups Removed 全为 0，没有第二种基线。

## 4. 局限

- 重放用的是调优之前的留存读法（SKILL.md v1.1、旧脱敏），合并副本时取行号最小那一行的读法；最终数字要等第三段用选定版本重跑。
- 两个客户例子都在开发集，开发时见过；复现它们只是回归测试。
- 汇总规则只由合成用例和这两个例子检验过；“读得对不对”和“取代判得对不对”都还没有人工评估。全部说明都被标注的多说明票货只有 8 票。
- 撤掉 Delta 之后，单个金额读错而模型不自报疑问的情形没有代码检查（2.1）。
- 第 2 条规则以内部代码判断“同一费用”，依赖模型给的代码；代码给错时取代也会错。
