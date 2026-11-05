"""A2 deliverable: reproduce the headline numbers of docs/analysis/01_problem_inventory.md and 01b_version_pairs.md.

Run from repo root: uv run python scratch/deliverables/A2_reproduce_inventory.py

Runs every script in scratch/analysis/ (unchanged, dev split only, no LLM calls) as a subprocess, saves its full
stdout to the git-ignored data/interim/deliverables/A2/<script>.txt (may contain row text), extracts selected
numbers with regexes, and compares them with the values stated in the reports. Prints and writes only the
aggregate comparison table (docs/deliverables/A2-problem-inventory/results/comparison.md).
"""

from __future__ import annotations

import re
import subprocess
import sys

from _shared import ROOT, md_table, results_dir, rowlevel_dir

FOLDER = "A2-problem-inventory"
SCRIPTS = ["a1_structure", "a2_numbers", "a3_reconcile", "a4_patterns", "a5_repeats", "a6_pt_surcharge",
           "a7_checks", "a8_event_date", "a9_version_pairs", "a10_delta_cumulative", "a11_r6_p3"]

# (report section, what, value stated in the report, script, regex; groups joined with "/", note)
# A value of None for regex means the number is not printed by any script.
CHECKS = [
    ("01 §0", "开发集行数 / shipment 数 / 承运商数", "953/813/18", "a1_structure",
     r"rows (\d+), shipments (\d+), carriers (\d+)", ""),
    ("01 §0.1", "Delta ≠ Invoice − Shipment 的行数", "0", "a1_structure", r"Delta != Invoice - Shipment \(>0\.005\): (\d+)", ""),
    ("01 §0.1", "目的地在加拿大省份 / 起点在加拿大 / 跨境", "831/790/41", "a1_structure",
     r"destination in Canadian province: (\d+).*?source in Canadian province: (\d+).*?cross-border[^:]*: (\d+)", ""),
    ("01 §0.1", "PK 为空的行（占比）", "322/33.8%", "a1_structure", r"PK empty: (\d+) \(([\d.]+%)\)", ""),
    ("01 §0.1", "Delta = 0 / Delta < 0 的行", "13/1", "a1_structure", r"== 0: (\d+), < 0: (\d+)", ""),
    ("01 §0.1", "Reason Code 为“其他附加费”的行（占比）", "823/86.4%", "a1_structure",
     r"OTHER_ACCESSORIALS': (\d+).*?OTHER_ACCESSORIALS share: ([\d.]+%)", ""),
    ("01 §0", "不同的非空文本数", "528", "a1_structure", r"distinct non-empty texts (\d+)", ""),
    ("01 §0.1", "数字 token / 带 $ / 占比", "1328/1109/83.5%", "a2_numbers",
     r"number tokens \(dates and times removed\): (\d+)\s+with \$ before: (\d+) \(([\d.]+%)\)", ""),
    ("01 P1", "按事件去重后的事件数 / 纯重复行（占比）", "908/45/4.7%", "a5_repeats",
     r"events: (\d+)\n.*?pure repeats of an event: (\d+) \(([\d.]+%)\)", ""),
    ("01 P1", "多 PK 的 shipment / 其中满足 行数=事件数×PK数", "10/10", "a5_repeats",
     r"shipments with >1 PK: (\d+); of these rows == events x PKs: (\d+)", ""),
    ("01 P2", "多次争议 shipment / Invoice Amount 有变化的", "91/73", "a5_repeats",
     r"shipments with >1 distinct event: (\d+)\n.*?Invoice Amount differs across events: (\d+) / \d+", ""),
    ("01 P2", "后续争议 95 条：单个或最后数字 / 数字之和 / 其他", "50/36/9", "a5_repeats",
     r"'single/last number = Delta': (\d+), 'sum of numbers = Delta': (\d+), 'other': (\d+)",
     "01b §5 修正 1：这是同一文本内的加总，不是跨争议累计"),
    ("01 P2 → 01b §5.2", "Delta 确实 ≠ 这次争议金额的行（修正值；01 原值 209 行 / 21.9%）", "21/2.2%", "a11_r6_p3",
     r"3 Delta != this dispute's amount\s+(\d+) \(([\d.]+%)\)", "原值 209/21.9% 仍由 a3 复现"),
    ("01 P2（原值）", "Delta ≠ 唯一或最后数字的行（已被 01b 修正）", "209/21.9%", "a3_reconcile",
     r"\(R5-R10\): (\d+) \(([\d.]+%)\)", "数字本身可复现，但解读已被 01b §5.2 取代"),
    ("01b §3.4", "C4：等于文本金额 / 重复前一版 / 看不到前一版 / 后续未重复", "879/27/11/2", "a11_r6_p3",
     r"1 Delta = the amount the text states\s+(\d+).*?re-lists amounts of the previous dispute\s+(\d+)"
     r".*?no earlier event visible\s+(\d+).*?nothing re-listed\s+(\d+)", "48 = 21+27；61 = 48+11+2"),
    ("01 P2 → 01b §5.8", "约 5% 增幅处数 / 最小 / 中位 / 最大 / 落在 1.0475–1.0525（修正值；01 原值 41/94）",
     "39/1.032/1.050/1.055/29", "a10_delta_cumulative",
     r"uplifts \(replacement or stacked balance\): (\d+); ratio min ([\d.]+), median ([\d.]+), max ([\d.]+); "
     r"within 1\.0475-1\.0525: (\d+)", "比值四舍五入到 3 位比较；原值 41/94 仍由 a5 复现"),
    ("01 P3 → 01b §3.3", "BALANCE DUE 且 ≥2 个 $ 金额：行数 / Delta = 含余额之和", "53/45", "a4_patterns",
     r"'BALANCE DUE' with >=2 \$ amounts: (\d+) rows -> \{[^}]*'Delta = sum incl\. balance': (\d+)", ""),
    ("01 P3", "其余 8 行拆分：Delta 不含余额 / 其他", "4/4", "a4_patterns",
     r"'Delta = balance \(last\)': (\d+), 'Delta = sum incl\. balance': \d+, 'other': (\d+)",
     "脚本只输出 '余额即 Delta' 2 / '其他' 6，没有 '不含余额' 这一类；01b §3.3 修正为 5 行 Delta 不含余额（a11 可复现）"),
    ("01b §3.3", "同一写法 Delta 不含余额：唯一一条 / 后续争议", "4/1", "a11_r6_p3",
     r"BALANCE DUE rows in R9[^:]*: \{'only event of its shipment': (\d+), 'later event of a multi-event shipment': (\d+)\}", ""),
    ("01 P5", "Delta ≤ 0 的行", "14", "a7_checks", r"Delta <= 0 rows: (\d+)", ""),
    ("01 P6", "Delta = 2 × 文本金额且 Delta 不在文本中", "10", "a7_checks", r"Delta = 2 x a stated number and Delta itself not stated: (\d+)", ""),
    ("01 P7", "空格千分位行 / 其中重量 / 其中金额", "109/101/7", "a2_numbers",
     r"rows with space-thousands number: (\d+)\s+of which the number is a weight[^:]*: (\d+)\s+of which the number has a \$[^:]*: (\d+)", ""),
    ("01 P7", "负号行 / 其中作分隔符", "352/342", "a2_numbers",
     r"minus sign directly before a number: (\d+)\s+of which minus is used as a separator[^:]*: (\d+)", ""),
    ("01 P7", "含日期行 / ISO / M/D/YYYY / M/D/YY / M/D", "48/19/16/3/13", "a2_numbers",
     r"rows with dates: (\d+)\s+ISO dates \(2022-03-14\): (\d+); M/D/YYYY: (\d+); M/D/YY: (\d+); M/D without year: (\d+)", ""),
    ("01 P8", "百分比 / 带重量单位 / ZIP（行）", "10/103/10", "a2_numbers",
     r"rows with percent: (\d+)\nrows with weight unit \(LBS/KG\): (\d+).*?rows with ZIP code: (\d+)", ""),
    ("01 P9", "a+b=c 加总处数 / 一致", "10/10", "a4_patterns", r"stated sums 'a \+ b = c' found: (\d+); consistent (\d+)", ""),
    ("01 P9", "司机等候带时段 / 符合 60 分钟免费+每 15 分钟 $30", "15/13", "a7_checks",
     r"driver detention with window: (\d+); amount = \$30 per started 15 min after 60 free min: (\d+)", ""),
    ("01 P10", "提到税 / 有金额 / 只写税种 / 税是争议对象", "24/18/4/4", "a4_patterns",
     r"mentions tax: (\d+) rows.*?tax with its own amount: (\d+) rows.*?tax named without an amount[^:]*: (\d+) rows"
     r".*?tax as the subject of the dispute[^:]*: (\d+) rows", ""),
    ("01 P11", "purchase(d) transportation 写法种数 / 错别字行", "11/27", "a4_patterns",
     r"distinct surface forms of the charge name: (\d+).*?misspelling \(list in script\): (\d+) rows", ""),
    ("01 P12", "purchase(d) transportation 行（占比）", "569/59.7%", "a4_patterns",
     r"purchase\(d\)-transportation family: (\d+) rows \(([\d.]+%)\)", ""),
    ("01 P12", "只此一项且金额=Delta / 正好 $20 / 其他金额", "391/209/182", "a6_pt_surcharge",
     r"PT-only rows with amount = Delta: (\d+)\s+exactly \$20\.00: (\d+); other amounts: (\d+)", ""),
    ("01 P12", "非 $20 行 金额÷Shipment Amount 10/50/90% 分位", "0.185/0.255/0.380", "a6_pt_surcharge",
     r"quantiles \(10/50/90%\): \[([\d.]+) ([\d.]+) ([\d.]+)\]\n", "四舍五入到 3 位比较"),
    ("01 P13", "一个金额对应多项费用的行", "5", "a4_patterns", r"one \$ amount covering two named charges[^:]*: (\d+) rows", ""),
    ("01 P14", "只有一个数字 / 只有付款或总额词（行）", "11/26", "a4_patterns",
     r"text is only a number: (\d+) rows.*?text names no charge[^:]*: (\d+) rows", ""),
    ("01 P15", "费率/合同类主张：行 / 不同文本", "83/35", "a4_patterns",
     r"argues rating / contract / weight[^:]*: (\d+) rows \([\d.]+%\), (\d+) distinct", ""),
    ("01 P16", "以 PPG 人员或名单为依据：行 / 不同文本", "89/32", "a4_patterns",
     r"cites a PPG person[^:]*: (\d+) rows \([\d.]+%\), (\d+) distinct", ""),
    ("01 P18", "提到 hazmat 的行 / 其中编为“其他附加费”", "58/57", "a4_patterns",
     r"HAZMAT\s+(\d+) rows; reason codes: \{'INCORRECT_MISSING_OTHER_ACCESSORIALS': (\d+)", ""),
    ("01 P19", "含人名：行 / 不同文本；含邮箱行", "54/28/2", "a4_patterns",
     r"contains a person's name[^:]*: (\d+) rows \([\d.]+%\), (\d+) distinct.*?contains an email address: (\d+) rows", ""),
    ("01 P20", "最大承运商行占比 / 前 3 占比", "61.1%/89.6%", "a1_structure",
     r"top carrier share ([\d.]+%); top 3 share ([\d.]+%)", ""),
    ("01 P20", "模板数 / 前 10 覆盖 / 前 30 覆盖 / 单承运商模板数", "179/52.8%/77.6%/178", "a4_patterns",
     r"distinct templates \(digits masked\): (\d+); top 10 cover ([\d.]+%); top 30 cover ([\d.]+%)\n"
     r"carrier rows in templates used by only one carrier: (\d+)", ""),
    ("01 P21", "R3 + R4 简单样本行（占比）", "731/76.7%", "a3_reconcile",
     r"R3 single number = \|Delta\|\s+(\d+) \(([\d.]+)%\)\nR4 last number = \|Delta\| \(multi-number text\)\s+(\d+) \(([\d.]+)%\)",
     "由 R3 663 + R4 68 相加"),
    ("01 P11", "同一文本最多出现次数", "75", "", None, "没有脚本输出这个数"),
    ("01 P12", "非 $20 行的最小金额", "20.09", "", None, "a6 只输出全部金额范围 20.00–535.18，没有单独输出非 $20 的最小值"),
    ("01b §0", "最大 / 第二大 / 第三大承运商的“行”数", "580/164/87", "a8_event_date",
     "TOPCARRIERS",
     "数值与 a8 的事件数一致；按行算是 582/185/87（a1）。报告把事件数写成了“行”"),
    ("01b §1.1", "0–7 点的行 / 第二大承运商 / 最大承运商", "70/56/14", "a8_event_date",
     "NIGHT", "总数 = 两家之和（a8 的小时分布 0–7 点合计也是 70）"),
    ("01b §1.2", "多事件 shipment 的事件 / 同分钟并列组 / 涉及事件 / 可完全排序", "186/10/20/81", "a8_event_date",
     r"events in them: (\d+)\n\(shipment, Event Date\) groups holding >1 distinct event: (\d+); events involved: (\d+)"
     r".*?fully orderable \(no tie\): (\d+) / 91", ""),
    ("01b §1.3", "不同时间戳 / 被多个 shipment 共用", "870/27", "a8_event_date",
     r"distinct timestamps (\d+) for 908 events; timestamps shared by >1 shipment: (\d+)", ""),
    ("01b §1.3", "文本带日期事件 / 晚于 Event Date 1 天以上 / ±1 天内 / 更早", "48/15/31/2", "a8_event_date",
     r"events whose text contains a date: (\d+)\n\s+latest text date is >1 day AFTER Event Date: (\d+) .*?within \+-1 day: (\d+); >1 day before: (\d+)", ""),
    ("01b §1.3", "Event Date 与 shipment 编号秩相关", "0.966", "a8_event_date", r"= ([\d.]+)\n\nDispute Status", ""),
    ("01b §1.4", "方向检验：后引前 / 前引后", "21/1", "a8_event_date",
     r"later quotes earlier Delta only (\d+); earlier quotes later Delta only (\d+)", ""),
    ("01b §2.1", "相邻配对 / 有序 / 并列", "95/85/10", "a9_version_pairs",
     r"adjacent pairs (\d+) \(ordered (\d+), same Event Date (\d+)\)", ""),
    ("01b §2.2", "关系分布：重复 / 补充 / 加付款措辞 / ~5%替换 / 叠加余额 / 金额其他 / 新增 / 删除 / 无关 / 换名 / 改写",
     "4/7/4/20/18/6/3/7/11/4/1", "a9_version_pairs", "LABELS", "按标签逐项读取"),
    ("01b §2.2", "付款状态副标记：对数 / BALANCE DUE / paid 类", "55/54/1", "a9_version_pairs",
     r"as a secondary flag on ordered pairs: (\d+);.*?'BALANCE DUE/OWING': (\d+), 'paid/unpaid/owe': (\d+)", ""),
    ("01b §2.4", "前一版 DECLINED 的有序对 / 其中修改版", "18/14", "a9_version_pairs",
     r"earlier event is DECLINED: (\d+); of these a modified version[^:]*: (\d+)", ""),
    ("01b §2.4", "前一版非 DECLINED 的有序对 / 其中修改版（占比）", "67/57/85%", "a9_version_pairs",
     r"earlier event is not DECLINED: (\d+); modified: (\d+) \((\d+%)\)", "按 a9 交叉表手算：67 − 重复 2 − 无关 9 = 56"),
    ("01b §2.4", "Status 不同的多事件 shipment / 前后 Status 不同的对", "0/0", "a9_version_pairs",
     r"more than one status: (\d+) / 91\n\s+pairs with status_a != status_b: (\d+) / 95", ""),
    ("01b §2.4", "DECLINED 事件 / 其后还有事件；非 DECLINED / 其后还有", "133/18/775/67", "a9_version_pairs",
     r"DECLINED events: (\d+); followed by a later event of the same shipment: (\d+)\n\s+non-DECLINED events: (\d+); followed by a later event: (\d+)", ""),
    ("01b §3.1", "后一版 Delta = 自身金额 / 最后金额 / 前版+新增 / ×1.05 精确 / 1.03–1.07 / 发票变化量 / 都不是",
     "82/51/21/9/20/0/3", "a10_delta_cumulative", "A10TESTS", "按测试名逐项读取"),
    ("01b §3.1", "Delta 变大 / 不变 / 变小", "57/20/8", "a10_delta_cumulative",
     r"Delta_b vs Delta_a: larger (\d+), equal (\d+), smaller (\d+)", ""),
    ("01b §3.2", "R6 / R6a / R6b / R6c 行数", "121/71/40/10", "a11_r6_p3",
     r"R6 rows: (\d+)\n\s+R6a .*?: (\d+) rows.*?R6b .*?: (\d+) rows.*?R6c .*?\): (\d+) rows", ""),
    ("01b §3.3", "P3 中 Y 独立的 45 行：后续 / 唯一 / 并列", "45/29/13/3", "a11_r6_p3",
     r"\(Delta = sum incl\. balance\): (\d+) rows.*?later event of a multi-event shipment\s+(\d+)\nonly event of its shipment\s+(\d+)"
     r"\nmulti-event shipment, same Event Date as another event\s+(\d+)", ""),
]

LABELS = ["identical", "elaboration (same amount, fuller text)", "payment/balance wording added (same amount)",
          "amount change: ~5% (replaces earlier amount)", "amount change: earlier amount kept + new ~5%-higher balance",
          "amount change: other", "added charge", "removed charge", "unrelated new dispute",
          "other: same amount, different charge name", "other: same amount, reworded without new information"]
A10TESTS = ["t_own", "t_own_last", "t_prev_plus_new", "t_x105_exact", "t_x105_band", "t_d_inv", "t_none"]


def run_all() -> dict[str, str]:
    out_dir = rowlevel_dir("A2")
    outs = {}
    for s in SCRIPTS:
        p = subprocess.run(["uv", "run", "python", f"scratch/analysis/{s}.py"], cwd=ROOT, capture_output=True, text=True)
        if p.returncode != 0:
            sys.exit(f"{s} failed:\n{p.stderr[-2000:]}")
        (out_dir / f"{s}.txt").write_text(p.stdout)
        outs[s] = p.stdout
    return outs


def norm(v: str) -> str:
    """Compare decimals like 0.1854 vs 0.185 and 1.0547 vs 1.055 at 3 places; leave counts and percentages as is."""
    if re.fullmatch(r"\d+\.\d{3,}", v):
        return f"{float(v):.3f}"
    return v


def extract(outs: dict[str, str], script: str, pattern: str) -> str | None:
    text = outs[script]
    if pattern == "LABELS":
        sec = text.split("1. relation of ordered pairs")[1].split("All ")[0]
        vals = [re.search(rf"^{re.escape(lab)}\s+\d+\s+\d+\s+(\d+)$", sec, re.M) for lab in LABELS]
        return "/".join(m.group(1) for m in vals) if all(vals) else None
    if pattern == "TOPCARRIERS":  # event counts per carrier (no carrier code is kept), largest three
        sizes = sorted((int(x) for x in re.findall(r"'size': (\d+)", text.split("events at an exact HH:00")[1].split("\n")[0])), reverse=True)
        return "/".join(str(x) for x in sizes[:3])
    if pattern == "NIGHT":  # rows at 00:00-07:59: total / second-largest carrier / largest carrier (codes dropped)
        m = re.search(r"rows at 00:00-07:59 by carrier: \{'\w+': (\d+), '\w+': (\d+)\}", text)
        return f"{int(m.group(1)) + int(m.group(2))}/{m.group(1)}/{m.group(2)}" if m else None
    if pattern == "A10TESTS":
        vals = [re.search(rf"^\s+{t}\s+(\d+)\s", text, re.M) for t in A10TESTS]
        return "/".join(m.group(1) for m in vals) if all(vals) else None
    m = re.search(pattern, text, re.S)
    if not m:
        return None
    g = list(m.groups())
    if script == "a3_reconcile" and len(g) == 4:  # R3 + R4 -> rows and share
        return f"{int(g[0]) + int(g[2])}/{float(g[1]) + float(g[3]):.1f}%"
    return "/".join(norm(x) for x in g)


def main() -> None:
    outs = run_all()
    rows, n_ok, n_bad, n_na = [], 0, 0, 0
    for i, (sec, what, stated, script, pat, note) in enumerate(CHECKS, 1):
        if pat is None:
            got, verdict = "—", "无法复现"
            n_na += 1
        else:
            got = extract(outs, script, pat) or "（未匹配）"
            stated_n = "/".join(norm(x) for x in stated.split("/"))
            if got == stated_n:
                verdict = "是"
                n_ok += 1
            else:
                verdict = "否"
                n_bad += 1
        rows.append([i, sec, what, stated, f"`{script}.py`" if script else "—", got, verdict, note])
    header = ["#", "报告位置", "数字", "报告值", "脚本", "重跑值", "一致", "说明"]
    table = md_table(header, rows)
    summary = (f"共 {len(CHECKS)} 项：一致 {n_ok}，不一致 {n_bad}，没有脚本输出、无法复现 {n_na}。"
               f"数据：开发集 data/processed/dev.csv 全量（953 行 / 908 事件），不是测试集。")
    print(table)
    print(summary)
    md = ("# A2 问题盘点数字复现对照表\n\n"
          "由 `uv run python scratch/deliverables/A2_reproduce_inventory.py` 生成。只含汇总数字。"
          "多值项按 “/” 分隔逐项比较；小数四舍五入到 3 位比较。\n\n"
          f"{summary}\n\n{table}")
    (results_dir(FOLDER) / "comparison.md").write_text(md)


if __name__ == "__main__":
    main()
