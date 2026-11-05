"""Generate docs/status/project_status.{zh,en}.md from docs/status/cards.yaml.

cards.yaml is the single source of the status board; the two Markdown boards are generated
and must not be edited by hand.

Usage (from the repo root; `run.sh` wraps the uv command):
  sh scratch/status/run.sh            regenerate both boards, then run the checks
  sh scratch/status/run.sh --check    checks only; exit 1 if anything fails, incl. a stale board

Checks
  - every card has the required fields, every text field has both zh and en
  - overview edges and colours / evidence levels refer to known ids
  - colour rules: light green needs a deliverable folder, a test report and at least in-sample
    evidence; dark green needs independent / human-review evidence and threshold_preset: true;
    a yellow card with evidence needs a test report; every non-dark-green card states needs_b04
  - every linked file or folder exists; every test report states the card's evidence level
  - the boards on disk equal a fresh render (catches hand edits)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/status/cards.yaml"
OUT_DIR = ROOT / "docs/status"
TEMPLATES = Path(__file__).with_name("templates")
LANGS = ("zh", "en")
ITEMS = ["what_is", "status_detail", "deliverable_note", "start_conditions",
         "approach", "depends", "open_items", "completion_text"]
GREENS = ("light_green", "dark_green")

LABELS = {
    "zh": {
        "title": "项目状态看板", "sep": "：", "period": "。",
        "generated": "由 [`cards.yaml`](cards.yaml) 生成，不要手改。",
        "generated_how": "改卡片内容只改 `cards.yaml`，然后在仓库根目录运行 `sh scratch/status/run.sh` 重新生成中英两版。",
        "updated": "最后更新", "task": "更新它的任务",
        "authoritative": "**中文版为准**；英文版 [`project_status.en.md`](project_status.en.md) 结构相同，由同一份数据生成。",
        "progress": "整体进度", "shaped": "成型度", "verified": "验证度",
        "progress_count": "张数", "progress_formula": "计算方法",
        "standard": "颜色和证据级别标准", "color": "颜色", "meaning": "含义",
        "evidence": "证据级别", "evidence_intro": "每份测试报告开头标明证据级别：",
        "rules": "规则", "overview": "总览图", "table": "卡片总表",
        "col_id": "编号", "col_card": "卡片", "col_status": "一句话现状",
        "col_summary": "摘要", "col_deliv": "交付物", "col_report": "测试报告",
        "none": "无", "summary_link": "摘要", "folder": "文件夹", "report": "报告",
        "what_is": "是什么", "one_screen": "一屏摘要",
        "claim": "声称做到了什么", "tested": "测了什么", "data": "用什么数据",
        "result_vs_threshold": "结果对比门槛", "limits": "局限",
        "no_summary": "还没有检验结果。",
        "status_detail": "现状与依据",
        "links": "交付物和测试报告", "deliverable": "交付物", "test_report": "测试报告",
        "deliverable_note": "说明",
        "completion": "完成标准", "completion_text": "完成标准（原文）",
        "criteria": "升到 {target} 的检验", "method": "检验方法",
        "threshold": "门槛", "preset": "门槛是否在跑检验之前写定",
        "yes": "是", "no": "否",
        "start_conditions": "开始条件", "approach": "做法",
        "depends": "前置依赖与被谁依赖", "open_items": "待决事项（写明谁决定）",
        "needs_b04": "升到下一档是否依赖 B04",
        "b04": {"yes": "依赖", "no": "不依赖", "partly": "部分依赖", "self": "本卡即 B04", "n/a": "不适用"},
        "kind_analysis": "分析类卡片：\"检验\"是脚本可复现与数字核对。",
        "back": "回到总表",
        "edges_from_yaml": "分栏和连线来自 `cards.yaml` 的 `columns`、`overview_edges`；节点颜色即卡片颜色。",
    },
    "en": {
        "title": "Project status board", "sep": ": ", "period": ". ",
        "generated": "Generated from [`cards.yaml`](cards.yaml); do not edit by hand.",
        "generated_how": "Change card content in `cards.yaml` only, then run `sh scratch/status/run.sh` from the repo root to regenerate both languages.",
        "updated": "Last updated", "task": "Updated by task",
        "authoritative": "**The Chinese version [`project_status.zh.md`](project_status.zh.md) is authoritative**; this English version has the same structure and is generated from the same data.",
        "progress": "Overall progress", "shaped": "Shaped", "verified": "Verified",
        "progress_count": "cards", "progress_formula": "How it is computed",
        "standard": "Colour and evidence standard", "color": "Colour", "meaning": "Meaning",
        "evidence": "Evidence level", "evidence_intro": "Every test report states its evidence level at the top:",
        "rules": "Rules", "overview": "Overview", "table": "Card table",
        "col_id": "ID", "col_card": "Card", "col_status": "Status in one line",
        "col_summary": "Summary", "col_deliv": "Deliverable", "col_report": "Test report",
        "none": "none", "summary_link": "summary", "folder": "folder", "report": "report",
        "what_is": "What it is", "one_screen": "One-screen summary",
        "claim": "Claim", "tested": "What was tested", "data": "Data",
        "result_vs_threshold": "Result vs threshold", "limits": "Limitations",
        "no_summary": "No test results yet.",
        "status_detail": "Status and evidence",
        "links": "Deliverable and test report", "deliverable": "Deliverable", "test_report": "Test report",
        "deliverable_note": "Note",
        "completion": "Done when", "completion_text": "Done when (original text)",
        "criteria": "Check for moving up to {target}", "method": "Method",
        "threshold": "Threshold", "preset": "Threshold written down before the check runs",
        "yes": "yes", "no": "no",
        "start_conditions": "Start condition", "approach": "Approach",
        "depends": "Depends on / needed by", "open_items": "Open items (with who decides)",
        "needs_b04": "Does moving up a level depend on B04",
        "b04": {"yes": "yes", "no": "no", "partly": "partly", "self": "this card is B04", "n/a": "not applicable"},
        "kind_analysis": "Analysis card: the \"check\" is script reproducibility and number cross-checking.",
        "back": "back to the card table",
        "edges_from_yaml": "Columns and edges come from `columns` and `overview_edges` in `cards.yaml`; node colour = card colour.",
    },
}


def load() -> dict:
    return yaml.safe_load(SRC.read_text(encoding="utf-8"))


def rel(path: str | None) -> str | None:
    """Repo-relative path -> link relative to docs/status (keeps a trailing slash for folders)."""
    if not path:
        return None
    r = os.path.relpath(ROOT / path, OUT_DIR)
    return r + "/" if path.endswith("/") else r


def progress(data: dict) -> dict:
    cards = [c for c in data["cards"] if c["color"] != "grey"]
    total = sum(c["weight"] for c in cards)
    credit = data["meta"]["progress"]["yellow_credit"]
    shaped = sum(c["weight"] for c in cards if c["color"] in GREENS) \
        + credit * sum(c["weight"] for c in cards if c["color"] == "yellow")
    verified = sum(c["weight"] for c in cards if c["color"] == "dark_green")
    counts = {k: sum(1 for c in data["cards"] if c["color"] == k) for k in data["meta"]["colors"]}

    def fmt(x):
        return f"{x:g}"
    return {"total": fmt(total), "shaped": fmt(shaped), "verified": fmt(verified),
            "shaped_pct": round(100 * shaped / total), "verified_pct": round(100 * verified / total),
            "counts": counts}


def render(data: dict, lang: str) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES), trim_blocks=True,
                             lstrip_blocks=True, keep_trailing_newline=True,
                             undefined=jinja2.StrictUndefined)
    env.filters["rel"] = rel
    tpl = env.get_template("project_status.md.j2")
    by_col = {c["id"]: [k for k in data["cards"] if k["column"] == c["id"]] for c in data["columns"]}
    return tpl.render(d=data, m=data["meta"], L=LABELS[lang], lang=lang, by_col=by_col,
                      p=progress(data), items=ITEMS)


def check(data: dict, rendered: dict[str, str]) -> list[str]:
    errs: list[str] = []
    meta = data["meta"]
    ids = [c["id"] for c in data["cards"]]
    if len(ids) != len(set(ids)):
        errs.append("duplicate card ids")
    cols = {c["id"] for c in data["columns"]}

    def bilingual(obj, where):
        if isinstance(obj, dict):
            if set(obj) == set(LANGS):
                for lg in LANGS:
                    if where.endswith(".lead") and obj[lg] == "":
                        continue  # an item may have only bullets; both languages then have ""
                    if not (isinstance(obj[lg], (str, list)) and obj[lg]):
                        errs.append(f"{where}: empty {lg}")
                return
            if set(obj) & set(LANGS):
                errs.append(f"{where}: has {sorted(set(obj) & set(LANGS))} but not both languages")
            for k, v in obj.items():
                bilingual(v, f"{where}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                bilingual(v, f"{where}[{i}]")

    bilingual(data, "cards.yaml")
    for chain in data["overview_edges"]:
        for n in chain:
            if n not in ids:
                errs.append(f"overview edge refers to unknown card {n}")
    for c in data["cards"]:
        cid = c["id"]
        for k in ("id", "column", "name", "kind", "weight", "color", "evidence_level", "status_line"):
            if k not in c:
                errs.append(f"{cid}: missing {k}")
        if c.get("column") not in cols:
            errs.append(f"{cid}: unknown column {c.get('column')}")
        if c.get("color") not in meta["colors"]:
            errs.append(f"{cid}: unknown colour {c.get('color')}")
        if c.get("evidence_level") not in meta["evidence_levels"]:
            errs.append(f"{cid}: unknown evidence level {c.get('evidence_level')}")
        if c["color"] != "grey":
            for k in ITEMS:
                if k not in c:
                    errs.append(f"{cid}: missing legacy item {k}")
            if "criteria" not in c:
                errs.append(f"{cid}: missing criteria")
        for p in [c.get("deliverable_dir")] + list((c.get("test_report") or {}).values()):
            if p and not (ROOT / p).exists():
                errs.append(f"{cid}: linked path does not exist: {p}")
        color, ev = c["color"], c["evidence_level"]
        if color in GREENS and not (c.get("deliverable_dir") and c.get("test_report")):
            errs.append(f"{cid}: {color} needs a deliverable folder and a test report")
        if color == "light_green" and ev == "none":
            errs.append(f"{cid}: light green needs at least in-sample evidence")
        if color == "dark_green":
            if ev not in ("independent", "human_review"):
                errs.append(f"{cid}: dark green needs independent or human-review evidence")
            if not (c.get("criteria") or {}).get("threshold_preset"):
                errs.append(f"{cid}: dark green needs a threshold written down in advance")
        if color == "yellow" and ev != "none" and not c.get("test_report"):
            errs.append(f"{cid}: yellow card with evidence needs a test report")
        if color in GREENS and "summary" not in c:
            errs.append(f"{cid}: {color} needs a one-screen summary")
        if color != "dark_green" and "needs_b04" not in c:
            errs.append(f"{cid}: non-dark-green card must state needs_b04")
        for lg, p in (c.get("test_report") or {}).items():
            f = ROOT / p
            if f.exists():
                head = "\n".join(f.read_text(encoding="utf-8").splitlines()[:12])
                want = meta["evidence_levels"][ev]["name"][lg]
                if want not in head:
                    errs.append(f"{cid}: {p} does not state evidence level '{want}' near the top")
    for lg in LANGS:
        out = OUT_DIR / f"project_status.{lg}.md"
        if not out.exists() or out.read_text(encoding="utf-8") != rendered[lg]:
            errs.append(f"{out.relative_to(ROOT)} differs from a fresh render of cards.yaml "
                        "(hand-edited or not regenerated)")
    return errs


def main(argv: list[str]) -> int:
    data = load()
    rendered = {lg: render(data, lg) for lg in LANGS}
    if "--check" not in argv:
        for lg in LANGS:
            (OUT_DIR / f"project_status.{lg}.md").write_text(rendered[lg], encoding="utf-8")
            print(f"wrote docs/status/project_status.{lg}.md")
    errs = check(data, rendered)
    p = progress(data)
    print(f"shaped {p['shaped']}/{p['total']} ({p['shaped_pct']}%), "
          f"verified {p['verified']}/{p['total']} ({p['verified_pct']}%), colours {p['counts']}")
    for e in errs:
        print("CHECK FAIL:", e)
    print("checks:", "all passed" if not errs else f"{len(errs)} failed")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
