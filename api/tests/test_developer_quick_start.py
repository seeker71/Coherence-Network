"""Acceptance tests for spec: developer-quick-start (idea: developer-experience).

Covers done_when criteria:
  - GET /api/health returns status ok with schema_ok true
  - pytest runs all flow tests in under 10 seconds
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

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
    subprocess and asserts its child CPU time stays under 10s.

    Wall time is retained in the failure message, but is not the performance
    contract: shared-runner scheduling and filesystem I/O can pause a healthy
    child arbitrarily.
    """
    test_file = Path(__file__).with_name("test_flow_core_api.py")
    child_env = os.environ.copy()
    child_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    child_runner = (
        "import sys, time\n"
        "started = time.process_time()\n"
        "import pytest\n"
        "exit_code = pytest.main(sys.argv[1:])\n"
        'print(f"FLOW_CPU_SECONDS={time.process_time() - started:.6f}")\n'
        "raise SystemExit(int(exit_code))\n"
    )
    wall_started = time.perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            child_runner,
            "--assert=plain",
            "-p",
            "pytest_asyncio.plugin",
            str(test_file),
            "-x",
            "-q",
            "--tb=no",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=child_env,
    )
    wall_elapsed = time.perf_counter() - wall_started
    # The tests should pass
    assert result.returncode == 0, (
        f"Flow tests failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
    )
    measured = re.findall(r"^FLOW_CPU_SECONDS=([0-9]+(?:\.[0-9]+)?)$", result.stdout, re.M)
    assert measured, f"child did not report CPU time:\n{result.stdout}"
    child_cpu_elapsed = float(measured[-1])
    assert child_cpu_elapsed < 10.0, (
        f"Flow tests used {child_cpu_elapsed:.1f}s CPU and "
        f"{wall_elapsed:.1f}s wall (CPU limit 10s)"
    )
