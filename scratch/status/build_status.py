"""Generate the status board from docs/status/cards.yaml: Chinese to docs/status/project_status.zh.md,
English to STATUS.md in the repository root (the only English copy; task 11).

cards.yaml is the single source of the status board; the two Markdown boards are generated
and must not be edited by hand. Links in cards.yaml are written relative to docs/status/; for the
root English board they are rebased to the repository root.

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
  - plan mapping (task 10): every card has a tier; Must cards name Must tasks of docs/status/progress.yaml;
    every Must task has at least one card; cards outside Must have weight 0
  - the boards on disk equal a fresh render (catches hand edits)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/status/cards.yaml"
PLAN = ROOT / "docs/status/progress.yaml"   # the 23 Must tasks: hours, owner, status (task 10)
STATUS_EN = {"未做": "not done", "已做待验收": "done, awaiting acceptance", "已验收": "accepted"}
OWNER_EN = {"CC": "CC", "人工": "manual"}
OUT_DIR = ROOT / "docs/status"          # links in cards.yaml and rel() are relative to this folder
OUT = {"zh": OUT_DIR / "project_status.zh.md", "en": ROOT / "STATUS.md"}
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
        "authoritative": "**中文版为准**；英文版在仓库根目录 [`STATUS.md`](../../STATUS.md)，结构相同，由同一份数据生成。",
        "progress": "整体进度", "shaped": "成型度", "verified": "验证度",
        "progress_count": "张", "all_cards": "上面一行的颜色计数是全部 {n} 张卡，含不进分母的。", "progress_formula": "计算方法",
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
        "must": "Must 清单（11 月 5 日计划）", "col_plan": "计划任务", "col_task": "任务", "col_hours": "人时",
        "col_owner": "负责方", "col_task_status": "任务状态", "col_cards": "对应卡片", "tier": "层",
        "denominator": "Must 分母", "outside": "不进分母",
        "must_legend": "任务状态（未做 / 已做待验收 / 已验收）按计划里的完成标准记，由 `progress.yaml` 维护；卡片颜色按证据定。两者不是一回事：任务做完了，卡片仍可能是黄的（证据或交付物还不够）。",
        "edges_from_yaml": "分栏和连线来自 `cards.yaml` 的 `columns`、`overview_edges`；节点颜色即卡片颜色。",
    },
    "en": {
        "title": "Project status board", "sep": ": ", "period": ". ",
        "generated": "Generated from [`cards.yaml`](cards.yaml); do not edit by hand.",
        "generated_how": "Change card content in `cards.yaml` only, then run `sh scratch/status/run.sh` from the repo root to regenerate both languages.",
        "updated": "Last updated", "task": "Updated by task",
        "authoritative": "**The Chinese version [`project_status.zh.md`](project_status.zh.md) is authoritative**; this English version has the same structure and is generated from the same data.",
        "progress": "Overall progress", "shaped": "Shaped", "verified": "Verified",
        "progress_count": "cards", "all_cards": "The colour counts on the line above cover all {n} cards, including those outside the denominator.", "progress_formula": "How it is computed",
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
        "must": "Must list (2026-11-05 plan)", "col_plan": "Plan task", "col_task": "Task", "col_hours": "Hours",
        "col_owner": "Owner", "col_task_status": "Task status", "col_cards": "Cards", "tier": "Tier",
        "denominator": "Must denominator", "outside": "outside the denominator",
        "must_legend": "Task status (not done / done, awaiting acceptance / accepted) follows the plan's done-when text and is kept in `progress.yaml`; card colour follows evidence. They are different things: a task can be done while its card is still yellow (evidence or deliverable still short).",
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


_LINK = re.compile(r"\]\(([^)\s#]+)(#[^)\s]*)?\)")


def rebase_links(md: str, out: Path) -> str:
    """Rewrite relative Markdown links (written relative to docs/status/) for a board saved at `out`."""
    if out.parent == OUT_DIR:
        return md

    def fix(m: re.Match) -> str:
        target, frag = m.group(1), m.group(2) or ""
        if re.match(r"[a-z]+:", target):
            return m.group(0)
        r = os.path.relpath(os.path.normpath(OUT_DIR / target), out.parent)
        return f"]({r}{'/' if target.endswith('/') else ''}{frag})"
    return _LINK.sub(fix, md)


def load_plan() -> list[dict]:
    return yaml.safe_load(PLAN.read_text(encoding="utf-8"))["tasks"]


def must_rows(data: dict, plan: list[dict], lang: str) -> list[dict]:
    """One row per Must task, in plan order, with the cards mapped to it."""
    rows = []
    for t in plan:
        cards = [c for c in data["cards"] if t["id"] in c.get("plan_tasks", [])]
        rows.append({"id": t["id"], "name": t["name"][lang], "hours": f"{t['hours'][0]}–{t['hours'][1]}",
                     "owner": t["owner"] if lang == "zh" else OWNER_EN[t["owner"]],
                     "status": t["status"] if lang == "zh" else STATUS_EN[t["status"]], "cards": cards})
    return rows


def progress(data: dict) -> dict:
    cards = [c for c in data["cards"] if c["color"] != "grey" and c.get("tier") == "must"]
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
            "counts": counts, "n_must": len(cards),
            "outside": {t: sum(1 for c in data["cards"] if c.get("tier") == t) for t in data["meta"]["tiers"] if t != "must"},
            "grey_must": sum(1 for c in data["cards"] if c["color"] == "grey" and c.get("tier") == "must")}


def render(data: dict, lang: str, plan: list[dict]) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES), trim_blocks=True,
                             lstrip_blocks=True, keep_trailing_newline=True,
                             undefined=jinja2.StrictUndefined)
    env.filters["rel"] = rel
    tpl = env.get_template("project_status.md.j2")
    by_col = {c["id"]: [k for k in data["cards"] if k["column"] == c["id"]] for c in data["columns"]}
    md = tpl.render(d=data, m=data["meta"], L=LABELS[lang], lang=lang, by_col=by_col,
                    p=progress(data), items=ITEMS, must=must_rows(data, plan, lang))
    return rebase_links(md, OUT[lang])


def check(data: dict, rendered: dict[str, str], plan: list[dict]) -> list[str]:
    errs: list[str] = []
    meta = data["meta"]
    ids = [c["id"] for c in data["cards"]]
    must_ids = [t["id"] for t in plan]
    for t in plan:
        if t["status"] not in STATUS_EN or t["owner"] not in OWNER_EN:
            errs.append(f"progress.yaml {t['id']}: unknown status or owner")
        if not any(t["id"] in c.get("plan_tasks", []) for c in data["cards"]):
            errs.append(f"Must task {t['id']} has no card")
    for c in data["cards"]:
        tier = c.get("tier")
        if tier not in meta["tiers"]:
            errs.append(f"{c['id']}: unknown or missing tier {tier}")
        if not isinstance(c.get("plan_tasks"), list):
            errs.append(f"{c['id']}: missing plan_tasks")
        elif tier == "must" and (not c["plan_tasks"] or any(t not in must_ids for t in c["plan_tasks"])):
            errs.append(f"{c['id']}: a Must card must name Must tasks, got {c['plan_tasks']}")
        elif tier != "must" and any(t in must_ids for t in c["plan_tasks"]):
            errs.append(f"{c['id']}: a card outside Must names a Must task")
        if tier != "must" and c.get("weight") != 0:
            errs.append(f"{c['id']}: cards outside Must must have weight 0")
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
        out = OUT[lg]
        if not out.exists() or out.read_text(encoding="utf-8") != rendered[lg]:
            errs.append(f"{out.relative_to(ROOT)} differs from a fresh render of cards.yaml "
                        "(hand-edited or not regenerated)")
    return errs


def main(argv: list[str]) -> int:
    data = load()
    plan = load_plan()
    rendered = {lg: render(data, lg, plan) for lg in LANGS}
    if "--check" not in argv:
        for lg in LANGS:
            OUT[lg].write_text(rendered[lg], encoding="utf-8")
            print(f"wrote {OUT[lg].relative_to(ROOT)}")
    errs = check(data, rendered, plan)
    p = progress(data)
    print(f"Must denominator {p['n_must']} cards; shaped {p['shaped']}/{p['total']} ({p['shaped_pct']}%), "
          f"verified {p['verified']}/{p['total']} ({p['verified_pct']}%), colours {p['counts']}")
    for e in errs:
        print("CHECK FAIL:", e)
    print("checks:", "all passed" if not errs else f"{len(errs)} failed")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
