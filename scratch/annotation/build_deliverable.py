"""Task 15 section 3: one clean, English merged annotation table (git-ignored, it holds real text substrings), plus the
combined finalisation + re-judging log. Reads only the returned packs, the task-14 finalisation and the task-15
re-judging; never a run.
Usage: uv run python scratch/annotation/build_deliverable.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agreement import derive  # noqa: E402
from import_annotations import load_long  # noqa: E402

from freight_lineitems.config import ROOT  # noqa: E402
from freight_lineitems.records import group_explanations, load_dev  # noqa: E402
from freight_lineitems.textprep import normalize  # noqa: E402

A = ROOT / "data" / "interim" / "annotation"
OUT = A / "deliverable"
TAXWORD = re.compile(r"\b(GST|HST|PST|QST|TAX)\b")
COLUMNS = ["record_key", "number_id", "substring", "annotators", "p1_what", "p1_claim", "p1_category", "p2_what", "p2_claim",
           "p2_category", "p3_what", "p3_claim", "p3_category", "final_what", "final_claim", "final_category",
           "finalisation_rules", "rejudge_class", "rejudged_claim", "rejudged_category", "needs_person_by_standard",
           "needs_person_reasons"]


def main() -> None:
    raw = load_long(A / "final" / "raw_import.csv")
    final = derive(load_long(A / "final" / "final_gold.csv"))
    log = list(csv.DictReader((A / "final" / "correction_log.csv").open()))
    rej = json.loads((OUT / "rejudge.json").read_text())
    recs = {r.record_id: r for r in load_dev()}
    groups = {}
    for g in group_explanations(list(recs.values())):
        for r in g:
            groups[r.record_id] = g
    rules_of = {}
    for x in log:
        if x["record_id"]:
            rules_of.setdefault((x["record_id"], x["number_id"]), set()).add(x["rule"])
    rows = []
    for (rid, nid), fg in final.groupby(["record_id", "number_id"], sort=False):
        f = fg.iloc[0]
        ra = raw[(raw.record_id == rid) & (raw.number_id == nid)]
        per = {a: ra[ra.annotator == a].iloc[0] if (ra.annotator == a).any() else None for a in ("P1", "P2", "P3")}
        j = rej.get(rid, {})
        o = (j.get("gold_overrides") or {}).get(nid, {})
        rows.append({"record_key": rid, "number_id": nid, "substring": f["number_raw"],
                     "annotators": "+".join(a for a, v in per.items() if v is not None),
                     **{f"{a.lower()}_{k}": (v[k] if v is not None else "") for a, v in per.items() for k in ("what", "claim", "category")},
                     "final_what": f["what"], "final_claim": f["claim"], "final_category": f["category"],
                     "finalisation_rules": "+".join(sorted(rules_of.get((rid, nid), set()) | rules_of.get((rid, ""), set()))),
                     "rejudge_class": j.get("class", ""), "rejudged_claim": o.get("claim", f["claim"] if j else ""),
                     "rejudged_category": o.get("category", f["category"] if j else ""), "needs_person_by_standard": "", "needs_person_reasons": ""})
    kept = {r["record_key"] for r in rows}
    for (rid, nid), rg in raw[~raw.record_id.isin(kept)].groupby(["record_id", "number_id"], sort=False):   # dropped by R-3 / R-4
        per = {a: rg[rg.annotator == a].iloc[0] if (rg.annotator == a).any() else None for a in ("P1", "P2", "P3")}
        rows.append({"record_key": rid, "number_id": nid, "substring": rg.iloc[0]["number_raw"],
                     "annotators": "+".join(a for a, v in per.items() if v is not None),
                     **{f"{a.lower()}_{k}": (v[k] if v is not None else "") for a, v in per.items() for k in ("what", "claim", "category")},
                     "final_what": "DROPPED", "final_claim": "DROPPED", "final_category": "DROPPED",
                     "finalisation_rules": "+".join(sorted(rules_of.get((rid, nid), set()))), "rejudge_class": "",
                     "rejudged_claim": "", "rejudged_category": "", "needs_person_by_standard": "not judged", "needs_person_reasons": ""})
    t15 = {r["record_id"]: r for r in json.loads((ROOT / "data" / "interim" / "eval" / "t15" / "rows_annotations_after.json").read_text())}
    for r in [r for r in rows if r["final_claim"] != "DROPPED"]:   # record-level truth from the confusion step (truth side only: gates G1-G8 against the annotations)
        x = t15[r["record_key"]]
        r["needs_person_by_standard"] = "yes" if x["positive"] else "no"
        r["needs_person_reasons"] = "+".join(x["gates"])
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "merged_annotations.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with (OUT / "finalisation_and_rejudge_log.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(log[0]) + ["basis"])
        w.writeheader()
        for x in log:
            w.writerow(x | {"basis": "task 14 finalisation rule " + x["rule"]})
        for rid, j in rej.items():
            w.writerow({"file": "task 15 re-judging", "row": "", "record_id": rid, "item_id": "", "annotator": "FINAL",
                        "number_id": "", "field": "rejudge_class", "before": "UNCLEAR", "after": j["class"], "rule": j["class"],
                        "basis": j["basis"]})
            for nid, ov in j["gold_overrides"].items():
                w.writerow({"file": "task 15 re-judging", "row": "", "record_id": rid, "item_id": "", "annotator": "FINAL",
                            "number_id": nid, "field": "claim/category", "before": "UNCLEAR", "after": f"{ov['claim']}/{ov['category']}",
                            "rule": j["class"], "basis": j["basis"]})
    print(f"{len(rows)} number rows, {len({r['record_key'] for r in rows})} records -> {OUT / 'merged_annotations.csv'}")


if __name__ == "__main__":
    main()
