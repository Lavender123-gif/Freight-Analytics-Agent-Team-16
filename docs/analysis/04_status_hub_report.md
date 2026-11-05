# 04 看板改成可点击的进度入口，颜色以测试报告为依据：执行报告

- **任务**：`docs/tasks/cc_task_04_status_hub.md`
- **执行日期**：2026-11-03
- **编号**：`docs/tasks/` 里已有 01（`cc_task_problem_inventory.md`）、02、03，`docs/analysis/` 里有 01、01b、02、03。04 不冲突，没有改名。
- **没有做的事**：没有调用 LLM API；没有打开测试集，也没有读原始 Excel；没有跑新的检验，测试报告里的结果全部取自任务 03 的交付物、03 报告和 02；没有改 `src/`、`pyproject.toml`、`.gitignore`、`scratch/prototype/`，没有改流程图（`docs/status/pipeline_flow.*`、`flow_src/`）；没有 commit。
- **读了开发集**：收尾的脱敏反查（第 8 节）读了 `data/processed/dev.csv` 的 ID、承运商、地址列取值，用来扫描新文件。这是对文档的检查，不是对系统的检验。

## 1. 新建和改动的文件

**改动**
- `CLAUDE.md`："收尾检查"一节按任务书第 7 节替换为 5 条。第 1 条里写明了生成命令 `sh scratch/status/run.sh`，其余内容未动。
- `docs/status/project_status.zh.md`、`project_status.en.md`：改为由 `cards.yaml` 生成，文件头注明"由 cards.yaml 生成，不要手改"。

**新建：数据源与生成器**
- `docs/status/cards.yaml`：单一数据源。文件头说明全部字段；内容为 25 张卡、19 条总览连线和 meta（颜色、证据级别、规则、权重方案）。
- `scratch/status/check_report_pairs.py`：逐对比对中英测试报告的标题、表格行、条目、代码块、数字和反引号标记。
- `scratch/status/build_status.py`：生成脚本，带 `--check`；`scratch/status/templates/project_status.md.j2`：中英共用的模板；`scratch/status/run.sh`：包装 uv 命令。
- `scratch/status/migration/`：一次性迁移的记录，以后不再使用。
  - `migrate_from_md.py`：解析旧看板，与叠加文件合并，生成 `cards.yaml`
  - `overlay_task04.yaml`：任务 04 新增的字段
  - `cards_header.txt`：`cards.yaml` 的文件头
  - `check_migration.py`：核对信息有没有丢失

**新建：测试报告**（22 个，见第 4 节）
- 8 张浅绿卡：放进已有的交付物文件夹，即 `docs/deliverables/{A1-dev-test-split, A2-problem-inventory, A3-design-proposal, B01-gate, B02-number-parse, B03-auto-reject-precheck, B10-outputs, C1-diagnostics-catalog}/test_report.{zh,en}.md`。
- 3 张黄卡：新建只放测试报告的文件夹，即 `docs/deliverables/{B07-submit-checks, B08-history-checks, B09-disposition}/test_report.{zh,en}.md`。
- 已有的 README 没有改，继续作为交付物说明。

**新建：报告**
- `docs/analysis/04_status_hub_report.md`（本文件）

**行级 / 临时**（git 忽略）
- `data/interim/status_legacy/project_status.{zh,en}.md`：任务 03 看板的原样副本，供迁移核对。

**怎么用**：卡片内容只改 `docs/status/cards.yaml`，然后在仓库根目录运行 `sh scratch/status/run.sh`，它会重新生成两版看板并跑检查。只检查不写文件，用 `sh scratch/status/run.sh --check`；有不合规则或看板被手改时，以非零状态退出。

## 2. 每张卡片的颜色和证据级别

### 2.1 有变化的卡片

| 卡片 | 原来 | 现在 | 证据级别 | 依据 |
|---|---|---|---|---|
| A1 | 🟩 绿 | 🟩 浅绿 | 样本内 | [测试报告](../deliverables/A1-dev-test-split/test_report.zh.md)。通过条件（0 重叠、行数守恒）事先写在测试里，但只有写代码的一方核过，没有人工审核，不满足深绿 |
| A2 | 🟩 绿 | 🟩 浅绿 | 样本内（分析类） | [测试报告](../deliverables/A2-problem-inventory/test_report.zh.md)。复现用的是写报告时读过的同一个开发集；门槛未事先设定 |
| A3 | 🟩 绿 | 🟩 浅绿 | 样本内（分析类） | [测试报告](../deliverables/A3-design-proposal/test_report.zh.md)。期望值来自 02 原文，属复现目标，不是质量门槛；质量门槛未事先设定 |
| B01 | 🟩 绿 | 🟩 浅绿 | 样本内 | [测试报告](../deliverables/B01-gate/test_report.zh.md)。脱敏规则是读开发集后写的，0 漏检是样本内结果；质量门槛未事先设定 |
| B02 | 🟩 绿 | 🟩 浅绿 | 样本内 | [测试报告](../deliverables/B02-number-parse/test_report.zh.md)。解析规则来自开发集写法；覆盖 100% 是设计不变量，没有作为门槛事先写进卡片 |
| B03 | 🟩 绿 | 🟩 浅绿 | 样本内 | [测试报告](../deliverables/B03-auto-reject-precheck/test_report.zh.md)。精确率门槛（100%，02 §9.2）早已写定，但还没有人工确认；3 个合成用例是照规则事后写的，数量也少，不算独立样本 |
| B10 | 🟩 绿 | 🟩 浅绿 | 样本内 | [测试报告](../deliverables/B10-outputs/test_report.zh.md)。结构检查只在代码部分的输出上做；门槛未事先设定 |
| C1 | 🟩 绿 | 🟩 浅绿 | 样本内 | [测试报告](../deliverables/C1-diagnostics-catalog/test_report.zh.md)。目录一致性检查；61 种里 41 种没有触发过；门槛未事先设定 |

8 张原绿卡全部改为浅绿，没有一张满足深绿的全部条件。深绿需要两条同时满足：独立样本或人工审核的证据，以及跑检验之前写定的门槛。8 张卡都没有独立样本或人工审核的证据；除 A1、B03 外，也都没有事先写定的质量门槛。

### 2.2 颜色不变、证据级别新标注的卡片

| 卡片 | 颜色 | 证据级别 | 依据 |
|---|---|---|---|
| B07 | 🟨 黄 | 样本内 | [测试报告](../deliverables/B07-submit-checks/test_report.zh.md)：17 个合成用例是和代码一起写的；"17 个全过"只记在任务 03 的看板里，没有结果文件 |
| B08 | 🟨 黄 | 样本内 | [测试报告](../deliverables/B08-history-checks/test_report.zh.md)：预判模式的 6 种计数与 02 一致；模型后那一遍只在 2 条扮演的走例上跑过 |
| B09 | 🟨 黄 | 样本内 | [测试报告](../deliverables/B09-disposition/test_report.zh.md)：代码部分 flag 上的处置计数与 02 一致 |
| B05、B06、C2、C3 | 🟨 黄 | 无 | 没有可单列的检验结果。C2 的 9 个阈值核对已在 A3 的测试报告里 |
| B04、D1、D2、V1、V2、V3、V4、F2、F3 | 🟥 红 | 无 | 未开始 |
| F1 | ⬜ 灰 | 无 | 由我维护 |

每张非深绿卡都在看板的"升到下一档是否依赖 B04"一节写明了是否依赖 B04：
- 依赖：B05、B06、B07、B08、B09、B10、D2、V2、V3、V4、F2、F3
- 部分依赖：C1、C2、D1
- 不依赖：A1、A2、A3、B01、B02、B03、C3、V1
- 本卡即 B04：B04
- 不适用：F1

## 3. 整体进度

| 成型度 | 验证度 |
|---|---|
| **33%**（8 / 24） | **0%**（0 / 24） |

**权重方案** `[建议，待确认]`：
- 每张卡权重 1，记在 `cards.yaml` 的 `weight` 字段。
- 灰卡 F1 不进分母，所以分母 = 24。
- 黄卡不算部分分（`meta.progress.yellow_credit: 0`）。理由：黄卡做了多少没有测量，给部分分会让数字无法核对。黄卡张数（7）在看板上单列。

**公式**：
- 成型度 = Σ权重(浅绿 + 深绿) ÷ Σ权重(非灰卡)
- 验证度 = Σ权重(深绿) ÷ Σ权重(非灰卡)

**参照**：如果黄卡算 0.5 分（把 `yellow_credit` 改成 0.5 即可），成型度 = (8 + 3.5) / 24 ≈ 48%。

**两个数的区别**：成型度回答"做出来、在开发集上跑过、有交付物的有多少"；验证度回答"其中有多少经过没见过的数据或别人的核对，并且达到事先定的门槛"。现在两者差 33 个百分点，说明目前的全部进度都只有样本内证据。

## 4. 测试报告与升深绿方案

### 4.1 新增的测试报告（22 个）

每份报告的结构相同：
- 开头：证据级别
- 声称的结论
- 为什么是这个证据级别
- 检验方法
- 检验数据，写明"不是测试集"；A1 照旧写明它只读了测试集的 ID 列
- 门槛及是否事先设定
- 结果
- 局限
- 复现命令

浅绿卡另有一节"升到深绿的检验方案"；黄卡的这一节是"升到下一档（浅绿）需要什么"。

| 卡片 | 中文 | 英文 |
|---|---|---|
| A1 | [zh](../deliverables/A1-dev-test-split/test_report.zh.md) | [en](../deliverables/A1-dev-test-split/test_report.en.md) |
| A2 | [zh](../deliverables/A2-problem-inventory/test_report.zh.md) | [en](../deliverables/A2-problem-inventory/test_report.en.md) |
| A3 | [zh](../deliverables/A3-design-proposal/test_report.zh.md) | [en](../deliverables/A3-design-proposal/test_report.en.md) |
| B01 | [zh](../deliverables/B01-gate/test_report.zh.md) | [en](../deliverables/B01-gate/test_report.en.md) |
| B02 | [zh](../deliverables/B02-number-parse/test_report.zh.md) | [en](../deliverables/B02-number-parse/test_report.en.md) |
| B03 | [zh](../deliverables/B03-auto-reject-precheck/test_report.zh.md) | [en](../deliverables/B03-auto-reject-precheck/test_report.en.md) |
| B07 | [zh](../deliverables/B07-submit-checks/test_report.zh.md) | [en](../deliverables/B07-submit-checks/test_report.en.md) |
| B08 | [zh](../deliverables/B08-history-checks/test_report.zh.md) | [en](../deliverables/B08-history-checks/test_report.en.md) |
| B09 | [zh](../deliverables/B09-disposition/test_report.zh.md) | [en](../deliverables/B09-disposition/test_report.en.md) |
| B10 | [zh](../deliverables/B10-outputs/test_report.zh.md) | [en](../deliverables/B10-outputs/test_report.en.md) |
| C1 | [zh](../deliverables/C1-diagnostics-catalog/test_report.zh.md) | [en](../deliverables/C1-diagnostics-catalog/test_report.en.md) |

英文版由两个子代理按中文版翻译，我用脚本核对了两版的数字和结构（见第 8 节）。

### 4.2 浅绿卡升深绿的方案摘要

方案都写进了各卡 `cards.yaml` 的 `criteria`，也就是看板上的"完成标准"，现在写定、尚未执行。除 B03 外，门槛都标 `[建议，待确认]`，`threshold_preset` 记为 `false`；你确认之后改为 `true`，再跑检验。

**现在就能做（不依赖 B04）**

| 卡片 | 做法 | 门槛 |
|---|---|---|
| A1 | 组员独立复跑拆分检查，并审读 `data_split.py`（人工审核） | 0 个共同 shipment；行数相加等于 1347；审读无未解决问题 |
| A2 | 组员从 01、01b 正文随机抽约 20 个数字自己核对，并抽读 5 对版本对（人工审核） | 全部一致或已在对照表里；关系标签无异议 |
| A3 | 组员审读一致性脚本，手工抽查 §4.3 约 10 行和 9 个阈值（人工审核） | 0 处未解释的差异 |
| B01 | 合成注入开发集里没有的人名、邮箱，另建注入对抗样本集，与 E5 共用（独立样本） | 人名漏检 ≤ 2%；数字误改 0；对抗样本检出率门槛另定 |
| B02 | 合成数字写法集，答案已知（独立样本）；切分正确率另在 V1 上测（人工审核，V1 不依赖 B04） | 覆盖 100%；切分正确率 ≥ 98% |
| B03 | 组员或审核员逐条核对 10 条自动打回（人工审核）；再加一批合成变体（独立样本） | 精确率 100%（10 / 10），**02 §9.2 已事先设定**；合成用例全过 |
| C1 | 为 41 种没触发过的诊断手写合成提交（独立样本），组员评审说明文字（人工审核）。部分依赖 B04：`RUN.*` 类只有真实运行才会自然触发 | 61 / 61 能触发；文字 100% 来自目录；评审无阻塞性意见 |

**要等 B04**

| 卡片 | 做法 | 门槛 |
|---|---|---|
| B10 | 用真实模型输出重跑结构检查，加内容非空检查；客户方审核员看一次 Excel（这一步可以先做） | 结构全过；除自动打回外内容字段 100% 非空；审核员无阻塞性意见 |

## 5. 现成工具调查（第 3 节）

结论：没有能直接用的现成工具，用"简单脚本 + 模板"。

- **GitHub Projects / Issues**：数据不在仓库里，组员不能通过相对链接点到交付物和测试报告，也不符合"所有输出只落在仓库内"。
- **mkdocs + macros 一类静态站点工具**：要先构建站点，GitHub 不会渲染构建前的源文件；本机也没装。
- **yq、gomplate、pandoc**：本机都没装。
- **选定**：PyYAML + Jinja2。两个库都在 uv 缓存里，已验证能离线导入（6.0.3 / 3.1.6），通过 `uv run --no-project --with` 使用，不改 `pyproject.toml`。中英两版共用一个模板，界面文字放在脚本的 `LABELS` 里，所以两版结构一定相同。

## 6. Archify 来源证据的调查结论（第 6 节）

依据：读了 `~/.claude/skills/archify/` 的文档和源码（Archify 3.2.0），主要是 `renderers/shared/repository-evidence.mjs`、`schemas/common.schema.json`、`schemas/workflow.schema.json`、`bin/archify.mjs`、`references/repository-authoring.md`。关键几处由我亲自抽查过。没有改动任何流程图文件。

1. **workflow 类型支持。**
   - 字段：节点上的 `nodes[].sources`，1 到 3 条，每条 `{path, line?, end_line?, label?}`，`label` 最多 48 个字符；顶层的 `meta.repository: {url, revision, provider?, link_mode?}`。
   - 边不能带来源。
   - 生成时，`validate`、`finalize`、`deliver`、`render` 都必须加 `--repo-root <仓库顶层目录>`，否则报 `repository-evidence/root-required`。现在 `flow_src/README.md` 里的命令没有这个参数，加来源证据后要一起改。
2. **要求文件已 commit、要求具体版本、要求远程仓库地址：三项都要求。**
   - `revision` 必须是完整的 40 位 commit SHA，并且本地有这个 commit。
   - 被引用的文件按该 commit 的 git 对象读取，不读工作区；未跟踪或未提交的文件报 `repository-evidence/file-missing`。行号范围也按那个版本的文件核对。
   - 仓库必须有 `origin` 远程，并且与 `meta.repository.url` 一致；`--repo-root` 必须是 git 顶层目录。
   - 本仓库的 `origin` 是 `https://github.com/regnartsw/freight-lineitems.git`，HEAD 是 `42490b6`。但 `docs/`、`scratch/` 都没有跟踪，所以**现在只能引用已经 commit 的 `src/`、`tests/` 文件**；原型代码、交付物和测试报告都要先 commit 才能被引用。
3. **链接的形式：只能由 Archify 拼出来。**
   - `path` 必须是仓库内的相对 POSIX 路径，不能以 `/` 开头，不能有 `..`、`\`、`.git`。不能填相对于 HTML 的路径，也不能填完整 URL。
   - Archify 按 `{url}/blob/{revision}/{path}#L{line}-L{end_line}` 拼出 GitHub 链接（GitLab 用 `/-/blob/`）。
   - `link_mode: "local-only"` 只核验，不生成链接，面板里显示为纯文本。
   - 注意：Archify 只检查本地 git 对象，不检查这个 commit 是否已经 push、仓库是否公开。私有仓库或没推送的 commit，组员点开会是 404。
4. **`check --require-provenance` 仍能通过，前提是重新走 `finalize` 或 `deliver`。**
   - 这里的 provenance 指 `.delivery.json` 交付回执，不指来源证据。它检查回执是否存在、格式是否正确、最近一次交付是否成功、有没有未完成的锁，以及 HTML 的 sha256 和字节数是否与回执一致。它不重新核验来源，也不接受 `--repo-root`。
   - 带来源证据时，`deliver` 会在回执里写入一个 `evidence` 块；这个块格式不对时交付失败（`delivery/evidence-receipt-invalid`）。
   - 手改 HTML 加链接会让 sha256 校验失败，所以不能这样做。

**建议** `[建议，待确认]`：如果要给流程图节点加来源证据，先把要引用的文件 commit 并 push，再在两份 workflow JSON 里加 `meta.repository`（`revision` 写那个 commit）和 `nodes[].sources`，把 `--repo-root` 加进 `flow_src/README.md` 的命令，然后重新 `finalize`。这件事属于以后的任务。

## 7. 标了 `[建议，待确认]` 的条目

看板上中文共 53 处，英文对应 53 处 `[suggestion, to be confirmed]`。其中 44 处是任务 03 原有的，全部原样迁移，清单见 03 报告第 5 节；任务 04 新增 9 处：

1. **整体进度的权重方案**：每卡权重 1、灰卡不计、黄卡不给部分分（我）。
2. **A1 升深绿的门槛**：0 重叠、行数守恒、审读无未解决问题（我）。
3. **A2 升深绿的门槛**：抽查约 20 个数字和 5 对，全部一致或差异已列出（我）。
4. **A3 升深绿的门槛**：0 处未解释的差异（我）。
5. **B01 升深绿的门槛**：人名漏检 ≤ 2%、数字误改 0、对抗样本门槛另定（我）。
6. **B02 升深绿的门槛**：覆盖 100%、切分正确率 ≥ 98%（我）。
7. **B10 升深绿的门槛**：结构全过、内容 100% 非空、审核员无阻塞性意见（我，审核员由客户方出）。
8. **C1 升深绿的门槛**：61 / 61 能触发、文字 100% 来自目录、评审无阻塞性意见（我）。
9. **D1 是否依赖 B04**：迁移本身不依赖，接口形状等 B04 的后端（我）。

B03 的门槛（精确率 100%）出自 02 §9.2，没有标建议。测试报告里的门槛与卡片相同，没有另算。

## 8. 阻塞与需要你知道的事

1. **B07 的"17 个合成用例全过"没有结果文件**：只记在任务 03 的看板和 03 报告里。本任务不跑检验，测试报告如实写明，并给出重跑命令。
2. **流程图节点的文字和看板总览图不同**：总览图的节点文字现在用总表里的完整卡片名，例如"B04 3 agent 循环（接模型）"、"V2 Baseline B0 / B1"；以前是手写的短名。分栏和 19 条连线与旧图逐条一致，已用脚本核对。
3. **旧文字里的"见 7"**：A3、B04、B07 的部分原文写"（见 7）"，指旧版第 7 项"待决事项"。新版每节用标题而不用编号，原文按"信息不得丢失"保留未改；在新版里对应"待决事项"一节。
4. **渲染只在本地看过源码**：GitHub 上 `<a id>` 锚点能否跳转、Mermaid 的五种颜色能否渲染，要推送后才能确认。GitHub 支持 Mermaid 和 `<a id>` 锚点，但本任务没有推送，无法实测。
5. **任务 03 报告里提到的 `scratch/analysis/a4_patterns.py` 硬编码人名**：仍未处理，因为本任务不改 `scratch/analysis/`。`scratch/` 一旦 commit，这个名字会进版本库。
6. **核对结果**：
   - `sh scratch/status/run.sh --check` 全部通过：链接存在、颜色规则成立、看板与 `cards.yaml` 一致、每份测试报告开头写了证据级别。
   - 迁移核对（`check_migration.py`）：旧看板每条原文中英各 360 条，都在新看板里找到；按设计替换的只有旧颜色标准、文件头和总表表头，每个都列了理由。
   - 中英两版测试报告：`check_report_pairs.py` 比对 11 对，10 对完全一致；A3 有 1 处是正常的译法差异（中文两句各提一次"02"，英文合成一句），内容相同。看板两版的标题（228）、锚点（29）、表格行（201）数量相同。
   - 脱敏反查：扫描 35 个新建、改动的文件，对照开发集 ID、承运商、地址列的 4852 个取值、人名词表、邮箱格式和 6 位以上数字串。真实数据命中 0；仅有的几处命中是灰色的颜色值 `#333333` / `#777777`，以及 `CLAUDE.md` 原有的原始文件名日期。
   - `git diff` 只有 `CLAUDE.md`，`src/`、`scratch/prototype/`、流程图在任务期间没有被修改。
   - 这些核对的实际输出记在本次会话的回报里。
