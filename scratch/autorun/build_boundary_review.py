"""Turn boundary_results.json into docs/autorun/boundary_cases_review.zh.md: every case marked keep / modify / void
with a reason tied to a framework decision (docs/decisions/2026-11-04_framework_decisions.zh.md, "决定 x.y"),
task 09 section 1 ("第1节第n条") or a confirmed bug. Cases are synthetic (Codex), so the table can be tracked."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
res = json.load(open(ROOT / "data/interim/autorun/boundary_results.json"))

KEEP_GAP = "保留：期望不与任何决定冲突；但历史比对（决定 4.2）和跨发票、跨批次查重属于 R1c，不在本段范围（任务书第 4 节），本段未实现，列为缺口"
M = {
 "BC003": ("修改", "建议人工审核；REC.TEXT.NO_NUMBER、ITEM.AMOUNT.MISSING、CLAIM.DELTA.MISMATCH_*", "决定 3.2、第1节第4条：与 Delta 不一致交审核员判断，系统不裁决，不再直接建议退回"),
 "BC004": ("修改", "建议人工审核；第一份带 DUP.ROW.HAS_LATER_COPIES，后一份 DUP.ROW.COPY 指向第一份", "决定 5.3、第1节第7条：副本不合并，第二份起标识"),
 "BC029": ("修改", "解析通过检查；NUM.JUDGMENT.DOLLAR_EXCLUDED 作为事实列给审核员", "决定 3.5：带 $ 不计入必须有原文依据——没有依据时作为强制检查退回模型（RUN 层），有依据时只列给审核员。用例转换时以模型自己的 evidence_phrase 充当依据"),
 "BC034": ("作废", "—", "决定 3.8：去掉'这里没有数字'选项；提交 v2 的 schema 要求每个认不出的区域必须带 as_number，'读了但没判断'无法发生"),
 "BC037": ("修改", "建议人工审核；ITEM.CODE.OTHER", "决定 3.7：代码表里找不到就打标识（第1节第5条：颜色由规则算）"),
 "BC045": ("修改", "建议人工审核；ITEM.TAX.NO_AMOUNT、ITEM.TAX.PRESENT", "决定 4.4、第1节第5条：涉及税的一律到人工"),
 "BC046": ("修改", "建议人工审核；ITEM.TAX.PRESENT", "决定 4.4、第1节第5条：涉及税的一律到人工"),
 "BC047": ("修改", "建议人工审核；ITEM.TAX.PRESENT、ITEM.TAX.RATE_MISMATCH（只作事实）", "决定 4.4：税的问题送人工，不判承运商算错"),
 "BC051": ("修改", "建议人工审核；ITEM.ARITH.RELATION_FAILS（原 QTY_RATE_MISMATCH）、ITEM.ARITH.QTY_RATE_NO_RESULT", "决定 3.3：算式由代码每次验算；第1节第4条：原文自身不一致交审核员判断，不直接建议退回。容差保持 0.005（本用例发现我曾放宽到 0.011，已改回）"),
 "BC052": ("修改", "解析通过检查；NUM.ARITH.CUE_WITHOUT_RELATION（提示）", "决定 3.3：有算式迹象而模型没写算式关系，打一个提示（info），不改颜色"),
 "BC054": ("修改", "建议人工审核；CLAIM.DELTA.FIRST_MISMATCH、CLAIM.DELTA.MISMATCH_*（原 CLAIM.RECON.SUM_MISMATCH）", "决定 3.2：不一致只回'不一致'，结果交审核员；代码名随之改"),
 "BC055": ("修改", "建议人工审核；CLAIM.DELTA.MISMATCH_*，CLAIM.DELTA.TOTAL_COUNTED_TWICE_PATTERN 作解释", "决定 3.4：合计算两次不再作门槛，只作解释；决定 3.2 不一致交审核员；含税还要到人工（决定 4.4）"),
 "BC056": ("修改", "建议人工审核；同上", "决定 3.4、3.2"),
 "BC057": ("修改", "建议人工审核；CLAIM.RECON.TOTAL_MISMATCH、ITEM.TAX.PRESENT", "决定 4.4：含税一律到人工"),
 "BC058": ("修改", "建议人工审核；CLAIM.DELTA.MATCH_AFTER_REVISION、CLAIM.ATTEMPT.STATUS_CHANGED", "决定 3.5：自动比较前后两次尝试，把改了状态的数字列给审核员；决定 3.2 第一次读法要可见"),
 "BC059": ("保留", "（不变）", KEEP_GAP), "BC060": ("保留", "（不变）", KEEP_GAP), "BC061": ("保留", "（不变）", KEEP_GAP),
 "BC062": ("保留", "（不变）", KEEP_GAP), "BC063": ("保留", "（不变）", KEEP_GAP), "BC064": ("保留", "（不变）", KEEP_GAP),
 "BC066": ("保留", "（不变）", KEEP_GAP), "BC068": ("保留", "（不变）", KEEP_GAP), "BC069": ("保留", "（不变）", KEEP_GAP),
 "BC070": ("保留", "（不变）", KEEP_GAP + "；推荐颜色已一致"),
 "BC071": ("保留", "（不变）", "用例只给了 report_uncertainty 的调用、没给读法，所以 ITEM.AMOUNT.UNNAMED 无从产生；推荐颜色一致"),
 "BC072": ("修改", "建议人工审核；RUN.SUBMIT.FAILED_CHECKS（原 RUN.SUBMIT.FAILED）", "决定 3.2：原样重提是'坚持'，属于正常路径，不再自动结束；强制检查（缺编号）仍不通过时，次数用完显式失败"),
 "BC073": ("修改", "建议人工审核；RUN.SUBMIT.FAILED_CHECKS（原 RUN.SUBMIT.FAILED）", "代码改名（第1节第6条：失败显式标出），含义不变"),
 "BC074": ("保留", "（不变）", "模型从未提交 → RUN.SUBMIT.NONE、人工；与第1节第6条一致"),
 "BC075": ("作废", "—", "决定 3.1：去掉试算工具 reconcile"), "BC076": ("作废", "—", "决定 3.1：去掉试算工具 reconcile"),
 "BC077": ("作废", "—", "决定 3.1：去掉试算工具 reconcile"),
 "BC078": ("保留", "（不变）", "RUN.SUBMIT.SCHEMA_INVALID 仍存在；本表的转换器把旧格式补全成合法提交，掩盖了这一点，改由单元测试 test_schema_invalid_submission_is_returned_then_fails_explicitly 覆盖"),
 "BC082": ("修改", "建议人工审核；ITEM.CODE.OTHER", "决定 3.7（其他代码打标识）；计分阈值已由三档取代（决定日志 D-13，验收包 f 单独说明）"),
 "BC084": ("保留", "（不变）", "用例的工具记录是汇总数，无法回放；'先人工后退回'的顺序由 test_recommendation_order_attention_before_return 覆盖，'重试用完显式失败'由 test_repairs_exhausted_fail_explicitly 覆盖"),
 "BC086": ("保留", "（不变）", "决定 3.6 的费用代码依据核对属于 P4b（应该做，不在本段），本段未实现，列为缺口"),
 "BC087": ("修改", "解析通过检查；币种按国家推算为 USD 并标'推算'；只有推不出来时打 REC.FIELD.CURRENCY_UNDETERMINED", "决定 4.3：币种放在记录一级、按国家推算、标为推算"),
 "BC088": ("修改", "建议人工审核；NUM.JUDGMENT.DOLLAR_EXCLUDED（去掉 RUN.TOOL.RECONCILE_OVERUSE）", "决定 3.1：去掉 reconcile；其余期望不变"),
}
rows, cnt = [], Counter()
for o in res:
    same_rec = o["our_recommendation"] == o["expected_recommendation"]
    miss = sorted(set(o["expected_diagnostics"]) - set(o["our_codes"]))
    if o["case_id"] in M:
        cls, new, why = M[o["case_id"]]
    elif same_rec and not miss:
        cls, new, why = "保留", "（不变）", "期望与决定记录一致；新框架结果一致"
    else:
        cls, new, why = "说不清", "?", "未归类（需要人看）"
    cnt[cls] += 1
    now_ok = "一致" if same_rec and not miss else ("推荐一致" if same_rec else "不一致")
    rows.append(f"| {o['case_id']} | `{o['target_rule']}` | {o['expected_recommendation']}；{', '.join(o['expected_diagnostics']) or '无'} | "
                f"{o['our_recommendation']}；{', '.join(o['our_codes']) or '无'} | {now_ok} | **{cls}** | {new} | {why} |")
head = f"""# 88 个边界用例逐条核对（任务 09 阶段 2 内部关口）

来源：Codex 审阅的 `agent/boundary_cases/rules_and_diagnostics.jsonl`（合成用例，不含真实数据；副本在 git 忽略的 `data/external/`）。
方法：`scratch/autorun/boundary_cases.py` 把每条用例的假设读法从原型格式转成提交 v2，交给真实的提交控制器（不调用模型）；没有读法的用例只跑确定性步骤（"模型没跑"的标识不计）。`scratch/autorun/build_boundary_review.py` 生成本表。

**结果：保留 {cnt['保留']}、修改 {cnt['修改']}、作废 {cnt['作废']}、说不清 {cnt['说不清']}。** 不改 Codex 的原文件；"新期望"一列是按决定改后的期望。
保留里有 11 条是本段未实现的缺口（历史比对 9 条、P4b 1 条、R1c 相关 1 条），现结果与期望不一致，不算通过。

用例在本段发现的问题（已修，都有单元测试）：
- **BC049（bug）**：原文本身含 `[PERSON_1]` 这样的占位符时，"脱敏改动了数字"检查误报。已修：比较两边都先去掉占位符。
- **BC051（阈值）**：我曾把算式关系的容差从原型的 0.005 放宽到 0.011，没有决定支持。已改回 0.005，记入期望值和阈值改动记录。
- **BC039（规则档位）**：我把"一笔金额多个代码"定为送人工，没有决定支持；改回提示（info），与用例期望一致。

| 用例 | 目标规则 | 原期望（推荐；诊断） | 现结果（推荐；诊断） | 现结果与原期望 | 分类 | 新期望 | 理由 |
|---|---|---|---|---|---|---|---|
"""
(ROOT / "docs/autorun/boundary_cases_review.zh.md").write_text(head + "\n".join(rows) + "\n")
print(dict(cnt))
