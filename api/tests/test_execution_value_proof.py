from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.cc_economics import CCExchangeRate
from app.models.value_lineage import UsageEvent
from app.services import execution_value_proof_service

BASE = "http://test"


def test_grounded_value_summary_uses_measured_metrics() -> None:
    data = {
        "specs": [
            {
                "idea_id": "nutrition-loop",
                "actual_cost": 2.0,
                "actual_value": 9.5,
                "estimated_cost": 3.0,
                "potential_value": 20.0,
            }
        ],
        "runtime_summaries": [],
        "lineage_links": [],
        "lineage_valuations": {},
        "commit_records": [],
        "friction_events": [],
    }

    summary = execution_value_proof_service.summarize_grounded_value(
        ["nutrition-loop"],
        data,
    )

    assert summary.ideas_count == 1
    assert summary.ideas_with_value == 1
    assert summary.measured_value_usd == 9.5
    assert summary.measured_cost_usd == 2.0
    assert summary.net_value_usd == 7.5
    assert summary.roi_ratio == 4.75
    assert summary.top_ideas[0].idea_id == "nutrition-loop"


def test_paid_read_cc_is_income_but_not_spendable_fiat() -> None:
    paid_event = UsageEvent(
        id="evt-paid",
        lineage_id="asset:guide",
        source="read",
        metric="reads",
        value=12.0,
        asset_id="guide",
        reader_id="reader",
        read_type="paid",
        cc_amount=12.0,
        payment_token="x402:test",
        captured_at=datetime.now(timezone.utc),
    )

    income = execution_value_proof_service.summarize_income(
        paid_events=[paid_event],
        settled_cc=0.0,
        cc_per_usd=4.0,
    )

    assert income.income_proven is True
    assert income.spendable_income_proven is False
    assert income.proof_level == "paid_read_cc_measured"
    assert income.paid_read_count == 1
    assert income.paid_read_cc == 12.0
    assert income.estimated_paid_read_usd == 3.0
    assert income.spendable_fiat_usd == 0.0


@pytest.mark.asyncio
async def test_execution_value_proof_route_composes_measured_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    paid_event = UsageEvent(
        id="evt-route",
        lineage_id="asset:route-guide",
        source="read",
        metric="reads",
        value=8.0,
        asset_id="route-guide",
        reader_id="reader-route",
        read_type="paid",
        cc_amount=8.0,
        payment_token="x402:route",
        captured_at=now,
    )

    monkeypatch.setattr(
        execution_value_proof_service.grounded_idea_metrics_service,
        "collect_all_data",
        lambda: {
            "specs": [
                {
                    "idea_id": "route-proof",
                    "actual_cost": 1.5,
                    "actual_value": 6.0,
                    "estimated_cost": 2.0,
                    "potential_value": 10.0,
                }
            ],
            "runtime_summaries": [],
            "lineage_links": [],
            "lineage_valuations": {},
            "commit_records": [],
            "friction_events": [],
        },
    )
    monkeypatch.setattr(
        execution_value_proof_service.idea_service,
        "list_tracked_idea_ids",
        lambda: ["route-proof"],
    )
    monkeypatch.setattr(
        execution_value_proof_service.value_lineage_service,
        "query_read_events",
        lambda **_kwargs: [paid_event],
    )
    monkeypatch.setattr(
        execution_value_proof_service.cc_economics_service,
        "exchange_rate",
        lambda: CCExchangeRate(
            cc_per_usd=4.0,
            spread_pct=0.0,
            buy_rate=4.0,
            sell_rate=4.0,
            oracle_source="test",
        ),
    )
    monkeypatch.setattr(
        execution_value_proof_service.metrics_service,
        "get_aggregates",
        lambda window_days=None: {
            "success_rate": {"completed": 3, "failed": 1, "total": 4, "rate": 0.75},
            "execution_time": {"p50_seconds": 11, "p95_seconds": 24},
        },
    )
    monkeypatch.setattr(
        execution_value_proof_service.agent_service,
        "list_tasks",
        lambda **_kwargs: ([], 0, 0),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.get(
            "/api/execution/value-proof",
            params={"window_days": 30, "daily_nutrition_usd": 2.0},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"]["can_generate_value_with_execution"] is True
    assert body["answer"]["can_prove_income"] is True
    assert body["answer"]["can_cover_nutrition"] is False
    assert body["answer"]["status"] == "paid_cc_income_proven_offramp_needed"
    assert body["execution"]["completed"] == 3
    assert body["execution"]["p95_seconds"] == 24
    assert body["value"]["measured_value_usd"] == 6.0
    assert body["income"]["paid_read_cc"] == 8.0
    assert body["income"]["estimated_paid_read_usd"] == 2.0
    assert body["income"]["spendable_fiat_usd"] == 0.0
    assert body["nutrition"]["covered_days_by_estimated_cc"] == 1.0
