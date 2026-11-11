"""Read-only results page (task 09 stage 5 item 2): one static HTML file, no external resources, no buttons, no
script, nothing recorded. Grouped by carrier invoice, expanded to each claim (line item). Contains row-level redacted
text, so it is written only to the git-ignored data/interim/autorun/acceptance/.

Run: uv run python scratch/autorun/build_results_page.py
"""

from __future__ import annotations

import html
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_run import load  # noqa: E402

from freight_lineitems.config import ROOT  # noqa: E402

RUNS = {"样本 A": "20261110-184540-finA-d700", "样本 B": "20261110-184723-finB2-4b6b",
        "公开 mock": "20261110-184540-finMock-da71", "第一批（停点一）": "20261110-171337-stage1-1cc1"}
OUT = ROOT / "data" / "interim" / "autorun" / "acceptance" / "results.html"
COLOR = {"PASSED_CHECKS": ("#2e7d32", "解析通过检查"), "HUMAN_REVIEW": ("#b8860b", "建议人工审核"),
         "RETURN_SUGGESTED": ("#c62828", "建议退回承运商")}
SEV = {"attention": "需人看", "return": "可退回", "info": "提示"}
FIRST = {"MATCH": "首次一致", "MISMATCH": "首次不一致", "NO_ANCHOR": "无锚点（Delta 为 0）", None: "未得到可比的读法"}
e = html.escape


def reading_rows(r: dict) -> str:
    f = r["facts"]
    rd = f["reading"] or {}
    raw = {n["id"]: n["raw"] for n in f["number_table"]["numbers"]}
    nums = {j["id"]: j for j in rd.get("numbers", [])} | {x["region_id"]: x["as_number"] for x in rd.get("unrecognized_reads", [])}
    rows = []
    for k, li in enumerate(rd.get("line_items", [])):
        j = nums.get(li["amount_ref"]) if li["amount_ref"] else None
        codes = (j["charge_codes"] if j else li["charge_codes"]) or ["（无代码）"]
        amt = raw.get(li["amount_ref"], "（无金额）") if li["amount_ref"] else "（无金额）"
        rows.append(f"<tr><td>{k}</td><td>{e(str(amt))}{' 贷记' if j and j.get('is_credit') else ''}</td><td>{e(', '.join(codes))}</td>"
                    f"<td>{e(li.get('raw_charge_label') or '')}</td><td>{e(li.get('carrier_stated_reason') or '')}</td>"
                    f"<td>{e(li.get('carrier_stated_basis_type'))}{(': ' + e(li['carrier_stated_basis'])) if li.get('carrier_stated_basis') else ''}</td></tr>")
    nrows = "".join(f"<tr><td>{e(i)}</td><td>{e(str(raw.get(i, '')))}</td><td>{e(j['kind'])}</td><td>{e(j['status'])}"
                    f"{' 贷记' if j.get('is_credit') else ''}</td><td>{e(', '.join(j['charge_codes']))}</td><td>{e(j.get('evidence_phrase') or '')}</td>"
                    f"<td>{e(j.get('exclusion_phrase') or '')}</td></tr>" for i, j in nums.items())
    return (f"<table><tr><th>#</th><th>金额</th><th>费用代码</th><th>原文费用名</th><th>承运商理由（未核实）</th><th>承运商依据（未核实）</th></tr>{''.join(rows)}</table>"
            f"<details><summary>每个数字的读法</summary><table><tr><th>编号</th><th>原文</th><th>类型</th><th>状态</th><th>代码</th><th>依据片段</th><th>不计入的依据</th></tr>{nrows}</table></details>")


def anchor(run_id: str, record_id: str) -> str:
    return f"{run_id}__{record_id.replace('#', '-')}"


def dispute(r: dict, run_id: str) -> str:
    f, j, p = r["facts"], r["judgment"], r["process"]
    col, label = COLOR[j["recommendation"]]
    flags = "".join(f"<li class='{fl['severity']}'>[{SEV[fl['severity']]}] <code>{e(fl['code'])}</code>"
                    f"{' → 指向 ' + e(fl['points_to']) if fl.get('points_to') else ''}"
                    f"<span class='ev'>{e(json.dumps(fl['evidence'], ensure_ascii=False)[:400])}</span></li>"
                    for fl in j["flags"])
    notes = [ev.get("note") for fl in j["flags"] if fl["code"] == "RUN.AGENT.UNCERTAINTY_REPORTED" for ev in fl["evidence"]]
    reasons = [a["raw_submission"].get("reason") for a in p.get("attempts", []) if a["raw_submission"].get("reason")]
    atts = "".join(f"<li>第 {a['attempt_no']} 次（{e(a['response_type'] or '')}）：与 Delta {e(a['delta_check'] or '未比较')}"
                   f"{'；收到的反馈：' + e(a['feedback_given']) if a.get('feedback_given') else ''}"
                   f"{'；退回的检查错误：' + e(', '.join(x['code'] for x in a['repair_errors'])) if a['repair_errors'] else ''}</li>"
                   for a in p.get("attempts", []))
    open_attr = " open" if any(fl["severity"] != "info" for fl in j["flags"]) else ""
    return (f"<details class='dispute' id='{e(anchor(run_id, r['record_id']))}'{open_attr}><summary><span class='dot' style='background:{col}'></span>"
            f"<b>{e(r['record_id'])}</b> · {label} · {FIRST.get(f['first_check'], f['first_check'])} · 最终：{e(f['delta_consistency'])} · "
            f"Delta {e(str(f['source']['delta']))}</summary>"
            f"<p class='text'>{e(f['text_redacted']) or '（空文本）'}</p>"
            f"{reading_rows(r)}"
            f"<p><b>模型的说明</b>：{'；'.join(e(x) for x in reasons + notes) or '（没有）'}</p>"
            f"<p><b>尝试</b>（全部保留，第一次可见）：</p><ul>{atts or '<li>模型没有运行或没有提交</li>'}</ul>"
            f"<p><b>标识</b>（颜色由规则算）：</p><ul class='flags'>{flags or '<li>无</li>'}</ul></details>")


def main():
    parts = []
    for name, rid in RUNS.items():
        rs = load(rid)
        by_inv = defaultdict(list)
        for r in rs:
            by_inv[r["facts"]["invoice_key"]].append(r)
        inv_html = []
        for k, (inv, items) in enumerate(sorted(by_inv.items(), key=lambda x: min(r["record_id"] for r in x[1]))):
            counts = defaultdict(int)
            for r in items:
                for fl in r["judgment"]["flags"]:
                    counts[fl["severity"]] += 1
            worst = min((COLOR[r["judgment"]["recommendation"]][1] for r in items), key=lambda x: ["建议人工审核", "建议退回承运商", "解析通过检查"].index(x))
            inv_html.append(f"<section class='invoice'><h3>发票 {k + 1}（{len(items)} 笔争议）· 最需注意：{worst} · "
                            f"需人看 {counts['attention']} · 可退回 {counts['return']} · 提示 {counts['info']}</h3>"
                            + "".join(dispute(r, rid) for r in sorted(items, key=lambda r: r["record_id"])) + "</section>")
        parts.append(f"<h2 id='{e(rid)}'>{e(name)}（运行 {e(rid)}，{len(rs)} 条）</h2>" + "".join(inv_html))
    css = """body{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1100px;margin:auto;padding:16px;color:#222}
h2{border-bottom:2px solid #999;margin-top:40px}.invoice{border:1px solid #ccc;border-radius:6px;padding:6px 10px;margin:10px 0}
.invoice h3{font-size:14px;margin:4px 0}.dispute{margin:6px 0 6px 12px}.dot{display:inline-block;width:10px;height:10px;border-radius:5px;margin-right:6px}
.text{font-family:monospace;background:#f6f6f6;padding:6px}table{border-collapse:collapse;font-size:12px;margin:4px 0}
td,th{border:1px solid #ddd;padding:2px 6px;text-align:left}.ev{display:block;color:#666;font-size:11px}
li.attention{color:#8a6100}li.return{color:#a00}li.info{color:#555}code{font-size:12px}"""
    head = ("<h1>运费争议解析结果（只读）</h1><p>任务 09 阶段 5 验收包。脱敏后的原文、模型读法、按规则算出的颜色和标识、首次是否不一致。"
            "页面没有按钮，不记录任何决定；颜色不代表该不该付。定位：每笔争议的锚点是「运行编号__record_id（# 换成 -）」，例如 <code>results.html#20261110-171337-stage1-1cc1__dev-r193</code>；也可以在页面里搜索 record_id。</p><ul>"
            + "".join(f"<li><a href='#{e(rid)}'>{e(n)}</a></li>" for n, rid in RUNS.items()) + "</ul>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(f"<!doctype html><html lang='zh'><head><meta charset='utf-8'><title>运费争议解析结果（只读）</title>"
                   f"<style>{css}</style></head><body>{head}{''.join(parts)}</body></html>")
    print(OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
