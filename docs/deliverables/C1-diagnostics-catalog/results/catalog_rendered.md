# Diagnostics catalog (rendered by scratch/prototype/render_catalog.py)

#### 记录（REC）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `REC.INPUT.EXPORT_DUPLICATE` | 多行在 (shipment, Event Date, 文本, Invoice Amount, Delta) 上完全相同，被合并为一条 | {n_rows, source_rows, pks} | 1 | 只记录 | info / none | 无需处理；统计时按合并后的一条计 | 无 | 无 |
| `REC.TEXT.EMPTY` | 说明文本为空或只有空白 | {text_length} | 1 | 只记录 | high / alone | 没有任何可拆分内容 | 补充说明：写明每一项费用的名称和金额，以及收费原因 | 文本至少包含一个费用名称和一个金额，且列出的金额之和等于本次差额 |
| `REC.TEXT.NUMBERS_ONLY` | 文本去掉数字、日期、标点后没有任何字母 | {text, numbers} | 2 | 只记录 | high / alone | 金额没有名称；若同一票货更早有同 Delta 的完整说明，参照该记录 | 写明这笔金额对应的费用名称和收费原因 | 每个金额旁边都有费用名称；金额之和等于本次差额 |
| `REC.TEXT.NO_NUMBER` | 文本有文字但没有任何数字（如 "PURCHASED TRANSPORTATION SURCHARGE --"） | {text} | 2 | 只记录 | high / alone | 有费用名称没有金额，无法对账 | 写明该项费用的金额 | 每个费用名称都有对应金额，金额之和等于本次差额 |
| `REC.TEXT.INJECTION_SUSPECT` | 文本命中 rules.yaml 中的指令式模式，或含不可打印字符、超长 | {patterns_hit, length} | 1 | 只记录 | critical / alone | 文本可能试图影响自动处理；人工阅读原文 | 无 | 无 |
| `REC.TEXT.PII_REDACTED` | 脱敏替换了人名或邮箱 | {n_person, n_email}（不含原值） | 1 | 只记录 | info / none | 无需处理；导出时可在本地还原 | 无 | 无 |
| `REC.TEXT.REDACTION_ALTERED_DIGITS` | 脱敏前后文本的数字字符序列不同（脱敏误删了数字） | {digits_before_count, digits_after_count} | 1 | 只记录 | critical / alone | 脱敏影响了金额，拆分结果不可信 | 无 | 无 |
| `REC.TEXT.DATE_AFTER_EVENT` | 文本中带年份的日期晚于 Event Date 超过 1 天 | {latest_text_date, event_date, days_after} | 2 | 只记录 | info / none | 文本可能在 Event Date 之后写成或改过；历史比对的时间顺序要谨慎看待 | 无 | 无 |
| `REC.FIELD.DELTA_ZERO` | Delta 为 0 | {delta} | 1 | 只记录 | high / alone | 没有对账锚点，拆分无法用 Delta 验证；文本可能是费率、批准额或结案说明 | 无 | 无 |
| `REC.FIELD.DELTA_NEGATIVE` | Delta 小于 0（承运商开票低于计划金额） | {delta} | 1 | 只记录 | high / alone | 这不是多收，按文本核对承运商在说什么 | 无 | 无 |
| `REC.FIELD.CROSS_BORDER` | 起点和终点国家不同 | {origin_country, destination_country} | 1 | 只记录 | info / none | 税的适用规则可能不同（零税率等，待确认） | 无 | 无 |
| `REC.FIELD.REASON_CODE_CONFLICT` | Reason Code 映射到一个具体类别（rules.yaml 映射表），模型给出的费用代码也属于具体类别，且两者不同 | {reason_code, reason_category, model_categories} | 6a | 只记录 | low / none | 结构化编码和文本内容不一致；以文本为准，编码问题用于统计 | 无 | 无 |

#### 数字（NUM）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `NUM.PARSE.UNRECOGNIZED_REGION` | 有数字字符没有被数字或日期规则认领（如 "CV19"） | {region_id, raw, span} | 2 | 只记录 | low / score +1 | 该处由模型解读，解读值已与原文数字字符精确比对 | 无 | 无 |
| `NUM.PARSE.SPACE_MERGED` | 数字由空格分隔的数字组合并而成（"1 684.68"） | {id, raw, value} | 2 | 只记录 | info / none | 合并是规则推断，可能本应是两个数 | 无 | 无 |
| `NUM.PARSE.UNUSUAL_DECIMALS` | 小数位不是 0、1、2（"33.744 LBS"） | {id, raw, decimals} | 2 | 只记录 | info / none | 点可能是千分位 | 无 | 无 |
| `NUM.PARSE.LEADING_DOT` | 以点开头的小数（".73"） | {id, raw} | 2 | 只记录 | info / none | 常见于费率 | 无 | 无 |
| `NUM.PARSE.MINUS_ADJACENT` | 数字或 $ 紧贴一个减号（"-250"、"-$ 400.00"） | {id, raw} | 2 | 只记录 | info / none | 减号可能是负号，也可能是分隔符 | 无 | 无 |
| `NUM.REF.UNKNOWN_ID` | 提交中引用了编号表里没有的编号 | {given, valid_ids} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.REF.DUPLICATE_ID` | 同一编号被判断了不止一次 | {id, count} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.REF.MISSING_ID` | 编号表中有编号没有被判断 | {missing_ids} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.JUDGMENT.STATUS_ON_NON_MONEY` | kind 为 RATE、QUANTITY、REFERENCE 却给了 NONE 以外的 status | {id, kind, status} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.JUDGMENT.UNIT_CONFLICT` | 判为金额类 kind 的数字紧跟重量、百分比、天数等单位词 | {id, kind, unit_hint} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.JUDGMENT.EVIDENCE_NOT_FOUND` | evidence_phrase 在脱敏原文中找不到（精确匹配和容忍空格、大小写的匹配都失败） | {id, phrase} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.JUDGMENT.DOLLAR_EXCLUDED` | 带 $ 的数字被判为非金额 kind，或金额 kind 但 status 为 NONE；判为 RATE 且有单价线索（@、AT、EACH、PER、A DAY，见 rules.yaml）的不算 | {id, raw, kind, status} | 4-5 | 只记录 | high / alone | 一个写了 $ 的金额没有计入本次主张；核对这个排除是否合理（可能是为了凑 Delta） | 无 | 无 |
| `NUM.JUDGMENT.SPACE_MERGED_IN_CLAIM` | 由空格合并出来的数字被计入本次主张 | {id, raw, value} | 4-5 | 只记录 | medium / score +2 | 计入的金额来自推断性的合并，核对原文 | 金额不要用空格分隔千位 | 金额写成连续数字（如 8400.00） |
| `NUM.READ.UNRECOGNIZED_MISMATCH` | 模型对未识别区域给出的值，去掉非数字字符后与原文该区域的数字字符不相等 | {region_id, raw_digits, given_digits} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `NUM.READ.UNRECOGNIZED_UNREAD` | 有未识别区域没有给出解读 | {region_ids} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |

#### line item（ITEM）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `ITEM.CODE.UNKNOWN` | 费用代码不在 taxonomy 中 | {path, code} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.CODE.OTHER_PHRASE_MISSING` | 使用 OTHER 但没有 other_phrase，或 other_phrase 不在原文中 | {path, other_phrase} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.CODE.OTHER` | 费用代码为 OTHER | {path, other_phrase} | 4-5 | 只记录 | medium / score +2 | 费用不在代码表中，人工确认名称；同时是扩充代码表的候选 | 使用标准费用名称 | 费用名称属于 PPG 认可的费用清单 |
| `ITEM.CODE.PENDING_MEANING` | 费用代码属于 PENDING 类（purchase(d) transportation） | {path, code} | 4-5 | 只记录 | info / none | 这项费用的含义和计费方式尚未确认，拆分只能说明"承运商收了这一项" | 无 | 无 |
| `ITEM.CODE.COMBINED` | 一个金额对应多个费用代码 | {path, codes, amount} | 4-5 | 只记录 | low / score +1 | 金额无法拆到各项；不要自行按惯例拆分 | 每项费用分别列出金额 | 每个费用名称各有一个金额，金额之和等于本次差额 |
| `ITEM.REF.CLAIM_NOT_ITEMIZED` | status 为 CLAIMED 或 UNPAID 的非合计金额没有被任何 line item 引用 | {ids} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.REF.INVALID` | line item 引用了不存在的编号、非金额编号、非计入状态的编号，或同一编号被多个 line item 引用 | {path, amount_ref, reason} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.PHRASE.NOT_FOUND` | carrier_stated_reason、carrier_stated_basis 或 other_phrase 在原文中找不到 | {path, field, phrase} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
| `ITEM.AMOUNT.MISSING` | 一个非税的费用被提到但没有金额（amount_ref 为空） | {path, codes} | 4-5 | 只记录 | high / alone | 有费用名没有金额，这一项无法对账 | 写明该项费用的金额 | 每个费用名称都有金额 |
| `ITEM.AMOUNT.UNNAMED` | 计入本次主张的金额没有任何费用代码 | {path, amount_ref, amount} | 4-5 | 只记录 | medium / score +2 | 这笔钱没有写明是什么费用；不要按 Reason Code 或惯例补名称 | 写明这笔金额对应的费用名称 | 每个金额旁边都有费用名称 |
| `ITEM.TAX.NO_AMOUNT` | 文本提到税（"+ HST"）但没有写税额；代码按 Delta 与其他金额之差算出隐含税额 | {path, implied_tax, expected_tax, province} | 4-5 | 只记录 | low / score +1 | 税额是代码推算的，不是原文金额；推算值为 0 表示 Delta 没有包含税 | 写明税额 | 税种和税额都写出，税额与适用税率一致 |
| `ITEM.TAX.RATE_MISMATCH` | 税额（原文的或推算的）与税率表按基数计算的结果相差超过容差 | {path, base, tax, implied_rate, expected_rate, province} | 4-5 | 只记录 | high / alone | 税额与该省税率不符，核对适用省份和基数 | 按适用税率重新计算税额 | 税额 = 基数 × 适用税率（误差不超过 1 分） |
| `ITEM.TAX.NO_RULE` | 提到税，但适用省份没有税率规则（非加拿大，或 PST/QST 是否适用于运费未定） | {path, province, tax_codes} | 4-5 | 只记录 | medium / score +2 | 税额未经检查 | 无 | 无 |
| `ITEM.BASIS.PPG_CLAIMED` | 依据类型为 PPG_NOTIFIED、PPG_APPROVED 或 PPG_LIST | {path, basis_type, basis} | 4-5 | 只记录 | info / none | 承运商声称 PPG 通知、批准或有清单；需对照 PPG 内部记录核实，系统未核实 | 无 | 无 |
| `ITEM.BASIS.CONTRACT_CLAIMED` | 依据类型为 CONTRACT_OR_TARIFF 或 SHIPPING_DOCUMENT | {path, basis_type, basis} | 4-5 | 只记录 | info / none | 需对照合同、价目表或单据核实，系统未核实 | 无 | 无 |
| `ITEM.NATURE.RATE_CORRECTION` | 费用代码属于 RATE_CORRECTION 类 | {path, code} | 4-5 | 只记录 | low / none | 主张的是费率或计费方式错误，金额是差额，需要合同才能核实 | 无 | 无 |
| `ITEM.ARITH.QTY_RATE_MISMATCH` | line item 给出了数量和单价，数量 × 单价 ≠ 金额 | {path, quantity, unit_rate, amount} | 4-5 | 只记录 | medium / score +2 | 文本自己的算式不成立 | 更正数量、单价或金额，使三者一致 | 数量 × 单价 = 金额 |

#### 主张汇总（CLAIM）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `CLAIM.RECON.SUM_MISMATCH` | 计入状态的非合计金额之和（加上推算税额）≠ Delta，且不属于下面的数据型模式 | {counted_ids, claimed_sum, delta, difference} | 4-5 | 退回 | 不生成 flag | 重试用完后见 RUN.SUBMIT.FAILED | 列出的金额之和要等于本次差额 | 列出的金额之和等于本次差额 |
| `CLAIM.RECON.DELTA_COUNTS_TOTAL_TWICE` | 文本写了合计（a + b = c），Delta = 各项 + 合计（即合计被算了两次；a + b = c 时 Delta = 2c 是其特例） | {claimed_sum, total, delta} | 4-5 | 只记录 | high / alone | 发票金额可能把同一组费用计了两次；拆分本身按文本给出 | 发票金额只计一次合计 | 本次差额等于文本合计 |
| `CLAIM.RECON.TOTAL_MISMATCH` | 文本中的合计与计入金额之和（加推算税额）不一致 | {total_id, total, claimed_sum, implied_tax} | 4-5 | 只记录 | medium / score +2 | 文本自带的算式不成立 | 更正合计或各项金额 | 各项之和等于合计 |
| `CLAIM.RECON.PASSED_AFTER_RETURN` | 对账在第 2 次或以后的提交才通过 | {attempt, changed_fields} | 4-5 | 只记录 | low / score +1 | 模型改了判断才对上，看改动是否有原文依据 | 无 | 无 |

#### 与同一票货其他记录的关系（HIST）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `HIST.REPEAT.IDENTICAL_TEXT` | 更早的记录文本与 Delta 都相同 | {earlier_record_id, minutes_between} | 5.5 | 只记录 | medium / alone | 同一主张重复提交 | 不要重复提交同一争议 | 同一费用只有一条未结争议 |
| `HIST.REPEAT.SAME_DELTA` | 更早的记录 Delta 相同、文本不同 | {earlier_record_id} | 5.5 | 只记录 | low / score +1 | 可能是补充说明，也可能换了名目；对照更早的记录 | 无 | 无 |
| `HIST.REPEAT.SAME_AMOUNT_NEW_CODES` | 更早的记录 Delta 相同，但两次的费用代码类别不相交（要用到模型输出） | {earlier_record_id, earlier_codes, codes} | 5.5 | 只记录 | high / alone | 同一笔金额换了费用名目再提 | 说明为什么同一金额改用了不同费用名称 | 一笔金额只对应一个费用名称，并说明改动原因 |
| `HIST.REPEAT.REVISED_SAME_CHARGES` | 更早的记录 Delta 不同，但费用代码有交集（要用到两条记录的模型输出；税代码不算） | {earlier_record_id, earlier_delta, shared_codes} | 5.5 | 只记录 | low / score +1 | 同一项费用改了金额再提，看本次是替换还是追加 | 说明本次金额是替换还是追加更早的主张 | 文本写明与更早争议的关系（替换或追加）及原因 |
| `HIST.AMOUNT.EQUALS_EARLIER_DELTA` | 本次计入的某个金额等于更早某条记录的 Delta，而本次 Delta 与那条不同 | {id, amount, earlier_record_id, earlier_delta} | 5.5 | 只记录 | high / alone | 本次文本重复列出了更早争议的金额，可能同一笔钱主张了两次 | 只列出本次新增的金额，或说明与更早争议的关系 | 本次列出的金额不包含已主张过的金额，或明确写出是替换哪一次 |
| `HIST.AMOUNT.NEAR_105_EARLIER` | 本次计入的某个金额约为更早某条记录 Delta 的 1.03 到 1.07 倍（阈值在 rules.yaml） | {id, amount, earlier_record_id, earlier_delta, ratio} | 5.5 | 只记录 | medium / score +2 | 金额像是更早金额加了约 5%（可能是 GST），但文本没有写税 | 如含税，分别写出税前金额和税额 | 税额单列，且与适用税率一致 |
| `HIST.ORDER.SAME_MINUTE_SIBLING` | 同一票货有另一条记录的 Event Date 与本条相同（精确到分钟），两者互相不可见 | {sibling_record_id} | 5.5 | 只记录 | info / none | 两条同时提交，系统没有比较它们 | 无 | 无 |
| `HIST.CONTEXT.EARLIER_EXPLAINED` | 更早的记录 Delta 相同，且文本有费用名称（用于自动打回的豁免） | {earlier_record_id} | 5.5 | 只记录 | info / none | 本条缺的说明可以在更早的记录里找到 | 无 | 无 |

#### 处理过程（RUN）

| 代码 | 触发条件 | 证据 | 步骤 | 处理 | 严重程度 / 转人工作用 | 给审核员 | 给承运商的修改要求 | 合格标准 |
|---|---|---|---|---|---|---|---|---|
| `RUN.AGENT.UNCERTAINTY_REPORTED` | 模型调用 report_uncertainty | {target_path, reason_type, note} | 3 | 只记录 | medium / score +2 | 模型对某个对象没有把握，看它指出的地方 | 无 | 无 |
| `RUN.SUBMIT.FAILED` | 重试用完（或模型原样重提）仍有可退回的错误；最后一次答案标为未通过 | {attempts, last_errors} | 4-5 | 只记录 | critical / alone | 拆分未通过检查，以原文为准人工拆分 | 无 | 无 |
| `RUN.SUBMIT.NONE` | 达到轮数上限仍没有调用 submit_line_items | {turns} | 3 | 只记录 | critical / alone | 没有拆分结果 | 无 | 无 |
| `RUN.TOOL.RECONCILE_OVERUSE` | reconcile 调用次数超过上限，或试过的不同组合数达到上限（rules.yaml agent.reconcile_max_calls） | {calls, distinct_hypotheses} | 3 | 只记录 | low / score +1 | 模型试了多种读法才找到对得上的，结果可能是凑出来的 | 无 | 无 |
| `RUN.SUBMIT.SCHEMA_INVALID` | 提交不符合工具 schema（启用 strict 后理论上不出现；保留作为兜底） | {path, msg} | 4-5 | 退回 | 不生成 flag | 无 | 无 | 无 |
