"""Coherence Network MCP server.

Exposes the platform as tools any agent can use via the Model Context Protocol.

Entry point:
    python -m api.mcp_server
    python api/mcp_server.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Ensure the api/ directory is on sys.path so ``from app.services...`` works
# regardless of how the script is invoked.
_API_DIR = Path(__file__).resolve().parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from app.services.mcp_tool_registry import TOOLS, TOOL_MAP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

server = Server("coherence-network")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Return all registered tools."""
    return [
        Tool(
            name=t["name"],
            description=t["description"],
            inputSchema=t["input_schema"],
        )
        for t in TOOLS
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Dispatch a tool call to the appropriate handler."""
    tool_def = TOOL_MAP.get(name)
    if tool_def is None:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    handler = tool_def["handler"]
    args = arguments or {}

    try:
        result = handler(args)
        text = json.dumps(result, default=str)
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        text = json.dumps({"error": str(exc)})

    return [TextContent(type="text", text=text)]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
