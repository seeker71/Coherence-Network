"""MCP tool registry: maps tool names to handlers, schemas, and descriptions.

Each entry defines a tool that the MCP server exposes. Handlers are thin
wrappers over existing service functions -- no business logic lives here.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_safe(obj: Any) -> Any:
    """Convert pydantic models and other objects to JSON-serialisable dicts."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_json_safe(item) for item in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Read-only tool handlers
# ---------------------------------------------------------------------------

def browse_ideas_handler(arguments: dict[str, Any]) -> Any:
    from app.services import idea_service

    sort_by = arguments.get("sort_by", "free_energy")
    limit = int(arguments.get("limit", 20))
    offset = int(arguments.get("offset", 0))

    result = idea_service.list_ideas(
        limit=limit,
        offset=offset,
        sort_method=sort_by,
    )
    return _json_safe(result)


def get_idea_handler(arguments: dict[str, Any]) -> Any:
    from app.services import idea_service

    idea_id = str(arguments["idea_id"])
    result = idea_service.get_idea(idea_id)
    if result is None:
        return {"error": f"Idea '{idea_id}' not found"}
    return _json_safe(result)


def browse_specs_handler(arguments: dict[str, Any]) -> Any:
    from app.services import spec_registry_service

    limit = int(arguments.get("limit", 20))
    offset = int(arguments.get("offset", 0))
    results = spec_registry_service.list_specs(limit=limit, offset=offset)
    return _json_safe(results)


def get_resonance_feed_handler(arguments: dict[str, Any]) -> Any:
    """Return ideas with recent activity (approximated by listing all and
    slicing to limit -- a lightweight proxy until a dedicated feed exists)."""
    from app.services import idea_service

    limit = int(arguments.get("limit", 20))
    # window_hours is accepted but not deeply filtered in the service layer;
    # we return the top ideas sorted by score as a reasonable proxy.
    result = idea_service.list_ideas(limit=limit, sort_method="free_energy")
    return _json_safe(result)


def get_strategies_handler(arguments: dict[str, Any]) -> Any:
    from app.services import federation_service

    strategy_type = arguments.get("strategy_type")
    rows, total = federation_service.list_active_strategies(
        strategy_type=strategy_type,
    )
    return {"strategies": rows, "total": total}


def get_provider_stats_handler(arguments: dict[str, Any]) -> Any:
    from app.services.slot_selection_service import SlotSelector

    selector = SlotSelector("provider_spec")
    return selector.stats()


# ---------------------------------------------------------------------------
# Write tool handlers (require contributor_id)
# ---------------------------------------------------------------------------

def publish_idea_handler(arguments: dict[str, Any]) -> Any:
    from app.models.governance import (
        ActorType,
        ChangeRequestCreate,
        ChangeRequestType,
    )
    from app.services import governance_service

    idea_id = f"mcp-{uuid4().hex[:12]}"
    payload = {
        "id": idea_id,
        "name": str(arguments["name"]),
        "description": str(arguments["description"]),
        "potential_value": float(arguments["potential_value"]),
        "estimated_cost": float(arguments["estimated_cost"]),
        "confidence": float(arguments.get("confidence", 0.5)),
    }
    cr = governance_service.create_change_request(
        ChangeRequestCreate(
            request_type=ChangeRequestType.IDEA_CREATE,
            title=f"MCP: publish idea '{payload['name']}'",
            payload=payload,
            proposer_id=str(arguments["contributor_id"]),
            proposer_type=ActorType.MACHINE,
            auto_apply_on_approval=True,
        )
    )
    return _json_safe(cr)


def add_question_handler(arguments: dict[str, Any]) -> Any:
    from app.models.governance import (
        ActorType,
        ChangeRequestCreate,
        ChangeRequestType,
    )
    from app.services import governance_service

    payload = {
        "idea_id": str(arguments["idea_id"]),
        "question": str(arguments["question"]),
        "value_to_whole": float(arguments["value_to_whole"]),
        "estimated_cost": float(arguments["estimated_cost"]),
    }
    cr = governance_service.create_change_request(
        ChangeRequestCreate(
            request_type=ChangeRequestType.IDEA_ADD_QUESTION,
            title=f"MCP: add question to '{payload['idea_id']}'",
            payload=payload,
            proposer_id=str(arguments["contributor_id"]),
            proposer_type=ActorType.MACHINE,
            auto_apply_on_approval=True,
        )
    )
    return _json_safe(cr)


def answer_question_handler(arguments: dict[str, Any]) -> Any:
    from app.models.governance import (
        ActorType,
        ChangeRequestCreate,
        ChangeRequestType,
    )
    from app.services import governance_service, idea_service

    idea_id = str(arguments["idea_id"])
    question_index = int(arguments["question_index"])

    # Resolve question text from index
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        return {"error": f"Idea '{idea_id}' not found"}
    if question_index < 0 or question_index >= len(idea.open_questions):
        return {"error": f"Question index {question_index} out of range (0..{len(idea.open_questions) - 1})"}

    question_text = idea.open_questions[question_index].question
    payload = {
        "idea_id": idea_id,
        "question": question_text,
        "answer": str(arguments["answer"]),
    }
    cr = governance_service.create_change_request(
        ChangeRequestCreate(
            request_type=ChangeRequestType.IDEA_ANSWER_QUESTION,
            title=f"MCP: answer question on '{idea_id}'",
            payload=payload,
            proposer_id=str(arguments["contributor_id"]),
            proposer_type=ActorType.MACHINE,
            auto_apply_on_approval=True,
        )
    )
    return _json_safe(cr)


def create_spec_handler(arguments: dict[str, Any]) -> Any:
    from app.models.governance import (
        ActorType,
        ChangeRequestCreate,
        ChangeRequestType,
    )
    from app.services import governance_service

    spec_id = f"mcp-spec-{uuid4().hex[:8]}"
    payload = {
        "spec_id": spec_id,
        "title": str(arguments["title"]),
        "summary": str(arguments["summary"]),
        "idea_id": str(arguments.get("idea_id", "")),
        "potential_value": 0.0,
        "actual_value": 0.0,
        "estimated_cost": 0.0,
        "actual_cost": 0.0,
        "created_by_contributor_id": str(arguments["contributor_id"]),
    }
    cr = governance_service.create_change_request(
        ChangeRequestCreate(
            request_type=ChangeRequestType.SPEC_CREATE,
            title=f"MCP: create spec '{payload['title']}'",
            payload=payload,
            proposer_id=str(arguments["contributor_id"]),
            proposer_type=ActorType.MACHINE,
            auto_apply_on_approval=True,
        )
    )
    return _json_safe(cr)


def fork_idea_handler(arguments: dict[str, Any]) -> Any:
    from app.services import idea_service

    source_id = str(arguments["source_idea_id"])
    contributor_id = str(arguments["contributor_id"])
    adaptation_notes = arguments.get("adaptation_notes", "")

    source = idea_service.get_idea(source_id)
    if source is None:
        return {"error": f"Source idea '{source_id}' not found"}

    fork_id = f"fork-{uuid4().hex[:12]}"
    forked = idea_service.create_idea(
        idea_id=fork_id,
        name=f"Fork of {source.name}",
        description=f"Forked from {source_id}. {adaptation_notes or ''}".strip(),
        potential_value=source.potential_value,
        estimated_cost=source.estimated_cost,
        confidence=source.confidence,
        parent_idea_id=source_id,
    )
    if forked is None:
        return {"error": "Failed to create forked idea"}
    return _json_safe(forked)


# ---------------------------------------------------------------------------
# Measurement tool handlers
# ---------------------------------------------------------------------------

def push_measurements_handler(arguments: dict[str, Any]) -> Any:
    from app.services import federation_service

    node_id = str(arguments["node_id"])
    summaries = arguments.get("summaries", [])
    if not isinstance(summaries, list):
        return {"error": "summaries must be a list"}
    count = federation_service.store_measurement_summaries(node_id, summaries)
    return {"stored": count, "node_id": node_id}


def record_usage_handler(arguments: dict[str, Any]) -> Any:
    from app.models.value_lineage import UsageEventCreate
    from app.services import value_lineage_service

    # idea_id is used as lineage_id lookup -- find lineage links for this idea
    idea_id = str(arguments["idea_id"])
    source = str(arguments["source"])
    metric = str(arguments["metric"])
    value = float(arguments["value"])

    # Try to find a lineage link for this idea
    links = value_lineage_service.list_links(limit=500)
    matching = [lnk for lnk in links if lnk.idea_id == idea_id]
    if not matching:
        return {"error": f"No lineage link found for idea '{idea_id}'"}

    lineage_id = matching[0].id
    event = value_lineage_service.add_usage_event(
        lineage_id,
        UsageEventCreate(source=source, metric=metric, value=value),
    )
    if event is None:
        return {"error": f"Lineage link '{lineage_id}' not found"}
    return _json_safe(event)


# ---------------------------------------------------------------------------
# Coordination tool handlers
# ---------------------------------------------------------------------------

def vote_on_change_handler(arguments: dict[str, Any]) -> Any:
    from app.models.governance import ActorType, ChangeRequestVoteCreate, VoteDecision
    from app.services import governance_service

    change_request_id = str(arguments["change_request_id"])
    vote = str(arguments["vote"]).lower()
    rationale = arguments.get("rationale")
    voter_id = str(arguments["voter_id"])

    decision = VoteDecision.YES if vote in ("yes", "approve") else VoteDecision.NO
    result = governance_service.cast_vote(
        change_request_id,
        ChangeRequestVoteCreate(
            voter_id=voter_id,
            voter_type=ActorType.MACHINE,
            decision=decision,
            rationale=rationale,
        ),
    )
    if result is None:
        return {"error": f"Change request '{change_request_id}' not found"}
    return _json_safe(result)


def list_open_changes_handler(arguments: dict[str, Any]) -> Any:
    from app.services import governance_service

    limit = int(arguments.get("limit", 20))
    all_crs = governance_service.list_change_requests(limit=limit)
    open_crs = [cr for cr in all_crs if cr.status.value == "open"]
    return _json_safe(open_crs)


# ---------------------------------------------------------------------------
# Tool definitions registry
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    # --- Read-only tools ---
    {
        "name": "browse_ideas",
        "description": "Browse the idea portfolio sorted by value. Returns ideas with scores, stages, and open questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "enum": ["free_energy", "marginal_cc"], "default": "free_energy"},
                "limit": {"type": "integer", "default": 20},
                "offset": {"type": "integer", "default": 0},
            },
        },
        "handler": browse_ideas_handler,
    },
    {
        "name": "get_idea",
        "description": "Get a single idea by ID with full details including questions and stage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string"},
            },
            "required": ["idea_id"],
        },
        "handler": get_idea_handler,
    },
    {
        "name": "browse_specs",
        "description": "Browse the spec registry. Returns specs with value/cost tracking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "offset": {"type": "integer", "default": 0},
            },
        },
        "handler": browse_specs_handler,
    },
    {
        "name": "get_resonance_feed",
        "description": "Get ideas with recent activity, sorted by energy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "window_hours": {"type": "integer", "default": 24},
                "limit": {"type": "integer", "default": 20},
            },
        },
        "handler": get_resonance_feed_handler,
    },
    {
        "name": "get_strategies",
        "description": "Get active strategy broadcasts from the federation network.",
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy_type": {"type": "string", "description": "Filter by strategy type (optional)"},
            },
        },
        "handler": get_strategies_handler,
    },
    {
        "name": "get_provider_stats",
        "description": "Get provider success rates and selection probabilities from Thompson Sampling.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
        "handler": get_provider_stats_handler,
    },
    # --- Write tools ---
    {
        "name": "publish_idea",
        "description": "Publish a new idea via governance change request. Requires approval before it takes effect.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "potential_value": {"type": "number"},
                "estimated_cost": {"type": "number"},
                "confidence": {"type": "number", "default": 0.5},
                "contributor_id": {"type": "string"},
            },
            "required": ["name", "description", "potential_value", "estimated_cost", "contributor_id"],
        },
        "handler": publish_idea_handler,
    },
    {
        "name": "add_question",
        "description": "Add an open question to an idea via governance change request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string"},
                "question": {"type": "string"},
                "value_to_whole": {"type": "number"},
                "estimated_cost": {"type": "number"},
                "contributor_id": {"type": "string"},
            },
            "required": ["idea_id", "question", "value_to_whole", "estimated_cost", "contributor_id"],
        },
        "handler": add_question_handler,
    },
    {
        "name": "answer_question",
        "description": "Answer an open question on an idea via governance change request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string"},
                "question_index": {"type": "integer"},
                "answer": {"type": "string"},
                "contributor_id": {"type": "string"},
            },
            "required": ["idea_id", "question_index", "answer", "contributor_id"],
        },
        "handler": answer_question_handler,
    },
    {
        "name": "create_spec",
        "description": "Create a spec entry linked to an idea via governance change request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "contributor_id": {"type": "string"},
            },
            "required": ["idea_id", "title", "summary", "contributor_id"],
        },
        "handler": create_spec_handler,
    },
    {
        "name": "fork_idea",
        "description": "Fork an existing idea with value lineage. Creates a new idea with parent_idea_id set.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_idea_id": {"type": "string"},
                "contributor_id": {"type": "string"},
                "adaptation_notes": {"type": "string"},
            },
            "required": ["source_idea_id", "contributor_id"],
        },
        "handler": fork_idea_handler,
    },
    # --- Measurement tools ---
    {
        "name": "push_measurements",
        "description": "Push provider measurement summaries from a federation node.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "summaries": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
            "required": ["node_id", "summaries"],
        },
        "handler": push_measurements_handler,
    },
    {
        "name": "record_usage",
        "description": "Record a value/usage event against an idea's lineage link.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string"},
                "source": {"type": "string"},
                "metric": {"type": "string"},
                "value": {"type": "number"},
            },
            "required": ["idea_id", "source", "metric", "value"],
        },
        "handler": record_usage_handler,
    },
    # --- Coordination tools ---
    {
        "name": "vote_on_change",
        "description": "Cast a vote (yes/no) on a pending governance change request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "change_request_id": {"type": "string"},
                "vote": {"type": "string", "enum": ["yes", "no"]},
                "rationale": {"type": "string"},
                "voter_id": {"type": "string"},
            },
            "required": ["change_request_id", "vote", "voter_id"],
        },
        "handler": vote_on_change_handler,
    },
    {
        "name": "list_open_changes",
        "description": "List pending governance change requests awaiting votes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
            },
        },
        "handler": list_open_changes_handler,
    },
]

# Build lookup for fast access by name
TOOL_MAP: dict[str, dict[str, Any]] = {t["name"]: t for t in TOOLS}
