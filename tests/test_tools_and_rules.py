"""L2 tool implementations, R1a recommendation order, budget ledger arithmetic, pipeline invariants."""

from freight_lineitems import budget
from freight_lineitems.checks import diag
from freight_lineitems.config import RULES
from freight_lineitems.disposition import flags_from, recommend
from freight_lineitems.pipeline import assemble, prepare
from freight_lineitems.tools import TOOLS, calculate, find_similar_examples, lookup_charge_code, lookup_tax_rule

from helpers import record


def test_at_least_five_tools_each_with_full_description():
    assert len(TOOLS) >= 5
    for t in TOOLS:
        d = t["description"]
        assert t["strict"] is True and "When to use" in d and "Returns" in d and "Failure modes" in d


def test_calculate_is_exact_and_closed():
    assert calculate("3 * 75") == {"result": "225"}
    assert calculate("13.00 + 15.00") == {"result": "28"}
    assert calculate("$1,234.50 - 0.50") == {"result": "1234"}
    assert "error" in calculate("__import__('os')")
    assert "error" in calculate("1/0")


def test_lookup_charge_code_finds_by_phrasing():
    assert lookup_charge_code("TAILGATE DELIVERY")["matches"][0]["code"] == "ACCESSORIAL.LIFTGATE"
    assert lookup_charge_code("ZZZ QQQ")["matches"] == []


def test_lookup_tax_rule():
    on = lookup_tax_rule("ON", "2022-01-01")
    assert on["components"] == [{"name": "HST", "rate": 0.13}]
    assert lookup_tax_rule("TX", "")["components"] == []
    assert "outside" in lookup_tax_rule("AB", "2025-01-01")["note"]


def test_find_similar_examples_excludes_self_and_shipment():
    lib = [{"example_id": "E1", "record_id": "a", "shipment_key": "S1", "marked_text": "SHORT PAID [#1 5]", "reading": {}, "note": ""},
           {"example_id": "E2", "record_id": "b", "shipment_key": "S2", "marked_text": "SHORT PAID [#1 7]", "reading": {}, "note": ""}]
    got = find_similar_examples("SHORT PAID", 3, lib, {"b"}, "S1")
    assert got["examples"] == []
    got = find_similar_examples("SHORT PAID", 3, lib, set(), None)
    assert [e["example_id"] for e in got["examples"]] == ["E1", "E2"]


def test_recommendation_order_attention_before_return():
    """Decision 2.3: people-first, then return, else passed."""
    ret = flags_from([diag("REC.TEXT.EMPTY", "text", {}, "1")])
    assert recommend(ret)["recommendation"] == "RETURN_SUGGESTED"
    both = flags_from([diag("REC.TEXT.EMPTY", "text", {}, "1"), diag("ITEM.TAX.PRESENT", "claim", {}, "4")])
    r = recommend(both)
    assert r["recommendation"] == "HUMAN_REVIEW" and r["return_draft"]["sent"] is False
    assert recommend(flags_from([diag("REC.TEXT.PII_REDACTED", "text", {}, "1")]))["recommendation"] == "PASSED_CHECKS"


def test_unconfigured_code_is_visible_not_silent():
    f = flags_from([diag("SOMETHING.NEW", "text", {}, "1")])
    assert f[0]["unconfigured"] and recommend(f)["recommendation"] == "HUMAN_REVIEW"


def test_every_return_flag_has_a_carrier_fix():
    for code, cfg in RULES["flags"].items():
        assert cfg["severity"] in ("info", "attention", "return"), code
        if cfg["severity"] == "return":
            assert cfg.get("carrier_fix"), code


def test_no_payment_decision_fields_in_output():
    out = assemble(prepare(record("DRIVER DETENTION $41.20", "41.20")), None)
    blob = str(out).lower()
    for word in ("approve", "should_pay", "payable", "valid_charge"):
        assert word not in blob


def test_model_not_run_is_explicit():
    out = assemble(prepare(record("DRIVER DETENTION $41.20", "41.20")), None)
    assert out["facts"]["parse_status"] == "NOT_RUN"
    assert "RUN.SUBMIT.NONE" in {f["code"] for f in out["judgment"]["flags"]}


def test_budget_cost_and_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, "LEDGER", tmp_path / "l.jsonl")
    u = budget.Usage(model="claude-sonnet-5-5", input=1_000_000, output=100_000, cache_write_5m=0, cache_write_1h=0,
                     cache_read=1_000_000, n_calls=1)
    assert abs(budget.cost_usd(u.as_dict()) - (2.0 + 1.0 + 0.1)) < 1e-9
    budget.append_entry("r", [u])
    assert abs(budget.spent_usd() - 3.1) < 1e-9
    cap = budget.CAP_USD   # expectation follows the configured cap (task 10 raised it from 50 to 110)
    assert budget.check_estimate(cap - 3.0)[0] is False and budget.check_estimate(cap - 4.0)[0] is True


def test_budget_reservations_block_concurrent_overrun(tmp_path, monkeypatch):
    """Audit M6."""
    monkeypatch.setattr(budget, "LEDGER", tmp_path / "l.jsonl")
    monkeypatch.setattr(budget, "RESERVATIONS", tmp_path / "r.json")
    part = budget.CAP_USD * 0.6
    assert budget.reserve("run1", part)[0] is True
    assert budget.reserve("run2", part)[0] is False          # 60% in flight + 60% > cap
    budget.release("run1")
    assert budget.reserve("run2", part)[0] is True


def test_non_ascii_is_info_not_injection():
    """Audit L7."""
    from freight_lineitems.pipeline import prepare
    p = prepare(record("NÃO COBRAR $62.00", "62"))
    codes = {d.code for d in p["pre_diags"]}
    assert "REC.TEXT.NON_ASCII" in codes and "REC.TEXT.INJECTION_SUSPECT" not in codes


# ---- task 10 section 1: 'return' only where code alone decides

def _rec(*codes):
    return recommend(flags_from([diag(c, "x", {}, "4") for c in codes]))["recommendation"]


def test_return_only_for_code_decided_flags():
    assert {c for c, f in RULES["flags"].items() if f["severity"] == "return"} == {"REC.TEXT.EMPTY", "REC.TEXT.NUMBERS_ONLY"}
    assert _rec("ITEM.AMOUNT.UNNAMED") == "HUMAN_REVIEW"
    assert _rec("ITEM.AMOUNT.MISSING") == "HUMAN_REVIEW"
    assert _rec("REC.TEXT.NO_NUMBER") == "HUMAN_REVIEW"


def test_subsumption_keeps_code_decided_returns():
    assert _rec("REC.TEXT.NUMBERS_ONLY", "ITEM.AMOUNT.UNNAMED") == "RETURN_SUGGESTED"
    assert _rec("REC.TEXT.EMPTY", "CLAIM.DELTA.FIRST_MISMATCH", "CLAIM.DELTA.MISMATCH_INSISTED") == "RETURN_SUGGESTED"
    # anything else that needs a person still wins, and the subsumed flag stays visible
    assert _rec("REC.TEXT.NUMBERS_ONLY", "ITEM.AMOUNT.UNNAMED", "DUP.ROW.COPY") == "HUMAN_REVIEW"
    assert _rec("REC.TEXT.EMPTY", "REC.FIELD.DELTA_ZERO") == "HUMAN_REVIEW"
    assert _rec("REC.TEXT.EMPTY", "RUN.AGENT.UNCERTAINTY_REPORTED") == "HUMAN_REVIEW"
    fl = flags_from([diag("REC.TEXT.NUMBERS_ONLY", "x", {}, "2"), diag("ITEM.AMOUNT.UNNAMED", "x", {}, "4")])
    un = next(f for f in fl if f["code"] == "ITEM.AMOUNT.UNNAMED")
    assert un["severity"] == "info" and un["subsumed_by"] == ["REC.TEXT.NUMBERS_ONLY"] and un["severity_before_subsumption"] == "attention"


def test_exclusion_basis_categories():
    from freight_lineitems.checks import exclusion_basis_category as cat
    assert cat("PREVIOUSLY PAID") == "paid" and cat("EACH") == "unit_rate" and cat("BALANCE DUE") == "total"
    assert cat("2 DAYS @ $50") == "unit_rate" and cat("CREDIT ISSUED") == "credit" and cat("RATE APPROVAL") in ("unit_rate", "reference")
    assert cat("ADD $100 TO THE FREIGHT") is None and cat("ONLY") is None and cat(None) is None
    assert cat("REPAIRED") is None          # whole words only: 'PAID' inside another word is not a basis
    assert RULES["flags"]["NUM.JUDGMENT.EXCLUSION_BASIS_UNLISTED"]["severity"] == "attention"
