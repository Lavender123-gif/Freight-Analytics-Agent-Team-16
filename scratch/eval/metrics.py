"""V1 metric script: how well does a pipeline run read the text? (definitions: docs/eval/metrics.zh.md)

Usage:
  uv run python scratch/eval/metrics.py annotations --run RUN_ID [--annotations data/interim/annotation/annotations_long.csv]
  uv run python scratch/eval/metrics.py mock --run RUN_ID
  uv run python scratch/eval/metrics.py selftest --run RUN_ID [--noise 0.1]

annotations  compares the run with the human answers number by number. It reads the import format written by
             scratch/annotation/import_annotations.py directly. Human "Unclear" cells are reported separately and
             never scored; the inter-annotator agreement on the common records is printed next to the result.
mock         wraps scratch/autorun/mock_eval.score on the PUBLIC mock and adds the distribution of the three
             recommendations. (The held-out mock batch is used once, for the final test, not here.)
selftest     builds fake annotations from the run's own reading plus random noise and scores the run against them;
             proves the script runs end to end before real annotations exist. Not a result.

All three print aggregates only: no record text, no ids. Nothing here says whether a charge should be paid.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve()
sys.path[:0] = [str(_HERE.parents[1] / "annotation"), str(_HERE.parents[1] / "autorun")]

from agreement import agreement_table, derive, format_table, number_value  # noqa: E402
from annot_schema import IMPORT_COLUMNS, NO_CHARGE_NAMED  # noqa: E402
from mock_eval import signed_sum  # noqa: E402

from freight_lineitems.config import RUNS_DIR, category  # noqa: E402

MONEY_KINDS = {"CHARGE_AMOUNT", "UNSPECIFIED_AMOUNT", "TAX_AMOUNT", "TOTAL"}
ITEM_KINDS = {"CHARGE_AMOUNT", "UNSPECIFIED_AMOUNT", "TAX_AMOUNT"}
COUNTED_STATUSES = {"CLAIMED", "UNPAID"}
THREE = ("COUNTED", "NOT_COUNTED", "CREDIT")


def load_run(run_id: str, runs_dir: Path = RUNS_DIR) -> dict[str, dict]:
    """Results by record id. A run made after task 14 holds one result per explanation; every source row of the
    explanation (an order copy) maps to that result, so an annotated copy finds the reading of its explanation."""
    path = runs_dir / run_id / "records.jsonl"
    out = {}
    for r in (json.loads(x) for x in path.read_text().splitlines() if x.strip()):
        out[r["record_id"]] = r
        for s in r["facts"].get("source_rows") or []:
            out.setdefault(s["record_id"], r)
    return out


# ------------------------------------------------------------------------------------------------ the model's reading

def model_view(rec: dict) -> dict[str, dict] | None:
    """The run's final reading of one record, per number id, in the vocabulary of the annotation:
    {is_money, claim3 (COUNTED / NOT_COUNTED / CREDIT), categories (set), kind, status}. None when there is no reading."""
    reading = rec["facts"].get("reading")
    if not reading:
        return None
    out = {}
    for j in reading["numbers"] + [u["as_number"] for u in reading.get("unrecognized_reads", [])]:
        money = j["kind"] in MONEY_KINDS
        counted = j["kind"] in ITEM_KINDS and j["status"] in COUNTED_STATUSES
        cats = {category(c) for c in j.get("charge_codes") or []}
        if not cats:
            cats = {"TAX"} if j["kind"] == "TAX_AMOUNT" else {NO_CHARGE_NAMED}
        out[j["id"]] = {"is_money": money, "claim3": ("CREDIT" if j.get("is_credit") else "COUNTED") if counted else "NOT_COUNTED",
                        "categories": cats, "kind": j["kind"], "status": j["status"]}
    return out


def table_rows(rec: dict) -> list[tuple[str, str]]:
    t = rec["facts"]["number_table"]
    return sorted([(tuple(n["span"]), n["id"], n["raw"]) for n in t["numbers"]] + [(tuple(u["span"]), u["id"], u["raw"]) for u in t["unrecognized"]])


# ------------------------------------------------------------------------------------------------ run vs. humans

def _human3(coarse: str) -> str:
    """Human answer in the three classes scored against the model (a number that is not money is not counted)."""
    return {"NOT_MONEY": "NOT_COUNTED"}.get(coarse, coarse)


def _score(rows: list[dict], sums: list[dict]) -> dict:
    """rows: one per scored (reference answer, number); sums: one per scored (reference answer, record)."""
    def rate(a: int, n: int):
        return {"n": n, "agree": a, "percent": round(100 * a / n, 1) if n else None}

    money = [r for r in rows if r["h_money"] != ""]
    claim = [r for r in rows if r["h3"] in THREE]
    unclear = [r for r in rows if r["h3"] == "UNCLEAR"]
    cat = [r for r in rows if r["h3"] == "COUNTED" and r["m3"] == "COUNTED" and r["h_cat"]]
    scored = [s for s in sums if s["human"] is not None]
    return {
        "is_money": rate(sum((r["h_money"] == "MONEY") == r["m_money"] for r in money), len(money)),
        "counted_not_counted_credit": rate(sum(r["h3"] == r["m3"] for r in claim), len(claim))
        | {"confusion_human>model": dict(sorted(Counter(f"{r['h3']}>{r['m3']}" for r in claim).items()))},
        "charge_category": rate(sum(r["h_cat"] in r["m_cats"] for r in cat), len(cat))
        | {"scored_on": "numbers both sides count", "model_gave_several_categories": sum(len(r["m_cats"]) > 1 for r in cat)},
        "claim_sum_per_record": rate(sum(s["human"] == s["model"] for s in scored), len(scored))
        | {"model_has_no_reading": sum(s["model"] is None for s in scored)},
        "human_unclear": {"numbers": len(unclear), "model_said": dict(sorted(Counter(r["m3"] for r in unclear).items())),
                          "records_with_an_unclear_cell_not_scored_on_sum": len(sums) - len(scored)},
    }


def compare(run: dict[str, dict], ann: pd.DataFrame) -> dict:
    """Compare a run with the human answers (import format). Returns aggregates only.

    Pooled reference: a number answered by one annotator uses that answer; a number answered by several uses their
    answer when they all agree on the field, and is left out of that field ('contested') when they do not. The
    per-annotator tables use each annotator's own answers on all the records that annotator did.
    """
    missing = [c for c in IMPORT_COLUMNS if c not in ann.columns]
    if missing:
        raise ValueError(f"annotations are not in the import format; columns missing: {missing}")
    d = derive(ann[ann["record_id"] != ""])
    coverage = Counter()
    views, model_sums = {}, {}
    for rid, g in d.groupby("record_id"):
        coverage["annotated_records"] += 1
        rec = run.get(rid)
        if rec is None:
            coverage["not_in_run"] += 1
            continue
        want = sorted(set(zip(g["number_id"], g["number_raw"])))
        if want != sorted((i, raw) for _, i, raw in table_rows(rec)):
            coverage["number_table_differs_from_pack"] += 1      # pack and run were cut by different code versions
            continue
        views[rid] = model_view(rec)
        model_sums[rid] = signed_sum(rec["facts"]["reading"], rec["facts"]["number_table"])
        coverage["compared_records"] += 1
        coverage["compared_records_without_model_reading"] += views[rid] is None

    def rows_for(g: pd.DataFrame, rid: str, pooled: bool) -> tuple[list[dict], dict]:
        view = views[rid]
        rows, contested = [], Counter()
        for nid, gn in g.groupby("number_id", sort=False):
            m = (view or {}).get(nid) or {"is_money": None, "claim3": "MISSING", "categories": set()}
            vals = {}
            for col in ("is_money", "claim_coarse", "category"):
                answers = set(gn[col])
                if len(answers) > 1:
                    contested[col] += 1
                    vals[col] = None
                else:
                    vals[col] = answers.pop()
            rows.append({"h_money": vals["is_money"] if vals["is_money"] is not None else "",
                         "h3": _human3(vals["claim_coarse"]) if vals["claim_coarse"] is not None else "CONTESTED",
                         "h_cat": vals["category"] or "", "m_money": m["is_money"], "m3": m["claim3"], "m_cats": m["categories"]})
        return rows, contested

    def human_sum(g: pd.DataFrame) -> Decimal | None:
        """Signed sum of what the humans count; None when a cell is Unclear, empty, or the annotators differ."""
        s = Decimal("0")
        for nid, gn in g.groupby("number_id", sort=False):
            cs = set(gn["claim_coarse"])
            if len(cs) > 1 or cs & {"UNCLEAR", ""}:
                return None
            c = cs.pop()
            v = number_value(nid, gn["number_raw"].iloc[0])
            s += v if c == "COUNTED" else -v if c == "CREDIT" else 0
        return s

    def scope(frame: pd.DataFrame, pooled: bool) -> dict:
        rows, sums, contested = [], [], Counter()
        for rid, g in frame.groupby("record_id"):
            if rid not in views:
                continue
            r, c = rows_for(g, rid, pooled)
            rows += r
            contested += c
            sums.append({"human": human_sum(g), "model": model_sums[rid]})
        out = _score(rows, sums) | {"records": len(sums), "numbers": len(rows)}
        if pooled:
            out["contested_between_annotators_not_scored"] = dict(contested)
        return out

    return {"coverage": dict(coverage), "pooled": scope(d, True),
            "by_annotator": {a: scope(d[d["annotator"] == a], False) for a in sorted(d["annotator"].unique())},
            "inter_annotator_agreement": agreement_table(ann)}


def format_compare(res: dict, run_id: str) -> str:
    def line(name: str, m: dict) -> str:
        pc = "n/a" if m["percent"] is None else f"{m['percent']:.1f}%"
        return f"  {name:<34}{m['agree']:>5} / {m['n']:<5} {pc}"

    out = [f"run {run_id} against human annotations", f"coverage: {res['coverage']}"]
    for title, s in [("pooled (all annotators)", res["pooled"])] + [(f"annotator {a}", s) for a, s in res["by_annotator"].items()]:
        out += [f"{title}: {s['records']} records, {s['numbers']} numbers",
                line("is money", s["is_money"]), line("counted / not counted / credit", s["counted_not_counted_credit"]),
                line("charge category", s["charge_category"]), line("claimed sum per record", s["claim_sum_per_record"]),
                f"  human Unclear (not scored): {s['human_unclear']}",
                f"  confusion human>model: {s['counted_not_counted_credit']['confusion_human>model']}"]
        if "contested_between_annotators_not_scored" in s:
            out.append(f"  contested between annotators (not scored): {s['contested_between_annotators_not_scored']}")
    return "\n".join(out + [format_table(res["inter_annotator_agreement"])])


# ------------------------------------------------------------------------------------------------ public mock

def mock_report(run_id: str) -> dict:
    """mock_eval.score on the public mock, plus the distribution of the three recommendations (all rows of the run)."""
    from mock_eval import score
    summary = score(run_id)
    recs = Counter(r["judgment"]["recommendation"] for r in load_run(run_id).values())
    n = sum(recs.values())
    summary["recommendation_distribution"] = {k: {"n": v, "percent": round(100 * v / n, 1)} for k, v in sorted(recs.items())}
    summary["rows_in_run"] = n
    return summary


# ------------------------------------------------------------------------------------------------ self-test data

def fake_annotations_from_run(run: dict[str, dict], annotators: tuple[str, ...] = ("F1", "F2"), noise: float = 0.1,
                              seed: int = 0, n_common: int = 15) -> pd.DataFrame:
    """Fake human answers in the import format, derived from the run's own reading with random noise.
    For testing the script only: with noise 0 every metric must be 100%. The first `n_common` records are answered
    by every fake annotator, the rest are dealt round-robin."""
    from annot_schema import CATEGORY, CLAIM, WHAT
    rng = random.Random(seed)
    rows = []
    usable = [(rid, rec) for rid, rec in sorted(run.items()) if model_view(rec) and table_rows(rec)]
    for k, (rid, rec) in enumerate(usable):
        view = model_view(rec)
        who = annotators if k < n_common else (annotators[k % len(annotators)],)
        for a in who:
            conf = "NO" if rng.random() < noise else "YES"
            for _, nid, raw in table_rows(rec):
                m = view.get(nid)
                if m is None:
                    what, claim, cat = "ID", "", ""
                elif not m["is_money"]:
                    what, claim, cat = {"QUANTITY": "QUANTITY", "RATE": "RATE"}.get(m["kind"], "ID"), "", ""
                else:
                    what = "MONEY"
                    claim = m["claim3"] if m["claim3"] != "NOT_COUNTED" else (
                        "NOT_TOTAL" if m["kind"] == "TOTAL" else "NOT_HISTORY" if m["status"] in ("BILLED", "PAID", "DEDUCTED") else "NOT_REFERENCE")
                    cat = sorted(m["categories"])[0] if claim == "COUNTED" else ""
                if rng.random() < noise:
                    what = rng.choice(list(WHAT))
                    claim = rng.choice(list(CLAIM)) if what == "MONEY" else ""
                    cat = rng.choice(list(CATEGORY)) if claim == "COUNTED" else ""
                elif what == "MONEY" and rng.random() < noise:
                    claim = rng.choice(list(CLAIM))
                    cat = (cat or rng.choice(list(CATEGORY))) if claim == "COUNTED" else ""
                rows.append({"annotator": a, "pack": "FAKE", "item_id": f"{a}-{k}", "record_id": rid, "is_common": k < n_common,
                             "number_id": nid, "number_raw": raw, "what": what, "claim": claim, "category": cat,
                             "confident": conf, "note": "", "source_file": "fake", "source_row": 0})
    return pd.DataFrame(rows, columns=IMPORT_COLUMNS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("annotations", "mock", "selftest"):
        sp = sub.add_parser(name)
        sp.add_argument("--run", required=True)
        sp.add_argument("--json", type=Path, help="also write the aggregates as JSON")
        if name == "annotations":
            sp.add_argument("--annotations", type=Path, default=RUNS_DIR.parent / "annotation" / "annotations_long.csv")
        if name == "selftest":
            sp.add_argument("--noise", type=float, default=0.1)
    a = ap.parse_args()
    if a.cmd == "mock":
        result = mock_report(a.run)
        print(json.dumps(result, indent=1, ensure_ascii=False))
    else:
        the_run = load_run(a.run)
        if a.cmd == "annotations":
            from import_annotations import load_long
            table = load_long(a.annotations)
        else:
            table = fake_annotations_from_run(the_run, noise=a.noise)
            print(f"SELF-TEST with fake annotations (noise {a.noise}); these numbers are not a result")
        result = compare(the_run, table)
        print(format_compare(result, a.run))
    if a.json:
        a.json.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str))
