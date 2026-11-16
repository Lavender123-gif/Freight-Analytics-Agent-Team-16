# 任务 20 第 3 节：第四轮公开 mock 的事先写定（看任何结果之前提交）

日期：2026-11-15 晚。写这份文件时只看了第四轮 mock 的文件结构、`open_summary.json`、`validation_round_04_v2.json` 和标准答案一侧的字段（轮次、失败类型、费用名、预期建议），**没有调模型，没有算任何系统结果**。提交之后才运行。不为达标改任何东西；发现的问题只记进 `docs/autorun/pending.zh.md`（任务 20 第 3 节第 3 条）。

## 1. 数据和分组

`data/external/mock_public_r4/`：690 个事件、981 行、561 票货，全部 `active`。核对过：第三轮的 833 行在第四轮里逐字段相同；没有一票货同时含第三轮和第四轮新增的行。

| 组 | 事件 | 系统一侧 | 证据级别 |
|---|---|---|---|
| 第三轮部分 | 568（未变 517 + 重判 51） | 任务 19 存档读法 `mockR3T19routed-4079`，只重算模型之后的步骤（`pipeline.finish_batch`）；标准答案用第四轮文件（含重判） | 样本内（开发时用过） |
| 第四轮新增 | 122（148 行、90 票货） | 新跑主流程（`routed` 布局 + 注入筛查，代码在本文件提交时的版本），只跑这 148 行 | 独立检验（开发时没用过） |

## 2. 两种口径

- **口径 A（mock 答案）**：阳性 = 预期建议不是"解析通过检查"，或系统计入金额之和 ≠ `claim.current_claim_total`（同任务 19 `t19_eval.py`）。
- **口径 B（我们写下的标准）**：同任务 19：A 的预期，加上标准答案一侧的理由（费用名不在代码表、没写费用名、副本订单号相同或为空、P-40 写法），`understanding_one_amount_two_fees` 没有理由时为阴性；再加系统计入金额错（P-40 写法除外）。第四轮新增的费用名事先归类如下（依据 `config/taxonomy.yaml`）：purchased transportation、purchase fee → 在代码表（待定义的购买运输）；appointment fee、delivery appointment → 预约；fuel surcharge correction → 燃油档位更正；fuel surcharge amount → 燃油附加费；contract rate difference → 按合同补差；tax、hst → 税；daily storage → 仓储；tail lift → 尾板；overpayment refund → 贷记；**dock slot → 归预约（在代码表）**，另报一个敏感性结果：把 dock slot 当作代码表外。副本订单号相同或为空：按事件自己的各行用 `duplicates.normalize_pk` 判断。
- **送人工** = 说明的建议不是"解析通过检查"，或它所在票货自身标识的建议不是"解析通过检查"（`confusion.sent`）。

## 3. 报告的内容

1. **主矩阵**：两组分开、两种口径分开：TP、FP、FN、TN，Recall、FOR、Precision，Wilson 95% 区间。另给两组合计，仅供参考。
2. **注入**：两组（写法像客户数据的：direct、system_prompt、embedded、change_amount；故意拼错、拆字的：obfuscated、unicode_confusables），报送人工的比例。第四轮新增里没有注入事件，所以这两组全部来自第三轮部分。
3. **票货层**：系统默认新总额和 `shipment_truth_open.jsonl` 的 `new_total` 相差不超过 0.005 的比例，单说明和多说明票货分开，两组分开；标准答案没有新总额的票货单独计数。
4. **加权的"接近真实"Recall**（两种口径，在全部 690 个事件上算）：
   - **写法类别**，按下面的优先顺序取第一个命中的，正则沿用任务 16（`scratch/eval/t16_diagnosis.py` `coverage_gaps`），作用在事件第一行的原文（大写）上：
     1. 购买运输 `PURCHASE[D]? (FEE|TRANSP)`
     2. 燃油档位更正 `FSC.*SHOULD APPLY`
     3. 按合同 `PER CONTRACT`
     4. BALANCE DUE 写在最前面（BALANCE DUE 之前没有 `$`）
     5. BALANCE DUE 写在其他 `$` 之后
     6. 按天计费 `DAY\(S\)\s*@`
     7. 以点开头的小数 `(?<![\d.,])\.\d+`
     8. 空格千位数 `\b\d{1,3} \d{3}(?:\.\d\d)?\b`
     9. 连字符加金额 `-\s?\$\s?\d|\$\s?-\d`
     10. 税种词 `\b(GST|HST|PST|QST)\b`
     11. mock 特有写法（任务 16 列为真实数据里没有的任一项：`USD`、分号、数字字母混写、CREDIT、EARLIER CLAIM / PRIOR ACCESSORIAL、REBILL / REVISED、注入词、非 ASCII、括号金额、逗号小数、邮箱电话）
     12. 其他（都不命中）
   - **真实比例**：开发集 908 条说明（每条取第一行原文，同任务 16）按同样的优先顺序归类的比例。
   - **权重** = 真实比例 ÷ mock 比例（mock 比例 = 该类事件数 ÷ 690）。真实数据里有、mock 里没有的类别，报它们合计占真实数据的比例（没有被覆盖的部分），不进加权。
   - 加权 Recall = Σ 权重 × TP ÷ Σ 权重 × 阳性。同时报未加权 Recall、加权后的有效样本量（Kish：(Σw)² ÷ Σw²，在阳性事件上算）和据此算的 Wilson 95% 区间。阳性事件少于 5 个、权重却大于 1 的类别单独列出。
5. 第四轮新增部分的花费、注入筛查命中数。

## 4. 门槛

主矩阵 Recall ≥ 95%、FOR ≤ 2%（卡片 V7 上已写定的硬指标），每组、每种口径照实报达到没有；加权 Recall 也和 95% 对照报。不为达标改任何东西。

## 5. 预算

任务 19 的 mock 运行 564 条说明花 7.38 美元，每条约 0.0131；新增 122 条估 1.60 美元，加 40% 余量按每条 0.018 美元预留，合计约 2.20 美元。账本已用 115.95，停线 140。
