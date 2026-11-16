"""The reading skill's text, generated from its templates and config/rules.yaml (task 19).

The skill folder holds templates: the core `SKILL.md` and the topic references in `reference/`. Every business
concept is written there as a placeholder `{{CONCEPT:<id>}}` and filled in from `rules.yaml` `concepts.<id>.model`,
so a concept has one definition (T18 design 4.5). Other placeholders: `{{EXCLUSION_WORDS}}` (rules.yaml
`exclusion_basis`), `{{TAXONOMY}}` (config/taxonomy.yaml), `{{TAX_TABLE}}` / `{{TAX_WINDOW}}` (config/tax_rules.yaml),
`{{TOOL_TABLE}}` (the tool definitions), `{{EXAMPLES}}` (worked examples).

Two layouts (config/model.yaml `skill_layout`; FL_SKILL_LAYOUT overrides it for one run):
- `routed`: the system prompt is the core with 2-3 generic examples; code adds the topic references and 1-2 similar
  examples an explanation needs to its input (features.py).
- `single`: the system prompt is the core with every topic reference appended and the fixed example set; the input
  carries nothing extra. Same generated text, no routing: the clean previous layout.
"""

from __future__ import annotations

import os
import re

import yaml

from freight_lineitems.config import CONFIG_DIR, RULES, SKILL_PATH, TAX

SKILL_DIR = SKILL_PATH.parent
REF_DIR = SKILL_DIR / "reference"
CONCEPT_RE = re.compile(r"\{\{CONCEPT:([a-z_]+)\}\}")
LAYOUTS = ("single", "routed")
REFERENCE_TITLES = {   # order in the single layout and in an explanation's notes
    "tax.md": "Tax", "balance_and_history.md": "Balances and payment history", "quantity_rate.md": "Quantity x rate",
    "rate_correction.md": "Rate corrections", "credit.md": "Credits and negative amounts"}


def layout() -> str:
    """`single` or `routed`."""
    lay = os.environ.get("FL_SKILL_LAYOUT") or yaml.safe_load((CONFIG_DIR / "model.yaml").read_text()).get("skill_layout", "single")
    if lay not in LAYOUTS:
        raise ValueError(f"unknown skill_layout {lay!r}")
    return lay


def exclusion_words_text() -> str:
    """The accepted exclusion words by reason, from rules.yaml `exclusion_basis.categories`."""
    cats = RULES["exclusion_basis"]["categories"]
    return "; ".join(f"{cat}: " + ", ".join(f"'{w}'" for w in words) for cat, words in cats.items())


def concept_text(cid: str) -> str:
    c = RULES["concepts"].get(cid)
    if c is None or not c.get("model"):
        raise KeyError(f"concept {cid!r} has no model text in rules.yaml")
    return " ".join(c["model"].split()).replace("{{EXCLUSION_WORDS}}", exclusion_words_text())


def tax_table_text() -> str:
    lines = ["| province | components |", "|---|---|"]
    for prov, rule in TAX["provinces"].items():
        comps = ", ".join(f"{k.upper()} {float(v) * 100:g}%" for k, v in rule.items() if k in ("gst", "hst", "pst", "qst"))
        if rule.get("pst_applies_to_freight") == "unknown":
            comps += " (whether PST/QST applies to freight is not known)"
        lines.append(f"| {prov} | {comps} |")
    return "\n".join(lines)


def tax_window_text() -> str:
    return f"rates in force {TAX['effective']['from']} to {TAX['effective']['to']}"


def tool_table_text() -> str:
    from freight_lineitems.tools import TOOLS
    rows = ["| tool | use it to |", "|---|---|"]
    for t in TOOLS:
        rows.append(f"| `{t['name']}` | {t['description'].split(chr(10))[0].rstrip('.')} |")
    return "\n".join(rows)


def render(text: str, examples: str | None = None) -> str:
    """Fill every placeholder. An unknown concept id raises KeyError."""
    from freight_lineitems.tools import taxonomy_for_prompt
    out = CONCEPT_RE.sub(lambda m: concept_text(m.group(1)), text)
    rep = {"{{EXCLUSION_WORDS}}": exclusion_words_text, "{{TAX_TABLE}}": tax_table_text, "{{TAX_WINDOW}}": tax_window_text,
           "{{TAXONOMY}}": taxonomy_for_prompt, "{{TOOL_TABLE}}": tool_table_text}
    for k, f in rep.items():
        if k in out:
            out = out.replace(k, f())
    if examples is not None:
        out = out.replace("{{EXAMPLES}}", examples)
    return out


def reference_names() -> list[str]:
    return list(REFERENCE_TITLES)


def reference_text(name: str) -> str:
    """One topic reference, rendered."""
    return render((REF_DIR / name).read_text()).strip()


def render_examples(examples: list[dict]) -> str:
    import json
    parts = []
    for e in examples:
        parts.append(f"### {e['example_id']}\nmarked_text: {e['marked_text']}\nreading: "
                     f"{json.dumps(e['reading'], separators=(',', ':'))}\nwhy: {e['note']}")
    return "\n\n".join(parts)


def system_prompt(lay: str, examples: list[dict]) -> str:
    """The system prompt for one layout. `examples` are the ones fixed in the prompt (routed: the generic ones;
    single: the whole fixed set)."""
    core = SKILL_PATH.read_text()
    if lay == "single":
        notes = "\n\n".join(reference_text(n).replace("# Topic note:", "### Topic note:", 1) for n in reference_names())
        notes = re.sub(r"\n\nCode added this note because [^\n]*(\n[^\n]+)*?\n\n", "\n\n", notes)
        core = core.replace("## 8. Worked examples", "## 8. Topic notes\n\nNotes for topics some texts touch; use the "
                            "ones your text needs.\n\n" + notes + "\n\n## 9. Worked examples")
        core = re.sub(r"Before the record, the message may hold `<topic_notes>`.*?what the\ntext says\.\n",
                      "Section 8 holds notes on topics some texts touch (tax, balances and payment history, quantity x "
                      "rate,\nrate corrections, credits).\n", core, flags=re.S)
    return render(core, render_examples(examples))
