"""Redaction miss rate and false-redaction rate on the dev split, with person_tokens.txt as the gold standard.

Unit: word-token occurrences, counted over dispute events (export repeats collapsed) and over distinct texts.
A gold token counts as caught if any redaction span covers it. A redacted word that is not a gold token is a
false redaction. Emails are handled by regex in every configuration and excluded from both counts.
Prints aggregates and the false-redacted words (business words, not personal data). Names are never printed.

Run: scratch/prototype/run.sh presidio_eval.py
"""

import re
from collections import Counter

from config import ROOT
from gate import EMAIL_RE, collapse, load_rows, person_spans

GOLD = {t.strip() for t in (ROOT / "data" / "interim" / "person_tokens.txt").read_text().split() if t.strip()}
CONFIGS = {
    "A presidio, raw uppercase": dict(engine="presidio", title_case=False, context_rules=False),
    "B presidio, title-cased": dict(engine="presidio", title_case=True, context_rules=False),
    "B2 presidio, dictionary-cased": dict(engine="presidio", title_case="dict", context_rules=False),
    "C presidio title-cased + context rules": dict(engine="presidio", title_case=True, context_rules=True),
    "C2 presidio dictionary-cased + context rules": dict(engine="presidio", title_case="dict", context_rules=True),
    "D context rules only (no NER)": dict(engine="email_only", title_case=False, context_rules=True),
}

ev = collapse(load_rows())
texts = {"events": list(ev.text_norm), "distinct texts": list(dict.fromkeys(ev.text_norm))}

for unit, ts in texts.items():
    print(f"\n=== unit: {unit} ({len(ts)}) ===")
    for name, kw in CONFIGS.items():
        gold_n = caught = false_n = rec_with = rec_leak = 0
        false_words: Counter = Counter()
        for t in ts:
            spans = person_spans(t, **kw)
            no_email = EMAIL_RE.sub(lambda m: " " * len(m.group(0)), t)
            leak = False
            has_gold = False
            for m in re.finditer(r"[A-Z][A-Z'.-]*", no_email):
                covered = any(a <= m.start() and m.end() <= b for a, b in spans)
                if m.group(0) in GOLD:
                    has_gold = True
                    gold_n += 1
                    caught += covered
                    leak |= not covered
                elif covered:
                    false_n += 1
                    false_words[m.group(0)] += 1
            rec_with += has_gold
            rec_leak += leak
        print(f"{name:42s} gold tokens {gold_n:4d}  missed {gold_n - caught:4d} ({(gold_n - caught) / max(gold_n, 1):.1%})"
              f"  | records with a name {rec_with:3d}, with a leak {rec_leak:3d} ({rec_leak / max(rec_with, 1):.1%})"
              f"  | false-redacted words {false_n:4d} {dict(false_words.most_common(8))}")
