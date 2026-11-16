"""Order copies merged into explanations (task 14 / T12-02, proposal C4). Synthetic rows only.

Three cases: one PK per copy (normal: several orders on one truck, order count only, no flag), a repeated PK and an
empty PK (SHIP.COPY.SAME_OR_NO_PK). Delta is not part of the key; Event Date is."""

from datetime import datetime

from freight_lineitems import duplicates
from freight_lineitems.pipeline import assemble, prepare
from freight_lineitems.records import group_explanations

from helpers import record


def fake_result(rec):
    out = assemble(prepare(rec), None)
    out["facts"]["parse_status"] = "PASSED_CHECKS"
    out["judgment"] = {"flags": [], "recommendation": "PASSED_CHECKS", "diagnostics": []}   # no model run in this test
    return out


def rows(pks, text="DETENTION $50.00", deltas=None):
    out = []
    for i, pk in enumerate(pks):
        r = record(text, (deltas or ["50"] * len(pks))[i], rid=f"dev#r{i + 1}", pk=pk)
        r.row_number = i + 1
        out.append(r)
    return out


def codes(res):
    return {f["code"] for f in res["judgment"]["flags"]}


def test_one_pk_per_copy_is_one_explanation_with_an_order_count_and_no_flag():
    recs = rows(["P1", "P2", "P3"])
    groups = group_explanations(recs)
    assert len(groups) == 1 and [r.record_id for r in groups[0]] == ["dev#r1", "dev#r2", "dev#r3"]
    (res,) = duplicates.apply(recs, [fake_result(recs[0])])
    assert res["facts"]["n_rows"] == 3 and res["facts"]["n_orders"] == 3
    assert [s["pk"] for s in res["facts"]["source_rows"]] == ["P1", "P2", "P3"]
    assert codes(res) == set() and res["judgment"]["recommendation"] == "PASSED_CHECKS"


def test_repeated_pk_is_flagged():
    recs = rows(["P1", "P1"])
    (res,) = duplicates.apply(recs, [fake_result(recs[0])])
    f = next(f for f in res["judgment"]["flags"] if f["code"] == "SHIP.COPY.SAME_OR_NO_PK")
    assert f["evidence"][0]["rows_repeating_a_pk"] == ["dev#r2"] and res["judgment"]["recommendation"] == "HUMAN_REVIEW"
    assert res["facts"]["n_orders"] == 1


def test_empty_pk_is_flagged():
    recs = rows(["P1", None])
    (res,) = duplicates.apply(recs, [fake_result(recs[0])])
    f = next(f for f in res["judgment"]["flags"] if f["code"] == "SHIP.COPY.SAME_OR_NO_PK")
    assert f["evidence"][0]["rows_without_pk"] == ["dev#r2"]


def test_single_row_without_pk_is_not_a_copy():
    recs = rows([None])
    (res,) = duplicates.apply(recs, [fake_result(recs[0])])
    assert codes(res) == set() and res["facts"]["n_orders"] == 0


def test_delta_is_not_part_of_the_key_but_event_date_and_text_are():
    recs = rows(["P1", "P2"], deltas=["50", "55"])            # same text, different Delta: one explanation (C4)
    assert len(group_explanations(recs)) == 1
    later = rows(["P1", "P2"])
    later[1].event_date = datetime(2022, 3, 9, 10, 0)          # same text on another day: two explanations
    assert len(group_explanations(later)) == 2
    other = rows(["P1", "P2"])
    other[1].text_raw = "DETENTION $55.00"
    assert len(group_explanations(other)) == 2
    spaced = rows(["P1", "P2"])
    spaced[1].text_raw = "DETENTION   $50.00 "                 # normalised text: spacing does not split
    assert len(group_explanations(spaced)) == 1
    assert duplicates.content_key(recs[0]) == duplicates.content_key(recs[1])


def test_different_shipments_never_merge():
    a, b = rows(["P1", "P2"])
    b.shipment_key = "S2"
    assert len(group_explanations([a, b])) == 2


def test_mock_r3_loader_maps_order_id_to_pk(tmp_path, monkeypatch):
    import json
    from freight_lineitems import records
    p = tmp_path / "m.jsonl"
    base = {"shipment_id": "S", "event_date": "2026-01-03T19:00:00Z", "shipment_amount": 10.0, "origin_state": "TX",
            "destination_state": "NM", "reason_code": "X", "carrier": "C", "text": "FEE $5.00", "delta": 5.0, "invoice_amount": 15.0}
    p.write_text("\n".join(json.dumps(base | {"row_id": f"R{i}", "order_id": o, "active": act}) for i, (o, act) in
                           enumerate([("O1", True), ("O2", True), ("O3", False)])))
    monkeypatch.setattr(records, "assert_readable", lambda x: x)
    rs = records.load_mock_r3(p)
    assert [r.pk for r in rs] == ["O1", "O2"] and len(group_explanations(rs)) == 1


def test_pk_normalised_before_comparing_p35():
    assert duplicates.normalize_pk(" ord-00123 ") == duplicates.normalize_pk("ORD-123") == "ORD-123"
    assert duplicates.normalize_pk("PO 0077") == "PO77" and duplicates.normalize_pk("000") == "0"
    assert duplicates.normalize_pk(None) == "" and duplicates.normalize_pk("  ") == ""
    recs = rows(["AB-0042", "ab-42"])
    (res,) = duplicates.apply(recs, [fake_result(recs[0])])
    assert "SHIP.COPY.SAME_OR_NO_PK" in codes(res) and res["facts"]["n_orders"] == 1
    distinct = rows(["AB-0042", "AB-0043"])
    (res,) = duplicates.apply(distinct, [fake_result(distinct[0])])
    assert codes(res) == set() and res["facts"]["n_orders"] == 2
