"""Integration tests: identity-driven-onboarding (TOFU MVP, OAuth upgrade later)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import auth_keys
from app.services.prompt_ab_roi_service import record_prompt_outcome
from app.services.unified_db import reset_engine


@pytest.fixture
def isolated_graph_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Fresh SQLite DB + graph for each test."""
    monkeypatch.setenv("PYTEST_ALLOW_DATABASE_URL", "1")
    dbfile = tmp_path / "onboard.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{dbfile}")
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    reset_engine()
    yield
    reset_engine()


@pytest.fixture
def clean_auth_stores():
    auth_keys._KEY_STORE.clear()
    auth_keys._CHALLENGES.clear()
    yield
    auth_keys._KEY_STORE.clear()
    auth_keys._CHALLENGES.clear()


@pytest.mark.asyncio
async def test_generate_api_key_creates_contributor(
    isolated_graph_db: None,
    clean_auth_stores: None,
) -> None:
    name = "u-onboard-001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/onboard",
            json={
                "name": name,
                "provider": "github",
                "provider_id": "gh-handle-001",
                "display_name": name,
            },
        )
    assert res.status_code == 201
    body = res.json()
    assert body["contributor_id"] == name
    assert body["api_key"].startswith(f"cc_{name}_")
    assert "scopes" in body


@pytest.mark.asyncio
async def test_whoami_returns_contributor_info(
    isolated_graph_db: None,
    clean_auth_stores: None,
) -> None:
    name = "u-whoami-002"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ob = await client.post(
            "/api/onboard",
            json={
                "name": name,
                "provider": "github",
                "provider_id": "gh-002",
                "display_name": name,
            },
        )
        key = ob.json()["api_key"]
        r = await client.get("/api/auth/whoami", headers={"X-API-Key": key})
    data = r.json()
    assert data["authenticated"] is True
    assert data["contributor_id"] == name
    assert "own:write" in data["scopes"]


@pytest.mark.asyncio
async def test_duplicate_contributor_is_idempotent(
    isolated_graph_db: None,
    clean_auth_stores: None,
) -> None:
    name = "u-dup-003"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/api/contributors",
            json={
                "name": name,
                "type": "HUMAN",
                "email": f"{name}@coherence.network",
            },
        )
        assert first.status_code == 201
        second = await client.post(
            "/api/contributors",
            json={
                "name": name,
                "type": "HUMAN",
                "email": f"{name}@coherence.network",
            },
        )
    assert second.status_code in (409, 422)
    assert second.status_code != 500


@pytest.mark.asyncio
async def test_key_format_matches_pattern(
    isolated_graph_db: None,
    clean_auth_stores: None,
) -> None:
    name = "u-fmt-004"
    pat = re.compile(r"^cc_[a-zA-Z0-9\-]+_[0-9a-f]{32}$")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/onboard",
            json={
                "name": name,
                "provider": "github",
                "provider_id": "x",
                "display_name": name,
            },
        )
    assert pat.match(res.json()["api_key"])


@pytest.mark.asyncio
async def test_scopes_include_required_permissions(
    isolated_graph_db: None,
    clean_auth_stores: None,
) -> None:
    required = {"own:read", "own:write", "contribute", "stake", "vote"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/onboard",
            json={
                "name": "u-scope-005",
                "provider": "github",
                "provider_id": "z",
                "display_name": "u-scope-005",
            },
        )
    scopes = set(res.json()["scopes"])
    assert required <= scopes


@pytest.mark.asyncio
async def test_verification_challenge_flow(
    isolated_graph_db: None,
    clean_auth_stores: None,
) -> None:
    name = "u-chal-006"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gh = await client.post(
            "/api/auth/verify/challenge",
            json={"contributor_id": name, "provider": "github"},
        )
        assert gh.status_code == 200
        ghb = gh.json()
        assert len(ghb.get("challenge", "")) >= 16
        assert "coherence-verify" in ghb.get("instructions", "")
        fake = await client.post(
            "/api/auth/verify/challenge",
            json={"contributor_id": name, "provider": "fakeprovider"},
        )
        assert fake.status_code == 200
        assert fake.status_code != 500


@pytest.mark.asyncio
async def test_tofu_identity_starts_unverified(
    isolated_graph_db: None,
    clean_auth_stores: None,
) -> None:
    name = "u-tofu-007"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/onboard",
            json={
                "name": name,
                "provider": "github",
                "provider_id": "tofu-user",
                "display_name": name,
            },
        )
        ident = await client.get(f"/api/identity/{name}")
    assert ident.status_code == 200
    rows = ident.json()
    assert isinstance(rows, list)
    gh = next((x for x in rows if x.get("provider") == "github"), None)
    assert gh is not None
    assert gh.get("verified") is False


def test_record_onboarding_roi_signal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Measurable ROI signal: TOFU MVP path beats OAuth-first on cost/velocity."""
    store = tmp_path / "slots.json"
    monkeypatch.setenv("PYTEST_ALLOW_DATABASE_URL", "1")
    out = record_prompt_outcome(
        "trust_on_first_use_mvp",
        "impl",
        value_score=0.85,
        resource_cost=1.0,
        task_id="task_25001d4cdd712213",
        raw_signals={"idea": "identity-driven-onboarding", "decision": "tofu_before_oauth"},
        store_path=store,
    )
    assert out.get("slot_id") == "trust_on_first_use_mvp"
    assert store.exists()
