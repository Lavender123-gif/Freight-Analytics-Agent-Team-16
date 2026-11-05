"""Steps 0-1: read, collapse export repeats, redact, injection check.

Redaction engine is Presidio (PERSON) on title-cased text plus an email regex. person_tokens.txt is NOT used
here; it is only the gold standard in presidio_eval.py.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd

from config import DEV_PATH, RULES, country
from schemas import Diagnostic, Handling, Location, ObjectType

EVENT_KEY = ["SHIPMENT_GID", "Event Date", "text_norm", "Invoice Amount", "Delta"]
PLACEHOLDER_RE = re.compile(r"\[(?:PERSON|EMAIL)_\d+\]")
EMAIL_RE = re.compile(r"'?[\w.+-]+@[\w-]+(?:\.[\w-]+)+'?")
CONTEXT_RULES = [   # optional, generic English patterns; off by default (rules.yaml redaction.context_rules)
    re.compile(r"\b(?:APPROVED BY|AS PER|EMAILED .{0,40}? TO|NOTIFIED BY|CONFIRMED BY)\s+([A-Z]{2,}(?: [A-Z]{2,})?)\b"),
    re.compile(r"\b([A-Z]{2,} [A-Z]{2,}) (?:FROM|OF) PPG\b"),
]
NOT_NAMES = {"PPG", "THE", "LIST", "CONTRACT", "BOL", "TERMS"}

_ANALYZER = None
_DICT_WORDS: set[str] | None = None


def _dict_case(text: str) -> str:
    """Lowercase words that are ordinary lowercase dictionary words, title-case the rest (candidate proper nouns)."""
    global _DICT_WORDS
    if _DICT_WORDS is None:
        try:
            _DICT_WORDS = {w.strip() for w in open("/usr/share/dict/words") if w.strip().islower()}
        except OSError:
            _DICT_WORDS = set()
    return re.sub(r"[A-Z]+", lambda m: m.group(0).lower() if m.group(0).lower() in _DICT_WORDS else m.group(0).title(), text)


def now() -> datetime:
    return datetime.now(timezone.utc)


def diag(code: str, obj: ObjectType, path: str, evidence: dict, step: str, handling=Handling.RECORD) -> Diagnostic:
    return Diagnostic(code=code, location=Location(object_type=obj, path=path), evidence=evidence, step=step,
                      handling=handling, created_at=now())


def load_rows() -> pd.DataFrame:
    df = pd.read_csv(DEV_PATH, dtype=str)
    df["row"] = range(len(df))
    df["text_norm"] = df["Descritipion"].fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
    for c in ["Invoice Amount", "Shipment Amount", "Delta"]:
        df[c] = df[c].map(lambda x: Decimal(x).quantize(Decimal("0.01")))
    return df


def collapse(df: pd.DataFrame) -> pd.DataFrame:
    """One record per dispute event. Keeps the first row's fields and lists the collapsed rows and PKs."""
    g = df.groupby(EVENT_KEY, sort=False, dropna=False)
    ev = g.first().reset_index()
    ev["source_rows"] = g["row"].apply(list).values
    ev["pks"] = g["PK"].apply(lambda s: sorted(set(s.dropna()))).values
    ev["record_id"] = ["dev.csv#r%d" % rows[0] for rows in ev.source_rows]
    ev["ts"] = pd.to_datetime(ev["Event Date"], format="%Y-%m-%d %H:%M:%S")
    return ev


def _presidio():
    global _ANALYZER
    if _ANALYZER is None:
        from presidio_analyzer import AnalyzerEngine
        _ANALYZER = AnalyzerEngine()
    return _ANALYZER


def person_spans(text: str, engine: str | None = None, title_case: bool | str | None = None,
                 context_rules: bool | None = None) -> list[tuple[int, int]]:
    """title_case: False = raw uppercase, True = str.title(), "dict" = dictionary-based casing."""
    cfg = RULES["redaction"]
    engine = engine or cfg["engine"]
    title_case = cfg["title_case_before_ner"] if title_case is None else title_case
    context_rules = cfg["context_rules"] if context_rules is None else context_rules
    spans: list[tuple[int, int]] = []
    if engine == "presidio":
        probe = _dict_case(text) if title_case == "dict" else text.title() if title_case else text
        for r in _presidio().analyze(text=probe, language="en", entities=cfg["presidio_entities"]):
            if r.score >= cfg["score_threshold"]:
                spans.append((r.start, r.end))
    if context_rules:
        for rx in CONTEXT_RULES:
            for m in rx.finditer(text):
                if not set(m.group(1).split()) & NOT_NAMES:
                    spans.append(m.span(1))
    # drop spans inside emails (handled separately) and merge overlaps
    emails = [m.span() for m in EMAIL_RE.finditer(text)]
    spans = [s for s in spans if not any(a <= s[0] and s[1] <= b for a, b in emails)]
    merged: list[tuple[int, int]] = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


def redact(text: str, **kw) -> tuple[str, int, int]:
    """Return (redacted_text, n_person_placeholders, n_email_placeholders). Same name -> same placeholder."""
    repl: list[tuple[int, int, str]] = []
    names: dict[str, int] = {}
    for a, b in person_spans(text, **kw):
        key = text[a:b]
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


INJ = [re.compile(p) for p in RULES["injection"]["patterns"]]


def injection_hits(text: str) -> list[str]:
    hits = [p.pattern for p in INJ if p.search(text)]
    if len(text) > RULES["injection"]["max_length"]:
        hits.append("max_length")
    if any(ord(c) < 32 or ord(c) > 126 for c in text):
        hits.append("non_printable_or_non_ascii")
    return hits


def gate(ev_row) -> tuple[dict, list[Diagnostic]]:
    """Steps 0-1 for one collapsed event. Returns (partial record dict, diagnostics)."""
    t = ev_row.text_norm
    d: list[Diagnostic] = []
    if len(ev_row.source_rows) > 1:
        d.append(diag("REC.INPUT.EXPORT_DUPLICATE", ObjectType.RECORD, "source",
                      {"n_rows": len(ev_row.source_rows), "source_rows": ev_row.source_rows, "n_pks": len(ev_row.pks)}, "1"))
    red, n_p, n_e = redact(t)
    if n_p or n_e:
        d.append(diag("REC.TEXT.PII_REDACTED", ObjectType.RECORD, "text", {"n_person": n_p, "n_email": n_e}, "1"))
    # emails may contain digits; compare digits outside emails only
    if re.sub(r"\D", "", EMAIL_RE.sub("", t)) != re.sub(r"\D", "", PLACEHOLDER_RE.sub("", red)):
        d.append(diag("REC.TEXT.REDACTION_ALTERED_DIGITS", ObjectType.RECORD, "text", {}, "1"))
    if t == "":
        d.append(diag("REC.TEXT.EMPTY", ObjectType.RECORD, "text", {"text_length": 0}, "1"))
    hits = injection_hits(t)
    if hits:
        d.append(diag("REC.TEXT.INJECTION_SUSPECT", ObjectType.RECORD, "text", {"patterns_hit": hits, "length": len(t)}, "1"))
    delta = ev_row.Delta
    if delta == 0:
        d.append(diag("REC.FIELD.DELTA_ZERO", ObjectType.RECORD, "source/delta", {"delta": str(delta)}, "1"))
    elif delta < 0:
        d.append(diag("REC.FIELD.DELTA_NEGATIVE", ObjectType.RECORD, "source/delta", {"delta": str(delta)}, "1"))
    oc, dc = country(ev_row["Source State"]), country(ev_row["Destination State"])
    if oc != dc:
        d.append(diag("REC.FIELD.CROSS_BORDER", ObjectType.RECORD, "source", {"origin_country": oc, "destination_country": dc}, "1"))
    rec = {
        "source": dict(
            record_id=ev_row.record_id, shipment_id=ev_row.SHIPMENT_GID, invoice_pks=ev_row.pks,
            source_rows=ev_row.source_rows, event_date=ev_row.ts.to_pydatetime(),
            invoice_amount=ev_row["Invoice Amount"], shipment_amount=ev_row["Shipment Amount"], delta=delta,
            origin_state=ev_row["Source State"], destination_state=ev_row["Destination State"],
            origin_country=oc, destination_country=dc, reason_code=ev_row["Reason Code"], carrier=ev_row.Carrier),
        "text": dict(original_sha1=hashlib.sha1(t.encode()).hexdigest(), redacted=red,
                     n_person_placeholders=n_p, n_email_placeholders=n_e, injection_hits=hits),
    }
    return rec, d
