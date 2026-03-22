import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok_with_required_fields() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"

    required_fields = [
        "status",
        "version",
        "timestamp",
        "started_at",
        "uptime_seconds",
        "uptime_human",
    ]
    for field in required_fields:
        assert field in payload

    assert isinstance(payload["version"], str)
    assert isinstance(payload["timestamp"], str)
    assert isinstance(payload["started_at"], str)
    assert isinstance(payload["uptime_seconds"], int)
    assert isinstance(payload["uptime_human"], str)
