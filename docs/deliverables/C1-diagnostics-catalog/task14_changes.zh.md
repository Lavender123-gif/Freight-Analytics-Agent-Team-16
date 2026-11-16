# 任务 14：运行时标识的增删（规则 v1.2，2026-11-15）

本目录的诊断目录（`scratch/prototype/diagnostics_catalog.yaml`）是原型的，任务 09 起已标为“待改”。本文只列任务 14 对运行时标识（`config/rules.yaml`）的改动，以 `rules.yaml` 为准；目录本身的重写和一致性检查重跑还没做，所以 C1 卡是黄。

## 删除的 14 个

| 标识 | 原级别 | 为什么删 |
|---|---|---|
| `CLAIM.DELTA.FIRST_MISMATCH`、`MATCH_AFTER_REVISION`、`MISMATCH_INSISTED`、`MISMATCH_UNRESOLVED`、`TOTAL_COUNTED_TWICE_PATTERN`、`DIFFERENCE_MATCHES_AMOUNTS` | 提示 / 送人工 | C1：Delta 是客户的 Excel 估算，运行时不再比较 |
| `REC.FIELD.DELTA_ZERO`、`DELTA_MISSING`、`DELTA_NEGATIVE` | 送人工 | 同上 |
| `REC.FIELD.CURRENCY_UNDETERMINED` | 提示 | C6：全部按 USD |
| `DUP.ROW.HAS_LATER_COPIES`、`DUP.ROW.COPY` | 提示 / 送人工 | C4：订单副本合并成一条说明，改由 `SHIP.COPY.SAME_OR_NO_PK` |
| `DUP.INVOICE.SAME_CHARGE`、`DUP.INVOICE.NOT_CHECKED` | 送人工 / 提示 | 并入票货汇总的取代规则 |

## 改级别的 2 个

| 标识 | 原 → 新 | 依据 |
|---|---|---|
| `ITEM.TAX.PRESENT` | 送人工 → 提示 | C6：税单独成行是客户要的写法 |
| `ITEM.TAX.NO_AMOUNT` | 提示 → 送人工 | C6：写了税种没写税额，总额不完整 |

## 新增的 10 个（全部送人工）

| 标识 | 触发 | 证据 | 给审核员 |
|---|---|---|---|
| `SHIP.COPY.SAME_OR_NO_PK` | 一条说明有多行，其中有 PK 为空或重复 | 行数、不同 PK 数、没有 PK 的行、重复 PK 的行 | 这几行不是“一车多个订单”能解释的副本，看是不是重复导出或重复提交 |
| `SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE` | 后一条说明的同一费用（最细一层内部代码）取代更早的行 | 被取代的行、取代它的行、另一种读法的新总额 | 默认按后一条只算一次；如果其实是两笔，用另一种读法的总额 |
| `SHIP.ROLLUP.SAME_AMOUNT_EARLIER` | 后一条的金额与更早仍计入的一行相同、代码不同 | 两行、另一种读法的新总额 | 默认相加；如果是同一笔写了两个名字，用另一种读法 |
| `SHIP.ROLLUP.RATIO_SUPERSEDED` | BALANCE DUE（或下一条说明的单个金额）是更早某个金额的 1.03 到 1.07 倍 | 两个金额、比值、另一种读法 | 默认只算后面的数 |
| `SHIP.ROLLUP.BALANCE_DUE_UNRESOLVED` | 其余 BALANCE DUE 写法，前后都有 `$` 金额 | BALANCE DUE 后的数、前面的数 | 默认取模型读法，请看原文 |
| `SHIP.ROLLUP.BALANCE_DUE_READING_DIFFERS` | 上一条第一种情况里，代码的默认和模型的读法计入的数不同 | 两边各计入哪些编号 | 代码给的是默认数，模型读法也保留 |
| `SHIP.ROLLUP.TAX_PARTLY_ORPHANED` | 一条说明只被取代一部分，它的税留着 | 留下的税、被取代的行 | 分不清税属于哪一项 |
| `SHIP.ROLLUP.RELATION_UNDECIDED` | “其他”代码且原文名称不同、没有费用名、一个金额对多个有交集的代码 | 这一行和更早的行、原因 | 代码判不了是取代还是相加，默认相加 |
| `SHIP.ROLLUP.INCOMPLETE` | 有说明没有可用读法 | 哪几条 | 默认总额没算这几条 |
| `SHIP.ROLLUP.ORDER_TIED` | 取代方向取决于 Event Date 相同时的行号顺序 | 涉及的说明 | 先后是按行号定的，请确认 |

另外 `rules.yaml → review_groups` 让内部不一致（`CLAIM.RECON.TOTAL_MISMATCH`、`ITEM.ARITH.RELATION_FAILS`、`ITEM.ARITH.QTY_RATE_NO_RESULT`）和措辞不清（`ITEM.AMOUNT.UNNAMED`、`RUN.AGENT.UNCERTAINTY_REPORTED`、`ITEM.CODE.OTHER`）两组在同一档里排在最前（C6）。
