"""Sample records and build the annotation packs for team members (task 10 section 6).

Usage:  uv run python scratch/annotation/build_packs.py [--split dev] [--seed 20261110]

What it does (deterministic for a seed):
1. Loads the chosen split, runs every record through the real `prepare()` (redaction + number table).
2. Samples 15 common records (in every pack) + 30 unique records per pack: half by real frequency, half from hard
   categories (several numbers, payment history, tax, quantity x rate, first attempt inconsistent with Delta).
   At most 2 records per template in the whole set, no two records with the same text, none of the records used as
   examples in the prompt (nor a record with the same text as one).
3. Balances the number count of the packs by swapping records of the same bucket between packs.
4. Writes one workbook per pack (Instructions, Examples, Glossary, Annotation) and the key (item id -> record) to
   data/interim/annotation/ (git-ignored: the workbooks contain client text).

Annotators see the redacted text and the numbers the code cut. They do not see the model's reading, Delta, shipment
or invoice numbers, or the carrier.

The split is a parameter. The default is the dev split. The other split is NOT to be used by this script unless the
project owner decides so and runs it personally: it needs both --owner-allows-held-out-split and the environment
variable FL_ALLOW_TEST_SPLIT=1, and is refused otherwise.

The cue patterns below are generic English, used only to draw the sample; the pipeline never reads them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from annot_schema import ANNOTATION_COLUMNS, ANNOTATOR_CELL, CATEGORY, CLAIM, COL, CONFIDENT, PACK_ID_CELL, SHEETS, WHAT, label  # noqa: E402

from freight_lineitems.config import DEV_PATH, EXAMPLES_PATH, ROOT, RUNS_DIR  # noqa: E402
from freight_lineitems.records import InputRecord  # noqa: E402
from freight_lineitems.sampling import style  # noqa: E402
from freight_lineitems.textprep import normalize  # noqa: E402

OUT_DIR = ROOT / "data" / "interim" / "annotation"
DEFAULT_SEED = 20261110
N_PACKS, N_COMMON, N_UNIQUE = 3, 15, 30
TEMPLATE_CAP = 2
NUMBER_TARGET = 120                      # numbers per pack we try to stay under
MULTI_NUMBER_MIN = 3                     # "several numbers": at least this many number rows
FIRST_MISMATCH_RUNS = ("finA", "finB2")  # retained runs whose first attempt is used; full-dev runs are added automatically
HARD_CATEGORIES = ["first_mismatch", "tax", "qty_rate", "multi_number", "payment_history"]
QTY_RATE_RE = re.compile(r"@|\bX\b|\bEACH\b|\bDAYS?\b|\bHOURS?\b|\bHRS?\b|\bPER (?:DAY|HOUR|HR|CWT|MILE|LB|PALLET)\b")


# ----------------------------------------------------------------------------------------------------- loading

def load_records(split: str, owner_allows: bool = False) -> list[InputRecord]:
    """Records of one split. 'dev' is the normal case. Any other split is refused unless the owner flag AND the
    environment variable are both set (the held-out split is the owner's decision, never this script's)."""
    from freight_lineitems.records import _from_frame, load_dev
    if split == "dev":
        return load_dev()
    if split != "test":
        raise SystemExit(f"unknown split '{split}'")
    if not (owner_allows and os.environ.get("FL_ALLOW_TEST_SPLIT") == "1"):
        raise SystemExit("refused: the held-out split may only be used by the project owner. It needs both "
                         "--owner-allows-held-out-split and FL_ALLOW_TEST_SPLIT=1.")
    import pandas as pd
    return _from_frame(pd.read_csv(DEV_PATH.with_name(f"{split}.csv"), dtype=str), split, split)


def first_mismatch_ids(runs_dir: Path, split: str, n_split: int) -> tuple[set[str], list[str]]:
    """Record ids whose first valid attempt did not match Delta, from the retained runs named in FIRST_MISMATCH_RUNS
    and from any run that covers (nearly) the whole split. Returns (ids, names of the runs used)."""
    ids: set[str] = set()
    used: list[str] = []
    for d in sorted(runs_dir.glob("*")) if runs_dir.exists() else []:
        f = d / "records.jsonl"
        parts = d.name.split("-")
        if not f.exists() or len(parts) < 4:
            continue
        rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
        own = [r for r in rows if r["record_id"].startswith(split + "#")]
        full = len(own) == len(rows) and len(own) >= 0.95 * n_split
        if not own or not (parts[2] in FIRST_MISMATCH_RUNS and split == "dev" or full):
            continue
        used.append(d.name)
        ids |= {r["record_id"] for r in own if r["facts"].get("first_check") == "MISMATCH"}
    return ids, used


def example_record_ids(path: Path = EXAMPLES_PATH) -> set[str]:
    return {e["record_id"] for e in json.loads(path.read_text())} if path.exists() else set()


# ----------------------------------------------------------------------------------------------------- candidates

def signature(text: str) -> str:
    """Template signature: placeholders and numbers masked, punctuation dropped. Two texts that differ only in their
    amounts, ids, names or punctuation have the same signature."""
    t = re.sub(r"\[(?:PERSON|EMAIL|PHONE)_\d+\]", " P ", text.upper())
    t = re.sub(r"\$?\s?\d[\d ,./:-]*\d|\$?\s?\d|\.\d+", " 0 ", t)
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0%@+=]", " ", t)).strip()


def item_from_prepared(prep: dict) -> dict:
    """What an annotator sees for one record: the redacted text and one row per number (or unrecognised chunk) the
    code cut, in text order, each with a short context that marks the number."""
    p, text = prep["parse"], prep["redacted"]
    toks = sorted([(n.span, n.id, n.raw) for n in p.numbers] + [(u.span, u.id, u.raw) for u in p.unrecognized])
    rows = []
    for (a, b), tid, raw in toks:
        left, right = text[max(0, a - 40):a], text[b:b + 40]
        rows.append({"number_id": tid, "number_raw": raw,
                     "context": ("…" if a > 40 else "") + left + "»" + text[a:b] + "«" + right + ("…" if b + 40 < len(text) else "")})
    return {"text": text, "numbers": rows}


def candidates(records: list[InputRecord], mismatch_ids: set[str], exclude_ids: set[str]) -> tuple[list[dict], Counter]:
    """Prepare every record and keep the ones that can be annotated. Returns (candidates, counts of what was dropped)."""
    from freight_lineitems.pipeline import prepare
    dropped: Counter = Counter()
    preps = [(r, prepare(r)) for r in records]
    banned = set()
    for r, p in preps:
        if r.record_id in exclude_ids:
            banned |= {normalize(r.text_raw).upper(), p["redacted"].upper()}
    out = []
    for r, p in preps:
        item = item_from_prepared(p)
        if r.record_id in exclude_ids:
            dropped["prompt_example"] += 1
        elif normalize(r.text_raw).upper() in banned or p["redacted"].upper() in banned:
            dropped["same_text_as_prompt_example"] += 1
        elif not item["numbers"]:
            dropped["no_number_to_annotate"] += 1
        else:
            st = style(r.text_raw)
            flags = set()
            if len(item["numbers"]) >= MULTI_NUMBER_MIN:
                flags.add("multi_number")
            if st == "tax" or re.search(r"\b(GST|HST|PST|QST|TAX)\b", p["redacted"].upper()):
                flags.add("tax")
            if st == "payment_history" or re.search(r"\b(PAID|BILLED|ADJUST\w*|SHORT|OWE\w*|BALANCE)\b", p["redacted"].upper()):
                flags.add("payment_history")
            if len(item["numbers"]) >= 2 and QTY_RATE_RE.search(p["redacted"].upper()):
                flags.add("qty_rate")
            if r.record_id in mismatch_ids:
                flags.add("first_mismatch")
            out.append({"record_id": r.record_id, "text_key": p["redacted"].upper(), "sig": signature(p["redacted"]),
                        "n": len(item["numbers"]), "flags": flags, "item": item})
    return out, dropped


# ----------------------------------------------------------------------------------------------------- sampling

def select(cands: list[dict], seed: int, n_packs: int = N_PACKS, n_common: int = N_COMMON, n_unique: int = N_UNIQUE,
           template_cap: int = TEMPLATE_CAP) -> dict:
    """Draw the common records and the unique records of each pack.

    Hard half first (those pools are small), then the frequency half: records in random order, i.e. each template
    in proportion to how often it occurs, skipping a record when its text is already in the set or its template
    already has `template_cap` records. Every pack gets the same number of records per bucket, so any subset of the
    packs is a study of the same design.
    """
    rng = random.Random(seed)
    order = sorted(cands, key=lambda c: c["record_id"])
    rng.shuffle(order)
    used_text: set[str] = set()
    sig_n: Counter = Counter()
    taken: set[str] = set()

    def ok(c: dict) -> bool:
        return c["record_id"] not in taken and c["text_key"] not in used_text and sig_n[c["sig"]] < template_cap

    def take(c: dict, bucket: str) -> dict:
        taken.add(c["record_id"])
        used_text.add(c["text_key"])
        sig_n[c["sig"]] += 1
        return c | {"bucket": bucket}

    def draw_hard(cat: str, k: int) -> list[dict]:
        """k records of one hard category: the one asked for, or (when it cannot supply k) the next one in order.
        All k come from the same category, so a row dealt across the packs keeps their composition equal."""
        rot = HARD_CATEGORIES[HARD_CATEGORIES.index(cat):] + HARD_CATEGORIES[:HARD_CATEGORIES.index(cat)]
        for name in rot:
            picks, texts, sigs = [], set(), Counter()
            for c in order:
                if name in c["flags"] and ok(c) and c["text_key"] not in texts and sig_n[c["sig"]] + sigs[c["sig"]] < template_cap:
                    picks.append(c)
                    texts.add(c["text_key"])
                    sigs[c["sig"]] += 1
                    if len(picks) == k:
                        return [take(c, name) for c in picks]
        raise SystemExit("not enough hard records for the requested pack sizes")

    hard_common, hard_unique = (n_common + 1) // 2, n_unique // 2
    size = {k: sum(k in c["flags"] for c in cands) for k in HARD_CATEGORIES}
    cats = sorted(HARD_CATEGORIES, key=lambda k: (size[k], HARD_CATEGORIES.index(k)))     # scarce categories first
    packs: list[list[dict]] = [[] for _ in range(n_packs)]
    common: list[dict] = []
    for i in range(max(hard_unique, hard_common)):
        cat = cats[i % len(cats)]
        if i < hard_unique:
            for p, c in zip(packs, draw_hard(cat, n_packs)):
                p.append(c)
        if i < hard_common:
            common += draw_hard(cat, 1)

    n_freq = (n_common - hard_common) + n_packs * (n_unique - hard_unique)
    freq = []
    for c in order:
        if len(freq) == n_freq:
            break
        if ok(c):
            freq.append(take(c, "frequency"))
    if len(freq) < n_freq:
        raise SystemExit(f"not enough records for the frequency half ({len(freq)} of {n_freq}); lower the pack sizes")
    for i in sorted(rng.sample(range(n_freq), n_common - hard_common), reverse=True):
        common.append(freq.pop(i))
    for i, c in enumerate(freq):
        packs[i % n_packs].append(c)

    balance(packs)
    return {"common": common, "packs": packs}


def balance(packs: list[list[dict]]) -> None:
    """Swap records of the same bucket between packs while that narrows the spread of the packs' number counts."""
    def spread(tot):
        return max(tot) - min(tot)
    while True:
        tot = [sum(c["n"] for c in p) for p in packs]
        best = None
        for a in range(len(packs)):
            for b in range(a + 1, len(packs)):
                for i, x in enumerate(packs[a]):
                    for j, y in enumerate(packs[b]):
                        if x["bucket"] != y["bucket"] or x["n"] == y["n"]:
                            continue
                        new = list(tot)
                        new[a] += y["n"] - x["n"]
                        new[b] += x["n"] - y["n"]
                        cand = (spread(new), x["record_id"], y["record_id"], a, b, i, j)
                        if cand[0] < spread(tot) and (best is None or cand < best):
                            best = cand
        if best is None:
            return
        _, _, _, a, b, i, j = best
        packs[a][i], packs[b][j] = packs[b][j], packs[a][i]


def item_id(seed: int, pack: str, record_id: str) -> str:
    """Opaque id: says nothing about the record, differs between packs even for a common record."""
    h = hashlib.sha256(f"{seed}|{pack}|{record_id}".encode()).hexdigest()
    return "T" + str(int(h[:12], 16) % 10**6).zfill(6)


def layout(sel: dict, seed: int) -> list[dict]:
    """Order each pack (common records mixed in, a different order in every pack) and assign item ids."""
    packs = []
    for k, uniq in enumerate(sel["packs"], 1):
        pack = f"P{k}"
        items = [c | {"is_common": True} for c in sel["common"]] + [c | {"is_common": False} for c in uniq]
        items.sort(key=lambda c: c["record_id"])
        random.Random(f"{seed}|{pack}").shuffle(items)
        ids = [item_id(seed, pack, c["record_id"]) for c in items]
        if len(set(ids)) != len(ids):
            raise SystemExit("item id collision; change the seed")
        packs.append({"pack": pack, "items": [c | {"item_id": i, "position": n} for n, (c, i) in enumerate(zip(items, ids), 1)]})
    return packs


def check_design(packs: list[dict], template_cap: int = TEMPLATE_CAP) -> None:
    """Hard constraints of the task, verified on the result (raises when one is broken)."""
    recs = {c["record_id"]: c for p in packs for c in p["items"]}
    texts = Counter(c["text_key"] for c in recs.values())
    sigs = Counter(c["sig"] for c in recs.values())
    assert max(texts.values()) == 1, "two records with identical text"
    assert max(sigs.values()) <= template_cap, "template cap exceeded"
    common = [{c["record_id"] for c in p["items"] if c["is_common"]} for p in packs]
    assert all(s == common[0] for s in common), "common records differ between packs"
    uniq = [{c["record_id"] for c in p["items"] if not c["is_common"]} for p in packs]
    assert all(not (uniq[a] & uniq[b]) for a in range(len(uniq)) for b in range(a + 1, len(uniq))), "a unique record is in two packs"
    comp = [Counter(c["bucket"] for c in p["items"]) for p in packs]
    assert all(c == comp[0] for c in comp), "packs differ in composition"


# ----------------------------------------------------------------------------------------------------- workbook

def _put(ws, row: int, col: int, value, **style_kw):
    cell = ws.cell(row=row, column=col, value=value)
    if isinstance(value, str):
        cell.data_type = "s"            # never let Excel read carrier text starting with '=' or '+' as a formula
    for k, v in style_kw.items():
        setattr(cell, k, v)
    return cell


def write_pack(path: Path, pack_id: str, items: list[dict]) -> None:
    """One workbook: Instructions, Examples, Glossary, Annotation (frozen header, dropdowns by data validation).
    Everything in it is English; the only text not written by this project is the record text itself."""
    import annot_guide as g
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    bold, wrap = Font(bold=True), Alignment(wrap_text=True, vertical="top")
    head_fill, fill_in = PatternFill("solid", fgColor="D9E1F2"), PatternFill("solid", fgColor="FFF2CC")
    grey, band = PatternFill("solid", fgColor="E7E6E6"), PatternFill("solid", fgColor="F7F7F7")
    plain = lambda s: s.replace("**", "").replace("`", "")  # noqa: E731

    wb = Workbook()
    ws = wb.active
    ws.title = SHEETS[0]
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 34, 110
    _put(ws, 1, 1, "Annotation pack: what is each number in a carrier note?", font=Font(bold=True, size=14))
    _put(ws, 2, 1, "Pack", font=bold)
    _put(ws, 2, 2, pack_id)
    _put(ws, 3, 1, "Your annotator ID (fill in)", font=bold)
    _put(ws, 3, 2, None, fill=fill_in)
    assert (PACK_ID_CELL, ANNOTATOR_CELL) == ("B2", "B3")
    r = 5
    # English only: not every annotator reads Chinese (the Chinese guide is docs/annotation/annotation_guide.zh.md)
    for title, lines in (("The task", g.TASK["en"]),
                         ("What you fill in", [f"{h} {b}" for h, b in g.ITEMS["en"]]),
                         ("Rules", g.RULES["en"])):
        _put(ws, r, 1, title, font=bold)
        for line in lines:
            _put(ws, r, 2, plain(line), alignment=wrap)
            r += 1
        r += 1
    # dropdown lists live here, visible, and the data validations point at them
    lists_col, ranges = 4, {}
    _put(ws, 1, lists_col, "Dropdown options (do not edit)", font=bold)
    for k, (field, opts) in enumerate((("what", WHAT), ("claim", CLAIM), ("category", CATEGORY), ("confident", CONFIDENT))):
        col = lists_col + k
        letter = get_column_letter(col)
        ws.column_dimensions[letter].width = 46
        _put(ws, 2, col, field, font=bold, fill=head_fill)
        for i, code in enumerate(opts):
            _put(ws, 3 + i, col, label(field, code))
        ranges[field] = f"={SHEETS[0]}!${letter}$3:${letter}${2 + len(opts)}"

    ws = wb.create_sheet(SHEETS[1])
    for letter, w in zip("ABCDEF", (8, 18, 30, 44, 44, 90)):
        ws.column_dimensions[letter].width = w
    _put(ws, 1, 1, "Worked examples. They are synthetic (written for this guide, not items of any pack).", font=bold)
    r = 3
    for i, ex in enumerate(g.EXAMPLES, 1):
        item = g.example_rows(ex)
        _put(ws, r, 1, f"Example {i}: {ex['title']['en']}", font=Font(bold=True, size=12))
        for name, val in (("Text", item["text"]), ("Where to look", plain(ex["look"]["en"])), ("Criterion", plain(ex["criterion"]["en"]))):
            r += 1
            _put(ws, r, 1, name, font=bold)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
            _put(ws, r, 2, val, alignment=wrap)
            ws.row_dimensions[r].height = 15 * max(1, -(-len(val) // 150))
        r += 1
        for c, h in enumerate(("No.", "Number as written", "1. What is this number?", "2. Part of this claim?", "3. Charge category", "Why"), 1):
            _put(ws, r, c, h, font=bold, fill=head_fill)
        for n in item["numbers"]:
            r += 1
            what, claim, cat, why, _ = ex["answers"][n["number_id"]]
            vals = (n["number_id"], n["number_raw"], label("what", what), label("claim", claim) if claim else "(leave empty)",
                    label("category", cat) if cat else "(leave empty)", plain(why))
            for c, v in enumerate(vals, 1):
                _put(ws, r, c, v, alignment=wrap)
        r += 1
        _put(ws, r, 1, "4.", font=bold)
        _put(ws, r, 2, f"Confident: {label('confident', ex['confident'][0])}. {ex['confident'][1]}")
        r += 3

    ws = wb.create_sheet(SHEETS[2])
    for letter, w in zip("AB", (44, 100)):
        ws.column_dimensions[letter].width = w
    for c, h in enumerate(("Term", "Meaning"), 1):
        _put(ws, 1, c, h, font=bold, fill=head_fill)
    for i, (term, en, _zh) in enumerate(g.GLOSSARY, 2):
        for c, v in enumerate((plain(term), en), 1):
            _put(ws, i, c, v, alignment=wrap)
    ws.freeze_panes = "A2"

    ws = wb.create_sheet(SHEETS[3])
    for i, (header, _, width) in enumerate(ANNOTATION_COLUMNS, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
        _put(ws, 1, i, header, font=bold, fill=head_fill, alignment=wrap)
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"
    dvs = {}
    for field in ("what", "claim", "category", "confident"):
        dv = DataValidation(type="list", formula1=ranges[field], allow_blank=True, showErrorMessage=True,
                            errorTitle="Use the dropdown", error="Choose one of the options in the list.")
        ws.add_data_validation(dv)
        dvs[field] = dv
    top = Border(top=Side(style="thin"))
    r = 1
    for k, it in enumerate(items):
        for j, n in enumerate(it["item"]["numbers"]):
            r += 1
            first = j == 0
            shade = band if k % 2 else None
            _put(ws, r, COL["item_id"], it["item_id"])
            _put(ws, r, COL["text"], it["item"]["text"] if first else None, alignment=wrap)
            _put(ws, r, COL["number_id"], n["number_id"])
            _put(ws, r, COL["number_raw"], n["number_raw"])
            _put(ws, r, COL["context"], n["context"], alignment=wrap)
            for field in ("what", "claim", "category"):
                dvs[field].add(ws.cell(row=r, column=COL[field]))
            if first:
                dvs["confident"].add(ws.cell(row=r, column=COL["confident"]))
                ws.row_dimensions[r].height = 15 * max(2, -(-len(it["item"]["text"]) // 62))
            else:
                ws.cell(row=r, column=COL["confident"]).fill = grey
                ws.row_dimensions[r].height = 30
            for c in range(1, len(ANNOTATION_COLUMNS) + 1):
                cell = ws.cell(row=r, column=c)
                if shade and not (c == COL["confident"] and not first):
                    cell.fill = shade
                if first:
                    cell.border = top
                if c in (COL["note"],):
                    cell.alignment = wrap
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


# ----------------------------------------------------------------------------------------------------- main

def build(split: str, seed: int, out_dir: Path = OUT_DIR, owner_allows: bool = False, runs_dir: Path = RUNS_DIR) -> dict:
    records = load_records(split, owner_allows)
    mismatch, runs_used = first_mismatch_ids(runs_dir, split, len(records))
    cands, dropped = candidates(records, mismatch, example_record_ids())
    packs = layout(select(cands, seed), seed)
    check_design(packs)
    suffix = "" if split == "dev" else f"_{split}"
    pack_dir = out_dir / f"packs{suffix}"
    key = {"split": split, "seed": seed, "first_mismatch_runs": runs_used, "items": []}
    report = {"split": split, "seed": seed, "records_in_split": len(records), "candidates": len(cands),
              "dropped": dict(dropped), "hard_pool_sizes": {k: sum(k in c["flags"] for c in cands) for k in HARD_CATEGORIES},
              "first_mismatch_runs": runs_used, "templates_in_pool": len({c["sig"] for c in cands}), "packs": []}
    for p in packs:
        path = pack_dir / f"annotation_pack_{p['pack']}.xlsx"
        write_pack(path, p["pack"], p["items"])
        for c in p["items"]:
            key["items"].append({"item_id": c["item_id"], "pack": p["pack"], "position": c["position"], "record_id": c["record_id"],
                                 "is_common": c["is_common"], "bucket": c["bucket"],
                                 "numbers": [{"number_id": n["number_id"], "number_raw": n["number_raw"]} for n in c["item"]["numbers"]]})
        nums = sum(c["n"] for c in p["items"])
        report["packs"].append({
            "pack": p["pack"], "file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "records": len(p["items"]), "common": sum(c["is_common"] for c in p["items"]), "numbers_total": nums,
            "numbers_in_common": sum(c["n"] for c in p["items"] if c["is_common"]), "within_number_target": nums <= NUMBER_TARGET,
            "buckets": dict(sorted(Counter(c["bucket"] for c in p["items"]).items())),
            "common_positions": [c["position"] for c in p["items"] if c["is_common"]]})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"key_{split}.json").write_text(json.dumps(key, indent=1))
    recs = {c["record_id"]: c for p in packs for c in p["items"]}
    report["distinct_records"] = len(recs)
    report["distinct_templates_in_set"] = len({c["sig"] for c in recs.values()})
    report["any_two_packs"] = {"distinct_records": N_COMMON + 2 * N_UNIQUE, "double_annotated": N_COMMON}
    (out_dir / f"build_report_{split}.json").write_text(json.dumps(report, indent=1))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", default="dev", choices=["dev", "test"], help="which data split to sample (default: dev)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--owner-allows-held-out-split", action="store_true",
                    help="only the project owner sets this, together with FL_ALLOW_TEST_SPLIT=1")
    a = ap.parse_args()
    print(json.dumps(build(a.split, a.seed, owner_allows=a.owner_allows_held_out_split), indent=1))   # counts only, no row text
