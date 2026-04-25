"""Flow-centric tests for the Workspace tenant primitive.

Four flows cover the surface:

  · Workspace CRUD (list, create, get, patch, duplicate-409, 404)
  · Idea creation validation (unknown workspace, pillar not in
    taxonomy, parent cross-workspace, parent missing)
  · Cross-workspace filtering of ideas/specs/tasks
  · WorkspaceResolver (default vs custom bundle, pillars/guide loading)
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


@pytest.mark.asyncio
async def test_workspace_crud_flow():
    """Default workspace is always available; create → get → patch
    pillars + description → 409 on duplicate → 404 on unknown →
    pillars endpoint reflects the taxonomy."""
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Default workspace is auto-ensured with the 6-pillar taxonomy.
        default = await c.get(f"/api/workspaces/{DEFAULT_WS}")
        assert default.status_code == 200
        body = default.json()
        assert body["id"] == DEFAULT_WS
        assert set(body["pillars"]) >= {
            "realization", "pipeline", "economics",
            "surfaces", "network", "foundation",
        }

        # List includes the default.
        listed = await c.get("/api/workspaces")
        assert DEFAULT_WS in {ws["id"] for ws in listed.json()}

        # Create a custom workspace, read it back.
        created = await c.post("/api/workspaces", json={
            "id": ws_id, "name": "Test Project",
            "description": "Isolated tenant for testing.",
            "pillars": ["alpha", "beta", "gamma"],
            "visibility": "public",
        })
        assert created.status_code == 201, created.text
        cb = created.json()
        assert cb["id"] == ws_id and cb["pillars"] == ["alpha", "beta", "gamma"]
        assert cb["visibility"] == "public"
        got = await c.get(f"/api/workspaces/{ws_id}")
        assert got.status_code == 200 and got.json()["name"] == "Test Project"

        # Duplicate create → 409.
        dup = await c.post("/api/workspaces", json={"id": ws_id, "name": "Second"})
        assert dup.status_code == 409

        # Patch updates pillars + description.
        patched = await c.patch(f"/api/workspaces/{ws_id}", json={
            "pillars": ["alpha", "beta", "gamma", "delta"],
            "description": "Expanded taxonomy.",
        })
        assert patched.status_code == 200
        pb = patched.json()
        assert pb["pillars"] == ["alpha", "beta", "gamma", "delta"]
        assert pb["description"] == "Expanded taxonomy."

        # Patch nonexistent → 404.
        assert (await c.patch("/api/workspaces/does-not-exist",
                              json={"name": "Nope"})).status_code == 404

        # Pillars endpoint reflects current taxonomy.
        pillars = await c.get(f"/api/workspaces/{ws_id}/pillars")
        assert pillars.status_code == 200
        assert pillars.json() == ["alpha", "beta", "gamma", "delta"]


@pytest.mark.asyncio
async def test_workspace_idea_validation_flow():
    """Layer 1 validation: ideas rejected for unknown workspace,
    pillar outside taxonomy, parent in another workspace, parent
    missing. Valid pillar accepted."""
    ws_a = _uid("ws")
    ws_b = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/workspaces", json={
            "id": ws_a, "name": "Scoped", "pillars": ["alpha", "beta"],
        })
        await c.post("/api/workspaces", json={"id": ws_b, "name": "Other"})

        # Unknown workspace → 404 with workspace_not_found code.
        r1 = await c.post("/api/ideas", json={
            "id": _uid("idea"), "name": "Stray", "description": "Belongs nowhere.",
            "potential_value": 10.0, "estimated_cost": 1.0, "confidence": 0.5,
            "workspace_id": "ghost-workspace",
        })
        assert r1.status_code == 404
        assert r1.json()["detail"]["code"] == "workspace_not_found"

        # Pillar outside taxonomy → 400 with pillar_not_in_workspace.
        r2 = await c.post("/api/ideas", json={
            "id": _uid("idea"), "name": "Wrong pillar",
            "description": "Claims pillar gamma which isn't declared.",
            "potential_value": 10.0, "estimated_cost": 1.0, "confidence": 0.5,
            "workspace_id": ws_a, "pillar": "gamma",
        })
        assert r2.status_code == 400
        assert r2.json()["detail"]["code"] == "pillar_not_in_workspace"
        assert "alpha" in r2.json()["detail"]["message"]

        # Pillar in taxonomy → 201 accepted, carries both fields.
        parent_id = _uid("parent")
        r3 = await c.post("/api/ideas", json={
            "id": parent_id, "name": "Good pillar",
            "description": "Uses alpha which is declared.",
            "potential_value": 10.0, "estimated_cost": 1.0, "confidence": 0.5,
            "workspace_id": ws_a, "pillar": "alpha",
        })
        assert r3.status_code == 201
        assert r3.json()["workspace_id"] == ws_a and r3.json()["pillar"] == "alpha"

        # Child in workspace B pointing to parent in A → 400.
        r4 = await c.post("/api/ideas", json={
            "id": _uid("child"), "name": "Cross-tenant child",
            "description": "Wants parent from the other workspace.",
            "potential_value": 5.0, "estimated_cost": 1.0, "confidence": 0.5,
            "workspace_id": ws_b, "parent_idea_id": parent_id,
        })
        assert r4.status_code == 400
        assert r4.json()["detail"]["code"] == "parent_idea_cross_workspace"

        # Parent that doesn't exist anywhere → 404.
        r5 = await c.post("/api/ideas", json={
            "id": _uid("orphan"), "name": "Orphan",
            "description": "Parent is fictional.",
            "potential_value": 5.0, "estimated_cost": 1.0, "confidence": 0.5,
            "parent_idea_id": "does-not-exist-anywhere",
        })
        assert r5.status_code == 404
        assert r5.json()["detail"]["code"] == "parent_idea_not_found"


@pytest.mark.asyncio
async def test_workspace_cross_tenant_filter_flow():
    """Ideas, specs, and tasks filtered by ?workspace_id= return only
    items in that tenant; default workspace returns default items.
    All three surfaces share one tenant-isolation contract."""
    ws_id = _uid("ws")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/workspaces", json={
            "id": ws_id, "name": "Filter", "pillars": ["growth"],
        })

        # One idea per workspace.
        scoped_idea = _uid("scoped")
        r = await c.post("/api/ideas", json={
            "id": scoped_idea, "name": "Scoped idea", "description": "scoped",
            "potential_value": 10.0, "estimated_cost": 1.0, "confidence": 0.5,
            "workspace_id": ws_id, "pillar": "growth",
        })
        assert r.status_code == 201
        default_idea = _uid("default")
        r = await c.post("/api/ideas", json={
            "id": default_idea, "name": "Default idea", "description": "default",
            "potential_value": 10.0, "estimated_cost": 1.0, "confidence": 0.5,
        })
        assert r.status_code == 201

        scoped_ideas = {i["id"] for i in (await c.get(
            f"/api/ideas?workspace_id={ws_id}&limit=200")).json()["ideas"]}
        assert scoped_idea in scoped_ideas and default_idea not in scoped_ideas
        default_ideas = {i["id"] for i in (await c.get(
            f"/api/ideas?workspace_id={DEFAULT_WS}&limit=200")).json()["ideas"]}
        assert default_idea in default_ideas and scoped_idea not in default_ideas

        # One spec per workspace.
        scoped_spec = _uid("spec-scoped")
        assert (await c.post("/api/spec-registry", headers=AUTH, json={
            "spec_id": scoped_spec, "title": "Scoped spec",
            "summary": "Scoped.", "workspace_id": ws_id,
        })).status_code == 201
        default_spec = _uid("spec-default")
        assert (await c.post("/api/spec-registry", headers=AUTH, json={
            "spec_id": default_spec, "title": "Default spec",
            "summary": "Default.",
        })).status_code == 201

        scoped_specs_resp = await c.get(f"/api/spec-registry?workspace_id={ws_id}&limit=200")
        scoped_specs = {s["spec_id"] for s in scoped_specs_resp.json()}
        assert scoped_spec in scoped_specs and default_spec not in scoped_specs
        assert int(scoped_specs_resp.headers["x-total-count"]) == 1
        default_specs = {s["spec_id"] for s in (await c.get(
            f"/api/spec-registry?workspace_id={DEFAULT_WS}&limit=200")).json()}
        assert default_spec in default_specs and scoped_spec not in default_specs

        # Tasks (via idea_id → workspace_id lookup).
        scoped_task = (await c.post("/api/agent/tasks", headers=AUTH, json={
            "task_type": "impl", "direction": "Scoped task",
            "context": {"idea_id": scoped_idea},
        })).json()["id"]
        default_task = (await c.post("/api/agent/tasks", headers=AUTH, json={
            "task_type": "impl", "direction": "Default task",
            "context": {"idea_id": default_idea},
        })).json()["id"]

        scoped_tasks = {t["id"] for t in (await c.get(
            f"/api/agent/tasks?workspace_id={ws_id}&limit=100")).json()["tasks"]}
        assert scoped_task in scoped_tasks and default_task not in scoped_tasks
        default_tasks = {t["id"] for t in (await c.get(
            f"/api/agent/tasks?workspace_id={DEFAULT_WS}&limit=100")).json()["tasks"]}
        assert default_task in default_tasks and scoped_task not in default_tasks


def test_workspace_resolver_flow(tmp_path: Path):
    """WorkspaceResolver: default workspace lives at repo root (legacy
    layout, not workspaces/coherence-network/); custom workspaces
    live under workspaces/{slug}/. Pillars come from yaml when
    present, taxonomy fallback otherwise. Guides load from the
    bundle; missing guides return None."""
    from app.services.workspace_resolver import (
        CoLocatedResolver,
        COHERENCE_NETWORK_PILLARS,
    )
    from app.models.workspace import DEFAULT_WORKSPACE_ID

    # Default workspace resolves to repo root (specs/, ideas/).
    default_resolver = CoLocatedResolver()
    default_root = default_resolver.get_bundle_root(DEFAULT_WORKSPACE_ID)
    assert (default_root / "specs").is_dir()
    assert (default_root / "ideas").is_dir()
    assert default_root.name != DEFAULT_WORKSPACE_ID
    # Default gets the 6-pillar taxonomy (yaml or fallback).
    assert set(default_resolver.get_pillars(DEFAULT_WORKSPACE_ID)) >= set(COHERENCE_NETWORK_PILLARS)

    # Custom workspace resolves to workspaces/{slug}/.
    custom = CoLocatedResolver(repo_root=tmp_path)
    assert custom.get_bundle_root("team-x") == tmp_path / "workspaces" / "team-x"

    # Pillars loaded from pillars.yaml when present.
    (tmp_path / "workspaces" / "team-x").mkdir(parents=True)
    (tmp_path / "workspaces" / "team-x" / "pillars.yaml").write_text(
        "pillars:\n  - product\n  - infra\n  - research\n", encoding="utf-8",
    )
    assert custom.get_pillars("team-x") == ["product", "infra", "research"]

    # Guide loaded from bundle; missing guide → None.
    (tmp_path / "workspaces" / "team-x" / "guides").mkdir(parents=True)
    (tmp_path / "workspaces" / "team-x" / "guides" / "contribution.md").write_text(
        "# Team X contribution rules\nDo not break prod.\n", encoding="utf-8",
    )
    guide = custom.get_guide("team-x", "contribution")
    assert guide and "Team X contribution rules" in guide
    assert custom.get_guide("nonexistent-ws", "onboarding") is None
