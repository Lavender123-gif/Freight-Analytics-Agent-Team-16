# 流程图源文件 / Pipeline flow source

## 现行来源（Archify）

| 文件 | 用途 |
|---|---|
| `pipeline_flow.zh.workflow.json` | 中文版源文件（Archify workflow JSON，schema v2，`meta.locale: zh-CN`） |
| `pipeline_flow.en.workflow.json` | 英文版源文件（同上，`meta.locale: en`） |
| `../pipeline_flow.zh.html`、`../pipeline_flow.en.html` | 生成物，不要直接改 |
| `../pipeline_flow.zh.delivery.json`、`../pipeline_flow.en.delivery.json` | Archify 的交付回执（记录源文件和 HTML 的 sha256），`check --require-provenance` 用它确认 HTML 来自对应源文件；随 HTML 一起重新生成，不要手改 |

**v5（任务 07，2026-11-04 决定）。**两份源文件由 `scratch/status/flow_v5_build.py` 从同一份定义生成，保证结构一致；改图时改这个脚本再运行，然后按下面的步骤重新生成 HTML。每个节点的四项说明（做什么、为什么、现状、给 Jake 的问题）放在 `docs/plan/2026-11-05_status_and_plan.zh.md` 第 2 节（英文版 `.en.md`），因为 Archify 的节点只有标题、副标题和角标。角标里的"待改"表示现有实现与 2026-11-04 决定不一致，颜色暂不动。v5 生成时的浏览器检查证据在 `data/interim/deliverables/_archify/finalize-v5-zh/`、`finalize-v5-en/`。

**中英文用两份源文件。** Archify 的 `meta.translations` 只翻译界面文字（按钮、菜单），不翻译图里的节点和标签，所以每种语言一份源文件。两份的结构必须完全一致：节点 `id`、`lane`、`col`、`type`、`yOffset`，边的 `id`、`from`、`to`、`role`、`variant`、`fromSide`、`toSide`、`route`，泳道、阶段和 `mainPath` 都相同，只有文字不同。改结构时两份一起改，以中文版为准。英文标签比中文宽，有几处英文措辞比中文短（例如 `amounts + codes`），这是为了满足 Archify 的画布宽度和可读性检查。

**颜色怎么对应卡片状态。** workflow 节点只能按 `type` 上色，所以这里用 `type` 表示看板卡片的状态，并在 `meta.legend.entries` 里把图例改写成状态说明：`backend` = 绿卡，`cloud` = 黄卡，`security` = 红卡，`external` = 不对应卡片的人（承运商、审核员）。卡片编号写在节点的 `tag` 里。卡片颜色变化时，改对应节点的 `type`，与 `docs/status/project_status.zh.md` 保持一致。

**布局。** Archify workflow 最多 6 列（`col` 0–5）。动作规则泳道的 6c、6b 和资产泳道的 rules.yaml、诊断目录各自在第 5 列用 `yOffset` 上下叠放。少数边的 `fromSide`、`toSide` 是为了满足 showcase 档"连线不交叉、不共用通道"的检查而指定的；改动节点位置后，这些方向可能需要重新调整，以 `validate` 的诊断为准。

### Archify 版本与安装

- 版本：**Archify 3.2.0**（stable 渠道，GitHub release `v3.2.0`，2026-10-19 发布，标记为 Latest、非预发布）。旧图也是 3.2.0 生成的。
- 来源：官方仓库 `tt-a1i/archify` 的 release 附件 `archify.zip`，sha256 `70e210265c59f24dcbdf2a502ff671104b5454e7ee7d3554aecd86bad32384f5`（与 release 页面公布的值一致）。
- 安装位置：用户级 `~/.claude/skills/archify/`，不在仓库里，没有改 `pyproject.toml`、`.gitignore`。需要 Node（本机 v26.8.2）。Archify 本身零依赖，不需要 `npm install`。
- 安装方式（任务 03 实际执行的命令）：
  ```
  gh release download v3.2.0 -R tt-a1i/archify -p archify.zip
  echo "70e210265c59f24dcbdf2a502ff671104b5454e7ee7d3554aecd86bad32384f5  archify.zip" | shasum -a 256 -c
  unzip -q archify.zip -d x && mkdir -p ~/.claude/skills && mv x/archify ~/.claude/skills/archify
  node ~/.claude/skills/archify/bin/archify.mjs doctor
  ```
- Archify 默认会联网查一次有没有新版本（只读、不自动更新）。下面的命令都设了 `ARCHIFY_UPDATE_CHECK_DISABLED=1` 关掉这一项。

### 怎么改、怎么重新生成

1. 改 `pipeline_flow.zh.workflow.json`，再把同样的结构改动同步到 `pipeline_flow.en.workflow.json`。
2. 在仓库根目录运行（`A` 是 Archify 的入口）：
   ```
   export ARCHIFY_UPDATE_CHECK_DISABLED=1
   A=~/.claude/skills/archify/bin/archify.mjs
   for l in zh en; do
     node $A validate workflow docs/status/flow_src/pipeline_flow.$l.workflow.json --quality showcase
     node $A finalize workflow docs/status/flow_src/pipeline_flow.$l.workflow.json docs/status/pipeline_flow.$l.html \
       --quality showcase --out-dir data/interim/deliverables/_archify/finalize-$l
   done
   ```
   `finalize` 依次跑 validate、deliver、严格 check、真实浏览器 browser-check，任何一步不过都以非零退出。浏览器检查的证据写到 git 忽略的 `data/interim/`；HTML 和交付回执写到 `docs/status/`。
3. 检查和截图：
   ```
   for l in zh en; do
     node $A check docs/status/pipeline_flow.$l.html --require-provenance
     node $A visual-check docs/status/pipeline_flow.$l.html --summary --require-provenance \
       --out-dir data/interim/deliverables/_archify/visual-$l
   done
   ```
   `visual-check` 只截首屏；它报告的 `visualReview: pending` 表示还需要人眼看。完整高度的截图可以用浏览器无头模式另截，确认标签没有压住节点。

### 已被取代的旧来源

`flow.yaml` 和 `build.py` 是任务 03 第一轮在 Archify 不可用时写的 YAML + Python 生成器。它们**已被上面的 Archify 源文件取代，不再作为来源**，也不要再运行 `build.py`（它会覆盖 Archify 生成的 HTML）。保留它们只作为历史记录；两者的节点、边和 15 处改动已全部迁移到 Archify 源文件里。

---

## Current source (Archify)

- `pipeline_flow.zh.workflow.json` and `pipeline_flow.en.workflow.json` are Archify workflow JSON (schema v2) sources, one per language. Archify's `meta.translations` covers only viewer UI strings, not diagram content, hence two files. Their structure (node ids, lanes, columns, types, offsets, edge ids, endpoints, roles, sides, routes, phases, main path) must stay identical; only text differs. The Chinese file is authoritative.
- Node `type` encodes the status-board colour, relabelled in `meta.legend.entries`: `backend` = green card, `cloud` = yellow, `security` = red, `external` = people with no card. The card ID is the node `tag`.
- Archify **3.2.0** (stable, GitHub release `v3.2.0`, asset `archify.zip`, sha256 `70e21026…84f5`, verified), installed at user level in `~/.claude/skills/archify/` (not in the repo; `pyproject.toml` and `.gitignore` untouched). Requires Node.
- Regenerate with `validate` then `finalize --quality showcase` for both languages, then `check --require-provenance` and `visual-check` (commands above). The `*.delivery.json` receipts next to the HTML are rewritten with it.
- **v5 (task 07, 2026-11-04 decisions):** both sources are generated from one definition by `scratch/status/flow_v5_build.py`; edit that script, run it, then regenerate the HTML. The four-part notes for each node (what, why, status, Jake questions) live in section 2 of `docs/plan/2026-11-05_status_and_plan.en.md`, because Archify nodes only carry a label, sublabel and tag. A "to revise" tag means the current code conflicts with the 2026-11-04 decisions; colours are unchanged for now.
- `flow.yaml` and `build.py` are **superseded** and no longer a source; kept for history only. Do not run `build.py`: it would overwrite the Archify output.
