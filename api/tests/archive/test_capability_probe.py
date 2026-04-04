"""Tests for Spec 137: node capability auto-discovery probe."""

from __future__ import annotations

from unittest.mock import patch

from app.services.capability_probe import CapabilityProbe


def test_probe_detects_available_executor(monkeypatch):
    """When command exists, executor appears in probe output."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with patch("app.services.capability_probe.shutil.which") as mock_which:
        mock_which.side_effect = lambda cmd: "/usr/bin/claude" if cmd == "claude" else None
        result = CapabilityProbe.probe()
    assert "claude" in result.executors


def test_probe_detects_missing_executor(monkeypatch):
    """Missing commands are not reported."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with patch("app.services.capability_probe.shutil.which", return_value=None):
        result = CapabilityProbe.probe()
    assert "cursor" not in result.executors
    assert "agent" not in result.executors


def test_probe_detects_system_tools(monkeypatch):
    """Tool discovery reports only available tools."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def _which(cmd: str):
        if cmd in {"git", "python3"}:
            return f"/usr/bin/{cmd}"
        return None

    with patch("app.services.capability_probe.shutil.which", side_effect=_which):
        result = CapabilityProbe.probe()

    assert "git" in result.tools
    assert "python3" in result.tools
    assert "docker" not in result.tools


def test_probe_reads_hardware_metadata():
    """Probe includes cpu/memory/gpu hardware shape."""
    result = CapabilityProbe.probe()
    assert "cpu_count" in result.hardware
    assert "memory_total_gb" in result.hardware
    assert "gpu_available" in result.hardware
    assert "gpu_type" in result.hardware


def test_probe_loads_models_from_config():
    """Probe reads models grouped by executor from model_routing.json."""
    models = CapabilityProbe._load_models_by_executor()
    assert isinstance(models, dict)
    assert "openrouter" in models
    assert isinstance(models["openrouter"], list)


def test_probe_completes_within_timeout(monkeypatch):
    """A hanging tool check is bounded by timeout and does not block probe."""
    import time

    def _slow_check(_cmd: str):
        time.sleep(10)
        return None

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    start = time.monotonic()
    with patch("app.services.capability_probe.CapabilityProbe._check_command_available", side_effect=_slow_check):
        result = CapabilityProbe.probe()
    elapsed = time.monotonic() - start
    assert elapsed < 6.5
    assert isinstance(result.executors, list)
