"""T13 step 2.1: turn the client's Addenda B accessorial list (PDF) into a table of (name, EDI code).

Read-only on the PDF. No model calls. The full table is client material: it is written only to the git-ignored
folder data/interim/deliverables/T13/ and this script prints counts, never the whole list.

How a row is read: words are grouped into lines by their vertical position; the word that starts in the code
column (x >= CODE_X) is the EDI code, everything left of it is the name. A line with no word in the code column
is the first half of an entry that wraps onto the next line. Nothing in the source text is corrected.

pdfplumber is not a project dependency (this task does not change pyproject.toml); run with:
  uv run --with pdfplumber python docs/deliverables/T13-taxonomy-mapping/scripts/s1_extract_addenda.py
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[4]
PDF = ROOT / "data" / "incoming" / "2026-11-13" / "carrier_addendum-b-accessorial-list_ada.pdf"
OUT = ROOT / "data" / "interim" / "deliverables" / "T13"
CODE_X = 380          # the code column starts at x of about 390 on every page; names never reach it
HEADER = {"Addenda B", "Accessorial List", "Description EDI Code"}
CODE_RE = re.compile(r"^[A-Z0-9]{3}$")


def lines_of(page) -> list[tuple[str, str]]:
    """[(name part, code part)] per printed line, top to bottom."""
    by_top: dict[int, list[dict]] = defaultdict(list)
    for w in page.extract_words(keep_blank_chars=False):
        key = next((t for t in by_top if abs(t - w["top"]) <= 3), round(w["top"]))
        by_top[key].append(w)
    out = []
    for top in sorted(by_top):
        ws = sorted(by_top[top], key=lambda w: w["x0"])
        name = " ".join(w["text"] for w in ws if w["x0"] < CODE_X)
        code = " ".join(w["text"] for w in ws if w["x0"] >= CODE_X)
        out.append((name, code))
    return out


def main() -> None:
    rows, anomalies, pending = [], [], None
    with pdfplumber.open(PDF) as pdf:
        n_pages = len(pdf.pages)
        for pno, page in enumerate(pdf.pages, 1):
            for name, code in lines_of(page):
                if f"{name} {code}".strip() in HEADER:
                    continue
                if not code:                      # first half of a wrapped entry (or a row without a code)
                    if pending:
                        anomalies.append({"type": "no_code", "page": pending[1], "name": pending[0]})
                    pending = (name, pno)
                    continue
                if pending:
                    anomalies.append({"type": "wrapped", "page": pno, "name": f"{pending[0]} {name}", "code": code})
                    name, pending = f"{pending[0]} {name}", None
                if not CODE_RE.match(code):
                    anomalies.append({"type": "odd_code", "page": pno, "name": name, "code": code})
                if not name:
                    anomalies.append({"type": "no_name", "page": pno, "code": code})
                rows.append({"row": len(rows) + 1, "page": pno, "name": name, "edi_code": code})
    if pending:
        anomalies.append({"type": "no_code", "page": pending[1], "name": pending[0]})

    by_name: dict[str, list[str]] = defaultdict(list)
    by_code: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by_name[r["name"]].append(r["edi_code"])
        by_code[r["edi_code"]].append(r["name"])
    # observations only; the source text is kept as printed
    for n in by_name:
        if n != n.upper():
            anomalies.append({"type": "not_upper_case", "name": n})
        if re.search(r"\s-\S|\S-\s|,\S", n):
            anomalies.append({"type": "irregular_spacing", "name": n})
        if n.split()[-1] in by_name[n] and len(n.split()) > 1:
            anomalies.append({"type": "name_ends_with_its_code", "name": n})
    for c, ns in by_code.items():
        if len(ns) > 1:
            anomalies.append({"type": "code_on_2plus_rows", "code": c, "names": ns})
    upper = defaultdict(set)
    for n in by_name:
        upper[re.sub(r"[^A-Z0-9]", "", n.upper())].add(n)
    for v in upper.values():
        if len(v) > 1:
            anomalies.append({"type": "names_differ_only_in_case_or_punctuation", "names": sorted(v)})

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "addenda_b_rows.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["row", "page", "name", "edi_code"])
        w.writeheader()
        w.writerows(rows)
    with (OUT / "addenda_b_names.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "n_codes", "edi_codes"])
        for n in sorted(by_name):
            w.writerow([n, len(by_name[n]), " ".join(by_name[n])])
    multi = {n: len(c) for n, c in by_name.items() if len(c) > 1}
    dist = defaultdict(int)
    for c in by_name.values():
        dist[len(c)] += 1
    summary = {
        "pdf": PDF.name, "pages": n_pages, "rows": len(rows), "distinct_names": len(by_name),
        "distinct_codes": len(by_code), "numeric_codes": sum(1 for c in by_code if c.isdigit()),
        "alpha_codes": sum(1 for c in by_code if not c.isdigit()),
        "names_with_2plus_codes": len(multi), "rows_under_names_with_2plus_codes": sum(multi.values()),
        "names_by_number_of_codes": dict(sorted(dist.items())),
        "names_with_2plus_codes_detail": dict(sorted(multi.items(), key=lambda kv: (-kv[1], kv[0]))),
        "anomalies": anomalies,
    }
    (OUT / "extract_report.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k != "names_with_2plus_codes_detail"}, indent=1, ensure_ascii=False))
    print("names with 2+ codes:", "; ".join(f"{n} ({k})" for n, k in summary["names_with_2plus_codes_detail"].items()))


if __name__ == "__main__":
    main()
