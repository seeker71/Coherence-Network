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
                "referrer_domain": "https://Example.org/path?invite=1",
            },
        )
        assert first.status_code == 201, first.text
        first_body = first.json()
        source_point_id = first_body["source_point_id"]

        assert source_point_id.startswith("anon:")
        assert first_body["session"]["surface_count"] == 1
        assert first_body["session"]["entry_surface"] == "/come-in"
        assert first_body["session"]["surface_sequence"] == ["/come-in"]
        assert first_body["session"]["page_count"] == 1
        assert first_body["session"]["duration_ms"] == 12000
        assert first_body["session"]["duration_bucket"] == "10s_to_1m"
        assert first_body["session"]["referrer_domain"] == "example.org"
        assert first_body["summary"]["meeting_count"] == 1
        assert first_body["summary"]["surfaces_met"] == ["/come-in"]
        assert first_body["summary"]["entry_surface"] == "/come-in"
        assert first_body["summary"]["surface_sequence"] == ["/come-in"]
        assert first_body["summary"]["page_count"] == 1
        assert first_body["summary"]["referrer_domains"] == ["example.org"]
        assert first_body["session"]["raw_keys_stored"] is False

        second_surface = await client.post(
            "/api/meetings/anonymous-traces",
            json={
                "visitor_key": "local-visitor-alpha",
                "session_key": "session-one",
                "surface": "/vision",
                "duration_ms": 5000,
                "referrer_domain": "docs.example.net/docs/start",
            },
        )
        assert second_surface.status_code == 201, second_surface.text
        session = second_surface.json()["session"]
        assert session["surface_count"] == 2
        assert session["entry_surface"] == "/come-in"
        assert session["surface_sequence"] == ["/come-in", "/vision"]
        assert session["page_count"] == 2
        assert session["duration_ms"] == 17000
        assert session["duration_bucket"] == "10s_to_1m"
        assert session["surfaces"] == [
            {"surface": "/come-in", "duration_ms": 12000, "referrer_domain": "example.org"},
            {"surface": "/vision", "duration_ms": 5000, "referrer_domain": "docs.example.net"},
        ]
        assert session["referrer_domains"] == ["example.org", "docs.example.net"]

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
        assert returning_body["summary"]["duration_bucket"] == "10s_to_1m"
        assert returning_body["summary"]["entry_surface"] == "/come-in"
        assert returning_body["summary"]["surfaces_met"] == ["/come-in", "/vision", "/with-us"]
        assert returning_body["summary"]["surface_sequence"] == ["/come-in", "/vision", "/with-us"]
        assert returning_body["summary"]["page_count"] == 3
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
