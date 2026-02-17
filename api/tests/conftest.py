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
    # Ensure env-driven storage paths are honored per-test and avoid cross-test
    # leakage through module-level engine/cache state.
    from app.services import (
        agent_service,
        governance_service,
        commit_evidence_service,
        idea_registry_service,
        idea_service,
        spec_registry_service,
    )

    for service in (idea_registry_service, spec_registry_service, governance_service):
        cache = getattr(service, "_ENGINE_CACHE", None)
        if isinstance(cache, dict):
            engine = cache.get("engine")
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass
            cache["url"] = ""
            cache["engine"] = None
            cache["sessionmaker"] = None

    evidence_cache = getattr(commit_evidence_service, "_ENGINE_CACHE", None)
    if isinstance(evidence_cache, dict):
        engine = evidence_cache.get("engine")
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass
        evidence_cache["url"] = ""
        evidence_cache["engine"] = None
        evidence_cache["sessionmaker"] = None

    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_test_context = None

    idea_service._TRACKED_IDEA_CACHE["expires_at"] = 0.0
    idea_service._TRACKED_IDEA_CACHE["idea_ids"] = []
    idea_service._TRACKED_IDEA_CACHE["cache_key"] = ""

    for key in (
        "DATABASE_URL",
        "IDEA_REGISTRY_DATABASE_URL",
        "IDEA_REGISTRY_DB_URL",
        "GOVERNANCE_DATABASE_URL",
        "GOVERNANCE_DB_URL",
        "COMMIT_EVIDENCE_DATABASE_URL",
        "IDEA_COMMIT_EVIDENCE_DIR",
    ):
        os.environ.pop(key, None)

    os.environ["COMMIT_EVIDENCE_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'commit_evidence_test.db'}"
