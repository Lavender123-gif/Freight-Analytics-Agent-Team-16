# 02 成型设计方案（v3）与开发集实测

## 0. 范围、方法与口径

- **依据**：任务书 `docs/tasks/cc_task_02_design_proposal.md` 第四节的设计决定；`01_problem_inventory.md`；`01b_version_pairs.md`（其第 5 节修正优先于 01）；`scratch/analysis/` 全部脚本。`docs/design/` 下两份旧文件只读来了解来龙去脉，没有作为依据。
- **数据**：只用开发集 `data/processed/dev.csv`（953 行，按 P1 合并导出重复后 908 条争议事件，813 个 shipment）。没有打开测试集和原始 Excel。没有从任何脚本调用 LLM API。
- **原型**：全部在 `scratch/prototype/`，不在 `src/`。附加依赖（pydantic、pyyaml、presidio-analyzer、spaCy 模型）用 `uv run --with` 装在临时环境里，**没有改 `pyproject.toml`**。行级输出（记录对象、事件日志、Excel 导出）只写到 git-ignored 的 `data/interim/prototype/`。

  | 文件 | 内容 |
  |---|---|
  | `schemas.py` | Pydantic 数据模型：记录对象、LLM 输入、LLM 输出、诊断、flag、修复回执、事件日志 |
  | `taxonomy.yaml`、`tax_rules.yaml` | 费用代码表草稿、税率表 |
  | `diagnostics_catalog.yaml` | 诊断类型目录（每种的固定说明，打回通知取自这里） |
  | `rules.yaml` | 规则配置：严重程度、转人工作用、自动打回、阈值、容差 |
  | `gate.py` | 第 0 到 1 步：读入、合并导出重复、脱敏、注入检查 |
  | `number_parse.py` | 第 2 步：数字识别、编号、覆盖检查 |
  | `checks.py` | 第 2 步的记录级检查；第 4 到 5 步（提交工具内部）的全部检查 |
  | `history.py` | 第 5.5 步：同一票货更早记录的比对 |
  | `disposition.py` | 第 6a 到 6c 步：汇总成 flag、处置规则、打回草稿 |
  | `tools.py` | 五个工具的定义（写给 LLM 读）、实现，以及提交控制器（重试与回执） |
  | `pipeline.py` | 单条记录走完第 0 到 7 步；第 3 步可插拔 |
  | `run_dev.py` | 在整个开发集上跑代码能做的部分并计数（第 7 节） |
  | `walkthrough.py` | 10 条走例，第 3 步由我扮演（第 8 节） |
  | `presidio_eval.py` | 脱敏漏检率与误删率（第 7.4 节） |
  | `prototype_checks.py` | 17 个检查的单元测试，只用合成字符串 |
  | `render_catalog.py` | 把目录和规则渲染成第 4 节的表 |
  | `skill/SKILL.md` | Agent 操作规程草稿 |
  | `run.sh` | 带附加依赖运行上面脚本的包装 |

  复现命令（从仓库根目录）：`sh scratch/prototype/run.sh run_dev.py`、`sh scratch/prototype/run.sh walkthrough.py`、`sh scratch/prototype/run.sh presidio_eval.py`、`uv run --with pydantic --with pyyaml --with pytest pytest scratch/prototype/prototype_checks.py -q`、`uv run --with pyyaml python scratch/prototype/render_catalog.py`。测试文件故意不叫 `test_*.py`，这样项目原有的 `uv run pytest` 不会去收集它（原有 5 个测试仍全部通过）。
- **计数单位**：默认是争议事件（908），必要时同时给出行数（953）。
- **标记**：【事实】= 脚本可复现；【推测】= 我的解释或估计。第 8 节第 3 步是我扮演的 LLM，**不代表模型的实际表现**。
- **脱敏**：例子中的人名写作 `[PERSON]`，邮箱写作 `[EMAIL]`；不引用 shipment 号、发票号和承运商代码。

---

## 1. 总览

### 1.1 方案一句话

代码先把文本里的每个数字找全、编号、记下客观特征；LLM 只对编号下判断（是什么、处于什么状态、属于哪项费用、原文依据是什么），唯一的出口是 `submit_line_items`；提交工具内部的检查把"模型能改的错"退回给模型，把"数据本身的问题"只记下来；之后代码再拿同一票货更早的记录比对。所有发现先成为挂在具体对象上的**诊断**，汇总成 **flag**，再由 `rules.yaml` 里的规则算出三种处置之一：**自动打回**、**转人工**、**拆分可信**（`SPLIT_TRUSTED`，只表示拆分结果可信，不涉及付款）。

### 1.2 与第四节流程的对应

| 第四节步骤 | 本方案的实现 | 原型文件 | 与第四节的差别 |
|---|---|---|---|
| 0-1 读入与门控 | 按 (shipment, Event Date, 文本, Invoice Amount, Delta) 合并；Presidio + 邮箱正则脱敏；注入检查；Delta 正负作为结构属性记录 | `gate.py` | 脱敏需要在 Presidio 前做大小写处理并加上下文规则，见 1.3 的 D10 |
| 2 数字识别与标准化 | 先认领日期时间，再认领数字；记录原文写法、标准化值、位置、`$`、空格合并、前导点、尾随点、小数位、紧邻减号、前一个符号、后一个词与单位词；覆盖检查 | `number_parse.py` | 无 |
| （新增）打回预判 | 第 2 步之后、第 3 步之前，用第 5.5 步的同一段代码（只看更早的记录）判断是否自动打回；命中则不调用模型 | `pipeline.py` | D4 |
| 3 理解 | 单一模型，五个工具的 agent 循环，SKILL.md 作为操作规程 | `tools.py`、`skill/SKILL.md` | 无 |
| 4-5 提交检查 | 在 `submit_line_items` 内部：结构、引用、短语、单位冲突、对账、税、合计；按目录决定退回或只记录；重试 2 次；原样重提即结束 | `checks.py`、`tools.py` | D3、D5、D6 |
| 5.5 历史检查 | 只看 Event Date 严格更早的记录；同一分钟互相不可见；第 3 步之后用模型的计入金额和费用代码再跑一遍 | `history.py` | D11 |
| 6a 汇总 | 按代码、位置去重，从 `rules.yaml` 取严重程度和作用 | `disposition.py` | 无 |
| 6b 处置规则 | 自动打回 → 单独即转人工 → 累计分数达到阈值转人工 → 拆分可信 | `disposition.py`、`rules.yaml` | 无 |
| 6c 打回 | 模板文字全部取自目录；自动打回直接生成通知，转人工的生成草稿 | `disposition.py` | 无 |
| 7 输出 | 记录对象 JSON、追加式事件日志、Excel（两张表） | `run_dev.py` | D7 |

### 1.3 与第四节结论不同、或第四节没有规定而我做了决定的地方

| 编号 | 内容 | 理由 |
|---|---|---|
| **D1** | **不设 `dispute_type`。** | 见 2.6。它原来唯一的下游用途（选对账规则）已经没有了；其余用途都能由更细的、可校验的字段或 flag 推出来；留一个没有检查者的 LLM 输出字段，等于新增一个静默错误面 |
| **D2** | 依据类型在第四节四种（已通知 PPG、按 PPG 清单、按合同、无）之外加三种：`PPG_APPROVED`、`SHIPPING_DOCUMENT`、`OTHER`；"按合同"扩为 `CONTRACT_OR_TARIFF` | 开发集里有 `APPROVED BY [PERSON]`、`EMAILED ... RATE APPROVAL`（声称批准，强于通知）、`AS PER BOL`（单据，不是合同）、`AS PER TERMS AND CONDITIONS`（条款）。审核员核实它们要查不同的东西，合在一起会丢信息 |
| **D3** | 对账规则的三处细化：(a) `TOTAL` 不进和，只用来比对；(b) Delta 为负时和 \|Delta\| 比；(c) 文本只写税种不写税额（`+ HST`）时，代码用 \|Delta\| − 计入之和算出**隐含税额**，与税率表一致才算对上，隐含税额标为代码推算，不是原文金额 | (a) 否则 `a + b = c` 会把 c 算两遍；(c) 第四节规定模型不能写金额，而 `+ HST` 的记录又没有原文金额可引用，只能由代码推算 |
| **D3'** | 把第四节"Delta 恰为合计两倍"推广为 `CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE`：**Delta = 各项 + 合计** | 【事实】开发集里 `MISSING $41.25 DETENTION TIME AND $15.00 CV19 FEE + HST = $63.55` 的 Delta 是 119.80 = 41.25 + 15 + 63.55，不是 2 倍，但机制相同（合计被计了两次）。"2 倍"只是各项之和恰好等于合计时的特例。推广后同一条规则覆盖 11 条事件，而不是 9 条 |
| **D4** | 自动打回在第 3 步**之前**判定，命中则不调用模型 | 判定条件（文本为空或只有数字、更早没有同 Delta 的完整说明）全部是代码可定的；调用模型不会改变结论，只增加一个可能出错的环节 |
| **D5** | 修复回执明确给模型一个"坚持原读法"的出口：原样重提即结束重试，记录转人工，最后一次答案标为未通过 | 第四节说对账不平要退回给模型，又说退回数据问题会诱导凑数。两者之间的缝隙是：模型读对了，但 Delta 和文本本来就对不上（开发集约 0.2% 到 1.2%，见 7.3）。如果不给出口，模型唯一能"通过"的办法就是改状态凑数 |
| **D6** | 增加三种反凑数诊断：`NUM.JUDGMENT.DOLLAR_EXCLUDED`（写了 `$` 的金额没有计入，单价例外；**单独即转人工**）、`CLAIM.RECON.PASSED_AFTER_RETURN`（附改动清单）、`RUN.TOOL.RECONCILE_OVERUSE` | 退回对账不平这条路一旦存在，就要能看出模型是不是凑出来的。走例 W3C 演示了：模型静默去掉一个金额后对账通过，仍然被这条诊断送去人工 |
| **D7** | `Dispute Status` 连记录对象都不进，只在第 7 步导出 Excel 时按 `record_id` 关联回去 | 第四节只要求它不进 LLM。不进记录对象更彻底：任何读记录对象的代码（包括以后的规则）都碰不到它，避免它悄悄变成处置规则的输入 |
| **D8** | 费用代码挂在数字上（第四节已定），line item 只引用数字编号，并补上原因片段和依据；只有"提到费用但没有金额"的 line item 自己带代码 | 避免同一事实写两遍，两处不一致又要多一种检查 |
| **D9** | 诊断对象在第四节举的四类（数字、line item、记录、与其他记录的关系）之外，单列"主张汇总"（`CLAIM`）和"处理过程"（`RUN`） | 对账、合计属于记录 JSON 里的 `claim` 对象；重试用完、模型报告没把握属于 `run` 对象。按"挂在 JSON 的哪个对象上"来分，它们就是独立的对象 |
| **D10** | 脱敏不能只靠 Presidio：全大写文本下它漏掉 95% 的人名词（7.4）。方案改为"按词典转大小写 + Presidio + 通用上下文规则" | 实测。但上下文规则是我读过开发集后写的，开发集上 0% 的漏检率是**样本内**数字，见 7.4 和第 10 节 |
| **D11** | 第 5.5 步增加 `HIST.REPEAT.REVISED_SAME_CHARGES`（同一费用代码、不同 Delta 再提），并因此要求**同一票货的记录按 Event Date 顺序处理**，更早记录的通过答案要存下来供后面的记录比对 | 01b 的 85 对里有 20 对"约 5% 替换"、6 对"金额变化：其他"；只看金额对不出这类关系，要用到两边的费用代码 |
| **D12** | 保留 `reconcile`，但限 3 次、全程记日志、超限打 flag，并把"去掉 `reconcile`"列为首要对照实验 | 它最直接的用途恰好是试出能对上 Delta 的组合，也就是凑数。价值需要实验证明，见 6.2 和 9.4 |

---

## 2. 数据模型

结构在 `scratch/prototype/schemas.py`，下面解释每个对象的字段为什么存在、谁会用。所有金额是 `Decimal`，序列化为字符串，不用浮点。

### 2.1 数字表（第 2 步产出，`NumberToken`）

| 字段 | 为什么存在 | 谁用 |
|---|---|---|
| `id` | `#1`、`#2` 按文本顺序。模型只引用编号，不抄数字 | 模型、所有检查 |
| `raw`、`span` | 原文写法（含 `$` 和它后面的空格）和位置。标记文本里显示的就是 `raw`，例如 `[#1 $ 8 400.00]` | 模型（看原文写法）；审核员界面（高亮） |
| `value`、`digits` | 标准化值；只留数字字符的串用于"未识别区域"的精确比对 | 对账、历史比对 |
| `has_dollar`、`dollar_space` | 是否写了 `$` | 模型；`DOLLAR_EXCLUDED` 检查 |
| `space_merged` | 是否由空格分隔的数字组合并而来（`1 684.68`） | 模型（可报告拆错）；`SPACE_MERGED_IN_CLAIM` |
| `leading_dot`、`trailing_dot`、`decimals` | `.73`、`$400.`、`33.744` 这类写法 | 模型；`UNUSUAL_DECIMALS` |
| `minus_before` | 减号紧贴（可能是负号）还是隔空格（多半是分隔符） | 模型 |
| `prev_symbol`、`prev_word`、`next_word`、`unit_hint` | 客观上下文：`@`、`=`、前后词、是否在单位词表里 | 模型；单位冲突检查；单价例外判断 |

日期时间（`DateToken`，`D1`）和未识别区域（`UnrecognizedRegion`，`?1`）分开编号，日期不要求模型逐个判断。

### 2.2 LLM 输入（`LLMInput`，白名单）

`redacted_text`、`marked_text`、`numbers`（数字表中给模型看的子集）、`unrecognized`、`delta`、`delta_sign`、`origin_province`、`destination_province`。`extra="forbid"`，这个结构之外的字段在构造时就会报错。`Dispute Status`、`Reason Code`、`Carrier` 都不在里面。每次调用的输入原样存进记录对象（`Record.llm_input`），可以重放。

**同一票货更早的记录不进 LLM 输入。**我考虑过把它们给模型（01b 4.2 曾建议"一起给出"），最后没有这样做：历史比对是代码可以确定完成的（第 5.5 步），给模型看历史反而可能让它"解释掉"重复主张。代价是后续记录里的 `BALANCE DUE $21` 只能被读成"性质未说明的金额"，要靠第 5.5 步的 flag 告诉审核员它约是上一次的 1.05 倍。

### 2.3 LLM 输出（`Submission`）

| 字段 | 为什么存在 | 谁检查 |
|---|---|---|
| `numbers[].kind`、`status`、`charge_codes` | 第四节已定的三个独立维度 | 状态与 kind 一致性、单位冲突、代码在表内 |
| `numbers[].other_phrase` | 用 `OTHER` 时必须带原文短语 | 短语核对 |
| `numbers[].evidence_phrase` | 每个判断的原文支撑 | 短语核对（精确，失败后容忍空格大小写） |
| `line_items[].amount_ref` | 指向金额编号；`null` 表示"提到但没有金额" | 引用检查、是否每个计入金额都被列出 |
| `line_items[].charge_codes` | 只在 `amount_ref` 为空时用 | 代码在表内 |
| `line_items[].quantity_ref`、`unit_rate_ref` | 可选；文本写了"数量 × 单价"时填 | `QTY_RATE_MISMATCH` |
| `line_items[].carrier_stated_reason`、`carrier_stated_basis_type`、`carrier_stated_basis` | 内容层第 3 问，字段名直接标为"承运商声称" | 短语核对 |
| `unrecognized_reads` | 唯一允许模型写数字的地方 | 只留数字字符后精确比对 |

没有任何"有效、应付、批准"一类字段，也没有自由文本说明字段：模型想表达的疑问只能通过 `report_uncertainty` 挂在具体对象上。

### 2.4 诊断、flag、修复回执

- **诊断**（`Diagnostic`）：`code`（点分层级，对象在前）、`location`（对象类别 + 记录 JSON 里的路径，如 `numbers/#3`、`content/line_items/1`、`history/<record_id>`）、`evidence`（各代码固定格式，见第 4 节）、`step`（只是属性）、`handling`（退回或只记录）、`created_at`。
- **Flag**（`Flag`）：同一代码的诊断合并成一条，带全部位置和证据、`severity`、`escalation_role`（`alone` / `score` / `none`）、`points`。后两者从 `rules.yaml` 读，改规则不用改代码。
- **修复回执**（`RepairReceipt`）：只回给模型、写日志，不进记录对象。格式见 6.3。

### 2.5 记录对象（`Record`）与事件日志（`Event`）

| 部分 | 内容 | 写入步骤 | 谁用 |
|---|---|---|---|
| `source` | `record_id`（文件 + 首行号）、shipment、合并掉的 PK 列表和行号、Event Date、三个金额、起止州省及推出的国家、Reason Code、Carrier | 0-1 | 历史比对、统计、导出；Reason Code 只用于冲突检查；Carrier 只用于评估和承运商统计 |
| `text` | 原文哈希（原文不复制）、脱敏文本、占位符个数、注入命中 | 1 | 后续所有步骤只读脱敏文本 |
| `parse` | 数字表、日期、未识别区域、标记文本、覆盖是否完整 | 2 | 模型输入、全部检查 |
| `llm_input` | 第 3 步的输入原样存档 | 3 | 重放、审计 |
| `run` | `passed` / `failed` / `not_run_auto_reject`、提交次数、`reconcile` 次数、工具调用序列、模型和 prompt 版本 | 3-5 | 统计返工、评估稳定性 |
| `content` | 通过（或最后一次未通过）的 `Submission` | 4-5 | 内容层第 2、3 问 |
| `claim` | 计入编号、计入之和、隐含税额、Delta、是否对上、合计、触发了哪些历史关系 | 4-5、5.5 | 内容层第 1 问 |
| `diagnostics`、`flags` | 全部诊断和汇总后的 flag | 各步 / 6a | 审核员、规则 |
| `disposition` | 结论、触发的规则和 flag、分数、规则版本 | 6b | 路由 |
| `reject_draft` | 是否自动、模板代码、理由、要改什么、合格标准 | 6c | 审核员或自动通知 |
| `versions` | taxonomy、规则、目录、税率表、prompt、模型的版本 | 7 | 复现 |

**事件日志**是追加式的：`ingested`、`diagnostic`、`flag`、`disposition`、`auto_reject_sent`、`reject_draft_created`、`reviewer_decision`、`carrier_resubmission_linked`。审核员的记录用 `ReviewerDecision`：决定（拆分确认、拆分更正、退回承运商、无法判断）、**问题归属**（承运商文本、承运商开票、系统解析、系统 LLM、PPG 数据、未知）、对每个 flag 的评价（有用、噪音、错误），以及更正后的内容。没有付款字段。第四节 4.1 要求的"承运商管理的数据基础"（flag、转人工原因、审核员决定与归属、承运商重提）都落在这里：重提通过第 5.5 步找到的更早记录关联起来。本项目不做基于这些数据的功能。

### 2.6 `dispute_type` 还有没有用途

第一阶段 P17 提出"处理路径分类"，理由是决定用哪条对账规则。逐条检查它还剩下的可能用途：

| 可能的用途 | 现在由什么承担 | 结论 |
|---|---|---|
| 选对账规则 | 已统一成一条规则 | 没有用途 |
| 决定记录去哪个人工队列 | 规则按 flag 计算；队列也可以按 flag 和费用代码类别由代码推出 | 不需要 LLM 给 |
| 提示审核员要核实什么 | `ITEM.BASIS.*`（PPG 通知或清单、合同或单据）、`ITEM.NATURE.RATE_CORRECTION`、数字的 `status`（付款历史）都挂在具体对象上，比记录级一个标签更细，也都经过检查 | 已覆盖，而且更细 |
| 承运商管理统计 | 由费用代码、状态、flag 聚合得到 | 可推出 |
| 帮模型更准（先分类再抽取） | v1 没有证据表明需要；01 P17 已论证主要错误来自缺信息和歧义 | 列为对照实验（9.4 的 E6）。即使实验支持，它也只是第 3 步内部的中间产物，不需要作为记录字段 |
| 评估时分层 | 分层标签由代码从标注推出，或在标注集里单独标 | 不需要运行时字段 |

保留它的代价是：一个由模型写、没有任何代码能核对的字段（它不对应原文短语，也不参与对账），出错了不会被发现；而一旦存在，下游很容易拿它当路由或统计依据，把一个未经校验的判断变成决策输入。**结论：不设 `dispute_type`。**

---

## 3. 逐步规格

| 步骤 | 输入 | 输出 | 由谁做 | 会产生的诊断 | 失败时 |
|---|---|---|---|---|---|
| 0 读入 | 开发集 CSV（以后是 OTM 导出） | 一行一个对象；金额转 `Decimal`；空白归一 | 代码 | 无 | 列缺失、金额不能解析：整个文件退回（文件级检查，不是逐条） |
| 1 门控 | 第 0 步的行 | 合并后的事件；脱敏文本；注入命中；国家 | 代码（Presidio + 规则） | `REC.INPUT.EXPORT_DUPLICATE`、`REC.TEXT.EMPTY`、`REC.TEXT.PII_REDACTED`、`REC.TEXT.REDACTION_ALTERED_DIGITS`、`REC.TEXT.INJECTION_SUSPECT`、`REC.FIELD.DELTA_ZERO`、`REC.FIELD.DELTA_NEGATIVE`、`REC.FIELD.CROSS_BORDER` | 脱敏改动了数字字符：单独即转人工。注入嫌疑：继续处理但单独即转人工。脱敏漏检运行时发现不了，只能离线测（7.4） |
| 2 数字识别 | 脱敏文本 | 数字表、日期、未识别区域、标记文本、覆盖标志 | 代码 | `REC.TEXT.NUMBERS_ONLY`、`REC.TEXT.NO_NUMBER`、`REC.TEXT.DATE_AFTER_EVENT`、`NUM.PARSE.*` | 覆盖检查保证没有数字字符被漏掉：漏掉的一定成为未识别区域，交模型解读，解读值逐位比对。认错（合并、拆分）只能部分靠对账发现，正确率需要离线标注（9.2） |
| 打回预判 | 第 1、2 步的诊断 + 更早记录（文本、Delta） | 是否自动打回 | 代码 | `HIST.CONTEXT.EARLIER_EXPLAINED` 等第 5.5 步诊断（预判模式） | 命中且无豁免：不调用模型，直接到 6c |
| 3 理解 | `LLMInput`、SKILL.md、五个工具 | 工具调用；一次或多次 `submit_line_items` | LLM | `RUN.AGENT.UNCERTAINTY_REPORTED`、`RUN.TOOL.RECONCILE_OVERUSE`、`RUN.SUBMIT.NONE` | 轮数上限（12）内没有提交：`RUN.SUBMIT.NONE`，单独即转人工 |
| 4-5 提交检查 | 一次提交 | 接受，或修复回执 | 代码（在提交工具内部） | 退回类 15 种（`NUM.REF.*`、`NUM.JUDGMENT.*` 中的 4 种、`NUM.READ.*`、`ITEM.CODE.UNKNOWN`、`ITEM.CODE.OTHER_PHRASE_MISSING`、`ITEM.REF.*`、`ITEM.PHRASE.NOT_FOUND`、`CLAIM.RECON.SUM_MISMATCH`、`RUN.SUBMIT.SCHEMA_INVALID`）；只记录类见第 4 节 | 首次 + 2 次重试；原样重提立即结束；仍不通过则最后一次答案标为未通过，加 `RUN.SUBMIT.FAILED`（单独即转人工） |
| 5.5 历史检查 | 本条 + 同一票货 Event Date 严格更早的记录（含其通过的答案） | 历史诊断；`claim.history_relations` | 代码 | `HIST.*` | 更早记录没有通过的答案时，只做文本和 Delta 层面的比对。同一分钟的记录只得到 `SAME_MINUTE_SIBLING` |
| 6a 汇总 | 全部"只记录"类诊断 | flag 列表 | 代码 | 加上 `REC.FIELD.REASON_CODE_CONFLICT` | `rules.yaml` 缺某个代码的配置：代码直接报错（`render_catalog.py` 里有断言），不会默认放过 |
| 6b 处置 | flag | `AUTO_REJECT` / `HUMAN_REVIEW` / `SPLIT_TRUSTED` | 代码 + `rules.yaml` | 无 | 无 |
| 6c 打回 | flag + 处置 | 自动通知或审核员草稿 | 代码生成，人决定 | 无 | 没有承运商可改的 flag 时不生成草稿 |
| 7 输出 | 记录对象 | JSON、事件日志、Excel | 代码 | 无 | 无 |

**处理顺序**：同一票货内按 Event Date 升序处理（D11）；同一分钟的记录彼此独立；不同 shipment 之间可以并行。

---

## 4. 诊断类型目录

### 4.1 组织方式

代码三段：`对象.子类.类型`。对象是记录 JSON 里的位置（`REC` 记录、`NUM` 数字、`ITEM` line item、`CLAIM` 主张汇总、`HIST` 与同一票货其他记录的关系、`RUN` 处理过程）；子类相当于异常类的中间层（如 `NUM.PARSE` 是解析特征，`NUM.REF` 是引用错误，`NUM.JUDGMENT` 是判断问题，`NUM.READ` 是未识别区域的解读）。"在哪一步发现"只是每条诊断的 `step` 属性：例如 `HIST.*` 既可能在打回预判时发现，也可能在第 3 步之后发现。

### 4.2 退回还是只记录

只有**模型改答案就能解决**的才退回：引用了不存在的编号、漏判编号、状态与 kind 矛盾、金额紧跟重量单位、短语在原文里找不到、代码不在表里、计入金额没有列成 line item、未识别区域读错，以及计入之和对不上 Delta。**数据本身的性质**一律只记录：合计被计两次、文本算式不成立、税额与税率表不符、`+ HST` 的推算、历史关系、承运商声称的依据。退回后者只会诱导模型去改判断凑数。

"计入之和对不上 Delta"是唯一两边都可能的情况：可能是模型读错（应退回），也可能是数据对不上（不该退回）。处理办法是：先排除代码能识别的数据型模式（Delta 为 0、合计被计两次），剩下的才退回；同时在回执里明确允许"原样重提 + 报告没把握"（D5），并用 `DOLLAR_EXCLUDED`、`PASSED_AFTER_RETURN` 检查退回后的改动（D6）。

### 4.3 完整清单

下表由 `render_catalog.py` 从 `diagnostics_catalog.yaml` 和 `rules.yaml` 生成。共 61 种：退回 15 种，只记录 46 种。退回类不生成 flag：重试成功就消失（只留 `CLAIM.RECON.PASSED_AFTER_RETURN`），重试用完则汇总进 `RUN.SUBMIT.FAILED` 的证据。

#### 记录（REC）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `REC.INPUT.EXPORT_DUPLICATE` | 多行在 (shipment, Event Date, 文本, Invoice Amount, Delta) 上完全相同，被合并为一条 | {n_rows, source_rows, pks} | 1 | 只记录 | info / none | 无需处理；统计时按合并后的一条计 | 无 | 无 |
| `REC.TEXT.EMPTY` | 说明文本为空或只有空白 | {text_length} | 1 | 只记录 | high / alone | 没有任何可拆分内容 | 补充说明：写明每一项费用的名称和金额，以及收费原因 | 文本至少包含一个费用名称和一个金额，且列出的金额之和等于本次差额 |
| `REC.TEXT.NUMBERS_ONLY` | 文本去掉数字、日期、标点后没有任何字母 | {text, numbers} | 2 | 只记录 | high / alone | 金额没有名称；若同一票货更早有同 Delta 的完整说明，参照该记录 | 写明这笔金额对应的费用名称和收费原因 | 每个金额旁边都有费用名称；金额之和等于本次差额 |
| `REC.TEXT.NO_NUMBER` | 文本有文字但没有任何数字（如 "PURCHASED TRANSPORTATION SURCHARGE --"） | {text} | 2 | 只记录 | high / alone | 有费用名称没有金额，无法对账 | 写明该项费用的金额 | 每个费用名称都有对应金额，金额之和等于本次差额 |
| `REC.TEXT.INJECTION_SUSPECT` | 文本命中 rules.yaml 中的指令式模式，或含不可打印字符、超长 | {patterns_hit, length} | 1 | 只记录 | critical / alone | 文本可能试图影响自动处理；人工阅读原文 | 无 | 无 |
| `REC.TEXT.PII_REDACTED` | 脱敏替换了人名或邮箱 | {n_person, n_email}（不含原值） | 1 | 只记录 | info / none | 无需处理；导出时可在本地还原 | 无 | 无 |
| `REC.TEXT.REDACTION_ALTERED_DIGITS` | 脱敏前后文本的数字字符序列不同（脱敏误删了数字） | {digits_before_count, digits_after_count} | 1 | 只记录 | critical / alone | 脱敏影响了金额，拆分结果不可信 | 无 | 无 |
| `REC.TEXT.DATE_AFTER_EVENT` | 文本中带年份的日期晚于 Event Date 超过 1 天 | {latest_text_date, event_date, days_after} | 2 | 只记录 | info / none | 文本可能在 Event Date 之后写成或改过；历史比对的时间顺序要谨慎看待 | 无 | 无 |
| `REC.FIELD.DELTA_ZERO` | Delta 为 0 | {delta} | 1 | 只记录 | high / alone | 没有对账锚点，拆分无法用 Delta 验证；文本可能是费率、批准额或结案说明 | 无 | 无 |
| `REC.FIELD.DELTA_NEGATIVE` | Delta 小于 0（承运商开票低于计划金额） | {delta} | 1 | 只记录 | high / alone | 这不是多收，按文本核对承运商在说什么 | 无 | 无 |
| `REC.FIELD.CROSS_BORDER` | 起点和终点国家不同 | {origin_country, destination_country} | 1 | 只记录 | info / none | 税的适用规则可能不同（零税率等，待确认） | 无 | 无 |
| `REC.FIELD.REASON_CODE_CONFLICT` | Reason Code 映射到一个具体类别（rules.yaml 映射表），模型给出的费用代码也属于具体类别，且两者不同 | {reason_code, reason_category, model_categories} | 6a | 只记录 | low / none | 结构化编码和文本内容不一致；以文本为准，编码问题用于统计 | 无 | 无 |

#### 数字（NUM）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `NUM.PARSE.UNRECOGNIZED_REGION` | 有数字字符没有被数字或日期规则认领（如 "CV19"） | {region_id, raw, span} | 2 | 只记录 | low / score +1 | 该处由模型解读，解读值已与原文数字字符精确比对 | 无 | 无 |
| `NUM.PARSE.SPACE_MERGED` | 数字由空格分隔的数字组合并而成（"1 684.68"） | {id, raw, value} | 2 | 只记录 | info / none | 合并是规则推断，可能本应是两个数 | 无 | 无 |
| `NUM.PARSE.UNUSUAL_DECIMALS` | 小数位不是 0、1、2（"33.744 LBS"） | {id, raw, decimals} | 2 | 只记录 | info / none | 点可能是千分位 | 无 | 无 |
| `NUM.PARSE.LEADING_DOT` | 以点开头的小数（".73"） | {id, raw} | 2 | 只记录 | info / none | 常见于费率 | 无 | 无 |
| `NUM.PARSE.MINUS_ADJACENT` | 数字或 $ 紧贴一个减号（"-250"、"-$ 400.00"） | {id, raw} | 2 | 只记录 | info / none | 减号可能是负号，也可能是分隔符 | 无 | 无 |
| `NUM.REF.UNKNOWN_ID` | 提交中引用了编号表里没有的编号 | {given, valid_ids} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.REF.DUPLICATE_ID` | 同一编号被判断了不止一次 | {id, count} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.REF.MISSING_ID` | 编号表中有编号没有被判断 | {missing_ids} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.JUDGMENT.STATUS_ON_NON_MONEY` | kind 为 RATE、QUANTITY、REFERENCE 却给了 NONE 以外的 status | {id, kind, status} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.JUDGMENT.UNIT_CONFLICT` | 判为金额类 kind 的数字紧跟重量、百分比、天数等单位词 | {id, kind, unit_hint} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.JUDGMENT.EVIDENCE_NOT_FOUND` | evidence_phrase 在脱敏原文中找不到（精确匹配和容忍空格、大小写的匹配都失败） | {id, phrase} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.JUDGMENT.DOLLAR_EXCLUDED` | 带 $ 的数字被判为非金额 kind，或金额 kind 但 status 为 NONE；判为 RATE 且有单价线索（@、AT、EACH、PER、A DAY，见 rules.yaml）的不算 | {id, raw, kind, status} | 4-5 | 只记录 | high / alone | 一个写了 $ 的金额没有计入本次主张；核对这个排除是否合理（可能是为了凑 Delta） | 无 | 无 |
| `NUM.JUDGMENT.SPACE_MERGED_IN_CLAIM` | 由空格合并出来的数字被计入本次主张 | {id, raw, value} | 4-5 | 只记录 | medium / score +2 | 计入的金额来自推断性的合并，核对原文 | 金额不要用空格分隔千位 | 金额写成连续数字（如 8400.00） |
| `NUM.READ.UNRECOGNIZED_MISMATCH` | 模型对未识别区域给出的值，去掉非数字字符后与原文该区域的数字字符不相等 | {region_id, raw_digits, given_digits} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.READ.UNRECOGNIZED_UNREAD` | 有未识别区域没有给出解读 | {region_ids} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |

#### line item（ITEM）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `ITEM.CODE.UNKNOWN` | 费用代码不在 taxonomy 中 | {path, code} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.CODE.OTHER_PHRASE_MISSING` | 使用 OTHER 但没有 other_phrase，或 other_phrase 不在原文中 | {path, other_phrase} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.CODE.OTHER` | 费用代码为 OTHER | {path, other_phrase} | 4-5 | 只记录 | medium / score +2 | 费用不在代码表中，人工确认名称；同时是扩充代码表的候选 | 使用标准费用名称 | 费用名称属于 PPG 认可的费用清单 |
| `ITEM.CODE.PENDING_MEANING` | 费用代码属于 PENDING 类（purchase(d) transportation） | {path, code} | 4-5 | 只记录 | info / none | 这项费用的含义和计费方式尚未确认，拆分只能说明"承运商收了这一项" | 无 | 无 |
| `ITEM.CODE.COMBINED` | 一个金额对应多个费用代码 | {path, codes, amount} | 4-5 | 只记录 | low / score +1 | 金额无法拆到各项；不要自行按惯例拆分 | 每项费用分别列出金额 | 每个费用名称各有一个金额，金额之和等于本次差额 |
| `ITEM.REF.CLAIM_NOT_ITEMIZED` | status 为 CLAIMED 或 UNPAID 的非合计金额没有被任何 line item 引用 | {ids} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.REF.INVALID` | line item 引用了不存在的编号、非金额编号、非计入状态的编号，或同一编号被多个 line item 引用 | {path, amount_ref, reason} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.PHRASE.NOT_FOUND` | carrier_stated_reason、carrier_stated_basis 或 other_phrase 在原文中找不到 | {path, field, phrase} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.AMOUNT.MISSING` | 一个非税的费用被提到但没有金额（amount_ref 为空） | {path, codes} | 4-5 | 只记录 | high / alone | 有费用名没有金额，这一项无法对账 | 写明该项费用的金额 | 每个费用名称都有金额 |
| `ITEM.AMOUNT.UNNAMED` | 计入本次主张的金额没有任何费用代码 | {path, amount_ref, amount} | 4-5 | 只记录 | medium / score +2 | 这笔钱没有写明是什么费用；不要按 Reason Code 或惯例补名称 | 写明这笔金额对应的费用名称 | 每个金额旁边都有费用名称 |
| `ITEM.TAX.NO_AMOUNT` | 文本提到税（"+ HST"）但没有写税额；代码按 Delta 与其他金额之差算出隐含税额 | {path, implied_tax, expected_tax, province} | 4-5 | 只记录 | low / score +1 | 税额是代码推算的，不是原文金额；推算值为 0 表示 Delta 没有包含税 | 写明税额 | 税种和税额都写出，税额与适用税率一致 |
| `ITEM.TAX.RATE_MISMATCH` | 税额（原文的或推算的）与税率表按基数计算的结果相差超过容差 | {path, base, tax, implied_rate, expected_rate, province} | 4-5 | 只记录 | high / alone | 税额与该省税率不符，核对适用省份和基数 | 按适用税率重新计算税额 | 税额 = 基数 × 适用税率（误差不超过 1 分） |
| `ITEM.TAX.NO_RULE` | 提到税，但适用省份没有税率规则（非加拿大，或 PST/QST 是否适用于运费未定） | {path, province, tax_codes} | 4-5 | 只记录 | medium / score +2 | 税额未经检查 | 无 | 无 |
| `ITEM.BASIS.PPG_CLAIMED` | 依据类型为 PPG_NOTIFIED、PPG_APPROVED 或 PPG_LIST | {path, basis_type, basis} | 4-5 | 只记录 | info / none | 承运商声称 PPG 通知、批准或有清单；需对照 PPG 内部记录核实，系统未核实 | 无 | 无 |
| `ITEM.BASIS.CONTRACT_CLAIMED` | 依据类型为 CONTRACT_OR_TARIFF 或 SHIPPING_DOCUMENT | {path, basis_type, basis} | 4-5 | 只记录 | info / none | 需对照合同、价目表或单据核实，系统未核实 | 无 | 无 |
| `ITEM.NATURE.RATE_CORRECTION` | 费用代码属于 RATE_CORRECTION 类 | {path, code} | 4-5 | 只记录 | low / none | 主张的是费率或计费方式错误，金额是差额，需要合同才能核实 | 无 | 无 |
| `ITEM.ARITH.QTY_RATE_MISMATCH` | line item 给出了数量和单价，数量 × 单价 ≠ 金额 | {path, quantity, unit_rate, amount} | 4-5 | 只记录 | medium / score +2 | 文本自己的算式不成立 | 更正数量、单价或金额，使三者一致 | 数量 × 单价 = 金额 |

#### 主张汇总（CLAIM）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `CLAIM.RECON.SUM_MISMATCH` | 计入状态的非合计金额之和（加上推算税额）≠ Delta，且不属于下面的数据型模式 | {counted_ids, claimed_sum, delta, difference} | 4-5 | 退回 | 不生成 flag | 重试用完后见 RUN.SUBMIT.FAILED | 列出的金额之和要等于本次差额 | 列出的金额之和等于本次差额 |
| `CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE` | 文本写了合计（a + b = c），Delta = 各项 + 合计（即合计被算了两次；a + b = c 时 Delta = 2c 是其特例） | {claimed_sum, total, delta} | 4-5 | 只记录 | high / alone | 发票金额可能把同一组费用计了两次；拆分本身按文本给出 | 发票金额只计一次合计 | 本次差额等于文本合计 |
| `CLAIM.RECON.TOTAL_MISMATCH` | 文本中的合计与计入金额之和（加推算税额）不一致 | {total_id, total, claimed_sum, implied_tax} | 4-5 | 只记录 | medium / score +2 | 文本自带的算式不成立 | 更正合计或各项金额 | 各项之和等于合计 |
| `CLAIM.RECON.PASSED_AFTER_RETURN` | 对账在第 2 次或以后的提交才通过 | {attempt, changed_fields} | 4-5 | 只记录 | low / score +1 | 模型改了判断才对上，看改动是否有原文依据 | 无 | 无 |

#### 与同一票货其他记录的关系（HIST）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `HIST.REPEAT.IDENTICAL_TEXT` | 更早的记录文本与 Delta 都相同 | {earlier_record_id, minutes_between} | 5.5 | 只记录 | medium / alone | 同一主张重复提交 | 不要重复提交同一争议 | 同一费用只有一条未结争议 |
| `HIST.REPEAT.SAME_DELTA` | 更早的记录 Delta 相同、文本不同 | {earlier_record_id} | 5.5 | 只记录 | low / score +1 | 可能是补充说明，也可能换了名目；对照更早的记录 | 无 | 无 |
| `HIST.REPEAT.SAME_AMOUNT_NEW_CODES` | 更早的记录 Delta 相同，但两次的费用代码类别不相交（要用到模型输出） | {earlier_record_id, earlier_codes, codes} | 5.5 | 只记录 | high / alone | 同一笔金额换了费用名目再提 | 说明为什么同一金额改用了不同费用名称 | 一笔金额只对应一个费用名称，并说明改动原因 |
| `HIST.REPEAT.REVISED_SAME_CHARGES` | 更早的记录 Delta 不同，但费用代码有交集（要用到两条记录的模型输出；税代码不算） | {earlier_record_id, earlier_delta, shared_codes} | 5.5 | 只记录 | low / score +1 | 同一项费用改了金额再提，看本次是替换还是追加 | 说明本次金额是替换还是追加更早的主张 | 文本写明与更早争议的关系（替换或追加）及原因 |
| `HIST.AMOUNT.EQUALS_EARLIER_DELTA` | 本次计入的某个金额等于更早某条记录的 Delta，而本次 Delta 与那条不同 | {id, amount, earlier_record_id, earlier_delta} | 5.5 | 只记录 | high / alone | 本次文本重复列出了更早争议的金额，可能同一笔钱主张了两次 | 只列出本次新增的金额，或说明与更早争议的关系 | 本次列出的金额不包含已主张过的金额，或明确写出是替换哪一次 |
| `HIST.AMOUNT.NEAR_105_EARLIER` | 本次计入的某个金额约为更早某条记录 Delta 的 1.03 到 1.07 倍（阈值在 rules.yaml） | {id, amount, earlier_record_id, earlier_delta, ratio} | 5.5 | 只记录 | medium / score +2 | 金额像是更早金额加了约 5%（可能是 GST），但文本没有写税 | 如含税，分别写出税前金额和税额 | 税额单列，且与适用税率一致 |
| `HIST.ORDER.SAME_MINUTE_SIBLING` | 同一票货有另一条记录的 Event Date 与本条相同（精确到分钟），两者互相不可见 | {sibling_record_id} | 5.5 | 只记录 | info / none | 两条同时提交，系统没有比较它们 | 无 | 无 |
| `HIST.CONTEXT.EARLIER_EXPLAINED` | 更早的记录 Delta 相同，且文本有费用名称（用于自动打回的豁免） | {earlier_record_id} | 5.5 | 只记录 | info / none | 本条缺的说明可以在更早的记录里找到 | 无 | 无 |

#### 处理过程（RUN）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `RUN.AGENT.UNCERTAINTY_REPORTED` | 模型调用 report_uncertainty | {target_path, reason_type, note} | 3 | 只记录 | medium / score +2 | 模型对某个对象没有把握，看它指出的地方 | 无 | 无 |
| `RUN.SUBMIT.FAILED` | 重试用完（或模型原样重提）仍有可退回的错误；最后一次答案标为未通过 | {attempts, last_errors} | 4-5 | 只记录 | critical / alone | 拆分未通过检查，以原文为准人工拆分 | 无 | 无 |
| `RUN.SUBMIT.NONE` | 达到轮数上限仍没有调用 submit_line_items | {turns} | 3 | 只记录 | critical / alone | 没有拆分结果 | 无 | 无 |
| `RUN.TOOL.RECONCILE_OVERUSE` | reconcile 调用次数超过上限，或试过的不同组合数达到上限（rules.yaml agent.reconcile_max_calls） | {calls, distinct_hypotheses} | 3 | 只记录 | low / score +1 | 模型试了多种读法才找到对得上的，结果可能是凑出来的 | 无 | 无 |
| `RUN.SUBMIT.SCHEMA_INVALID` | 提交不符合工具 schema（启用 strict 后理论上不出现；保留作为兜底） | {path, msg} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |

---

## 5. 规则配置草稿（`scratch/prototype/rules.yaml`）

### 5.1 三种作用

- `alone`：单独出现即转人工。用于"拆分结果本身不可信"或"审核员必须先看这一点才能使用拆分结果"的情况：处理失败、Delta 为 0 或负、合计被计两次、重复列出更早的金额、同额换名、`$` 金额被排除、有费用名没金额、税额与税率表不符、注入嫌疑、脱敏动了数字。
- `score`：按分数累计，总分 ≥ 3 转人工。用于单独看可以接受、叠加起来说明这条记录难读的情况：未识别区域 1 分，合并金额 1 分，`OTHER` 2 分，未命名金额 2 分，约 1.05 倍 2 分，同一费用改金额再提 1 分，模型报告没把握 2 分，对账第二次才通过 1 分。
- `none`：只展示。包括所有"需要核实但不影响拆分可信度"的提示（承运商声称 PPG 通知、按合同、费率主张）、P12 的"含义待确认"代码，以及解析特征。

`SPLIT_TRUSTED` 只说明"这条记录的拆分可以直接用"，审核员仍然要做付款决定，`none` 类 flag 照样显示。

### 5.2 自动打回

```yaml
auto_reject:
  triggers: [REC.TEXT.EMPTY, REC.TEXT.NUMBERS_ONLY]
  exempt_if_any: [HIST.CONTEXT.EARLIER_EXPLAINED]     # 只看更早的记录
  earlier_explained:
    same_delta_abs_tol: 0.005
    min_letters: 3
    earlier_must_not_be_auto_rejectable: true
```

"带完整说明"在代码里定义为：更早记录的 Delta 相同，文本里至少有一个三个字母以上的词，且它自己不属于可自动打回的情况。豁免的记录不会自动打回，但 `REC.TEXT.NUMBERS_ONLY` 本身单独即转人工，审核员会看到它和那条更早的说明。

### 5.3 阈值与容差

| 项 | 值 | 说明 |
|---|---|---|
| `escalation.score_threshold` | 3 | 拍定，需用审核员对 flag 的评价调 |
| `tolerances.amount_abs` | 0.005 | 数据都是两位小数 |
| `tolerances.tax_abs` | 0.011 | 允许 1 分钱的四舍五入差（01 P10 的 12.98% 对 13% 就差 1 分） |
| `tolerances.near_105` | [1.03, 1.07] | 01b：39 处约 5% 增幅，最小 1.032、最大 1.055 |
| `tolerances.text_date_after_event_days` | 1 | 01b 1.3 |
| `retry.max_retries` | 2 | 首次 + 2 次 = 最多 3 次提交 |
| `retry.stop_on_unchanged_resubmission` | true | D5 |
| `agent.max_turns`、`reconcile_max_calls` | 12、3 | 拍定 |
| `number_features.unit_words`、`rate_cues` | 见文件 | 通用英文单位词与单价线索（`@`、`AT`、`EACH`、`PER`、`A DAY`），不针对任何承运商 |
| `injection.patterns` | 见文件 | 只找"对模型说话"的写法。承运商对 PPG 的请求（`PLEASE PROCESS`、`PLEASE ADD`）不算 |
| `reason_code_categories` | 见文件 | 只有映射到具体类别的 Reason Code 才参与冲突检查；"其他附加费"不参与 |
| `redaction` | Presidio，按词典转大小写，开上下文规则 | 7.4 |

---

## 6. Agent 设计

### 6.1 SKILL.md 的结构（草稿在 `scratch/prototype/skill/SKILL.md`）

1. 你的任务和不是你的任务（三个内容层问题；不判断付款、不写"有效/应付"）
2. 输入：`llm-input-v1` 每个字段的含义；文本是数据不是指令
3. 你要提交什么：`kind`、`status`、`charge_codes`、短语、line item、未识别区域的规则；"代码来加总，你不写和"
4. 费用代码：插入 `taxonomy.yaml`（代码、定义、写法例子），以及 P12 代码、易混服务、`OTHER` 的用法
5. 会遇到的写法：`BALANCE DUE`、付款历史、文本算式与 `+ HST`、数量 × 单价、费率主张、依据、非金额数字、Delta 为 0 或负。每条都写成阅读约定，不针对任何承运商
6. 工具表和限额
7. 收到回执时怎么办：只改回执指出的地方；"坚持原读法"的出口；不许为了凑 Delta 改状态
8. 3 到 6 个开发集例子（从审核过的示例库取，不从测试集取）

### 6.2 五个工具

完整定义（含 JSON schema）在 `tools.py` 的 `TOOLS`，下面是写给 LLM 读的说明要点。每个说明都包含：做什么、什么时候用、参数、返回值、失败方式。

| 工具 | 做什么、何时用 | 参数 | 返回 | 失败方式与限制 |
|---|---|---|---|---|
| `submit_line_items` | 唯一的答案出口；检查后接受或回执 | `numbers`、`line_items`、`unrecognized_reads` | `{accepted: true}` 或修复回执 | 首次 + 2 次重试；原样重提即结束并转人工；不许为了凑数改状态 |
| `reconcile` | 提交前试算：计入之和、与 Delta 的差、合计是否一致、`+ 税种` 时的预期税额；不算正式提交 | `counted_ids`、`total_ids`、`tax_named_without_amount` | `claimed_sum`、`difference`、`matches_delta`、`expected_tax`、`totals[].consistent_with_items`、`calls_left` | 每条记录 3 次；全部记日志；超限或试满 3 种组合打 `RECONCILE_OVERUSE`。说明里写明"试了很多组合才对上不算证据" |
| `lookup_tax_rule` | 查省份税率 | `province`、`date` | 各税种税率；PST 是否适用于运费（未定处为 `unknown`） | 只有加拿大 2021 到 2022；适用省份（起点还是终点）未定，检查暂用终点 |
| `find_similar_examples` | 取写法相似的已审核例子 | `query`、`k`（1 到 5） | 例子的标记文本和提交 | 例子只来自开发集，同一 shipment 永不返回；做"留一承运商"实验时排除该承运商。说明里写明"例子是示范，不是规则"。原型用"数字遮蔽后的词集合 Jaccard"检索 |
| `report_uncertainty` | 对某个具体对象报告没把握；只生成诊断，不决定去向 | `target_path`、`reason_type`（6 种枚举）、`note` | `{recorded: true}` | 无 |

全部工具 `strict: true`。查过当前文档：`strict: true` 保证工具输入严格符合 schema，`claude-opus-5` 支持（同时支持强制 `tool_choice`）；schema 不支持数值和字符串长度约束，Python SDK 会把它们去掉、在客户端校验。v1 建议模型 `claude-opus-5`，`tool_choice: auto` + 指令要求最后必须调用 `submit_line_items`，开 adaptive thinking。以上只是设计，本任务没有调用 API。

**`reconcile` 的问题要说清楚。**它的价值是让模型在不消耗重试次数的情况下检查算术；它的风险是让模型在提交前就试出能对上 Delta 的组合，凑数从此不会在回执里留下痕迹。原型里的应对是限次、记日志、配合 `DOLLAR_EXCLUDED`；更根本的是 9.4 的 E2 实验：如果去掉它之后准确率不降，就删掉。删掉后工具只剩 4 个，课程要求"至少 5 个"要另外考虑，但不应为了凑数保留一个有害的工具。

### 6.3 修复回执的格式

回执只陈述事实和允许的修改，不给建议值。下面是走例 W3A 第一次提交收到的回执（原型实际输出）：

```json
{
  "receipt_version": "receipt-v1",
  "accepted": false,
  "attempt": 1,
  "retries_left": 2,
  "errors": [{
    "code": "CLAIM.RECON.SUM_MISMATCH",
    "object_type": "CLAIM",
    "path": "claim",
    "evidence": {"counted_ids": ["#1", "#2", "#3", "#4"], "claimed_sum": "69.31", "delta": "48.12", "difference": "-21.19"},
    "allowed_fixes": ["re-read kind/status of the counted numbers and of the numbers you did not count",
                      "if your reading is right, resubmit it unchanged and call report_uncertainty"]
  }],
  "never_allowed": ["change the number table, add numbers, or write amounts outside unrecognized_reads",
                    "change a status or kind only to make the sum match Delta"],
  "if_you_believe_your_reading_is_correct": "Resubmit the same reading unchanged and call report_uncertainty with what does not fit. The record will be passed to a human with your reading; this is an acceptable outcome."
}
```

每个错误的 `code`、`path`、`evidence` 格式固定（第 4 节"证据"列）。回执里**不出现**只记录类的诊断：告诉模型"合计被计了两次"之类，等于提示它朝某个方向改。

### 6.4 最后一步用 Instructor 还是自己写

| | Instructor | 自己写（`tools.py` 的 `Session`） |
|---|---|---|
| 结构校验与重试 | 核心功能：Pydantic 校验失败后把错误信息附上重新请求 | `strict: true` 已在 API 层保证结构合法，Instructor 的主要价值大部分被抵消 |
| 业务检查 | 可以写成 validator 抛错，但"哪些错退回、哪些只记录"要绕开它的重试机制 | 直接按目录分两类 |
| 与其他工具的关系 | 面向"一次请求得到一个结构化对象"；提交之前还有 `reconcile`、`lookup_tax_rule` 等调用，要把它嵌进自写的循环里 | 提交只是循环里的一个工具，重试计数只算提交 |
| 特殊规则 | "原样重提即结束""回执里给出口""对比两次提交写改动清单"都要自定义 | 已实现，约 100 行 |
| 审计 | 中间尝试要另外挂钩记录 | 每次尝试和回执都在 `tool_log` 里 |
| 依赖 | 新增一个包，并包装 SDK 客户端；项目规定只用官方 SDK、不用框架 | 只用 Anthropic SDK |

**建议自己写。**原型的 `Session.submit` / `_reject` / `_fail` / `finish` 就是这部分，已有单元测试（重试上限、原样重提）。

---

## 7. 用开发集实测

### 7.1 跑了什么

`run_dev.py` 在全部 908 条事件上跑了第 0 到 2 步、打回预判、第 5.5 步（预判模式）和第 6 步，**没有第 3 步**，所以第 4 到 5 步中依赖模型输出的检查没有跑。为了估计它们，脚本另外算了一个"对账代理指标"（7.3）。第 4 到 5 步的检查本身在第 8 节走例和 `prototype_checks.py` 的 17 个合成用例里实际运行过。

原型过程中发现并修好的两个问题，说明了"不允许静默错误"在实现上的具体含义，在这里记下：

1. 【事实】脱敏占位符 `[PERSON_1]` 里有数字字符，第一次运行时被"脱敏改动了数字"检查抓到 56 条，同时被覆盖检查标成 59 条未识别区域。修复办法：两处都先去掉占位符再比对。如果没有这两道检查，这个错误会一直藏着。
2. 【事实】`tax_rules.yaml` 里不加引号的键 `ON`（安大略）被 YAML 1.1 读成布尔值，安大略因此不在税率表里，跨境计数一度是 105 而不是 41。是和 01 的已知数字（41）对不上才发现的。已全部加引号并注释。

### 7.2 代码可判定的诊断：触发次数

【事实】`run_dev.py` 第 1 节。比例的分母是 908 条事件。

| 代码 | 诊断数 | 事件 | 比例 | 行 | 说明 |
|---|---:|---:|---:|---:|---|
| `REC.INPUT.EXPORT_DUPLICATE` | 27 | 27 | 3.0% | 72 | 27 个事件合并了 72 行，与 01 P1 的 45 行重复一致 |
| `REC.TEXT.EMPTY` | 4 | 4 | 0.4% | 4 | |
| `REC.TEXT.NUMBERS_ONLY` | 6 | 6 | 0.7% | 11 | |
| `REC.TEXT.NO_NUMBER` | 1 | 1 | 0.1% | 1 | `PURCHASED TRANSPORTATION SURCHARGE --` |
| `REC.TEXT.PII_REDACTED` | 58 | 58 | 6.4% | 58 | 含人名 54、含邮箱 2，另有 2 条是误删（7.4） |
| `REC.TEXT.REDACTION_ALTERED_DIGITS` | 0 | 0 | 0 | 0 | 修复占位符问题后 |
| `REC.TEXT.INJECTION_SUSPECT` | 0 | 0 | 0 | 0 | 开发集没有指令式文本；规则用合成用例测过 |
| `REC.TEXT.DATE_AFTER_EVENT` | 6 | 6 | 0.7% | 6 | 只算带年份的日期；01b 的 15 条含不带年份的 |
| `REC.FIELD.DELTA_ZERO` | 13 | 13 | 1.4% | 13 | |
| `REC.FIELD.DELTA_NEGATIVE` | 1 | 1 | 0.1% | 1 | |
| `REC.FIELD.CROSS_BORDER` | 41 | 41 | 4.5% | 41 | 与 01 一致 |
| `NUM.PARSE.UNRECOGNIZED_REGION` | 1 | 1 | 0.1% | 1 | 只有 `CV19` |
| `NUM.PARSE.SPACE_MERGED` | 99 | 99 | 10.9% | 109 | 94 处是重量（后接 `LBS`），5 处是金额（4 种文本：`1 684.68`、`$1 277.68`、`$ 8 400.00` 两次、`$ 3 536.01`） |
| `NUM.PARSE.UNUSUAL_DECIMALS` | 1 | 1 | 0.1% | 1 | `33.744 LBS` |
| `NUM.PARSE.LEADING_DOT` | 7 | 7 | 0.8% | 7 | |
| `NUM.PARSE.MINUS_ADJACENT` | 2 | 2 | 0.2% | 2 | `-250 TONU`、`-$ 400.00` |
| `HIST.REPEAT.IDENTICAL_TEXT` | 4 | 4 | 0.4% | 6 | 与 01b 的 4 对一致 |
| `HIST.REPEAT.SAME_DELTA` | 16 | 16 | 1.8% | 22 | |
| `HIST.AMOUNT.EQUALS_EARLIER_DELTA` | 21 | 21 | 2.3% | 21 | 与 01b 3.1 的 21 对一致 |
| `HIST.AMOUNT.NEAR_105_EARLIER` | 41 | 41 | 4.5% | 43 | |
| `HIST.ORDER.SAME_MINUTE_SIBLING` | 10 | 10 | 1.1% | 10 | 与 01b 的 10 组一致（每组记在后处理的那条上） |
| `HIST.CONTEXT.EARLIER_EXPLAINED` | 15 | 15 | 1.7% | 18 | |

数字解析【事实】：529 条不同文本（含空文本）全部通过覆盖检查，没有数字字符被漏掉。

### 7.3 转人工和自动打回的比例

**只算代码能判定的部分**【事实】（`run_dev.py` 第 2 节）：

| 处置 | 事件 | 比例 | 行 |
|---|---:|---:|---:|
| `AUTO_REJECT` | 10 | 1.1% | 15 |
| `HUMAN_REVIEW` | 35 | 3.9% | 37 |
| `SPLIT_TRUSTED`（代码层面没有发现问题） | 863 | 95.0% | 901 |

- 自动打回 10 条：只有数字 6 条，空文本 4 条；没有一条被"更早有完整说明"豁免。【事实】这 10 条里有 5 条在同一票货**之后**出现了 Delta 相同、写了文字的版本（只查更早的，所以不影响判定）。这和 01b"补充说明"那 7 对的方向一致：缺说明的版本后来确实被补上了说明。
- 转人工 35 条的原因：重复列出更早的金额 21，Delta 为 0 8（另外 5 条 Delta 为 0 的已被自动打回），完全重复 4，Delta 为负 1，有文字没数字 1（同时 Delta 为 0），累计分数 1（约 1.05 倍 + 同 Delta）。

**LLM 部分会怎样改变这个数字。**`run_dev.py` 第 3 节用一个代理指标估计第 4 到 5 步会发现什么：把文本中的金额候选（有 `$` 的数字；文本没有 `$` 时取没有单位词的数字）与 Delta 比较。这是估计，不是模型输出。在 898 条会进入第 3 步的事件里【事实】：

| 代理类别 | 事件 | 比例 | 模型读对时会发生什么 |
|---|---:|---:|---|
| A Delta = 金额候选之和 | 848 | 94.4% | 对账一次通过 |
| B Delta 只等于部分数字之和 | 29 | 3.2% | 要留出一些数字不计。其中 13 条是单价（`3 DAYS AT $75 EACH`），按单价例外不打 flag；5 条是付款历史（留出的数字是 PAID / BILLED / DEDUCTED，不打 flag）；5 条是 `BALANCE DUE $Y` 不在 Delta 里，2 条是港口拖运清单只取了部分，1 条同一金额写了两次，3 条其他 |
| C Delta = 各项 + 合计 | 11 | 1.2% | `DELTA_COUNTS_TOTAL_TWICE`，单独即转人工。9 条是 01 的 P6，2 条是 `+ HST` 的记录 |
| D 任何子集都对不上 | 2 | 0.2% | 对账失败，最终 `RUN.SUBMIT.FAILED` |
| Delta 为 0 | 8 | 0.9% | 已经转人工 |

据此估计【推测】，在模型读对的前提下，第 3 到 5 步会把转人工的数量从 35 条增加到约 80 条（约 8.7%）：

- 约 1.05 倍的 21 条目前还在"拆分可信"里，加上第 3 步之后才能算的 `REVISED_SAME_CHARGES`（1 分），总分到 3，转人工：**+21**
- C 类：**+11**；D 类：**+2**
- B 类里会触发 `DOLLAR_EXCLUDED` 的约 **+10**（`BALANCE DUE` 不在 Delta 里 5、港口清单 2、重复写 1、`PURCHASE FEE $20 BALANCE DUE 20.97` 1、`$5900 RATE APPROVAL` 1）

这个估计**只会偏低**：它假设模型从不出错。模型的每一次读错，要么在对账时被抓到（重试或失败转人工），要么碰巧对上（这就是第 9 节要测的"可信但错"）；模型主动报告没把握也会加分。另一方面，`ITEM.CODE.PENDING_MEANING` 预计会落在约 62%（567 条）的记录上【推测：按 01 的 purchase(d) transportation 写法计】，目前设为 `none`；如果改成转人工，转人工比例会超过六成（见第 10 节问题 1）。

### 7.4 Presidio 脱敏的漏检率与误删率

【事实】`presidio_eval.py`，以 `person_tokens.txt` 作为标准答案（它只用于这里的评估，不进运行时）。单位是人名词出现次数；"有泄漏的记录"指至少一个人名词没有被遮住。邮箱在所有配置里都由正则处理，不计入。

| 配置 | 事件口径：漏检的人名词 | 含人名的记录中有泄漏的 | 误删的非人名词 | 不同文本口径：漏检 |
|---|---:|---:|---:|---:|
| A Presidio，原样大写 | 102 / 107（95.3%） | 51 / 54 | 0 | 50 / 55（90.9%） |
| B Presidio，`str.title()` | 102 / 107（95.3%） | 51 / 54 | 19（`PURCAHSE`、`FEE`、`BALANCE` 等） | 50 / 55 |
| B2 Presidio，按词典转大小写 | 52 / 107（48.6%） | 52 / 54 | 2（`TONU`、`ENTERD`） | 26 / 55（47.3%） |
| C Presidio（title）+ 上下文规则 | 0 / 107 | 0 / 54 | 19 | 0 / 55 |
| C2 Presidio（词典）+ 上下文规则（当前配置） | 0 / 107 | 0 / 54 | 2 | 0 / 55 |
| D 只用上下文规则 | 1 / 107（0.9%） | 1 / 54 | 0 | 1 / 55 |

安装顺利（presidio-analyzer + spaCy `en_core_web_lg`，临时环境，约 30 秒）。结论：

1. **Presidio 单独用在这份数据上不可用。**全大写文本让 spaCy 的人名识别几乎失效；简单的首字母大写不但没用，还把业务词误认成人名。"按词典转大小写"（普通英语词转小写，其余首字母大写）把漏检降到一半，但含人名的记录几乎每条都还有泄漏（漏的多是姓）。
2. 上下文规则（`APPROVED BY`、`AS PER`、`EMAILED ... TO`、`... FROM PPG`、`... OF PPG` 后面的一两个词）把漏检降到 0。**但这些规则是我读过开发集之后写的**，开发集上的 0% 是样本内结果，本质上和"用开发集的答案应付开发集"只差一步：规则是通用的英语句式，不是名单，但句式本身来自这份数据。真实的漏检率要在没见过的数据上测（测试集只测一次，或 Jake 提供的新数据）。
3. 当前配置选 C2：误删最少（2 个词，`TONU`、`ENTERD`，都不影响数字），样本内漏检 0。误删 `TONU`（truck ordered not used）会丢掉一个费用名，这是要在第 10 节讨论的代价。
4. 运行时防线是 `REC.TEXT.REDACTION_ALTERED_DIGITS`：脱敏动了数字字符的记录单独即转人工。它防的是误删金额，不防漏检；漏检在运行时发现不了，只能写成评估报告里的残余风险，或者请 PPG 提供员工名单做本地匹配（这份名单是 PPG 的参考数据，不是开发集的答案，所以不违反"不用开发集名单"的约定）。

---

## 8. 端到端走例

**第 3 步是我在会话中扮演的 LLM**：工具调用和提交是我按 SKILL.md 手写的（`walkthrough.py` 的 `PLAYS`），而且写的时候我知道检查会做什么。它们**不代表模型的实际表现**，只用来展示每一步的产出和代码的反应。第 0 到 2、4 到 7 步和第 5.5 步全部是原型代码的实际输出（`sh scratch/prototype/run.sh walkthrough.py`）。

W5 和 W9 的前一条记录也扮演了一次（W5a、W9a），这样第 5.5 步才能拿到它们的费用代码。

### 总表

| 走例 | 覆盖 | 原文（脱敏） | Delta | 第 3 步各轮 | 主要 flag | 处置 |
|---|---|---|---:|---|---|---|
| W1 | 普通附加费，无 `$`，依据为 PPG 清单 | `TAILGATE REQUIRED TO THIS STORE LOCATION AS PER LIST FROM PPG 15.75` | 15.75 | 提交 1 次通过 | `ITEM.BASIS.PPG_CLAIMED`（none） | 拆分可信 |
| W2 | 多项费用 | `INSIDE DELIVERY CHARGE - $13.00 PURCHASE TRANSPORTATION SURCHARGE - $20.00 TAILGATE DELIVERY - $15.00` | 48.00 | 提交 1 次通过 | `PENDING_MEANING`（none） | 拆分可信 |
| W3A | BALANCE DUE，Delta 不含余额；模型如实读 | `INSIDE DELIVERY $13 TAILGATE $15 PURCHASE FEE $20.12 BALANCE DUE $21.19` | 48.12 | 提交 → 回执（69.31 ≠ 48.12）→ 报告没把握 → 原样重提 → 结束 | `RUN.SUBMIT.FAILED`（alone）、`UNNAMED`、`UNCERTAINTY` | 转人工 |
| W3C | 同一条；模型静默去掉余额去凑 | 同上 | 48.12 | `reconcile` 两次试出组合 → 提交通过 | `NUM.JUDGMENT.DOLLAR_EXCLUDED`（alone） | 转人工 |
| W4 | 付款历史 | `SHORT PAID 75.27 ADJUSTED OFF 150.00 HAZMAT BILLED LINEHAUL 1 684.68 FUEL SURCHARGE 513.83 AND 50.00 PAID REPOSITIONING CHARGE ...` | 75.27 | 提交 1 次通过 | `ITEM.AMOUNT.UNNAMED`（+2）、`SPACE_MERGED`（none） | 拆分可信（分数 2） |
| W5 | 合并金额；后续记录 | `TAILGATE AND PURCHASE FEE BALANCE DUE $35`（前一条 `... FEE - $33.43 & TAILGATE - $15.00`，Delta 48.43） | 35.00 | 提交 1 次通过 | `COMBINED`（+1）、`REVISED_SAME_CHARGES`（+1） | 拆分可信（分数 2） |
| W6 | 只有数字 | `56.56` | 56.56 | 不调用模型 | `REC.TEXT.NUMBERS_ONLY` | **自动打回** |
| W7 | 费率主张；W6 的后续 | `$56.56 - ZIP 60506 TO FL IS FACTOR 124.2%` | 56.56 | 提交 1 次通过 | `RATE_CORRECTION`（none）、`SAME_DELTA`（+1） | 拆分可信（分数 1） |
| W8 | Delta 为零 | `.73 FSC` | 0.00 | 报告没把握 → 提交通过（没有计入金额） | `REC.FIELD.DELTA_ZERO`（alone）、`UNCERTAINTY` | 转人工 |
| W9 | 多次争议的后续：重列旧金额 + 约 1.05 倍余额 | `PURCHASE FEE $20 BALANCE DUE $21`（前一条 `PURCHASED TRANSPORTATION $20.00`，Delta 20） | 41.00 | 提交 1 次通过 | `EQUALS_EARLIER_DELTA`（alone）、`NEAR_105`（+2）、`UNNAMED`（+2）、`REVISED_SAME_CHARGES`（+1） | 转人工（分数 5） |
| W10 | `+ HST` 无税额、未识别区域、合计被计两次 | `MISSING $41.25 DETENTION TIME AND $15.00 CV19 FEE + HST = $63.55` | 119.80 | 查税率 → `reconcile` → 提交 1 次通过 | `DELTA_COUNTS_TOTAL_TWICE`（alone）、`OTHER`（+2）、`TAX.NO_AMOUNT`（+1）、`UNRECOGNIZED_REGION`（+1） | 转人工（分数 4） |

### 逐条要点

**W1 普通附加费。**第 2 步：`... FROM PPG [#1 15.75]`，没有 `$`。扮演的提交：`#1` = 费用金额 / 本次主张 / `ACCESSORIAL.LIFTGATE`，依据 `PPG_LIST`："AS PER LIST FROM PPG"。对账 15.75 = 15.75。同一票货更早有一条道路封闭费的记录（费用不同、没有扮演），第 5.5 步只做了文本和 Delta 层面的比对，没有发现关系。唯一的 flag 是"承运商声称有 PPG 清单"，只展示。

**W2 多项费用。**三个编号各对应一项，`#2` 用 `PENDING.PURCHASED_TRANSPORTATION`。和为 48.00。

**W3A：如实读，坚持原读法。**扮演的模型把 `BALANCE DUE $21.19` 读成"性质未说明的金额 / 本次主张"，第一次提交得到 6.3 的回执。模型重读后仍认为文本就是在要这笔钱，于是调用 `report_uncertainty`（`numbers/#4`，`delta_does_not_match_text`）并原样重提，处理立即结束。最终：`run.status = failed`，最后一次答案保留，`RUN.SUBMIT.FAILED` 的证据里带着最后的错误。审核员拿到的是"三项之和恰好等于 Delta，余额 21.19 不在 Delta 里"这一事实，而不是一个被改过的答案。草稿只列出承运商可改的一项（写明 21.19 是什么费用）。

**W3C：静默凑数。**同一条记录，扮演的模型先用 `reconcile` 试了 4 项（不对），再试 3 项（对上），然后把 `#4` 标成 NONE 提交，没有报告任何疑问。对账通过，没有回执，但 `NUM.JUDGMENT.DOLLAR_EXCLUDED`（"一个写了 `$` 的金额没有计入"）单独即转人工。这说明防线不依赖模型是否诚实。这个例子也是 D6 把 `DOLLAR_EXCLUDED` 设为 `alone` 的直接理由：如果它只算 2 分，这条会以"拆分可信"放行。

**W4 付款历史。**五个数字分别是：`#1` 75.27 未付（"SHORT PAID"）、`#2` 150.00 扣减 / 危险品（"ADJUSTED OFF 150.00 HAZMAT"）、`#3` 1684.68 已开票 / 干线运费（空格合并）、`#4` 513.83 已开票 / 燃油、`#5` 50.00 已付 / `OTHER`（"REPOSITIONING CHARGE"）。只有 `#1` 计入，75.27 = Delta。短付的是什么费用文本没说，所以 `#1` 没有费用代码，得到 `ITEM.AMOUNT.UNNAMED`（2 分），不到阈值。`#3` 是空格合并的，但没有计入，所以只有解析层面的提示。

**W5 合并金额。**`#1` $35 带两个代码（尾板、purchase fee）。前一条（W5a）是两项分列、共 48.43。第 5.5 步：35 与 48.43 不相等，也不在 1.03 到 1.07 倍之间，但两条的费用代码有交集，产生 `REVISED_SAME_CHARGES`（"同一费用改了金额再提"）。合计 2 分，拆分可信。审核员看到的提示是：这一笔无法拆分，且它是对更早一次争议的改写。

**W6 只有数字，自动打回。**第 2 步之后就判定：文本没有字母，更早没有同 Delta 的说明。不调用模型。自动通知取自目录："写明这笔金额对应的费用名称和收费原因"；合格标准："每个金额旁边都有费用名称；金额之和等于本次差额"。【事实】这条的同一票货后来确实提交了带说明的版本（W7）。

**W7 费率主张，且是 W6 的后续。**`#1` $56.56 本次主张 / `RATE_CORRECTION.ZONE_FACTOR`，`#2` 60506 参考信息（ZIP），`#3` 124.2 费率（后接 `%`）。第 5.5 步：更早的 W6 Delta 相同、文本不同，得到 `SAME_DELTA`（1 分）。W6 不算"带完整说明"，所以不会产生豁免标记。费率主张只展示：金额是差额，核实需要合同。

**W8 Delta 为零。**`.73 FSC`，扮演的模型判为"费率 / 无 / 燃油"，没有计入金额，并报告"像是燃油附加费费率"。对账无锚点（`reconciles = None`），`REC.FIELD.DELTA_ZERO` 单独即转人工。

**W9 重列旧金额。**扮演的模型照文本读：`#1` $20 purchase fee、`#2` $21 性质未说明，二者都是本次主张，41 = Delta，一次通过。模型没有看历史。第 5.5 步（用模型的计入金额）：`$20` 恰好等于更早一条的 Delta（`EQUALS_EARLIER_DELTA`，单独即转人工）；`$21` 是更早 Delta 的 1.05 倍（`NEAR_105`）；两条费用代码相同、Delta 不同（`REVISED_SAME_CHARGES`）。草稿给审核员四条可选的修改要求，例如"只列出本次新增的金额，或说明与更早争议的关系"。这就是 01b 所说"对账能通过，但分不出哪些是新的钱"的情况：对账通过了，历史检查把它拦了下来。

**W10 `+ HST`、未识别区域、合计被计两次。**第 2 步：`CV19` 是未识别区域 `?1`。扮演的模型查到安大略 HST 13%，用 `reconcile` 试算：计入 41.25 + 15.00 = 56.25，预期税 7.31，合计 63.55 与"56.25 + 7.31"一致，但 Delta 是 119.80。模型照实提交：`#3` 为合计，加一条只有税种的 line item（`TAX.HST`），`?1` 读作 19（与原文数字字符逐位比对一致）。提交检查：隐含税额 63.55 与预期 7.31 不符，但 56.25 + 63.55 = 119.80，是"合计被计两次"，**只记录、不退回**，所以一次通过。审核员得到的结论是：文本内部自洽（合计与税率一致，差 1 分钱在容差内），是发票金额把合计又算了一遍。

---

## 9. 评估方案

### 9.1 标注集

- **来源**：只从开发集抽。测试集只在最后跑一次。
- **抽样**：按"数字遮蔽后的模板"分层（01 P20：179 种模板，前 10 种覆盖 52.8% 的行），每个模板最多取 3 条；第 7.3 节代理类别 B、C、D 的事件全部收入；01b 的 85 对有序版本全部收入（用于历史关系）；再随机补到约 200 条事件。同时报告"逐条""按模板去重""按承运商宏平均"三种指标。
- **工具**：Label Studio。把第 2 步的数字表作为预标注的文本区域导入，每个区域用 per-region 的选择题标 `kind`、`status`，用多选标费用代码；line item 的原因和依据用文本区域标出；记录级标两件事："这条的拆分能否直接用"和"是否应退回承运商、为什么"。标注导出后转成 `Submission` 结构，和系统输出逐字段对比。
- **一致性**：约 50 条由两人独立标注，报告 `kind`、`status`、费用代码的 Cohen's κ。P12 的费用、P2 和 P6 的 Delta 口径等需要 Jake 确认的地方，先按"含义待确认"标，不猜。
- **时间隔离**：评估时每条记录只能看到同一票货 Event Date 严格更早的记录（与运行时相同）。01b 指出前一版的文本本身可能是之后写的，这一点控制不了，写进报告的局限。

### 9.2 指标

| 层 | 问题 | 指标 |
|---|---|---|
| 内容 1 | 要多少钱 | 计入编号集合的完全一致率；计入之和与标注一致率；历史关系 flag 的精确率和召回率（以 01b 的 85 对为测试集） |
| 内容 2 | 为了什么 | 每个数字 `kind`、`status` 的准确率和宏 F1；line item 费用代码集合的完全一致率，以及退到大类时的一致率；`OTHER` 比例（代码表覆盖率）；合并金额的召回率；同一输入跑三次的代码一致率（只测量，不进 v1 规则） |
| 内容 3 | 理由和依据 | 依据类型准确率；原因、依据片段与标注的重叠率 |
| 数字解析 | 第 2 步 | 每个数字的切分正确率（合并、拆分错误），按写法分层 |
| 动作 | 转人工 | **"拆分可信"里的错误率**（可信但错 = 静默错误率，最重要的指标）；转人工比例（覆盖率的代价）；每种 flag 的精确率（审核员评价"有用、噪音、错误"）；转人工的记录里真正有问题的比例 |
| 动作 | 自动打回 | 精确率（目标 100%：被自动打回的都应当被打回） |
| 安全 | 脱敏、注入 | 人名漏检率与误删率（7.4 的口径，在未见数据上）；对抗样本集上的注入检出率；越界输出率（schema 层面为 0，检查是否有绕过） |

### 9.3 Baseline

- **B0**：每条记录 + 一段认真写的 prompt（同样的 taxonomy、同样的模型），让模型直接输出 JSON line items（金额由模型写），没有数字表、没有工具、没有检查。
- **B1**：B0 加上同一个输出 schema 和 strict 结构，但不做任何业务检查。用来区分"schema 带来的增益"和"检查带来的增益"。

B0、B1 没有"转人工"，比较时把本方案的"拆分可信"部分与 B0 全部输出的错误率比较，同时报告本方案的转人工比例。设计原则 3 已经承认：本方案覆盖率一定比 baseline 低，卖点是"放行的部分错得更少，错的部分被暴露出来"。

### 9.4 对照实验

| 编号 | 对照 | 看什么 |
|---|---|---|
| E1 | 本方案 vs B0 vs B1 | 可信但错的比例；各内容层指标；成本和时延 |
| E2 | 有 / 没有 `reconcile` | 准确率；`DOLLAR_EXCLUDED` 中没有原文依据的比例；提交次数 |
| E3 | 有 / 没有 `find_similar_examples`，并做"留一承运商" | 尾部模板和未见承运商上的准确率 |
| E4 | 有 / 没有第 5.5 步 | 85 对版本上，重复主张被暴露的比例 |
| E5 | 护栏开 / 关：脱敏、注入检查、白名单输入 | 课程要求的"安全护栏有无对比"；用合成对抗文本测注入 |
| E6 | 先分类再抽取 vs 一步抽取 | 只有错误集中在某些类别时才做；决定 `dispute_type` 是否以内部中间产物的形式出现 |
| E7 | 给 / 不给 Reason Code | 01 P18 的假设：给了会被带偏 |
| E8 | 同一模型跑三次的一致性 | 只测量；决定以后是否加入多次运行 |
| E9 | 双模型（操作方 + 审核方） | 留作以后，方案里的位置：在第 4 到 5 步之后、第 5.5 步之前加一个只读的审核调用，输出只能是诊断 |

---

## 10. 未决问题

### 10.1 需要你我讨论的设计选择

1. **P12 的"含义待确认"代码设为 `none`（只展示）。**开发集约 62% 的记录会带它。设为转人工，转人工比例超过六成，系统就失去意义；设为 `none`，等于默认"承运商收了一项含义不明的费用"不影响拆分可信度。我倾向后者，直到 Jake 回答。
2. **"转人工"的含义。**我把它定义为"拆分结果不能直接用"，因此承运商声称 PPG 批准、按合同这类"需要核实"的提示不转人工。如果 PPG 的流程是"凡是需要核实的都要人看"，这些要改成 `alone`，转人工比例会再增加约 10% 到 17%（01 P15、P16 的计数）。
3. **累计阈值 3 和各项分数**都是拍定的。要等审核员对 flag 的评价（事件日志里的 `flag_verdicts`）积累后再调。
4. **`DOLLAR_EXCLUDED` 设为 `alone`**，预计带来约 1% 的转人工。可以接受吗？
5. **`reconcile` 要不要保留**（6.2、E2）。如果去掉，工具只剩 4 个。
6. **脱敏的上下文规则来自开发集。**选项：(a) 保留，在测试集上测一次真实漏检率；(b) 请 PPG 提供员工名单；(c) 两者都做。另外，误删 `TONU` 会丢掉一个费用名，要不要给上下文规则和 NER 加一个"费用词不脱敏"的白名单（白名单本身也来自数据，同样有样本内问题）？
7. **同一分钟的记录互相不可见。**10 组里有 2 组是同一费用写了两遍（01b 1.2），按现在的规则这类重复抓不到。可以只为"完全相同"和"同 Delta"两种检查放开同一分钟的比较（它们是同时提交的，不存在"看到未来"的问题）。是否放开？
8. **自动打回的范围。**`REC.TEXT.NO_NUMBER`（有费用名没金额，开发集 1 条）是否也自动打回？我按第四节没有加。
9. **处理顺序约束（D11）**：同一票货必须按 Event Date 顺序处理，更早记录的答案必须先存好。这和"每条记录独立处理"的原则不冲突（单条的口径不变），但要求流水线有状态。可以接受吗？
10. **严重程度和转人工作用是两套配置。**严重程度只用于展示排序；如果觉得冗余，可以只保留作用。
11. **taxonomy 的 `x12_ref` 还是空的**，要对照 X12 210 L1 / SAC 代码表填；LUMPER 与 SORTATION 是否分开、DWELL 放在仓储还是 per diem 下，要定。

### 10.2 要问 Jake 的问题（合并 01 第 3 节、01b 第 5 节修正，加上本次新增）

1. **Delta 和 Invoice Amount 的口径**：每条争议是否对应一个独立的发票版本（01b 的证据支持这一点）？两次争议之间有没有部分付款？能否拿到**每一版争议各自的状态和处理时间**（现在的 `Dispute Status` 在同一票货内从不变化）？
2. **Event Date 的来源字段**：它是服务日期、开票日期还是提交时间？争议说明提交后能否修改（有 15 条文本写到了 Event Date 之后的日期）？
3. **Delta 把合计算了两次**：`SORTATION FEE $60.00 + GST $3.00 = $63.00` 的 Delta 是 126；`... + HST = $63.55` 的 Delta 是 119.80（= 各项 + 合计）。共 11 条。这是重复开票、导出问题，还是另有口径？
4. **purchase(d) transportation surcharge / fee** 是什么费用、按什么计算、有没有 $20 的最低收费？
5. **重提的写法**：最大承运商把前一次金额原样再写一遍、再加一个约高 5% 的 `BALANCE DUE`，审核员理解为两笔钱还是同一笔钱含税重开？约 5% 是不是 GST？
6. **导出方式**：数据是否按 PK 做过连接？`Invoice Dups Removed` 的含义？能否给一份不重复的导出？
7. **字段定义**：Reason Code 由谁选？PPG 或 OTM 有没有现成的费用代码表可以对齐？
8. **税**：按起点还是终点省份判断？跨境运输怎么处理？BC、SK、MB 的 PST 和魁北克 QST 是否适用于运费？文本金额与 Delta 是否同币种（H2）？
9. **人名**：能否提供一份需要脱敏的员工名单，只用于本地匹配？（Presidio 在全大写文本上漏掉约 95% 的人名词。）
10. **评估数据**：能否提供一批其他承运商的记录，或 10 到 20 条由审核员拆好的 line items？
11. **输出给谁用**：审核员最需要哪些提示，哪些是噪音？现在是否每一条争议都由人看过？如果是，"拆分可信"的记录在流程上意味着什么（批量确认拆分）？
12. **自动打回**：PPG 是否愿意把"空文本、只有数字"的争议自动退回承运商？现在退回用什么渠道和模板？
