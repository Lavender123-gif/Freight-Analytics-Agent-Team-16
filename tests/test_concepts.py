"""Task 19 step 1: one definition per concept (config/rules.yaml `concepts`) and one implementation in src/.

Synthetic examples only."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from freight_lineitems import claim
from freight_lineitems.config import RULES
from freight_lineitems.schemas import Kind, Status

SRC = Path(__file__).resolve().parents[1] / "src" / "freight_lineitems"
CONCEPTS = RULES["concepts"]


def _src_files():
    return sorted(SRC.glob("*.py"))


def test_counted_definition():
    assert claim.is_counted("CHARGE_AMOUNT", "CLAIMED")
    assert claim.is_counted(Kind.TAX_AMOUNT, Status.UNPAID)
    assert claim.is_counted("UNSPECIFIED_AMOUNT", "UNPAID")
    assert not claim.is_counted("TOTAL", "CLAIMED")          # a TOTAL is never counted, whatever its status
    assert not claim.is_counted("RATE", "NONE")
    assert not claim.is_counted("CHARGE_AMOUNT", "BILLED")
    assert claim.is_history("PAID") and claim.is_history(Status.DEDUCTED) and not claim.is_history("CLAIMED")
    assert claim.signed_amount(Decimal("20"), True) == Decimal("-20")
    assert claim.signed_amount(Decimal("20"), False) == Decimal("20")


def test_counted_ids_on_a_stored_reading():
    reading = {"numbers": [{"id": "#1", "kind": "CHARGE_AMOUNT", "status": "CLAIMED"},
                           {"id": "#2", "kind": "TOTAL", "status": "CLAIMED"},
                           {"id": "#3", "kind": "CHARGE_AMOUNT", "status": "PAID"}],
               "unrecognized_reads": [{"region_id": "?1", "as_number": {"id": "?1", "kind": "TAX_AMOUNT", "status": "UNPAID"}}]}
    assert claim.counted_ids(reading) == {"#1", "?1"}
    assert claim.counted_ids(None) == set()


def test_counted_statuses_are_spelled_out_only_in_claim_py():
    """No other module in src/ lists the counted or history statuses itself (T18 design 4.5: 'counted' had 4 copies)."""
    pats = [re.compile(r"[\"']CLAIMED[\"']\s*,\s*[\"']UNPAID[\"']"), re.compile(r"Status\.CLAIMED\s*,\s*Status\.UNPAID"),
            re.compile(r"[\"']BILLED[\"']\s*,\s*[\"']PAID[\"']\s*,\s*[\"']DEDUCTED[\"']"),
            re.compile(r"^\s*(COUNTED_STATUSES|HISTORY_STATUSES|COUNTED_KINDS)\s*[:=]", re.M)]
    for f in _src_files():
        if f.name == "claim.py":
            continue
        text = f.read_text()
        for p in pats:
            assert not p.search(text), f"{f.name} defines counted/history itself ({p.pattern}); call freight_lineitems.claim"


def test_one_function_per_concept_implementation():
    """Each concept's implementation names exactly one function, and that function is defined once in src/."""
    for cid, c in CONCEPTS.items():
        impl = c.get("implementation")
        if c["scope"] not in ("reading", "shipment") or not impl or impl.startswith("none"):
            continue
        mod, fn = impl.rsplit(".", 1)
        defs = [f.name for f in _src_files() if re.search(rf"^def {re.escape(fn)}\(", f.read_text(), re.M)]
        assert defs == [mod.split(".")[-1] + ".py"], f"{cid}: {fn} defined in {defs}"


def test_every_concept_has_both_definitions_and_scope():
    for cid, c in CONCEPTS.items():
        assert c["scope"] in ("reading", "shipment", "cross_explanation"), cid
        assert c.get("zh"), cid
        if c["scope"] == "reading":
            assert c.get("model"), cid
        elif c["scope"] == "shipment":       # task 20: code-only concepts; nothing of them is shown to the model
            assert not c.get("model") and c.get("implementation"), cid
        else:
            assert "next week" in c.get("status", ""), cid       # addendum: definition only, implemented next week
    required = {"counted", "history", "total", "credit", "quantity_rate", "exclusion_basis", "rate_correction", "other",
                "injection", "earlier_claim_mention", "balance_due", "stated_amount_due",
                "gap", "supersede", "add", "balance_due_cross", "order_copy", "same_amount_earlier", "history_echo"}
    assert required <= set(CONCEPTS)


def test_concept_keys_exist_in_rules():
    for cid, c in CONCEPTS.items():
        for key in c.get("keys", []):
            node = RULES
            if key.startswith("flags."):
                assert key[len("flags."):] in RULES["flags"], (cid, key)
                continue
            for part in key.split("."):
                assert part in node, (cid, key)
                node = node[part]
