"""Step 1: normalise, redact and check the carrier text before anything else sees it.

Redaction is the existing prototype step (scratch/prototype/gate.py, B01), moved here unchanged in behaviour:
Presidio PERSON on dictionary-cased text, generic English context rules, and an email regex. Every text sent to
the model goes through `redact` first (CLAUDE.md; task 09 section 1.10). There is no rejection branch here: every
record continues to the model whatever this step finds (decision 2.1).

Other name detectors (task 10 section 4) live in redaction_variants.py and are selected by rules.yaml
`redaction.engine` or the environment variable FL_REDACTION_ENGINE; the default `presidio` path is unchanged.
"""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata

from freight_lineitems.config import RULES

PLACEHOLDER_RE = re.compile(r"\[(?:PERSON|EMAIL|PHONE)_\d+\]")
EMAIL_RE = re.compile(r"'?[\w.+-]+@[\w-]+(?:\.[\w-]+)+'?")
# an email spelled out to dodge filters: 'name dot surname at domain dot com' (found by the public mock)
_AT = r"(?:\s+AT\s+|\s*[\[(]\s*AT\s*[\])]\s*)"
_DOT = r"(?:\s+DOT\s+|\s*[\[(]\s*DOT\s*[\])]\s*|\.)"
SPELLED_EMAIL_RE = re.compile(rf"\b[\w+-]+(?:{_DOT}[\w+-]+)*{_AT}[\w-]+(?:{_DOT}[\w-]+)+\b", re.I)
# North American phone numbers (found by the public mock); redacted so they are never read as amounts
PHONE_RE = re.compile(r"(?<![\d$.])(?:\+?1[ .-])?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?![\d.])")
CONTEXT_RULES = [   # generic English patterns, not carrier phrasing (rules.yaml redaction.context_rules)
    re.compile(r"\b(?:APPROVED BY|AS PER|EMAILED .{0,40}? TO|NOTIFIED BY|CONFIRMED BY)\s+([A-Z]{2,}(?: [A-Z]{2,})?)\b"),
    re.compile(r"\b([A-Z]{2,} [A-Z]{2,}) (?:FROM|OF) PPG\b"),
]
NOT_NAMES = {"PPG", "THE", "LIST", "CONTRACT", "BOL", "TERMS"}

_ANALYZER = None
_DICT_WORDS: set[str] | None = None


def normalize(text: str | None) -> str:
    """Collapse whitespace; None/NaN becomes ''."""
    if text is None or (isinstance(text, float) and text != text):
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _dict_case(text: str) -> str:
    """Lowercase ordinary dictionary words, title-case the rest (candidate proper nouns) before NER."""
    global _DICT_WORDS
    if _DICT_WORDS is None:
        try:
            _DICT_WORDS = {w.strip() for w in open("/usr/share/dict/words") if w.strip().islower()}
        except OSError:
            _DICT_WORDS = set()
    return re.sub(r"[A-Z]+", lambda m: m.group(0).lower() if m.group(0).lower() in _DICT_WORDS else m.group(0).title(), text)


_VOCAB: set[str] | None = None


def _charge_vocab() -> set[str]:
    global _VOCAB
    if _VOCAB is None:
        from freight_lineitems.config import CODES
        words = " ".join(" ".join([c["definition"], *c.get("phrasings", [])]) for c in CODES.values())
        _VOCAB = {w for w in re.findall(r"[A-Z]{3,}", words.upper())}
    return _VOCAB


def _presidio():
    global _ANALYZER
    if _ANALYZER is None:
        from presidio_analyzer import AnalyzerEngine
        _ANALYZER = AnalyzerEngine()
    return _ANALYZER


def redaction_engine() -> str:
    """The name-redaction method in force: rules.yaml `redaction.engine`, or FL_REDACTION_ENGINE for one run."""
    return os.environ.get("FL_REDACTION_ENGINE") or RULES["redaction"]["engine"]


def person_spans(text: str) -> list[tuple[int, int]]:
    cfg = RULES["redaction"]
    spans: list[tuple[int, int]] = []
    engine = redaction_engine()   # the env var selects a variant for one run
    if engine not in ("presidio", "email_only"):
        from freight_lineitems import redaction_variants
        spans.extend(redaction_variants.spans(engine, text) if text else [])
    if engine == "presidio" and text:
        tc = cfg["title_case_before_ner"]
        probe = _dict_case(text) if tc == "dict" else text.title() if tc else text
        for r in _presidio().analyze(text=probe, language="en", entities=cfg["presidio_entities"]):
            if r.score >= cfg["score_threshold"]:
                spans.append((r.start, r.end))
    if cfg["context_rules"]:
        for rx in CONTEXT_RULES:
            for m in rx.finditer(text):
                if not set(m.group(1).split()) & NOT_NAMES:
                    spans.append(m.span(1))
    if engine not in ("presidio", "email_only"):
        spans = redaction_variants.clip(text, spans)       # variants never mask digits or charge-vocabulary words
    emails = [m.span() for rx in (EMAIL_RE, SPELLED_EMAIL_RE, PHONE_RE) for m in rx.finditer(text)]
    # a span made only of charge-vocabulary words (taxonomy phrasings and definitions) is not a name ('LIFTGATE')
    spans = [s for s in spans if not set(re.findall(r"[A-Z]+", text[s[0]:s[1]].upper())) <= _charge_vocab()]
    spans = [s for s in spans if not any(a <= s[0] and s[1] <= b for a, b in emails)]
    merged: list[tuple[int, int]] = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


def redact(text: str) -> tuple[str, int, int]:
    """Return (redacted_text, n_person_placeholders, n_email_placeholders). Same name -> same placeholder."""
    repl: list[tuple[int, int, str]] = []
    names: dict[str, int] = {}
    for a, b in person_spans(text):
        key = text[a:b]
        names.setdefault(key, len(names) + 1)
        repl.append((a, b, f"[PERSON_{names[key]}]"))
    emails: dict[str, int] = {}
    taken = [(a, b) for a, b, _ in repl]
    for rx in (EMAIL_RE, SPELLED_EMAIL_RE):
        for m in rx.finditer(text):
            if any(not (m.end() <= a or b <= m.start()) for a, b in taken):
                continue
            emails.setdefault(m.group(0), len(emails) + 1)
            repl.append((m.start(), m.end(), f"[EMAIL_{emails[m.group(0)]}]"))
            taken.append(m.span())
    phones: dict[str, int] = {}
    for m in PHONE_RE.finditer(text):
        if any(not (m.end() <= a or b <= m.start()) for a, b in taken):
            continue
        phones.setdefault(m.group(0), len(phones) + 1)
        repl.append((m.start(), m.end(), f"[PHONE_{phones[m.group(0)]}]"))
        taken.append(m.span())
    out = text
    for a, b, r in sorted(repl, reverse=True):
        out = out[:a] + r + out[b:]
    return out, len(names), len(emails)


def redaction_altered_digits(original: str, redacted: str) -> bool:
    """True if redaction removed or changed digits outside emails (a name span swallowed a number)."""
    # placeholders already present in the source text are ignored on both sides (boundary case BC049)
    stripped = PHONE_RE.sub("", SPELLED_EMAIL_RE.sub("", EMAIL_RE.sub("", original)))
    return (re.sub(r"\D", "", PLACEHOLDER_RE.sub("", stripped))
            != re.sub(r"\D", "", PLACEHOLDER_RE.sub("", redacted)))


_INJ = [re.compile(p) for p in RULES["injection"]["patterns"]]


_CONFUSABLES = str.maketrans({"\u0406": "I", "\u0456": "I", "\u0410": "A", "\u0430": "A", "\u0415": "E", "\u0435": "E",
                              "\u041e": "O", "\u043e": "O", "\u0421": "C", "\u0441": "C", "\u0420": "P", "\u0440": "P",
                              "\u0391": "A", "\u0395": "E", "\u0399": "I", "\u039f": "O", "\u0405": "S", "\u0455": "S"})


def _probe(text: str) -> str:
    """Matching copy only (never sent anywhere): NFKC, common look-alike letters, letters split by single spaces
    ('i G n O r E') joined, digits used as letters inside words ('RU1ES') mapped back."""
    import unicodedata
    t = unicodedata.normalize("NFKC", text).translate(_CONFUSABLES).upper()
    t = re.sub(r"\b(?:[A-Z] ){2,}[A-Z]\b", lambda m: m.group(0).replace(" ", ""), t)
    return re.sub(r"(?<=[A-Z])[10](?=[A-Z])", lambda m: {"1": "L", "0": "O"}[m.group(0)], t)


_LEET = str.maketrans({"0": "O", "1": "I", "3": "E", "4": "A", "5": "S", "7": "T", "8": "B", "@": "A", "$": "S", "|": "I", "!": "I"})
_CONFUSABLE = str.maketrans({"А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
                             "Х": "X", "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N",
                             "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "І": "I", "Ј": "J", "Ѕ": "S"})


def _edits(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def fuzzy_injection_hits(text: str) -> list[str]:
    """Task 17 fix 4: injection wording in disguise, on the original text (before redaction). Undo look-alike digits
    and confusable letters, rejoin words split by spaces, then match a verb and an object of rules.yaml
    `injection_fuzzy` by edit distance. Returns 'fuzzy:VERB>OBJECT' or 'fuzzy:PHRASE' for each hit."""
    cfg = RULES.get("injection_fuzzy")
    if not cfg or not text:
        return []
    t = unicodedata.normalize("NFKC", text).upper().translate(_CONFUSABLE)
    raw = [w.translate(_LEET) for w in re.findall(r"[A-Z0-9@$|!]+", t)]
    raw = [re.sub(r"[^A-Z]", "", w) for w in raw]
    raw = [w for w in raw if w]

    def near(w: str, vocab) -> str | None:
        if len(w) < cfg["min_token_len"]:
            return next((v for v in vocab if w == v), None)
        for v in vocab:
            lim = cfg["max_edits_short"] if len(v) <= 5 else cfg["max_edits_long"]
            if abs(len(w) - len(v)) <= lim and _edits(w, v) <= lim:
                return v
        return None

    verbs, objects = list(cfg["verbs"]), list(cfg["objects"])
    tokens: list[tuple[int, str]] = []          # (position, word) including joins of 2 and 3 neighbours
    for i in range(len(raw)):
        for k in (1, 2, 3):
            if i + k <= len(raw):
                tokens.append((i, "".join(raw[i:i + k])))
    hits = []
    for i, w in tokens:
        v = near(w, verbs)
        if not v:
            continue
        for j, o in tokens:
            if i < j <= i + cfg["window_tokens"]:
                ob = near(o, objects)
                if ob:
                    hits.append(f"fuzzy:{v}>{ob}")
                    break
    joined = " ".join(raw)
    for ph in cfg.get("phrases", {}):
        if re.search(rf"(?<![A-Z]){ph}(?![A-Z])", joined):
            hits.append(f"fuzzy:{ph}")
    return sorted(set(hits))


def injection_hits(text: str) -> list[str]:
    probe = _probe(text) if RULES["injection"].get("normalize_before_match") else text
    hits = [p.pattern for p in _INJ if p.search(text) or p.search(probe)]
    hits += fuzzy_injection_hits(text)                 # task 17 fix 4
    if len(text) > RULES["injection"]["max_length"]:
        hits.append("max_length")
    if any(ord(c) < 32 for c in text):
        hits.append("non_printable")      # non-ASCII letters are a separate info code (audit L7)
    return hits
