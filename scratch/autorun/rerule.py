"""Recompute a stored record's recommendation under the rules.yaml in the working tree (no model call).

Used so that runs made under older rules can be compared with newer ones on the same footing (task 10).
Usage: uv run python scratch/autorun/rerule.py <run_id>...      # prints the three-recommendation counts per run
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_run import load  # noqa: E402

from freight_lineitems.checks import diag, exclusion_basis_category  # noqa: E402
from freight_lineitems.disposition import flags_from, recommend  # noqa: E402
from freight_lineitems.schemas import Diagnostic  # noqa: E402

UNLISTED = "NUM.JUDGMENT.EXCLUSION_BASIS_UNLISTED"


def current(r: dict) -> dict:
    """{'recommendation', 'flags'} for a stored record under today's rules."""
    ds = [Diagnostic(**d) for d in r["judgment"]["diagnostics"]]
    if not any(d.code == UNLISTED for d in ds):          # runs made before P-15: derive it from the stored phrase
        for d in list(ds):
            if d.code == "NUM.JUDGMENT.DOLLAR_EXCLUDED" and exclusion_basis_category(d.evidence.get("exclusion_phrase")) is None:
                ds.append(diag(UNLISTED, d.path, {"id": d.evidence.get("id"), "exclusion_phrase": d.evidence.get("exclusion_phrase")}, "4"))
    fl = flags_from(ds)
    return {"recommendation": recommend(fl)["recommendation"], "flags": fl}


def dist(run_id: str) -> dict:
    c = Counter(current(r)["recommendation"] for r in load(run_id))
    return {k: c.get(k, 0) for k in ("PASSED_CHECKS", "HUMAN_REVIEW", "RETURN_SUGGESTED")}


if __name__ == "__main__":
    for rid in sys.argv[1:]:
        print(rid, dist(rid))
