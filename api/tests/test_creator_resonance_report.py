from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.creator_resonance import (
    CreatorMetricSnapshot,
    CreatorPlatformSnapshot,
    CreatorResonanceReportRequest,
)
from app.services import creator_resonance_service

BASE = "http://test"


def test_creator_resonance_report_scores_multiple_dimensions() -> None:
    request = CreatorResonanceReportRequest(
        artist_name="Mira Sound",
        campaign_title="River Single",
        snapshots=[
            CreatorPlatformSnapshot(
                platform="Instagram",
                kind="baseline",
                metrics=CreatorMetricSnapshot(
                    reach=1000,
                    saves=20,
                    shares=10,
                    comments=5,
                    link_clicks=8,
                    followers=300,
                ),
                source_label="IG baseline export",
            ),
            CreatorPlatformSnapshot(
                platform="Instagram",
                kind="current",
                metrics=CreatorMetricSnapshot(
                    reach=2400,
                    saves=90,
                    shares=55,
                    comments=22,
                    link_clicks=70,
                    followers=360,
                ),
                source_label="IG current export",
            ),
            CreatorPlatformSnapshot(
                platform="Spotify",
                kind="baseline",
                metrics=CreatorMetricSnapshot(
                    listeners=200,
                    streams=900,
                    playlist_adds=6,
                    revenue_usd=0,
                ),
                source_label="Spotify baseline export",
            ),
            CreatorPlatformSnapshot(
                platform="Spotify",
                kind="current",
                metrics=CreatorMetricSnapshot(
                    listeners=460,
                    streams=2100,
                    playlist_adds=28,
                    saves=45,
                    revenue_usd=18.5,
                ),
                source_label="Spotify current export",
            ),
        ],
        costs=[],
        artifacts=[{"title": "River reel", "platform": "Instagram"}],
        desired_outcomes=["more listeners", "support revenue"],
    )

    report = creator_resonance_service.build_creator_resonance_report(
        request,
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    assert report.report_id.startswith("creator-resonance:")
    assert report.answer.can_generate_attention_value is True
    assert report.answer.can_validate_generation is True
    assert report.answer.can_show_income is True
    assert report.proof_quality == "strong"
    assert report.resonance_score > 0.20
    assert report.confidence >= 0.75
    assert report.attention_total == 2860
    assert report.engagement_total == 212
    assert report.conversion_total == 2198
    assert report.income_usd == 18.5
    assert report.platform_summaries[0].strongest_metric is not None
    assert any(item.name == "conversion" and item.lift > 1 for item in report.dimensions)
    assert not any("baseline" in gap.lower() for gap in report.evidence_gaps)


def test_creator_resonance_report_names_evidence_gaps() -> None:
    request = CreatorResonanceReportRequest(
        artist_name="No Baseline Artist",
        campaign_title="First Drop",
        snapshots=[
            CreatorPlatformSnapshot(
                platform="Instagram",
                kind="current",
                metrics=CreatorMetricSnapshot(reach=500, saves=10, link_clicks=5),
            )
        ],
    )

    report = creator_resonance_service.build_creator_resonance_report(request)

    assert report.answer.can_generate_attention_value is True
    assert report.answer.can_validate_generation is False
    assert report.proof_quality in {"thin", "unproven"}
    assert any("baseline" in gap.lower() for gap in report.evidence_gaps)
    assert any("income" in gap.lower() or "revenue" in gap.lower() for gap in report.evidence_gaps)


@pytest.mark.asyncio
async def test_creator_resonance_report_route() -> None:
    payload = {
        "artist_name": "Route Artist",
        "campaign_title": "Live Room",
        "snapshots": [
            {
                "platform": "Instagram",
                "kind": "baseline",
                "source_label": "manual baseline",
                "metrics": {"reach": 100, "saves": 3, "link_clicks": 1},
            },
            {
                "platform": "Instagram",
                "kind": "current",
                "source_label": "manual current",
                "metrics": {"reach": 900, "saves": 35, "link_clicks": 22},
            },
        ],
        "costs": [{"label": "boost", "amount_usd": 5}],
        "artifacts": [{"title": "Live clip", "artifact_type": "reel", "platform": "Instagram"}],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post("/api/creator-economy/resonance-report", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["artist_name"] == "Route Artist"
    assert body["answer"]["can_generate_attention_value"] is True
    assert body["cost_usd"] == 5
    assert body["net_income_usd"] == -5
    assert body["platform_summaries"][0]["platform"] == "instagram"
    assert body["validation_plan"]
