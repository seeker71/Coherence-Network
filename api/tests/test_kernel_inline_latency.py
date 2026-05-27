"""Latency sensing for the inline (PyO3) kernel path.

The transmuted endpoints serve through one of three runtimes:
``inline`` (PyO3 extension), ``subprocess`` (fork+exec the rust binary),
or ``python-fallback``. This test exists to make the cost difference
visible: when the inline path is hot, per-request kernel overhead drops
from milliseconds (process spawn) to microseconds (a C call into Rust).

The assertion is deliberately soft. We pin two things:

  1. The inline path, when active, has bounded per-request latency
     (< 50 ms wall time including FastAPI's full request cycle).
  2. The recipe still returns the parity-suite canonical value (16185)
     — the inline runtime is the same kernel, so the answer cannot drift.

When the inline kernel is not loaded the test skips — it is a sensing
readout for the optimized path, not a gate on the subprocess path.
"""
from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.form_kernel_bridge import inline_available

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestKernelInlineLatency:
    """The inline path's job is to remove process-spawn overhead per request."""

    @pytest.mark.anyio
    async def test_inline_path_serves_under_budget(self, client: AsyncClient):
        """When inline is active, /api/utils/coherence_weight returns under 50 ms."""
        if not inline_available():
            pytest.skip("PyO3 extension not loaded — inline path not available")

        # Warm-up: first call may include cold caches (FastAPI middleware
        # init, route resolution). Subsequent calls measure the steady state.
        warmup = await client.get("/api/utils/coherence_weight")
        assert warmup.status_code == 200
        assert warmup.json()["weight"] == 16185
        assert warmup.json()["runtime"] == "inline", (
            f"expected inline, got {warmup.json()['runtime']!r}"
        )

        # Measure five warm calls. ASGITransport adds ~ms per request on
        # its own, so 50 ms per request leaves headroom and still fails
        # loudly if we accidentally re-introduce a subprocess spawn.
        deadline_ms = 50.0
        latencies_ms: list[float] = []
        for _ in range(5):
            t0 = time.perf_counter()
            res = await client.get("/api/utils/coherence_weight")
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            assert res.status_code == 200
            assert res.json()["weight"] == 16185
            assert res.json()["runtime"] == "inline"
            latencies_ms.append(elapsed_ms)

        avg_ms = sum(latencies_ms) / len(latencies_ms)
        max_ms = max(latencies_ms)
        assert max_ms < deadline_ms, (
            f"inline path latency regressed: max={max_ms:.2f} ms avg={avg_ms:.2f} ms "
            f"deadline={deadline_ms:.0f} ms — has a subprocess seam come back?"
        )

    @pytest.mark.anyio
    async def test_kernel_status_reports_active_path(self, client: AsyncClient):
        """/api/utils/kernel_status names the active runtime."""
        res = await client.get("/api/utils/kernel_status")
        assert res.status_code == 200
        data = res.json()
        assert data["active"] in ("inline", "subprocess", "python-fallback")
        assert "inline_available" in data
        assert "binary_available" in data

    @pytest.mark.anyio
    async def test_health_reports_kernel_runtime(self, client: AsyncClient):
        """/api/health surfaces kernel_runtime so the witness can read it."""
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["kernel_runtime"] in ("inline", "subprocess", "python-fallback")
