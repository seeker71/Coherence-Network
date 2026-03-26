"""Acceptance tests for spec 155 (tasks page fetch/CORS regression)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def test_get_api_base_uses_proxy_for_browser_remote_api() -> None:
    """Spec 155: browser + remote API URL must return empty base for Next proxy."""
    source = (REPO_ROOT / "web" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert 'const isBrowser = typeof window !== "undefined";' in source
    assert "if (isBrowser && resolved !== DEV_API_URL) return \"\";" in source


def test_get_api_base_returns_full_url_for_server_components() -> None:
    """Spec 155: server-side path keeps full API URL when env is resolved."""
    source = (REPO_ROOT / "web" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert "return resolved;" in source
    assert "if (isBrowser) return \"\";" in source
    assert "return DEV_API_URL;" in source


def test_tasks_page_fetches_agent_tasks_via_relative_api_path() -> None:
    """Spec 155: /tasks client fetch stays relative and never hardcodes remote API host."""
    source = (REPO_ROOT / "web" / "app" / "tasks" / "page.tsx").read_text(encoding="utf-8")

    assert "fetchWithTimeout(`/api/agent/tasks?" in source
    assert "https://api.coherencycoin.com" not in source


def test_agent_tasks_endpoint_returns_non_empty_total_after_seed() -> None:
    """Spec 155 verification: tasks list returns data (total > 0)."""
    create = client.post(
        "/api/agent/tasks",
        json={"direction": "spec-155 regression seed", "task_type": "test"},
    )
    assert create.status_code == 201, create.text

    listed = client.get("/api/agent/tasks?limit=1")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert int(payload.get("total", 0)) > 0
