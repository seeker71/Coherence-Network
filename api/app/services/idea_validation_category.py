"""Validation category inference and per-category verification hooks for ideas.

Runner and review automation call these without embedding category logic in CRUD.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.idea import Idea, ValidationCategory

_API_PATH = re.compile(r"/api/[^\s\"']+", re.I)
_CC_TOKEN = re.compile(r"\bcc\s+[a-z][a-z0-9_-]*", re.I)


def infer_validation_category(
    interfaces: list[str] | None,
    description: str | None,
) -> ValidationCategory:
    """Infer category from interfaces + description (spec-phase helper)."""
    iface = [str(x).strip() for x in (interfaces or []) if isinstance(x, str) and str(x).strip()]
    joined_i = " ".join(iface).lower()
    desc = (description or "").lower()
    blob = f"{joined_i} {desc}"

    if any(k in blob for k in ("uptime", "sla", "health check", "on-call", "pager", "monitoring")):
        return ValidationCategory.INFRASTRUCTURE
    if any(k in blob for k in ("community vote", "discussion forum", "engagement metric")):
        return ValidationCategory.COMMUNITY
    if "peer review" in blob or ("research" in desc and "literature" in desc):
        return ValidationCategory.RESEARCH
    if any(
        t in joined_i
        for t in ("evidence:url", "screenshot", "external-project", "upstream")
    ) or ("third-party" in blob and "api" not in blob):
        return ValidationCategory.EXTERNAL_PROJECT
    if _API_PATH.search(blob) or "machine:api" in joined_i or "/api/" in desc:
        return ValidationCategory.NETWORK_INTERNAL
    if _CC_TOKEN.search(blob) or "cli" in joined_i:
        return ValidationCategory.NETWORK_INTERNAL
    if "research" in desc or "hypothesis" in desc:
        return ValidationCategory.RESEARCH

    return ValidationCategory.NETWORK_INTERNAL


def _check_dict(passed: bool, summary: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "passed": passed,
        "summary": summary,
        "checks": checks,
    }


def verify_network_internal(idea: Idea) -> dict[str, Any]:
    """Heuristic: idea lists concrete API paths or automation tags."""
    checks: list[dict[str, Any]] = []
    text = " ".join(idea.interfaces or []) + " " + (idea.description or "")
    for m in _API_PATH.finditer(text):
        checks.append({"kind": "api_path", "value": m.group(0), "ok": True})
    if "machine:api" in " ".join(idea.interfaces or []).lower():
        checks.append({"kind": "interface_tag", "value": "machine:api", "ok": True})
    if _CC_TOKEN.search(text):
        checks.append({"kind": "cli_hint", "ok": True})
    passed = len(checks) > 0
    summary = (
        "Listed API/CLI hints found — verify each against production."
        if passed
        else "No API path or CLI hint in interfaces/description; add interfaces such as GET /api/health."
    )
    return _check_dict(passed, summary, checks)


def verify_external_project(idea: Idea) -> dict[str, Any]:
    """Heuristic: evidence URL or screenshot reference."""
    checks: list[dict[str, Any]] = []
    blob = " ".join(idea.interfaces or []) + " " + (idea.description or "")
    lowered = blob.lower()
    if "http://" in lowered or "https://" in lowered:
        checks.append({"kind": "url", "ok": True})
    if "screenshot" in lowered or "evidence" in lowered:
        checks.append({"kind": "evidence_keyword", "ok": True})
    passed = len(checks) > 0
    summary = (
        "Evidence markers present; confirm contributor-supplied proof manually."
        if passed
        else "Add an evidence URL or screenshot reference in description or interfaces."
    )
    return _check_dict(passed, summary, checks)


def verify_research(idea: Idea) -> dict[str, Any]:
    """Heuristic: spec linkage and peer-review readiness."""
    checks: list[dict[str, Any]] = []
    if idea.stage.value in ("specced", "implementing", "testing", "reviewing", "complete"):
        checks.append({"kind": "stage", "value": idea.stage.value, "ok": True})
    qs = len(idea.open_questions or [])
    if qs > 0:
        checks.append({"kind": "open_questions", "count": qs, "ok": True})
    passed = len(checks) > 0
    summary = (
        "Spec lifecycle or open questions recorded — complete peer review checklist."
        if passed
        else "Advance stage or record open questions before marking research validated."
    )
    return _check_dict(passed, summary, checks)


def verify_community(idea: Idea) -> dict[str, Any]:
    """Placeholder metrics hook — presence of engagement keywords."""
    checks: list[dict[str, Any]] = []
    blob = ((idea.description or "") + " " + " ".join(idea.interfaces or [])).lower()
    if any(k in blob for k in ("vote", "discussion", "contribution", "stake")):
        checks.append({"kind": "engagement_keyword", "ok": True})
    passed = len(checks) > 0
    summary = (
        "Engagement signals named — tie to real metrics (votes, tasks, threads) in review."
        if passed
        else "Describe how community validation will be measured."
    )
    return _check_dict(passed, summary, checks)


def verify_infrastructure(idea: Idea) -> dict[str, Any]:
    """Heuristic: health / uptime intent."""
    checks: list[dict[str, Any]] = []
    blob = ((idea.description or "") + " " + " ".join(idea.interfaces or [])).lower()
    if any(k in blob for k in ("health", "uptime", "slo", "sla", "monitor")):
        checks.append({"kind": "ops_keyword", "ok": True})
    passed = len(checks) > 0
    summary = (
        "Ops keywords found — confirm via /api/health or deployment checks."
        if passed
        else "Reference health or uptime targets in description."
    )
    return _check_dict(passed, summary, checks)


_VERIFIERS = {
    ValidationCategory.NETWORK_INTERNAL: verify_network_internal,
    ValidationCategory.EXTERNAL_PROJECT: verify_external_project,
    ValidationCategory.RESEARCH: verify_research,
    ValidationCategory.COMMUNITY: verify_community,
    ValidationCategory.INFRASTRUCTURE: verify_infrastructure,
}


def verify_for_category(idea: Idea) -> dict[str, Any]:
    """Run the verification function for the idea's validation_category."""
    fn = _VERIFIERS.get(idea.validation_category, verify_network_internal)
    inner = fn(idea)
    return {
        "category": idea.validation_category.value,
        **inner,
    }


def review_prompt_addendum_for_category(validation_category: str | None) -> str:
    """Extra instructions appended to review tasks (idea_to_task_bridge)."""
    raw = (validation_category or "network_internal").strip().lower()
    try:
        cat = ValidationCategory(raw)
    except ValueError:
        cat = ValidationCategory.NETWORK_INTERNAL

    if cat == ValidationCategory.NETWORK_INTERNAL:
        return (
            "Validation (network-internal): Confirm production evidence — Coherence API routes respond "
            "(curl GET /api/health, relevant /api/* paths from the idea), web surfaces load if claimed, "
            "and any `cc` CLI steps cited exist in the deployed CLI help."
        )
    if cat == ValidationCategory.EXTERNAL_PROJECT:
        return (
            "Validation (external-project): Require contributor evidence — working link to upstream repo, "
            "demo URL, or screenshot path recorded in the idea or spec; reject if only narrative proof."
        )
    if cat == ValidationCategory.RESEARCH:
        return (
            "Validation (research): Check spec completeness (requirements, risks, verification scenarios) "
            "and record peer review outcome; implementation may be N/A until research gates pass."
        )
    if cat == ValidationCategory.COMMUNITY:
        return (
            "Validation (community): Verify engagement metrics named in the idea — contributions, votes, or "
            "discussion threads — with links or API ids."
        )
    return (
        "Validation (infrastructure): Verify health checks, uptime or SLO statements against monitoring "
        "or `/api/health` and deployment status."
    )


def spec_phase_category_hint(interfaces: list[str] | None, description: str | None) -> str:
    """One-line hint for spec tasks (bridge spec direction)."""
    cat = infer_validation_category(interfaces, description)
    return (
        f"Set validation_category to `{cat.value}` (inferred from interfaces/description); "
        "override in the spec if the inference is wrong."
    )
