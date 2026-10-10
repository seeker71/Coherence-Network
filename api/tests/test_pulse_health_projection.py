"""The continuous pulse witness uses bounded health, not deep runtime proof."""

from types import SimpleNamespace

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
        lambda: SimpleNamespace(verified=True),
    )
    monkeypatch.setattr(health_router, "_check_schema", lambda: True)
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
    assert response.json() == {
        "status": "ok",
        "timestamp": response.json()["timestamp"],
        "schema_ok": True,
        "integrity_compromised": False,
        "integrity_verified": True,
        "recent_outcomes": {
            "last_1m": {"2xx": 3, "4xx": 0, "5xx": 0, "total": 3}
        },
    }


@pytest.mark.asyncio
async def test_pulse_health_projection_exposes_failed_integrity_verification(
    monkeypatch,
):
    def fail_verification():
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(
        health_router.audit_ledger_service,
        "verify_chain",
        fail_verification,
    )
    monkeypatch.setattr(health_router, "_check_schema", lambda: True)
    monkeypatch.setattr(health_router, "recent_outcomes_snapshot", lambda: None)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health/pulse")

    assert response.status_code == 200
    assert response.json()["integrity_verified"] is False
    assert response.json()["integrity_compromised"] is False
