"""Shared constants, patterns, and limits for inventory services."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.models.agent import TaskType

logger = logging.getLogger("coherence.inventory")

# ROI helpers (used by lineage, flow_helpers, roi_helpers, proactive)
def _question_roi(value_to_whole: float, estimated_cost: float) -> float:
    if estimated_cost <= 0:
        return 0.0
    return round(float(value_to_whole) / float(estimated_cost), 4)


def _answer_roi(measured_delta: float | None, estimated_cost: float) -> float:
    if measured_delta is None or estimated_cost <= 0:
        return 0.0
    return round(float(measured_delta) / float(estimated_cost), 4)


IMPLEMENTATION_REQUEST_PATTERN = re.compile(
    r"\b(implement|implementation|build|create|add|fix|integrate|ship|expose|wire|develop)\b",
    re.IGNORECASE,
)
_API_KEY_TERM_RE = re.compile(r"\bapi[_ -]?key\b", re.IGNORECASE)
_API_KEY_ENV_RE = re.compile(r"\bOPENAI_API_KEY\b", re.IGNORECASE)


def _sanitize_oauth_only_language(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    cleaned = _API_KEY_ENV_RE.sub("OAuth session credential", cleaned)
    cleaned = _API_KEY_TERM_RE.sub("oauth", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()

_FLOW_STAGE_ORDER: tuple[str, ...] = ("spec", "process", "implementation", "validation")
_FLOW_STAGE_ESTIMATED_COST: dict[str, float] = {
    "spec": 2.0,
    "process": 3.0,
    "implementation": 5.0,
    "validation": 2.0,
}
_FLOW_STAGE_TASK_TYPE: dict[str, TaskType] = {
    "spec": TaskType.SPEC,
    "process": TaskType.SPEC,
    "implementation": TaskType.IMPL,
    "validation": TaskType.TEST,
}
_TRACEABILITY_GAP_DEFAULT_IDEA_ID = "portfolio-governance"
_TRACEABILITY_GAP_CONTRIBUTOR_ID = "openai-codex"
_PROCESS_COMPLETENESS_TASK_TYPE_BY_CHECK: dict[str, TaskType] = {
    "ideas_have_standing_questions": TaskType.SPEC,
    "specs_linked_to_ideas": TaskType.SPEC,
    "specs_have_process_and_pseudocode": TaskType.SPEC,
    "ideas_have_specs": TaskType.SPEC,
    "endpoints_have_idea_mapping": TaskType.IMPL,
    "endpoints_have_spec_coverage": TaskType.SPEC,
    "endpoints_have_process_coverage": TaskType.IMPL,
    "endpoints_have_validation_coverage": TaskType.TEST,
    "all_endpoints_have_usage_events": TaskType.TEST,
    "canonical_route_registry_complete": TaskType.IMPL,
    "assets_are_modular_and_reusable": TaskType.SPEC,
}

_ASSET_MODULARITY_LIMITS: dict[str, int] = {
    "idea_description_sentences": 10,
    "idea_description_chars": 1800,
    "spec_summary_sentences": 10,
    "spec_summary_chars": 2000,
    "process_summary_sentences": 10,
    "process_summary_chars": 2000,
    "pseudocode_summary_sentences": 10,
    "pseudocode_summary_chars": 2200,
    "implementation_summary_sentences": 10,
    "implementation_summary_chars": 2200,
    "implementation_file_lines": 450,
}

_ROI_SPEC_CHEAP_MODEL = "openai/gpt-4o-mini"
_ROI_SPEC_TASK_INPUT_MAX_TOKENS = 1200
_ROI_SPEC_TASK_OUTPUT_MAX_TOKENS = 300
_ROI_SPEC_CHUNK_PLAN: tuple[tuple[str, str, str], ...] = (
    (
        "scope_roi",
        "Scope and ROI frame",
        "Constrain to a small deliverable and restate explicit ROI signal assumptions.",
    ),
    (
        "process_pseudocode",
        "Process and pseudocode",
        "Write process+pseudocode for the narrowed scope only; avoid broad refactors.",
    ),
    (
        "validation_rollout",
        "Validation and rollout",
        "Define measurable validation plus rollout guardrails tied to ROI updates.",
    ),
)

_INVENTORY_CACHE: dict[str, dict[str, Any]] = {
    "system_lineage": {"expires_at": 0.0, "items": {}},
    "flow": {"expires_at": 0.0, "items": {}},
    "idea_cards": {"expires_at": 0.0, "items": {}},
}
