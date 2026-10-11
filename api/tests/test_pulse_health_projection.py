"""The continuous pulse witness uses bounded health, not deep runtime proof."""

import httpx
import pytest

from app.main import app
from app.routers import health as health_router
from app.services import native_runtime_observation


@pytest.mark.asyncio
async def test_pulse_health_projection_keeps_deep_runtime_proof_off_hot_path(
    monkeypatch,
):
    monkeypatch.setattr(
        health_router.audit_ledger_service,
        "verify_chain",
        lambda: pytest.fail("pulse health invoked audit-ledger proof"),
    )
    monkeypatch.setattr(
        health_router,
        "_check_schema",
        lambda: pytest.fail("pulse health invoked database schema proof"),
    )
    monkeypatch.setattr(
        health_router,
        "recent_outcomes_snapshot",
        lambda: {"last_1m": {"2xx": 3, "4xx": 0, "5xx": 0, "total": 3}},
    )
    monkeypatch.setattr(
        native_runtime_observation,
        "observe_native_runtime",
        lambda: pytest.fail("pulse health invoked deep native-runtime proof"),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health/pulse")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_ok"] is False
    assert body["integrity_compromised"] is False
    assert body["integrity_verified"] is False
    assert body["recent_outcomes"] == {
        "last_1m": {"2xx": 3, "4xx": 0, "5xx": 0, "total": 3}
    }
    assert body["version"]
    assert body["started_at"]
    assert body["uptime_seconds"] >= 0
    assert body["uptime_human"]
    assert "deployed_sha" in body
    assert "deployed_sha_source" in body
    assert body["native_runtime_observation"] is None
    assert body["deployment_witness_node_id"] is None
    assert body["deployment_observation_fresh"] is False


@pytest.mark.asyncio
async def test_pulse_health_projection_survives_outcome_snapshot_failure(
    monkeypatch,
):
    def fail_outcome_snapshot():
        raise RuntimeError("outcome snapshot unavailable")

    monkeypatch.setattr(
        health_router.audit_ledger_service,
        "verify_chain",
        lambda: pytest.fail("pulse health invoked audit-ledger proof"),
    )
    monkeypatch.setattr(
        health_router,
        "_check_schema",
        lambda: pytest.fail("pulse health invoked database schema proof"),
    )
    monkeypatch.setattr(
        health_router,
        "recent_outcomes_snapshot",
        fail_outcome_snapshot,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health/pulse")

    assert response.status_code == 200
    assert response.json()["schema_ok"] is False
    assert response.json()["integrity_verified"] is False
    assert response.json()["integrity_compromised"] is False
    assert response.json()["recent_outcomes"] is None
