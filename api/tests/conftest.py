"""Pytest configuration and asyncio support fixtures.

This project typically uses pytest-asyncio, but CI/dev environments may not
have that package preinstalled. Keep a tiny built-in fallback so `pytest -v`
works out of the box.
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


@pytest.fixture
def event_loop() -> asyncio.AbstractEventLoop:
    """Provide an event loop fixture for async tests."""
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


def pytest_configure(config: pytest.Config) -> None:
    """Register asyncio marker for compatibility."""
    config.addinivalue_line("markers", "asyncio: mark test to run in an asyncio event loop")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """Execute async test functions without requiring pytest-asyncio plugin."""
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
