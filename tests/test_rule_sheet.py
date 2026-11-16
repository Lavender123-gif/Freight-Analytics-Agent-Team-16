"""The plain-English rule sheet follows config/rules.yaml: every flag has wording, no wording is orphaned, and
docs/rule_sheet.en.md is the output of the generator for the current rules (regenerate it after any rule change)."""

import importlib.util
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parents[1] / "scratch" / "rules" / "build_rule_sheet.py"


def _gen():
    spec = importlib.util.spec_from_file_location("build_rule_sheet", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_flag_has_wording_and_nothing_is_orphaned():
    g = _gen()
    assert g.problems(yaml.safe_load(g.RULES.read_text()), yaml.safe_load(g.TEXT.read_text())) == []


def test_committed_sheet_is_up_to_date():
    g = _gen()
    assert g.main(["--check"]) == 0, "run: uv run python scratch/rules/build_rule_sheet.py"


def test_a_flag_without_wording_is_reported():
    g = _gen()
    rules, text = yaml.safe_load(g.RULES.read_text()), yaml.safe_load(g.TEXT.read_text())
    rules["flags"]["NEW.FLAG.WITHOUT_WORDS"] = {"severity": "attention"}
    del text["SHIP.COPY.SAME_OR_NO_PK"]
    errs = g.problems(rules, text)
    assert "no wording for flag NEW.FLAG.WITHOUT_WORDS" in errs and "no wording for flag SHIP.COPY.SAME_OR_NO_PK" in errs


def test_severity_in_the_sheet_is_the_one_in_rules_yaml():
    g = _gen()
    rules, text = yaml.safe_load(g.RULES.read_text()), yaml.safe_load(g.TEXT.read_text())
    rules["flags"]["REC.TEXT.EMPTY"]["severity"] = "info"
    sheet = g.render(rules, text)
    assert "| `REC.TEXT.EMPTY` | Info |" in sheet and "| `REC.TEXT.EMPTY` | Return |" not in sheet
