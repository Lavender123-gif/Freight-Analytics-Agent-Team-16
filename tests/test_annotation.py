"""Annotation packs, import, agreement and the V1 metric script, end to end on SYNTHETIC text only.

No data file is read here: records are generated in the test, workbooks are written to pytest's temp folder.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scratch" / "annotation"), str(ROOT / "scratch" / "eval")]

import agreement  # noqa: E402
import annot_guide  # noqa: E402
import annot_schema as sc  # noqa: E402
import build_packs as bp  # noqa: E402
import import_annotations as imp  # noqa: E402
import metrics  # noqa: E402
from helpers import N, S, record  # noqa: E402

from freight_lineitems.pipeline import prepare  # noqa: E402

CHARGES = ["LIFTGATE", "INSIDE DELIVERY", "REDELIVERY", "HAZMAT", "LUMPER", "STORAGE", "DETENTION", "CHASSIS", "APPOINTMENT",
           "RESIDENTIAL", "REWEIGH", "LIMITED ACCESS"]
FORMS = ["{c} ${a}", "ADD ${a} FOR {c}", "{c} CHARGE - ${a} PER BOL {i}",                       # simple
         "{c} ${a} + GST ${t} = ${s}", "{c} BILLED ${a} PAID ${b} SHORT PAID ${d}",             # tax, payment history
         "{c} {q} DAYS @ ${r} EACH = ${p}", "{c} ${a} AND FUEL ${b} AND LINE HAUL ${d} WEIGHT {w} LBS"]   # qty x rate, multi


def synthetic_records(n: int = 420, seed: int = 5):
    rng = random.Random(seed)
    out = []
    for k in range(n):
        f = FORMS[k % len(FORMS)] if k % 3 else FORMS[0]          # the first form is the frequent one
        a, b, q, r = rng.randint(20, 900), rng.randint(5, 90), rng.randint(2, 9), rng.randint(20, 90)
        text = f.format(c=CHARGES[rng.randrange(len(CHARGES))], a=f"{a}.00", b=f"{b}.50", d=f"{a - b}.50", t=f"{a * 5 // 100}.00",
                        s=f"{a + a * 5 // 100}.00", q=q, r=r, p=q * r, i=rng.randint(10000, 99999), w=rng.randint(1000, 9000))
        out.append(record(text, "1.00", rid=f"syn#r{k}"))
    return out


@pytest.fixture(scope="module")
def cands():
    recs = synthetic_records()
    mismatch = {r.record_id for r in recs[::17]}
    exclude = {recs[0].record_id}
    c, dropped = bp.candidates(recs, mismatch, exclude)
    return recs, c, dropped


@pytest.fixture(scope="module")
def packs(cands):
    _, c, _ = cands
    return bp.layout(bp.select(c, seed=7, n_common=5, n_unique=8), seed=7)


# ------------------------------------------------------------------------------------------------- guide

def test_guide_examples_are_cut_by_the_real_code_and_obey_the_rules():
    assert 3 <= len(annot_guide.EXAMPLES) <= 5
    for ex in annot_guide.EXAMPLES:
        item = annot_guide.example_rows(ex)                      # raises if the answers do not match the numbers found
        assert [n["number_id"] for n in item["numbers"]] == list(ex["answers"])
    claims = {a[1] for ex in annot_guide.EXAMPLES for a in ex["answers"].values()}
    whats = {a[0] for ex in annot_guide.EXAMPLES for a in ex["answers"].values()}
    assert {"COUNTED", "NOT_TOTAL", "NOT_HISTORY", "CREDIT"} <= claims and {"MONEY", "WEIGHT", "QUANTITY", "RATE", "ID"} <= whats


def test_guide_has_every_required_term_and_matches_the_tracked_files():
    need = ["BALANCE DUE", "SHORT PAID", "ADJUSTED OFF", "OVERPAYMENT", "AMOUNT APPROVED", "LINE HAUL", "FSC", "ACCESSORIAL",
            "DETENTION", "DWELL", "PER DIEM", "STORAGE", "LUMPER", "LIFTGATE", "TAILGATE", "TONU", "CHASSIS", "PRE-PULL", "BOL",
            "GST", "HST", "PST", "QST", "[PERSON_1]", "$ 8 400.00", ".69", "PURCHASED TRANSPORTATION"]
    terms = " | ".join(t for t, _, _ in annot_guide.GLOSSARY)
    assert not [t for t in need if t not in terms]
    for lang in ("en", "zh"):
        md = annot_guide.render_markdown(lang)
        assert "synthetic" in md or "合成" in md
        f = annot_guide.DOCS_DIR / f"annotation_guide.{lang}.md"
        assert f.read_text(encoding="utf-8") == md, "run: uv run python scratch/annotation/annot_guide.py"


def test_categories_follow_the_taxonomy():
    from freight_lineitems.config import TAXONOMY
    assert set(TAXONOMY["categories"]) | {sc.NO_CHARGE_NAMED} == set(sc.CATEGORY)
    assert 8 <= len(sc.CATEGORY) <= 10


# ------------------------------------------------------------------------------------------------- sampling

def test_sampling_design(cands, packs):
    recs, c, dropped = cands
    assert dropped["prompt_example"] == 1
    bp.check_design(packs)
    assert [len(p["items"]) for p in packs] == [13, 13, 13]
    assert all(sum(i["is_common"] for i in p["items"]) == 5 for p in packs)
    everything = {i["record_id"]: i for p in packs for i in p["items"]}
    assert len(everything) == 5 + 3 * 8
    assert recs[0].record_id not in everything
    assert not any(i["text_key"] == prepare(recs[0])["redacted"].upper() for i in everything.values())
    half_hard = sum(i["bucket"] != "frequency" for i in packs[0]["items"])
    assert half_hard in (6, 7)                                   # half by frequency, half hard
    assert len({tuple(i["position"] for i in p["items"] if i["is_common"]) for p in packs}) > 1   # mixed in differently
    ids = [i["item_id"] for p in packs for i in p["items"]]
    assert len(set(ids)) == len(ids) and not any(i["record_id"].split("#")[1] in i["item_id"] for p in packs for i in p["items"])
    totals = [sum(i["n"] for i in p["items"]) for p in packs]
    assert max(totals) - min(totals) <= 2                        # balanced by swapping


def test_sampling_is_deterministic(cands, packs):
    _, c, _ = cands
    again = bp.layout(bp.select(c, seed=7, n_common=5, n_unique=8), seed=7)
    assert [[i["item_id"] for i in p["items"]] for p in again] == [[i["item_id"] for i in p["items"]] for p in packs]
    other = bp.layout(bp.select(c, seed=8, n_common=5, n_unique=8), seed=8)
    assert [[i["record_id"] for i in p["items"]] for p in other] != [[i["record_id"] for i in p["items"]] for p in packs]


def test_signature_groups_texts_that_differ_only_in_numbers():
    assert bp.signature("LIFTGATE $15.00 PER BOL 12345") == bp.signature("LIFTGATE $ 1 250.00 PER BOL 99")
    assert bp.signature("LIFTGATE $15.00") != bp.signature("STORAGE $15.00")


def test_held_out_split_is_refused(monkeypatch):
    monkeypatch.delenv("FL_ALLOW_TEST_SPLIT", raising=False)
    with pytest.raises(SystemExit):
        bp.load_records("test", owner_allows=True)               # flag without the environment variable
    monkeypatch.setenv("FL_ALLOW_TEST_SPLIT", "1")
    with pytest.raises(SystemExit):
        bp.load_records("test", owner_allows=False)              # environment variable without the flag


# ------------------------------------------------------------------------------------------------- workbook, import, agreement

def _key(packs) -> dict:
    return {"items": [{"item_id": i["item_id"], "pack": p["pack"], "position": i["position"], "record_id": i["record_id"],
                       "is_common": i["is_common"], "numbers": [{"number_id": n["number_id"], "number_raw": n["number_raw"]}
                                                                for n in i["item"]["numbers"]]} for p in packs for i in p["items"]]}


def _answer(n: dict) -> tuple[str, str, str]:
    """A fixed fake answer per number: '$' numbers are counted accessorials, the rest are ids."""
    return ("MONEY", "COUNTED", "ACCESSORIAL") if n["number_raw"].startswith("$") else ("ID", "", "")


def _fill(path: Path, annotator: str, change=None) -> None:
    from openpyxl import load_workbook
    wb = load_workbook(path)
    wb[sc.SHEETS[0]][sc.ANNOTATOR_CELL] = annotator
    ws = wb[sc.SHEETS[3]]
    seen = set()
    for r in range(2, ws.max_row + 1):
        item, raw = ws.cell(row=r, column=sc.COL["item_id"]).value, ws.cell(row=r, column=sc.COL["number_raw"]).value
        what, claim, cat = _answer({"number_raw": raw})
        ws.cell(row=r, column=sc.COL["what"]).value = sc.label("what", what)
        ws.cell(row=r, column=sc.COL["claim"]).value = sc.label("claim", claim) if claim else None
        ws.cell(row=r, column=sc.COL["category"]).value = sc.label("category", cat) if cat else None
        if item not in seen:
            ws.cell(row=r, column=sc.COL["confident"]).value = sc.label("confident", "YES")
            seen.add(item)
    if change:
        change(ws)
    wb.save(path)


@pytest.fixture()
def written(packs, tmp_path):
    paths = []
    for p in packs:
        path = tmp_path / f"annotation_pack_{p['pack']}.xlsx"
        bp.write_pack(path, p["pack"], p["items"])
        paths.append(path)
    return paths, _key(packs)


def test_workbook_shows_only_what_annotators_may_see(written, packs):
    from openpyxl import load_workbook
    paths, _ = written
    wb = load_workbook(paths[0])
    assert wb.sheetnames == sc.SHEETS
    ws = wb[sc.SHEETS[3]]
    assert ws.freeze_panes == "A2"
    assert [c.value for c in ws[1]] == [h for h, _, _ in sc.ANNOTATION_COLUMNS]
    assert len(ws.data_validations.dataValidation) == 4 and all(d.type == "list" for d in ws.data_validations.dataValidation)
    cells = " ".join(str(c.value) for s in wb for row in s.iter_rows() for c in row if c.value is not None)
    for hidden in ("syn#r", "S1", "I1", "C1", "Delta", "DELTA"):       # record id, shipment, invoice, carrier, Delta
        assert hidden not in cells.replace("PERSON_1", "").replace("EMAIL_1", "").replace("PHONE_1", "")
    assert ws.max_row - 1 == sum(i["n"] for i in packs[0]["items"])
    assert all(ws.cell(row=r, column=sc.COL["what"]).value is None for r in range(2, ws.max_row + 1))   # no pre-filled reading


def test_import_and_agreement_end_to_end(written):
    paths, key = written

    def flip(ws):                                                  # annotator B disagrees on the first row
        ws.cell(row=2, column=sc.COL["what"]).value = sc.label("what", "MONEY")
        ws.cell(row=2, column=sc.COL["claim"]).value = sc.label("claim", "UNCLEAR")
        ws.cell(row=2, column=sc.COL["category"]).value = None

    _fill(paths[0], "A")
    _fill(paths[1], "B", flip)
    _fill(paths[2], "C")
    table, warnings = imp.import_files(paths, key)
    assert list(table.columns) == sc.IMPORT_COLUMNS and not warnings
    assert set(table["annotator"]) == {"A", "B", "C"} and table["record_id"].str.startswith("syn#r").all()
    assert set(table["what"]) <= set(sc.WHAT) and set(table["claim"]) <= set(sc.CLAIM) | {""}
    assert (table.groupby(["annotator", "item_id"])["confident"].nunique() == 1).all()

    out = paths[0].parent / "long.csv"
    table.to_csv(out, index=False)
    rows = agreement.agreement_table(imp.load_long(out))
    assert {(r["annotator_a"], r["annotator_b"]) for r in rows} == {("A", "B"), ("A", "C"), ("B", "C")}
    by = {(r["field"], r["annotator_a"], r["annotator_b"]): r for r in rows}
    n_common_numbers = table[(table["annotator"] == "A") & (table["is_common"])].shape[0]
    assert by[("what", "A", "C")]["n"] == n_common_numbers and by[("what", "A", "C")]["percent"] == 100.0
    assert by[("claim", "A", "C")]["kappa"] in (1.0, None)
    assert by[("confident", "A", "C")]["n"] == 5 and by[("claim_sum", "A", "C")]["percent"] == 100.0
    first_is_common = bool(table[(table["annotator"] == "B") & (table["source_row"] == 2)]["is_common"].iloc[0])
    if first_is_common:
        assert by[("claim", "A", "B")]["agree"] == by[("claim", "A", "B")]["n"] - 1
        assert by[("claim_sum", "A", "B")]["n_skipped"] == 1       # a record with an Unclear cell has no sum
    assert "kappa" in agreement.format_table(rows)

    # only two packs returned: still a complete study
    two, _ = imp.import_files(paths[:2], key)
    assert {r["field"] for r in agreement.agreement_table(two)} == set(agreement.FIELDS)


def test_import_errors_are_loud(written):
    paths, key = written
    from openpyxl import load_workbook

    _fill(paths[0], "A", lambda ws: ws.cell(row=3, column=sc.COL["what"], value="Probably money"))
    with pytest.raises(imp.AnnotationImportError) as e:
        imp.import_files(paths[:1], key)
    assert "F3" in str(e.value) and "not a dropdown option" in str(e.value)

    _fill(paths[0], "A", lambda ws: setattr(ws.cell(row=3, column=sc.COL["what"]), "value", None))
    with pytest.raises(imp.AnnotationImportError, match="item 1 is required"):
        imp.import_files(paths[:1], key)
    table, warnings = imp.import_files(paths[:1], key, allow_incomplete=True)
    assert len(warnings) >= 1 and (table["what"] == "").sum() == 1

    _fill(paths[0], "A", lambda ws: ws.delete_rows(4))
    with pytest.raises(imp.AnnotationImportError, match="do not match the key"):
        imp.import_files(paths[:1], key, allow_incomplete=True)

    wb = load_workbook(paths[1])                                   # never filled in: no annotator id
    wb.save(paths[1])
    with pytest.raises(imp.AnnotationImportError, match="annotator id missing"):
        imp.import_files(paths[1:2], key, allow_incomplete=True)

    _fill(paths[1], "Z")
    _fill(paths[2], "Z")                                           # one annotator returns two packs: common records twice
    with pytest.raises(imp.AnnotationImportError, match="same record twice"):
        imp.import_files(paths[1:], key)


def test_cohen_kappa():
    assert agreement.cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(0.5)
    assert agreement.cohen_kappa(list("aabb"), list("aabb")) == 1.0
    assert agreement.cohen_kappa(list("aaaa"), list("aaaa")) is None
    assert agreement.cohen_kappa(list("abab"), list("baba")) == pytest.approx(-1.0)


# ------------------------------------------------------------------------------------------------- V1 metric script

def _run_record(rid: str, text: str, numbers: list[dict], recommendation: str = "PASSED_CHECKS") -> dict:
    p = prepare(record(text, "1.00", rid=rid))["parse"]
    return {"record_id": rid, "facts": {"number_table": json.loads(p.model_dump_json()), "reading": S(numbers, [])},
            "judgment": {"recommendation": recommendation}}


@pytest.fixture(scope="module")
def run():
    recs = [
        _run_record("syn#a", "LIFTGATE $45.00 PER BOL 88213", [N("#1", codes=["ACCESSORIAL.LIFTGATE"]), N("#2", "REFERENCE", "NONE")]),
        _run_record("syn#b", "INSIDE DELIVERY $25 FUEL SURCHARGE $31.20 BALANCE DUE $56.20",
                    [N("#1", codes=["ACCESSORIAL.INSIDE_DELIVERY"]), N("#2", codes=["FUEL.SURCHARGE"]), N("#3", "TOTAL", "NONE")]),
        _run_record("syn#c", "BILLED $ 1 250.00 PAID 1 100.00 SHORT PAID 150.00 LESS CREDIT $20.00",
                    [N("#1", status="BILLED"), N("#2", status="PAID"), N("#3", "UNSPECIFIED_AMOUNT", "UNPAID"), N("#4", credit=True, codes=["OTHER"])]),
        _run_record("syn#d", "STORAGE 3 DAYS @ $75 EACH = $225", [N("#1", "QUANTITY", "NONE"), N("#2", "RATE", "NONE"),
                                                                  N("#3", codes=["DETENTION_STORAGE.TERMINAL_STORAGE"])]),
    ]
    return {r["record_id"]: r for r in recs}


def test_metrics_perfect_on_noise_free_fake_annotations(run):
    ann = metrics.fake_annotations_from_run(run, noise=0.0, n_common=2)
    assert list(ann.columns) == sc.IMPORT_COLUMNS                 # the metric script reads the import format directly
    res = metrics.compare(run, ann)
    assert res["coverage"]["compared_records"] == 4
    for scope in [res["pooled"], *res["by_annotator"].values()]:
        for m in ("is_money", "counted_not_counted_credit", "charge_category", "claim_sum_per_record"):
            assert scope[m]["percent"] == 100.0, m
        assert scope["human_unclear"]["numbers"] == 0
    assert res["pooled"]["numbers"] == 12 and res["pooled"]["claim_sum_per_record"]["n"] == 4
    assert all(r["percent"] == 100.0 for r in res["inter_annotator_agreement"])
    assert "claimed sum per record" in metrics.format_compare(res, "synthetic")


def test_metrics_report_disagreement_and_unclear_separately(run):
    ann = metrics.fake_annotations_from_run(run, annotators=("H1",), noise=0.0, n_common=0)
    i = ann.index[(ann["record_id"] == "syn#b") & (ann["number_id"] == "#3")][0]
    ann.loc[i, ["claim", "category"]] = ["COUNTED", "NO_CHARGE_NAMED"]           # the human counts the total: a disagreement
    j = ann.index[(ann["record_id"] == "syn#c") & (ann["number_id"] == "#3")][0]
    ann.loc[j, ["claim", "category"]] = ["UNCLEAR", ""]                          # the human cannot tell
    k = ann.index[(ann["record_id"] == "syn#a") & (ann["number_id"] == "#1")][0]
    ann.loc[k, "category"] = "FUEL"                                              # wrong category
    extra = ann[ann["record_id"] == "syn#a"].assign(record_id="syn#not-in-run")
    res = metrics.compare(run, __import__("pandas").concat([ann, extra], ignore_index=True))
    p = res["pooled"]
    assert res["coverage"]["not_in_run"] == 1 and res["coverage"]["compared_records"] == 4
    assert p["counted_not_counted_credit"]["n"] == 11 and p["counted_not_counted_credit"]["agree"] == 10
    assert p["counted_not_counted_credit"]["confusion_human>model"]["COUNTED>NOT_COUNTED"] == 1
    assert p["human_unclear"] == {"numbers": 1, "model_said": {"COUNTED": 1}, "records_with_an_unclear_cell_not_scored_on_sum": 1}
    assert p["claim_sum_per_record"]["n"] == 3 and p["claim_sum_per_record"]["agree"] == 2
    assert p["charge_category"]["agree"] == p["charge_category"]["n"] - 1
    assert p["is_money"]["percent"] == 100.0


def test_metrics_with_noise_runs(run):
    res = metrics.compare(run, metrics.fake_annotations_from_run(run, noise=0.5, seed=3, n_common=4))
    assert res["pooled"]["is_money"]["n"] <= 12 and res["inter_annotator_agreement"]
