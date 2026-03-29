"""Acceptance tests for the full traceability chain (full-traceability-chain idea).

Validates that machine-readable surfaces expose idea → spec → process → validation
linkage for API endpoints (GET /api/inventory/endpoint-traceability, spec 089) and
that meta self-discovery reports spec/idea coverage (GET /api/meta/summary).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import inventory_service


@pytest.mark.asyncio
async def test_inventory_endpoint_traceability_happy_path_exposes_chain_summary() -> None:
    """Full chain dimensions appear in summary; each item carries traceability gaps or fully_traced."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/endpoint-traceability")
    assert resp.status_code == 200
    payload = resp.json()

    assert "generated_at" in payload
    assert "summary" in payload
    assert "items" in payload
    summary = payload["summary"]
    for key in (
        "total_endpoints",
        "with_idea",
        "with_spec",
        "with_process",
        "with_validation",
        "fully_traced",
        "missing_idea",
        "missing_spec",
    ):
        assert key in summary

    assert summary["total_endpoints"] >= 1
    assert isinstance(summary["fully_traced"], int)
    assert summary["fully_traced"] <= summary["total_endpoints"]

    sample = next(iter(payload["items"]), None)
    assert sample is not None
    assert "path" in sample
    assert "traceability" in sample
    assert "fully_traced" in sample["traceability"]
    assert "gaps" in sample["traceability"]
    assert isinstance(sample["traceability"]["gaps"], list)


@pytest.mark.asyncio
async def test_meta_summary_reports_bounded_traceability_coverage() -> None:
    """Meta summary exposes traced_count and spec_coverage for endpoint↔spec/idea linkage."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["endpoint_count"] >= 1
    assert data["module_count"] >= 1
    assert 0 <= data["traced_count"] <= data["endpoint_count"]
    assert 0.0 <= data["spec_coverage"] <= 1.0


@pytest.mark.asyncio
async def test_endpoint_traceability_rejects_runtime_window_below_minimum() -> None:
    """Query validation error when runtime_window_seconds is below allowed range."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/inventory/endpoint-traceability",
            params={"runtime_window_seconds": 30},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_traceability_rejects_runtime_window_above_maximum() -> None:
    """Query validation error when runtime_window_seconds exceeds upper bound."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/inventory/endpoint-traceability",
            params={"runtime_window_seconds": 99999999},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_isolated_endpoints_without_evidence_show_traceability_gaps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When idea/spec/process signals are absent, fully_traced is false and gaps are listed."""
    monkeypatch.setattr(
        inventory_service,
        "_discover_api_endpoints_from_runtime",
        lambda: [],
    )
    monkeypatch.setattr(
        inventory_service,
        "_discover_api_endpoints_from_source",
        lambda: [
            {
                "path": "/api/only-in-test-chain",
                "methods": ["GET"],
                "source_files": ["api/app/routers/health.py"],
            },
        ],
    )
    monkeypatch.setattr(inventory_service, "_read_commit_evidence_records", lambda limit=1200: [])
    monkeypatch.setattr(inventory_service.runtime_service, "summarize_by_endpoint", lambda seconds=86400: [])
    monkeypatch.setattr(
        inventory_service.route_registry_service,
        "get_canonical_routes",
        lambda: {"api_routes": [], "web_routes": []},
    )
    monkeypatch.setattr(
        inventory_service.spec_registry_service,
        "list_specs",
        lambda limit=5000: [],
    )
    monkeypatch.setattr(
        inventory_service,
        "_discover_specs",
        lambda limit=2000: ([], "none"),
    )
    monkeypatch.setattr(
        inventory_service.idea_service,
        "list_ideas",
        lambda: SimpleNamespace(summary=SimpleNamespace(total_ideas=0)),
    )
    monkeypatch.setattr(
        inventory_service,
        "_discover_web_api_reference_evidence",
        lambda: [],
    )
    # Default resolver maps every /api path to a derived idea; disable so we can assert missing-idea gaps.
    monkeypatch.setattr(
        inventory_service.runtime_service,
        "resolve_idea_id",
        lambda endpoint, explicit_idea_id=None, method=None: "unmapped",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/endpoint-traceability")
    assert resp.status_code == 200
    payload = resp.json()
    row = next(r for r in payload["items"] if r["path"] == "/api/only-in-test-chain")
    assert row["traceability"]["fully_traced"] is False
    gaps = set(row["traceability"]["gaps"])
    assert "idea" in gaps
    assert "spec" in gaps
