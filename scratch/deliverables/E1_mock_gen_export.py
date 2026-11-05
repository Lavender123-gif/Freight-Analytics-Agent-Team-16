"""E1: redacted copy of the dev split for external mock-data generation.

Run from repo root:
    sh scratch/deliverables/run.sh E1_mock_gen_export.py            # scan only, writes nothing outside the repo
    (run.sh forwards only one argument; for --write call uv run with the same --with list as run.sh)

Reads data/processed/dev.csv only (every row). Never touches test.csv or the raw Excel. No LLM calls.
Name/email redaction reuses scratch/prototype/gate.person_spans and EMAIL_RE (imported read-only), with a
short allowlist of non-name words (NOT_PERSON).

Outputs
- --write: ~/Desktop/CC Response/ppg-mock-gen/agent/input/samples/{dev_redacted.jsonl, README.md}
- always:  data/interim/deliverables/E1/ (git-ignored): seed.txt, scan_report.md, and with --write the
           code-to-original lookup files (carrier_codes.csv, group_codes.csv, number_codes.csv, row_map.csv).
           None of the lookups goes to the export folder.
"""

from __future__ import annotations

import csv
import json
import re
import secrets
import sys
from collections import Counter, defaultdict
from pathlib import Path
from random import Random

import pandas as pd

from _shared import DEV_CSV, ROOT, rowlevel_dir

sys.path.insert(0, str(ROOT / "scratch" / "prototype"))
from config import CANADIAN, US_STATES  # noqa: E402
from gate import EMAIL_RE, person_spans  # noqa: E402

EXPORT = Path.home() / "Desktop" / "CC Response" / "ppg-mock-gen" / "agent" / "input" / "samples"
INTERIM = rowlevel_dir("E1")
LONG_NUM = re.compile(r"(?<!\d)\d{6,}(?!\d)")
ID_COLS = ["SHIPMENT_GID", "PK", "Invoice/Bill ID", "SAP BOL", "Shipment Number", "Carrier Invoice"]
PHONE_RES = [
    re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)"),
    re.compile(r"(?<!\d)\d{3}[\s.-]\d{4}(?!\d)"),
    re.compile(r"\b(?:PH|PHONE|TEL|CELL|MOBILE|FAX|EXT|CALL(?:ED)?)\b\.?\s*:?\s*#?\s*\d", re.I),
]
NAME_CUES = re.compile(
    r"\b(?:ATTN|ATTENTION|CONTACT|SPOKE (?:WITH|TO)|TALKED TO|CALLED|PER|BY|FROM|TO|CC|MR|MRS|MS|DR|THANKS|THANK YOU|"
    r"REGARDS|SIGNED|NAME)\b\.?:?\s+([A-Z][A-Z'-]+(?:\s+[A-Z][A-Z'-]+)?)", re.I)


# Spans the NER marks as PERSON that are not names (checked by hand on the dev scan, 2026-11-03, user-approved):
# "SPECIAL DELV. CHG", the typo "ENTERD", and TONU (truck ordered not used). Kept as written.
# PURCAHSE (typo for PURCHASE) and LINEHAUL are hit only when the source spacing is kept (2026-11-03, user-approved).
NOT_PERSON = {"DELV", "ENTERD", "TONU", "PURCAHSE", "LINEHAUL"}


def redact(text: str) -> tuple[str, int, int]:
    """Same as scratch/prototype/gate.redact, minus spans listed in NOT_PERSON."""
    repl: list[tuple[int, int, str]] = []
    names: dict[str, int] = {}
    for a, b in person_spans(text):
        key = text[a:b]
        if key.strip().upper() in NOT_PERSON:
            continue
        names.setdefault(key, len(names) + 1)
        repl.append((a, b, f"[PERSON_{names[key]}]"))
    emails: dict[str, int] = {}
    for m in EMAIL_RE.finditer(text):
        emails.setdefault(m.group(0), len(emails) + 1)
        repl.append((m.start(), m.end(), f"[EMAIL_{emails[m.group(0)]}]"))
    out = text
    for a, b, r in sorted(repl, reverse=True):
        out = out[:a] + r + out[b:]
    return out, len(names), len(emails)


def load_seed() -> int:
    p = INTERIM / "seed.txt"
    if not p.exists():
        p.write_text(str(secrets.randbits(64)))
    return int(p.read_text().strip())


def country(state: str | None) -> str | None:
    if not isinstance(state, str) or not state:
        return None
    return "CAN" if state in CANADIAN else "USA" if state in US_STATES else None   # 3-letter: CA is a state code (California)


def build():
    df = pd.read_csv(DEV_CSV, dtype=str)
    assert DEV_CSV.name == "dev.csv"
    df["row"] = range(len(df))
    df["ts"] = pd.to_datetime(df["Event Date"], format="%Y-%m-%d %H:%M:%S")
    df["text_norm"] = df["Descritipion"].fillna("")   # spaces and tabs kept exactly as in the source
    rng = Random(load_seed())

    carriers = sorted(df["Carrier"].unique())
    rng.shuffle(carriers)
    assert len(carriers) <= 26
    carrier_code = {c: f"CARRIER_{chr(65 + i)}" for i, c in enumerate(carriers)}

    gids = sorted(df["SHIPMENT_GID"].unique())
    rng.shuffle(gids)
    group_code = {g: f"G{i + 1:04d}" for i, g in enumerate(gids)}

    # 6+ digit runs: one random replacement per distinct value, same length, never equal to any original run
    originals = {m.group(0) for t in df["text_norm"] for m in LONG_NUM.finditer(t)}
    number_code: dict[str, str] = {}
    for orig in sorted(originals):
        while True:
            first = rng.choice("0123456789" if orig[0] == "0" else "123456789")
            cand = first + "".join(rng.choice("0123456789") for _ in range(len(orig) - 1))
            if cand not in originals and cand not in number_code.values():
                number_code[orig] = cand
                break

    df = df.sort_values(["SHIPMENT_GID", "ts", "row"]).reset_index(drop=True)
    df["seq_in_group"] = df.groupby("SHIPMENT_GID").cumcount() + 1
    df["group_size"] = df.groupby("SHIPMENT_GID")["row"].transform("size")
    prev = df.groupby("SHIPMENT_GID")["ts"].shift()
    df["days_since_prev"] = ((df["ts"] - prev).dt.total_seconds() / 86400).round(3)
    df["days_since_first"] = ((df["ts"] - df.groupby("SHIPMENT_GID")["ts"].transform("min")).dt.total_seconds()
                              / 86400).round(3)

    recs, mid = [], []
    for _, r in df.iterrows():
        red, n_p, n_e = redact(r.text_norm) if r.text_norm else ("", 0, 0)
        final = LONG_NUM.sub(lambda m: number_code[m.group(0)], red)
        mid.append(red)
        recs.append({
            "group_id": group_code[r.SHIPMENT_GID],
            "seq_in_group": int(r.seq_in_group),
            "group_size": int(r.group_size),
            "days_since_prev": None if pd.isna(r.days_since_prev) else float(r.days_since_prev),
            "days_since_first": float(r.days_since_first),
            "carrier": carrier_code[r.Carrier],
            "text": final if r.text_norm else None,
            "delta": float(r.Delta),
            "currency": None,
            "origin_country": country(r["Source State"]),
            "origin_state": r["Source State"] if isinstance(r["Source State"], str) else None,
            "destination_country": country(r["Destination State"]),
            "destination_state": r["Destination State"] if isinstance(r["Destination State"], str) else None,
            "_row": int(r.row), "_n_person": n_p, "_n_email": n_e,
        })
    recs.sort(key=lambda x: (x["group_id"], x["seq_in_group"]))
    for i, x in enumerate(recs):
        x["record_id"] = f"R{i + 1:04d}"
    return df, recs, carrier_code, group_code, number_code


def scan(df, recs, number_code) -> tuple[str, dict]:
    """Residual check on every final text. Returns (markdown report, counts)."""
    texts = [(x["record_id"], x["text"] or "") for x in recs]
    gold = {t.strip().upper() for t in (ROOT / "data" / "interim" / "person_tokens.txt").read_text().split() if t.strip()}
    try:
        dict_words = {w.strip().upper() for w in open("/usr/share/dict/words") if w.strip().islower()}
    except OSError:
        dict_words = set()
    word_freq = Counter(w for _, t in texts for w in set(re.findall(r"[A-Z][A-Z'-]+", t.upper())))

    id_vals = set()
    for c in ID_COLS + ["Source Address", "Destination Address"]:
        for v in df[c].dropna():
            v = v.strip().upper()
            if len(v) >= 4:
                id_vals.add(v)
                if v.startswith("PPGTM."):
                    id_vals.add(v[6:])
    scac = {c.upper().removeprefix("PPGTM.") for c in df["Carrier"].unique()}

    found: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for rid, t in texts:
        if not t:
            continue
        u = t.upper()
        for m in re.finditer(r"\S*[A-Za-z0-9._-]@[A-Za-z]\S*", t):   # '@' used as a price ("@ $150") is not an email
            found["email"].append((rid, m.group(0), t))
        for m in EMAIL_RE.finditer(t):
            found["email"].append((rid, m.group(0), t))
        for rx in PHONE_RES:
            for m in rx.finditer(t):
                found["phone"].append((rid, m.group(0), t))
        for w in set(re.findall(r"[A-Z][A-Z'-]+", u)):
            if w in gold:
                found["name_gold_token"].append((rid, w, t))
        for a, b in person_spans(t, title_case=True, context_rules=True):
            found["name_presidio_titlecase"].append((rid, t[a:b], t))
        for m in NAME_CUES.finditer(t):
            words = [w for w in m.group(1).upper().split() if not w.startswith("[")]
            if words and any(w not in dict_words for w in words):
                found["name_after_cue_word"].append((rid, m.group(0), t))
        for w in set(re.findall(r"\b[A-Z][A-Z'-]{2,}\b", u)):
            if w not in dict_words and word_freq[w] <= 2 and not re.search(r"\d", w):
                found["rare_non_dictionary_word"].append((rid, w, t))
        for v in id_vals:
            if v in u:
                found["id_or_address_value"].append((rid, v, t))
        for w in set(re.findall(r"\b[A-Z0-9]{4}\b", u)) & scac:
            found["carrier_scac"].append((rid, w, t))
        for orig in number_code:
            if orig in t:
                found["original_long_number_left"].append((rid, orig, t))

    lines = ["# E1 residual scan (final export texts, before writing)", "",
             f"records: {len(recs)}; non-empty texts: {sum(1 for _, t in texts if t)}; "
             f"with [PERSON]: {sum(1 for x in recs if x['_n_person'])}; with [EMAIL]: {sum(1 for x in recs if x['_n_email'])}",
             ""]
    counts = {}
    for cat in ["email", "phone", "name_gold_token", "name_presidio_titlecase", "name_after_cue_word",
                "rare_non_dictionary_word", "id_or_address_value", "carrier_scac", "original_long_number_left"]:
        hits = found.get(cat, [])
        counts[cat] = len(hits)
        lines.append(f"## {cat}: {len(hits)} hits")
        by_tok: dict[str, list[str]] = defaultdict(list)
        ex: dict[str, str] = {}
        for rid, tok, t in hits:
            by_tok[tok].append(rid)
            ex.setdefault(tok, t)
        for tok, rids in sorted(by_tok.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"- `{tok}` x{len(rids)} ({', '.join(sorted(set(rids))[:5])}): {ex[tok]}")
        lines.append("")
    return "\n".join(lines), counts


README = """# dev_redacted.jsonl

Redacted copy of the development split of the PPG freight dispute data, for generating synthetic test data.
One JSON object per line, one line per row of the dev split (no rows dropped or merged).

- Records: {n_rec}
- Shipment groups: {n_grp} (group sizes: {sizes})
- Carrier codes: {n_car} (`CARRIER_A` ... `CARRIER_{last}`)
- Rows with empty text: {n_empty}; rows with a `[PERSON_n]` placeholder: {n_p}; with `[EMAIL_n]`: {n_e}

Sorted by `group_id`, then `seq_in_group`.

## Fields

| field | type | meaning |
|---|---|---|
| `record_id` | string | `R0001`...; sequential in this file, no link to any source ID |
| `group_id` | string | `G0001`...; random label. Rows with the same `group_id` belong to the same shipment. Nothing else is encoded |
| `seq_in_group` | int | 1-based order of the row within its shipment, by event time (ties keep the source row order) |
| `group_size` | int | number of rows in the shipment |
| `days_since_prev` | number or null | days since the previous row of the same shipment (3 decimals; 0 = same timestamp); null for the first row |
| `days_since_first` | number | days since the first row of the same shipment |
| `carrier` | string | carrier code; the same carrier always has the same code |
| `text` | string or null | the carrier's free-text explanation, redacted (see below); null when the source was empty |
| `delta` | number | Invoice Amount - Shipment Amount, 2 decimals, unchanged |
| `currency` | null | the source has no currency column; always null. Any currency mentioned in `text` is left as written |
| `origin_country`, `destination_country` | `USA` / `CAN` | derived from the state/province code (Canadian provinces -> `CAN`, US states and PR -> `USA`). Three-letter codes so they cannot be confused with the state code `CA` (California). The source's own `US/CAN` column is `US` on every row and is not used |
| `origin_state`, `destination_state` | string | two-letter state/province code as in the source. Note `CA` here means California |

## Text redaction

Spaces and tabs are kept exactly as in the source (no collapsing or trimming; a tab appears as `\\t` in the JSON).

1. Personal names -> `[PERSON_n]`, email addresses -> `[EMAIL_n]` (n numbers distinct values within one text).
   Names are found by an NER model plus a few context rules, so recall is not perfect. Five words the model
   wrongly took for names (DELV, ENTERD, TONU, PURCAHSE, LINEHAUL) are kept as written.
2. Digit runs of 6 or more digits (invoice/order-type numbers) are replaced by random digits of the same length.
   The same original number gets the same replacement everywhere. All other numbers (amounts, dates, times,
   rates, weights) are unchanged.

Removed entirely: shipment, invoice, bill, BOL and PK identifiers, reason code, dispute status, invoice and
shipment amounts, addresses, cities, absolute event dates.

## Notes

- Some shipments contain repeated rows with identical text and timestamp (source export repeats). They are kept,
  visible as `days_since_prev` = 0 with the same `text`.
- The code-to-original lookup tables are not in this folder and are not distributed.
"""


def write(df, recs, carrier_code, group_code, number_code):
    EXPORT.mkdir(parents=True, exist_ok=True)
    pub = ["record_id", "group_id", "seq_in_group", "group_size", "days_since_prev", "days_since_first", "carrier",
           "text", "delta", "currency", "origin_country", "origin_state", "destination_country", "destination_state"]
    with open(EXPORT / "dev_redacted.jsonl", "w") as f:
        for x in recs:
            f.write(json.dumps({k: x[k] for k in pub}, ensure_ascii=False) + "\n")
    sizes = Counter(Counter(x["group_id"] for x in recs).values())
    (EXPORT / "README.md").write_text(README.format(
        n_rec=len(recs), n_grp=len(group_code), n_car=len(carrier_code), last=chr(64 + len(carrier_code)),
        sizes=", ".join(f"{k} rows: {v}" for k, v in sorted(sizes.items())),
        n_empty=sum(1 for x in recs if x["text"] is None), n_p=sum(1 for x in recs if x["_n_person"]),
        n_e=sum(1 for x in recs if x["_n_email"])))

    def dump(name, header, rows):
        with open(INTERIM / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    dump("carrier_codes.csv", ["code", "carrier"], sorted((v, k) for k, v in carrier_code.items()))
    dump("group_codes.csv", ["group_id", "SHIPMENT_GID"], sorted((v, k) for k, v in group_code.items()))
    dump("number_codes.csv", ["replacement", "original"], sorted((v, k) for k, v in number_code.items()))
    dump("row_map.csv", ["record_id", "dev_csv_row"], [(x["record_id"], x["_row"]) for x in recs])


def main():
    df, recs, carrier_code, group_code, number_code = build()
    report, counts = scan(df, recs, number_code)
    (INTERIM / "scan_report.md").write_text(report)
    print(report)
    print(f"\nrecords={len(recs)} groups={len(group_code)} carriers={len(carrier_code)} "
          f"long_numbers_replaced={len(number_code)}")
    if "--write" in sys.argv:
        write(df, recs, carrier_code, group_code, number_code)
        print(f"written: {EXPORT}")
    else:
        print("scan only; nothing written outside the repo")


if __name__ == "__main__":
    main()
