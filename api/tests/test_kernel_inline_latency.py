"""Latency sensing for the inline (PyO3) kernel path.

The transmuted endpoints serve through a kernel carrier:
``inline`` (PyO3 extension) or ``subprocess`` (fork+exec the rust binary).
This test exists to make the cost difference visible: when the inline path is hot,
per-request kernel overhead drops
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
from app.services import form_kernel_bridge as bridge
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
        try:
            bridge.load_recipe("endpoint_coherence_weight_demo.fk")
        except FileNotFoundError:
            pytest.skip("recipe not compiled (deploy-time artifact absent) — "
                        "endpoint cannot serve inline")

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
        assert data["active"] in ("inline", "subprocess", "unavailable")
        assert "inline_available" in data
        assert "binary_available" in data

    @pytest.mark.anyio
    async def test_health_reports_kernel_runtime(self, client: AsyncClient):
        """/api/health surfaces kernel_runtime so the witness can read it."""
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["kernel_runtime"] in ("inline", "subprocess", "unavailable")


class TestRoutePreload:
    """The route-preload path parses each recipe ONCE and walks per request.

    The four already-transmuted endpoint recipes share the shape
    ``(do <defn...> <input lets...> <final call>)``. ``split_recipe`` peels the
    input lets out, the warm ``Preloader`` parses setup-once + body-once, and
    ``run`` walks only the body with fresh bindings — no per-request parse. The
    value must still match the parity-suite canonical; the preload is the same
    kernel, so the answer cannot drift.
    """

    # (recipe file, bindings, expected value) — the parity-suite canonicals.
    CASES = [
        (
            "endpoint_coherence_weight_demo.fk",
            {"values": [72, 38, 91, 55, 28, 67, 84, 45, 95, 12], "threshold": 50},
            16185,
        ),
        (
            "endpoint_nodeid_distance_demo.fk",
            {"a_pkg": 1, "a_lvl": 5, "a_type": 4, "a_inst": 1,
             "b_pkg": 1, "b_lvl": 4, "b_type": 4, "b_inst": 7},
            7,
        ),
        (
            "endpoint_nodeid_compatibility_demo.fk",
            {"a_pkg": 1, "a_lvl": 5, "a_type": 4, "a_inst": 1,
             "b_pkg": 1, "b_lvl": 4, "b_type": 4, "b_inst": 7},
            2,
        ),
        (
            "endpoint_weighted_average_demo.fk",
            {"values": [0.5, 0.75, 1.0], "weights": [0.25, 0.25, 0.5]},
            0.8125,
        ),
    ]

    def _require_recipe(self, name: str) -> str:
        """Load a recipe or skip — the .fk is a deploy-compiled, gitignored
        artifact, absent in a fresh checkout / CI without the compile step."""
        try:
            return bridge.load_recipe(name)
        except FileNotFoundError:
            pytest.skip(f"{name} not compiled (deploy-time artifact absent)")

    def test_split_recipe_separates_setup_from_body(self):
        """split_recipe drops the input lets and keeps the trailing call as body."""
        src = self._require_recipe("endpoint_nodeid_distance_demo.fk")
        setup, body = bridge.split_recipe(src, {"a_pkg", "a_lvl", "a_type", "a_inst",
                                                 "b_pkg", "b_lvl", "b_type", "b_inst"})
        # Setup keeps the defn, body is the trailing call — and the dropped
        # input names do not appear as `(let NAME ...)` in either part.
        assert "(defn manhattan" in setup
        assert body.startswith("(manhattan")
        assert "(let a_pkg" not in setup and "(let a_pkg" not in body

    def test_preloaded_values_match_parity_canonicals(self):
        """All four endpoints return their canonical value through the preload path."""
        if not bridge.preload_available():
            pytest.skip("Preloader (route-preload pair) not available")
        for recipe, binds, expected in self.CASES:
            self._require_recipe(recipe)  # skip if the .fk artifact is absent
            handle = bridge.preload_route(recipe, set(binds))
            assert handle is not None, f"{recipe} did not preload"
            value = bridge.run_preloaded(handle, binds)
            if isinstance(expected, float):
                assert abs(float(value) - expected) < 1e-9, (recipe, value)
            else:
                assert value == expected, (recipe, value)

    def test_preload_handle_is_cached_and_rebinds(self):
        """Same recipe → same handle; fresh bindings → fresh result (no re-parse)."""
        if not bridge.preload_available():
            pytest.skip("Preloader (route-preload pair) not available")
        self._require_recipe("endpoint_nodeid_distance_demo.fk")  # skip if absent
        names = {"a_pkg", "a_lvl", "a_type", "a_inst", "b_pkg", "b_lvl", "b_type", "b_inst"}
        h1 = bridge.preload_route("endpoint_nodeid_distance_demo.fk", names)
        h2 = bridge.preload_route("endpoint_nodeid_distance_demo.fk", names)
        assert h1 == h2  # idempotent load — parsed once, handle cached
        # Two different inputs against the one pre-parsed body.
        r_far = bridge.run_preloaded(h1, {"a_pkg": 0, "a_lvl": 0, "a_type": 0, "a_inst": 0,
                                          "b_pkg": 1, "b_lvl": 1, "b_type": 1, "b_inst": 1})
        r_zero = bridge.run_preloaded(h1, {"a_pkg": 5, "a_lvl": 5, "a_type": 5, "a_inst": 5,
                                           "b_pkg": 5, "b_lvl": 5, "b_type": 5, "b_inst": 5})
        assert r_far == 4 and r_zero == 0
