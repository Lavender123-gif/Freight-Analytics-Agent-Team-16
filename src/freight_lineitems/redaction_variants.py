"""Alternative person-name detectors for `textprep.person_spans` (task 10 section 4).

Selected by `rules.yaml` `redaction.engine` or the environment variable `FL_REDACTION_ENGINE`:

- `names_list`  public name lists (US Census first names and surnames) plus generic English context rules.
                Names that are also ordinary words (BILL, MARK, PRICE) are masked only in a name context.
- `allowlist`   whitelist inversion: everything `names_list` masks, plus every alphabetic word that is not a
                number, a charge-vocabulary word, a common English word or a near-spelling of one.
- `local_ner`   GLiNER (zero-shot span model, label 'person') run locally with onnxruntime on the text as it is;
                in the comparison it read all-uppercase names far better than uncased BERT NER models.
                Nothing leaves the machine.
- `a+b`         the union of two of the engines above, e.g. `allowlist+local_ner`.

Every function returns character spans `[start, end)` into the text it was given. Spans only ever cover
alphabetic words that do not touch a digit, so no detector here can remove or change a digit. Emails, phone
numbers and existing placeholders are left to `textprep.redact`. Nothing here depends on the carrier.
The word lists and the model are loaded on first use (heavy imports are lazy). Not thread-safe by design:
`pipeline.prepare` is called sequentially.
"""

from __future__ import annotations

import re
from functools import lru_cache

from freight_lineitems.config import CANADIAN, ROOT, RULES, US_STATES

ENGINES = ("names_list", "allowlist", "local_ner")

WORD_RE = re.compile(r"[A-Za-z]+")
CALENDAR = set("JANUARY FEBRUARY MARCH APRIL MAY JUNE JULY AUGUST SEPTEMBER OCTOBER NOVEMBER DECEMBER JAN FEB MAR APR JUN "
               "JUL AUG SEP SEPT OCT NOV DEC MONDAY TUESDAY WEDNESDAY THURSDAY FRIDAY SATURDAY SUNDAY MON TUE TUES WED "
               "THU THUR THURS FRI SAT SUN".split())
MIN_LEN = 3            # one- and two-letter tokens (initials, state codes, AM/PM) are never masked
MIN_UNKNOWN = 4        # a word that is in no list counts as a possible name from this length (names_list only)

# Generic English cues after which a person is often named.
_CUE = (r"(?:APPROVED|AUTHORI[ZS]ED|CONFIRMED|NOTIFIED|REQUESTED|SIGNED|RECEIVED|ADVISED|INSTRUCTED) BY|"
               r"(?:CONFIRMED|SPOKE|SPOKEN|TALKED|SPEAKING|CHECKED|VERIFIED) (?:WITH|TO)|"
               r"E-?MAIL(?:ED)?(?: (?:FROM|TO))?|E-?MAILED .{0,40}? TO|CALLED|CONTACT(?:ED)?|ATTN|ATTENTION|"
               r"MR|MRS|MS|C/O|(?:AS )?PER")
CUE_RE = re.compile(rf"\b(?:{_CUE})\b[ .:\-]{{0,3}}(?=[A-Z])")
AFTER_RE = re.compile(r"[ ]+(?:(?:FROM|OF|AT|WITH) PPG\b|"
                      r"(?:APPROVED|CONFIRMED|ADVISED|SAID|STATED|REQUESTED|AUTHORI[ZS]ED|AGREED|REPLIED|RESPONDED)\b)")
NOT_AFTER_AMBIGUOUS = {"OF", "TO", "CALL", "BE", "NOT"}   # BILL OF LADING, BILL TO, WILL CALL, MAY BE


@lru_cache(maxsize=1)
def _names() -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """(first names, surnames, ambiguous names) from the file named in rules.yaml."""
    first, last, amb = set(), set(), set()
    for line in (ROOT / RULES["redaction"]["names_file"]).read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        name, role, flag = line.split("\t")
        if "F" in role:
            first.add(name)
        if "L" in role:
            last.add(name)
        if flag == "A":
            amb.add(name)
    return frozenset(first), frozenset(last), frozenset(amb)


@lru_cache(maxsize=1)
def _common() -> frozenset[str]:
    text = (ROOT / RULES["redaction"]["common_words_file"]).read_text()
    return frozenset(w for w in text.splitlines() if w and not w.startswith("#"))


@lru_cache(maxsize=1)
def _protected() -> frozenset[str]:
    """Words that are never a name here: the charge vocabulary, unit words, calendar words, state codes."""
    from freight_lineitems import textprep
    units = {u.upper() for u in RULES["number_features"]["unit_words"]}
    extra = {w.upper() for w in RULES["redaction"].get("allow_words", [])}
    return frozenset(textprep._charge_vocab() | textprep.NOT_NAMES | units | CALENDAR | CANADIAN | US_STATES | extra)


def _kind(word: str) -> str:
    """P protected, M calendar word that is also a first name (APRIL, MAY), S name-only word, A name that is also
    an ordinary word, C common word, U in no list, X one or two letters."""
    first, last, amb = _names()
    if word in CALENDAR and word in first and len(word) >= MIN_LEN:
        return "M"
    if word in _protected():
        return "P"
    if len(word) < MIN_LEN:
        return "X"
    if word in amb:
        return "A"
    if word in first or word in last:
        return "S"
    return "C" if word in _common() else "U"


def _tokens(text: str) -> list[tuple[int, int, str, str]]:
    """Standalone alphabetic words as (start, end, WORD, kind). Words that touch a digit (IDs such as PRO123), and
    words inside an email, a phone number or an existing placeholder are left out, so they can never be masked."""
    from freight_lineitems import textprep
    blocked = [m.span() for rx in (textprep.EMAIL_RE, textprep.SPELLED_EMAIL_RE, textprep.PHONE_RE, textprep.PLACEHOLDER_RE)
               for m in rx.finditer(text)]
    out = []
    for m in WORD_RE.finditer(text):
        a, b = m.span()
        if (a and text[a - 1].isdigit()) or (b < len(text) and text[b].isdigit()):
            continue
        if any(a < y and x < b for x, y in blocked):
            continue
        w = m.group(0).upper()
        out.append((a, b, w, _kind(w)))
    return out


def _joined(text: str, left: tuple, right: tuple) -> bool:
    """Two words belong to one name when only a space, a hyphen or an apostrophe is between them."""
    return text[left[1]:right[0]] in (" ", "-", "'")


def _merge(text: str, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping spans and spans separated by one space/hyphen/apostrophe ('FIRST LAST' is one person)."""
    merged: list[tuple[int, int]] = []
    for a, b in sorted(set(spans)):
        if merged and (a <= merged[-1][1] or text[merged[-1][1]:a] in (" ", "-", "'")):
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


def names_list_spans(text: str) -> list[tuple[int, int]]:
    """Name-list hits plus generic context rules."""
    toks = _tokens(text)
    if not toks:
        return []
    first, last, _ = _names()
    upper = text.upper()
    masked: set[int] = {i for i, t in enumerate(toks) if t[3] == "S"}

    def unknown(t) -> bool:
        return t[3] == "U" and len(t[2]) >= MIN_UNKNOWN

    # a name-only word carries its neighbour: first name + surname that is a word or in no list, and the reverse
    for i in sorted(masked):
        w = toks[i][2]
        if i + 1 < len(toks) and _joined(text, toks[i], toks[i + 1]) and w in first:
            nxt = toks[i + 1]
            if unknown(nxt) or (nxt[3] == "A" and nxt[2] in last):
                masked.add(i + 1)
        if i and _joined(text, toks[i - 1], toks[i]) and w in last:
            prv = toks[i - 1]
            if unknown(prv) or prv[3] == "M" or (prv[3] == "A" and prv[2] in first):
                masked.add(i - 1)

    by_start = {t[0]: i for i, t in enumerate(toks)}
    by_end = {t[1]: i for i, t in enumerate(toks)}

    def follows_ok(i: int) -> bool:
        """An ambiguous word is not a name when an ordinary continuation follows (BILL OF LADING, WILL CALL)."""
        if i + 1 >= len(toks) or not _joined(text, toks[i], toks[i + 1]):
            return True
        nxt = toks[i + 1][2]
        if nxt == "OF":                                  # 'MARK OF PPG' is a person, 'BILL OF LADING' is not
            return i + 2 < len(toks) and toks[i + 2][2] == "PPG"
        return nxt not in NOT_AFTER_AMBIGUOUS

    # cue + up to two words
    for m in CUE_RE.finditer(upper):
        i = by_start.get(m.end())
        if i is None:
            continue
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) and _joined(text, t, toks[i + 1]) else None
        if t[3] == "M":
            # APRIL / MAY after a cue is a person only when a surname-like word follows (PER MAY INVOICE is not)
            ok = nxt is not None and (nxt[3] == "S" or unknown(nxt))
        elif t[3] == "A":
            # an ambiguous word is a name here if it is a first name (PER BILL) or a name-only word follows
            ok = follows_ok(i) and (t[2] in first or (nxt is not None and nxt[3] == "S"))
        else:
            ok = t[3] == "S" or unknown(t)
        if not ok:
            continue
        masked.add(i)
        if nxt is not None and (nxt[3] == "S" or unknown(nxt) or (nxt[3] == "A" and nxt[2] in last and follows_ok(i + 1))):
            masked.add(i + 1)

    # up to two words + 'FROM PPG' / a reporting verb
    for m in AFTER_RE.finditer(upper):
        i = by_end.get(m.start())
        if i is None:
            continue
        t = toks[i]
        prv = toks[i - 1] if i and _joined(text, toks[i - 1], t) else None
        prv_first = prv is not None and (prv[3] == "M" or (prv[3] in "SA" and prv[2] in first))
        if t[3] == "S" or unknown(t) or (t[3] == "A" and (t[2] in first or prv_first or "PPG" in m.group(0))):
            masked.add(i)
            if prv is not None and (prv[3] == "S" or unknown(prv) or prv_first):
                masked.add(i - 1)
    return _merge(text, [toks[i][:2] for i in masked])


@lru_cache(maxsize=1)
def _near_targets() -> frozenset[str]:
    """Words a misspelling may be close to: the charge vocabulary always, common words if configured."""
    from freight_lineitems import textprep
    cfg = RULES["redaction"]
    mode = cfg["allowlist_near_spelling"]            # all | charge_vocab | off
    words = set(_protected()) if mode in ("all", "charge_vocab") else set()
    if mode == "all":
        words |= _common()
    return frozenset(w for w in words if len(w) >= cfg["allowlist_near_min_len"] - 1)


_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def near_spelling(word: str) -> bool:
    """True if `word` is one edit (insert, delete, replace, swap of neighbours) away from an allowed word.
    TAILAGTE ~ TAILGATE. Short words are not considered: one edit turns too many names into words."""
    if len(word) < RULES["redaction"]["allowlist_near_min_len"]:
        return False
    targets = _near_targets()
    if not targets:
        return False
    for i in range(len(word) + 1):
        head, tail = word[:i], word[i:]
        if tail:
            if head + tail[1:] in targets:
                return True
            if len(tail) > 1 and head + tail[1] + tail[0] + tail[2:] in targets:
                return True
        for c in _ALPHA:
            if head + c + tail in targets or (tail and head + c + tail[1:] in targets):
                return True
    return False


def allowlist_spans(text: str) -> list[tuple[int, int]]:
    """Whitelist inversion: mask every word that is not known to be harmless."""
    spans = names_list_spans(text)
    for a, b, w, kind in _tokens(text):
        if kind == "U" and not near_spelling(w):
            spans.append((a, b))
    return _merge(text, spans)


_NER = None
_NER_FILES = ("tokenizer.json", "gliner_config.json")
_NER_WORD_RE = re.compile(r"\w+(?:[-_]\w+)*|\S")       # GLiNER's own word splitter ('whitespace' type)


def local_ner_available() -> bool:
    """True if the model files are already in the local Hugging Face cache (no download is attempted)."""
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    cfg = RULES["redaction"]
    return all(isinstance(try_to_load_from_cache(cfg["local_ner_model"], f), str) for f in (cfg["local_ner_file"], *_NER_FILES))


def _ner():
    """Load the GLiNER ONNX export once. Files come from the local Hugging Face cache (downloaded on first use)."""
    global _NER
    if _NER is None:
        import json

        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        cfg = RULES["redaction"]
        paths = {f: hf_hub_download(cfg["local_ner_model"], f) for f in (cfg["local_ner_file"], *_NER_FILES)}
        tok = Tokenizer.from_file(paths["tokenizer.json"])
        tok.no_truncation()
        tok.no_padding()
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        sess = ort.InferenceSession(paths[cfg["local_ner_file"]], sess_options=opts, providers=["CPUExecutionProvider"])
        _NER = (tok, sess, json.loads(open(paths["gliner_config.json"]).read()))
    return _NER


def local_ner_spans(text: str) -> list[tuple[int, int]]:
    """'person' spans from GLiNER (a zero-shot span model; it reads all-uppercase text as it is), run locally with
    onnxruntime. The input layout follows the gliner package: prompt '<<ENT>> person <<SEP>>' + the words, a mask
    naming the first sub-token of each word, and every candidate span of up to `max_width` words."""
    words = list(_NER_WORD_RE.finditer(text))
    if not words:
        return []
    import numpy as np
    tok, sess, gcfg = _ner()
    cfg = RULES["redaction"]
    thr, width = cfg["local_ner_threshold"], gcfg["max_width"]
    prompt = [gcfg["ent_token"], cfg["local_ner_label"], gcfg["sep_token"]]
    hits: list[tuple[int, int]] = []
    window = 300                                   # the model was trained on at most 384 words
    for start in range(0, len(words), window):
        chunk = words[start:start + window]
        enc = tok.encode(prompt + [m.group(0) for m in chunk], is_pretokenized=True)
        mask, prev = [], None
        for wid in enc.word_ids:
            mask.append(wid - len(prompt) + 1 if wid is not None and wid != prev and wid >= len(prompt) else 0)
            prev = wid
        n = len(chunk)
        span_idx = np.array([[(i, i + j) for i in range(n) for j in range(width)]], dtype=np.int64)
        feed = {"input_ids": np.array([enc.ids], dtype=np.int64), "attention_mask": np.ones((1, len(enc.ids)), dtype=np.int64),
                "words_mask": np.array([mask], dtype=np.int64), "text_lengths": np.array([[n]], dtype=np.int64),
                "span_idx": span_idx, "span_mask": span_idx[:, :, 1] < n}
        logits = sess.run(["logits"], feed)[0][0, :, :, 0]            # [word, width]
        for i, j in zip(*np.where(logits > np.log(thr / (1 - thr)))):  # sigmoid(logit) > thr
            if i + j < n:
                hits.append((chunk[i].start(), chunk[i + j].end()))
    if not hits:
        return []
    spans = [(a, b) for a, b, _, kind in _tokens(text) if kind not in "PX" and any(x < b and a < y for x, y in hits)]
    return _merge(text, spans)


def clip(text: str, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Reduce spans to the standalone words they cover, minus protected words. After this no span holds a digit,
    a charge-vocabulary word, or part of an email, phone number or placeholder, whatever rule produced it."""
    if not spans:
        return []
    return _merge(text, [(a, b) for a, b, _, kind in _tokens(text) if kind != "P" and any(x < b and a < y for x, y in spans)])


def spans(engine: str, text: str) -> list[tuple[int, int]]:
    """Person spans of one engine, or the union of several joined with '+' ('allowlist+local_ner').
    Raises ValueError for an unknown engine (a typo must not switch redaction off)."""
    if "+" in engine:
        return _merge(text, [s for part in engine.split("+") for s in spans(part, text)])
    if engine == "names_list":
        return names_list_spans(text)
    if engine == "allowlist":
        return allowlist_spans(text)
    if engine == "local_ner":
        return local_ner_spans(text)
    raise ValueError(f"unknown redaction engine {engine!r}")
