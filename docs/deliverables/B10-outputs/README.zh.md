# B10 第 7 步：输出

## 这一块做什么
把每条争议的处理结果写成三种输出（02 §2.5、D7）：
1. **记录对象 JSON**（每行一条 `Record`）：来源、脱敏文本、数字表、模型输入、运行信息、拆分内容、主张汇总、诊断、flag、处置、打回草稿、版本
2. **追加式事件日志**（每行一个 `Event`）：读入、flag、处置等事件；审核员决定、承运商重提等事件类型已在 schema 里定义
3. **Excel 导出**（两张表）：`records`（每条事件一行）和 `flags`（每个 flag 一行）

`Dispute Status` 不进记录对象，也不进模型输入，只在导出 Excel 时按记录关联回去（02 D7）。

## 输入和输出
- 输入：第 0-6 步产生的 `Record`
- 输出：`records.jsonl`、`events.jsonl`、`export.xlsx`，全部写到 git 忽略的 `data/interim/deliverables/B10/`
- 代码：`scratch/prototype/schemas.py` 的 `Record`、`Event`，`run_dev.py` 第 5 节的导出逻辑（原型，未改动；交付物脚本照抄这段逻辑，换了输出目录）

## 一条命令复现
```
sh scratch/deliverables/run.sh B10_outputs.py
```
结果写到 `results/summary.md`；一条记录对象的结构示例（标识字段已隐去）在 `results/example_record.json`。

## 检验数据
开发集全量：908 条事件。不是测试集。只跑代码能做的部分，**没有第 3 步**。

## 结果
11 项检查 **全部通过**：
- 908 条记录对象全部能按 schema 重新读回，`record_id` 唯一
- 事件日志 2190 个事件全部能按 schema 读回；每条记录正好一个处置事件；flag 事件数 = 记录上的 flag 数（374）
- Excel 有 `records`（908 行）和 `flags`（374 行）两张表
- `Dispute Status` 不出现在记录 JSON 和模型输入 schema 里，只出现在 Excel

## 局限
- 因为第 3 步（B04）还没接模型，908 条记录的 `llm_input`、`content`、`claim` 全部为空。拆分内容的输出格式只在 02 第 8 节的 10 条走例里出现过，而那些走例的第 3 步是扮演的。
- 事件日志现在只写 `ingested`、`flag`、`disposition` 三种；`diagnostic`、`auto_reject_sent`、`reject_draft_created`、`reviewer_decision`、`carrier_resubmission_linked` 在 schema 里定义了，但代码还不写。
- Excel 的列和格式没有经过客户（审核员）看过。
