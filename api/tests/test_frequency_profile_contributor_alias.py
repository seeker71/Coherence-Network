"""Contributor profile aliases resolve through the generic graph profile path."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_profile_accepts_bare_contributor_id_when_prefixed_node_exists():
    contributor_slug = _uid("alias-contributor")
    contributor_id = f"contributor:{contributor_slug}"
    concept_id = _uid("concept-profile-source")

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        contributor = await c.post(
            "/api/graph/nodes",
            json={
                "id": contributor_id,
                "type": "contributor",
                "name": "Contribution Alias",
                "description": (
                    "A source-backed contributor profile whose frequency should "
                    "derive from graph properties, contribution edges, and text."
                ),
                "properties": {
                    "contributor_type": "HUMAN",
                    "domains": ["contribution-graph"],
                    "keywords": ["attribution", "profile-derivation"],
                    "source_artifact_id": "docs/test/contribution-alias.md",
                    "extraction_method": "repo_manifest",
                    "ingestion_policy": "source_backed_profile_context",
                },
            },
        )
        assert contributor.status_code == 200, contributor.text

        concept = await c.post(
            "/api/graph/nodes",
            json={
                "id": concept_id,
                "type": "concept",
                "name": "Source-backed profile derivation",
                "description": "Profiles derive from source-backed graph data.",
                "properties": {
                    "domains": ["contribution-graph"],
                    "keywords": ["attribution"],
                },
            },
        )
        assert concept.status_code == 200, concept.text

        edge = await c.post(
            "/api/graph/edges",
            json={
                "from_id": contributor_id,
                "to_id": concept_id,
                "type": "inspires",
                "strength": 0.9,
                "created_by": "test",
            },
        )
        assert edge.status_code == 200, edge.text

        prefixed = await c.get(f"/api/profile/{contributor_id}")
        bare = await c.get(f"/api/profile/{contributor_slug}")

        assert prefixed.status_code == 200, prefixed.text
        assert bare.status_code == 200, bare.text
        prefixed_body = prefixed.json()
        bare_body = bare.json()
        assert bare_body["entity_id"] == contributor_id
        assert bare_body["hash"] == prefixed_body["hash"]
        dimensions = {row["dimension"] for row in bare_body["top"]}
        assert "_kw:attribution" in dimensions
        assert concept_id in dimensions
