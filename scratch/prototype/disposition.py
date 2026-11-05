"""Steps 6a-6c: diagnostics -> flags, disposition rules, reject drafts. Everything is read from rules.yaml and
diagnostics_catalog.yaml; the LLM has no say here.
"""

from __future__ import annotations

from collections import defaultdict

from config import CATALOG, RULES, TAXONOMY
from gate import diag
from schemas import Diagnostic, Disposition, Flag, ObjectType, RejectDraft, Severity, Submission

FLAG_RULES = RULES["flags"]


def aggregate(diags: list[Diagnostic]) -> list[Flag]:
    """6a: group record-handling diagnostics by code, dedupe by location, attach configured severity/role."""
    groups: dict[str, list[Diagnostic]] = defaultdict(list)
    for d in diags:
        if d.handling.value != "record":
            continue
        groups[d.code].append(d)
    flags = []
    for code, ds in groups.items():
        cfg = FLAG_RULES[code]
        locs = sorted({d.location.path for d in ds})
        flags.append(Flag(code=code, object_type=ds[0].location.object_type, severity=Severity(cfg["severity"]),
                          locations=locs, evidence=[d.evidence for d in ds], n_diagnostics=len(ds),
                          escalation_role=cfg["role"], points=cfg.get("points", 0)))
    order = [s.value for s in Severity]
    return sorted(flags, key=lambda f: (-order.index(f.severity.value), f.code))


def reason_code_conflict(reason_code: str | None, sub: Submission | None) -> list[Diagnostic]:
    """Only when both sides are specific categories and they differ."""
    cats = RULES["reason_code_categories"].get(reason_code or "")
    if not cats or sub is None:
        return []
    codes = {c for j in sub.numbers for c in j.charge_codes} | {c for li in sub.line_items for c in li.charge_codes}
    model_cats = {TAXONOMY["codes"][c]["category"] for c in codes if c in TAXONOMY["codes"]} - {"OTHER", "PENDING", "TAX"}
    specific = RULES.get("reason_code_specific_codes", {}).get(reason_code)
    if not model_cats:
        return []
    clash = (not (model_cats & set(cats))) or (specific is not None and not (codes & set(specific)))
    if clash:
        return [diag("REC.FIELD.REASON_CODE_CONFLICT", ObjectType.RECORD, "source/reason_code",
                     {"reason_code": reason_code, "reason_category": cats, "model_categories": sorted(model_cats)}, "6a")]
    return []


def decide(flags: list[Flag]) -> Disposition:
    """6b: auto-reject, escalate, or split trusted. 'SPLIT_TRUSTED' says nothing about payment."""
    codes = {f.code for f in flags}
    ar = RULES["auto_reject"]
    if codes & set(ar["triggers"]) and not codes & set(ar["exempt_if_any"]):
        return Disposition(outcome="AUTO_REJECT", reasons=["auto_reject:" + c for c in sorted(codes & set(ar["triggers"]))],
                           score=0, rules_version=RULES["version"])
    alone = [f.code for f in flags if f.escalation_role == "alone"]
    score = sum(f.points for f in flags if f.escalation_role == "score")
    reasons = ["alone:" + c for c in alone]
    if score >= RULES["escalation"]["score_threshold"]:
        reasons.append(f"score:{score}>=" + str(RULES["escalation"]["score_threshold"]))
    if reasons:
        return Disposition(outcome="HUMAN_REVIEW", reasons=reasons, score=score, rules_version=RULES["version"])
    return Disposition(outcome="SPLIT_TRUSTED", reasons=[], score=score, rules_version=RULES["version"])


def reject_draft(flags: list[Flag], disp: Disposition) -> RejectDraft | None:
    """6c: automatic notice for AUTO_REJECT; a draft for the reviewer for HUMAN_REVIEW. Text comes from the catalog."""
    if disp.outcome == "SPLIT_TRUSTED":
        return None
    use = [f for f in flags if CATALOG[f.code].get("carrier_fix")]
    if disp.outcome == "AUTO_REJECT":
        use = [f for f in use if f.code in RULES["auto_reject"]["triggers"]]
    if not use:
        return None
    return RejectDraft(automatic=disp.outcome == "AUTO_REJECT", template_codes=[f.code for f in use],
                       reasons=[CATALOG[f.code]["trigger"] for f in use],
                       required_changes=[CATALOG[f.code]["carrier_fix"] for f in use],
                       acceptance_criteria=[CATALOG[f.code]["acceptance"] for f in use])
