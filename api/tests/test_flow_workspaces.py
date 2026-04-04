"""Flow-centric tests for the Workspace tenant primitive.

Covers:
  - Workspace CRUD via the API (list / get / create / patch / pillars)
  - Layer 1 validation guardrails (workspace_not_found, pillar_not_in_workspace,
    parent_idea_cross_workspace, linked_idea_cross_workspace)
  - list_ideas workspace_id filter
  - WorkspaceResolver for default workspace (repo root fallback) vs custom
    workspaces (workspaces/{slug}/ bundle root)
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"
DEFAULT_WS = "coherence-network"


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_workspace_auto_ensured():
    """The default 'coherence-network' workspace is always available."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get(f"/api/workspaces/{DEFAULT_WS}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == DEFAULT_WS
        # Default workspace comes with the 6-pillar Coherence Network taxonomy.
        assert set(body["pillars"]) >= {
            "realization", "pipeline", "economics",
            "surfaces", "network", "foundation",
        }


@pytest.mark.asyncio
async def test_list_workspaces_includes_default():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/workspaces")
        assert r.status_code == 200, r.text
        ids = {ws["id"] for ws in r.json()}
        assert DEFAULT_WS in ids


@pytest.mark.asyncio
async def test_create_custom_workspace_and_get():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/workspaces", json={
            "id": ws_id,
            "name": "Test Project",
            "description": "Isolated tenant for testing.",
            "pillars": ["alpha", "beta", "gamma"],
            "visibility": "public",
        })
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["id"] == ws_id
        assert created["pillars"] == ["alpha", "beta", "gamma"]
        assert created["visibility"] == "public"

        r2 = await c.get(f"/api/workspaces/{ws_id}")
        assert r2.status_code == 200, r2.text
        assert r2.json()["name"] == "Test Project"


@pytest.mark.asyncio
async def test_create_duplicate_workspace_returns_409():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/workspaces", json={"id": ws_id, "name": "First"})
        assert r.status_code == 201, r.text
        r2 = await c.post("/api/workspaces", json={"id": ws_id, "name": "Second"})
        assert r2.status_code == 409, r2.text


@pytest.mark.asyncio
async def test_patch_workspace_updates_pillars():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/workspaces", json={
            "id": ws_id, "name": "Orig", "pillars": ["a"]
        })
        assert r.status_code == 201, r.text
        r2 = await c.patch(f"/api/workspaces/{ws_id}", json={
            "pillars": ["a", "b", "c"],
            "description": "Expanded taxonomy.",
        })
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["pillars"] == ["a", "b", "c"]
        assert body["description"] == "Expanded taxonomy."


@pytest.mark.asyncio
async def test_patch_nonexistent_workspace_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.patch(
            "/api/workspaces/does-not-exist",
            json={"name": "Nope"},
        )
        assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_get_workspace_pillars_endpoint():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/workspaces", json={
            "id": ws_id, "name": "Pil", "pillars": ["x", "y"]
        })
        r = await c.get(f"/api/workspaces/{ws_id}/pillars")
        assert r.status_code == 200, r.text
        assert r.json() == ["x", "y"]


# ---------------------------------------------------------------------------
# Layer 1 validation — idea creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_idea_in_unknown_workspace_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/ideas", json={
            "id": _uid("idea"),
            "name": "Stray",
            "description": "Belongs nowhere.",
            "potential_value": 10.0,
            "estimated_cost": 1.0,
            "confidence": 0.5,
            "workspace_id": "ghost-workspace",
        })
        assert r.status_code == 404, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "workspace_not_found"


@pytest.mark.asyncio
async def test_create_idea_with_pillar_outside_workspace_taxonomy_rejected():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/workspaces", json={
            "id": ws_id, "name": "Scoped", "pillars": ["alpha"]
        })
        r = await c.post("/api/ideas", json={
            "id": _uid("idea"),
            "name": "Wrong pillar",
            "description": "Claims pillar beta which isn't declared.",
            "potential_value": 10.0,
            "estimated_cost": 1.0,
            "confidence": 0.5,
            "workspace_id": ws_id,
            "pillar": "beta",
        })
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "pillar_not_in_workspace"
        assert "alpha" in detail["message"]


@pytest.mark.asyncio
async def test_create_idea_with_pillar_in_taxonomy_accepted():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/workspaces", json={
            "id": ws_id, "name": "Scoped", "pillars": ["alpha", "beta"]
        })
        r = await c.post("/api/ideas", json={
            "id": _uid("idea"),
            "name": "Good pillar",
            "description": "Uses alpha which is declared.",
            "potential_value": 10.0,
            "estimated_cost": 1.0,
            "confidence": 0.5,
            "workspace_id": ws_id,
            "pillar": "alpha",
        })
        assert r.status_code == 201, r.text
        assert r.json()["workspace_id"] == ws_id
        assert r.json()["pillar"] == "alpha"


@pytest.mark.asyncio
async def test_parent_idea_cross_workspace_rejected():
    ws_a = _uid("ws")
    ws_b = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/workspaces", json={"id": ws_a, "name": "A"})
        await c.post("/api/workspaces", json={"id": ws_b, "name": "B"})

        parent_id = _uid("parent")
        r = await c.post("/api/ideas", json={
            "id": parent_id,
            "name": "Parent",
            "description": "In workspace A.",
            "potential_value": 10.0, "estimated_cost": 1.0, "confidence": 0.5,
            "workspace_id": ws_a,
        })
        assert r.status_code == 201, r.text

        # Child attempts to live in workspace B while pointing at A's parent.
        r2 = await c.post("/api/ideas", json={
            "id": _uid("child"),
            "name": "Cross-tenant child",
            "description": "Wants parent from the other workspace.",
            "potential_value": 5.0, "estimated_cost": 1.0, "confidence": 0.5,
            "workspace_id": ws_b,
            "parent_idea_id": parent_id,
        })
        assert r2.status_code == 400, r2.text
        detail = r2.json()["detail"]
        assert detail["code"] == "parent_idea_cross_workspace"


@pytest.mark.asyncio
async def test_parent_idea_missing_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/ideas", json={
            "id": _uid("orphan"),
            "name": "Orphan",
            "description": "Parent is fictional.",
            "potential_value": 5.0, "estimated_cost": 1.0, "confidence": 0.5,
            "parent_idea_id": "does-not-exist-anywhere",
        })
        assert r.status_code == 404, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "parent_idea_not_found"


# ---------------------------------------------------------------------------
# list_ideas workspace_id filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_ideas_filtered_by_workspace():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/workspaces", json={"id": ws_id, "name": "Filter"})

        # Create one idea in the custom workspace.
        scoped_id = _uid("scoped")
        r = await c.post("/api/ideas", json={
            "id": scoped_id,
            "name": "In scoped workspace",
            "description": "Only in this workspace.",
            "potential_value": 10.0, "estimated_cost": 1.0, "confidence": 0.5,
            "workspace_id": ws_id,
        })
        assert r.status_code == 201, r.text

        # Create one idea in the default workspace.
        default_id = _uid("default")
        r2 = await c.post("/api/ideas", json={
            "id": default_id,
            "name": "In default workspace",
            "description": "Lives in the default workspace.",
            "potential_value": 10.0, "estimated_cost": 1.0, "confidence": 0.5,
        })
        assert r2.status_code == 201, r2.text

        # Filter to the custom workspace — only the scoped idea is present.
        r3 = await c.get(f"/api/ideas?workspace_id={ws_id}&limit=200")
        assert r3.status_code == 200, r3.text
        ids = {i["id"] for i in r3.json()["ideas"]}
        assert scoped_id in ids
        assert default_id not in ids

        # Filter to the default workspace — only the default idea is present.
        r4 = await c.get(f"/api/ideas?workspace_id={DEFAULT_WS}&limit=200")
        assert r4.status_code == 200, r4.text
        ids_default = {i["id"] for i in r4.json()["ideas"]}
        assert default_id in ids_default
        assert scoped_id not in ids_default


# ---------------------------------------------------------------------------
# list_specs workspace_id filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_specs_filtered_by_workspace():
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/workspaces", json={"id": ws_id, "name": "Specs"})

        # Create one spec in the custom workspace.
        scoped_spec = _uid("spec-scoped")
        r = await c.post("/api/spec-registry", headers=AUTH, json={
            "spec_id": scoped_spec,
            "title": "Scoped spec",
            "summary": "Lives in the custom workspace.",
            "workspace_id": ws_id,
        })
        assert r.status_code == 201, r.text

        # Create one spec in the default workspace.
        default_spec = _uid("spec-default")
        r2 = await c.post("/api/spec-registry", headers=AUTH, json={
            "spec_id": default_spec,
            "title": "Default spec",
            "summary": "Lives in the default workspace.",
        })
        assert r2.status_code == 201, r2.text

        # Filter to the custom workspace — only the scoped spec is present.
        r3 = await c.get(f"/api/spec-registry?workspace_id={ws_id}&limit=200")
        assert r3.status_code == 200, r3.text
        ids = {s["spec_id"] for s in r3.json()}
        assert scoped_spec in ids
        assert default_spec not in ids

        # Filter to the default workspace — only the default spec is present.
        r4 = await c.get(f"/api/spec-registry?workspace_id={DEFAULT_WS}&limit=200")
        assert r4.status_code == 200, r4.text
        ids_default = {s["spec_id"] for s in r4.json()}
        assert default_spec in ids_default
        assert scoped_spec not in ids_default

        # x-total-count header matches the filtered set.
        assert int(r3.headers["x-total-count"]) == 1
        # Default may have other specs from fixtures; at minimum it contains ours.
        assert int(r4.headers["x-total-count"]) >= 1


# ---------------------------------------------------------------------------
# WorkspaceResolver
# ---------------------------------------------------------------------------


def test_resolver_default_workspace_resolves_to_repo_root():
    from app.services.workspace_resolver import CoLocatedResolver
    from app.models.workspace import DEFAULT_WORKSPACE_ID

    resolver = CoLocatedResolver()
    root = resolver.get_bundle_root(DEFAULT_WORKSPACE_ID)
    # Default workspace bundle root is the repo root itself (legacy layout),
    # not workspaces/coherence-network/.
    assert (root / "specs").is_dir()
    assert (root / "ideas").is_dir()
    assert root.name != DEFAULT_WORKSPACE_ID


def test_resolver_custom_workspace_resolves_to_bundle_path(tmp_path: Path):
    from app.services.workspace_resolver import CoLocatedResolver

    resolver = CoLocatedResolver(repo_root=tmp_path)
    # Custom workspace bundle path is workspaces/{slug}/ under the repo root.
    assert resolver.get_bundle_root("team-x") == tmp_path / "workspaces" / "team-x"


def test_resolver_default_workspace_pillars_from_coherence_taxonomy():
    from app.services.workspace_resolver import (
        CoLocatedResolver,
        COHERENCE_NETWORK_PILLARS,
    )
    from app.models.workspace import DEFAULT_WORKSPACE_ID

    resolver = CoLocatedResolver()
    pillars = resolver.get_pillars(DEFAULT_WORKSPACE_ID)
    # Default workspace gets the 6-pillar taxonomy either from pillars.yaml
    # (when workspaces/coherence-network/pillars.yaml exists) or the hardcoded
    # fallback. Either way the full set is present.
    assert set(pillars) >= set(COHERENCE_NETWORK_PILLARS)


def test_resolver_custom_workspace_pillars_from_yaml(tmp_path: Path):
    from app.services.workspace_resolver import CoLocatedResolver

    bundle = tmp_path / "workspaces" / "team-x"
    bundle.mkdir(parents=True)
    (bundle / "pillars.yaml").write_text(
        "pillars:\n  - product\n  - infra\n  - research\n",
        encoding="utf-8",
    )

    resolver = CoLocatedResolver(repo_root=tmp_path)
    assert resolver.get_pillars("team-x") == ["product", "infra", "research"]


def test_resolver_custom_workspace_guide_loaded_from_bundle(tmp_path: Path):
    from app.services.workspace_resolver import CoLocatedResolver

    bundle = tmp_path / "workspaces" / "team-x" / "guides"
    bundle.mkdir(parents=True)
    (bundle / "contribution.md").write_text(
        "# Team X contribution rules\nDo not break prod.\n",
        encoding="utf-8",
    )

    resolver = CoLocatedResolver(repo_root=tmp_path)
    guide = resolver.get_guide("team-x", "contribution")
    assert guide is not None
    assert "Team X contribution rules" in guide


def test_resolver_missing_guide_returns_none(tmp_path: Path):
    from app.services.workspace_resolver import CoLocatedResolver

    resolver = CoLocatedResolver(repo_root=tmp_path)
    assert resolver.get_guide("nonexistent-ws", "onboarding") is None
