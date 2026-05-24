from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.routers import automation_usage as automation_usage_router
from app.main import app
from app.models.automation_usage import ProviderUsageOverview, ProviderUsageSnapshot, UsageMetric
from app.services import automation_usage_service


def test_finalize_snapshot_uses_summary_metric_for_usage_remaining() -> None:
    snapshot = ProviderUsageSnapshot(
        id="openai-runtime",
        provider="openai",
        kind="openai",
        status="ok",
        metrics=[
            UsageMetric(id="runtime_task_runs", label="Runtime runs", unit="tasks", used=12),
            UsageMetric(
                id="codex_subscription_5h",
                label="Codex 5h window",
                unit="hours",
                used=1,
                remaining=4,
                limit=5,
                validation_state="validated",
            ),
        ],
    )

    finalized = automation_usage_service._finalize_snapshot(snapshot)
    assert finalized.actual_current_usage == 12
    assert finalized.usage_remaining == 4
    assert finalized.usage_remaining_unit == "hours"


def test_automation_usage_endpoint_coalesces_provider_families() -> None:
    overview = ProviderUsageOverview(
        providers=[
            ProviderUsageSnapshot(id="openai", provider="openai", kind="openai", status="ok"),
            ProviderUsageSnapshot(id="codex", provider="openai-codex", kind="openai", status="ok"),
            ProviderUsageSnapshot(id="claude", provider="claude-code", kind="custom", status="ok"),
        ],
        tracked_providers=3,
    )

    coalesced = automation_usage_service.coalesce_usage_overview_families(overview)
    providers = {row.provider for row in coalesced.providers}
    assert providers == {"openai", "claude"}
    assert coalesced.tracked_providers == 2


@pytest.mark.asyncio
async def test_automation_usage_endpoint_times_out_to_snapshot_fallback(monkeypatch) -> None:
    async def timeout_wait_for(awaitable, timeout):
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(automation_usage_router.asyncio, "wait_for", timeout_wait_for)
    monkeypatch.setattr(
        automation_usage_service,
        "usage_overview_payload_from_snapshots",
        lambda compact=False, include_raw=False: {"providers": [], "tracked_providers": 0},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/automation/usage")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["data_source"] == "snapshot_fallback"
    assert body["meta"]["fallback_reason"] == "timeout"
