"""Coherence Network MCP server — Python implementation.

Exposes the Coherence Network API as 60 typed MCP tools.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

API_BASE = os.environ.get("COHERENCE_API_URL", "https://api.coherencycoin.com").rstrip("/")
API_KEY = os.environ.get("COHERENCE_API_KEY", "")

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE}{path}"
    filtered = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        r = httpx.get(url, params=filtered, headers=_headers(), timeout=15.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        return {"error": f"{exc.response.status_code} {exc.response.reason_phrase}"}
    except Exception as exc:
        return {"error": str(exc)}


def api_post(path: str, body: dict[str, Any]) -> Any:
    url = f"{API_BASE}{path}"
    try:
        r = httpx.post(url, json=body, headers=_headers(), timeout=15.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.reason_phrase)
        except Exception:
            detail = exc.response.reason_phrase
        return {"error": detail}
    except Exception as exc:
        return {"error": str(exc)}


def api_patch(path: str, body: dict[str, Any]) -> Any:
    url = f"{API_BASE}{path}"
    try:
        r = httpx.patch(url, json=body, headers=_headers(), timeout=15.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.reason_phrase)
        except Exception:
            detail = exc.response.reason_phrase
        return {"error": detail}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    # Ideas
    Tool(
        name="coherence_list_ideas",
        description="Browse the idea portfolio ranked by ROI and free-energy score. Returns ideas with scores, manifestation status, and selection weights.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "number", "description": "Max ideas to return (default 20)", "default": 20},
                "search": {"type": "string", "description": "Search keyword to filter ideas"},
                "workspace_id": {"type": "string", "description": "Optional workspace filter. Defaults to all workspaces."},
                "pillar": {"type": "string", "description": "Optional pillar filter."},
                "curated_only": {"type": "boolean", "description": "If true, only return curated super-ideas."},
            },
        },
    ),
    Tool(
        name="coherence_get_idea",
        description="Get full details for a single idea including scores, open questions, value gap, and linked tasks.",
        inputSchema={
            "type": "object",
            "properties": {
                "idea_id": {"type": "string", "description": "The idea ID"},
            },
            "required": ["idea_id"],
        },
    ),
    Tool(
        name="coherence_idea_progress",
        description="Get progress for an idea: stage, tasks by phase, CC staked/spent, contributors.",
        inputSchema={
            "type": "object",
            "properties": {"idea_id": {"type": "string"}},
            "required": ["idea_id"],
        },
    ),
    Tool(
        name="coherence_select_idea",
        description="Let the portfolio engine select the next highest-ROI idea to work on. Temperature controls exploration vs exploitation.",
        inputSchema={
            "type": "object",
            "properties": {
                "temperature": {"type": "number", "description": "0=deterministic, >1=explore (default 0.5)", "default": 0.5},
            },
        },
    ),
    Tool(
        name="coherence_showcase",
        description="List validated, shipped ideas that have proven their value.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="coherence_resonance",
        description="Show which ideas are generating the most energy and activity right now.",
        inputSchema={"type": "object", "properties": {}},
    ),
    # Specs
    Tool(
        name="coherence_list_specs",
        description="List feature specs with ROI metrics, value gaps, and implementation summaries.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "number", "default": 20},
                "search": {"type": "string", "description": "Search keyword"},
            },
        },
    ),
    Tool(
        name="coherence_get_spec",
        description="Get full spec detail including implementation summary, pseudocode, and ROI.",
        inputSchema={
            "type": "object",
            "properties": {"spec_id": {"type": "string"}},
            "required": ["spec_id"],
        },
    ),
    # Lineage
    Tool(
        name="coherence_list_lineage",
        description="List value lineage chains connecting ideas to specs, implementations, and payouts.",
        inputSchema={
            "type": "object",
            "properties": {"limit": {"type": "number", "default": 20}},
        },
    ),
    Tool(
        name="coherence_lineage_valuation",
        description="Get ROI valuation for a lineage chain — measured value, estimated cost, and ROI ratio.",
        inputSchema={
            "type": "object",
            "properties": {"lineage_id": {"type": "string"}},
            "required": ["lineage_id"],
        },
    ),
    # Identity
    Tool(
        name="coherence_list_providers",
        description="List all 37 supported identity providers grouped by category (Social, Dev, Crypto/Web3, Professional, Identity, Custom).",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="coherence_link_identity",
        description="Link a provider identity (GitHub, Discord, Ethereum, etc.) to a contributor. No registration required.",
        inputSchema={
            "type": "object",
            "properties": {
                "contributor_id": {"type": "string", "description": "Contributor name"},
                "provider": {"type": "string", "description": "Provider key (github, discord, ethereum, solana, ...)"},
                "provider_id": {"type": "string", "description": "Handle, address, or username on that provider"},
            },
            "required": ["contributor_id", "provider", "provider_id"],
        },
    ),
    Tool(
        name="coherence_lookup_identity",
        description="Find which contributor owns a specific provider identity. Reverse lookup.",
        inputSchema={
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "provider_id": {"type": "string"},
            },
            "required": ["provider", "provider_id"],
        },
    ),
    Tool(
        name="coherence_get_identities",
        description="Get all linked identities for a contributor.",
        inputSchema={
            "type": "object",
            "properties": {"contributor_id": {"type": "string"}},
            "required": ["contributor_id"],
        },
    ),
    # Contributions
    Tool(
        name="coherence_record_contribution",
        description="Record a contribution. Identify by contributor_id OR by provider+provider_id (no registration needed).",
        inputSchema={
            "type": "object",
            "properties": {
                "contributor_id": {"type": "string", "description": "Contributor name (optional if provider+provider_id given)"},
                "provider": {"type": "string", "description": "Identity provider (optional)"},
                "provider_id": {"type": "string", "description": "Identity handle (optional)"},
                "type": {"type": "string", "description": "Contribution type: code, docs, review, design, community, other"},
                "amount_cc": {"type": "number", "description": "CC value (default 1)", "default": 1},
                "idea_id": {"type": "string", "description": "Related idea ID (optional)"},
            },
            "required": ["type"],
        },
    ),
    Tool(
        name="coherence_contributor_ledger",
        description="Get a contributor's CC balance and contribution history.",
        inputSchema={
            "type": "object",
            "properties": {"contributor_id": {"type": "string"}},
            "required": ["contributor_id"],
        },
    ),
    # Status
    Tool(
        name="coherence_status",
        description="Get network health: API status, uptime, federation nodes, idea count.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="coherence_friction_report",
        description="Get friction report — where the pipeline struggles.",
        inputSchema={
            "type": "object",
            "properties": {"window_days": {"type": "number", "default": 30}},
        },
    ),
    # Federation
    Tool(
        name="coherence_list_federation_nodes",
        description="List federated nodes and their capabilities.",
        inputSchema={"type": "object", "properties": {}},
    ),
    # Tasks (Agent Work Protocol)
    Tool(
        name="coherence_list_tasks",
        description="List tasks in the agent work pipeline with optional filters (pending, running, completed, failed, needs_decision).",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: pending, running, completed, failed, needs_decision, timed_out"},
                "task_type": {"type": "string", "description": "Filter by type: spec, test, impl, review, code-review"},
                "limit": {"type": "number", "description": "Max tasks to return (default 20)", "default": 20},
                "offset": {"type": "number", "description": "Pagination offset", "default": 0},
            },
        },
    ),
    Tool(
        name="coherence_get_task",
        description="Get full detail for a single task including direction, context, worker_id, and result/output.",
        inputSchema={
            "type": "object",
            "required": ["task_id"],
            "properties": {
                "task_id": {"type": "string", "description": "The task ID"},
            },
        },
    ),
    Tool(
        name="coherence_task_next",
        description="Claim the highest-priority pending task from the queue. This is the entry point for agents to start working.",
        inputSchema={
            "type": "object",
            "properties": {
                "worker_id": {"type": "string", "description": "Identity of the agent/node claiming the task (defaults to 'mcp-agent')"},
            },
        },
    ),
    Tool(
        name="coherence_task_claim",
        description="Claim a specific task by ID.",
        inputSchema={
            "type": "object",
            "required": ["task_id"],
            "properties": {
                "task_id": {"type": "string", "description": "The task ID"},
                "worker_id": {"type": "string", "description": "Identity of the agent/node (defaults to 'mcp-agent')"},
            },
        },
    ),
    Tool(
        name="coherence_task_report",
        description="Report the result of a claimed task (completed or failed).",
        inputSchema={
            "type": "object",
            "required": ["task_id", "status"],
            "properties": {
                "task_id": {"type": "string", "description": "The task ID"},
                "status": {"type": "string", "description": "Result status: completed or failed"},
                "output": {"type": "string", "description": "The final work product (code, spec text, review notes, etc.)"},
            },
        },
    ),
    Tool(
        name="coherence_task_seed",
        description="Create a new task from an existing idea (e.g. seed a 'spec' task for idea X).",
        inputSchema={
            "type": "object",
            "required": ["idea_id"],
            "properties": {
                "idea_id": {"type": "string", "description": "Target idea ID"},
                "task_type": {"type": "string", "description": "Type of task: spec, test, impl, review (default: spec)", "default": "spec"},
                "direction": {"type": "string", "description": "Optional custom instruction for the task"},
            },
        },
    ),
    Tool(
        name="coherence_task_events",
        description="Get the activity log/event stream for a specific task.",
        inputSchema={
            "type": "object",
            "required": ["task_id"],
            "properties": {
                "task_id": {"type": "string", "description": "The task ID"},
            },
        },
    ),
    # Ideas (Lifecycle)
    Tool(
        name="coherence_create_idea",
        description="Create a new idea in the portfolio. Scoped to a workspace (default: coherence-network).",
        inputSchema={
            "type": "object",
            "required": ["id", "name", "description"],
            "properties": {
                "id": {"type": "string", "description": "Unique idea slug (e.g. 'my-new-feature')"},
                "name": {"type": "string", "description": "Short, descriptive name"},
                "description": {"type": "string", "description": "Detailed vision and value proposition"},
                "potential_value": {"type": "number", "description": "Estimated CC value (0-1000)", "default": 100},
                "estimated_cost": {"type": "number", "description": "Estimated CC cost (0-1000)", "default": 50},
                "parent_idea_id": {"type": "string", "description": "Optional parent idea for hierarchy. Must belong to the same workspace."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "List of tags"},
                "workspace_id": {"type": "string", "description": "Owning workspace slug. Defaults to 'coherence-network'."},
                "pillar": {"type": "string", "description": "Top-level pillar (must be one of the workspace's declared pillars)."},
            },
        },
    ),
    # Workspaces (Tenant primitive)
    Tool(
        name="coherence_list_workspaces",
        description="List all workspaces (tenants). Each workspace owns its own ideas, specs, pillars, and agent personas.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="coherence_get_workspace",
        description="Get a workspace's full manifest (name, description, pillars, visibility).",
        inputSchema={
            "type": "object",
            "required": ["workspace_id"],
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace slug (e.g. 'coherence-network')"},
            },
        },
    ),
    Tool(
        name="coherence_create_workspace",
        description="Create a new workspace (tenant) with its own pillar taxonomy. Use this to onboard a contributor team with isolated ideas/specs/agents.",
        inputSchema={
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string", "description": "Slug: lowercase + hyphens (e.g. 'my-startup')"},
                "name": {"type": "string", "description": "Human name"},
                "description": {"type": "string", "description": "Workspace purpose"},
                "pillars": {"type": "array", "items": {"type": "string"}, "description": "Top-level taxonomy for grouping ideas"},
                "visibility": {"type": "string", "description": "public | federation | private", "default": "public"},
                "owner_contributor_id": {"type": "string", "description": "Contributor who owns this workspace"},
            },
        },
    ),
    Tool(
        name="coherence_get_workspace_pillars",
        description="Get the pillar taxonomy declared by a workspace. Use this before setting `pillar` on a new idea.",
        inputSchema={
            "type": "object",
            "required": ["workspace_id"],
            "properties": {
                "workspace_id": {"type": "string"},
            },
        },
    ),
    Tool(
        name="coherence_update_idea",
        description="Update an existing idea's properties (stage, status, metadata).",
        inputSchema={
            "type": "object",
            "required": ["idea_id"],
            "properties": {
                "idea_id": {"type": "string", "description": "The idea ID"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "stage": {"type": "string", "description": "New stage: draft, proposed, active, completed, archived"},
                "manifestation_status": {"type": "string", "description": "none, spec, implemented, validated"},
                "potential_value": {"type": "number"},
                "estimated_cost": {"type": "number"},
            },
        },
    ),
    # Universal Graph (Navigation & Edges)
    Tool(
        name="coherence_list_edges",
        description="List relationship edges in the universal graph with optional filters.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Edge type: blocks, enables, depends-on, related-to, etc."},
                "from_id": {"type": "string", "description": "Source node ID"},
                "to_id": {"type": "string", "description": "Target node ID"},
                "limit": {"type": "number", "default": 50},
            },
        },
    ),
    Tool(
        name="coherence_get_entity_edges",
        description="Get all incoming and outgoing edges for any entity (Idea, Spec, Contributor, Asset).",
        inputSchema={
            "type": "object",
            "required": ["entity_id"],
            "properties": {
                "entity_id": {"type": "string", "description": "The entity ID"},
                "type": {"type": "string", "description": "Filter by edge type"},
                "direction": {"type": "string", "description": "both, outgoing, incoming", "default": "both"},
            },
        },
    ),
    Tool(
        name="coherence_create_edge",
        description="Create a typed relationship edge between two entities in the graph.",
        inputSchema={
            "type": "object",
            "required": ["from_id", "to_id", "type"],
            "properties": {
                "from_id": {"type": "string", "description": "Source entity ID"},
                "to_id": {"type": "string", "description": "Target entity ID"},
                "type": {"type": "string", "description": "Edge type: blocks, enables, depends-on, contains, transforms, opposes, etc."},
                "strength": {"type": "number", "description": "Edge strength (0.0-1.0)", "default": 1.0},
                "created_by": {"type": "string", "description": "Author/agent creating this edge", "default": "mcp-agent"},
            },
        },
    ),
    # Assets
    Tool(
        name="coherence_list_assets",
        description="List tracked assets (code, docs, endpoints) with pagination.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "number", "default": 100},
                "offset": {"type": "number", "default": 0},
            },
        },
    ),
    Tool(
        name="coherence_get_asset",
        description="Get detail for a specific asset by UUID.",
        inputSchema={
            "type": "object",
            "required": ["asset_id"],
            "properties": {
                "asset_id": {"type": "string", "description": "The asset UUID"},
            },
        },
    ),
    Tool(
        name="coherence_create_asset",
        description="Register a new tracked asset.",
        inputSchema={
            "type": "object",
            "required": ["type", "description"],
            "properties": {
                "type": {"type": "string", "description": "CODE, DOCS, ENDPOINT, etc."},
                "description": {"type": "string", "description": "Asset description"},
                "total_cost": {"type": "number", "description": "Initial CC cost", "default": 0},
            },
        },
    ),
    # News
    Tool(
        name="coherence_get_news_feed",
        description="Latest news items from configured RSS sources with optional POV ranking.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "number", "default": 50},
                "source": {"type": "string", "description": "Filter by source name"},
                "pov": {"type": "string", "description": "Point-of-view lens ID to rank items by affinity"},
                "refresh": {"type": "boolean", "default": False},
            },
        },
    ),
    Tool(
        name="coherence_get_news_resonance",
        description="News items matched to ideas with resonance scores and explanations.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "number", "default": 100},
                "top_n": {"type": "number", "default": 5},
                "refresh": {"type": "boolean", "default": False},
            },
        },
    ),
    Tool(
        name="coherence_list_news_sources",
        description="List all configured news sources.",
        inputSchema={
            "type": "object",
            "properties": {
                "active_only": {"type": "boolean", "default": False},
            },
        },
    ),
    Tool(
        name="coherence_add_news_source",
        description="Add a new news source (RSS).",
        inputSchema={
            "type": "object",
            "required": ["id", "url"],
            "properties": {
                "id": {"type": "string", "description": "Unique source ID"},
                "name": {"type": "string"},
                "url": {"type": "string", "description": "RSS feed URL"},
            },
        },
    ),
    Tool(
        name="coherence_get_trending_news",
        description="Trending keywords extracted from recent news items.",
        inputSchema={
            "type": "object",
            "properties": {
                "top_n": {"type": "number", "default": 20},
                "refresh": {"type": "boolean", "default": False},
            },
        },
    ),
    # Treasury
    Tool(
        name="coherence_get_treasury_info",
        description="Treasury wallet addresses, conversion rates, and total CC balance.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="coherence_record_deposit",
        description="Record a crypto deposit and convert to CC for a contributor.",
        inputSchema={
            "type": "object",
            "required": ["contributor_id", "asset", "amount", "tx_hash"],
            "properties": {
                "contributor_id": {"type": "string"},
                "asset": {"type": "string", "description": "eth or btc"},
                "amount": {"type": "number"},
                "tx_hash": {"type": "string"},
                "wallet_address": {"type": "string"},
            },
        },
    ),
    Tool(
        name="coherence_get_deposit_history",
        description="Get deposit history for a contributor.",
        inputSchema={
            "type": "object",
            "required": ["contributor_id"],
            "properties": {
                "contributor_id": {"type": "string"},
            },
        },
    ),
    # Governance
    Tool(
        name="coherence_list_change_requests",
        description="List open governance change proposals.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "number", "default": 200},
            },
        },
    ),
    Tool(
        name="coherence_get_change_request",
        description="Get detail for a specific change proposal.",
        inputSchema={
            "type": "object",
            "required": ["change_request_id"],
            "properties": {
                "change_request_id": {"type": "string"},
            },
        },
    ),
    Tool(
        name="coherence_vote_governance",
        description="Cast a vote on a governance change proposal.",
        inputSchema={
            "type": "object",
            "required": ["change_request_id", "voter_id", "vote"],
            "properties": {
                "change_request_id": {"type": "string"},
                "voter_id": {"type": "string"},
                "vote": {"type": "string", "description": "yes or no"},
                "rationale": {"type": "string"},
            },
        },
    ),
    Tool(
        name="coherence_propose_governance",
        description="Create a new governance change proposal.",
        inputSchema={
            "type": "object",
            "required": ["title", "description", "proposer_id"],
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "proposer_id": {"type": "string"},
                "idea_id": {"type": "string"},
            },
        },
    ),
    # DIF (Decentralized Identity Foundation)
    Tool(
        name="coherence_get_dif_stats",
        description="DIF accuracy statistics — true/false positive rates, accuracy by language.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="coherence_get_recent_dif",
        description="Recent DIF verification entries with scores and outcomes.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "number", "default": 20},
            },
        },
    ),
    # Peers (Contributor Discovery)
    Tool(
        name="coherence_get_resonant_peers",
        description="Find contributors with similar interests (structural resonance) to a specific contributor.",
        inputSchema={
            "type": "object",
            "required": ["contributor_id"],
            "properties": {
                "contributor_id": {"type": "string"},
                "limit": {"type": "number", "default": 20},
            },
        },
    ),
    Tool(
        name="coherence_get_nearby_peers",
        description="Find contributors physically close to a specific contributor.",
        inputSchema={
            "type": "object",
            "required": ["contributor_id"],
            "properties": {
                "contributor_id": {"type": "string"},
                "radius_km": {"type": "number", "default": 100.0},
                "limit": {"type": "number", "default": 20},
            },
        },
    ),
    # Blueprints (Project Templates)
    Tool(
        name="coherence_list_blueprints",
        description="List available project roadmap blueprints (templates).",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="coherence_apply_blueprint",
        description="Seed a full roadmap of ideas and edges from a blueprint template.",
        inputSchema={
            "type": "object",
            "required": ["blueprint_id"],
            "properties": {
                "blueprint_id": {"type": "string"},
                "prefix": {"type": "string", "description": "Optional ID prefix for created ideas"},
            },
        },
    ),
    Tool(
        name="coherence_read_file",
        description="Read raw file content from the repository (specs, docs, etc.) via direct link.",
        inputSchema={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "description": "Relative path from repo root (e.g. 'specs/169-procedural-memory.md')"},
            },
        },
    ),
    # Concepts (Living Codex ontology)
    Tool(
        name="coherence_list_concepts",
        description="Browse the Living Codex ontology — 184 universal concepts with typed relationships and 53 axes.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "number", "description": "Max concepts to return (default 50, max 500)", "default": 50},
                "offset": {"type": "number", "description": "Pagination offset", "default": 0},
                "search": {"type": "string", "description": "Search query to filter concepts"},
            },
        },
    ),
    Tool(
        name="coherence_get_concept",
        description="Get full details for a single concept from the Living Codex ontology.",
        inputSchema={
            "type": "object",
            "required": ["concept_id"],
            "properties": {
                "concept_id": {"type": "string", "description": "Concept ID (e.g. 'activity', 'knowledge', 'resonance')"},
                "include_edges": {"type": "boolean", "description": "Include typed relationship edges", "default": False},
            },
        },
    ),
    Tool(
        name="coherence_link_concepts",
        description="Create a typed relationship edge between two concepts in the Living Codex ontology.",
        inputSchema={
            "type": "object",
            "required": ["from_id", "relationship_type", "to_id"],
            "properties": {
                "from_id": {"type": "string", "description": "Source concept ID"},
                "relationship_type": {"type": "string", "description": "Relationship type (transforms, contains, enables, opposes, ...)"},
                "to_id": {"type": "string", "description": "Target concept ID"},
                "created_by": {"type": "string", "description": "Author/agent creating this edge", "default": "mcp"},
            },
        },
    ),
    # Spec CRUD
    Tool(
        name="coherence_create_spec",
        description="Create a new spec in the registry. Requires spec_id (slug), title, summary, and idea_id.",
        inputSchema={
            "type": "object",
            "required": ["spec_id", "title", "summary"],
            "properties": {
                "spec_id": {"type": "string", "description": "Unique spec slug (e.g. '170-my-feature')"},
                "title": {"type": "string", "description": "Spec title"},
                "summary": {"type": "string", "description": "Spec summary"},
                "idea_id": {"type": "string", "description": "Parent idea ID"},
                "potential_value": {"type": "number", "description": "Estimated CC value", "default": 0},
                "estimated_cost": {"type": "number", "description": "Estimated CC cost", "default": 0},
                "content_path": {"type": "string", "description": "Path to spec content file"},
                "implementation_summary": {"type": "string", "description": "Implementation summary text"},
            },
        },
    ),
    Tool(
        name="coherence_update_spec",
        description="Update an existing spec's properties (title, summary, value, cost, implementation summary).",
        inputSchema={
            "type": "object",
            "required": ["spec_id"],
            "properties": {
                "spec_id": {"type": "string", "description": "The spec ID"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "potential_value": {"type": "number"},
                "estimated_cost": {"type": "number"},
                "actual_value": {"type": "number"},
                "actual_cost": {"type": "number"},
                "idea_id": {"type": "string"},
                "implementation_summary": {"type": "string"},
                "process_summary": {"type": "string"},
                "content_path": {"type": "string"},
            },
        },
    ),
    # Workflow
    Tool(
        name="coherence_advance_idea",
        description="Check prerequisites and advance an idea to its next lifecycle stage. Returns current state, prerequisite check results, and whether advancement succeeded.",
        inputSchema={
            "type": "object",
            "required": ["idea_id"],
            "properties": {
                "idea_id": {"type": "string", "description": "The idea ID to advance"},
                "force": {"type": "boolean", "description": "Skip prerequisite checks", "default": False},
            },
        },
    ),
    Tool(
        name="coherence_trace",
        description="Trace the full lineage of any entity — from idea to specs to tasks to source files. Provides navigation breadcrumbs across the entire system.",
        inputSchema={
            "type": "object",
            "required": ["entity_id"],
            "properties": {
                "entity_id": {"type": "string", "description": "An idea slug, spec slug, or task ID"},
                "entity_type": {"type": "string", "description": "idea, spec, or task", "default": "idea"},
            },
        },
    ),
]

TOOL_MAP: dict[str, Tool] = {t.name: t for t in TOOLS}

# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def dispatch(name: str, args: dict[str, Any]) -> Any:
    match name:
        # Ideas
        case "coherence_list_ideas":
            if args.get("search"):
                return api_get("/api/ideas/cards", {"search": args["search"], "limit": args.get("limit", 20)})
            params = {"limit": args.get("limit", 20)}
            if args.get("workspace_id"):
                params["workspace_id"] = args["workspace_id"]
            if args.get("pillar"):
                params["pillar"] = args["pillar"]
            if args.get("curated_only"):
                params["curated_only"] = "true"
            return api_get("/api/ideas", params)
        case "coherence_get_idea":
            return api_get(f"/api/ideas/{args['idea_id']}")
        case "coherence_idea_progress":
            return api_get(f"/api/ideas/{args['idea_id']}/progress")
        case "coherence_select_idea":
            return api_post("/api/ideas/select", {"temperature": args.get("temperature", 0.5)})
        case "coherence_showcase":
            return api_get("/api/ideas/showcase")
        case "coherence_resonance":
            return api_get("/api/ideas/resonance")
        # Specs
        case "coherence_list_specs":
            if args.get("search"):
                return api_get("/api/spec-registry/cards", {"search": args["search"], "limit": args.get("limit", 20)})
            return api_get("/api/spec-registry", {"limit": args.get("limit", 20)})
        case "coherence_get_spec":
            return api_get(f"/api/spec-registry/{args['spec_id']}")
        # Lineage
        case "coherence_list_lineage":
            return api_get("/api/value-lineage/links", {"limit": args.get("limit", 20)})
        case "coherence_lineage_valuation":
            return api_get(f"/api/value-lineage/links/{args['lineage_id']}/valuation")
        # Identity
        case "coherence_list_providers":
            return api_get("/api/identity/providers")
        case "coherence_link_identity":
            return api_post("/api/identity/link", {
                "contributor_id": args["contributor_id"],
                "provider": args["provider"],
                "provider_id": args["provider_id"],
                "display_name": args["provider_id"],
            })
        case "coherence_lookup_identity":
            from urllib.parse import quote
            return api_get(f"/api/identity/lookup/{quote(args['provider'])}/{quote(args['provider_id'])}")
        case "coherence_get_identities":
            from urllib.parse import quote
            return api_get(f"/api/identity/{quote(args['contributor_id'])}")
        # Contributions
        case "coherence_record_contribution":
            return api_post("/api/contributions/record", {
                k: v for k, v in {
                    "contributor_id": args.get("contributor_id"),
                    "provider": args.get("provider"),
                    "provider_id": args.get("provider_id"),
                    "type": args["type"],
                    "amount_cc": args.get("amount_cc", 1),
                    "idea_id": args.get("idea_id"),
                }.items() if v is not None
            })
        case "coherence_contributor_ledger":
            from urllib.parse import quote
            return api_get(f"/api/contributions/ledger/{quote(args['contributor_id'])}")
        # Status
        case "coherence_status":
            health = api_get("/api/health")
            count = api_get("/api/ideas/count")
            nodes = api_get("/api/federation/nodes")
            return {
                "health": health,
                "ideas": count,
                "federation_nodes": len(nodes) if isinstance(nodes, list) else 0,
            }
        case "coherence_friction_report":
            return api_get("/api/friction/report", {"window_days": args.get("window_days", 30)})
        # Federation
        case "coherence_list_federation_nodes":
            nodes = api_get("/api/federation/nodes")
            caps = api_get("/api/federation/nodes/capabilities")
            return {"nodes": nodes, "capabilities": caps}
        # Tasks
        case "coherence_list_tasks":
            return api_get("/api/agent/tasks", {
                "status": args.get("status"),
                "task_type": args.get("task_type"),
                "limit": args.get("limit", 20),
                "offset": args.get("offset", 0),
            })
        case "coherence_get_task":
            return api_get(f"/api/agent/tasks/{args['task_id']}")
        case "coherence_task_next":
            # Claim next available pending task
            data = api_get("/api/agent/tasks", {"status": "pending", "limit": 1})
            tasks = data.get("tasks", []) if isinstance(data, dict) else []
            if not tasks:
                return {"error": "No pending tasks available"}
            task_id = tasks[0]["id"]
            return api_patch(f"/api/agent/tasks/{task_id}", {
                "status": "running",
                "worker_id": args.get("worker_id", "mcp-agent"),
            })
        case "coherence_task_claim":
            return api_patch(f"/api/agent/tasks/{args['task_id']}", {
                "status": "running",
                "worker_id": args.get("worker_id", "mcp-agent"),
            })
        case "coherence_task_report":
            return api_patch(f"/api/agent/tasks/{args['task_id']}", {
                "status": args["status"],
                "output": args.get("output", f"Task {args['status']} via mcp-agent"),
            })
        case "coherence_task_seed":
            idea_id = args["idea_id"]
            # Fetch idea for name if not provided in direction
            idea = api_get(f"/api/ideas/{idea_id}")
            idea_name = idea.get("name", "Unknown Idea") if isinstance(idea, dict) else "Unknown Idea"
            task_type = args.get("task_type", "spec")
            direction = args.get("direction") or f"{task_type} for '{idea_name}' ({idea_id})"
            return api_post("/api/agent/tasks", {
                "task_type": task_type,
                "direction": direction,
                "context": {
                    "idea_id": idea_id,
                    "idea_name": idea_name,
                    "seeded_by": "mcp-agent",
                },
            })
        case "coherence_task_events":
            return api_get(f"/api/agent/tasks/{args['task_id']}/stream")
        # Ideas
        case "coherence_create_idea":
            return api_post("/api/ideas", {
                "id": args["id"],
                "name": args["name"],
                "description": args["description"],
                "potential_value": args.get("potential_value", 100),
                "estimated_cost": args.get("estimated_cost", 50),
                "parent_idea_id": args.get("parent_idea_id"),
                "tags": args.get("tags"),
                "workspace_id": args.get("workspace_id"),
                "pillar": args.get("pillar"),
            })
        # Workspaces
        case "coherence_list_workspaces":
            return api_get("/api/workspaces")
        case "coherence_get_workspace":
            return api_get(f"/api/workspaces/{args['workspace_id']}")
        case "coherence_create_workspace":
            return api_post("/api/workspaces", {
                "id": args["id"],
                "name": args["name"],
                "description": args.get("description", ""),
                "pillars": args.get("pillars", []),
                "visibility": args.get("visibility", "public"),
                "owner_contributor_id": args.get("owner_contributor_id"),
            })
        case "coherence_get_workspace_pillars":
            return api_get(f"/api/workspaces/{args['workspace_id']}/pillars")
        case "coherence_update_idea":
            return api_patch(f"/api/ideas/{args['idea_id']}", {
                "name": args.get("name"),
                "description": args.get("description"),
                "stage": args.get("stage"),
                "manifestation_status": args.get("manifestation_status"),
                "potential_value": args.get("potential_value"),
                "estimated_cost": args.get("estimated_cost"),
            })
        # Graph / Edges
        case "coherence_list_edges":
            return api_get("/api/edges", {
                "type": args.get("type"),
                "from_id": args.get("from_id"),
                "to_id": args.get("to_id"),
                "limit": args.get("limit", 50),
            })
        case "coherence_get_entity_edges":
            return api_get(f"/api/entities/{args['entity_id']}/edges", {
                "type": args.get("type"),
                "direction": args.get("direction", "both"),
            })
        case "coherence_create_edge":
            return api_post("/api/edges", {
                "from_id": args["from_id"],
                "to_id": args["to_id"],
                "type": args["type"],
                "strength": args.get("strength", 1.0),
                "created_by": args.get("created_by", "mcp-agent"),
            })
        # Assets
        case "coherence_list_assets":
            return api_get("/api/assets", {"limit": args.get("limit", 100), "offset": args.get("offset", 0)})
        case "coherence_get_asset":
            return api_get(f"/api/assets/{args['asset_id']}")
        case "coherence_create_asset":
            return api_post("/api/assets", {
                "type": args["type"],
                "description": args["description"],
                "total_cost": args.get("total_cost", 0),
            })
        # News
        case "coherence_get_news_feed":
            return api_get("/api/news/feed", {
                "limit": args.get("limit", 50),
                "source": args.get("source"),
                "pov": args.get("pov"),
                "refresh": args.get("refresh", False),
            })
        case "coherence_get_news_resonance":
            return api_get("/api/news/resonance", {
                "limit": args.get("limit", 100),
                "top_n": args.get("top_n", 5),
                "refresh": args.get("refresh", False),
            })
        case "coherence_list_news_sources":
            return api_get("/api/news/sources", {"active_only": args.get("active_only", False)})
        case "coherence_add_news_source":
            return api_post("/api/news/sources", {
                "id": args["id"],
                "url": args["url"],
                "name": args.get("name"),
            })
        case "coherence_get_trending_news":
            return api_get("/api/news/trending", {
                "top_n": args.get("top_n", 20),
                "refresh": args.get("refresh", False),
            })
        # Treasury
        case "coherence_get_treasury_info":
            return api_get("/api/treasury")
        case "coherence_record_deposit":
            return api_post("/api/treasury/deposit", {
                "contributor_id": args["contributor_id"],
                "asset": args["asset"],
                "amount": args["amount"],
                "tx_hash": args["tx_hash"],
                "wallet_address": args.get("wallet_address"),
            })
        case "coherence_get_deposit_history":
            return api_get(f"/api/treasury/deposits/{args['contributor_id']}")
        # Governance
        case "coherence_list_change_requests":
            return api_get("/api/governance/change-requests", {"limit": args.get("limit", 200)})
        case "coherence_get_change_request":
            return api_get(f"/api/governance/change-requests/{args['change_request_id']}")
        case "coherence_vote_governance":
            return api_post(f"/api/governance/change-requests/{args['change_request_id']}/votes", {
                "voter_id": args["voter_id"],
                "vote": args["vote"],
                "rationale": args.get("rationale"),
            })
        case "coherence_propose_governance":
            return api_post("/api/governance/change-requests", {
                "title": args["title"],
                "description": args["description"],
                "proposer_id": args["proposer_id"],
                "idea_id": args.get("idea_id"),
            })
        # DIF
        case "coherence_get_dif_stats":
            return api_get("/api/dif/stats")
        case "coherence_get_recent_dif":
            return api_get("/api/dif/recent", {"limit": args.get("limit", 20)})
        # Peers
        case "coherence_get_resonant_peers":
            return api_get("/api/peers/resonant", {"contributor_id": args["contributor_id"], "limit": args.get("limit", 20)})
        case "coherence_get_nearby_peers":
            return api_get("/api/peers/nearby", {
                "contributor_id": args["contributor_id"],
                "radius_km": args.get("radius_km", 100.0),
                "limit": args.get("limit", 20)
            })
        # Blueprints
        case "coherence_list_blueprints":
            return api_get("/api/blueprints")
        case "coherence_apply_blueprint":
            return api_post(f"/api/blueprints/{args['blueprint_id']}/apply", {"prefix": args.get("prefix", "")})
        case "coherence_read_file":
            return api_get("/api/content/file", {"path": args["path"]})
        # Concepts
        case "coherence_list_concepts":
            if args.get("search"):
                return api_get("/api/concepts/search", {"q": args["search"], "limit": args.get("limit", 20)})
            return api_get("/api/concepts", {"limit": args.get("limit", 50), "offset": args.get("offset", 0)})
        case "coherence_get_concept":
            concept = api_get(f"/api/concepts/{args['concept_id']}")
            if args.get("include_edges"):
                edges = api_get(f"/api/concepts/{args['concept_id']}/edges")
                if isinstance(concept, dict):
                    concept["edges"] = edges
            return concept
        case "coherence_link_concepts":
            return api_post(f"/api/concepts/{args['from_id']}/edges", {
                "from_id": args["from_id"],
                "to_id": args["to_id"],
                "relationship_type": args["relationship_type"],
                "created_by": args.get("created_by", "mcp"),
            })
        # Spec CRUD
        case "coherence_create_spec":
            return api_post("/api/spec-registry", {
                "spec_id": args["spec_id"],
                "title": args["title"],
                "summary": args["summary"],
                "idea_id": args.get("idea_id"),
                "potential_value": args.get("potential_value", 0),
                "estimated_cost": args.get("estimated_cost", 0),
                "content_path": args.get("content_path"),
                "implementation_summary": args.get("implementation_summary"),
            })
        case "coherence_update_spec":
            body = {
                k: v for k, v in {
                    "title": args.get("title"),
                    "summary": args.get("summary"),
                    "potential_value": args.get("potential_value"),
                    "estimated_cost": args.get("estimated_cost"),
                    "actual_value": args.get("actual_value"),
                    "actual_cost": args.get("actual_cost"),
                    "idea_id": args.get("idea_id"),
                    "implementation_summary": args.get("implementation_summary"),
                    "process_summary": args.get("process_summary"),
                    "content_path": args.get("content_path"),
                }.items() if v is not None
            }
            return api_patch(f"/api/spec-registry/{args['spec_id']}", body)
        # Workflow
        case "coherence_advance_idea":
            idea_id = args["idea_id"]
            force = args.get("force", False)
            idea = api_get(f"/api/ideas/{idea_id}")
            if isinstance(idea, dict) and "error" in idea:
                return idea
            progress = api_get(f"/api/ideas/{idea_id}/progress")
            current_stage = idea.get("stage", "none") if isinstance(idea, dict) else "none"
            stage_order = ["none", "specced", "implementing", "testing", "reviewing", "complete"]
            idx = stage_order.index(current_stage) if current_stage in stage_order else 0
            if idx >= len(stage_order) - 1:
                return {"idea_id": idea_id, "current_stage": current_stage, "next_stage": None,
                        "prerequisites_met": False, "prerequisite_details": {"reason": "already at final stage"},
                        "advanced": False, "result": None}
            next_stage = stage_order[idx + 1]
            # Check prerequisites from progress tasks
            tasks_by_phase = progress.get("tasks_by_phase", {}) if isinstance(progress, dict) else {}
            prereq_checks = {
                "specced": ("spec", "at least 1 spec task completed"),
                "implementing": ("impl", "at least 1 impl task exists"),
                "testing": ("impl", "at least 1 impl task completed"),
                "reviewing": ("test", "at least 1 test task completed"),
                "complete": ("review", "at least 1 review task completed"),
            }
            prereqs_met = True
            prereq_details: dict[str, Any] = {}
            if next_stage in prereq_checks:
                phase_key, description = prereq_checks[next_stage]
                phase_tasks = tasks_by_phase.get(phase_key, [])
                if next_stage == "implementing":
                    prereqs_met = len(phase_tasks) > 0
                    prereq_details = {"check": description, "phase": phase_key, "task_count": len(phase_tasks)}
                else:
                    completed = [t for t in phase_tasks if isinstance(t, dict) and t.get("status") == "completed"]
                    prereqs_met = len(completed) > 0
                    prereq_details = {"check": description, "phase": phase_key,
                                      "completed_count": len(completed), "total_count": len(phase_tasks)}
            advanced = False
            result = None
            if prereqs_met or force:
                result = api_patch(f"/api/ideas/{idea_id}", {"stage": next_stage})
                advanced = not (isinstance(result, dict) and "error" in result)
            return {"idea_id": idea_id, "current_stage": current_stage, "next_stage": next_stage,
                    "prerequisites_met": prereqs_met, "prerequisite_details": prereq_details,
                    "advanced": advanced, "result": result}
        case "coherence_trace":
            entity_id = args["entity_id"]
            entity_type = args.get("entity_type", "idea")
            if entity_type == "idea":
                idea = api_get(f"/api/ideas/{entity_id}")
                progress = api_get(f"/api/ideas/{entity_id}/progress")
                specs = api_get("/api/spec-registry/cards", {"q": entity_id, "limit": 50})
                all_tasks = api_get("/api/agent/tasks", {"status": None, "limit": 50})
                task_list = all_tasks.get("tasks", []) if isinstance(all_tasks, dict) else []
                idea_tasks = [t for t in task_list if isinstance(t, dict)
                              and isinstance(t.get("context"), dict) and t["context"].get("idea_id") == entity_id]
                spec_items = specs if isinstance(specs, list) else specs.get("items", []) if isinstance(specs, dict) else []
                spec_ids = [s.get("spec_id", s.get("id", "")) for s in spec_items if isinstance(s, dict)]
                return {"entity_type": "idea", "idea": idea, "progress": progress,
                        "specs": spec_items, "tasks": idea_tasks,
                        "navigation": {"idea_file": f"ideas/{entity_id}.md",
                                       "spec_files": [f"specs/{s}.md" for s in spec_ids],
                                       "api": f"/api/ideas/{entity_id}",
                                       "cli": f"cc idea {entity_id}"}}
            elif entity_type == "spec":
                spec = api_get(f"/api/spec-registry/{entity_id}")
                spec_file = api_get("/api/content/file", {"path": f"specs/{entity_id}.md"})
                idea_id = spec.get("idea_id") if isinstance(spec, dict) else None
                parent_idea = api_get(f"/api/ideas/{idea_id}") if idea_id else None
                nav: dict[str, Any] = {"spec_file": f"specs/{entity_id}.md",
                                       "api": f"/api/spec-registry/{entity_id}",
                                       "cli": f"cc spec {entity_id}"}
                if idea_id:
                    nav["idea_file"] = f"ideas/{idea_id}.md"
                return {"entity_type": "spec", "spec": spec, "spec_file_content": spec_file,
                        "parent_idea": parent_idea, "navigation": nav}
            elif entity_type == "task":
                task = api_get(f"/api/agent/tasks/{entity_id}")
                events = api_get(f"/api/agent/tasks/{entity_id}/stream")
                context = task.get("context", {}) if isinstance(task, dict) else {}
                idea_id = context.get("idea_id") if isinstance(context, dict) else None
                parent_idea = api_get(f"/api/ideas/{idea_id}") if idea_id else None
                return {"entity_type": "task", "task": task, "events": events,
                        "parent_idea": parent_idea,
                        "navigation": {"api": f"/api/agent/tasks/{entity_id}",
                                       "cli": f"cc task {entity_id}"}}
            else:
                return {"error": f"Unknown entity_type: {entity_type}. Use 'idea', 'spec', or 'task'."}
        case _:
            return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

server = Server("coherence-network")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    args = arguments or {}
    try:
        result = dispatch(name, args)
        text = json.dumps(result, default=str)
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        text = json.dumps({"error": str(exc)})
    return [TextContent(type="text", text=text)]


async def run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
