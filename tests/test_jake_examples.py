"""T14-04 (T12-04, C7): the client's two worked examples as regression tests.

Two versions (T12 adjustment plan section 7 item 4):
- synthetic: the same structure with made-up text and amounts, always runs;
- real: reads the git-ignored dev split, the stored MVP dev run and the git-ignored expectations
  (data/interim/tests/jake_examples.json, written from the client's answer: every item of the client's two tables);
  skipped when any of them is missing, so a clean checkout runs only the synthetic version.
Both examples are in the dev split and were seen during development, so passing them is a regression check, not
evidence on an independent sample.
"""

import json
import re
from decimal import Decimal

import pytest

from freight_lineitems.config import ROOT, RUNS_DIR

from rollup_helpers import C, DAY1, DAY2, DAY3, T, X, codes, expl, roll

EXPECTED = ROOT / "data" / "interim" / "tests" / "jake_examples.json"


def test_synthetic_example_one_two_explanations_same_day_each_with_tax():
    """Shape of example 1: two explanations on the same Event Date, each a charge plus GST plus a stated total;
    different charges, so they add up and the taxes stay (made-up amounts)."""
    sh = roll(expl("SORT FEE $40.00 + GST $2.00 = $42.00", [C("#1", ["ACCESSORIAL.SORT_SEGREGATE"], "SORT FEE"), T("#2"), X("#3")], 1, DAY1, rid="a"),
              expl("FSC SHOULD APPLY. BALANCE DUE IS $18.10 + GST $0.91 = $19.01",
                   [C("#1", ["RATE_CORRECTION.FUEL_TIER"], "FSC"), T("#2"), X("#3")], 2, DAY1, rid="b"), original="150.00")
    assert sh["default_change"] == "61.01" and sh["new_total"] == "211.01" and codes(sh) == set()
    assert [ln["is_tax"] for ln in sh["lines"]] == [False, True, False, True]          # tax on its own line


def test_synthetic_example_two_three_explanations_eight_orders():
    """Shape of example 2: three explanations on three days, detention, a combined lumper/sort amount and a fuel
    amount, the same eight orders on every row; different charges, so all three add up (made-up amounts)."""
    pks = tuple(f"P{i}" for i in range(8))
    sh = roll(expl("FUEL SURCHARGE $12.00", [C("#1", ["RATE_CORRECTION.FUEL_TIER"], "FUEL SURCHARGE")], 1, DAY1, rid="a", pks=pks),
              expl("LUMPER/SORT FEE $40.00", [C("#1", ["ACCESSORIAL.LUMPER", "ACCESSORIAL.SORT_SEGREGATE"], "LUMPER/SORT FEE")], 9, DAY2, rid="b", pks=pks),
              expl("DRIVER DETENTION 2 HRS $150.00", [X("#1", "QUANTITY"), C("#2", ["DETENTION_STORAGE.DRIVER_DETENTION"], "DRIVER DETENTION")],
                   17, DAY3, rid="c", pks=pks), original="300.00")
    assert sh["default_change"] == "202.00" and sh["new_total"] == "502.00" and codes(sh) == set()
    assert sh["n_orders"] == 8


def _real():
    if not EXPECTED.exists():
        pytest.skip("git-ignored expectations not present")
    exp = json.loads(EXPECTED.read_text())
    run_file = RUNS_DIR / exp["run"] / "records.jsonl"
    if not run_file.exists():
        pytest.skip("stored dev run not present")
    try:
        from freight_lineitems.records import load_dev
        dev = load_dev()
    except (FileNotFoundError, OSError):
        pytest.skip("dev split not present")
    if "lines" not in exp["examples"][0]:
        pytest.skip("expectations predate task 23 (no line items)")
    return exp, run_file, dev


def _real_shipments(exp, run_file, dev) -> dict:
    """The two shipments through the production path: the stored readings of the MVP run (task 19, routed), order
    copies and roll-up recomputed by pipeline.finish_batch (as in every evaluation since task 20)."""
    from freight_lineitems import pipeline
    from freight_lineitems.disposition import flags_from, recommend
    from freight_lineitems.schemas import Diagnostic
    bols = {e["sap_bol"] for e in exp["examples"]}
    sel = [json.loads(x) for x in run_file.open()]
    sel = [r for r in sel if (r["facts"]["source"].get("raw") or {}).get("SAP BOL") in bols]
    keys = {r["facts"]["source"]["shipment_key"] for r in sel}
    for r in sel:      # finish_batch adds the copy flags again
        diags = [Diagnostic(**d) for d in r["judgment"]["diagnostics"] if d["code"] != "SHIP.COPY.SAME_OR_NO_PK"]
        fl = flags_from(diags)
        r["judgment"] = {"flags": fl, **recommend(fl), "diagnostics": [d.model_dump() for d in diags]}
    _, ships = pipeline.finish_batch([r for r in dev if r.shipment_key in keys], sel)
    return {s["sap_bol"]: s for s in ships}


def _name_words(name: str) -> set[str]:
    """Words of Jake's charge name that must appear in the label as written ('Charge' / 'Fee' are left out: Jake
    writes 'Driver Detention Charge' where the text has 'CHG')."""
    return {w for w in re.split(r"[^A-Z0-9]+", name.upper()) if w and w not in ("CHARGE", "FEE")}


def test_real_examples_reproduce_every_item_jake_wrote():
    """Task 23 (audit F-04). Every item of the client's two tables (data/incoming/2026-11-13, Q1 and Q3), compared
    with the shipment result of the production path and with its client-format table:
    - original amount, new total, change from original amount: equal as amounts;
    - each line: Jake's charge name (each of its words appears in the line's label as written), amount, and whether it
      is a tax line (GST on its own line, code TAX.GST); the shipment has exactly these lines, all counted;
    - the same original amount, lines (LINE / TAX rows) and totals in shipment_table.table_rows.
    Not compared, because Jake's tables do not state them: line order (our lines follow Event Date), recommendation,
    reminders, client names, gap, other readings, and in example 2 the split of the total over 8 orders (scope item
    D1, not done). Also checked, as our own regression and not as Jake's item: the internal code of each line."""
    from freight_lineitems import shipment_table
    exp, run_file, dev = _real()
    ships = _real_shipments(exp, run_file, dev)
    assert set(ships) == {e["sap_bol"] for e in exp["examples"]}
    for e in exp["examples"]:
        s, bol = ships[e["sap_bol"]], e["sap_bol"]
        assert Decimal(s["original_amount"]) == Decimal(e["original"]), bol
        assert Decimal(s["new_total"]) == Decimal(e["new_total"]), bol
        assert Decimal(s["default_change"]) == Decimal(e["change"]), bol
        assert all(ln["status"] == "COUNTED" for ln in s["lines"]), bol
        got = sorted((Decimal(ln["amount"]), ln["is_tax"], ln["label"].upper(), tuple(ln["codes"])) for ln in s["lines"])
        want = sorted((Decimal(x["amount"]), x["tax"], x["name"], tuple(x["codes"])) for x in e["lines"])
        assert len(got) == len(want), bol
        for (ga, gt, glabel, gcodes), (wa, wt, wname, wcodes) in zip(got, want):
            assert (ga, gt) == (wa, wt), (bol, wname)
            assert _name_words(wname) <= set(re.split(r"[^A-Z0-9]+", glabel)), (bol, wname, glabel)
            assert gcodes == wcodes, (bol, wname)
            assert gt == (gcodes == ("TAX.GST",)), (bol, wname)
        rows = shipment_table.table_rows(s)
        amount = {r["row"]: Decimal(r["amount"]) for r in rows if r["row"] in ("ORIGINAL_AMOUNT", "NEW_TOTAL", "CHANGE_FROM_ORIGINAL")}
        assert amount == {"ORIGINAL_AMOUNT": Decimal(e["original"]), "NEW_TOTAL": Decimal(e["new_total"]),
                          "CHANGE_FROM_ORIGINAL": Decimal(e["change"])}, bol
        assert sorted((Decimal(r["amount"]), r["row"] == "TAX") for r in rows if r["row"] in ("LINE", "TAX")) == \
            sorted((Decimal(x["amount"]), x["tax"]) for x in e["lines"]), bol


# ------------------------------------------------------------------ task 20: the shipment table in the client's format

JAKE1_CSV = """shipment_key,sap_bol,row,label,internal_code,amount,status,replaced_by,explanation,note
S1,,ORIGINAL_AMOUNT,Original Amount,,150.00,,,,
S1,,LINE,"SORT,SEGREGATE & STACKING CHG",ACCESSORIAL.SORT_SEGREGATE,40.00,COUNTED,,a,
S1,,TAX,GST - GOODS & SERVICE TAX,TAX.GST,2.00,COUNTED,,a,
S1,,LINE,FUEL SURCHARGE / fuel tier correction (sub-item),RATE_CORRECTION.FUEL_TIER,18.10,COUNTED,,b,
S1,,TAX,GST - GOODS & SERVICE TAX,TAX.GST,0.91,COUNTED,,b,
S1,,NEW_TOTAL,New Disputed Total,,211.01,,,,
S1,,CHANGE_FROM_ORIGINAL,Delta from Original Amount,,61.01,,,,
S1,,STATED_AMOUNT_DUE,Stated amount due,,,,,,MULTI_EXPLANATION_NO_SHIPMENT_GAP
S1,,GAP,Gap (stated amount due - line total),,,,,,
S1,,REMINDERS,Reminders,,,,,,SHIP.GAP.MULTI_EXPLANATION (info)
S1,,RECOMMENDATION,Recommendation,,,,,,PASSED_CHECKS
"""

JAKE2_CSV = """shipment_key,sap_bol,row,label,internal_code,amount,status,replaced_by,explanation,note
S1,,ORIGINAL_AMOUNT,Original Amount,,300.00,,,,
S1,,LINE,FUEL SURCHARGE / fuel tier correction (sub-item),RATE_CORRECTION.FUEL_TIER,12.00,COUNTED,,a,
S1,,LINE,"LUMPER SERVICE(EXTRA HELPER) + SORT,SEGREGATE & STACKING CHG",ACCESSORIAL.LUMPER+ACCESSORIAL.SORT_SEGREGATE,40.00,COUNTED,,b,
S1,,LINE,DRIVER DETENTION (generic),DETENTION_STORAGE.DRIVER_DETENTION,150.00,COUNTED,,c,
S1,,NEW_TOTAL,New Disputed Total,,502.00,,,,
S1,,CHANGE_FROM_ORIGINAL,Delta from Original Amount,,202.00,,,,
S1,,STATED_AMOUNT_DUE,Stated amount due,,,,,,
S1,,GAP,Gap (stated amount due - line total),,,,,,
S1,,REMINDERS,Reminders,,,,,,
S1,,RECOMMENDATION,Recommendation,,,,,,PASSED_CHECKS
"""


def _jake1():
    from freight_lineitems import charge_map
    sh = roll(expl("SORT FEE $40.00 + GST $2.00 = $42.00", [C("#1", ["ACCESSORIAL.SORT_SEGREGATE"], "SORT FEE"), T("#2"), X("#3")], 1, DAY1, rid="a"),
              expl("FSC SHOULD APPLY. BALANCE DUE IS $18.10 + GST $0.91 = $19.01",
                   [C("#1", ["RATE_CORRECTION.FUEL_TIER"], "FSC"), T("#2"), X("#3")], 2, DAY1, rid="b", due="#3"), original="150.00")
    return charge_map.annotate(sh)


def _jake2():
    from freight_lineitems import charge_map
    pks = tuple(f"P{i}" for i in range(8))
    sh = roll(expl("FUEL SURCHARGE $12.00", [C("#1", ["RATE_CORRECTION.FUEL_TIER"], "FUEL SURCHARGE")], 1, DAY1, rid="a", pks=pks),
              expl("LUMPER/SORT FEE $40.00", [C("#1", ["ACCESSORIAL.LUMPER", "ACCESSORIAL.SORT_SEGREGATE"], "LUMPER/SORT FEE")], 9, DAY2, rid="b", pks=pks),
              expl("DRIVER DETENTION 2 HRS $150.00", [X("#1", "QUANTITY"), C("#2", ["DETENTION_STORAGE.DRIVER_DETENTION"], "DRIVER DETENTION")],
                   17, DAY3, rid="c", pks=pks), original="300.00")
    return charge_map.annotate(sh)


def test_synthetic_examples_reproduce_the_shipment_table_exactly():
    from freight_lineitems import shipment_table
    assert shipment_table.to_csv([_jake1()]) == JAKE1_CSV
    assert shipment_table.to_csv([_jake2()]) == JAKE2_CSV


def test_shipment_table_json_has_every_column_of_the_client_format():
    from freight_lineitems import shipment_table
    j = shipment_table.shipment_json(_jake1())
    assert (j["original_amount"], j["new_total"], j["change_from_original"]) == ("150.00", "211.01", "61.01")
    assert [(ln["client_name"], ln["internal_code"], ln["amount"], ln["is_tax"], ln["status"], ln["replaced_by"])
            for ln in j["lines"]][1] == ("GST - GOODS & SERVICE TAX", "TAX.GST", "2.00", True, "COUNTED", None)
    assert j["stated_amount_due"] is None and j["gap"] is None and j["gap_note"] == "MULTI_EXPLANATION_NO_SHIPMENT_GAP"
    assert j["per_explanation_gap"][1] == {"explanation": "b", "items_total": "19.01", "stated_amount_due": "19.01", "gap": "0.00"}
    assert j["recommendation"] == "PASSED_CHECKS" and j["prior_history"] == "NOT_PROVIDED" and j["other_reading_totals"] == []
    assert {"schema_version", "reminders", "relation_undecided", "complete"} <= set(j)
    assert not any(k in json.dumps(j).lower() for k in ("approve", "deny", "should be paid", "payable"))


def test_shipment_table_shows_replacement_and_the_other_reading():
    from freight_lineitems import charge_map, shipment_table
    sh = charge_map.annotate(roll(expl("LIFTGATE $75.00", [C("#1", ["ACCESSORIAL.LIFTGATE"], "LIFTGATE")], 1, DAY1, rid="a"),
                                  expl("LIFTGATE $80.00", [C("#1", ["ACCESSORIAL.LIFTGATE"], "LIFTGATE")], 2, DAY2, rid="b")))
    rows = shipment_table.table_rows(sh)
    assert [r["status"] for r in rows if r["row"] == "LINE"] == ["SUPERSEDED", "COUNTED"]
    assert [r["replaced_by"] for r in rows if r["row"] == "LINE"] == ["b:#1", ""]
    other = [r for r in rows if r["row"] == "OTHER_READING_TOTAL"]
    assert len(other) == 1 and other[0]["amount"] == "255.00" and "SUPERSEDED_SAME_CHARGE" in other[0]["note"]
