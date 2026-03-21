import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health_status_and_uptime():
    """
    Verify GET /api/health returns status 'ok' and 'uptime_seconds' is a number.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://test"
    ) as client:
        response = await client.get("/api/health")
        
        # Verify status code is 200
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify status is 'ok'
        assert data["status"] == "ok"
        
        # Verify uptime_seconds is a number (int or float)
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        
        # Additional check as per request: specifically "is a number"
        # Since uptime_seconds is defined as int in the schema, it will be an int
        assert isinstance(data["uptime_seconds"], int)
