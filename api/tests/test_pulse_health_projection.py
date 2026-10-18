"""The continuous pulse witness uses bounded health, not deep runtime proof."""

import inspect
from types import SimpleNamespace

import httpx
import pytest

from app.main import app
from app.routers import health as health_router
from app.services import native_runtime_observation


def test_deep_health_runs_in_fastapi_threadpool_while_ping_stays_on_event_loop():
    assert not inspect.iscoroutinefunction(health_router.health)
    assert not inspect.iscoroutinefunction(health_router.ready)
    assert inspect.iscoroutinefunction(health_router.ping)


@pytest.mark.asyncio
async def test_ready_shares_schema_and_audit_proofs_without_native_runtime(
    monkeypatch,
):
    monkeypatch.setattr(app.state, "graph_store", object(), raising=False)
    monkeypatch.setattr(
        health_router.persistence_contract_service,
        "evaluate",
        lambda _app: {"required": False, "pass_contract": True},
    )
    monkeypatch.setattr(health_router, "_check_schema", lambda: True)
    monkeypatch.setattr(
        health_router.audit_ledger_service,
        "verify_chain",
        lambda: SimpleNamespace(verified=True),
    )
    monkeypatch.setattr(
        native_runtime_observation,
        "observe_native_runtime",
        lambda: pytest.fail("ready invoked deep native-runtime proof"),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ready")

    assert response.status_code == 200
    assert response.json()["schema_ok"] is True
    assert response.json()["integrity_verified"] is True
    assert response.json()["integrity_compromised"] is False


@pytest.mark.asyncio
async def test_ready_503_preserves_independent_organ_proofs(monkeypatch):
    monkeypatch.setattr(app.state, "graph_store", object(), raising=False)
    monkeypatch.setattr(
        health_router.persistence_contract_service,
        "evaluate",
        lambda _app: {"required": False, "pass_contract": True},
    )
    monkeypatch.setattr(health_router, "_check_schema", lambda: False)
    monkeypatch.setattr(
        health_router.audit_ledger_service,
        "verify_chain",
        lambda: SimpleNamespace(verified=True),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ready")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["failures"] == ["schema_check_failed"]
    assert detail["graph_store_ready"] is True
    assert detail["persistence_contract_ok"] is True
    assert detail["db_connected"] is True
    assert detail["schema_ok"] is False
    assert detail["integrity_verified"] is True
    assert detail["integrity_compromised"] is False


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
