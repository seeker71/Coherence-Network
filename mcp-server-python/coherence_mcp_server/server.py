"""Coherence Network MCP server — Python implementation.

Exposes the Coherence Network API as 22 typed MCP tools.
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
    # Governance
    Tool(
        name="coherence_list_change_requests",
        description="List governance change requests.",
        inputSchema={"type": "object", "properties": {}},
    ),
    # Federation
    Tool(
        name="coherence_list_federation_nodes",
        description="List federated nodes and their capabilities.",
        inputSchema={"type": "object", "properties": {}},
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
            return api_get("/api/ideas", {"limit": args.get("limit", 20)})
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
        # Governance
        case "coherence_list_change_requests":
            return api_get("/api/governance/change-requests")
        # Federation
        case "coherence_list_federation_nodes":
            nodes = api_get("/api/federation/nodes")
            caps = api_get("/api/federation/nodes/capabilities")
            return {"nodes": nodes, "capabilities": caps}
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
