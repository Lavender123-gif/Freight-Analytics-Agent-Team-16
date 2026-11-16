"""Task 19 step 2: the reading skill's generated text, the two layouts, feature groups and the routing of topic
references and examples. Synthetic examples only."""

from __future__ import annotations

import json
import re

import pytest

from freight_lineitems import features, pipeline, skilltext
from freight_lineitems.config import RULES, SKILL_PATH

CONCEPTS = RULES["concepts"]
READING = [c for c, v in CONCEPTS.items() if v["scope"] == "reading"]
TEMPLATES = [SKILL_PATH] + sorted(skilltext.REF_DIR.glob("*.md"))
LIB = [
    {"example_id": "G1", "record_id": "g#1", "shipment_key": "SG1", "marked_text": "LUMPER FEE [#1 $50.00]", "reading": {}, "note": "n"},
    {"example_id": "T1", "record_id": "t#1", "shipment_key": "ST1", "marked_text": "LIFTGATE [#1 $40.00] + HST", "reading": {}, "note": "n"},
    {"example_id": "T2", "record_id": "t#2", "shipment_key": "ST2", "marked_text": "TAILGATE [#1 $15.00] PLUS GST", "reading": {}, "note": "n"},
    {"example_id": "B1", "record_id": "b#1", "shipment_key": "SB1", "marked_text": "BILLED [#1 $500] PAID [#2 $400] BALANCE DUE [#3 $100]", "reading": {}, "note": "n"},
    {"example_id": "Q1", "record_id": "q#1", "shipment_key": "SQ1", "marked_text": "DETENTION [#1 3] HOURS AT [#2 $60] PER HOUR + HST", "reading": {}, "note": "n"},
]
LIB = [e | {"groups": features.groups_of(features.unmark(e["marked_text"]))} for e in LIB]


def _prompt(lay):
    return pipeline.system_prompt(None, lay)


@pytest.mark.parametrize("lay", ["single", "routed"])
def test_no_placeholder_left(lay):
    s = _prompt(lay)
    assert not re.search(r"\{\{[A-Z_]+(:[a-z_]+)?\}\}", s)
    for n in skilltext.reference_names():
        assert "{{" not in skilltext.reference_text(n)


def test_every_reading_concept_is_used_by_a_template():
    used = {m for t in TEMPLATES for m in skilltext.CONCEPT_RE.findall(t.read_text())}
    assert set(READING) <= used, set(READING) - used
    assert used <= set(CONCEPTS)


def test_concept_texts_come_only_from_generation():
    """The templates never write a concept's definition by hand: its guard terms appear in no template file, and in
    the rendered single prompt each reading concept's text appears exactly once."""
    for t in TEMPLATES:
        raw = " ".join(t.read_text().split())
        for cid in READING:
            for g in CONCEPTS[cid].get("guard_terms", []):
                assert g not in raw, f"{t.name} writes part of concept {cid} by hand: {g!r}"
    single = " ".join(_prompt("single").split())
    for cid in READING:
        assert single.count(skilltext.concept_text(cid)) == 1, cid


def test_routed_core_holds_core_concepts_and_references_hold_the_rest():
    core = " ".join(_prompt("routed").split())
    in_refs = {m for p in skilltext.REF_DIR.glob("*.md") for m in skilltext.CONCEPT_RE.findall(p.read_text())}
    for cid in READING:
        n = core.count(skilltext.concept_text(cid))
        assert n == (0 if cid in in_refs else 1), cid


def test_exclusion_words_generated_from_rules():
    txt = skilltext.concept_text("exclusion_basis")
    for words in RULES["exclusion_basis"]["categories"].values():
        for w in words:
            assert f"'{w}'" in txt


def test_no_stale_content_in_prompt_or_tools():
    import json
    from freight_lineitems.tools import TOOLS
    for s in (_prompt("single"), _prompt("routed"), json.dumps(TOOLS)):
        low = s.lower()
        assert "inconsistent" not in low and "adjustment on record" not in low and "delta" not in low


def test_single_layout_has_every_reference_and_no_routing_sentence():
    s = _prompt("single")
    for n in skilltext.reference_names():
        title = skilltext.reference_text(n).splitlines()[0].replace("# Topic note:", "### Topic note:")
        assert title in s
    assert "<topic_notes>" not in s and "Code added this note" not in s


def test_layout_switch(monkeypatch):
    monkeypatch.setenv("FL_SKILL_LAYOUT", "single")
    assert skilltext.layout() == "single"
    monkeypatch.setenv("FL_SKILL_LAYOUT", "routed")
    assert skilltext.layout() == "routed"
    monkeypatch.setenv("FL_SKILL_LAYOUT", "other")
    with pytest.raises(ValueError):
        skilltext.layout()


# ------------------------------------------------------------------------------------------------ feature groups

@pytest.mark.parametrize("text,want", [
    ("LIFTGATE $40.00 + HST", {"tax"}),
    ("BILLED $500.00 PAID $400.00 BALANCE DUE $100.00", {"balance_paid_billed"}),
    ("DETENTION 3 HOURS AT $60.00 PER HOUR", {"unit_rate"}),
    ("TL FSC SHOULD APPLY", {"rate_correction"}),
    ("LESS CREDIT OF $20.00", {"credit_negative"}),
    ("FUEL SURCHARGE - $12.34", set()),                      # a spaced dash is a separator, not a minus sign
    ("ADJUSTMENT -$12.34", {"credit_negative"}),
    ("PREVIOUSLY SUBMITTED LUMPER", {"history"}),
    ("INSIDE DELIVERY $85.00", set()),
])
def test_groups_of(text, want):
    assert set(features.groups_of(text)) == want


def test_references_for_groups():
    assert features.references_for(["tax", "unit_rate"]) == ["tax.md", "quantity_rate.md"]
    assert features.references_for(["balance_paid_billed", "history"]) == ["balance_and_history.md"]
    assert features.references_for([]) == []
    assert set(RULES["features"]["references"]) == set(RULES["features"]["groups"])
    for f in RULES["features"]["references"].values():
        assert (skilltext.REF_DIR / f).exists()


def test_select_examples_shares_a_group_and_prefers_similar_wording(monkeypatch):
    monkeypatch.setitem(RULES["features"]["examples"], "generic_ids", ["G1"])
    got = features.select_examples("TAILGATE [#1 $15.00] + GST", ["tax"], LIB, set(), None)
    assert [e["example_id"] for e in got] == ["T2", "T1"]          # both tax; T2 shares more words
    got = features.select_examples("DETENTION [#1 2] HOURS AT [#2 $50] + HST", ["tax", "unit_rate"], LIB, set(), None)
    assert got[0]["example_id"] == "Q1"                             # two shared groups first


def test_select_examples_excludes_self_shipment_and_generic(monkeypatch):
    monkeypatch.setitem(RULES["features"]["examples"], "generic_ids", ["T1"])
    got = features.select_examples("TAILGATE [#1 $15.00] + GST", ["tax"], LIB, {"t#2"}, None)
    assert [e["example_id"] for e in got] == ["Q1"]
    got = features.select_examples("TAILGATE [#1 $15.00] + GST", ["tax"], LIB, set(), "ST2")
    assert [e["example_id"] for e in got] == ["Q1"]


def test_no_group_means_no_reference_and_no_example(monkeypatch):
    monkeypatch.setitem(RULES["features"]["examples"], "generic_ids", ["G1"])
    r = features.routing("INSIDE DELIVERY $85.00", "INSIDE DELIVERY [#1 $85.00]", LIB, set(), None)
    assert r == {"groups": [], "references": [], "examples": [], "preamble": ""}


def test_routing_preamble_holds_notes_and_examples(monkeypatch):
    monkeypatch.setitem(RULES["features"]["examples"], "generic_ids", ["G1"])
    r = features.routing("TAILGATE $15.00 + GST", "TAILGATE [#1 $15.00] + GST", LIB, set(), None)
    assert r["references"] == ["tax.md"] and len(r["examples"]) == 2
    assert r["preamble"].startswith("<topic_notes>\n# Topic note: tax")
    assert "<similar_examples>" in r["preamble"] and r["preamble"].endswith("\n\n")
    assert "| ON | HST 13% |" in r["preamble"]                       # the tax table replaces the tax-lookup tool


def test_generic_examples_follow_config_order(monkeypatch):
    monkeypatch.setitem(RULES["features"]["examples"], "generic_ids", ["B1", "missing", "G1"])
    assert [e["example_id"] for e in features.generic_examples(LIB)] == ["B1", "G1"]


def test_routed_input_reaches_the_model():
    """The first user message carries the routed preamble before the record (scripted fake client, no API call)."""
    from helpers import record
    from test_agent import FakeClient
    from freight_lineitems import budget
    from freight_lineitems.agent import Session, run_agent
    prep = pipeline.prepare(record("TAILGATE $15.00 + GST", "15"))
    sess = Session(ctx=prep["ctx"], llm_input=prep["llm_input"])
    fc = FakeClient([])
    tr = run_agent(sess, "SYSTEM", fc, {"model": "claude-sonnet-5-5", "max_tokens": 100}, budget.UsageBook(), [], set(),
                   None, preamble="<topic_notes>\nX\n</topic_notes>\n\n")
    assert re.search(r"<topic_notes>\nX\n</topic_notes>\n\n<dispute_record>", tr["first_user_message"])
    assert "<topic_notes>" in json.dumps(fc.requests[0]["messages"][0])
