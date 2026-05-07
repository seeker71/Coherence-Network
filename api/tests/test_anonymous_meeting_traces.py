"""Anonymous meeting trace tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.mark.asyncio
async def test_anonymous_meeting_trace_remembers_source_surfaces_and_duration() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        first = await client.post(
            "/api/meetings/anonymous-traces",
            json={
                "visitor_key": "local-visitor-alpha",
                "session_key": "session-one",
                "surface": "/come-in",
                "duration_ms": 12000,
            },
        )
        assert first.status_code == 201, first.text
        first_body = first.json()
        source_point_id = first_body["source_point_id"]

        assert source_point_id.startswith("anon:")
        assert first_body["session"]["surface_count"] == 1
        assert first_body["session"]["duration_ms"] == 12000
        assert first_body["summary"]["meeting_count"] == 1
        assert first_body["summary"]["surfaces_met"] == ["/come-in"]
        assert first_body["session"]["raw_keys_stored"] is False

        second_surface = await client.post(
            "/api/meetings/anonymous-traces",
            json={
                "visitor_key": "local-visitor-alpha",
                "session_key": "session-one",
                "surface": "/vision",
                "duration_ms": 5000,
            },
        )
        assert second_surface.status_code == 201, second_surface.text
        session = second_surface.json()["session"]
        assert session["surface_count"] == 2
        assert session["duration_ms"] == 17000
        assert session["surfaces"] == [
            {"surface": "/come-in", "duration_ms": 12000},
            {"surface": "/vision", "duration_ms": 5000},
        ]

        returning = await client.post(
            "/api/meetings/anonymous-traces",
            json={
                "visitor_key": "local-visitor-alpha",
                "session_key": "session-two",
                "surface": "/with-us",
                "duration_ms": 3000,
                "contributor_id": "contributor:urs",
            },
        )
        assert returning.status_code == 201, returning.text
        returning_body = returning.json()
        assert returning_body["source_point_id"] == source_point_id
        assert returning_body["summary"]["meeting_count"] == 2
        assert returning_body["summary"]["total_duration_ms"] == 20000
        assert returning_body["summary"]["surfaces_met"] == ["/come-in", "/vision", "/with-us"]
        assert returning_body["summary"]["folded_into_contributor_id"] == "contributor:urs"

        listed = await client.get(
            "/api/meetings/anonymous-traces",
            params={"source_point_id": source_point_id},
        )
        assert listed.status_code == 200, listed.text
        listed_body = listed.json()
        assert listed_body["summary"]["meeting_count"] == 2
        assert listed_body["summary"]["folded_into_contributor_id"] == "contributor:urs"
        assert {row["session_id"] for row in listed_body["items"]} == {
            first_body["session"]["session_id"],
            returning_body["session"]["session_id"],
        }
