"""Generate WORKFLOW.md (repository root, English) from pipeline_flow.en.workflow.json.

WORKFLOW.md is the only English copy of the pipeline flow: a Mermaid diagram that GitHub renders
in the browser, plus one sentence per step. The structure (lanes, nodes, edges, colours, card tags)
is read from the Archify source next to this script, so the diagram follows the same source as
the Chinese HTML. Only the one-sentence notes live here, in NOTES.

Run from the repo root (standard library only):
  python3 docs/status/flow_src/build_workflow_md.py            write WORKFLOW.md
  python3 docs/status/flow_src/build_workflow_md.py --check    exit 1 if WORKFLOW.md is stale
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC = HERE / "pipeline_flow.en.workflow.json"
OUT = ROOT / "WORKFLOW.md"

# One sentence per node of the diagram, keyed by node id. A node id missing here fails the build.
NOTES = {
    "submit": "The carrier submits an invoice adjustment with a free-text explanation in the transportation system; we receive it as an Excel export.",
    "read": "Code reads each row, keeps it unchanged, redacts names, emails and phone numbers, and marks text that looks like an instruction to the model.",
    "nums": "Code finds every number and date in the text, gives each an ID, and checks that every digit is covered.",
    "llminput": "Code builds the model input from the redacted text and the number table; Delta, carrier and Reason Code are left out.",
    "understand": "The model reads the text without seeing Delta and says what each numbered amount is (charge type, claimed or not, supporting words); it can only answer through `submit_line_items`.",
    "tool": "Code checks each submission: every number is accounted for, stated arithmetic holds, quoted words are in the text, and the claimed total is compared with Delta; on a mismatch the model is told once and may keep or revise its reading.",
    "history": "Code looks for the same dispute or the same charge appearing again, by row and by invoice (the shipment and cross-batch levels are optional and not built).",
    "flags": "Code turns all diagnostics into flags with one of three severities set in `config/rules.yaml`.",
    "decide": "Code derives one of three recommendations from the flags (passed checks, human review, return suggested); every record goes to a reviewer whatever the recommendation.",
    "draft": "When a return is suggested, code fills a draft message from fixed wording for the reviewer to edit; nothing is ever sent.",
    "store": "Each run is saved to SQLite and JSON with the parse (facts) kept apart from flags and recommendations (judgments); the downstream export contains only readings that passed the checks.",
    "review": "The reviewer opens each dispute in a local screen, sees the parse, flags and recommendation, and records a decision with a reason; the screen changes nothing outside our own store.",
    "pushback": "If the reviewer decides to return a dispute, they do it themselves in the transportation system; our tool does not contact the carrier.",
    "skill": "The procedure and worked examples the model follows (`skill/freight-dispute-line-items/SKILL.md`; the examples in the repository are synthetic).",
    "taxonomy": "The table of charge codes with their names and known phrasings (`config/taxonomy.yaml`).",
    "taxrules": "The tools the model may call and the tax-rate table used by the checks (`config/tax_rules.yaml`).",
    "rulesyaml": "The settings that decide flag severity, duplicate rules and the recommendation order (`config/rules.yaml`).",
    "catalog": "Fixed explanatory wording for every diagnostic code, shown to the reviewer and used in return drafts.",
}

CLASS = {  # Archify node type -> (Mermaid class, legend text, style)
    "backend": ("green", "Light green: built, run on the dev split, has a deliverable; in-sample evidence only",
                "fill:#e3f4e6,stroke:#2e7d32,color:#1b3d1f"),
    "cloud": ("yellow", "Yellow: partly done", "fill:#fff6d1,stroke:#b8860b,color:#4d3800"),
    "security": ("red", "Red: not started", "fill:#fbe1e0,stroke:#c62828,color:#4a1010"),
    "external": ("plain", "White: a person or outside system, no status card", "fill:#ffffff,stroke:#8a94a6,color:#1f2937"),
}


def q(s: str) -> str:
    """Text safe inside a quoted Mermaid label."""
    return s.replace('"', "#quot;")


def render() -> str:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    nodes, lanes = d["nodes"], d["lanes"]
    missing = [n["id"] for n in nodes if n["id"] not in NOTES]
    if missing or len(NOTES) != len(nodes):
        raise SystemExit(f"NOTES and the diagram disagree: missing {missing}, "
                         f"extra {sorted(set(NOTES) - {n['id'] for n in nodes})}")
    lane_label = {ln["id"]: ln["label"] for ln in lanes}
    m = ["flowchart LR"]
    for ln in lanes:
        m.append(f'  subgraph {ln["id"]}["{q(ln["label"])}"]')
        for n in sorted((n for n in nodes if n["lane"] == ln["id"]), key=lambda n: (n["col"], n.get("yOffset", 0))):
            m.append(f'    {n["id"]}["{q(n["label"])}<br/>{q(n["sublabel"])}"]')
        m.append("  end")
    for e in d["edges"]:
        arrow = "-.->" if e.get("variant") == "dashed" else "-->"
        m.append(f'  {e["from"]} {arrow}|"{q(e["label"])}"| {e["to"]}')
    for cls, _, style in CLASS.values():
        m.append(f"  classDef {cls} {style}")
    for t, (cls, _, _) in CLASS.items():
        ids = [n["id"] for n in nodes if n["type"] == t]
        if ids:
            m.append(f'  class {",".join(ids)} {cls}')

    main = d["mainPath"]
    by_id = {n["id"]: n for n in nodes}

    def row(n: dict) -> str:
        card = n.get("tag", "").replace(" · to revise", "") or "none"
        return f'| {n["label"]} | {lane_label[n["lane"]]} | {NOTES[n["id"]]} | {card} |'

    off_path = [n for n in nodes if n["id"] not in main and n["lane"] != "assets"]
    assets = [n for n in nodes if n["lane"] == "assets" and n["id"] not in main]
    head = "| Step | Who does it | What happens | Card |\n|---|---|---|---|"
    out = [
        "<!-- Generated by docs/status/flow_src/build_workflow_md.py from pipeline_flow.en.workflow.json; do not edit by hand -->",
        "# Workflow",
        "",
        "How one freight adjustment dispute moves through the system, from the carrier's free text to a reviewer's "
        "decision. The system never decides whether a charge should be paid: it produces a structured reading, "
        "checks it, and raises flags for a person.",
        "",
        "```mermaid",
        *m,
        "```",
        "",
        "Boxes are grouped by who does the work. Solid arrows are the forward flow; dashed arrows go back to an earlier "
        "step or to the store. Box colour is the status of the matching card in [`STATUS.md`](STATUS.md):",
        "",
        *[f"- {legend}" for t, (_, legend, _) in CLASS.items() if any(n["type"] == t for n in nodes)],
        "",
        "## Main path, in order",
        "",
        head,
        *[row(by_id[i]) for i in main],
        "",
        "## Side steps",
        "",
        head,
        *[row(n) for n in off_path],
        "",
        "## Knowledge assets the steps read",
        "",
        head.replace("| Step |", "| Asset |").replace("| Who does it |", "| Lane |").replace("| What happens |", "| What it is |"),
        *[row(n) for n in assets],
        "",
        "## Source",
        "",
        "The diagram is generated from [`docs/status/flow_src/pipeline_flow.en.workflow.json`](docs/status/flow_src/pipeline_flow.en.workflow.json) "
        "by [`build_workflow_md.py`](docs/status/flow_src/build_workflow_md.py) in the same folder; how to change it is in "
        "[`docs/status/flow_src/README.md`](docs/status/flow_src/README.md). An interactive version exists in Chinese only: "
        "`docs/status/pipeline_flow.zh.html` (download it and open it in a browser). Longer notes per step (why each step "
        "is designed this way) are in [`docs/architecture.md`](docs/architecture.md).",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("WORKFLOW.md is up to date" if ok else "WORKFLOW.md differs from a fresh render")
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
