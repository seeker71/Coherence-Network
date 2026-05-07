"""No-auth remote MCP endpoint for connector clients.

The packaged MCP server remains the full stdio implementation. This router
provides a small streamable-HTTP compatible JSON-RPC surface for hosted clients
that need to discover and call read-only tools without an OAuth registration.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request, Response

from app.config_loader import get_str
from app.services.mcp_tool_registry import TOOL_MAP, TOOLS

router = APIRouter()

SERVER_NAME = "coherence-network"
SERVER_VERSION = "0.5.1"
READ_ONLY_TOOL_NAMES = {
    "browse_ideas",
    "get_idea",
    "browse_specs",
    "get_resonance_feed",
    "get_strategies",
    "get_provider_stats",
    "list_open_changes",
}


def _web_base_url() -> str:
    return get_str("agent_providers", "web_ui_base_url", default="https://coherencycoin.com").rstrip("/")


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _tool(name: str, description: str, input_schema: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "description": description, "inputSchema": input_schema}


SEARCH_TOOL = _tool(
    "search",
    "Search public Coherence Network ideas and specs. No authentication required.",
    {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"],
    },
)

FETCH_TOOL = _tool(
    "fetch",
    "Fetch one public Coherence Network search result by id. No authentication required.",
    {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Result id from search"}},
        "required": ["id"],
    },
)


def _remote_tools() -> list[dict[str, Any]]:
    tools = [SEARCH_TOOL, FETCH_TOOL]
    for item in TOOLS:
        if item["name"] not in READ_ONLY_TOOL_NAMES:
            continue
        tools.append(_tool(item["name"], item["description"], item["input_schema"]))
    return tools


def _contains_query(row: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(str(row.get(key, "")) for key in ("id", "idea_id", "spec_id", "name", "title", "description", "summary"))
    return query.lower() in haystack.lower()


def _search(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services import idea_service, spec_registry_service

    query = str(arguments.get("query", "")).strip()
    web_base = _web_base_url()
    results: list[dict[str, str]] = []

    ideas = _json_safe(idea_service.list_ideas(limit=50, sort_method="free_energy"))
    for idea in ideas.get("items", []) if isinstance(ideas, dict) else ideas:
        if not isinstance(idea, dict) or not _contains_query(idea, query):
            continue
        idea_id = str(idea.get("id") or idea.get("idea_id") or "")
        if not idea_id:
            continue
        results.append(
            {
                "id": f"idea:{idea_id}",
                "title": str(idea.get("name") or idea_id),
                "url": f"{web_base}/ideas/{idea_id}",
                "text": str(idea.get("description") or ""),
            }
        )

    specs = _json_safe(spec_registry_service.list_specs(limit=50))
    for spec in specs:
        if not isinstance(spec, dict) or not _contains_query(spec, query):
            continue
        spec_id = str(spec.get("spec_id") or "")
        if not spec_id:
            continue
        results.append(
            {
                "id": f"spec:{spec_id}",
                "title": str(spec.get("title") or spec_id),
                "url": f"{web_base}/specs/{spec_id}",
                "text": str(spec.get("summary") or ""),
            }
        )

    return {"results": results[:10]}


def _fetch(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services import idea_service, spec_registry_service

    raw_id = str(arguments.get("id", "")).strip()
    web_base = _web_base_url()
    if raw_id.startswith("idea:"):
        idea_id = raw_id.removeprefix("idea:")
        idea = idea_service.get_idea(idea_id)
        if idea is None:
            return {"error": f"Idea '{idea_id}' not found"}
        data = _json_safe(idea)
        return {
            "id": raw_id,
            "title": str(data.get("name") or idea_id),
            "url": f"{web_base}/ideas/{idea_id}",
            "text": json.dumps(data, default=str),
        }
    if raw_id.startswith("spec:"):
        spec_id = raw_id.removeprefix("spec:")
        spec = spec_registry_service.get_spec(spec_id)
        if spec is None:
            return {"error": f"Spec '{spec_id}' not found"}
        data = _json_safe(spec)
        return {
            "id": raw_id,
            "title": str(data.get("title") or spec_id),
            "url": f"{web_base}/specs/{spec_id}",
            "text": json.dumps(data, default=str),
        }
    return {"error": "Unknown result id. Expected an id starting with 'idea:' or 'spec:'."}


def _content_result(result: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(_json_safe(result), default=str)}],
        "isError": is_error,
    }


def _jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _handle_jsonrpc(payload: dict[str, Any]) -> dict[str, Any] | None:
    method = str(payload.get("method", ""))
    request_id = payload.get("id")
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}

    if request_id is None:
        return None
    if method == "initialize":
        protocol_version = str(params.get("protocolVersion") or "2024-11-05")
        return _jsonrpc_result(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": "Public read-only Coherence Network MCP endpoint. Authentication type: none.",
            },
        )
    if method == "tools/list":
        return _jsonrpc_result(request_id, {"tools": _remote_tools()})
    if method == "tools/call":
        name = str(params.get("name", ""))
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if name == "search":
            return _jsonrpc_result(request_id, _content_result(_search(arguments)))
        if name == "fetch":
            return _jsonrpc_result(request_id, _content_result(_fetch(arguments)))
        tool_def = TOOL_MAP.get(name)
        if tool_def is None or name not in READ_ONLY_TOOL_NAMES:
            return _jsonrpc_result(request_id, _content_result({"error": f"Tool '{name}' is not available on the no-auth remote MCP endpoint."}, is_error=True))
        try:
            return _jsonrpc_result(request_id, _content_result(tool_def["handler"](arguments)))
        except Exception as exc:
            return _jsonrpc_result(request_id, _content_result({"error": str(exc)}, is_error=True))
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


@router.get("/mcp", include_in_schema=False)
@router.get("/api/mcp", include_in_schema=False)
async def mcp_info() -> dict[str, Any]:
    return {
        "name": SERVER_NAME,
        "version": SERVER_VERSION,
        "transport": "streamable-http",
        "auth_required": False,
        "auth_schemes": ["none"],
        "tools": [tool["name"] for tool in _remote_tools()],
    }


@router.post("/mcp", include_in_schema=False)
@router.post("/api/mcp", include_in_schema=False)
async def mcp_jsonrpc(request: Request, response: Response) -> Any:
    response.headers["MCP-Protocol-Version"] = "2024-11-05"
    try:
        payload = await request.json()
    except Exception:
        return _jsonrpc_error(None, -32700, "Parse error")

    if isinstance(payload, list):
        replies = [_handle_jsonrpc(item) for item in payload if isinstance(item, dict)]
        return [reply for reply in replies if reply is not None]
    if not isinstance(payload, dict):
        return _jsonrpc_error(None, -32600, "Invalid Request")

    reply = _handle_jsonrpc(payload)
    if reply is None:
        response.status_code = 202
        return None
    return reply
