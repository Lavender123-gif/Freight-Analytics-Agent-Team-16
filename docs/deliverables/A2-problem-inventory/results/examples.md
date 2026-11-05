# A2 示例：问题模式与开发集计数 / Examples: problem patterns and dev-split counts

只列短文本片段，不含 shipment 号、发票号、PK、承运商代码或人名（下列片段本身不含人名）。计数来自开发集（953 行 / 908 事件），不是测试集；对应脚本见 `comparison.md`。
Short text fragments only; no shipment, invoice or PK numbers, carrier codes or names. Counts are on the dev split (953 rows / 908 events), not the test split.

| # | 问题 / Problem | 片段 / Fragment | Delta | 开发集计数 / Dev count | 脚本 / Script |
|---|---|---|---|---|---|
| 1 | P1 导出造成的重复行 / export duplicates | `DRIVER DETENTION CHG $318.18`（同一 shipment 出现 8 次，只有 PK 不同 / 8 copies, only PK differs） | 318.18 | 纯重复行 45（4.7%）/ 45 surplus rows | `a5_repeats.py` |
| 2 | P2 后一版重复列出前一版金额 / later version re-lists the earlier amount | 前一版 `PURCHASED TRANSPORTATION $20.00` → 后一版 `PURCHASE FEE $20 BALANCE DUE $21` | 20.00 → 41.00 | “保留前一版金额并叠加约 5% 余额” 18 对 / 18 ordered pairs | `a9_version_pairs.py` |
| 3 | P6 / R6c Delta 是文本自述总额的 2 倍 / Delta = 2 × stated total | `SORTATION FEE $60.00 + GST $3.00 = $63.00` | 126.00 | 10 行，2 个承运商 / 10 rows, 2 carriers | `a7_checks.py`, `a11_r6_p3.py` |
| 4 | 补充说明（金额不变）/ elaboration, same amount | 前一版 `SHORT PAID - $ 105.00` → 后一版 `DID NOT PAY HEAT CHARGE - $100.00 PLUS TAX $5.00` | 105.00 → 105.00 | 7 对 / 7 ordered pairs | `a9_version_pairs.py` |
| 5 | P5 费率不是金额 / a rate, not an amount | `.73 FSC` | 0.00 | 只有费率的 Delta ≤ 0 行 7 / 7 rate-only rows | `a4_patterns.py`, `a7_checks.py` |

以上片段都已出现在已入库的 `docs/analysis/01_problem_inventory.md` 或 `01b_version_pairs.md` 中。
All fragments already appear in the tracked reports `docs/analysis/01_problem_inventory.md` or `01b_version_pairs.md`.
