"""Production execution authority checks for c-bootstrapped fkwu.

This file keeps its historical name so existing test selectors remain stable.
The PyO3/preload runtime stack it once measured is retired: production endpoint
execution has one answer, ``fkwu``. Sibling kernels are primitive conformance
witnesses and cannot appear as an API runtime.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.form_kernel_bridge import active_runtime, kernel_available
from app.services.native_runtime_observation import (
    reset_native_runtime_observation_cache,
)

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestFkwuExecutionAuthority:
    @pytest.mark.anyio
    async def test_endpoint_executes_on_fkwu(self, client: AsyncClient):
        assert kernel_available(), "the pinned fkwu source or executable must be present"
        response = await client.get("/api/utils/coherence_weight")
        assert response.status_code == 200
        assert response.json()["weight"] == 16185
        assert response.json()["runtime"] == "fkwu"

    @pytest.mark.anyio
    async def test_kernel_status_has_one_runtime(self, client: AsyncClient):
        response = await client.get("/api/utils/kernel_status")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] == "fkwu"
        assert data["available"] is True
        assert active_runtime() == "fkwu"

    @pytest.mark.anyio
    async def test_health_reports_fkwu(self, client: AsyncClient):
        reset_native_runtime_observation_cache()
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["kernel_runtime"] == "fkwu"
