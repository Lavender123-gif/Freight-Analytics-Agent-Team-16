"""The synthetic worked examples shipped in the skill folder (K1; pending P-06, decided: newly written synthetic
examples, not dev-split rows). Re-validates the committed file with the real parser, schema and mandatory checks,
and tests the explicit fallback in `tools.load_examples()`. No model call, no dev data."""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import pytest

from freight_lineitems import config, pipeline, tools
from freight_lineitems.checks import check_submission
from freight_lineitems.config import SYNTHETIC_EXAMPLES_PATH
from freight_lineitems.numbers import parse
from freight_lineitems.schemas import Submission
from helpers import ctx

EXAMPLES = json.loads(SYNTHETIC_EXAMPLES_PATH.read_text())
KEYS = ["example_id", "record_id", "shipment_key", "marked_text", "reading", "note"]   # same as the runtime library
MARKER = re.compile(r"\[[#D?]\d+ ([^\]]*)\]")


def source_text(marked: str) -> str:
    return MARKER.sub(lambda m: m.group(1), marked)


def test_file_shape_and_ids():
    assert len(EXAMPLES) == 5
    for k, e in enumerate(EXAMPLES, 1):
        assert list(e) == KEYS
        assert e["example_id"] == f"SYN-{k}"
        # placeholder keys that cannot collide with a real record ('dev#r<row>', 'mock#<id>') or a real shipment id
        assert e["record_id"] == f"synthetic#SYN-{k}" and e["shipment_key"] == f"SYNTHETIC.SYN-{k}"
        assert e["note"].strip()


@pytest.mark.parametrize("e", EXAMPLES, ids=[e["example_id"] for e in EXAMPLES])
def test_marked_text_is_what_the_parser_produces(e):
    text = source_text(e["marked_text"])
    p = parse(text)
    assert p.marked_text == e["marked_text"]
    assert p.coverage_ok and not p.unrecognized
    assert "[PERSON_" not in text and "@" not in text      # no names or emails, not even redacted ones


@pytest.mark.parametrize("e", EXAMPLES, ids=[e["example_id"] for e in EXAMPLES])
def test_reading_passes_schema_and_mandatory_checks(e):
    sub = Submission.model_validate(e["reading"])
    assert sub.response_type == "FIRST" and sub.reason is None
    errs, _diags, claim = check_submission(ctx(source_text(e["marked_text"])), sub)
    assert errs == []
    assert claim is not None and claim.counted_ids


def test_cases_covered():
    by = {e["example_id"]: e["reading"] for e in EXAMPLES}
    kinds = lambda r: [n["kind"] for n in r["numbers"]]          # noqa: E731
    statuses = lambda r: {n["status"] for n in r["numbers"]}     # noqa: E731
    assert len(by["SYN-1"]["numbers"]) == 1 and len(by["SYN-1"]["line_items"]) == 1               # single charge
    assert "TOTAL" in kinds(by["SYN-2"]) and by["SYN-2"]["relations"][0]["relation_type"] == "SUM"   # items + total
    assert {"BILLED", "PAID", "UNPAID"} <= statuses(by["SYN-3"])                                 # payment history
    assert by["SYN-4"]["relations"][0]["relation_type"] == "PRODUCT"                             # quantity x rate
    assert {"QUANTITY", "RATE", "REFERENCE"} <= set(kinds(by["SYN-4"]))                          # non-money numbers
    assert any(n["is_credit"] for n in by["SYN-5"]["numbers"])                                   # a credit
    assert any(li["amount_ref"] is None and li["charge_codes"] == ["TAX.GST"] for li in by["SYN-5"]["line_items"])


def test_system_prompt_renders_with_synthetic_examples():
    sp = pipeline.system_prompt(EXAMPLES)
    assert "{{" not in sp and "### SYN-1" in sp and "### SYN-5" in sp


def test_loader_falls_back_to_synthetic_with_a_warning():
    missing = Path(__file__).parent / "no_such_examples_file.json"
    with pytest.warns(UserWarning, match="synthetic"):
        assert tools.load_examples(missing) == EXAMPLES


def test_loader_is_silent_and_unchanged_when_the_file_exists():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert tools.load_examples(SYNTHETIC_EXAMPLES_PATH) == EXAMPLES


def test_versions_record_the_examples_source(monkeypatch):
    monkeypatch.setattr(config, "EXAMPLES_PATH", Path(__file__).parent / "no_such_examples_file.json")
    v = config.versions()
    assert v["examples_source"] == "synthetic" and v["examples_sha"] == config.file_sha(SYNTHETIC_EXAMPLES_PATH)
    monkeypatch.setattr(config, "SYNTHETIC_EXAMPLES_PATH", Path(__file__).parent / "no_such_file_either.json")
    assert config.versions()["examples_source"] == "missing" and config.versions()["examples_sha"] == "missing"


def test_versions_say_dev_redacted_when_the_real_file_is_present():
    if not config.EXAMPLES_PATH.exists():
        pytest.skip("git-ignored real examples file not present")
    v = config.versions()
    assert v["examples_source"] == "dev_redacted" and v["examples_sha"] == config.file_sha(config.EXAMPLES_PATH)
