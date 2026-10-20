"""A real npm launcher completes MCP initialization, discovery, and a local call."""
import json
import shutil
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_npm_launcher_mcp_session():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to observe the npm launch surface")
    launcher = Path(__file__).resolve().parents[1] / "index.mjs"
    params = StdioServerParameters(command=node, args=[str(launcher)])
    async with (
        stdio_client(params) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        initialized = await session.initialize()
        assert initialized.serverInfo.name == "coherence-network"
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
        assert "coherence_grounded_ask" in tools
        assert "coherence_substrate_form" not in tools
        assert "capture_consent" in tools["coherence_capture"].inputSchema["required"]
        response = await session.call_tool(
            "coherence_transmute", {"raw": "This is dangerous; do not proceed."},
        )
        result = json.loads(response.content[0].text)
        assert result["raw"] == "This is dangerous; do not proceed."
        assert result["route"] == "current-chat"
        assert result["captured"] is False
