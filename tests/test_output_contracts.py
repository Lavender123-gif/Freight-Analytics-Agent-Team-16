"""Task 23 (audit F-03): the two output contracts list every field the code writes, to the second level.

The field lists in docs/reading_output_contract.md section 6 and docs/shipment_output_contract.md section 8 are read
from the documents and compared with the fields of real outputs built on synthetic input: the offline run on the
tracked synthetic batch (the files it writes) plus a small batch that reaches every conditional field (model not run,
screening run, order copies, a replacement with another reading, a lowered shipment flag). Adding, renaming or
removing a field without updating the document fails here. No model call, no real data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from freight_lineitems import pipeline, rollup
from freight_lineitems.agent import Session
from freight_lineitems.config import RULES
from freight_lineitems.offline import run_offline
from freight_lineitems.records import load_csv

from helpers import L, N, S, record

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "smoke"
CLASSES = {"stable", "diagnostic"}


def contract_fields(doc: str) -> dict[str, dict]:
    """{field: {"class", "present"}} from the table between the fields markers of a contract document."""
    text = (ROOT / "docs" / doc).read_text()
    block = text.split("<!-- fields:start -->", 1)[1].split("<!-- fields:end -->", 1)[0]
    out = {}
    for line in block.splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            assert m.group(1) not in out, f"{doc}: {m.group(1)} listed twice"
            out[m.group(1)] = {"class": m.group(2), "present": m.group(3)}
    return out


def field_paths(obj: dict, free_form: set[str], prefix: str = "", depth: int = 0) -> set[str]:
    """Field paths to the second level. A list of objects contributes `name[].key`; free-form fields are not opened."""
    out: set[str] = set()
    for k, v in obj.items():
        p = prefix + k
        out.add(p)
        if depth == 1 or p in free_form:
            continue
        if isinstance(v, dict):
            out |= field_paths(v, free_form, p + ".", depth + 1)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    out |= field_paths(x, free_form, p + "[].", depth + 1)
    return out


def _parent(p: str) -> str:
    return re.sub(r"(\[\])?\.[^.]+$", "", p)


def check_contract(doc: str, outputs: list[dict]) -> None:
    spec = contract_fields(doc)
    assert spec, f"{doc}: no field table found"
    bad_class = {f: s["class"] for f, s in spec.items() if s["class"] not in CLASSES}
    assert not bad_class, f"{doc}: unknown class {bad_class}"
    free_form = {f for f, s in spec.items() if "free-form" in s["present"]}
    seen: set[str] = set()
    for o in outputs:
        got = field_paths(o, free_form)
        seen |= got
        for f, s in spec.items():          # an 'always' field is present whenever its parent has any field
            if s["present"].startswith("always") and ("." not in f or any("." in g and _parent(g) == _parent(f) for g in got)):
                assert f in got, f"{doc}: '{f}' is listed as always present but is missing"
    undocumented, never_seen = sorted(seen - set(spec)), sorted(set(spec) - seen)
    assert not undocumented, f"{doc}: fields written by the code but not in the contract: {undocumented}"
    assert not never_seen, f"{doc}: fields in the contract that no output has: {never_seen}"


def _read(prep: dict, reading: dict | None, screening: dict | None = None) -> dict:
    """One explanation through Session.submit (the real checks), as the offline run does, optionally with a
    screening answer; reading None = the model did not run."""
    if reading is None:
        return pipeline.assemble(prep, None)
    sess = Session(ctx=prep["ctx"], llm_input=prep["llm_input"])
    sess.submit(reading)
    mo = {"session": sess, "transcript": {"calls": [], "events": [], "first_user_message": None},
          "routing": {"layout": "offline"}}
    if screening is not None:
        mo["screening"] = screening
    return pipeline.assemble(prep, mo)


def _liftgate(label: str) -> dict:
    return S([N("#1", codes=["ACCESSORIAL.LIFTGATE"], ev=label)], [L("#1", label=label)])


@pytest.fixture
def outputs(tmp_path, monkeypatch):
    """(reading outputs, shipment outputs) of the offline smoke run (read back from its files) and of a batch that
    reaches every conditional field."""
    records = load_csv(FIX / "batch.csv", prefix="smoke")
    readings = {f"smoke#r{k}": v for k, v in json.loads((FIX / "readings.json").read_text()).items()}
    _, _, _, out = run_offline(records, readings, "contract", tmp_path)
    rec_out = [json.loads(x) for x in (out / "records.jsonl").read_text().splitlines()]
    ship_out = [json.loads(x) for x in (out / "shipments.jsonl").read_text().splitlines()]

    a = record("LIFTGATE $15.00", "15", rid="syn#c1", shipment="S1", invoice="I1", pk="P1")
    b = record("LIFTGATE CHARGE $15.00", "15", rid="syn#c2", shipment="S1", invoice="I1", pk="P2")   # same day: replacement + order tie
    c1 = record("DETENTION $40.00", "40", rid="syn#c3", shipment="S2", invoice="I2", pk=None)       # two copies, no PK
    c2 = record("DETENTION $40.00", "40", rid="syn#c4", shipment="S2", invoice="I2", pk=None)
    d = record("LIFTGATE $10.00", "10", rid="syn#c5", shipment="S3", invoice="I3", pk="P5")        # model not run
    for i, r in enumerate((a, b, c1, c2, d)):
        r.row_number = i + 1
    screening = {"result": {"addressed_to_system": False, "quote": None, "kind": None}, "quote_found": None,
                 "calls": [], "error": None}
    results = [_read(pipeline.prepare(a), _liftgate("LIFTGATE"), screening),
               _read(pipeline.prepare(b), _liftgate("LIFTGATE CHARGE")),
               _read(pipeline.prepare(c1), S([N("#1", codes=["DETENTION_STORAGE.DRIVER_DETENTION"], ev="DETENTION")],
                                             [L("#1", label="DETENTION")])),
               _read(pipeline.prepare(d), None)]
    # a shipment flag lowered by `subsumption` (no shipment flag is listed there today): the two optional flag keys
    monkeypatch.setitem(RULES["subsumption"], "SHIP.ROLLUP.SUPERSEDED_SAME_CHARGE", ["SHIP.ROLLUP.ORDER_TIED"])
    results, ships = pipeline.finish_batch([a, b, c1, c2, d], results,
                                           relation_suggestions={"S1": [{"line": "x", "free": {"form": 1}}]})
    rec_out += json.loads(json.dumps(results, default=str))
    ship_out += json.loads(json.dumps(ships, default=str))
    return rec_out, ship_out


def test_reading_output_fields_equal_the_contract(outputs):
    recs, _ = outputs
    assert any("duplicate_clear_rules_applied" in r["judgment"] for r in recs)
    assert any("screening" in r["process"] for r in recs) and any(not r["process"]["model_ran"] for r in recs)
    assert all(r["schema_version"] == pipeline.READING_SCHEMA_VERSION for r in recs)
    check_contract("reading_output_contract.md", recs)


def test_shipment_output_fields_equal_the_contract(outputs):
    _, ships = outputs
    assert any(s["other_readings"] for s in ships)
    assert any("severity_before_subsumption" in f for s in ships for f in s["flags"])
    assert all(s["schema_version"] == rollup.SHIPMENT_SCHEMA_VERSION for s in ships)
    check_contract("shipment_output_contract.md", ships)


def test_an_undocumented_field_fails_the_check(outputs):
    """The check itself: one extra field, or one missing 'always' field, is caught."""
    recs, ships = outputs
    with pytest.raises(AssertionError, match="not in the contract"):
        check_contract("reading_output_contract.md", recs + [recs[0] | {"facts": recs[0]["facts"] | {"new_field": 1}}])
    with pytest.raises(AssertionError, match="always present"):
        check_contract("shipment_output_contract.md", ships + [{k: v for k, v in ships[0].items() if k != "gap"}])


def test_every_stable_reading_field_named_in_sections_2_and_3_is_in_the_list():
    spec = contract_fields("reading_output_contract.md")
    for f in ("facts.reading", "facts.claim", "facts.stated_amount_due", "facts.number_table", "facts.text_redacted",
              "judgment.flags", "judgment.recommendation", "facts.parse_status"):
        assert spec[f]["class"] == "stable", f
    for f in ("process.transcript", "process.attempts", "judgment.diagnostics"):
        assert spec[f]["class"] == "diagnostic", f

