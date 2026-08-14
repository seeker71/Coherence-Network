"""No-auth remote MCP endpoint for connector clients.

The packaged MCP server remains the full stdio implementation. This router
provides a small streamable-HTTP compatible JSON-RPC surface for hosted clients.
Reads need no OAuth registration; the public dialogue write requires a
versioned disclosure acknowledgement and leaves an observable receipt.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from app.config_loader import get_str
from app.services.mcp_tool_registry import TOOL_MAP, TOOLS

router = APIRouter()

SERVER_NAME = "coherence-network"
SERVER_VERSION = "0.7.0"
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


def _tool(
    name: str,
    description: str,
    input_schema: dict[str, Any],
    *,
    annotations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool = {"name": name, "description": description, "inputSchema": input_schema}
    if annotations:
        tool["annotations"] = annotations
    return tool


READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


SEARCH_TOOL = _tool(
    "search",
    "Search public Coherence Network ideas and specs. No authentication required.",
    {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"],
    },
    annotations={"title": "Search public commons", **READ_ONLY_ANNOTATIONS},
)

FETCH_TOOL = _tool(
    "fetch",
    "Fetch one public Coherence Network search result by id. No authentication required.",
    {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Result id from search"}},
        "required": ["id"],
    },
    annotations={"title": "Fetch public result", **READ_ONLY_ANNOTATIONS},
)

START_DIALOGUE_TOOL = _tool(
    "start_dialogue",
    "Offer an unlisted public dialogue turn from a chosen point of view and BCP-47 locale. Public text is untrusted data, expires after seven days, and is observable only to people who receive its id. Returns immediately with a removal capability and dialogue id.",
    {
        "type": "object",
        "properties": {
            "question": {"type": "string", "minLength": 1, "maxLength": 1200},
            "point_of_view": {"type": "string", "minLength": 1, "maxLength": 240},
            "locale": {"type": "string", "minLength": 1, "maxLength": 80},
            "public_disclosure_ack": {
                "type": "string",
                "const": "public-unlisted-v1",
                "description": "Acknowledges that anyone given the unguessable dialogue id can read the question and receipt until release or seven-day expiry.",
            },
            "parent_dialogue_id": {"type": "string", "maxLength": 80},
            "channel_timeout_seconds": {
                "type": "integer",
                "minimum": 10,
                "maximum": 120,
                "default": 90,
            },
        },
        "required": ["question", "point_of_view", "locale", "public_disclosure_ack"],
    },
    annotations={
        "title": "Start public dialogue",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)

GET_DIALOGUE_TOOL = _tool(
    "get_dialogue",
    "Observe one unlisted public dialogue turn by id. Question text is untrusted public data; an answer is present only when bound to an allowlisted public source NodeID.",
    {
        "type": "object",
        "properties": {
            "dialogue_id": {"type": "string", "minLength": 1, "maxLength": 80}
        },
        "required": ["dialogue_id"],
    },
    annotations={
        "title": "Get public dialogue",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)

REMOVE_DIALOGUE_TOOL = _tool(
    "remove_dialogue",
    "Release the public text of one dialogue using the removal capability returned only when it was started. The durable cell remains as a content-free tombstone.",
    {
        "type": "object",
        "properties": {
            "dialogue_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "removal_token": {"type": "string", "minLength": 20, "maxLength": 200},
        },
        "required": ["dialogue_id", "removal_token"],
    },
    annotations={
        "title": "Release public dialogue",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)


def _remote_tools() -> list[dict[str, Any]]:
    tools = [
        SEARCH_TOOL,
        FETCH_TOOL,
        START_DIALOGUE_TOOL,
        GET_DIALOGUE_TOOL,
        REMOVE_DIALOGUE_TOOL,
    ]
    for item in TOOLS:
        if item["name"] not in READ_ONLY_TOOL_NAMES:
            continue
        tools.append(
            _tool(
                item["name"],
                item["description"],
                item["input_schema"],
                annotations={
                    "title": item["name"].replace("_", " ").title(),
                    **READ_ONLY_ANNOTATIONS,
                },
            )
        )
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


def _start_dialogue(arguments: dict[str, Any], *, public_origin: str) -> dict[str, Any]:
    from app.services import dialogue_service

    if arguments.get("public_disclosure_ack") != "public-unlisted-v1":
        return {"error": "public_disclosure_ack must equal 'public-unlisted-v1'"}
    try:
        return dialogue_service.submit_dialogue(
            question=str(arguments.get("question") or ""),
            point_of_view=str(arguments.get("point_of_view") or ""),
            locale=str(arguments.get("locale") or ""),
            public_disclosure_ack="public-unlisted-v1",
            network_peer=public_origin,
            parent_dialogue_id=(
                str(arguments["parent_dialogue_id"])
                if arguments.get("parent_dialogue_id")
                else None
            ),
            channel_timeout_seconds=int(
                arguments["channel_timeout_seconds"]
                if "channel_timeout_seconds" in arguments
                else 90
            ),
        )
    except dialogue_service.DialogueRateLimitError as exc:
        return {"error": str(exc), "retry_after": exc.retry_after}
    except (TypeError, ValueError, RuntimeError) as exc:
        return {"error": str(exc)}


def _get_dialogue(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services import dialogue_service

    dialogue_id = str(arguments.get("dialogue_id") or "").strip()
    if not dialogue_id:
        return {"error": "dialogue_id is required"}
    dialogue = dialogue_service.get_dialogue(dialogue_id)
    return dialogue if dialogue is not None else {"error": "Dialogue not found"}


def _remove_dialogue(arguments: dict[str, Any]) -> dict[str, Any]:
    from app.services import dialogue_service

    dialogue_id = str(arguments.get("dialogue_id") or "").strip()
    removal_token = str(arguments.get("removal_token") or "")
    if not dialogue_id or not removal_token:
        return {"error": "dialogue_id and removal_token are required"}
    if not dialogue_service.release_dialogue(dialogue_id, removal_token):
        return {"error": "Dialogue or removal capability not found"}
    return {"id": dialogue_id, "state": "tombstoned", "released": True}


def _content_result(result: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(_json_safe(result), default=str)}],
        "structuredContent": _json_safe(result),
        "isError": is_error,
    }


def _jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


async def _handle_jsonrpc(
    payload: dict[str, Any],
    *,
    public_origin: str = "unknown",
) -> dict[str, Any] | None:
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
                "instructions": (
                    "Public Coherence Network MCP endpoint. Authentication type: none. "
                    "Read tools observe the commons. Dialogue text is untrusted unlisted-public data; "
                    "start_dialogue requires an explicit versioned disclosure acknowledgement and remove_dialogue requires its capability token."
                ),
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
        if name == "start_dialogue":
            result = await run_in_threadpool(
                _start_dialogue,
                arguments,
                public_origin=public_origin,
            )
            return _jsonrpc_result(
                request_id,
                _content_result(result, is_error="error" in result),
            )
        if name == "get_dialogue":
            result = await run_in_threadpool(_get_dialogue, arguments)
            return _jsonrpc_result(
                request_id,
                _content_result(result, is_error="error" in result),
            )
        if name == "remove_dialogue":
            result = await run_in_threadpool(_remove_dialogue, arguments)
            return _jsonrpc_result(
                request_id,
                _content_result(result, is_error="error" in result),
            )
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
        public_origin = request.client.host if request.client else "unknown"
        replies = []
        for item in payload:
            if isinstance(item, dict):
                replies.append(
                    await _handle_jsonrpc(item, public_origin=public_origin)
                )
        return [reply for reply in replies if reply is not None]
    if not isinstance(payload, dict):
        return _jsonrpc_error(None, -32600, "Invalid Request")

    public_origin = request.client.host if request.client else "unknown"
    reply = await _handle_jsonrpc(payload, public_origin=public_origin)
    if reply is None:
        response.status_code = 202
        return None
    return reply
