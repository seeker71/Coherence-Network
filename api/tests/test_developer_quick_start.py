"""Acceptance tests for spec: developer-quick-start (idea: developer-experience).

Covers done_when criteria:
  - GET /api/health returns status ok with schema_ok true
  - pytest runs all flow tests in under 10 seconds
"""

from __future__ import annotations

import subprocess
import sys
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


# ---------------------------------------------------------------------------
# 1. GET /api/health returns status ok with schema_ok true
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_returns_ok_with_schema_ok():
    """Health endpoint returns status=ok and schema_ok=true."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/health")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert body.get("schema_ok") is True


# ---------------------------------------------------------------------------
# 2. Test suite execution time is under 10 seconds (meta-test)
# ---------------------------------------------------------------------------

def test_flow_tests_run_under_10_seconds():
    """All flow tests complete in under 10 seconds.

    This is a meta-test: it invokes pytest on the core flow tests in a
    subprocess and asserts wall-clock time stays under 10s.
    """
    test_file = "api/tests/test_flow_core_api.py"
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-x", "-q", "--tb=no"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    elapsed = time.perf_counter() - t0

    # The tests should pass
    assert result.returncode == 0, (
        f"Flow tests failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
    )
    assert elapsed < 10.0, (
        f"Flow tests took {elapsed:.1f}s (limit 10s)"
    )
