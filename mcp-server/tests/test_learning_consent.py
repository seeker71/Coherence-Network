"""The exposed tool must preserve the same consent boundary as direct callers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coherence_mcp_server import form_cli_tools as fct
from coherence_mcp_server import server


def test_capture_schema_discloses_separate_local_copy():
    tool = server.TOOL_MAP["coherence_capture"]
    assert "capture_consent" in tool.inputSchema["required"]
    assert tool.inputSchema["properties"]["capture_consent"]["const"] == fct.CAPTURE_CONSENT
    assert "deleting the chat does not delete this copy" in tool.description
    assert tool.inputSchema["additionalProperties"] is False
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.idempotentHint is False


def test_capture_dispatch_does_not_supply_implicit_consent(monkeypatch):
    def no_storage():
        raise AssertionError("Denied tool call must not open settings or storage")
    monkeypatch.setattr(fct, "load_settings", no_storage)
    result = server.dispatch("coherence_capture", {"request": "private", "raw": "private", "transmuted": "private"})
    assert result["captured"] is False


def test_capture_dispatch_passes_only_callers_consent(monkeypatch):
    calls = []
    monkeypatch.setattr(fct, "catalog_capture", lambda *args, **kwargs: calls.append((args, kwargs)) or {"captured": True})
    assert server.dispatch("coherence_capture", {
        "request": "selected", "raw": "original", "transmuted": "reviewed",
        "capture_consent": fct.CAPTURE_CONSENT,
    })["captured"] is True
    assert calls[0][1] == {"capture_consent": fct.CAPTURE_CONSENT}
