# 抽查清单（任务 09 验收包第 3 项）

**抽样规则**（事先定、按规则抽，不是挑表现好的；随机种子 20261110，脚本 `scratch/autorun/acceptance_summary.py`）：
1. 从样本 A ∪ B2 的最终运行里，每种建议各随机抽 4 条（不足 4 条时全取）；
2. 在 A ∪ B2 里出现最多的 7 种非提示类标识，每种随机抽 1 条（不重复已抽到的）；
3. 第一批（停点一）里 2 条建议退回的记录全部放进来（用户 11-10 要求 e；其中 1 条第 1 步已经抽到）。

共 20 条。定位：用浏览器打开 `data/interim/autorun/acceptance/results.html`，在地址后加最后一列的锚点，或在页面里搜索 record_id。页面显示脱敏原文、模型每次尝试的读法、标识、首次是否不一致。

看的时候请记下：模型读法对不对（每个数字）、颜色是否合理、标识有没有误报或漏报。不需要判断该不该付。

| # | 记录 | 所在运行 | 推荐 | 决定颜色的标识 | 为什么被抽到 | 结果页锚点 |
|---|---|---|---|---|---|---|
| 1 | `dev#r243` | 样本 B2 | 解析通过检查 | — | 推荐 解析通过检查 | `results.html#20261110-184723-finB2-4b6b__dev-r243` |
| 2 | `dev#r605` | 样本 B2 | 解析通过检查 | — | 推荐 解析通过检查 | `results.html#20261110-184723-finB2-4b6b__dev-r605` |
| 3 | `dev#r177` | 样本 A | 解析通过检查 | — | 推荐 解析通过检查 | `results.html#20261110-184540-finA-d700__dev-r177` |
| 4 | `dev#r478` | 样本 A | 解析通过检查 | — | 推荐 解析通过检查 | `results.html#20261110-184540-finA-d700__dev-r478` |
| 5 | `dev#r947` | 样本 A | 建议人工审核 | RUN.AGENT.UNCERTAINTY_REPORTED | 推荐 建议人工审核 | `results.html#20261110-184540-finA-d700__dev-r947` |
| 6 | `dev#r45` | 样本 A | 建议人工审核 | DUP.ROW.COPY | 推荐 建议人工审核 | `results.html#20261110-184540-finA-d700__dev-r45` |
| 7 | `dev#r37` | 样本 A | 建议人工审核 | CLAIM.DELTA.MISMATCH_INSISTED, ITEM.TAX.PRESENT | 推荐 建议人工审核 | `results.html#20261110-184540-finA-d700__dev-r37` |
| 8 | `dev#r216` | 样本 A | 建议人工审核 | CLAIM.DELTA.MISMATCH_INSISTED, ITEM.CODE.OTHER, ITEM.TAX.PRESENT | 推荐 建议人工审核 | `results.html#20261110-184540-finA-d700__dev-r216` |
| 9 | `dev#r43` | 样本 A | 建议退回承运商 | ITEM.AMOUNT.UNNAMED, REC.TEXT.NUMBERS_ONLY | 推荐 建议退回承运商 | `results.html#20261110-184540-finA-d700__dev-r43` |
| 10 | `dev#r193` | 样本 A | 建议退回承运商 | ITEM.AMOUNT.UNNAMED | 推荐 建议退回承运商；第一批建议退回（用户要求 e） | `results.html#20261110-184540-finA-d700__dev-r193` |
| 11 | `dev#r156` | 样本 B2 | 建议退回承运商 | ITEM.AMOUNT.UNNAMED, REC.TEXT.NUMBERS_ONLY | 推荐 建议退回承运商 | `results.html#20261110-184723-finB2-4b6b__dev-r156` |
| 12 | `dev#r205` | 样本 A | 建议退回承运商 | ITEM.AMOUNT.UNNAMED | 推荐 建议退回承运商 | `results.html#20261110-184540-finA-d700__dev-r205` |
| 13 | `dev#r203` | 样本 A | 建议人工审核 | NUM.JUDGMENT.SPACE_MERGED_IN_CLAIM | 标识 ITEM.AMOUNT.UNNAMED | `results.html#20261110-184540-finA-d700__dev-r203` |
| 14 | `dev#r416` | 样本 A | 建议人工审核 | REC.FIELD.DELTA_NEGATIVE, RUN.AGENT.UNCERTAINTY_REPORTED | 标识 RUN.AGENT.UNCERTAINTY_REPORTED | `results.html#20261110-184540-finA-d700__dev-r416` |
| 15 | `dev#r54` | 样本 B2 | 建议人工审核 | CLAIM.DELTA.MISMATCH_INSISTED, ITEM.TAX.PRESENT | 标识 ITEM.TAX.PRESENT | `results.html#20261110-184723-finB2-4b6b__dev-r54` |
| 16 | `dev#r248` | 样本 B2 | 建议人工审核 | CLAIM.DELTA.MISMATCH_INSISTED, CLAIM.RECON.TOTAL_MISMATCH, DUP.INVOICE.SAME_CHARGE, ITEM.TAX.PRESENT, RUN.AGENT.UNCERTAINTY_REPORTED | 标识 CLAIM.DELTA.MISMATCH_INSISTED | `results.html#20261110-184723-finB2-4b6b__dev-r248` |
| 17 | `dev#r206` | 样本 A | 建议人工审核 | DUP.ROW.COPY | 标识 DUP.ROW.COPY | `results.html#20261110-184540-finA-d700__dev-r206` |
| 18 | `dev#r913` | 样本 A | 建议人工审核 | REC.FIELD.DELTA_ZERO | 标识 REC.FIELD.DELTA_ZERO | `results.html#20261110-184540-finA-d700__dev-r913` |
| 19 | `dev#r68` | 样本 B2 | 建议人工审核 | DUP.ROW.COPY | 标识 REC.TEXT.NUMBERS_ONLY | `results.html#20261110-184723-finB2-4b6b__dev-r68` |
| 20 | `dev#r155` | 样本 第一批 | 建议退回承运商 | ITEM.AMOUNT.UNNAMED, REC.TEXT.NUMBERS_ONLY | 第一批建议退回（用户要求 e） | `results.html#20261110-171337-stage1-1cc1__dev-r155` |
