"""Our internal charge codes -> the client's Addenda B names and candidate EDI codes (task 14 / T14-05).

Deterministic lookup in config/charge_map.yaml (generated from the T13 mapping). The internal code stays the identity
for every comparison (the roll-up compares internal codes, never client names); this module only adds display
columns: the client name, the candidate EDI codes, and the reference names when several client entries fit.
Coverage classes (T13 section 3.2): 1 exact or approximate, 2 one-to-many, 3 sub-item, 4 extension or not placed,
5 OTHER. An amount with several codes takes the weakest class of its codes.
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from freight_lineitems.config import CONFIG_DIR

CLASS_OF_RELATION = {"EXACT": 1, "APPROX": 1, "ONE_TO_MANY": 2, "CHILD": 3, "EXTENSION": 4, "TOP_LEVEL": 4}


@lru_cache(maxsize=1)
def charge_map() -> dict:
    return yaml.safe_load((CONFIG_DIR / "charge_map.yaml").read_text())


def entry(code: str) -> dict:
    """The mapping entry of one internal code. Unknown codes raise KeyError (a code missing from the map is a bug)."""
    return charge_map()["codes"][code]


def coverage_class(codes: list[str] | tuple[str, ...]) -> int | None:
    """T13 coverage class of one amount; None when the text names no charge."""
    if not codes:
        return None
    return max(5 if c == "OTHER" else CLASS_OF_RELATION[entry(c)["relation"]] for c in codes)


def describe(codes: list[str] | tuple[str, ...]) -> dict:
    """Display columns for one amount: client name, EDI candidates (all, none chosen), reference names."""
    if not codes:
        return {"client_name": "(no charge named)", "edi_candidates": "", "reference_names": "", "coverage_class": None}
    es = [entry(c) for c in codes]
    ref = [n for e in es if e["relation"] == "ONE_TO_MANY" for n in e["client_names"]]
    return {"client_name": " + ".join(e["client_name"] for e in es),
            "edi_candidates": " ".join(dict.fromkeys(x for e in es for x in e["edi_candidates"])),
            "reference_names": " | ".join(dict.fromkeys(ref)),
            "coverage_class": coverage_class(codes)}


def annotate(shipment: dict) -> dict:
    """Add the display columns to every line of a roll-up result (in place) and return it."""
    for ln in shipment["lines"]:
        ln |= describe(ln["codes"])
    return shipment
