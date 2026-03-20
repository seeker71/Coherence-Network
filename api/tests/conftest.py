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

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

    Each test gets a clean engine so env-var changes take effect.
    """
    from app.services import (
        agent_service,
        idea_service,
        unified_db,
    )

    # Reset the unified engine — all services delegate to this
    unified_db.reset_engine()

    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_test_context = None

    idea_service._TRACKED_IDEA_CACHE["expires_at"] = 0.0
    idea_service._TRACKED_IDEA_CACHE["idea_ids"] = []
    idea_service._TRACKED_IDEA_CACHE["cache_key"] = ""

    # Clear DB env vars so each test starts from default (local sqlite)
    for key in ("DATABASE_URL", "IDEA_COMMIT_EVIDENCE_DIR"):
        os.environ.pop(key, None)
