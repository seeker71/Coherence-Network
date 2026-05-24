from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _handle(prefix: str = "tofu") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_register_returns_tofu_session_and_roi_shape() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        handle = _handle()
        response = await client.post("/api/onboarding/register", json={"handle": handle})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["handle"] == handle
        assert body["trust_level"] == "tofu"
        assert body["session_token"]
        assert body["roi_signals"]["spec_ref"] == "spec-168"


@pytest.mark.asyncio
async def test_invalid_handle_returns_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/onboarding/register", json={"handle": "no spaces"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_handle_returns_409() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        handle = _handle("dup")
        first = await client.post("/api/onboarding/register", json={"handle": handle})
        assert first.status_code == 200, first.text
        duplicate = await client.post("/api/onboarding/register", json={"handle": handle})
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "handle_taken"


@pytest.mark.asyncio
async def test_session_validates_bearer_token() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        handle = _handle("session")
        registration = (await client.post("/api/onboarding/register", json={"handle": handle})).json()
        session = await client.get(
            "/api/onboarding/session",
            headers={"Authorization": f"Bearer {registration['session_token']}"},
        )
        assert session.status_code == 200, session.text
        assert session.json()["handle"] == handle

        missing = await client.get("/api/onboarding/session")
        assert missing.status_code == 422

        invalid = await client.get(
            "/api/onboarding/session",
            headers={"Authorization": "Bearer invalid"},
        )
        assert invalid.status_code == 401


@pytest.mark.asyncio
async def test_upgrade_stub_and_roi_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        upgrade = await client.post(
            "/api/onboarding/upgrade",
            json={"contributor_id": "c1", "provider": "github", "provider_id": "u1"},
        )
        assert upgrade.status_code == 501
        assert upgrade.json()["detail"]["spec_ref"] == "spec-168"

        roi = await client.get("/api/onboarding/roi")
        assert roi.status_code == 200
        assert roi.json()["spec_ref"] == "spec-168"
