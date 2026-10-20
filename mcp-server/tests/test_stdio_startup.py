"""The distributed npm artifact works outside a checkout and personal config."""
import asyncio
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_packed_npm_launcher_mcp_session():
    node = shutil.which("node")
    npm = shutil.which("npm")
    if node is None or npm is None or shutil.which("uv") is None:
        pytest.skip("Node, npm, and uv are required to observe the packaged launch surface")
    source = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="coherence packed smoke ") as scratch:
        isolated = Path(scratch)
        assert not isolated.resolve().is_relative_to(source.parent)
        packed = await asyncio.to_thread(
            subprocess.run,
            [npm, "pack", "--ignore-scripts", "--json", "--pack-destination", str(isolated)],
            cwd=source, text=True, capture_output=True, check=True, timeout=60,
        )
        artifact = isolated / json.loads(packed.stdout)[0]["filename"]
        # Copy only regular files from our artifact; this works on Python 3.10
        # without newer tarfile extraction filters and rejects linked members.
        with tarfile.open(artifact) as archive:
            for member in archive.getmembers():
                target = isolated / member.name
                assert target.resolve().is_relative_to(isolated.resolve())
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                assert member.isfile(), member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as stream:
                    target.write_bytes(stream.read())
                target.chmod(member.mode & 0o777)
        package = isolated / "package"
        manifest = json.loads((package / "package.json").read_text())
        assert manifest["license"] == "Apache-2.0"
        assert (package / "LICENSE").read_bytes() == (source.parent / "LICENSE").read_bytes()
        lock_before = (package / "uv.lock").read_bytes()
        personal = isolated / "isolated home"
        config = personal / ".coherence-network" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"mcp": {"api_base": "http://127.0.0.1:9"}}))
        # HOME/USERPROFILE are child-process isolation, never product settings.
        child_env = dict(os.environ, HOME=str(personal), USERPROFILE=str(personal))
        for key in ("PYTHONPATH", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
            child_env.pop(key, None)
        params = StdioServerParameters(
            command=node, args=[str(package / "index.mjs")],
            cwd=str(isolated), env=child_env,
        )
        async with (
            stdio_client(params) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            initialized = await session.initialize()
            assert initialized.serverInfo.name == "coherence-network"
            assert initialized.serverInfo.version == manifest["version"]
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            assert "coherence_grounded_ask" in tools
            assert "coherence_substrate_form" not in tools
            assert "coherence_capture" not in tools
            assert "coherence_create_idea" not in tools
            assert len(tools) == 10
            assert all(tool.annotations.readOnlyHint for tool in tools.values())
            response = await session.call_tool(
                "coherence_transmute", {"raw": "This is dangerous; do not proceed."},
            )
            assert response.isError is False
            result = json.loads(response.content[0].text)
            assert result["raw"] == "This is dangerous; do not proceed."
            assert result["route"] == "current-chat"
            assert result["captured"] is False
            denied = await session.call_tool(
                "coherence_create_idea", {"name": "must not be published"},
            )
            assert denied.isError is True
        assert (package / "uv.lock").read_bytes() == lock_before
        assert sorted(path.name for path in config.parent.iterdir()) == ["config.json"]
