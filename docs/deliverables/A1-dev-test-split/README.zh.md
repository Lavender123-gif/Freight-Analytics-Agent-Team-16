# A1 开发集 / 测试集拆分

## 这一块做什么
把原始争议数据按 shipment 拆成开发集和测试集，保证同一票货的所有行只在一边。在每个至少有 4 个 shipment 的承运商内，按 70/30 随机抽 shipment 进测试集（种子 16）；不足 4 个 shipment 的小承运商整个放进开发集。测试集在开发期间不打开，只在最后终测（V4）跑一次。

## 输入和输出
- 输入：`data/raw/AutoPay_Dispute_Data_20220815.xlsx`（1347 行，机密，git 忽略）
- 输出：`data/processed/dev.csv`（953 行）、`data/processed/test.csv`（394 行），均 git 忽略
- 代码：`src/freight_lineitems/data_split.py`；测试：`tests/test_data_split.py`（commit 42490b6）

## 一条命令复现
```
uv run python scratch/deliverables/A1_split_check.py
```
它运行现有的 `tests/test_data_split.py`，再统计两边的行数和 shipment 数。结果写到 `results/summary.md`。拆分本身由 `uv run python -m freight_lineitems.data_split` 生成，本交付物没有重新拆分。

## 检验数据
开发集全量（953 行、813 个 shipment）。**"不打开测试集"规则在本卡有一个经批准的例外**：重叠检查和行数检查必须同时看两边，所以 `test.csv` 只用 `usecols=["SHIPMENT_GID"]` 读这一列，得到行数和 shipment 数（与现有测试的读法相同）。没有读测试集的任何其他列，交付物里不出现任何 ID，只有计数和通过与否。原因：不看测试集的 ID，就无法证明两边没有重叠。

## 结果
8 项检查全部通过（`results/summary.md`）：
- 现有 5 个测试通过（3 个合成用例，2 个读 ID 列）
- 两边共有的 shipment：0
- 行数：953 + 394 = 1347，等于原始行数
- 开发集 813 个 shipment，测试集 343 个；测试集占 shipment 的 29.7%
- 开发集内每个 shipment 只有一个承运商
- 开发集按承运商排名的分布见 summary（承运商代码不列出）

## 局限
- 最大承运商在开发集占 582 / 953 行，测试集结构与之类似：在测试集上的结果主要反映最大承运商（01 P20）。
- 不足 4 个 shipment 的承运商全部在开发集，测试集测不到这些承运商的写法。
- 测试集行数是通过 ID 列计数得到的；测试集的内容没有被检查，也不应在开发期间检查。
