# C1 diagnostics catalog — examples

Five entries: a finding becomes a diagnostic with a fixed reviewer text and, where the carrier can fix it, a fixed request.

| code | trigger | handling | escalation role | to reviewer | to carrier |
|---|---|---|---|---|---|
| `REC.TEXT.NUMBERS_ONLY` | 文本去掉数字、日期、标点后没有任何字母 | 只记录 | alone | 金额没有名称；若同一票货更早有同 Delta 的完整说明，参照该记录 | 写明这笔金额对应的费用名称和收费原因 |
| `NUM.JUDGMENT.DOLLAR_EXCLUDED` | 带 $ 的数字被判为非金额 kind，或金额 kind 但 status 为 NONE；判为 RATE 且有单价线索（@、AT、EACH、PER、A DAY，见 rules.yaml）的不算 | 只记录 | alone | 一个写了 $ 的金额没有计入本次主张；核对这个排除是否合理（可能是为了凑 Delta） | 无 |
| `CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE` | 文本写了合计（a + b = c），Delta = 各项 + 合计（即合计被算了两次；a + b = c 时 Delta = 2c 是其特例） | 只记录 | alone | 发票金额可能把同一组费用计了两次；拆分本身按文本给出 | 发票金额只计一次合计 |
| `HIST.AMOUNT.EQUALS_EARLIER_DELTA` | 本次计入的某个金额等于更早某条记录的 Delta，而本次 Delta 与那条不同 | 只记录 | alone | 本次文本重复列出了更早争议的金额，可能同一笔钱主张了两次 | 只列出本次新增的金额，或说明与更早争议的关系 |
| `CLAIM.RECON.SUM_MISMATCH` | 计入状态的非合计金额之和（加上推算税额）≠ Delta，且不属于下面的数据型模式 | 退回 | 不生成 flag | 重试用完后见 RUN.SUBMIT.FAILED | 列出的金额之和要等于本次差额 |
