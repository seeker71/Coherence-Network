"""Pytest configuration and fixtures.

Prefer the real ``pytest-asyncio`` plugin when installed (CI/dev standard).
Fall back to a tiny built-in async runner in constrained environments where
that dependency is unavailable.
"""

from __future__ import annotations

import asyncio
import inspect
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
