"""Task 07: write the v5 Archify workflow sources (zh + en) from one spec so their structure is identical.

Run from repo root: uv run --no-project python scratch/status/flow_v5_build.py
Writes docs/status/flow_src/pipeline_flow.{zh,en}.workflow.json. Regenerate HTML afterwards (flow_src/README.md).
Node `type` encodes the card colour: backend = light green, cloud = yellow, security = red, external = no card.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/status/flow_src"

meta = {
    "zh": {"title": "PPG 运费争议处理流程 v5（按 2026-11-04 决定）", "locale": "zh-CN",
           "legend": {"backend": "浅绿卡：样本内证据 + 交付物", "cloud": "黄卡：部分完成",
                      "security": "红卡：未开始", "external": "不对应卡片（人、界面）"}},
    "en": {"title": "PPG freight dispute pipeline v5 (per 2026-11-04 decisions)", "locale": "en",
           "legend": {"backend": "Light-green card: in-sample evidence + deliverable", "cloud": "Yellow card: partly done",
                      "security": "Red card: not started", "external": "No card (people, interface)"}},
}
lanes = [("carrier", "承运商", "Carrier"), ("code", "处理（代码）", "Processing (code)"),
         ("llm", "理解（LLM）", "Understanding (LLM)"), ("rules", "标识与推荐（代码）", "Flags & recommendation (code)"),
         ("assets", "知识资产与数据", "Knowledge assets & data"), ("reviewer", "审核员", "Reviewer")]
phases = [("prep", "准备", "Preparation", 0, 1, None),
          ("content", "事实层：盲解析与核对", "Fact layer: blind parse & checks", 2, 3, "emphasis"),
          ("action", "判断层与审核", "Judgment layer & review", 4, 5, None)]
# id, lane, col, type, zh label, zh sub, en label, en sub, tag(zh), tag(en), yOffset
P = "待改"
PE = "to revise"
nodes = [
    ("submit", "carrier", 0, "external", "提交争议", "发票 + 文字说明", "Submit dispute", "invoice + free text", None, None, None),
    ("pushback", "carrier", 5, "external", "收到退回", "审核员在 OTM 执行", "Receives return", "via OTM", None, None, None),
    ("read", "code", 0, "backend", "0-1 读入", "原样存行 · 脱敏 · 注入检查", "0-1 Read", "keep · redact · inject", f"B01 · {P}", f"B01 · {PE}", None),
    ("nums", "code", 1, "backend", "2 数字识别", "找全 · 编号 · 覆盖检查", "2 Number parse", "find · number · cover", "B02", "B02", None),
    ("llminput", "code", 2, "security", "模型输入（白名单）", "去掉 Delta · 只给数字表", "Model input", "no Delta", "B04", "B04", None),
    ("tool", "code", 3, "cloud", "4-5 提交检查", "算式 · 防凑数 · 依据 · 对 Delta", "4-5 Checks", "math · padding · basis", f"B07 · {P}", f"B07 · {PE}", None),
    ("history", "code", 4, "cloud", "5.5 多层面查重", "行 · 发票内 · 票货内 · 跨批次", "5.5 Duplicates", "row · invoice · shipment", f"B08 · {P}", f"B08 · {PE}", None),
    ("understand", "llm", 2, "security", "3 盲解析（agent 循环）", "不给 Delta · 每次尝试都留", "3 Blind parse", "agent loop · no Delta", "B04", "B04", None),
    ("flags", "rules", 4, "cloud", "6a 标识", "按规则 · 证据 · 指向第一份", "6a Flags", "rules · evidence · → first", "B09", "B09", None),
    ("draft", "rules", 5, "backend", "6c 退回草稿", "只给审核员，不发送", "6c Return draft", "reviewer only, never sent", f"C1 · {P}", f"C1 · {PE}", -48),
    ("decide", "rules", 5, "cloud", "6b 推荐颜色", "正常 · 有标识 · 建议退回", "6b Recommendation", "normal · flagged · return suggested", f"B09 · {P}", f"B09 · {PE}", 48),
    ("skill", "assets", 0, "cloud", "SKILL.md", "操作规程 · 例子", "SKILL.md", "procedure · examples", f"B05 · {P}", f"B05 · {PE}", None),
    ("taxonomy", "assets", 1, "cloud", "代码表", "代码 · 别名 · 原文名称", "Code table", "codes · aliases · labels", "C3", "C3", None),
    ("taxrules", "assets", 3, "cloud", "工具 · 税率表", "计算器 · 税率 · 示例", "Tools · tax", "calc · tax · cases", f"B06 · {P}", f"B06 · {PE}", None),
    ("store", "assets", 4, "backend", "7 解析结果库", "事实层 · 判断层分开", "7 Parse store", "facts ≠ judgments", f"B10 · {P}", f"B10 · {PE}", None),
    ("rulesyaml", "assets", 5, "cloud", "rules.yaml", "查重 · 标识 · 大白话", "rules.yaml", "dups · flags · plain text", "C2", "C2", -48),
    ("catalog", "assets", 5, "backend", "诊断目录", "固定文字", "Diagnostics", "fixed wording", "C1", "C1", 48),
    ("review", "reviewer", 5, "external", "审核界面（终点）", "决定 · 理由", "Review UI (end)", "decide · reason", None, None, None),
]
# id, from, to, zh, en, role, variant, fromSide, toSide
edges = [
    ("e-submit-read", "submit", "read", "OTM 导出 Excel", "OTM Excel export", None, None, None, None),
    ("e-read-nums", "read", "nums", "脱敏文字", "redacted text", None, None, None, None),
    ("e-nums-llminput", "nums", "llminput", "数字表 + 诊断", "numbers + diagnostics", None, None, None, None),
    ("e-llminput-understand", "llminput", "understand", "不含 Delta", "no Delta", None, None, None, None),
    ("e-skill-understand", "skill", "understand", "操作规程", "procedure", None, None, None, None),
    ("e-taxonomy-understand", "taxonomy", "understand", "代码 + 别名", "codes + aliases", None, None, None, None),
    ("e-understand-tool", "understand", "tool", "解读 · 主张 · 算式", "readings · claim · math", None, None, None, None),
    ("e-tool-understand", "tool", "understand", "不一致：不透露 Delta，可坚持或修改", "mismatch: keep or revise", "return", "dashed", None, None),
    ("e-taxrules-tool", "taxrules", "tool", "税率", "tax rates", None, None, None, None),
    ("e-tool-history", "tool", "history", "每次尝试 + 状态", "attempts + status", None, None, None, None),
    ("e-store-history", "store", "history", "之前批次的解析结果", "earlier parses", "return", "dashed", None, None),
    ("e-history-flags", "history", "flags", "全部诊断", "all diagnostics", None, None, None, None),
    ("e-flags-decide", "flags", "decide", "标识", "flags", None, None, None, None),
    ("e-rulesyaml-decide", "rulesyaml", "decide", "规则", "rules", None, None, None, None),
    ("e-catalog-draft", "catalog", "draft", "固定文字", "fixed wording", None, None, None, None),
    ("e-decide-draft", "decide", "draft", "建议退回时", "if return", None, None, None, None),
    ("e-decide-review", "decide", "review", "三种推荐全部到这里", "all three colours", "branch", None, "right", None),
    ("e-decide-store", "decide", "store", "事实层 + 判断层", "facts + judgments", None, None, "bottom", None),
    ("e-review-pushback", "review", "pushback", "审核员决定退回", "reviewer returns", "branch", None, None, None),
    ("e-review-store", "review", "store", "决定 · 理由", "decision · reason", "return", "dashed", None, None),
]
cards = {
    "zh": [
        ("emerald", "颜色 = 看板卡片状态", ["浅绿：样本内证据 + 交付物；黄：部分完成；红：未开始",
                                       "角标是卡片编号；\"待改\" = 现有实现与 2026-11-04 决定不一致，颜色暂不动"]),
        ("cyan", "与 v4 的主要不同（2026-11-04 决定）", ["删除打回预判和自动通知；所有记录进模型、都到审核员（决定 2.1、2.2）",
                                                    "盲解析：模型看不到 Delta，不一致时回给模型，每次尝试都留（决定 3.1、3.2）",
                                                    "存自己的解析结果，做多层面、跨批次查重（决定 4.1、5.2）"]),
        ("violet", "输出分两层", ["事实层：解析结果，下游只读通过检查的（决定 3.9）",
                                 "判断层：诊断、标识、推荐颜色、退回草稿，给审核员（决定 2.3）",
                                 "每个节点的说明：docs/plan/2026-11-05_status_and_plan.zh.md 第 2 节"]),
    ],
    "en": [
        ("emerald", "Colour = status-board card", ["Light green: in-sample evidence + deliverable; yellow: partly done; red: not started",
                                                  "Tag = card ID; \"to revise\" = current code conflicts with the 2026-11-04 decisions, colour unchanged for now"]),
        ("cyan", "Main changes from v4 (2026-11-04 decisions)", ["Auto-reject pre-check and auto notice removed; every record goes to the model and to a reviewer (2.1, 2.2)",
                                                               "Blind parse: the model never sees Delta; on a mismatch it is told so, and every attempt is kept (3.1, 3.2)",
                                                               "We store our own parses for multi-level, cross-batch duplicate checks (4.1, 5.2)"]),
        ("violet", "Two output layers", ["Facts: the parse; downstream reads only records that passed the checks (3.9)",
                                        "Judgments: diagnostics, flags, colour, return draft; for the reviewer (2.3)",
                                        "Node notes: docs/plan/2026-11-05_status_and_plan.en.md section 2"]),
    ],
}

for lang in ("zh", "en"):
    zh = lang == "zh"
    m = meta[lang]
    doc = {
        "schema_version": 2, "diagram_type": "workflow",
        "meta": {"title": m["title"], "locale": m["locale"], "output": f"docs/status/pipeline_flow.{lang}.html",
                 "quality_profile": "showcase",
                 "legend": {"mode": "auto", "entries": {k: {"label": v} for k, v in m["legend"].items()}}},
        "lanes": [{"id": i, "label": z if zh else e} for i, z, e in lanes],
        "phases": [{"id": i, "label": z if zh else e, "fromCol": a, "toCol": b, **({"variant": v} if v else {})}
                   for i, z, e, a, b, v in phases],
        "mainPath": ["submit", "read", "nums", "llminput", "understand", "tool", "history", "flags", "decide", "review"],
        "nodes": [], "edges": [],
        "cards": [{"dot": d, "title": t, "items": it} for d, t, it in cards[lang]],
    }
    for i, lane, col, typ, zl, zs, el, es, zt, et, yo in nodes:
        n = {"id": i, "lane": lane, "col": col, "type": typ, "label": zl if zh else el, "sublabel": zs if zh else es}
        tag = zt if zh else et
        if tag:
            n["tag"] = tag
        if yo is not None:
            n["yOffset"] = yo
        doc["nodes"].append(n)
    for i, f, t, zl, el, role, var, fs, ts in edges:
        e = {"id": i, "from": f, "to": t, "label": zl if zh else el}
        for k, v in (("role", role), ("variant", var), ("fromSide", fs), ("toSide", ts)):
            if v:
                e[k] = v
        doc["edges"].append(e)
    (OUT / f"pipeline_flow.{lang}.workflow.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
print("written", len(nodes), "nodes", len(edges), "edges")
