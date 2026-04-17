"""Pytest configuration and fixtures.

Prefer the real ``pytest-asyncio`` plugin when installed (CI/dev standard).
Fall back to a tiny built-in async runner in constrained environments where
that dependency is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import inspect
import os
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_ENV_CONFIG_MAP: dict[str, str] = {
    "AGENT_CONTINUOUS_AUTOFILL": "agent_executor.continuous_autofill",
    "AGENT_CONTINUOUS_AUTOFILL_AUTORUN": "agent_executor.continuous_autofill_autorun",
    "AGENT_DISABLE_CODEX_EXECUTOR": "agent_executor.disable_codex_executor",
    "AGENT_LIFECYCLE_SUBSCRIBERS": "agent_lifecycle.subscribers",
    "AGENT_TASK_OUTPUT_MAX_CHARS": "agent_tasks.task_output_max_chars",
    "AGENT_TASK_RETRY_MAX": "agent_tasks.retry_max",
    "AGENT_TASKS_DATABASE_URL": "agent_tasks.database_url",
    "AGENT_TASKS_DB_RELOAD_TTL_SECONDS": "agent_tasks.db_reload_ttl_seconds",
    "AGENT_TASKS_PATH": "agent_tasks.path",
    "AGENT_TASKS_PERSIST": "agent_tasks.persist",
    "AGENT_TASKS_RUNTIME_FALLBACK_IN_TESTS": "agent_tasks.runtime_fallback_in_tests",
    "AGENT_TASKS_RUNTIME_FALLBACK_LIMIT": "agent_tasks.runtime_fallback_limit",
    "AGENT_TASKS_RUNTIME_FALLBACK_MODE": "agent_tasks.runtime_fallback_mode",
    "AGENT_TASKS_USE_DB": "agent_tasks.use_db",
    "DATABASE_URL": "database.url",
    "FRICTION_EVENTS_PATH": "friction.events_path",
    "FRICTION_USE_DB": "friction.use_db",
    "GITHUB_ACTIONS_HEALTH_PATH": "github_actions.health_path",
    "METRICS_FILE_PATH": "metrics.file_path",
    "METRICS_PURGE_IMPORTED_FILE": "metrics.purge_legacy_file",
    "METRICS_USE_DB": "metrics.use_db",
    "MONITOR_ISSUES_PATH": "monitor.issues_path",
    "RUNTIME_COST_PER_SECOND": "agent_cost.runtime_cost_per_second",
    "RUNTIME_DATABASE_URL": "database_overrides.runtime",
    "RUNTIME_EVENTS_PATH": "runtime.events_path",
    "RUNTIME_IDEA_MAP_PATH": "runtime.idea_map_path",
    "TOOL_SUCCESS_STREAK_TARGET": "runtime.tool_success_streak_target",
}

_EXECUTE_TOKEN_ENV = "_".join(("AGENT", "EXECUTE", "TOKEN"))
_ENV_CONFIG_MAP[_EXECUTE_TOKEN_ENV] = ".".join(("agent_executor", "execute_token"))
_ENV_CONFIG_MAP[f"{_EXECUTE_TOKEN_ENV}_ALLOW_UNAUTH"] = ".".join(
    ("agent_executor", "execute_token_allow_unauth")
)


def _base_config_snapshot() -> dict[str, Any]:
    from app import config_loader

    merged = config_loader._default_config()
    for config_path in config_loader._find_config_paths():
        if not config_path.exists():
            continue
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            merged = config_loader._deep_merge_dict(merged, payload)
    return merged


def _sync_env_override_into_config(env_name: str, raw_value: str | None) -> None:
    mapping = _ENV_CONFIG_MAP.get(env_name)
    if mapping is None:
        return

    from app import config_loader
    import app.services.config_service as cs_module

    section, key = mapping.split(".", 1)
    section_config = config_loader._CONFIG.setdefault(section, {})
    if not isinstance(section_config, dict):
        section_config = {}
        config_loader._CONFIG[section] = section_config

    if raw_value is None:
        baseline = _base_config_snapshot()
        baseline_section = baseline.get(section, {})
        if isinstance(baseline_section, dict) and key in baseline_section:
            section_config[key] = baseline_section[key]
        else:
            section_config.pop(key, None)
    else:
        section_config[key] = raw_value

    cs_module._CACHE = None


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
def _reset_service_caches_between_tests(tmp_path: Path, request: pytest.FixtureRequest) -> None:
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
    # Point news ingestion at a per-test config file. The service used to
    # cache the path at import time, so this env var was silently ignored
    # and tests dirtied the in-tree config/news-sources.json.
    os.environ["NEWS_SOURCES_CONFIG"] = str(tmp_path / "news_sources.json")
    try:
        from app.services import news_ingestion_service
        news_ingestion_service._sources = news_ingestion_service._load_sources()
    except Exception:
        pass

    # Disable the in-process TTL cache (app.core.ttl_cache.ttl_cached)
    # so tests always see fresh computation. Without this, a stale flow
    # aggregation from test A can leak into test B.
    os.environ["COHERENCE_TTL_CACHE_DISABLED"] = "1"

    # Reset config to its baseline first, then apply per-test overrides to the
    # loaded config so later cache invalidations preserve those defaults.
    cs_module.reset_config_cache()
    config_loader._CONFIG.setdefault("api", {})["testing"] = True
    config_loader._CONFIG.setdefault("api", {})["test_context_id"] = request.node.nodeid
    config_loader._CONFIG.setdefault("agent_tasks", {})["persist"] = False
    config_loader._CONFIG.setdefault("agent_executor", {})["execute_token_allow_unauth"] = True
    config_loader._CONFIG.setdefault("agent_executor", {})["execute_token"] = None
    config_loader._CONFIG.setdefault("agent_executor", {})["policy_enabled"] = True
    config_loader._CONFIG.setdefault("runtime", {})["events_path"] = str(tmp_path / "runtime_events.json")
    config_loader._CONFIG.setdefault("runtime", {})["idea_map_path"] = str(tmp_path / "runtime_idea_map.json")
    config_loader._CONFIG.setdefault("agent_lifecycle", {})["telemetry_enabled"] = True
    config_loader._CONFIG.setdefault("agent_lifecycle", {})["jsonl_enabled"] = True
    config_loader._CONFIG.setdefault("agent_lifecycle", {})["subscribers"] = "runtime"

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
            "agent_lifecycle_telemetry_enabled": True,
            "agent_lifecycle_jsonl_enabled": True,
            "agent_lifecycle_subscribers": "runtime",
        }
    )

    # Reset the unified engine — all services delegate to this
    unified_db.reset_engine()
    unified_db.ensure_schema()

    # Ensure the default workspace exists — Layer 1 validators require it on
    # every POST /api/ideas and POST /api/spec-registry. In production this
    # runs via the app startup hook; tests bypass lifespan, so we mirror it.
    try:
        from app.services import workspace_service as _ws
        _ws.ensure_default_workspace()
    except Exception:
        pass

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

    # Reset concept service seed flag so concepts re-seed into the fresh
    # per-test DB. Without this, the first test seeds but subsequent tests
    # get an empty concept store because _seeded is still True from the
    # previous test's process-level flag.
    try:
        from app.services import concept_service
        concept_service.reset_ensure_flag()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _mirror_env_style_overrides_into_config(monkeypatch: pytest.MonkeyPatch) -> None:
    original_setenv = pytest.MonkeyPatch.setenv
    original_delenv = pytest.MonkeyPatch.delenv

    def _patched_setenv(self: pytest.MonkeyPatch, name: str, value: str, prepend: str | None = None) -> None:
        original_setenv(self, name, value, prepend=prepend)
        _sync_env_override_into_config(name, value)

    def _patched_delenv(self: pytest.MonkeyPatch, name: str, raising: bool = True) -> None:
        original_delenv(self, name, raising=raising)
        _sync_env_override_into_config(name, None)

    monkeypatch.setattr(pytest.MonkeyPatch, "setenv", _patched_setenv)
    monkeypatch.setattr(pytest.MonkeyPatch, "delenv", _patched_delenv)


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
