# freight-lineitems

## Project
CMU Intro to AI client project (Team 16) for PPG. Convert the free-text explanations carriers give for freight invoice adjustments into structured line items, with internal-consistency checks and red flags for human reviewers.

## Scope (hard boundaries)
- In scope: parsing text, normalizing charge types to a taxonomy, numeric reconciliation against Delta, consistency flags.
- Out of scope: deciding whether a charge should be paid. Never add approve, deny, or payment-recommendation logic or output fields.
- No carrier-specific rules in code (no `if carrier == ...`). Domain knowledge must apply across all carriers. Carrier phrasing lives in example data, not in code.

## Data
- Raw data: data/raw/AutoPay_Dispute_Data_20220815.xlsx. Confidential. Everything under data/ is git-ignored; never commit data or write real rows into tracked files.
- Key columns: `Descritipion` (sic, the free text), `Delta` (= Invoice Amount - Shipment Amount), `Carrier`, `SHIPMENT_GID`.
- Dev/test split lives in data/processed/. Do not read, sample, or inspect the test split during development unless explicitly instructed.
- Redact personal data (names, emails) before any text is sent to an LLM.

## Architecture
- Python 3.12 managed with uv. Plain Python plus the official Anthropic SDK. No agent frameworks (no LangChain or similar).
- Deterministic tools handle parsing, validation, and reconciliation. The LLM only interprets text and decides which tools to call.
- The agent's only output path is `submit_line_items`, which rejects any amount that does not appear in the source text.
- Agent tools are closed: the agent gets no shell, file system, or network tools.

## Conventions
- Source code in src/freight_lineitems/, tests in tests/ using pytest.
- Every agent tool has type hints and a docstring written for an LLM reader: what it does, when to use it, arguments, return value, failure modes.
- Every tool has unit tests built from dev-split examples.
- Commands: `uv run pytest`, `uv add <package>`.
- Keep changes small and explain what changed and why.

## 收尾检查
每个任务结束前都执行：
1. 卡片内容只改 `docs/status/cards.yaml`，然后运行生成脚本（`sh scratch/status/run.sh`），重新生成中英两版看板；不手改生成的 Markdown。
2. 卡片变色必须有对应级别的测试报告：浅绿要样本内证据和交付物，深绿要独立样本或人工审核证据且达到事先写定的门槛。
3. 门槛在跑检验之前写进卡片的完成标准。
4. 本任务改动了流程结构的，更新 `docs/status/flow_src/` 并用 Archify 重新生成两版流程图。
5. 最终回报里列出：哪些卡片变了、从什么变成什么、依据哪份测试报告；没有变化写明"状态文件已检查，无变化"。
