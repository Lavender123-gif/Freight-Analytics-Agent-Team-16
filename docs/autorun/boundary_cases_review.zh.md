# 88 个边界用例逐条核对（任务 09 阶段 2 内部关口）

来源：Codex 审阅的 `agent/boundary_cases/rules_and_diagnostics.jsonl`（合成用例，不含真实数据；副本在 git 忽略的 `data/external/`）。
方法：`scratch/autorun/boundary_cases.py` 把每条用例的假设读法从原型格式转成提交 v2，交给真实的提交控制器（不调用模型）；没有读法的用例只跑确定性步骤（"模型没跑"的标识不计）。`scratch/autorun/build_boundary_review.py` 生成本表。

**结果：保留 65、修改 19、作废 4、说不清 0。** 不改 Codex 的原文件；"新期望"一列是按决定改后的期望。
保留里有 11 条是本段未实现的缺口（历史比对 9 条、P4b 1 条、R1c 相关 1 条），现结果与期望不一致，不算通过。

用例在本段发现的问题（已修，都有单元测试）：
- **BC049（bug）**：原文本身含 `[PERSON_1]` 这样的占位符时，"脱敏改动了数字"检查误报。已修：比较两边都先去掉占位符。
- **BC051（阈值）**：我曾把算式关系的容差从原型的 0.005 放宽到 0.011，没有决定支持。已改回 0.005，记入期望值和阈值改动记录。
- **BC039（规则档位）**：我把"一笔金额多个代码"定为送人工，没有决定支持；改回提示（info），与用例期望一致。

| 用例 | 目标规则 | 原期望（推荐；诊断） | 现结果（推荐；诊断） | 现结果与原期望 | 分类 | 新期望 | 理由 |
|---|---|---|---|---|---|---|---|
| BC001 | `REC.TEXT.EMPTY` | 建议退回承运商；REC.TEXT.EMPTY | 建议退回承运商；REC.TEXT.EMPTY | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC002 | `REC.TEXT.NUMBERS_ONLY` | 建议退回承运商；REC.TEXT.NUMBERS_ONLY, ITEM.AMOUNT.UNNAMED | 建议退回承运商；ITEM.AMOUNT.UNNAMED, REC.TEXT.NUMBERS_ONLY | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC003 | `REC.TEXT.NO_NUMBER` | 建议退回承运商；REC.TEXT.NO_NUMBER, ITEM.AMOUNT.MISSING, CLAIM.RECON.SUM_MISMATCH | 建议人工审核；CLAIM.DELTA.FIRST_MISMATCH, CLAIM.DELTA.MISMATCH_INSISTED, ITEM.AMOUNT.MISSING, REC.TEXT.NO_NUMBER | 不一致 | **修改** | 建议人工审核；REC.TEXT.NO_NUMBER、ITEM.AMOUNT.MISSING、CLAIM.DELTA.MISMATCH_* | 决定 3.2、第1节第4条：与 Delta 不一致交审核员判断，系统不裁决，不再直接建议退回 |
| BC004 | `REC.INPUT.EXPORT_DUPLICATE` | 解析通过检查；REC.INPUT.EXPORT_DUPLICATE | 建议人工审核；DUP.ROW.COPY | 不一致 | **修改** | 建议人工审核；第一份带 DUP.ROW.HAS_LATER_COPIES，后一份 DUP.ROW.COPY 指向第一份 | 决定 5.3、第1节第7条：副本不合并，第二份起标识 |
| BC005 | `injection.max_length` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC006 | `injection.max_length` | 建议人工审核；REC.TEXT.INJECTION_SUSPECT | 建议人工审核；REC.TEXT.INJECTION_SUSPECT | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC007 | `injection.patterns` | 建议人工审核；REC.TEXT.INJECTION_SUSPECT, REC.TEXT.NO_NUMBER | 建议人工审核；REC.TEXT.INJECTION_SUSPECT, REC.TEXT.NO_NUMBER | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC008 | `redaction.score_threshold` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC009 | `redaction.score_threshold` | 解析通过检查；REC.TEXT.PII_REDACTED | 解析通过检查；REC.TEXT.PII_REDACTED | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC010 | `REC.TEXT.REDACTION_ALTERED_DIGITS` | 建议人工审核；REC.TEXT.PII_REDACTED, REC.TEXT.REDACTION_ALTERED_DIGITS | 建议人工审核；REC.TEXT.PII_REDACTED, REC.TEXT.REDACTION_ALTERED_DIGITS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC011 | `tolerances.text_date_after_event_days` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC012 | `tolerances.text_date_after_event_days` | 解析通过检查；REC.TEXT.DATE_AFTER_EVENT | 解析通过检查；REC.TEXT.DATE_AFTER_EVENT | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC013 | `REC.FIELD.DELTA_ZERO` | 建议人工审核；REC.FIELD.DELTA_ZERO, NUM.PARSE.LEADING_DOT | 建议人工审核；NUM.PARSE.LEADING_DOT, REC.FIELD.DELTA_ZERO | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC014 | `REC.FIELD.DELTA_NEGATIVE` | 建议人工审核；REC.FIELD.DELTA_NEGATIVE, NUM.PARSE.MINUS_ADJACENT | 建议人工审核；NUM.PARSE.MINUS_ADJACENT, REC.FIELD.DELTA_NEGATIVE | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC015 | `REC.FIELD.CROSS_BORDER` | 解析通过检查；REC.FIELD.CROSS_BORDER | 解析通过检查；REC.FIELD.CROSS_BORDER, REC.FIELD.CURRENCY_UNDETERMINED | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC016 | `NUM.PARSE.UNRECOGNIZED_REGION` | 建议人工审核；NUM.PARSE.UNRECOGNIZED_REGION, ITEM.CODE.OTHER | 建议人工审核；ITEM.CODE.OTHER, NUM.PARSE.UNRECOGNIZED_REGION | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC017 | `NUM.PARSE.SPACE_MERGED` | 解析通过检查；NUM.PARSE.SPACE_MERGED | 解析通过检查；NUM.PARSE.SPACE_MERGED | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC018 | `NUM.PARSE.UNUSUAL_DECIMALS` | 解析通过检查；NUM.PARSE.UNUSUAL_DECIMALS | 解析通过检查；NUM.PARSE.UNUSUAL_DECIMALS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC019 | `NUM.PARSE.LEADING_DOT` | 解析通过检查；NUM.PARSE.LEADING_DOT | 解析通过检查；NUM.PARSE.LEADING_DOT | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC020 | `NUM.PARSE.MINUS_ADJACENT` | 建议人工审核；REC.FIELD.DELTA_NEGATIVE, NUM.PARSE.MINUS_ADJACENT | 建议人工审核；NUM.PARSE.MINUS_ADJACENT, REC.FIELD.DELTA_NEGATIVE | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC021 | `NUM.REF.UNKNOWN_ID` | 建议人工审核；NUM.REF.UNKNOWN_ID, NUM.REF.MISSING_ID | 建议人工审核；NUM.REF.MISSING_ID, NUM.REF.UNKNOWN_ID, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC022 | `NUM.REF.DUPLICATE_ID` | 建议人工审核；NUM.REF.DUPLICATE_ID | 建议人工审核；NUM.REF.DUPLICATE_ID, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC023 | `NUM.REF.MISSING_ID` | 建议人工审核；NUM.REF.MISSING_ID | 建议人工审核；NUM.REF.MISSING_ID, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC024 | `NUM.JUDGMENT.STATUS_ON_NON_MONEY` | 建议人工审核；NUM.JUDGMENT.STATUS_ON_NON_MONEY | 建议人工审核；NUM.ARITH.CUE_WITHOUT_RELATION, NUM.JUDGMENT.STATUS_ON_NON_MONEY, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC025 | `number_features.money_unit_conflicts` | 建议人工审核；NUM.JUDGMENT.UNIT_CONFLICT | 建议人工审核；ITEM.CODE.OTHER, NUM.JUDGMENT.UNIT_CONFLICT, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC026 | `number_features.money_unit_conflicts` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC027 | `NUM.JUDGMENT.EVIDENCE_NOT_FOUND` | 建议人工审核；NUM.JUDGMENT.EVIDENCE_NOT_FOUND | 建议人工审核；NUM.JUDGMENT.EVIDENCE_NOT_FOUND, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC028 | `number_features.rate_cues` | 解析通过检查；无 | 解析通过检查；NUM.JUDGMENT.DOLLAR_EXCLUDED | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC029 | `NUM.JUDGMENT.DOLLAR_EXCLUDED` | 建议人工审核；NUM.JUDGMENT.DOLLAR_EXCLUDED | 解析通过检查；NUM.JUDGMENT.DOLLAR_EXCLUDED | 不一致 | **修改** | 解析通过检查；NUM.JUDGMENT.DOLLAR_EXCLUDED 作为事实列给审核员 | 决定 3.5：带 $ 不计入必须有原文依据——没有依据时作为强制检查退回模型（RUN 层），有依据时只列给审核员。用例转换时以模型自己的 evidence_phrase 充当依据。**审计 M3 指出：这一条能对上新期望，只是因为转换脚本代填了依据；依据片段本身没有被检查是否真的表示不计入（待决 P-15）** |
| BC030 | `NUM.JUDGMENT.DOLLAR_EXCLUDED` | 建议人工审核；NUM.JUDGMENT.DOLLAR_EXCLUDED, ITEM.CODE.OTHER | 建议人工审核；ITEM.CODE.OTHER, NUM.JUDGMENT.DOLLAR_EXCLUDED | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC031 | `NUM.JUDGMENT.SPACE_MERGED_IN_CLAIM` | 建议人工审核；NUM.PARSE.SPACE_MERGED, NUM.JUDGMENT.SPACE_MERGED_IN_CLAIM, ITEM.CODE.OTHER | 建议人工审核；ITEM.CODE.OTHER, NUM.JUDGMENT.SPACE_MERGED_IN_CLAIM, NUM.PARSE.SPACE_MERGED | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC032 | `NUM.READ.UNRECOGNIZED_MISMATCH` | 建议人工审核；NUM.PARSE.UNRECOGNIZED_REGION, NUM.READ.UNRECOGNIZED_MISMATCH | 建议人工审核；ITEM.CODE.OTHER, NUM.PARSE.UNRECOGNIZED_REGION, NUM.READ.UNRECOGNIZED_MISMATCH, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC033 | `NUM.READ.UNRECOGNIZED_UNREAD` | 建议人工审核；NUM.PARSE.UNRECOGNIZED_REGION, NUM.READ.UNRECOGNIZED_UNREAD | 建议人工审核；ITEM.CODE.OTHER, NUM.PARSE.UNRECOGNIZED_REGION, NUM.READ.UNRECOGNIZED_UNREAD, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC034 | `NUM.READ.UNRECOGNIZED_NOT_JUDGED` | 建议人工审核；NUM.PARSE.UNRECOGNIZED_REGION, NUM.READ.UNRECOGNIZED_NOT_JUDGED | 建议人工审核；ITEM.CODE.OTHER, NUM.PARSE.UNRECOGNIZED_REGION | 推荐一致 | **作废** | — | 决定 3.8：去掉'这里没有数字'选项；提交 v2 的 schema 要求每个认不出的区域必须带 as_number，'读了但没判断'无法发生 |
| BC035 | `ITEM.CODE.UNKNOWN` | 建议人工审核；ITEM.CODE.UNKNOWN | 建议人工审核；ITEM.CODE.UNKNOWN, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC036 | `ITEM.CODE.OTHER_PHRASE_MISSING` | 建议人工审核；ITEM.CODE.OTHER_PHRASE_MISSING | 建议人工审核；ITEM.CODE.OTHER, ITEM.CODE.OTHER_PHRASE_MISSING, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC037 | `ITEM.CODE.OTHER` | 解析通过检查；ITEM.CODE.OTHER | 建议人工审核；ITEM.CODE.OTHER | 不一致 | **修改** | 建议人工审核；ITEM.CODE.OTHER | 决定 3.7：代码表里找不到就打标识（第1节第5条：颜色由规则算） |
| BC038 | `ITEM.CODE.PENDING_MEANING` | 解析通过检查；ITEM.CODE.PENDING_MEANING | 解析通过检查；ITEM.CODE.PENDING_MEANING | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC039 | `ITEM.CODE.COMBINED` | 解析通过检查；ITEM.CODE.COMBINED | 解析通过检查；ITEM.CODE.COMBINED | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC040 | `ITEM.REF.CLAIM_NOT_ITEMIZED` | 建议人工审核；ITEM.REF.CLAIM_NOT_ITEMIZED | 建议人工审核；ITEM.REF.CLAIM_NOT_ITEMIZED, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC041 | `ITEM.REF.INVALID` | 建议人工审核；REC.FIELD.DELTA_ZERO, ITEM.REF.INVALID | 建议人工审核；ITEM.REF.INVALID, NUM.JUDGMENT.DOLLAR_EXCLUDED, REC.FIELD.DELTA_ZERO, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC042 | `ITEM.PHRASE.NOT_FOUND` | 建议人工审核；ITEM.PHRASE.NOT_FOUND | 建议人工审核；ITEM.PHRASE.NOT_FOUND, RUN.SUBMIT.FAILED_CHECKS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC043 | `ITEM.AMOUNT.MISSING` | 建议人工审核；ITEM.AMOUNT.MISSING, ITEM.TAX.NO_RULE | 建议人工审核；ITEM.AMOUNT.MISSING, ITEM.TAX.NO_RULE, ITEM.TAX.PRESENT | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC044 | `ITEM.AMOUNT.UNNAMED` | 建议退回承运商；ITEM.AMOUNT.UNNAMED | 建议退回承运商；ITEM.AMOUNT.UNNAMED | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC045 | `ITEM.TAX.NO_AMOUNT` | 建议退回承运商；ITEM.TAX.NO_AMOUNT | 建议人工审核；ITEM.TAX.NO_AMOUNT, ITEM.TAX.PRESENT | 不一致 | **修改** | 建议人工审核；ITEM.TAX.NO_AMOUNT、ITEM.TAX.PRESENT | 决定 4.4、第1节第5条：涉及税的一律到人工 |
| BC046 | `tolerances.tax_abs` | 解析通过检查；NUM.PARSE.UNUSUAL_DECIMALS, ITEM.CODE.OTHER | 建议人工审核；ITEM.CODE.OTHER, ITEM.TAX.PRESENT, NUM.PARSE.UNUSUAL_DECIMALS | 不一致 | **修改** | 建议人工审核；ITEM.TAX.PRESENT | 决定 4.4、第1节第5条：涉及税的一律到人工 |
| BC047 | `tolerances.tax_abs` | 建议退回承运商；NUM.PARSE.UNUSUAL_DECIMALS, ITEM.CODE.OTHER, ITEM.TAX.RATE_MISMATCH | 建议人工审核；ITEM.CODE.OTHER, ITEM.TAX.PRESENT, ITEM.TAX.RATE_MISMATCH, NUM.PARSE.UNUSUAL_DECIMALS | 不一致 | **修改** | 建议人工审核；ITEM.TAX.PRESENT、ITEM.TAX.RATE_MISMATCH（只作事实） | 决定 4.4：税的问题送人工，不判承运商算错 |
| BC048 | `ITEM.TAX.NO_RULE` | 建议人工审核；ITEM.CODE.OTHER, ITEM.TAX.NO_RULE | 建议人工审核；ITEM.CODE.OTHER, ITEM.TAX.NO_RULE, ITEM.TAX.PRESENT | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC049 | `ITEM.BASIS.PPG_CLAIMED` | 解析通过检查；ITEM.BASIS.PPG_CLAIMED | 解析通过检查；ITEM.BASIS.PPG_CLAIMED | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC050 | `ITEM.BASIS.CONTRACT_CLAIMED` | 解析通过检查；ITEM.BASIS.CONTRACT_CLAIMED, ITEM.NATURE.RATE_CORRECTION | 解析通过检查；ITEM.BASIS.CONTRACT_CLAIMED, ITEM.NATURE.RATE_CORRECTION | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC051 | `ITEM.ARITH.QTY_RATE_MISMATCH` | 建议退回承运商；ITEM.ARITH.QTY_RATE_MISMATCH | 建议人工审核；ITEM.ARITH.QTY_RATE_NO_RESULT, ITEM.ARITH.RELATION_FAILS, NUM.JUDGMENT.DOLLAR_EXCLUDED | 不一致 | **修改** | 建议人工审核；ITEM.ARITH.RELATION_FAILS（原 QTY_RATE_MISMATCH）、ITEM.ARITH.QTY_RATE_NO_RESULT | 决定 3.3：算式由代码每次验算；第1节第4条：原文自身不一致交审核员判断，不直接建议退回。容差保持 0.005（本用例发现我曾放宽到 0.011，已改回） |
| BC052 | `ITEM.ARITH.OPERANDS_NOT_LINKED` | 建议人工审核；ITEM.ARITH.OPERANDS_NOT_LINKED | 解析通过检查；NUM.ARITH.CUE_WITHOUT_RELATION, NUM.JUDGMENT.DOLLAR_EXCLUDED | 不一致 | **修改** | 解析通过检查；NUM.ARITH.CUE_WITHOUT_RELATION（提示） | 决定 3.3：有算式迹象而模型没写算式关系，打一个提示（info），不改颜色 |
| BC053 | `tolerances.amount_abs` | 解析通过检查；NUM.PARSE.UNUSUAL_DECIMALS | 解析通过检查；NUM.PARSE.UNUSUAL_DECIMALS | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC054 | `tolerances.amount_abs` | 建议人工审核；NUM.PARSE.UNUSUAL_DECIMALS, CLAIM.RECON.SUM_MISMATCH | 建议人工审核；CLAIM.DELTA.FIRST_MISMATCH, CLAIM.DELTA.MISMATCH_INSISTED, NUM.PARSE.UNUSUAL_DECIMALS | 推荐一致 | **修改** | 建议人工审核；CLAIM.DELTA.FIRST_MISMATCH、CLAIM.DELTA.MISMATCH_*（原 CLAIM.RECON.SUM_MISMATCH） | 决定 3.2：不一致只回'不一致'，结果交审核员；代码名随之改 |
| BC055 | `CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE` | 建议退回承运商；CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE | 建议人工审核；CLAIM.DELTA.DIFFERENCE_MATCHES_AMOUNTS, CLAIM.DELTA.FIRST_MISMATCH, CLAIM.DELTA.MISMATCH_INSISTED, CLAIM.DELTA.TOTAL_COUNTED_TWICE_PATTERN, ITEM.TAX.PRESENT | 不一致 | **修改** | 建议人工审核；CLAIM.DELTA.MISMATCH_*，CLAIM.DELTA.TOTAL_COUNTED_TWICE_PATTERN 作解释 | 决定 3.4：合计算两次不再作门槛，只作解释；决定 3.2 不一致交审核员；含税还要到人工（决定 4.4） |
| BC056 | `CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE` | 建议退回承运商；ITEM.CODE.OTHER, CLAIM.RECON.SUM_MISMATCH, CLAIM.RECON.TOTAL_MISMATCH | 建议人工审核；CLAIM.DELTA.DIFFERENCE_MATCHES_AMOUNTS, CLAIM.DELTA.FIRST_MISMATCH, CLAIM.DELTA.MISMATCH_INSISTED, CLAIM.DELTA.TOTAL_COUNTED_TWICE_PATTERN, CLAIM.RECON.TOTAL_MISMATCH, ITEM.CODE.OTHER | 不一致 | **修改** | 建议人工审核；同上 | 决定 3.4、3.2 |
| BC057 | `CLAIM.RECON.TOTAL_MISMATCH` | 建议退回承运商；ITEM.CODE.OTHER, CLAIM.RECON.TOTAL_MISMATCH | 建议人工审核；CLAIM.RECON.TOTAL_MISMATCH, ITEM.CODE.OTHER, ITEM.TAX.PRESENT | 不一致 | **修改** | 建议人工审核；CLAIM.RECON.TOTAL_MISMATCH、ITEM.TAX.PRESENT | 决定 4.4：含税一律到人工 |
| BC058 | `CLAIM.RECON.PASSED_AFTER_RETURN` | 解析通过检查；CLAIM.RECON.PASSED_AFTER_RETURN | 建议人工审核；CLAIM.ATTEMPT.STATUS_CHANGED, CLAIM.DELTA.FIRST_MISMATCH, CLAIM.DELTA.MATCH_AFTER_REVISION | 不一致 | **修改** | 建议人工审核；CLAIM.DELTA.MATCH_AFTER_REVISION、CLAIM.ATTEMPT.STATUS_CHANGED | 决定 3.5：自动比较前后两次尝试，把改了状态的数字列给审核员；决定 3.2 第一次读法要可见 |
| BC059 | `HIST.REPEAT.IDENTICAL_TEXT` | 建议人工审核；HIST.REPEAT.IDENTICAL_TEXT, HIST.CONTEXT.EARLIER_EXPLAINED | 解析通过检查；无 | 不一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口 |
| BC060 | `HIST.REPEAT.SAME_DELTA` | 建议人工审核；HIST.REPEAT.SAME_DELTA, HIST.CONTEXT.EARLIER_EXPLAINED | 解析通过检查；无 | 不一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口 |
| BC061 | `HIST.REPEAT.SAME_AMOUNT_NEW_CODES` | 建议人工审核；HIST.REPEAT.SAME_DELTA, HIST.REPEAT.SAME_AMOUNT_NEW_CODES, HIST.CONTEXT.EARLIER_EXPLAINED | 解析通过检查；无 | 不一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口 |
| BC062 | `HIST.REPEAT.REVISED_SAME_CHARGES` | 建议人工审核；HIST.REPEAT.REVISED_SAME_CHARGES | 解析通过检查；无 | 不一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口 |
| BC063 | `HIST.AMOUNT.EQUALS_EARLIER_DELTA` | 建议人工审核；HIST.AMOUNT.EQUALS_EARLIER_DELTA | 解析通过检查；无 | 不一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口 |
| BC064 | `tolerances.near_105` | 建议人工审核；HIST.AMOUNT.NEAR_105_EARLIER | 解析通过检查；无 | 不一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口 |
| BC065 | `tolerances.near_105` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC066 | `tolerances.near_105` | 建议人工审核；HIST.AMOUNT.NEAR_105_EARLIER | 解析通过检查；无 | 不一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口 |
| BC067 | `tolerances.near_105` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC068 | `HIST.ORDER.SAME_MINUTE_SIBLING` | 解析通过检查；HIST.ORDER.SAME_MINUTE_SIBLING | 解析通过检查；无 | 推荐一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口 |
| BC069 | `HIST.INPUT.NOT_PROVIDED` | 解析通过检查；HIST.INPUT.NOT_PROVIDED | 解析通过检查；无 | 推荐一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口 |
| BC070 | `HIST.CONTEXT.EARLIER_EXPLAINED` | 建议退回承运商；REC.TEXT.NUMBERS_ONLY, HIST.REPEAT.SAME_DELTA, HIST.CONTEXT.EARLIER_EXPLAINED, ITEM.AMOUNT.UNNAMED | 建议退回承运商；REC.TEXT.NUMBERS_ONLY | 推荐一致 | **保留** | （不变） | 保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口；推荐颜色已一致 |
| BC071 | `RUN.AGENT.UNCERTAINTY_REPORTED` | 建议人工审核；RUN.AGENT.UNCERTAINTY_REPORTED, ITEM.AMOUNT.UNNAMED | 建议人工审核；RUN.AGENT.UNCERTAINTY_REPORTED | 推荐一致 | **保留** | （不变） | 用例只给了 report_uncertainty 的调用、没给读法，所以 ITEM.AMOUNT.UNNAMED 无从产生；推荐颜色一致 |
| BC072 | `retry.stop_on_unchanged_resubmission` | 建议人工审核；RUN.SUBMIT.FAILED | 建议人工审核；NUM.REF.MISSING_ID, RUN.SUBMIT.FAILED_CHECKS | 推荐一致 | **修改** | 建议人工审核；RUN.SUBMIT.FAILED_CHECKS（原 RUN.SUBMIT.FAILED） | 决定 3.2：原样重提是'坚持'，属于正常路径，不再自动结束；强制检查（缺编号）仍不通过时，次数用完显式失败 |
| BC073 | `retry.max_retries` | 建议人工审核；RUN.SUBMIT.FAILED | 建议人工审核；NUM.REF.MISSING_ID, RUN.SUBMIT.FAILED_CHECKS | 推荐一致 | **修改** | 建议人工审核；RUN.SUBMIT.FAILED_CHECKS（原 RUN.SUBMIT.FAILED） | 代码改名（第1节第6条：失败显式标出），含义不变 |
| BC074 | `agent.max_turns` | 建议人工审核；RUN.SUBMIT.NONE | 建议人工审核；RUN.SUBMIT.NONE | 一致 | **保留** | （不变） | 模型从未提交 → RUN.SUBMIT.NONE、人工；与第1节第6条一致 |
| BC075 | `agent.reconcile_max_calls` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **作废** | — | 决定 3.1：去掉试算工具 reconcile |
| BC076 | `agent.reconcile_max_calls` | 解析通过检查；RUN.TOOL.RECONCILE_OVERUSE | 解析通过检查；无 | 推荐一致 | **作废** | — | 决定 3.1：去掉试算工具 reconcile |
| BC077 | `agent.reconcile_max_calls` | 解析通过检查；RUN.TOOL.RECONCILE_OVERUSE | 解析通过检查；无 | 推荐一致 | **作废** | — | 决定 3.1：去掉试算工具 reconcile |
| BC078 | `RUN.SUBMIT.SCHEMA_INVALID` | 建议人工审核；RUN.SUBMIT.SCHEMA_INVALID | 建议人工审核；NUM.REF.MISSING_ID, RUN.SUBMIT.FAILED_CHECKS | 推荐一致 | **保留** | （不变） | RUN.SUBMIT.SCHEMA_INVALID 仍存在；本表的转换器把旧格式补全成合法提交，掩盖了这一点，改由单元测试 test_schema_invalid_submission_is_returned_then_fails_explicitly 覆盖 |
| BC079 | `reason_code_categories` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC080 | `reason_code_categories` | 解析通过检查；REC.FIELD.REASON_CODE_CONFLICT | 解析通过检查；REC.FIELD.REASON_CODE_CONFLICT | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC081 | `reason_code_categories` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC082 | `escalation.score_threshold` | 解析通过检查；ITEM.CODE.OTHER | 建议人工审核；ITEM.CODE.OTHER | 不一致 | **修改** | 建议人工审核；ITEM.CODE.OTHER | 决定 3.7（其他代码打标识）；计分阈值已由三档取代（决定日志 D-13，验收包 f 单独说明） |
| BC083 | `escalation.score_threshold` | 建议人工审核；NUM.PARSE.UNRECOGNIZED_REGION, ITEM.CODE.OTHER | 建议人工审核；ITEM.CODE.OTHER, NUM.PARSE.UNRECOGNIZED_REGION | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC084 | `recommendation.precedence` | 建议人工审核；ITEM.AMOUNT.UNNAMED, RUN.SUBMIT.FAILED | 解析通过检查；无 | 不一致 | **保留** | （不变） | 用例的工具记录是汇总数，无法回放；'先人工后退回'的顺序由 test_recommendation_order_attention_before_return 覆盖，'重试用完显式失败'由 test_repairs_exhausted_fail_explicitly 覆盖 |
| BC085 | `recommendation.clean_pass` | 解析通过检查；无 | 解析通过检查；无 | 一致 | **保留** | （不变） | 期望与决定记录一致；新框架结果一致 |
| BC086 | `ITEM.CODE.UNGROUNDED` | 建议人工审核；ITEM.CODE.UNGROUNDED | 解析通过检查；无 | 不一致 | **保留** | （不变） | 决定 3.6 的费用代码依据核对属于 P4b（应该做，不在本段），本段未实现，列为缺口 |
| BC087 | `REC.FIELD.CURRENCY_MISSING` | 建议人工审核；REC.FIELD.CURRENCY_MISSING | 解析通过检查；无 | 不一致 | **修改** | 解析通过检查；币种按国家推算为 USD 并标'推算'；只有推不出来时打 REC.FIELD.CURRENCY_UNDETERMINED | 决定 4.3：币种放在记录一级、按国家推算、标为推算 |
| BC088 | `RUN.TOOL.RECONCILE_OVERUSE+NUM.JUDGMENT.DOLLAR_EXCLUDED` | 建议人工审核；ITEM.CODE.OTHER, RUN.TOOL.RECONCILE_OVERUSE, NUM.JUDGMENT.DOLLAR_EXCLUDED | 建议人工审核；ITEM.CODE.OTHER, NUM.JUDGMENT.DOLLAR_EXCLUDED | 推荐一致 | **修改** | 建议人工审核；NUM.JUDGMENT.DOLLAR_EXCLUDED（去掉 RUN.TOOL.RECONCILE_OVERUSE） | 决定 3.1：去掉 reconcile；其余期望不变 |
