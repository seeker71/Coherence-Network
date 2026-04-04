import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


@pytest.mark.asyncio
async def test_get_providers_returns_available_execution_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_service,
        "list_available_task_execution_providers",
        lambda: ["openrouter", "cursor"],
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/providers")

    assert response.status_code == 200
    assert response.json() == {
        "providers": [
            {"id": "openrouter"},
            {"id": "cursor"},
        ]
    }
