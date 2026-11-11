# 独立审计报告：分支 `autorun-leg1`（任务 09 阶段 4）

审计日期：2026-11-10。审计者没有参与开发，只读仓库、留存的运行数据和日志。
范围：`git diff main...autorun-leg1`（19 个提交）、`src/freight_lineitems/`、`config/`、`skill/`、`tests/`、`docs/autorun/`、`data/interim/runs/` 下全部 17 个运行（2478 条记录）。
没有调用模型或网络，没有读测试集、原始 Excel、预留 mock。除本报告外没有改动任何文件。

## 一屏汇总

| 严重度 | 个数 | 一句话 |
|---|---|---|
| 高 | 3 | H1 欧式小数的认不出区域被代码算成 100 倍金额，模型被错误告知"不一致"；H2 下游事实导出收了副本、注入嫌疑和送人工的记录，且不带任何标识；H3 SKILL.md 里有大量只出自单一承运商（甚至单一记录）的措辞 |
| 中 | 6 | M1 运行中异常会丢掉已发生的全部尝试；M2 模型跑完后的崩溃会丢掉整批输出和账本记录；M3 "带 $ 不计入"的原文依据只核对"在原文里"，任意一个词都能通过；M4 样本 A、B 不独立（5 条完全副本）；M5 发票内查重把不同的 OTHER/PENDING 费用当成同一种；M6 并行批次的预算检查有竞态 |
| 低 | 12 | 协议漏洞、未标识的截断、文档与代码不符、未入记录的阈值改动、pytest 写到项目外等，见第 9 节 |

清单七项结论：

| 项 | 结论 |
|---|---|
| 1 Delta 是否进入模型输入 | **未发现问题**（留存内容逐条核对，2478 条；有两处可审计性缺口，见 L4） |
| 2 每条记录都到了模型 | **未发现问题**（数据层面全部到达）；代码里有把"模型已跑"误记成"没跑"的路径，见 M1 |
| 3 静默失败 | **发现问题**：M1、M2、M5、L2、L8 |
| 4 首次尝试留存、不被覆盖 | 数据**未发现问题**；代码**发现问题**：M1 |
| 5 期望值和阈值改动理由 | **发现问题**：M3（BC029 的转换方式、DOLLAR_EXCLUDED 降档）、L11（未入记录的改动）、L12 |
| 6 承运商或记录的硬编码 | **发现问题**：H3、L9（代码里没有 `if carrier ==`、没有记录编号） |
| 7 禁区 | 未发现越界读写测试集、原始 Excel、预留 mock、push、sudo、密钥；**有轻微问题**：L5、L6 |

`uv run pytest -q`：**58 passed, 2 skipped**（3.63 秒；跳过的两条是读测试集 ID 列的 `tests/test_data_split.py`，按 D-08 默认跳过）。

---

## 1. Delta 是否以任何形式进入模型输入 —— 未发现问题

**方法**（对 `data/interim/runs/*/records.jsonl` 全部 17 个运行、2478 条记录）：

1. `process.transcript.first_user_message`：去掉固定前后缀后解析 JSON，确认键只有 `schema_version, redacted_text, marked_text, numbers, unrecognized, origin_province, destination_province`（2478/2478）；`redacted_text` 与 `facts.text_redacted` 逐字相同；`numbers[*].raw` 都出现在原文中、`value` 与 `facts.number_table` 相同；起讫省与源字段相同。没有任何一条不符。
2. 把 Delta、Invoice Amount、Shipment Amount 各自的多种写法（两位小数、去尾零、整数部分、千分位逗号，取绝对值，兼顾负号）在 `first_user_message`、所有 `tool_results`、nudge 文本里搜索：
   - Delta 在首条消息里命中 15 164 次，其中 15 036 次同样出现在原文中（承运商自己写了这个数）；其余 128 次全部是数字表的 `value` 字段（原文 `$ 8 400.00` 规范化成 `8400.00` 之类），即原文数字的规范化写法，属巧合，不是泄漏。
   - Shipment Amount 命中 16 次不在原文中，同样全是 `value` 字段的规范化写法（如原文 `$1 277.68`）。
   - 工具结果里 Delta 命中 17 次（41 次 `calculate` 结果恰好等于 Delta）：全部是模型自己用原文数字做的算式（如 `325.84 + 75.07 + 52.12`、`3 * 18.50`），不是系统返回的信息。
3. 提交工具的返回只有四种形态：`{accepted}` 2478 次、`{accepted, result:'inconsistent', message, resubmissions_left}` 353 次、`{accepted, result:'checks_failed', errors, resubmissions_left}` 5 次、终止消息 0 次。`inconsistent` 的 `message` 恒为 `agent.py:32-37` 的固定文字，不含差额、方向或金额。检查错误的 `evidence` 只来自原文和提交（`checks.py` 的 `Ctx` 不含 Delta，`checks.py:34-42`）。
4. 系统提示：用当前代码 `pipeline.system_prompt()` 重建，以及 `tools.TOOLS` 序列化后搜索 `delta / invoice amount / shipment amount / too high / too low`：只出现"You are not given the invoice amounts"和"adjustment on record, which you do not see"这类说明，没有值或字段名。SKILL.md 在本分支的 6 个版本（`git log -p`）的新增行里也没有这些词。各运行用的 SKILL.md 哈希（`versions.skill_sha`）与 git 中的版本对应。
5. 留存的 `explain_mismatch` 结果（`CLAIM.DELTA.DIFFERENCE_MATCHES_AMOUNTS`，含差额和方向）只在会话结束后计算，`agent.py:192-193` 在 `outcome_diagnostics` 里调用，transcript 里没有出现。

**仍要说明的两点（不是泄漏，是可审计性）**：见 L4（系统提示没有逐条留存、例子库不在版本号里；样本 B 里 1 条记录与系统提示里的一个例子文字完全相同）。另外"接受/不一致"本身向模型透露 1 比特信息，这是决定 3.2 的设计，不算缺陷。

## 2. 每条开发集样本是否都到了模型 —— 未发现问题（代码有一处误记，见 M1）

- 样本表 A、B 各 100 条、R50 50 条（`wc -l` 显示 99 是因为文件末尾没有换行）。`baseA/t1A/t2A/t3A` 的记录集合与 A 完全相同，B、R50、公开 mock（375 行）同理：缺 0、多 0、无重复。
- 全部 2478 条 `process.model_ran = true`，`n_model_calls ≥ 1`，`attempts ≥ 1`；`parse_status` 全为 `PASSED_CHECKS`；没有 `RUN.*` 事件，没有 nudge。
- 第一批 26 条（`20261110-171337-stage1-1cc1`）和 dryrun 2 条没有留存样本编号表，只能确认文件里的每条都跑了模型，无法确认"抽了的都写出来了"。
- 代码路径：`pipeline.prepare`（`pipeline.py:49-86`）没有任何返回分支，空文本、只有数字、Delta 为 0 都只加诊断（`tests/test_agent.py:128` 覆盖空文本）。`run_batch` 对每条都调用 `run_model`。唯一的"没跑模型"出口是异常（`pipeline.py:179-180`），它会把**已经跑过模型**的记录也写成 `model_ran=false`、`RUN.SUBMIT.NONE {"reason": "model not run"}`，见 M1。
- 5 条例子记录及其票货按 D-11/D-32 不进任何评估样本；这是评估设计，不是生产路径上的分流。

## 3. 静默失败 —— 发现问题

已核对、无问题的：模型 API 错误（`RUN.MODEL.ERROR`，`agent.py:223-226`）、拒答（`agent.py:231-234`）、达到 `max_turns`（`agent.py:253-254`）、从未提交（`RUN.SUBMIT.NONE`）、强制检查用完（`RUN.SUBMIT.FAILED_CHECKS`）、未配置的诊断码（`disposition.py:27-31` 变成 attention 并标 `unconfigured`；数据中 0 次）、空读法（有数字时 `NUM.REF.MISSING_ID`；无数字时会与 Delta 不一致）。按当前 `rules.yaml` 重新计算全部记录的推荐，与留存一致；`MISMATCH_*` 与 `NO_ANCHOR` 的记录没有一条落在"解析通过检查"。

发现的问题：M1、M2、M5（失败读法不参与查重且不标）、L2（`max_tokens` 截断无专门标识、超额的疑问报告被丢弃）、L8（`INSERT OR IGNORE`）。

## 4. 首次尝试留存、重试不覆盖 —— 数据无问题，代码有问题（M1）

数据：2478 条记录逐条核对，`attempts[*].attempt_no` 连续从 1 开始；尝试数等于 transcript 里 `submit_line_items` 调用数；每次尝试的 `raw_submission` 与对应 `tool_use.input` 完全相同；第 1 次尝试的 `response_type` 都是 `FIRST`；`facts.first_check` 等于第一个有效尝试的判定。序列分布：一次一致 2035、不一致后坚持 342、无锚点 89、修改后一致 3、修改后仍不一致 4、其他 5。
代码：`Session.submit` 先 append 再处理（`agent.py:93-97`），之后只改当前尝试的字段，不改旧尝试。
一处命名问题（低）：第 1 次尝试没通过强制检查、第 2 次一致的记录（1 条）被记为 `MATCH_FIRST`（"第一个有效尝试"），与"首次"字面不符，汇总"首次不一致率"时要注意口径。

## 5. 期望值和阈值改动 —— 发现问题

逐条对照 `config/rules.yaml` 与 `scratch/prototype/rules.yaml`、`expectation_changes.zh.md`、`boundary_cases_review.zh.md`：

| 改动 | 理由是否成立 |
|---|---|
| 删除 `auto_reject`，空文本、只有数字改为 `return` | 成立（决定 2.1、第1节第3条） |
| 计分阈值改为三档 | 成立（第1节第5条、D-13）；颜色变化已列为待决 P-14 |
| 税相关全部 info + `ITEM.TAX.PRESENT` attention（BC045/046/047/057） | 成立（决定 4.4） |
| `ITEM.CODE.OTHER` attention（BC037/082） | 成立（决定 3.7） |
| `CLAIM.RECON.*` 改为 `CLAIM.DELTA.*`（BC003/054/055/056/058） | 成立（决定 3.2、3.4、3.5） |
| reconcile 相关作废（BC075-077/088） | 成立（决定 3.1） |
| BC034 作废 | 成立（决定 3.8） |
| BC052 `OPERANDS_NOT_LINKED` attention → `CUE_WITHOUT_RELATION` info | 成立（决定 3.3 用的是"提示"） |
| BC087 币种 | 成立（决定 4.3） |
| BC072/073 改名 | 成立 |
| `relation_abs` 0.011 → 0.005、`ITEM.CODE.COMBINED` attention → info（BC051、BC039） | 成立，且是向原型回退，方向正确 |
| **`NUM.JUDGMENT.DOLLAR_EXCLUDED` alone → info，BC029 改期望** | **理由偏弱**，见 M3：边界用例转换器拿模型自己的 `evidence_phrase` 充当 `exclusion_phrase`（`boundary_cases_review.zh.md` BC029 行），等于由测试工具替用例补上了"原文依据"，用例因此通过；而强制检查本身只验证短语在原文中，不验证它是否表达"不计入" |
| **`ITEM.AMOUNT.UNNAMED` score → return** | **理由与事实不符**，见 L12：理由写"代码能确定的问题"，但触发条件是模型没给费用代码 |
| **`agent.max_turns` 12 → 14、新增 `max_uncertainty_reports: 6`、新增 `ITEM.ARITH.QTY_RATE_NO_RESULT`（attention）、`NUM.ARITH.CUE_WITHOUT_RELATION`、`REC.FIELD.CURRENCY_UNDETERMINED`** | **没有写进 `expectation_changes.zh.md`**，见 L11（部分在决定日志 D-24、D-29 里有） |
| 注入模式新增 5 条 + 规范化匹配 | 有记录（公开 mock 第一类 bug），但副作用见 L7 |
| 措辞调优三轮 | 门槛在 `9ce690a`（17:50:43）提交，早于第 1 轮运行（17:50:44），三轮都按门槛回退，SKILL.md 回到基线（哈希 `bd93bccc9eb8` 与调优前相同）。成立。但 B 不是独立样本，见 M4 |
| `tests/test_data_split.py` 两条改为默认跳过 | 成立（禁区）；期望值本身没改 |

`tests/` 下其余文件都是新增，没有修改已有断言。

## 6. 承运商或记录的硬编码 —— 发现问题

- 代码：用开发集和 mock 的 23 个承运商代码、全部 shipment/发票/PK 值，在所有被跟踪的 `.py/.yaml/.md/.json/.toml/.txt/.html` 文件里搜索：0 命中。没有 `if carrier ==`。记录编号只出现在测试夹具里（`tests/helpers.py`、`tests/test_db.py`、`tests/test_duplicates.py` 的 `dev#r1..r3`，是合成记录的编号）。
- 措辞：**SKILL.md 有问题**，见 H3；taxonomy 别名进入代码行为，见 L9。

## 7. 禁区 —— 未发现越界；有两处轻微问题

- push：本地没有 `origin/autorun-leg1` 远端跟踪引用，`branch.autorun-leg1.remote` 未设（`git branch -r` 只有 `origin/main`、`team/freight-lineitems`）。未见 push 痕迹。
- 密钥：`git ls-files` 中没有 `.env`；全部提交里搜 `sk-ant` 和 `ANTHROPIC_API_KEY=<值>`：0 命中。`llm_client.py` 只从环境或 `.env` 读取，不打印。
- 测试集、原始 Excel：`src/`、`scratch/autorun/`、`tests/` 中只有 `data_split.py`（主分支已有的切分脚本）和 `tests/test_data_split.py` 引用测试集路径；后者默认跳过。D-08 记载阶段 0 按任务书"跑现有测试"跑过一次读测试集 ID 列的测试，与第 2 节"不读不碰测试集"有冲突，已在决定日志说明（见 L5）。
- 预留 mock：`.claude/settings.json` 对整个 mock 项目文件夹设了 Read/Edit/Write/Bash deny。D-02 说明在加 deny 之前，按 mock 项目索引里的路径把 4 个公开 mock 文件复制到了 `data/external/`；公开 mock 允许使用，没有证据显示读了预留 mock，但这一步确实进入过 mock 项目文件夹（读索引），建议在验收包里明说。
- sudo、`/tmp`：代码和脚本里没有 sudo、`/tmp`、`expanduser`、`Desktop`。但 pytest 的 `tmp_path` 会写到系统临时目录，见 L5。deny 规则本身的覆盖面见 L6。

---

## 8. 高、中严重度问题

### H1（高）认不出区域的数值由代码按"点号是小数点"推算，欧式写法被算成 100 倍，模型被错误告知"不一致"

- **是什么**：`checks.py:192-195` 只认最后一个 `.` 之后的数字为小数部分：`dec = re.search(r"\d\.(\d+)\D*$", raw)`。`1.234,56` 匹配不到（`.234` 后面还有数字），于是取全部数字 `123456`；`987,40` → `98740`。模型只能写 `digits_read`，没有办法表达小数位置。
- **证据**：公开 mock 4 次运行 × 5 条（`mock#ROW-00296` 至 `mock#ROW-00300`，原文如 `EU FORMAT 1.234,56 INSIDE PLACEMENT.`）共 20 条记录，`facts.claim.signed_sum` 为 `123456 / 98740 / 250075 / 61009 / 300125`，Delta 为 `1234.56 / 987.40 / …`。模型每次都读对（`reason` 里写明 "1234.56 in EU format"），却都被回了 `inconsistent`，最终 `MISMATCH_MODEL_INSISTED` 或 `MISMATCH_RETRIES_EXHAUSTED`。审核视图里显示的主张合计是错 100 倍的数。用 `tests/helpers.ctx` 复现：同一文本得到 `claim.signed_sum = 123456`，无任何错误。`mock_deterministic_review.zh.md:51` 把这类写成"被切成 `1.234` 和 `56`"，与实际行为（变成一个认不出区域、再被代码推算成 123456）不符。
- **影响**：错误的"不一致"信号会诱导模型改动正确读法（决定 3.2 的风险正在这里）；审核员看到错误金额；`CLAIM.DELTA.DIFFERENCE_MATCHES_AMOUNTS` 也会基于错误金额解释。开发集目前没有欧式写法，但任何带逗号的认不出区域都会走这条路径。
- **建议修法**：认不出区域的数值不要由代码猜；要么让模型在 `as_number` 里给出小数位数并由代码核对数字串，要么无法确定小数位时不计入合计、打显式标识（如 `NUM.READ.DECIMAL_UNDETERMINED`，attention）并不给模型回"不一致"。补单元测试，并更正 mock 核对文档。

### H2（高）下游事实导出收了副本、注入嫌疑和送人工的记录，且导出里没有任何标识

- **是什么**：`db.export_facts`（`db.py:215-229`）只按 `status = PASSED_CHECKS` 且 `delta_consistency ∈ {MATCH_FIRST, MATCH_AFTER_REVISION}` 筛选，不看推荐和标识；导出的每条只带 line items，没有 flags、推荐、copy_rank。
- **证据**（各运行 `export_facts.json` 与 `records.jsonl` 对照）：`20261110-174120-baseA-e448` 导出 78 条，其中 `DUP.ROW.COPY` 9 条、`RUN.AGENT.UNCERTAINTY_REPORTED` 11 条、`ITEM.TAX.PRESENT` 6 条、推荐为"建议人工审核"27 条、"建议退回"7 条；`20261110-174120-baseMock-176c` 导出 312 条，其中 `DUP.ROW.COPY` 10、`REC.TEXT.INJECTION_SUSPECT` 19、`ITEM.CODE.OTHER` 89、`DUP.INVOICE.SAME_CHARGE` 9、`REC.FIELD.DELTA_NEGATIVE` 10。其余运行同样。
- **影响**：决定 5.4 写明"下游汇总在审核员清理之后计算"，决定 3.9 写"下游只能读通过的"。现在下游拿到的是未经审核清理的数据，同一笔费用的副本会被重复计数，注入嫌疑的读法也直接流向下游，且下游无从区分。这比待决 P-02/P-07 讨论的范围更大。
- **建议修法**：事实导出至少排除 `DUP.ROW.COPY`，或给每条带上 `copy_rank`、`recommendation`、`flags` 和"未经审核"状态；更稳妥的是在有审核决定之前不出下游汇总，只出"候选"并明确标注。补测试（`tests/test_db.py:37` 现在只测了不一致和无锚点被排除）。

### H3（高）SKILL.md 有大量只出自单一承运商、甚至单一记录的措辞（违反第1节第2条）

- **是什么**：任务书第1节第2条"不写任何针对特定承运商的规则、措辞或例子"；`CLAUDE.md`"Carrier phrasing lives in example data, not in code"。SKILL.md 第 3、4、5 节直接引用了开发集原文短语。
- **证据**：在开发集里统计 SKILL.md 中出现的短语（只计数，不列承运商名）：

  | SKILL.md 中的短语（位置） | 开发集记录数 | 承运商数 |
  |---|---|---|
  | `TL FSC SHOULD APPLY`、`FACTOR PER CONTRACT`、`RATED AS`、`BOL WEIGHT`（第 5 节 "Rate or contract arguments"，四个例子全部） | 7 / 8 / 8 / 1 | 各 1 |
  | `FROM PPG NOTIFIED`、`AS PER LIST FROM PPG`、`AS PER BOL`、`APPROVED BY`（第 5 节 "Authority"，四个例子全部） | 48 / 32 / 7 / 1 | 各 1 |
  | `ADJUSTED OFF`、`STILL OWE`（第 3、5 节） | 1 / 2 | 各 1 |
  | `A DAY`、`EACH`、`DAYS AT`、`+ HST`（第 3、5 节） | 6 / 6 / 5 / 5 | 各 1 |
  | `CV19`（第 2、3 节的示例） | **1 条记录** | 1 |
  | "Purchase(d) transportation in any spelling is `PENDING.PURCHASED_TRANSPORTATION`"（第 4 节，一条专门规则） | 182 | 1 |

  `BALANCE DUE`（7 个承运商）、`SHORT PAID`（3 个）是跨承运商的，不算。这些措辞多数从 `scratch/prototype/skill/SKILL.md` 移植而来，但本分支重写了 SKILL.md（`b38d1fe`），第1节第2条是冻结决定。
- **影响**：模型对这些承运商的写法有"提示"，对其他承运商没有；在 A/B（按承运商分层）和 mock 上的数字因此可能偏向少数承运商；把单一记录的 `CV19` 写进提示，有对那条记录的过拟合。
- **建议修法**：第 5 节的阅读约定改成通用描述（"承运商引用了合同、费率表或计重依据"），具体短语只放在 git 忽略的例子库里；`PENDING.PURCHASED_TRANSPORTATION` 的识别交给代码表别名（决定 3.6 允许），从 SKILL.md 正文删去；把 `CV19` 换成合成写法。改后按调优规则在 B 和 mock 上验证。

### M1（中）会话中途抛异常时，已发生的尝试和 transcript 全部丢失，且记录被写成"模型没跑"

- **是什么**：`pipeline.py:176-180` 的 `one()` 捕获任何异常后调用 `assemble(prep, None, [RUN.MODEL.ERROR])`。`Session` 对象（含已留存的尝试）和 transcript 都被丢掉；`assemble` 还会加 `RUN.SUBMIT.NONE {"reason": "model not run"}`（`pipeline.py:131-132`），`process.model_ran = false`。
- **触发**：`dispatch` 内任何未预期异常（如 `check_submission` 的 bug、工具实现的异常）、`judge` 遇到 `delta=None` 的 `TypeError`、`explain_mismatch` 的异常等都会走这里。只有 `anthropic.APIError` 在循环里被单独处理（`agent.py:223`）。
- **证据**：代码阅读。现有数据里没有发生（全部 2478 条 `model_ran=true`）。
- **影响**：违反"第一次尝试必须留存"（第1节第4条）；已花的 token 记进了账本但对应的读法没了；"模型没跑"与事实不符。
- **建议修法**：在 `run_model` 里先建好 `Session` 和 transcript 容器，异常时把它们连同异常一起交给 `assemble`；`model_ran` 改为"是否发出过请求"；异常原因写成单独的 `RUN.PIPELINE.EXCEPTION`。补一条注入异常的测试。

### M2（中）模型跑完之后的步骤崩溃会丢掉整批输出和账本记录；有一个已确认的崩溃条件

- **是什么**：`run_batch` 在所有模型调用完成后才依次做 `duplicates.apply`、写 `records.jsonl`、写 SQLite、最后 `budget.append_entry`（`pipeline.py:186-198`），这一段没有异常保护。
- **已确认的崩溃**：`duplicates.invoice_level` 按 `(r.event_date or 0, r.row_number)` 排序（`duplicates.py:79`），同一发票里一条有日期、一条日期为空时 `TypeError: '<' not supported between instances of 'int' and 'datetime.datetime'`（用 `tests/helpers.record` 构造两条记录复现，模型没跑时也会崩）。另外 `prepare` 对 `delta=None` 也会 `TypeError`（`pipeline.py:63-66`；`records._dec` 对空单元格返回 `None`）。当前开发集 Event Date 和 Delta 都没有空值（953 条中 0），所以没发生过。
- **影响**：花了钱、模型读完了，记录和账本都没写；下一次预算检查少算这笔钱（第 5 节"每次运行后记账"）。
- **建议修法**：模型调用结束后立即先写 `records.jsonl` 和账本，再做查重和入库；排序键对空日期给明确的哨兵值；`Delta` 缺失时加诊断（如 `REC.FIELD.DELTA_MISSING`，attention）而不是崩溃。补测试。

### M3（中）"带 $ 却不计入必须有原文依据"只核对短语在原文里，任何词都能通过；同时该标识降成了 info

- **是什么**：`checks.py:239-246` 只调用 `phrase_found(j.exclusion_phrase, ctx.text)`。用 `tests/helpers.ctx` 复现：原文 `DETENTION $50.00 AND LUMPER $40.00`，把 `$40.00` 标 `BILLED`、`exclusion_phrase = "AND"`，没有任何错误，只得到 info 级的 `NUM.JUDGMENT.DOLLAR_EXCLUDED`。原型里这个标识是 `alone`（必送人工），现在是 `info`。
- **数据**：全部运行共 319 次 `DOLLAR_EXCLUDED`，其中 212 次的短语里没有任何表示"已付、已开票、单价、贷记、合计"的词。例：`dev#r234`（`20261110-174120-baseA-e448`）三笔 `$` 金额的排除依据都写成 `BALANCE DUE`，字面意思恰好相反；mock 里有 `HR X`、`/MI`、`ESTIMATE BETWEEN`、`CHANGE THE AMOUNT TO` 等。
- **为什么算期望值问题**：BC029 的新期望能"一致"，是因为边界用例转换器用模型自己的 `evidence_phrase` 充当了 `exclusion_phrase`（`boundary_cases_review.zh.md` BC029 行），由测试工具替用例补了依据。
- **影响**：决定 3.5 的防凑数在"第一次就一致"的情况下没有人工关口：模型把某个 `$` 金额排除、引一个任意词，凑成一致后得到"解析通过检查"。前后尝试比较（`CLAIM.ATTEMPT.STATUS_CHANGED`）只覆盖第二次才改的情况。
- **建议修法**：在 `rules.yaml` 里列出可接受的排除依据类别（已付、已开票、单价/每、贷记、历史等）并由代码核对短语是否命中，命中不了的改为强制检查错误或 attention；或者把 `DOLLAR_EXCLUDED` 在短语不命中这些类别时升为 attention。BC029 应该用原用例自带的数据重跑，不由转换器补字段。

### M4（中）样本 A、B 不独立：B 里有 A 的完全副本

- **证据**（用 `duplicates.content_key` 和源字段比较，不读测试集）：B 的 100 条中，5 条与 A 中某条除 PK/行号外完全相同；15 条与 A 共用同一票货和同一张承运商发票；22 条文字与 A 中某条完全相同。例：`dev#r109`、`dev#r111`（A）与 `dev#r110`（B）文字相同；`dev#r43`（A）与 `dev#r42`（B）；`dev#r119`（A）与 `dev#r120`（B）。A 内部也有 11 组副本（22 条）。D-32 写的是"互不重叠"，只在记录编号层面成立。
- **影响**：措辞调优"只看 A、在 B 上验证"的独立性打了折扣；以后若用 B 的结果支持状态板深绿（需要"独立样本"），证据不成立。
- **建议修法**：按票货（或发票）分组抽样，保证 A、B 不共用票货；在验收包里如实写明这次的重叠程度。

### M5（中）发票内查重把不同的 OTHER / PENDING 费用当成同一种；未通过检查的读法不参与查重且不留痕

- **是什么**：`duplicates.invoice_level` 以 `charge_code` 为键（`duplicates.py:80-90`），`OTHER` 和 `PENDING.*` 是兜底代码，不同费用会共享同一个键。`_items` 只取 `PASSED_CHECKS` 的读法（`duplicates.py:56-57`），其他记录直接跳过，没有"查重未执行"的标识。
- **证据**：全部运行共 46 次 `DUP.INVOICE.SAME_CHARGE`，12 次是 OTHER/PENDING。`20261110-174120-baseMock-176c` 里 `mock#ROW-00240`（`YARD ESCORT`）被标成指向 `mock#ROW-00325`（`PRIOR ACCESSORIAL`）的重复，`mock#ROW-00249` 同理指向 `mock#ROW-00334`：两笔不是同一种费用。
- **影响**：误报会送人工（attention），违背"标识不要太多"（决定 1.6）；失败读法不参与查重时，后一份通过的副本会被当成"第一次出现"而不标，这也是静默缺口。
- **建议修法**：OTHER 用规范化后的 `other_phrase`、PENDING 用原文费用名一起做键；没有通过检查的记录要么用最后一次读法参与，要么加 `DUP.INVOICE.NOT_CHECKED`（info）。补测试。

### M6（中）并行批次的预算检查有竞态

- **证据**：`docs/autorun/budget_ledger.jsonl` 里 `20261110-180249-t3A-43b7` 和 `20261110-180249-t3Mock-fbce` 同时启动（23:02:49 UTC），两条的 note 都是 "spent $19.5596 + estimate …"：两个批次各自读账本，互相看不见对方的预估。`budget.check_estimate` 只读已写入的账，`append_entry` 在批次结束后才写（`pipeline.py:164, 197`）。
- **影响**：本次总花费约 22 美元，没有超 50 美元上限；但离上限近时并行启动可以联手超支。
- **建议修法**：开跑前先在账本里写一条"预留"（预估金额），结束后用实际值替换；或者禁止并行批次。

（附：`budget.PRICES` 里 Sonnet 5.5 的单价——输入 2、输出 10、缓存读 0.10 美元/百万 token——与官方模型表一致，没有问题。）

## 9. 低严重度问题

| 编号 | 问题 | 证据 | 建议 |
|---|---|---|---|
| L1 | 协议漏洞：①后续尝试仍写 `response_type: FIRST` 时不要求 `reason`，并直接以 `MISMATCH_RETRIES_EXHAUSTED` 结束；②第一次就写 `INSISTED` 会跳过"不一致"回馈；③写 `REVISED` 但读法没变不检查 | `agent.py:119, 128-134`；用 FakeClient 复现①②。数据中 0 次（所有首次都是 FIRST） | 第 n>1 次只接受 REVISED/INSISTED，第 1 次只接受 FIRST；REVISED 而 `reading_key` 不变时作为检查错误 |
| L2 | `stop_reason` 为 `max_tokens` / `pause_turn` 时没有专门标识（只会落到"没提交"或"格式错"）；`report_uncertainty` 超过 6 条后被拒的疑问不留给审核员 | `agent.py:231-244, 164-165`；数据中 0 次 | 加 `RUN.MODEL.TRUNCATED`；被拒的疑问也存进诊断 |
| L3 | `schemas.py:8-9` 说盲解析由 `tests/test_blind.py` 保证，该文件不存在（实际测试在 `tests/test_agent.py:55-70`） | `ls tests` | 改文档 |
| L4 | 留存数据里没有实际发出的系统提示，只有 SKILL.md 的哈希；例子库 `data/interim/skill/examples.json` 不在 `versions()` 里（`config.py:54-60`），改例子不会改版本号。样本 B 里 1 条记录与系统提示中的某个例子文字完全相同（票货不同） | 第 1 节方法 4 | 把系统提示全文哈希（含例子）写进每条记录；例子库加版本号；样本排除与例子同文字的记录 |
| L5 | pytest 的 `tmp_path` 写到系统临时目录（项目文件夹以外），与第 2 节"不在项目文件夹以外写任何文件"字面冲突；阶段 0 跑过读测试集 ID 列的测试（D-08 已记） | `tests/test_db.py:16,37,55,72`、`tests/test_tools_and_rules.py:84` | 在 `pyproject.toml` 给 pytest 设项目内被忽略的 `--basetemp`；在验收包里说明 D-08 |
| L6 | deny 规则按命令文本匹配：通过 Python 拼路径读取测试集或原始数据、`git -C . push` 之类写法不会被拦 | `.claude/settings.json` | 在 `records.py` 读取层加硬检查（拒绝测试集和 `data/` 下原始文件路径）；deny 补 `Bash(git * push*)` |
| L7 | 任意非 ASCII 字符就打 `REC.TEXT.INJECTION_SUSPECT`（attention）；`[<>{}\`]` 也是注入模式 | `textprep.py:163-164`、`rules.yaml:115`；数据中 24 次注入命中含 `non_printable_or_non_ascii`，如 mock 里的葡萄牙语 `NÃO COBRAR` | 非 ASCII 单独成 info 级诊断，不与注入共用代码 |
| L8 | SQLite 写入用 `INSERT OR IGNORE`，主键冲突时静默丢行；`batch_id` 只由批次名和行数哈希得到，同名同行数的两批会冲突 | `db.py:73, 94` | 用普通 INSERT，冲突即报错；`batch_id` 加入内容哈希 |
| L9 | taxonomy 的 `phrasings` 含单条记录的拼写错误（如 `TAILAGTE`、`REDILVERY`、`PURCAHSE FEE`），并被代码用来决定"不是人名、不脱敏"（`textprep.py:59-65, 92`），承运商写法因此进入代码行为 | `config/taxonomy.yaml:23-56` | 别名表可以保留（决定 3.6），但脱敏豁免改用通用费用词表，不用别名 |
| L10 | 事实导出的 `amount` 只从数字表取值（`db.py:183, 189`），计入主张的认不出区域会导出 `amount: null` | 代码阅读；当前数据中这类记录都不一致，没有进导出 | 用 `values`（含区域读值）填 `amount` |
| L11 | `agent.max_turns` 12→14、新增 `max_uncertainty_reports: 6`、新增 `ITEM.ARITH.QTY_RATE_NO_RESULT`（attention）、`NUM.ARITH.CUE_WITHOUT_RELATION`、`REC.FIELD.CURRENCY_UNDETERMINED` 没有写进 `expectation_changes.zh.md` | 对照 `scratch/prototype/rules.yaml:86` 与 `config/rules.yaml:73,76` | 补进改动记录并写理由 |
| L12 | `ITEM.AMOUNT.UNNAMED` 定为 return 的理由写的是"代码能确定的问题"，但它由模型给空费用代码触发（`checks.py:380-381`）；它决定了 109 条"建议退回"中的 107 条（stage1、dryrun 以外的 15 个运行合计） | 数据统计 | 理由改写为实际情况，或只在原文确实没有费用词时才 return（用户已在 P-05 暂缓，属记录问题） |

另：公开 mock 上全大写人名有 11 处没脱敏（待决 P-08 已列）。这意味着开发集真实文本里的人名有一部分可能已经发给了模型，与 `CLAUDE.md` 的脱敏要求有张力，建议在验收包里明确写出这一风险，而不只是作为召回指标。

---

## 附：本次审计执行过的主要命令

- `git diff --stat main...autorun-leg1`、`git log main..autorun-leg1`、`git log -p ... -- skill/.../SKILL.md`、`git branch -r`、`git remote -v`
- 用 `uv run python -`（标准输入脚本，不落盘）逐条读取 `data/interim/runs/*/records.jsonl`、`export_facts.json`、`data/interim/autorun/samples/*.txt`、`data/external/mock_public/mock_records.jsonl`；用 `freight_lineitems.records.load_dev()` 读开发集做承运商短语统计和样本独立性检查
- 用 `tests/helpers.py` 与 `tests/test_agent.py` 的 FakeClient 在内存中复现 H1、M2、M3、L1（不调用 API）
- `uv run pytest -q`
