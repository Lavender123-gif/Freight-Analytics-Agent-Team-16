"""Measure the person-name redaction engines (task 10 section 4, steps 1 and 2).

Method: person names that do not occur in the dev split are inserted, at the positions where names really occur
in dev text, into dev sentences. The answer span is therefore known. Three things are measured per engine:
(a) miss rate: the inserted name is not fully masked;
(b) over-masking: a charge-vocabulary word or a digit falls inside a masked span, on the generated cases and on
    every dev record (the dev count must be 0 for an engine to qualify);
(c) digits altered by redaction, by `textprep.redaction_altered_digits` and by an independent comparison of the
    digit runs outside masked spans (must be 0).
Also: runtime per 1000 records, dev records with at least one mask, how much non-name text is masked on dev.

Frames, cases and per-engine word lists contain real dev text and go to the git-ignored data/interim/redaction/.
Only aggregates are printed and written to docs/deliverables/T10-redaction-comparison/results/metrics.json.
No model API is called. The test split is never read (records.load_dev only).

Run: uv run python scratch/redaction/measure.py            (all engines)
     uv run python scratch/redaction/measure.py presidio names_list
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from freight_lineitems import redaction_variants as RV
from freight_lineitems import textprep as T
from freight_lineitems.config import ROOT, RULES
from freight_lineitems.records import load_dev, load_mock

SEED = 20261110
OUT_PRIVATE = ROOT / "data" / "interim" / "redaction"
OUT_PUBLIC = ROOT / "docs" / "deliverables" / "T10-redaction-comparison" / "results"
REVIEWED = ROOT / "data" / "interim" / "person_tokens.txt"      # reviewed list of person tokens in dev (B01)

# ---- synthetic names (none may occur in dev; checked below) -------------------------------------------------
COMMON_FIRST = ("JAMES MARY ROBERT PATRICIA JENNIFER MICHAEL LINDA DAVID BARBARA RICHARD SUSAN JOSEPH JESSICA THOMAS "
                "SARAH KAREN DANIEL NANCY MATTHEW LISA ANTHONY BETTY STEVEN SANDRA KEVIN ASHLEY BRIAN EMILY JASON MELISSA").split()
COMMON_LAST = ("JOHNSON WILLIAMS JONES GARCIA MILLER DAVIS RODRIGUEZ MARTINEZ HERNANDEZ LOPEZ GONZALEZ WILSON ANDERSON "
               "TAYLOR MOORE JACKSON MARTIN THOMPSON HARRIS SANCHEZ CLARK RAMIREZ LEWIS ROBINSON WALKER PEREZ NGUYEN PATEL "
               "KOWALSKI SCHMIDT SMITH").split()
RARE_FIRST = ("THADDEUS XIOMARA ZBIGNIEW OLUWASEUN SAOIRSE ANNELIESE BARTHOLOMEW CAOIMHE DAGNY EZEKIEL FENELLA GWENLLIAN "
              "HYACINTH ISOLDE JOAQUIM KRZYSZTOF LEOPOLDO MAHALIA NIAMH OTTILIE PRZEMYSLAW QUILLON RAGNHILD SIDDHARTH TANVIR "
              "UMBERTO VASILIKI WILHELMINA YEVGENIY ZENOBIA NKECHI HARUTO BONGANI ANOUSHKA").split()
RARE_LAST = ("OKONKWO WOJCIECHOWSKI VANDERHOEVEN ABERNETHY BRZEZINSKI DELACROIX EZENWA FAIRWEATHER GRZYBOWSKI HATHERLEIGH "
             "IYENGAR JAROSZEWICZ KOVALENKO LINDQVIST MWANGI NAKASHIMA OYELARAN PAPADOPOULOS QUARTERMAINE RASMUSSEN "
             "SZCZEPANSKI THISTLEWOOD UZOMA VILLASENOR WICKRAMASINGHE XENAKIS YAMAGUCHI ZELENKO TRELOAR MACGILLIVRAY ODUYA").split()
AMBIG_FIRST = ("BILL MARK ROSE GRACE DREW FRANK CHASE PAT WILL MAY JACK ROB SUE DAWN HOPE FAITH JOY IVY AMBER CRYSTAL DON "
               "GENE RAY ART HERB CLIFF DALE GLEN LANCE PIERCE MILES NORM WADE SKIP RUSTY SANDY PENNY OLIVE VIOLET SUMMER "
               "AUTUMN APRIL JUNE AUGUST").split()
AMBIG_LAST = ("PRICE LONG WHITE BROWN YOUNG KING DAY BAKER COOK HILL WOOD STONE RICH BANKS FIELDS WATERS LITTLE GREEN BLACK "
              "CARTER PORTER MASON HUNTER BELL RICE BEST CASH FORD MARSH POWERS").split()

# ---- synthetic clauses with a name slot (generic English, not carrier phrasing) ----------------------------------
# 'cue': wording of the kind the context rules of some engine were written for (in-sample for those rules).
# 'heldout': wording that no rule in the code names; it was fixed before the engines were measured and must not
#            be added to any rule afterwards (otherwise this group stops being a held-out check).
CUE_CLAUSES = ["APPROVED BY {NAME}", "AUTHORIZED BY {NAME}", "PER {NAME}", "AS PER {NAME}", "SPOKE WITH {NAME}",
               "EMAILED {NAME}", "EMAILED INVOICE TO {NAME}", "CONFIRMED BY {NAME}", "ATTN {NAME}", "CONTACT {NAME}",
               "PER EMAIL FROM {NAME}", "{NAME} FROM PPG APPROVED", "{NAME} APPROVED", "CALLED {NAME}", "REQUESTED BY {NAME}"]
HELDOUT_CLAUSES = ["LEFT VM FOR {NAME}", "WAITING ON {NAME} TO REPLY", "{NAME} IN AP SAID OK TO BILL", "DRIVER {NAME} WAITED",
                   "THANKS {NAME}", "CC {NAME}", "SEE NOTE FROM {NAME}", "{NAME} WILL SEND PO", "OK WITH {NAME}",
                   "FWD TO {NAME} FOR REVIEW", "REP {NAME} ADVISED", "DISPATCHER {NAME} CONFIRMED"]
QUOTA = {"real": 300, "cue": 300, "heldout": 250, "bare": 150}
CLASSES = ["common_single", "common_full", "rare_single", "rare_full", "ambiguous_single", "ambiguous_full"]

DEFAULT_NEAR = RULES["redaction"]["allowlist_near_spelling"]
DEFAULT_THR = RULES["redaction"]["local_ner_threshold"]
CENSUS_CSV = OUT_PRIVATE / "dl_census" / "Names_2010Census.csv"     # optional, public file, downloaded by hand

GENERIC_CUE = re.compile(r"\b(?:PER|BY|WITH|TO|FROM|ATTN|ATTENTION|CONTACT|CONTACTED|CALLED|EMAILED|EMAIL|MR|MS|MRS)\b[ :.]*"
                         r"([A-Z]{3,}(?: [A-Z]{3,})?)")
WORD = re.compile(r"[A-Za-z]+")
DIGITS = re.compile(r"\d+")


def set_engine(name: str) -> None:
    """Select an engine for this process. 'allowlist/all' sets the near-spelling mode of the allowlist."""
    name, _, thr = name.partition("@")                 # 'local_ner@0.3': another score threshold
    engine, _, near = name.partition("/")
    os.environ["FL_REDACTION_ENGINE"] = engine
    RULES["redaction"]["local_ner_threshold"] = float(thr) if thr else DEFAULT_THR
    RULES["redaction"]["allowlist_near_spelling"] = near or DEFAULT_NEAR
    RV._near_targets.cache_clear()


def dev_texts() -> list[str]:
    return [T.normalize(r.text_raw) for r in load_dev()]


def collect_frames(distinct: list[str]) -> tuple[list[dict], dict]:
    """Where person names really occur in dev: runs of reviewed person tokens. Also reports how many of those
    positions the current redactor and the generic cue patterns find, and how many unreviewed candidates they add."""
    gold = set(REVIEWED.read_text().split())
    set_engine("presidio")
    frames, stats = [], Counter()
    for t in distinct:
        runs: list[list[int]] = []
        for m in re.finditer(r"[A-Z][A-Z'.-]*", t):
            if m.group(0) in gold:
                if runs and t[runs[-1][1]:m.start()] == " ":
                    runs[-1][1] = m.end()
                else:
                    runs.append([m.start(), m.end()])
        hits = T.person_spans(t)
        cues = [m.span(1) for m in GENERIC_CUE.finditer(t)
                if all(RV._kind(w) in ("S", "U") for w in m.group(1).split())]
        for a, b in runs:
            stats["positions"] += 1
            by_red = any(x <= a and b <= y for x, y in hits)
            by_cue = any(x < b and a < y for x, y in cues)
            stats["found_by_redactor"] += by_red
            stats["found_by_generic_cue"] += by_cue
            stats["found_by_neither"] += not (by_red or by_cue)
            pieces, pos = [], 0
            for x, y in runs:                             # other real names never reach a test sentence
                pieces += [t[pos:x], "{NAME}" if (x, y) == (a, b) else "[PERSON_9]"]
                pos = y
            frame = "".join(pieces) + t[pos:]
            frames.append({"frame": frame, "shape": re.sub(r"\d+", "0", frame), "n_tokens": len(t[a:b].split())})
        stats["redactor_hits_not_reviewed"] += sum(not any(x < b and a < y for a, b in runs) for x, y in hits)
        stats["cue_candidates_not_reviewed"] += sum(not any(x < b and a < y for a, b in runs) for x, y in cues)
    stats["distinct_shapes"] = len({f["shape"] for f in frames})
    return frames, dict(stats)


def build_names(dev_tokens: set[str]) -> tuple[dict[str, list[str]], dict]:
    pools = {"common_first": COMMON_FIRST, "common_last": COMMON_LAST, "rare_first": RARE_FIRST, "rare_last": RARE_LAST,
             "ambig_first": AMBIG_FIRST, "ambig_last": AMBIG_LAST}
    kept = {k: [n for n in v if n not in dev_tokens] for k, v in pools.items()}
    first, last, amb = RV._names()
    info = {k: {"listed": len(v), "dropped_because_in_dev": len(v) - len(kept[k]), "kept": len(kept[k]),
                "kept_in_bundled_name_list": sum(n in first or n in last for n in kept[k]),
                "kept_flagged_ambiguous_in_list": sum(n in amb for n in kept[k])} for k, v in pools.items()}
    return kept, info


def make_name(cls: str, pools: dict[str, list[str]], rng: random.Random) -> str:
    c = rng.choice
    if cls == "common_single":
        return c(pools["common_first"])
    if cls == "common_full":
        return f"{c(pools['common_first'])} {c(pools['common_last'])}"
    if cls == "rare_single":
        return c(pools["rare_first"] + pools["rare_last"])
    if cls == "rare_full":
        return f"{c(pools['rare_first'])} {c(pools['rare_last'])}"
    if cls == "ambiguous_single":
        return c(pools["ambig_first"])
    kind = rng.randrange(3)
    if kind == 0:
        return f"{c(pools['ambig_first'])} {c(pools['common_last'] + pools['rare_last'])}"
    if kind == 1:
        return f"{c(pools['common_first'])} {c(pools['ambig_last'])}"
    return f"{c(pools['ambig_first'])} {c(pools['ambig_last'])}"


def insert_clause(host: str, clause: str, rng: random.Random) -> str:
    """Put a clause at the end (most real names are at the end), at the start, or at a sentence boundary."""
    r = rng.random()
    cuts = [m.end() for m in re.finditer(r"[.;] ", host)]
    if r < 0.6 or (r >= 0.8 and not cuts):
        return f"{host.rstrip('. ')}. {clause}" if rng.random() < 0.5 else f"{host} {clause}"
    if r < 0.8:
        return f"{clause}. {host}"
    k = rng.choice(cuts)
    return f"{host[:k]}{clause}. {host[k:]}"


def build_cases(frames: list[dict], hosts: list[str], pools: dict[str, list[str]]) -> list[dict]:
    rng = random.Random(SEED)
    shapes = defaultdict(list)
    for f in frames:
        shapes[f["shape"]].append(f["frame"])
    shape_keys = sorted(shapes)
    cases = []
    for group, n in QUOTA.items():
        for i in range(n):
            cls = CLASSES[i % len(CLASSES)]
            name = make_name(cls, pools, rng)
            if group == "real":
                k = (i // len(CLASSES)) % len(shape_keys)                      # every real shape gets equal weight
                frame = rng.choice(shapes[shape_keys[k]])
                sub = f"real_shape_{k + 1}"
            else:
                host = rng.choice(hosts)
                if group == "bare":
                    clause = "{NAME}"
                    frame = f"{host} {clause}" if rng.random() < 0.7 else f"{clause} - {host}"
                else:
                    clause = rng.choice(CUE_CLAUSES if group == "cue" else HELDOUT_CLAUSES)
                    frame = insert_clause(host, clause, rng)
                sub = clause
            a = frame.index("{NAME}")
            text = frame.replace("{NAME}", name, 1)
            cases.append({"group": group, "sub": sub, "class": cls, "text": text, "span": [a, a + len(name)]})
    return cases


def digit_runs_outside(text: str, spans: list[tuple[int, int]]) -> list[str]:
    keep = "".join(" " if any(a <= i < b for a, b in spans) else ch for i, ch in enumerate(text))
    return DIGITS.findall(keep)


def independent_digit_check(text: str, redacted: str) -> bool:
    """True if a digit was lost or changed. Independent of textprep.redaction_altered_digits: compares the list of
    digit runs of the original, emails and phone numbers cut out, with that of the redacted text, placeholders cut out."""
    cut = [m.span() for rx in (T.EMAIL_RE, T.SPELLED_EMAIL_RE, T.PHONE_RE, T.PLACEHOLDER_RE) for m in rx.finditer(text)]
    before = digit_runs_outside(text, cut)
    after = digit_runs_outside(redacted, [m.span() for m in T.PLACEHOLDER_RE.finditer(redacted)])
    return before != after


def span_stats(text: str, spans: list[tuple[int, int]], ignore: tuple[int, int] | None, vocab: set[str]) -> dict:
    """What the masked spans cover outside `ignore` (the inserted name): digits, charge words, other words."""
    digit = any(text[i].isdigit() for a, b in spans for i in range(a, b) if not (ignore and ignore[0] <= i < ignore[1]))
    charge, other, total = [], [], 0
    for m in WORD.finditer(text):
        if ignore and ignore[0] <= m.start() < ignore[1]:
            continue
        total += 1
        if any(a < m.end() and m.start() < b for a, b in spans):
            (charge if m.group(0).upper() in vocab and len(m.group(0)) >= 3 else other).append(m.group(0).upper())
    return {"digit": digit, "charge": charge, "other": other, "words": total}


def evaluate(engine: str, cases: list[dict], dev: list[str], gold: set[str], vocab: set[str]) -> dict:
    set_engine(engine)
    T.redact("WARM UP APPROVED BY SOMEONE 1.00")          # load models and lists before timing
    res: dict = {"engine": engine}

    # (a) and (b) on the generated cases
    miss = Counter()
    n = Counter()
    over_cases = other_tokens = outside_words = digit_alt = digit_alt_ind = partial = 0
    for c in cases:
        text, (a, b) = c["text"], c["span"]
        spans = T.person_spans(text)
        letters = [i for i in range(a, b) if text[i].isalpha()]
        covered = [any(x <= i < y for x, y in spans) for i in letters]
        missed = not all(covered)
        partial += missed and any(covered)
        for key in ("all", f"class:{c['class']}", f"group:{c['group']}", f"group:{c['group']}|{c['class']}"):
            n[key] += 1
            miss[key] += missed
        st = span_stats(text, spans, (a, b), vocab)
        over_cases += bool(st["digit"] or st["charge"])
        other_tokens += len(st["other"])
        outside_words += st["words"]
        red = T.redact(text)[0]
        digit_alt += T.redaction_altered_digits(text, red)
        digit_alt_ind += independent_digit_check(text, red)
    res["cases"] = {
        "n": len(cases), "missed": miss["all"], "miss_rate": round(miss["all"] / len(cases), 4), "partially_masked": partial,
        "miss_by": {k: {"n": n[k], "missed": miss[k], "rate": round(miss[k] / n[k], 4)} for k in sorted(n) if k != "all"},
        "cases_with_charge_word_or_digit_masked": over_cases,
        "other_host_words_masked": other_tokens, "host_words": outside_words,
        "other_host_words_masked_rate": round(other_tokens / outside_words, 4),
        "digits_altered": digit_alt, "digits_altered_independent": digit_alt_ind}

    # (b), (c) and volume on every dev record
    t0 = time.perf_counter()
    reds = [T.redact(t)[0] for t in dev]
    elapsed = time.perf_counter() - t0
    with_mask = gate = digit_alt = digit_alt_ind = gold_n = gold_missed = words = masked_words = rec_non_name = 0
    non_name: Counter = Counter()
    charge_words: Counter = Counter()
    for t, red in zip(dev, reds):
        spans = T.person_spans(t)
        with_mask += bool(spans)
        st = span_stats(t, spans, None, vocab)
        real_charge = [w for w in st["charge"] if w not in gold]
        gate += bool(st["digit"] or real_charge)
        charge_words.update(real_charge)
        digit_alt += T.redaction_altered_digits(t, red)
        digit_alt_ind += independent_digit_check(t, red)
        words += st["words"]
        masked_words += len(st["charge"]) + len(st["other"])
        extra = [w for w in st["other"] if w not in gold]
        non_name.update(extra)
        rec_non_name += bool(extra)
        for m in re.finditer(r"[A-Z][A-Z'.-]*", t):
            if m.group(0) in gold:
                gold_n += 1
                gold_missed += not any(a <= m.start() and m.end() <= b for a, b in spans)
    res["dev"] = {
        "records": len(dev), "records_with_a_mask": with_mask,
        "records_with_charge_word_or_digit_masked": gate, "charge_words_masked_tokens": sum(charge_words.values()),
        "digits_altered": digit_alt, "digits_altered_independent": digit_alt_ind,
        "reviewed_name_tokens": gold_n, "reviewed_name_tokens_missed": gold_missed,
        "words": words, "words_masked": masked_words, "words_masked_rate": round(masked_words / words, 4),
        "non_name_words_masked": sum(non_name.values()), "non_name_words_masked_distinct": len(non_name),
        "records_with_non_name_word_masked": rec_non_name,
        "seconds_per_1000_records": round(elapsed / len(dev) * 1000, 2)}
    OUT_PRIVATE.mkdir(parents=True, exist_ok=True)
    (OUT_PRIVATE / f"dev_masked_words_{re.sub(r'[^a-z0-9_.]', '_', engine)}.json").write_text(json.dumps(
        {"non_name_words": non_name.most_common(), "charge_words": charge_words.most_common()}, indent=1))

    # secondary check only (decision P-08: nothing is tuned to the mock): person items annotated in the public mock
    try:
        truth = {x["mock_id"]: x for x in map(json.loads, (ROOT / "data/external/mock_public/ground_truth.jsonl").open())}
        rows = {r.pk: T.normalize(r.text_raw) for r in load_mock()}
        left = total = 0
        for ev in truth.values():
            for p in ev["pii"]:
                sub = p.get("substring") or p.get("text") or ""
                if "name" not in str(p.get("type", "")).lower() and "person" not in str(p.get("type", "")).lower():
                    continue
                for rid in ev["row_ids"]:
                    if sub and sub in rows.get(rid, ""):
                        total += 1
                        left += sub in T.redact(rows[rid])[0]
        mock_reds = [(t, T.redact(t)[0]) for t in rows.values()]
        res["mock_secondary"] = {"person_items": total, "left_in_text": left,
                                 "digits_altered": sum(T.redaction_altered_digits(t, r) for t, r in mock_reds),
                                 "records_with_charge_word_or_digit_masked": sum(
                                     bool((s := span_stats(t, T.person_spans(t), None, vocab))["digit"] or s["charge"])
                                     for t in rows.values())}
    except FileNotFoundError:
        res["mock_secondary"] = None
    return res


def heldout_surnames() -> dict | None:
    """Census 2010 surnames that are NOT in the bundled list (rank beyond the top 30,000): how many would pass the
    allowlist with no context around them. Weighted by the number of people bearing the name. This is the leak of
    the allowlist for names it has never seen, measured on a large public sample instead of a hand-written list."""
    if not CENSUS_CSV.exists():
        return None
    import csv
    first, last, _ = RV._names()
    with CENSUS_CSV.open(newline="") as fh:
        tail = [(r["name"], int(r["count"])) for r in csv.DictReader(fh)
                if r["name"].isalpha() and r["name"] not in first and r["name"] not in last]
    out = {"surnames": len(tail), "people": sum(c for _, c in tail), "pass_rate_by_people": {}}
    for mode in ("off", "charge_vocab", "all"):
        set_engine(f"allowlist/{mode}")
        passed = Counter()
        for name, count in tail:
            kind = RV._kind(name)
            reason = {"C": "is_common_word", "P": "is_protected_word", "X": "two_letters"}.get(kind)
            if kind == "U" and RV.near_spelling(name):
                reason = "near_spelling"
            if reason:
                passed[reason] += count
        out["pass_rate_by_people"][mode] = {"total": round(sum(passed.values()) / out["people"], 4),
                                            **{k: round(v / out["people"], 4) for k, v in sorted(passed.items())}}
    return out


def main() -> None:
    engines = sys.argv[1:] or ["presidio", "names_list", "allowlist", "allowlist/all", "local_ner", "local_ner@0.3",
                               "allowlist+local_ner"]
    dev = dev_texts()
    distinct = [t for t in dict.fromkeys(dev) if t]
    gold = set(REVIEWED.read_text().split())
    frames, frame_stats = collect_frames(distinct)
    dev_tokens = {w.upper() for t in distinct for w in WORD.findall(t)}
    pools, name_info = build_names(dev_tokens)
    hosts = [t for t in distinct if not (set(re.findall(r"[A-Z][A-Z'.-]*", t)) & gold) and WORD.search(t)]
    cases = build_cases(frames, hosts, pools)
    assert not any(w in dev_tokens for p in pools.values() for w in p)
    OUT_PRIVATE.mkdir(parents=True, exist_ok=True)
    (OUT_PRIVATE / "frames.jsonl").write_text("\n".join(json.dumps(f) for f in frames) + "\n")
    (OUT_PRIVATE / "cases.jsonl").write_text("\n".join(json.dumps(c) for c in cases) + "\n")
    vocab = set(T._charge_vocab())
    setup = {"seed": SEED, "dev_records": len(dev), "dev_distinct_texts": len(distinct), "frames": frame_stats,
             "host_texts": len(hosts), "names": name_info, "cases": dict(Counter(c["group"] for c in cases)),
             "cases_by_class": dict(Counter(c["class"] for c in cases)), "charge_vocabulary_words": len(vocab),
             "allowlist_near_spelling_default": DEFAULT_NEAR, "heldout_census_surnames": heldout_surnames()}
    print(json.dumps(setup, indent=1))
    results = []
    for e in engines:
        r = evaluate(e, cases, dev, gold, vocab)
        results.append(r)
        c, d = r["cases"], r["dev"]
        print(f"\n== {e}: miss {c['missed']}/{c['n']} ({c['miss_rate']:.1%}); cases with charge word/digit masked "
              f"{c['cases_with_charge_word_or_digit_masked']}; other host words masked {c['other_host_words_masked_rate']:.1%}; "
              f"digits altered {c['digits_altered']}/{c['digits_altered_independent']}")
        print("   by class:", {k[6:]: f"{v['missed']}/{v['n']}" for k, v in c["miss_by"].items() if k.startswith("class:")})
        print("   by group:", {k[6:]: f"{v['missed']}/{v['n']}" for k, v in c["miss_by"].items()
                               if k.startswith("group:") and "|" not in k})
        print("   dev:", d)
        print("   mock (secondary):", r["mock_secondary"])
    if not sys.argv[1:]:
        OUT_PUBLIC.mkdir(parents=True, exist_ok=True)
        (OUT_PUBLIC / "metrics.json").write_text(json.dumps({"setup": setup, "engines": results}, indent=1) + "\n")


if __name__ == "__main__":
    main()
