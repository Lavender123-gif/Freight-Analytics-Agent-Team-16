# A1 开发集 / 测试集拆分：测试报告

- **证据级别**：样本内
- **卡片颜色**：🟩 浅绿（看板：[A1](../../status/project_status.zh.md#card-a1)）
- **整理日期**：2026-11-03（任务 04）。内容取自任务 03 的交付物，本次没有重跑任何检验。
- 交付物说明：[README.zh.md](README.zh.md)；结果文件：[results/summary.md](results/summary.md)；英文版：[test_report.en.md](test_report.en.md)

## 1. 声称的结论

原始数据按 shipment 拆成开发集和测试集：两边没有共同的 shipment，行数相加等于原始行数，测试集在开发期间没有被打开（只读过 ID 列计数）。

## 2. 为什么是这个证据级别

检验覆盖了全部 shipment ID，不是抽样；但检验脚本和拆分代码出自同一方，没有写代码以外的人核对过，也没有在独立数据上检验。按看板的定义属于"样本内"，不满足深绿的"独立样本或人工审核"。

## 3. 检验方法

- 运行现有测试 `tests/test_data_split.py`（5 个：3 个合成用例，2 个读 ID 列）。
- `scratch/deliverables/A1_split_check.py` 的 8 项检查：pytest 结果、开发集行数和 shipment 数、测试集行数和 shipment 数、两边共有的 shipment 数、行数守恒、开发集内每个 shipment 只有一个承运商。

## 4. 检验数据

- 开发集全量：`data/processed/dev.csv`，953 行、813 个 shipment。
- **测试集例外（经批准，照旧写明）**：重叠检查和行数检查必须同时看两边，所以 `test.csv` 只用 `usecols=["SHIPMENT_GID"]` 读这一列，得到行数和 shipment 数，与现有测试的读法相同。没有读测试集的任何其他列；结果里只有计数和通过与否，没有 ID。
- 没有读原始 Excel。

## 5. 门槛及是否事先设定

| 门槛 | 是否事先设定 |
|---|---|
| 两边共有的 shipment = 0；行数相加 = 1347 | 是：写在 `tests/test_data_split.py`（commit 42490b6）和 `CLAUDE.md` 的 Data 节里，早于任务 03 的复跑 |
| 测试集占 shipment 的比例约 30% | 是：拆分设计（大承运商内 70/30）；这是描述值，不是通过条件 |

这些门槛虽然事先写定，但证据只是样本内的（见第 2 节），所以不能用来标深绿。

## 6. 结果

8 / 8 通过（`results/summary.md`）：

| 检查 | 结果 |
|---|---|
| pytest `tests/test_data_split.py` | 5 通过，0 失败 |
| 开发集行数 / shipment 数 | 953 / 813 |
| 测试集行数 / shipment 数 | 394 / 343 |
| 两边共有的 shipment | 0 |
| 行数相加 | 953 + 394 = 1347 |
| 开发集内有多于一个承运商的 shipment | 0 |

测试集占 shipment 的 29.7%。

## 7. 局限

- 最大承运商在开发集占 582 / 953 行，测试集结构类似：测试集上的结果主要反映最大承运商（01 P20）。
- 不足 4 个 shipment 的承运商全部在开发集，测试集测不到这些承运商的写法。
- 测试集只通过 ID 列计数；测试集的内容没有、也不应在开发期间检查。

## 8. 复现命令

在仓库根目录执行：

```
uv run python scratch/deliverables/A1_split_check.py
```

## 9. 升到深绿的检验方案

- **独立数据或核对人**：由写代码以外的组员核对（人工审核）。
- **做法**：组员在自己的环境里独立运行 `A1_split_check.py` 和 `uv run pytest tests/test_data_split.py`，并审读 `src/freight_lineitems/data_split.py`：分组键是 shipment、分层按承运商、小承运商规则、种子固定。审读意见写进本报告。
- **门槛**：0 个共同 shipment；行数相加等于 1347；审读没有未解决的问题 `[建议，待确认]`。门槛要在组员开始核对之前写进卡片的完成标准。
- **是否依赖 B04**：不依赖，现在就能做。
