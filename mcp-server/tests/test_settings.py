"""Verify MCP configuration selection and fail-closed transport setup."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coherence_mcp_server.settings import load_settings


def write_config(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_defaults_and_file_overlay_ignore_environment(tmp_path, monkeypatch):
    repo, home = tmp_path / "repo", tmp_path / "home"
    monkeypatch.setenv("COHERENCE_API_URL", "https://wrong.example")
    monkeypatch.setenv("COHERENCE_API_KEY", "ignored-secret")
    defaults = load_settings(repo=repo, home=home)
    assert defaults["api_base"] == "https://api.coherencycoin.com"
    assert defaults["api_key"] == ""
    assert defaults["capability_profile"] == "companion"
    assert defaults["grounded_ask_timeout_seconds"] == 90
    assert defaults["kernel_path"] == str(repo / "form" / "fkwu")
    write_config(repo / "api/config/api.json", {"mcp": {
        "api_base": "http://localhost:8000/", "api_key": "repo-key",
    }})
    write_config(home / ".coherence-network/config.json", {"mcp": {
        "api_key": "local-key", "grounded_ask_timeout_seconds": 120,
        "capability_profile": "advanced",
    }})
    selected = load_settings(repo=repo, home=home)
    assert selected["api_base"] == "http://localhost:8000"
    assert selected["api_key"] == "local-key"
    assert selected["grounded_ask_timeout_seconds"] == 120
    assert selected["capability_profile"] == "advanced"


@pytest.mark.parametrize("document", [
    [], {"mcp": None}, {"mcp": []}, {"mcp": {"api_key": False}},
    {"mcp": {"api_base": "file:///tmp/service"}},
    {"mcp": {"api_base": "https://secret:password@example.com"}},
    {"mcp": {"api_base": "https://example.com?key=secret"}},
    {"mcp": {"api_base": "https://example.com:bad"}},
    {"mcp": {"catalog_path": "relative.jsonl"}},
    {"mcp": {"grounded_ask_timeout_seconds": True}},
    {"mcp": {"grounded_ask_timeout_seconds": 0}},
    {"mcp": {"grounded_ask_timeout_seconds": 901}},
    {"mcp": {"grounded_ask_timeout_seconds": "90"}},
    {"mcp": {"capability_profile": "all"}},
    {"mcp": {"capability_profile": ""}},
    {"mcp": {"capability_profile": True}},
])
def test_invalid_configuration_does_not_select_a_fallback(tmp_path, document):
    write_config(tmp_path / ".coherence-network/config.json", document)
    with pytest.raises(ValueError) as failure:
        load_settings(repo=tmp_path / "repo", home=tmp_path)
    assert "secret" not in str(failure.value)
    assert "password" not in str(failure.value)


def test_malformed_overlay_is_not_silently_ignored(tmp_path):
    path = tmp_path / ".coherence-network/config.json"
    path.parent.mkdir()
    path.write_text('{"mcp": "credential-that-must-not-appear"')
    with pytest.raises(ValueError) as failure:
        load_settings(repo=tmp_path / "repo", home=tmp_path)
    assert "credential-that-must-not-appear" not in str(failure.value)
