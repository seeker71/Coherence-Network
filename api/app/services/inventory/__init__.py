"""Inventory submodules: constants, cache, spec discovery, lineage, evidence, flow, idea cards."""

from app.services.inventory.constants import (
    IMPLEMENTATION_REQUEST_PATTERN,
    _ASSET_MODULARITY_LIMITS,
    _FLOW_STAGE_ESTIMATED_COST,
    _FLOW_STAGE_ORDER,
    _FLOW_STAGE_TASK_TYPE,
    _INVENTORY_CACHE,
    _PROCESS_COMPLETENESS_TASK_TYPE_BY_CHECK,
    _ROI_SPEC_CHUNK_PLAN,
    _ROI_SPEC_CHEAP_MODEL,
    _ROI_SPEC_TASK_INPUT_MAX_TOKENS,
    _ROI_SPEC_TASK_OUTPUT_MAX_TOKENS,
    _TRACEABILITY_GAP_CONTRIBUTOR_ID,
    _TRACEABILITY_GAP_DEFAULT_IDEA_ID,
)
from app.services.inventory.cache import (
    _cache_key,
    _inventory_environment_cache_key,
    _inventory_cache_ttl_seconds,
    _inventory_timing_enabled,
    _inventory_timing_ms_threshold,
    _read_inventory_cache,
    _row_signature,
    _write_inventory_cache,
)
from app.services.inventory.spec_discovery import (
    _project_root,
    _spec_api_path,
    _idea_api_path,
    _discover_specs,
    _spec_source_path_for_id,
    _tracking_ref,
    _tracking_repository,
    sync_spec_implementation_gap_tasks,
)
from app.services.inventory.lineage import build_system_lineage_inventory
from app.services.inventory.impl_questions import (
    sync_implementation_request_question_tasks,
)
from app.services.inventory.evidence import (
    _read_commit_evidence_records,
    build_commit_evidence_inventory,
)
from app.services.inventory.route_evidence import (
    build_route_evidence_inventory,
    _ROUTE_PROBE_DISCOVERY_CACHE,
)
from app.services.inventory.proactive import (
    derive_proactive_questions_from_recent_changes,
    sync_proactive_questions_from_recent_changes,
)

__all__ = [
    "IMPLEMENTATION_REQUEST_PATTERN",
    "_ASSET_MODULARITY_LIMITS",
    "_FLOW_STAGE_ESTIMATED_COST",
    "_FLOW_STAGE_ORDER",
    "_FLOW_STAGE_TASK_TYPE",
    "_INVENTORY_CACHE",
    "_PROCESS_COMPLETENESS_TASK_TYPE_BY_CHECK",
    "_ROI_SPEC_CHUNK_PLAN",
    "_ROI_SPEC_CHEAP_MODEL",
    "_ROI_SPEC_TASK_INPUT_MAX_TOKENS",
    "_ROI_SPEC_TASK_OUTPUT_MAX_TOKENS",
    "_TRACEABILITY_GAP_CONTRIBUTOR_ID",
    "_TRACEABILITY_GAP_DEFAULT_IDEA_ID",
    "_cache_key",
    "_inventory_environment_cache_key",
    "_inventory_cache_ttl_seconds",
    "_inventory_timing_enabled",
    "_inventory_timing_ms_threshold",
    "_read_inventory_cache",
    "_row_signature",
    "_write_inventory_cache",
    "_project_root",
    "_spec_api_path",
    "_idea_api_path",
    "_discover_specs",
    "_spec_source_path_for_id",
    "_tracking_ref",
    "_tracking_repository",
    "build_system_lineage_inventory",
    "sync_implementation_request_question_tasks",
    "sync_spec_implementation_gap_tasks",
    "_read_commit_evidence_records",
    "build_commit_evidence_inventory",
    "build_route_evidence_inventory",
    "_ROUTE_PROBE_DISCOVERY_CACHE",
    "derive_proactive_questions_from_recent_changes",
    "sync_proactive_questions_from_recent_changes",
]
