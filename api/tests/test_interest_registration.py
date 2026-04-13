"""Flow-centric tests for interest registration — privacy-first community gathering.

Tests the full journey: register interest, verify privacy controls,
check community directory, and validate aggregate stats.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


class TestInterestRegistration:
    """Interest registration endpoints — POST /api/interest/register."""

    @pytest.mark.anyio
    async def test_register_basic(self, client: AsyncClient):
        """Register with minimal fields — name + email required."""
        res = await client.post("/api/interest/register", json={
            "name": "Luna",
            "email": "luna@example.com",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["id"].startswith("ip-")
        assert data["name"] == "Luna"
        # Email should NOT be in response
        assert "email" not in data

    @pytest.mark.anyio
    async def test_register_full(self, client: AsyncClient):
        """Register with all fields including roles and consent."""
        res = await client.post("/api/interest/register", json={
            "name": "Sol",
            "email": "sol@example.com",
            "location": "Colorado, USA",
            "skills": "Natural building, permaculture",
            "offering": "10 acres of mountain land",
            "resonant_roles": ["living-structure-weaver", "form-grower"],
            "message": "I've been dreaming of this for years",
            "consent_share_name": True,
            "consent_share_location": True,
            "consent_share_skills": True,
            "consent_findable": True,
            "consent_email_updates": True,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Sol"
        assert "living-structure-weaver" in data["resonant_roles"]
        assert "form-grower" in data["resonant_roles"]

    @pytest.mark.anyio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Registration with invalid email should fail."""
        res = await client.post("/api/interest/register", json={
            "name": "Test",
            "email": "not-an-email",
        })
        assert res.status_code == 422

    @pytest.mark.anyio
    async def test_register_empty_name(self, client: AsyncClient):
        """Registration with empty name should fail."""
        res = await client.post("/api/interest/register", json={
            "name": "",
            "email": "test@example.com",
        })
        assert res.status_code == 422

    @pytest.mark.anyio
    async def test_register_invalid_roles_filtered(self, client: AsyncClient):
        """Invalid roles should be silently filtered out."""
        res = await client.post("/api/interest/register", json={
            "name": "River",
            "email": "river@example.com",
            "resonant_roles": ["living-structure-weaver", "made-up-role", "another-fake"],
        })
        assert res.status_code == 200
        data = res.json()
        # Only valid role should remain
        assert data["resonant_roles"] == ["living-structure-weaver"]


class TestCommunityDirectory:
    """Community directory — consent-filtered listing."""

    @pytest.mark.anyio
    async def test_community_empty(self, client: AsyncClient):
        """Community directory returns list (may be empty for fresh DB)."""
        res = await client.get("/api/interest/community")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    @pytest.mark.anyio
    async def test_privacy_not_findable(self, client: AsyncClient):
        """Person who doesn't opt in to findable should not appear in directory."""
        # Register without findable consent
        await client.post("/api/interest/register", json={
            "name": "Shadow",
            "email": "shadow@example.com",
            "consent_findable": False,
        })
        res = await client.get("/api/interest/community")
        assert res.status_code == 200
        members = res.json()
        # Shadow should not appear
        names = [m["name"] for m in members]
        assert "Shadow" not in names

    @pytest.mark.anyio
    async def test_privacy_findable_appears(self, client: AsyncClient):
        """Person who opts in should appear in directory."""
        reg = await client.post("/api/interest/register", json={
            "name": "Beacon",
            "email": "beacon@example.com",
            "consent_share_name": True,
            "consent_findable": True,
        })
        person_id = reg.json()["id"]

        res = await client.get("/api/interest/community")
        assert res.status_code == 200
        members = res.json()
        found = [m for m in members if m["id"] == person_id]
        assert len(found) == 1
        assert found[0]["name"] == "Beacon"

    @pytest.mark.anyio
    async def test_privacy_name_hidden_when_not_consented(self, client: AsyncClient):
        """Person findable but name not consented should show as anonymous."""
        reg = await client.post("/api/interest/register", json={
            "name": "Secret",
            "email": "secret@example.com",
            "consent_share_name": False,
            "consent_findable": True,
        })
        person_id = reg.json()["id"]

        res = await client.get("/api/interest/community")
        members = res.json()
        found = [m for m in members if m["id"] == person_id]
        assert len(found) == 1
        assert found[0]["name"] == "A resonant soul"


class TestInterestStats:
    """Aggregate stats — no PII exposed."""

    @pytest.mark.anyio
    async def test_stats_structure(self, client: AsyncClient):
        """Stats endpoint returns expected shape."""
        res = await client.get("/api/interest/stats")
        assert res.status_code == 200
        data = res.json()
        assert "total_interested" in data
        assert "findable_count" in data
        assert "role_interest" in data
        assert "location_regions" in data


class TestRoles:
    """Available roles endpoint."""

    @pytest.mark.anyio
    async def test_list_roles(self, client: AsyncClient):
        """Should return 6 roles."""
        res = await client.get("/api/interest/roles")
        assert res.status_code == 200
        roles = res.json()
        assert len(roles) == 6
        slugs = {r["slug"] for r in roles}
        assert "living-structure-weaver" in slugs
        assert "frequency-holder" in slugs
