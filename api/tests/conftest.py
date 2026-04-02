"""Pytest configuration and fixtures.

Prefer the real ``pytest-asyncio`` plugin when installed (CI/dev standard).
Fall back to a tiny built-in async runner in constrained environments where
that dependency is unavailable.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def set_config() -> Any:
    """Set config values directly for tests without using ENV vars.
    
    Usage:
        def test_something(set_config):
            set_config("agent_tasks", "persist", False)
            set_config("agent_cost", "allow_paid_providers", True)
    
    Overrides values in config_loader._CONFIG and config_service cache.
    """
    from app import config_loader
    import app.services.config_service as cs_module
    
    # Keys that need to be set under both agent_executor and executor sections
    EXECUTOR_KEYS = {
        "policy_enabled", "cheap_default", "default", "escalate_to",
        "escalate_failure_threshold", "escalate_retry_threshold", "open_question_default"
    }
    
    def _set(section: str, key: str, value: Any) -> None:
        # Set in config_loader
        if section not in config_loader._CONFIG:
            config_loader._CONFIG[section] = {}
        config_loader._CONFIG[section][key] = value
        
        # Set in config_service cache (initialized by autouse fixture)
        if cs_module._CACHE is not None:
            cs_module._CACHE[f"{section}_{key}"] = value
            if section == "agent_executor":
                cs_module._CACHE[f"agent_{key}"] = value
        
        # For executor-related keys, also set under 'executor' section
        if section == "agent_executor" and key in EXECUTOR_KEYS:
            config_loader._CONFIG.setdefault("executor", {})[key] = value
            if cs_module._CACHE is not None:
                cs_module._CACHE[f"executor_{key}"] = value
    
    return _set

# Mark environment as test BEFORE any app module imports — this disables
# rate limiting middleware and relaxes auth requirements for testing.
os.environ.setdefault("COHERENCE_ENV", "test")

_DB_ENV_VARS = (
    "DATABASE_URL",
    "AGENT_TASKS_DATABASE_URL",
    "IDEA_COMMIT_EVIDENCE_DIR",
)

if os.getenv("PYTEST_ALLOW_DATABASE_URL", "").strip().lower() not in {"1", "true", "yes", "on"}:
    for _env_key in _DB_ENV_VARS:
        # Wipe external DB URLs before importing application modules so
        # tests never try to connect to shared Postgres instances during
        # collection. Individual tests can still opt into a DB by setting
        # their own env vars via monkeypatch.
        os.environ.pop(_env_key, None)

try:  # prefer real plugin when available
    import pytest_asyncio as _pytest_asyncio  # noqa: F401
except ModuleNotFoundError:
    HAS_PYTEST_ASYNCIO = False
else:
    HAS_PYTEST_ASYNCIO = True


if HAS_PYTEST_ASYNCIO:
    pytest_plugins = ("pytest_asyncio",)
else:

    @pytest.fixture
    def event_loop() -> asyncio.AbstractEventLoop:
        """Provide event loop fixture compatible with async tests."""
        loop = asyncio.new_event_loop()
        try:
            yield loop
        finally:
            loop.close()

    def pytest_configure(config: pytest.Config) -> None:
        """Register asyncio marker when fallback runner is active."""
        config.addinivalue_line("markers", "asyncio: mark test to run in an asyncio event loop")

    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
        """Execute async test functions when pytest-asyncio isn't installed."""
        test_func = pyfuncitem.obj
        if not inspect.iscoroutinefunction(test_func):
            return None

        loop = pyfuncitem.funcargs.get("event_loop")
        owns_loop = False
        if loop is None:
            loop = asyncio.new_event_loop()
            owns_loop = True

        try:
            kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
            loop.run_until_complete(test_func(**kwargs))
        finally:
            if owns_loop:
                loop.close()

        return True


@pytest.fixture(autouse=True)
def _reset_service_caches_between_tests(tmp_path: Path) -> None:
    """Reset unified DB engine and service caches between tests.

    Each test gets a clean engine and a unique, isolated SQLite database
    in tmp_path so env-var changes take effect and state never leaks.
    """
    from app import config_loader
    import app.services.config_service as cs_module
    from app.services import (
        agent_service,
        automation_usage_service,
        idea_service,
        unified_db,
        unified_models,  # noqa: F401 — ensures all table models are registered
    )
    from app.services.agent_routing import model_routing_loader

    # Use an isolated DB for each test
    db_file = tmp_path / "test_coherence.db"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_file}"
    # Ideas now live in graph_nodes (unified DB) — don't set file-based portfolio path
    os.environ.pop("IDEA_PORTFOLIO_PATH", None)
    os.environ["AGENT_TASKS_USE_DB"] = "0"

    # Start from the normal config defaults, then pin the test-specific overrides.
    config_loader.reload_config()
    config_loader._CONFIG.setdefault("agent_tasks", {})["persist"] = False
    config_loader._CONFIG.setdefault("agent_executor", {})["execute_token_allow_unauth"] = True
    config_loader._CONFIG.setdefault("agent_executor", {})["execute_token"] = None
    config_loader._CONFIG.setdefault("agent_executor", {})["policy_enabled"] = True
    config_loader._CONFIG.setdefault("runtime", {})["events_path"] = str(tmp_path / "runtime_events.json")
    config_loader._CONFIG.setdefault("runtime", {})["idea_map_path"] = str(tmp_path / "runtime_idea_map.json")
    config_loader._CONFIG.setdefault("agent_lifecycle", {})["subscribers"] = "runtime"

    # Reset config_service cache with the normal defaults so unrelated tests keep working.
    # Then overlay the specific knobs these agent tests expect to control directly.
    cs_module.reset_config_cache()
    cs_module._CACHE = dict(cs_module.get_config())
    cs_module._CACHE.update(
        {
            "agent_tasks_persist": False,
            "agent_executor_execute_token_allow_unauth": True,
            "agent_execute_token_allow_unauth": True,
            "agent_executor_execute_token": None,
            "agent_execute_token": None,
            "runtime_events_path": str(tmp_path / "runtime_events.json"),
            "runtime_idea_map_path": str(tmp_path / "runtime_idea_map.json"),
            "agent_lifecycle_subscribers": "runtime",
        }
    )

    # Reset the unified engine — all services delegate to this
    unified_db.reset_engine()
    unified_db.ensure_schema()

    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_test_context = None

    idea_service._TRACKED_IDEA_CACHE["expires_at"] = 0.0
    idea_service._TRACKED_IDEA_CACHE["idea_ids"] = []
    idea_service._TRACKED_IDEA_CACHE["cache_key"] = ""
    idea_service._invalidate_ideas_cache()

    automation_usage_service.invalidate_cache()
    model_routing_loader.reset_model_routing_cache()


@pytest.fixture
def seeded_db(tmp_path: Path) -> None:
    """Provide a seeded database for tests that expect initial data."""
    from app.services import unified_db
    unified_db.ensure_schema()

    try:
        from app.services import graph_service
        # Seed a minimal test idea into graph_nodes
        if not graph_service.get_node("test-idea-001"):
            graph_service.create_node(
                id="test-idea-001", type="idea",
                name="Test Idea",
                description="A test idea for automated tests",
                phase="gas",
                properties={
                    "potential_value": 100.0,
                    "estimated_cost": 10.0,
                    "actual_value": 0.0,
                    "actual_cost": 0.0,
                    "confidence": 0.5,
                    "manifestation_status": "none",
                    "stage": "none",
                    "idea_type": "standalone",
                    "interfaces": [],
                    "open_questions": [],
                },
            )
    except Exception as e:
        print(f"Warning: seeded_db graph seed: {e}")


@pytest.fixture
def production_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set production URLs for tests that verify production URL formatting."""
    from app.services import config_service
    config_service.reset_config_cache()
    # Force production URLs in config
    monkeypatch.setenv("COHERENCE_ENV", "production")
