"""Stratified samples from the dev split (task 09 stage 1 and stage 3).

Strata = carrier x writing style. The style classes use generic English cues and are used only to draw samples and
to report results; the pipeline never reads them (no carrier-specific or style-specific logic in the pipeline).
"""

from __future__ import annotations

import random
import re
from collections import defaultdict

from freight_lineitems.records import InputRecord

STYLE_ORDER = ["empty_or_numbers", "tax", "payment_history", "arithmetic", "multi_number", "simple"]


def style(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip().upper()
    if not re.search(r"[A-Z]", t):
        return "empty_or_numbers"
    if re.search(r"\b(GST|HST|PST|QST|TAX)\b", t):
        return "tax"
    if re.search(r"\b(PAID|BILLED|ADJUST\w*|SHORT|OWE\w*|BALANCE)\b", t):
        return "payment_history"
    if re.search(r"@|\bX\b|\bPER\b|\bEACH\b|\bDAYS?\b|=|\+", t):
        return "arithmetic"
    if len(re.findall(r"\d+(?:\.\d+)?", t)) >= 2:
        return "multi_number"
    return "simple"


def stratified(records: list[InputRecord], n: int, seed: int, exclude_ids: set[str] = frozenset(),
               exclude_shipments: set[str] = frozenset()) -> list[InputRecord]:
    """Round-robin over strata (carrier, style), smallest strata first so rare carriers and styles are covered,
    then fill by stratum size. Deterministic for a seed."""
    rng = random.Random(seed)
    pool = [r for r in records if r.record_id not in exclude_ids and r.shipment_key not in exclude_shipments]
    strata: dict[tuple[str, str], list[InputRecord]] = defaultdict(list)
    for r in pool:
        strata[(r.carrier, style(r.text_raw))].append(r)
    for v in strata.values():
        rng.shuffle(v)
    # order: carriers by size descending, then within carrier styles in fixed order; rotate across carriers
    by_carrier: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for k in strata:
        by_carrier[k[0]].append(k)
    carriers = sorted(by_carrier, key=lambda c: -sum(len(strata[k]) for k in by_carrier[c]))
    for c in carriers:   # styles within a carrier: largest stratum first, so common writing is not crowded out
        by_carrier[c].sort(key=lambda k: (-len(strata[k]), STYLE_ORDER.index(k[1])))
    out: list[InputRecord] = []
    chosen: set[str] = set()
    rnd = 0
    while len(out) < n and any(strata.values()):
        for c in carriers:
            keys = [k for k in by_carrier[c] if strata[k]]
            if not keys:
                continue
            k = keys[rnd % len(keys)]
            r = strata[k].pop()
            if r.record_id not in chosen:
                out.append(r)
                chosen.add(r.record_id)
            if len(out) >= n:
                break
        rnd += 1
    return out
