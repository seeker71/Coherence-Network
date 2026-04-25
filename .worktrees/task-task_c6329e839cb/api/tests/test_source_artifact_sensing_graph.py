"""Source artifact -> sensing -> concept graph integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import graph_service

BASE = "http://test"


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_source_artifact_sensing_creates_provenance_edge_and_profile():
    artifact_id = _uid("artifact-source")
    concept_id = _uid("concept-gestational-field")

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        artifact = await c.post(
            "/api/graph/nodes",
            json={
                "id": artifact_id,
                "type": "artifact",
                "name": "Peace Bathing source summary",
                "description": "Summary-only source artifact for extracted concepts.",
                "properties": {
                    "artifact_kind": "transcript_summary_pdf",
                    "source_uri": "/Users/ursmuff/Downloads/20260419_Transcript___Summary_Peace_Bathing_Session_04_19_26.pdf",
                    "source_sha256": "sha256:example",
                    "rights": "external_copyrighted_source",
                    "ingestion_policy": "summary_and_extracted_concepts_only",
                    "language": "en",
                },
            },
        )
        assert artifact.status_code == 200, artifact.text

        concept = await c.post(
            "/api/graph/nodes",
            json={
                "id": concept_id,
                "type": "concept",
                "name": "Gestational Field",
                "description": "A generic holding state where potential becomes form.",
                "properties": {
                    "domains": ["idea-lifecycle", "resonance"],
                    "keywords": ["incubation", "becoming", "readiness"],
                },
            },
        )
        assert concept.status_code == 200, concept.text

        sensing = await c.post(
            "/api/sensings",
            json={
                "kind": "wandering",
                "summary": "Spark, gestation, release, and belonging pattern.",
                "content": "Summary-only reflection that extracts reusable graph concepts without storing the transcript body.",
                "source": "local_pdf_ingestion",
                "related_to": [concept_id],
                "metadata": {
                    "source_artifact_id": artifact_id,
                    "extraction_method": "manual_summary",
                    "ingestion_policy": "summary_and_extracted_concepts_only",
                    "quote_policy": "no_full_text_republication",
                    "confidence": 0.82,
                    "edge_rationales": {
                        concept_id: "The source frames becoming as a held field before form."
                    },
                },
            },
        )
        assert sensing.status_code == 201, sensing.text
        sensing_body = sensing.json()

        edges = await c.get(
            f"/api/graph/nodes/{sensing_body['id']}/edges",
            params={"direction": "outgoing", "type": "analogous-to"},
        )
        assert edges.status_code == 200, edges.text
        edge_rows = [row for row in edges.json() if row["to_id"] == concept_id]
        assert len(edge_rows) == 1
        provenance = edge_rows[0]["properties"]
        assert provenance["source_artifact_id"] == artifact_id
        assert provenance["sensing_id"] == sensing_body["id"]
        assert provenance["extraction_method"] == "manual_summary"
        assert provenance["confidence"] == 0.82
        assert provenance["ingestion_policy"] == "summary_and_extracted_concepts_only"
        assert "held field" in provenance["rationale"]

        # Multi-view profile — categorical view carries sensing provenance
        # as IDF-weighted features (source_artifact, provenance, ingestion_policy).
        profile = await c.get(f"/api/profile/{sensing_body['id']}")
        assert profile.status_code == 200, profile.text
        body = profile.json()
        assert "views" in body
        dim_keys = {d["dimension"] for d in body["top"]}
        assert f"_source_artifact:{artifact_id}" in dim_keys
        assert "_provenance:source_backed" in dim_keys
        assert "_ingestion_policy:summary_and_extracted_concepts_only" in dim_keys


def test_provenance_edge_helper_rejects_incomplete_metadata():
    source = graph_service.create_node(
        id=_uid("sensing"),
        type="event",
        name="Test sensing",
        properties={"sensing_kind": "wandering"},
    )
    target = graph_service.create_node(
        id=_uid("concept"),
        type="concept",
        name="Test concept",
        properties={},
    )

    with pytest.raises(ValueError, match="source_artifact_id"):
        graph_service.create_provenance_edge(
            from_id=source["id"],
            to_id=target["id"],
            type="analogous-to",
            provenance={
                "sensing_id": source["id"],
                "extraction_method": "manual_summary",
                "confidence": 0.7,
                "ingestion_policy": "summary_and_extracted_concepts_only",
                "rationale": "Missing artifact id should fail.",
            },
        )
