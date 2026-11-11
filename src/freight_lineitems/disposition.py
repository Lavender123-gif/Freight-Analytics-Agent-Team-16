"""Flags and the recommendation (R1a). Everything is read from rules.yaml; the model has no say here.

Order (decision 2.3): anything that needs a person -> HUMAN_REVIEW; else anything returnable -> RETURN_SUGGESTED;
else PASSED_CHECKS. Every record goes to a reviewer whatever the recommendation; the system takes no action
(decision 2.2). A return draft is text for the reviewer to use or edit; nothing is sent.
"""

from __future__ import annotations

from collections import defaultdict

from freight_lineitems.config import RULES
from freight_lineitems.schemas import Diagnostic

FLAG_RULES: dict = RULES["flags"]
RECOMMENDATIONS = {"HUMAN_REVIEW": "建议人工审核", "RETURN_SUGGESTED": "建议退回承运商", "PASSED_CHECKS": "解析通过检查"}


def flags_from(diags: list[Diagnostic]) -> list[dict]:
    """Group diagnostics by code. A code missing from rules.yaml becomes an `attention` flag marked unconfigured,
    so a forgotten rule is visible instead of silently ignored."""
    groups: dict[str, list[Diagnostic]] = defaultdict(list)
    for d in diags:
        groups[d.code].append(d)
    out = []
    for code, ds in groups.items():
        cfg = FLAG_RULES.get(code)
        out.append({
            "code": code,
            "severity": cfg["severity"] if cfg else "attention",
            "unconfigured": cfg is None,
            "origin": "MODEL_REPORTED" if any(d.origin == "MODEL_REPORTED" for d in ds) else "CODE_RULE",
            "paths": sorted({d.path for d in ds}),
            "evidence": [d.evidence for d in ds],
            "points_to": next((d.evidence.get("points_to_record_id") for d in ds if d.evidence.get("points_to_record_id")), None),
        })
    present = set(groups)
    for f in out:   # rules.yaml `subsumption`: implied by a code-decided fact on the same record -> shown as info
        by = [c for c in RULES.get("subsumption", {}).get(f["code"], []) if c in present]
        if by and f["severity"] != "info":
            f["severity_before_subsumption"], f["severity"], f["subsumed_by"] = f["severity"], "info", by
    order = {"attention": 0, "return": 1, "info": 2}
    return sorted(out, key=lambda f: (order[f["severity"]], f["code"]))


def recommend(flags: list[dict]) -> dict:
    attention = [f["code"] for f in flags if f["severity"] == "attention"]
    ret = [f["code"] for f in flags if f["severity"] == "return"]
    if attention:
        rec, decisive = "HUMAN_REVIEW", attention
    elif ret:
        rec, decisive = "RETURN_SUGGESTED", ret
    else:
        rec, decisive = "PASSED_CHECKS", []
    draft = None
    if ret:   # the draft is prepared whenever a returnable issue exists; the reviewer decides whether to use it
        draft = {"issues": ret, "requested_changes": [FLAG_RULES[c]["carrier_fix"] for c in ret if FLAG_RULES[c].get("carrier_fix")],
                 "sent": False}
    return {"recommendation": rec, "recommendation_zh": RECOMMENDATIONS[rec], "decisive_flags": decisive,
            "return_draft": draft, "rules_version": RULES["version"]}
