"""Read the annotation workbooks that come back and turn them into one long-format table.

Usage:  uv run python scratch/annotation/import_annotations.py returned/*.xlsx
            [--key data/interim/annotation/key_dev.json] [--out data/interim/annotation/annotations_long.csv]
            [--allow-incomplete] [--annotator FILE_STEM=ID ...]

Long format (annot_schema.IMPORT_COLUMNS), one row per annotator x number:
    annotator, pack, item_id, record_id, is_common, number_id, number_raw,
    what, claim, category, confident, note, source_file, source_row
`what`, `claim`, `category`, `confident` hold the option codes of annot_schema (MONEY, COUNTED, ...), not the labels.
`confident` is the record-level answer repeated on every row of the item. Empty cells are empty strings.

Errors are loud: every problem in every file is collected and raised together, naming the file and the cell.
- Always fatal: a missing sheet or column, a value that is not a dropdown option, rows added / removed / changed
  compared with the key, a missing annotator id, the same annotator answering the same record twice.
- Fatal unless --allow-incomplete: an empty required cell; an answer where the guide says to leave the cell empty
  (item 2 on a number that is not money, item 3 on an amount that is not Counted). With the flag these are printed
  as warnings; a superfluous answer is dropped, an empty required cell stays empty.
The output contains record ids, so it goes under data/interim/annotation/ (git-ignored).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from annot_schema import ANNOTATION_COLUMNS, ANNOTATOR_CELL, COL, IMPORT_COLUMNS, LABEL_TO_CODE, PACK_ID_CELL, SHEETS  # noqa: E402

from freight_lineitems.config import ROOT  # noqa: E402

DEFAULT_KEY = ROOT / "data" / "interim" / "annotation" / "key_dev.json"
DEFAULT_OUT = ROOT / "data" / "interim" / "annotation" / "annotations_long.csv"


class AnnotationImportError(Exception):
    """Raised with the full list of problems found in the returned workbooks."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(f"{len(problems)} problem(s) in the returned annotation files:\n  " + "\n  ".join(problems))


def _clean(v) -> str:
    return "" if v is None else str(v).strip()


def read_workbook(path: Path, key: dict | None, annotator: str | None = None) -> tuple[list[dict], list[str], list[str]]:
    """Rows of one returned workbook. Returns (rows, fatal problems, completeness problems)."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    fatal: list[str] = []
    soft: list[str] = []
    name = path.name
    wb = load_workbook(path, data_only=True)
    missing = [s for s in (SHEETS[0], SHEETS[3]) if s not in wb.sheetnames]
    if missing:
        return [], [f"{name}: sheet(s) missing: {missing}"], []
    pack = _clean(wb[SHEETS[0]][PACK_ID_CELL].value)
    who = annotator or _clean(wb[SHEETS[0]][ANNOTATOR_CELL].value)
    if not pack:
        fatal.append(f"{name}: pack id missing ({SHEETS[0]}!{PACK_ID_CELL})")
    if not who:
        fatal.append(f"{name}: annotator id missing ({SHEETS[0]}!{ANNOTATOR_CELL}); fill it in or pass --annotator {path.stem}=ID")
    ws = wb[SHEETS[3]]
    header = [_clean(c.value) for c in ws[1]][:len(ANNOTATION_COLUMNS)]
    if header != [h for h, _, _ in ANNOTATION_COLUMNS]:
        return [], fatal + [f"{name}: {SHEETS[3]} header row was changed"], []

    def ref(r: int, field: str) -> str:
        return f"{name}: {SHEETS[3]}!{get_column_letter(COL[field])}{r}"

    rows: list[dict] = []
    seen_items: set[str] = set()
    for r in range(2, ws.max_row + 1):
        raw = {k: _clean(ws.cell(row=r, column=c).value) for k, c in COL.items()}
        if not any(raw.values()):
            continue
        if not raw["item_id"] or not raw["number_id"]:
            fatal.append(f"{ref(r, 'item_id')}: row without item id or number id")
            continue
        first = raw["item_id"] not in seen_items
        seen_items.add(raw["item_id"])
        code = {}
        for field in ("what", "claim", "category", "confident"):
            v = raw[field]
            if v and v not in LABEL_TO_CODE[field]:
                fatal.append(f"{ref(r, field)}: '{v}' is not a dropdown option")
                v = ""
            code[field] = LABEL_TO_CODE[field].get(v, "")
        if not code["what"]:
            soft.append(f"{ref(r, 'what')}: empty (item 1 is required on every row)")
        if code["what"] == "MONEY" and not code["claim"]:
            soft.append(f"{ref(r, 'claim')}: empty (item 2 is required for a money amount)")
        if code["what"] and code["what"] != "MONEY" and code["claim"]:
            soft.append(f"{ref(r, 'claim')}: filled in for a number that is not money (dropped)")
            code["claim"] = ""
        if code["claim"] == "COUNTED" and not code["category"]:
            soft.append(f"{ref(r, 'category')}: empty (item 3 is required for a counted amount)")
        if code["claim"] != "COUNTED" and code["category"]:
            soft.append(f"{ref(r, 'category')}: filled in for an amount that is not Counted (dropped)")
            code["category"] = ""
        if first and not code["confident"]:
            soft.append(f"{ref(r, 'confident')}: empty (item 4 is required on the first row of each item)")
        if not first and code["confident"]:
            soft.append(f"{ref(r, 'confident')}: filled in on a row that is not the first row of the item (ignored)")
            code["confident"] = ""
        rows.append({"annotator": who, "pack": pack, "item_id": raw["item_id"], "record_id": "", "is_common": "",
                     "number_id": raw["number_id"], "number_raw": raw["number_raw"], **code, "note": raw["note"],
                     "source_file": name, "source_row": r})
    conf = {x["item_id"]: x["confident"] for x in rows if x["confident"]}
    for x in rows:                                   # the record-level answer is repeated on every row of the item
        x["confident"] = conf.get(x["item_id"], "")

    if key is not None and pack:
        want = [(i["item_id"], n["number_id"], n["number_raw"]) for i in sorted((i for i in key["items"] if i["pack"] == pack),
                                                                                  key=lambda i: i["position"]) for n in i["numbers"]]
        got = [(x["item_id"], x["number_id"], x["number_raw"]) for x in rows]
        if not want:
            fatal.append(f"{name}: pack '{pack}' is not in the key")
        elif sorted(got) != sorted(want):
            diff = len(set(want) - set(got)), len(set(got) - set(want))
            fatal.append(f"{name}: rows do not match the key for pack {pack} ({diff[0]} missing or changed, {diff[1]} unexpected); "
                         "rows must not be added, deleted or edited")
        info = {i["item_id"]: i for i in key["items"] if i["pack"] == pack}
        for x in rows:
            if x["item_id"] in info:
                x["record_id"], x["is_common"] = info[x["item_id"]]["record_id"], bool(info[x["item_id"]]["is_common"])
    return rows, fatal, soft


def import_files(paths: list[Path], key: dict | None, allow_incomplete: bool = False,
                 annotators: dict[str, str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """All returned workbooks as one long table. Raises AnnotationImportError listing every problem.
    Returns (table, warnings); warnings are the completeness problems tolerated by allow_incomplete."""
    rows: list[dict] = []
    fatal: list[str] = []
    soft: list[str] = []
    if not paths:
        raise AnnotationImportError(["no files given"])
    for p in sorted(paths):
        r, f, s = read_workbook(Path(p), key, (annotators or {}).get(Path(p).stem))
        rows += r
        fatal += f
        soft += s
    seen: dict[tuple, str] = {}
    for x in rows:
        k = (x["annotator"], x["record_id"] or (x["pack"], x["item_id"]), x["number_id"])
        if k in seen and x["annotator"]:
            fatal.append(f"{x['source_file']}: annotator '{x['annotator']}' answers the same record twice (also in {seen[k]}); "
                         "one annotator, one pack")
            break
        seen[k] = x["source_file"]
    problems = fatal + ([] if allow_incomplete else soft)
    if problems:
        raise AnnotationImportError(problems)
    return pd.DataFrame(rows, columns=IMPORT_COLUMNS), soft


def load_long(path: Path) -> pd.DataFrame:
    """Read a table written by this script (all cells as text; is_common back to bool)."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [c for c in IMPORT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: not an annotation import table, columns missing: {missing}")
    df["is_common"] = df["is_common"].map({"True": True, "False": False, "": False})
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--key", type=Path, default=DEFAULT_KEY)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--allow-incomplete", action="store_true")
    ap.add_argument("--annotator", action="append", default=[], metavar="FILE_STEM=ID")
    a = ap.parse_args()
    try:
        table, warnings = import_files(a.files, json.loads(a.key.read_text()), a.allow_incomplete,
                                       dict(x.split("=", 1) for x in a.annotator))
    except AnnotationImportError as e:
        sys.exit(str(e))
    for w in warnings:
        print("WARNING", w)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(a.out, index=False)
    print(f"wrote {len(table)} rows, {table['annotator'].nunique()} annotator(s), {table['record_id'].nunique()} records -> {a.out}")
    from agreement import agreement_table, format_table
    print(format_table(agreement_table(table)))
