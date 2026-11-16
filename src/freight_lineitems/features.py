"""Feature groups and routing for the reading skill (task 19, T18 design 4.3).

Code, not the model, picks what an explanation needs: the topic references whose feature group the text matches
(rules.yaml `features.groups` -> `features.references`), and up to `features.examples.max_in_input` worked examples
that share a group with it, most shared groups first, then word similarity with numbers masked. An explanation that
matches no group gets no reference and no extra example. Examples never come from the explanation itself or its
shipment.
"""

from __future__ import annotations

import json
import re

from freight_lineitems.config import EXAMPLES_PATH, RULES, SYNTHETIC_EXAMPLES_PATH

FEAT = RULES["features"]
GROUPS = {k: re.compile(v) for k, v in FEAT["groups"].items()}
MARKER_RE = re.compile(r"\[[#D?]\d+ ([^\]]*)\]")


def groups_of(text: str | None) -> list[str]:
    """The feature groups an (upper-cased) text matches, in rules.yaml order."""
    t = (text or "").upper()
    return [k for k, rx in GROUPS.items() if rx.search(t)]


def references_for(groups: list[str]) -> list[str]:
    """Reference file names for the groups, without repeats, in the order of the skill's reference list."""
    from freight_lineitems.skilltext import reference_names
    want = {FEAT["references"][g] for g in groups if g in FEAT["references"]}
    return [n for n in reference_names() if n in want]


def unmark(marked_text: str) -> str:
    """Marked text back to plain text ('[#1 $15.00]' -> '$15.00')."""
    return MARKER_RE.sub(r"\1", marked_text)


def _words(s: str) -> set[str]:
    s = re.sub(r"\[[#D?]\d+ [^\]]*\]", " N ", s)
    return set(re.findall(r"[A-Z]+", s.upper()))


def similarity(a: str, b: str) -> float:
    """Jaccard similarity of the word sets of two marked texts, numbers masked."""
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / max(len(wa | wb), 1)


def example_library() -> list[dict]:
    """Every worked example available: the redacted dev examples (git-ignored, when present) and the synthetic
    examples shipped in the skill folder. Each gets its feature groups computed from its text."""
    out, seen = [], set()
    for p in (EXAMPLES_PATH, SYNTHETIC_EXAMPLES_PATH):
        if p.exists():
            for e in json.loads(p.read_text()):
                if e["example_id"] not in seen:
                    seen.add(e["example_id"])
                    out.append(e | {"groups": groups_of(unmark(e["marked_text"]))})
    return out


def generic_examples(library: list[dict]) -> list[dict]:
    """The examples fixed in the routed system prompt (rules.yaml `features.examples.generic_ids`, in that order)."""
    by_id = {e["example_id"]: e for e in library}
    return [by_id[i] for i in FEAT["examples"]["generic_ids"] if i in by_id]


def select_examples(marked_text: str, groups: list[str], library: list[dict], exclude_record_ids: set[str],
                    exclude_shipment: str | None) -> list[dict]:
    """Up to max_in_input examples sharing at least min_shared_groups groups with the explanation; never a generic
    example (already in the prompt), the explanation itself or another explanation of its shipment."""
    cfg = FEAT["examples"]
    generic = set(cfg["generic_ids"])
    pool = [e for e in library if e["example_id"] not in generic and e["record_id"] not in exclude_record_ids
            and (exclude_shipment is None or e.get("shipment_key") != exclude_shipment)]
    scored = []
    for e in pool:
        shared = len(set(groups) & set(e["groups"]))
        if shared >= cfg["min_shared_groups"] and shared > 0:
            scored.append((-shared, -similarity(marked_text, e["marked_text"]), e["example_id"], e))
    scored.sort(key=lambda x: x[:3])
    return [x[3] for x in scored[: cfg["max_in_input"]]]


def routing(redacted_text: str, marked_text: str, library: list[dict], exclude_record_ids: set[str],
            exclude_shipment: str | None) -> dict:
    """What code adds to one explanation's input in the routed layout: {groups, references, examples, preamble}."""
    from freight_lineitems.skilltext import reference_text, render_examples
    g = groups_of(redacted_text)
    refs = references_for(g)
    exs = select_examples(marked_text, g, library, exclude_record_ids, exclude_shipment)
    parts = []
    if refs:
        parts.append("<topic_notes>\n" + "\n\n".join(reference_text(n) for n in refs) + "\n</topic_notes>")
    if exs:
        parts.append("<similar_examples>\n" + render_examples(exs) + "\n</similar_examples>")
    return {"groups": g, "references": refs, "examples": [e["example_id"] for e in exs],
            "preamble": "\n\n".join(parts) + ("\n\n" if parts else "")}
