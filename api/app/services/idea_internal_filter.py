"""Internal-idea classification — pure config + ID heuristics.

Extracted from idea_service.py to reduce that module under the modularity
threshold (#163). Public surface (re-exported from idea_service):
  is_internal_idea_id, canonical_discovered_idea_id

Private helpers (only used inside the idea_service universe):
  _configured_internal_idea_prefixes, _configured_internal_idea_exact_ids,
  _configured_internal_idea_interface_tags, _is_transient_internal_idea_id,
  _canonical_discovered_idea_id, _should_track_discovered_idea_id
"""

from __future__ import annotations

import re

from app.config_loader import get_str


_KNOWN_INTERNAL_IDEA_IDS: set[str] = {
    "coherence-network-agent-pipeline",
    "coherence-network-api-runtime",
    "coherence-network-value-attribution",
    "coherence-network-web-interface",
    "deployment-gate-reliability",
    "interface-trust-surface",
    "minimum-e2e-path",
    "funder-proof-page",
    "idea-hierarchy-model",
    "unified-sqlite-store",
    "agent-prompt-ab-roi",
    "agent-failed-task-diagnostics",
    "agent-auto-heal",
    "agent-grounded-measurement",
}

DEFAULT_INTERNAL_IDEA_PREFIXES = (
    "spec-origin-",
    "endpoint-lineage-",
    "public-e2e-",
    "e2e-idea-",
)
DEFAULT_INTERNAL_IDEA_INTERFACE_TAGS = {"machine:commit-evidence"}
TRANSIENT_INTERNAL_ID_PATTERNS = (
    re.compile(r"^public-e2e-[0-9a-f]{8}$"),
)
DISCOVERED_INTERNAL_ID_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^public-e2e-[0-9a-f]{8}$"), "deployment-gate-reliability"),
    (re.compile(r"^e2e-idea-[0-9a-f]{8}$"), "deployment-gate-reliability"),
    (re.compile(r"^spec-origin-"), "portfolio-governance"),
    (re.compile(r"^endpoint-lineage-"), "oss-interface-alignment"),
)

_SCHEMA_ARTIFACT_IDS = frozenset({
    "string", "string?", "string|null", "number", "boolean", "integer",
    "object", "array", "null", "type", "required", "properties",
    "properties:", "tracked:", "added_properties:",
})


def _configured_internal_idea_prefixes() -> set[str]:
    raw = get_str("ideas", "internal_idea_id_prefixes")
    if not raw:
        return set(DEFAULT_INTERNAL_IDEA_PREFIXES)
    out = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return out or set(DEFAULT_INTERNAL_IDEA_PREFIXES)


def _configured_internal_idea_exact_ids() -> set[str]:
    out = set(_KNOWN_INTERNAL_IDEA_IDS)
    raw = get_str("ideas", "internal_idea_id_exact")
    if raw:
        out.update(item.strip().lower() for item in raw.split(",") if item.strip())
    return out


def _configured_internal_idea_interface_tags() -> set[str]:
    raw = get_str("ideas", "internal_idea_interface_tags")
    if not raw:
        return set(DEFAULT_INTERNAL_IDEA_INTERFACE_TAGS)
    out = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return out or set(DEFAULT_INTERNAL_IDEA_INTERFACE_TAGS)


def is_internal_idea_id(idea_id: str, interfaces: list[str] | None = None) -> bool:
    normalized_id = str(idea_id or "").strip().lower()
    if not normalized_id:
        return False
    if normalized_id in _configured_internal_idea_exact_ids():
        return True
    for prefix in _configured_internal_idea_prefixes():
        if normalized_id.startswith(prefix):
            return True
    if isinstance(interfaces, list):
        tags = {str(item).strip().lower() for item in interfaces if str(item).strip()}
        if tags.intersection(_configured_internal_idea_interface_tags()):
            return True
    return False


def _is_transient_internal_idea_id(idea_id: str) -> bool:
    normalized_id = str(idea_id or "").strip().lower()
    if not normalized_id:
        return False
    return any(pattern.match(normalized_id) for pattern in TRANSIENT_INTERNAL_ID_PATTERNS)


def _canonical_discovered_idea_id(idea_id: str) -> str | None:
    normalized_id = str(idea_id or "").strip().lower().rstrip("])}\"'")
    if not normalized_id or normalized_id == "unmapped":
        return None
    # Reject schema/YAML artifacts that aren't real idea IDs
    if normalized_id in _SCHEMA_ARTIFACT_IDS:
        return None
    # Reject IDs that are clearly not slugs (contain special chars)
    if any(c in normalized_id for c in "?[]{}|;:\"'<>"):
        return None
    # Reject very short IDs (likely parsing noise)
    if len(normalized_id) < 4:
        return None
    for pattern, target_id in DISCOVERED_INTERNAL_ID_ALIASES:
        if pattern.match(normalized_id):
            return target_id
    if _is_transient_internal_idea_id(normalized_id):
        return None
    return normalized_id


def canonical_discovered_idea_id(idea_id: str) -> str | None:
    return _canonical_discovered_idea_id(idea_id)


def _should_track_discovered_idea_id(idea_id: str) -> bool:
    return _canonical_discovered_idea_id(idea_id) is not None
