"""T14-05: the deterministic mapping from internal codes to the client's names and EDI candidates."""

from freight_lineitems import charge_map as cm
from freight_lineitems.config import CODES


def test_every_internal_code_is_mapped_and_ids_are_unchanged():
    assert set(cm.charge_map()["codes"]) == set(CODES)
    assert cm.charge_map()["client_roots_used"] == 40


def test_purchased_transportation_and_corrections_are_sub_items_of_freight():
    for code in ("PENDING.PURCHASED_TRANSPORTATION", "RATE_CORRECTION.BASE_RATE", "RATE_CORRECTION.WEIGHT",
                 "RATE_CORRECTION.ZONE_FACTOR", "LINEHAUL.MINIMUM"):
        e = cm.entry(code)
        assert e["relation"] == "CHILD" and e["parent"] == "Freight" and e["edi_candidates"] == cm.entry("LINEHAUL.BASE")["edi_candidates"]
    assert cm.entry("RATE_CORRECTION.FUEL_TIER")["parent"] == "FUEL SURCHARGE"


def test_one_to_many_lists_every_candidate_and_chooses_none():
    d = cm.describe(["DETENTION_STORAGE.DRIVER_DETENTION"])
    assert d["client_name"] == "DRIVER DETENTION (generic)" and d["reference_names"].count("|") >= 5
    assert len(d["edi_candidates"].split()) > 1 and d["coverage_class"] == 2


def test_extensions_and_top_level_entries():
    assert cm.entry("ACCESSORIAL.ROAD_CLOSURE")["relation"] == "EXTENSION"
    assert "not on the list" in cm.entry("ACCESSORIAL.ROAD_CLOSURE")["client_name"]
    assert cm.entry("OTHER")["relation"] == "TOP_LEVEL" and cm.coverage_class(["OTHER"]) == 5
    assert cm.coverage_class(["TAX.UNSPECIFIED"]) == 4


def test_combined_amount_takes_the_weakest_class_and_no_code_has_none():
    assert cm.coverage_class(["ACCESSORIAL.LIFTGATE"]) == 1
    assert cm.coverage_class(["ACCESSORIAL.LIFTGATE", "PENDING.PURCHASED_TRANSPORTATION"]) == 3
    assert cm.coverage_class([]) is None and cm.describe([])["client_name"] == "(no charge named)"


def test_both_prompt_layouts_list_every_internal_code_once(monkeypatch):
    import re
    from freight_lineitems import tools
    for layout in ("internal", "client_rooted"):
        monkeypatch.setenv("FL_TAXONOMY_LAYOUT", layout)
        text = tools.taxonomy_for_prompt()
        found = re.findall(r"^- ([A-Z_]+(?:\.[A-Z_]+)?)", text, flags=re.M)
        assert sorted(found) == sorted(CODES), layout
    monkeypatch.setenv("FL_TAXONOMY_LAYOUT", "client_rooted")
    assert "Freight" in tools.taxonomy_for_prompt().splitlines()[2]
    monkeypatch.setenv("FL_TAXONOMY_LAYOUT", "bogus")
    import pytest
    with pytest.raises(ValueError):
        tools.taxonomy_layout()
