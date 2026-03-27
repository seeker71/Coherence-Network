"""Acceptance tests for UX Ideas Hierarchy View (idea: ux-ideas-hierarchy-view).

Spec reference: `specs/117-idea-hierarchy-super-child.md` — follow-up
"Visual hierarchy in web UI (/ideas page tree view)". The web page consumes
`GET /api/ideas`; these tests lock the API contract and parent/child consistency
needed to render a hierarchy without a flat-only list.

No mocks — real FastAPI app + isolated portfolio file (same pattern as test_ideas.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


def _hierarchy_keys_present(idea: dict[str, Any]) -> bool:
    return (
        "idea_type" in idea
        and "parent_idea_id" in idea
        and "child_idea_ids" in idea
    )


def build_idea_forest(ideas: list[dict[str, Any]]) -> tuple[list[str], dict[str, list[str]]]:
    """Derive roots and adjacency the way a /ideas tree view would.

    Roots: ideas whose parent_idea_id is missing, empty, or points to an id
    not in this response (strategic parents may be filtered or omitted).
    Children map: parent_id -> ordered list of child ids (by first-seen order).
    """
    ids = {i["id"] for i in ideas}
    roots: list[str] = []
    children: dict[str, list[str]] = {}

    for idea in ideas:
        iid = idea["id"]
        raw_parent = idea.get("parent_idea_id")
        pid = raw_parent if isinstance(raw_parent, str) and raw_parent.strip() else None
        if pid is None or pid not in ids:
            roots.append(iid)
        else:
            children.setdefault(pid, []).append(iid)

    return roots, children


def forest_has_cycle(ideas: list[dict[str, Any]]) -> bool:
    """Return True if following parent_idea_id links among *this* payload forms a cycle."""
    by_id = {i["id"]: i for i in ideas}
    for start_id in by_id:
        seen: set[str] = set()
        cur: str | None = start_id
        steps = 0
        while cur is not None and cur in by_id and steps <= len(by_id) + 1:
            if cur in seen:
                return True
            seen.add(cur)
            p = by_id[cur].get("parent_idea_id")
            cur = p if isinstance(p, str) and p.strip() else None
            steps += 1
    return False


@pytest.mark.asyncio
async def test_get_ideas_includes_hierarchy_fields_for_tree_view(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every idea in GET /api/ideas exposes hierarchy fields for the UX tree."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": "ux-hier-root",
                "name": "Root",
                "description": "Portfolio root for hierarchy UX contract test.",
                "potential_value": 40.0,
                "estimated_cost": 5.0,
                "confidence": 0.7,
                "idea_type": "standalone",
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201

        resp = await client.get("/api/ideas")
    assert resp.status_code == 200
    data = resp.json()
    assert "ideas" in data
    for idea in data["ideas"]:
        assert _hierarchy_keys_present(idea), idea


@pytest.mark.asyncio
async def test_super_and_child_ideas_round_trip_parent_links(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Super idea lists children; each child references the super as parent (spec 117 UX)."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_super = await client.post(
            "/api/ideas",
            json={
                "id": "ux-hier-super",
                "name": "Strategic super",
                "description": "Non-actionable umbrella.",
                "potential_value": 100.0,
                "estimated_cost": 20.0,
                "confidence": 0.8,
                "idea_type": "super",
                "child_idea_ids": ["ux-hier-child-a", "ux-hier-child-b"],
            },
            headers=AUTH_HEADERS,
        )
        assert r_super.status_code == 201

        for cid, title in (
            ("ux-hier-child-a", "Child A"),
            ("ux-hier-child-b", "Child B"),
        ):
            r_child = await client.post(
                "/api/ideas",
                json={
                    "id": cid,
                    "name": title,
                    "description": "Actionable sub-idea.",
                    "potential_value": 25.0,
                    "estimated_cost": 8.0,
                    "confidence": 0.75,
                    "idea_type": "child",
                    "parent_idea_id": "ux-hier-super",
                },
                headers=AUTH_HEADERS,
            )
            assert r_child.status_code == 201

        resp = await client.get("/api/ideas")
    assert resp.status_code == 200
    ideas = resp.json()["ideas"]
    by_id = {i["id"]: i for i in ideas}

    super_row = by_id["ux-hier-super"]
    assert super_row["idea_type"] == "super"
    assert set(super_row["child_idea_ids"]) == {"ux-hier-child-a", "ux-hier-child-b"}

    for cid in ("ux-hier-child-a", "ux-hier-child-b"):
        row = by_id[cid]
        assert row["idea_type"] == "child"
        assert row["parent_idea_id"] == "ux-hier-super"


@pytest.mark.asyncio
async def test_get_idea_by_id_includes_hierarchy_for_detail_panel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Detail route returns the same hierarchy fields as the list (drill-down from tree)."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "ux-hier-detail-child",
                "name": "Detail child",
                "description": "Child for GET by id.",
                "potential_value": 12.0,
                "estimated_cost": 3.0,
                "confidence": 0.6,
                "idea_type": "child",
                "parent_idea_id": "ux-hier-detail-super",
            },
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/ideas",
            json={
                "id": "ux-hier-detail-super",
                "name": "Detail super",
                "description": "Parent for detail view.",
                "potential_value": 50.0,
                "estimated_cost": 10.0,
                "confidence": 0.7,
                "idea_type": "super",
                "child_idea_ids": ["ux-hier-detail-child"],
            },
            headers=AUTH_HEADERS,
        )

        one = await client.get("/api/ideas/ux-hier-detail-child")
    assert one.status_code == 200
    body = one.json()
    assert body["idea_type"] == "child"
    assert body["parent_idea_id"] == "ux-hier-detail-super"
    assert _hierarchy_keys_present(body)


def test_build_idea_forest_groups_children_under_parent() -> None:
    """Forest builder used by tree UX: two children nest under one parent."""
    ideas = [
        {
            "id": "p",
            "idea_type": "super",
            "parent_idea_id": None,
            "child_idea_ids": ["c1", "c2"],
            "free_energy_score": 5.0,
            "value_gap": 1.0,
            "marginal_cc_score": 0.0,
            "selection_weight": 0.0,
            "remaining_cost_cc": 0.0,
            "value_gap_cc": 0.0,
            "roi_cc": 0.0,
        },
        {
            "id": "c1",
            "idea_type": "child",
            "parent_idea_id": "p",
            "child_idea_ids": [],
            "free_energy_score": 3.0,
            "value_gap": 1.0,
            "marginal_cc_score": 0.0,
            "selection_weight": 0.0,
            "remaining_cost_cc": 0.0,
            "value_gap_cc": 0.0,
            "roi_cc": 0.0,
        },
        {
            "id": "c2",
            "idea_type": "child",
            "parent_idea_id": "p",
            "child_idea_ids": [],
            "free_energy_score": 2.0,
            "value_gap": 1.0,
            "marginal_cc_score": 0.0,
            "selection_weight": 0.0,
            "remaining_cost_cc": 0.0,
            "value_gap_cc": 0.0,
            "roi_cc": 0.0,
        },
    ]
    roots, ch = build_idea_forest(ideas)
    assert "p" in roots
    assert set(ch["p"]) == {"c1", "c2"}


def test_forest_detects_parent_cycle() -> None:
    """If payload ever contained a cycle, the UX must not infinite-loop — detectable."""
    ideas = [
        {"id": "a", "parent_idea_id": "b"},
        {"id": "b", "parent_idea_id": "a"},
    ]
    assert forest_has_cycle(ideas) is True


def test_forest_no_cycle_for_linear_chain() -> None:
    ideas = [
        {"id": "root", "parent_idea_id": None},
        {"id": "leaf", "parent_idea_id": "root"},
    ]
    assert forest_has_cycle(ideas) is False
