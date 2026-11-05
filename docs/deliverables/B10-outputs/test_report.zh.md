# B10 第 7 步 输出：测试报告

- **证据级别**：样本内
- **卡片颜色**：🟩 浅绿（看板：[B10](../../status/project_status.zh.md#card-b10)）
- **整理日期**：2026-11-03（任务 04）。内容取自任务 03 的交付物，本次没有重跑任何检验。
- 交付物说明：[README.zh.md](README.zh.md)；结果文件：[results/summary.md](results/summary.md)；结构示例：[results/example_record.json](results/example_record.json)；英文版：[test_report.en.md](test_report.en.md)

## 1. 声称的结论

记录对象 JSON、追加式事件日志、Excel（records、flags 两张表）三种输出在开发集 908 条事件上生成，都能按 schema 读回；`Dispute Status` 只出现在 Excel 里（02 D7）。

## 2. 为什么是这个证据级别

检验在开发集上做，只跑了代码部分；检验和输出代码出自同一方，没有人工审核，Excel 也没有给客户看过。属"样本内"。

## 3. 检验方法

`scratch/deliverables/B10_outputs.py`（照抄 `run_dev.py` 第 5 节的导出逻辑，换了输出目录）生成三种输出，然后做 11 项结构检查：记录按 `Record` schema 读回、`record_id` 唯一、事件按 `Event` schema 读回、每条记录一个处置事件、flag 事件数等于记录上的 flag 数、Excel 两张表及行数、`Dispute Status` 不在记录 JSON 和模型输入 schema 里、只在 Excel 里。

## 4. 检验数据

开发集全量 908 条事件，只跑代码部分，**没有第 3 步**。**不是测试集**；没有读原始 Excel。

## 5. 门槛及是否事先设定

**门槛未事先设定。** 11 项检查的期望值（例如 908、374、"不出现"）是检查时按设计推出来的，没有事先写进卡片。

## 6. 结果

11 / 11 通过（`results/summary.md`）：

| 检查 | 结果 |
|---|---|
| 记录读回 / `record_id` 唯一 | 908 / 908 |
| 事件日志读回 | 2190 个事件 |
| 每条记录一个处置事件 | 908 |
| flag 事件数 = 记录上的 flag 数 | 374 = 374 |
| Excel 表 / `records` 行 / `flags` 行 | records、flags / 908 / 374 |
| `Dispute Status` 不在记录 JSON、不在模型输入 schema、只在 Excel | 是 / 是 / 是 |

记录对象各部分的填充情况：`source`、`text`、`parse`、`run`、`disposition`、`versions` 为 908；`diagnostics`、`flags` 为 273；`reject_draft` 为 37；`llm_input`、`content`、`claim` 为 **0**。

## 7. 局限

- 第 3 步（B04）没有接模型，908 条记录的 `llm_input`、`content`、`claim` 全为空。拆分内容的输出格式只在 02 第 8 节的 10 条走例里出现过，而那些走例的第 3 步是扮演的。
- 事件日志只写 `ingested`、`flag`、`disposition` 三种；另外 5 种在 schema 里定义了，但代码还不写。
- Excel 的列和格式没有经过客户（审核员）看过。

## 8. 复现命令

在仓库根目录执行：

```
sh scratch/deliverables/run.sh B10_outputs.py
```

## 9. 升到深绿的检验方案

- **独立数据或核对人**：(a) B04 跑通后的真实模型输出，这是开发本卡时没有的数据；(b) 人工审核：由客户方审核员看一次 Excel 导出。
- **做法**：(a) 用真实内容重跑 11 项检查，再加内容检查：`content`、`claim`、`llm_input` 是否非空，是否能按 schema 读回；(b) 审核员对列、提示和格式给出意见，记下来。
- **门槛**：结构检查全过；除自动打回外，100% 的记录内容字段非空；审核员没有阻塞性意见 `[建议，待确认]`。门槛要在重跑和请审核员看之前写进卡片的完成标准。
- **是否依赖 B04**：依赖。内容部分需要 B04 的真实输出；审核员看 Excel 的格式可以先做。
