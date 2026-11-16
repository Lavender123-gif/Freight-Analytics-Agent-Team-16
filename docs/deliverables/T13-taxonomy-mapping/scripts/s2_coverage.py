"""T13 steps 2.2 (counts), 2.3 and 2.4: how much of the dev split's charges land on the client's list.

Read-only replay of ONE stored run (default: the full dev run of leg 2, 20261110-195411-devFull-4823). No model
calls, nothing is re-read by a model, no source or config file is changed.

Unit: one counted amount of one distinct explanation.
  distinct explanation = one (SHIPMENT_GID, Event Date, text) group, as in T12
  counted amount       = a number the stored reading marks CLAIMED or UNPAID with kind CHARGE_AMOUNT,
                         UNSPECIFIED_AMOUNT or TAX_AMOUNT (the same rule as T12 s2_bol_replay.items)
Each counted amount carries our charge code(s); the hand-made mapping in t13_mapping.py folds it onto the list.
An amount with two codes ('A and B $x') cannot be split, so it takes the weaker class of its codes.
Amounts with no code at all (the text names no charge) are reported apart: no code list can place them.
Money: absolute values, CAD and USD added without conversion (shares only; per-currency sums are in the JSON).

Prints aggregates only. Row-level detail goes to data/interim/deliverables/T13/ (git-ignored).
Run: uv run python docs/deliverables/T13-taxonomy-mapping/scripts/s2_coverage.py [run_dir_name]
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t13_mapping as m  # noqa: E402

from freight_lineitems.checks import region_value  # noqa: E402
from freight_lineitems.config import CODES, ROOT, RUNS_DIR  # noqa: E402

OUT = ROOT / "data" / "interim" / "deliverables" / "T13"
RUN = sys.argv[1] if len(sys.argv) > 1 else "20261110-195411-devFull-4823"
COUNTED = {"CLAIMED", "UNPAID"}
KINDS = ("CHARGE_AMOUNT", "UNSPECIFIED_AMOUNT", "TAX_AMOUNT")
CLASSES = ["1_exact_or_approx", "2_one_to_many", "3_child", "4_extension", "5_other"]
CLASS_OF = {m.EXACT: CLASSES[0], m.APPROX: CLASSES[0], m.ONE_TO_MANY: CLASSES[1], m.CHILD: CLASSES[2], m.NONE: CLASSES[3]}


def class_of(code: str) -> str:
    return CLASSES[4] if code == "OTHER" else CLASS_OF[m.MAPPING[code][0]]


def norm_phrase(p: str | None) -> str:
    p = " ".join((p or "").upper().split())
    return m.OTHER_ALIASES.get(p, p)


def load_names() -> dict[str, list[str]]:
    with (OUT / "addenda_b_names.csv").open() as f:
        return {r["name"]: r["edi_codes"].split() for r in csv.DictReader(f)}


def counted_amounts(rec: dict) -> list[dict]:
    f = rec["facts"]
    val = {n["id"]: Decimal(n["value"]) for n in f["number_table"]["numbers"]}
    val |= {u["id"]: region_value(u["raw"]) for u in f["number_table"]["unrecognized"]}
    label = {li["amount_ref"]: li.get("raw_charge_label") for li in f["reading"].get("line_items", [])}
    js = list(f["reading"]["numbers"]) + [u["as_number"] | {"id": u["region_id"]} for u in f["reading"].get("unrecognized_reads", [])]
    out = []
    for j in js:
        if j["status"] in COUNTED and j["kind"] in KINDS:
            out.append({"record_id": rec["record_id"], "codes": list(j["charge_codes"]), "amount": abs(val[j["id"]]),
                        "credit": bool(j["is_credit"]), "currency": f["currency"], "label": label.get(j["id"]) or "",
                        "other_phrase": norm_phrase(j.get("other_phrase")) if "OTHER" in j["charge_codes"] else ""})
    return out


def main() -> None:
    names = load_names()
    # --- 2.2 sanity: the mapping covers exactly the codes of the current taxonomy and only real client names
    assert set(m.MAPPING) == set(CODES), sorted(set(m.MAPPING) ^ set(CODES))
    missing = sorted(m.used_names() - set(names))
    assert not missing, missing
    by_type = Counter(t for t, *_ in m.MAPPING.values())
    target_names = {n for _t, ns, _p, _w in m.MAPPING.values() for n in ns}
    res: dict = {"run": RUN, "taxonomy_codes": len(CODES),
                 "mapping_by_type": {m.TYPE_ZH[t]: by_type[t] for t in (m.EXACT, m.APPROX, m.ONE_TO_MANY, m.CHILD, m.NONE)},
                 "client_names_used_as_target": len(target_names),
                 "client_names_used_incl_extension_parents": len(m.used_names()),
                 "target_names_with_one_edi_code": sum(1 for n in target_names if len(names[n]) == 1),
                 "target_names_with_2plus_edi_codes": sum(1 for n in target_names if len(names[n]) > 1)}

    # --- 2.3 coverage on the stored dev run
    recs = [json.loads(line) for line in (RUNS_DIR / RUN / "records.jsonl").open()]
    seen, units = set(), Counter()
    rows: list[dict] = []
    for r in recs:
        f, s = r["facts"], r["facts"]["source"]
        assert s["source"] == "dev", s["source"]
        k = (s["shipment_key"], s["event_date"], f["text_sha256"])
        if k in seen:
            units["rows_that_repeat_an_explanation"] += 1
            continue
        seen.add(k)
        units["distinct_explanations"] += 1
        if f["parse_status"] != "PASSED_CHECKS" or not f["reading"]:
            units["explanations_reading_not_passed"] += 1
            continue
        got = counted_amounts(r)
        units["explanations_with_counted_amounts" if got else "explanations_passed_without_counted_amount"] += 1
        rows += got
    res["units"] = {"rows_in_run": len(recs), **units, "counted_amounts": len(rows)}

    n_cls, amt_cls, cur_cls = Counter(), Counter(), defaultdict(Counter)
    per_code = defaultdict(lambda: [0, Decimal(0)])
    per_name_n: Counter = Counter()
    single_edi = [0, Decimal(0)]
    for x in rows:
        if not x["codes"]:
            x["class"] = "0_no_charge_named"
        else:
            x["class"] = max(class_of(c) for c in x["codes"])       # class names sort from strongest to weakest
            if len(x["codes"]) > 1:
                units["amounts_with_2_codes"] += 1
        n_cls[x["class"]] += 1
        amt_cls[x["class"]] += x["amount"]
        cur_cls[x["class"]][x["currency"]] += x["amount"]
        tgt = []
        for c in x["codes"]:
            per_code[c][0] += 1
            per_code[c][1] += x["amount"] if len(x["codes"]) == 1 else Decimal(0)
            typ, ns, ext_parent, _ = m.MAPPING[c]
            tgt += ns or ([f"[ext under] {ext_parent}"] if ext_parent else [])
            for n in ns:
                per_name_n[n] += 1
        x["client_names"] = " | ".join(dict.fromkeys(tgt))
        # EDI code decidable from the name alone: class 1, one code, a single client name that has a single EDI code
        if x["class"] == CLASSES[0] and all(len(names[n]) == 1 for c in x["codes"] for n in m.MAPPING[c][1]):
            single_edi[0] += 1
            single_edi[1] += x["amount"]
    named = [x for x in rows if x["codes"]]
    tot_n, tot_a = len(named), sum((x["amount"] for x in named), Decimal(0))
    res["units"]["amounts_with_2_codes"] = units["amounts_with_2_codes"]
    res["coverage"] = {
        "named_counted_amounts": tot_n, "named_money": str(tot_a),
        "classes": {c: {"n": n_cls[c], "n_share": round(n_cls[c] / tot_n, 4), "money": str(amt_cls[c]),
                        "money_share": round(float(amt_cls[c] / tot_a), 4),
                        "money_by_currency": {k: str(v) for k, v in sorted(cur_cls[c].items())}} for c in CLASSES},
        "no_charge_named": {"n": n_cls["0_no_charge_named"], "money": str(amt_cls["0_no_charge_named"]),
                            "money_by_currency": {k: str(v) for k, v in sorted(cur_cls["0_no_charge_named"].items())}},
        "class1_where_name_has_one_edi_code": {"n": single_edi[0], "money": str(single_edi[1])},
    }
    pt = "PENDING.PURCHASED_TRANSPORTATION"
    rest = [x for x in named if pt not in x["codes"]]
    rn, ra = len(rest), sum((x["amount"] for x in rest), Decimal(0))
    res["coverage_without_purchased_transportation"] = {
        "n": rn, "money": str(ra),
        "classes": {c: {"n": sum(1 for x in rest if x["class"] == c),
                        "n_share": round(sum(1 for x in rest if x["class"] == c) / rn, 4),
                        "money": str(sum((x["amount"] for x in rest if x["class"] == c), Decimal(0))),
                        "money_share": round(float(sum((x["amount"] for x in rest if x["class"] == c), Decimal(0)) / ra), 4)}
                    for c in CLASSES}}
    res["per_code"] = {c: {"type": m.TYPE_ZH[m.MAPPING[c][0]], "n": per_code[c][0], "money_single_code_amounts": str(per_code[c][1])}
                       for c in CODES}
    res["codes_with_no_dev_occurrence"] = [c for c in CODES if per_code[c][0] == 0]

    # class 5: distinct phrasings in OTHER and whether the list can take them
    oth = defaultdict(lambda: [0, Decimal(0)])
    for x in rows:
        if "OTHER" in x["codes"]:
            oth[x["other_phrase"]][0] += 1
            oth[x["other_phrase"]][1] += x["amount"]
    unjudged = sorted(set(oth) - set(m.OTHER_VERDICTS))
    assert not unjudged, unjudged
    res["other"] = {"distinct_phrasings": len(oth),
                    "phrasings": {p: {"n": v[0], "money": str(v[1]), "client_name": m.OTHER_VERDICTS[p][0]} for p, v in oth.items()},
                    "absorbed_n": sum(v[0] for p, v in oth.items() if m.OTHER_VERDICTS[p][0]),
                    "absorbed_money": str(sum((v[1] for p, v in oth.items() if m.OTHER_VERDICTS[p][0]), Decimal(0)))}

    # --- 2.4 the list seen from the other side
    used = m.used_names()
    irrelevant: dict[str, str] = {}
    for line in (OUT / "unused_irrelevant_names.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            g, n = line.split("\t")
            assert n in names and n not in used, n
            irrelevant[n] = g
    unused = sorted(set(names) - used)
    road = [n for n in unused if n not in irrelevant]
    hit = {n for n, k in per_name_n.items() if k}
    res["list_side"] = {"distinct_names": len(names), "used": len(used), "used_with_dev_occurrences": len(hit & used),
                        "unused": len(unused), "unused_irrelevant": len(irrelevant),
                        "unused_irrelevant_by_group": dict(sorted(Counter(irrelevant.values()).items())),
                        "unused_road_possible": len(road), "unused_road_possible_names": road,
                        "edi_rows_under_used_names": sum(len(names[n]) for n in used),
                        "edi_rows_under_unused_irrelevant": sum(len(names[n]) for n in irrelevant),
                        "edi_rows_under_unused_road_possible": sum(len(names[n]) for n in road)}

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "coverage_detail.csv").open("w", newline="") as f:
        cols = ["record_id", "class", "codes", "client_names", "amount", "credit", "currency", "label", "other_phrase"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for x in rows:
            w.writerow({**{c: x[c] for c in cols if c != "codes"}, "codes": "+".join(x["codes"])})
    with (OUT / "unused_names.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "n_edi_codes", "group"])
        for n in unused:
            w.writerow([n, len(names[n]), irrelevant.get(n, "ROAD_POSSIBLE")])
    (OUT / "coverage.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
