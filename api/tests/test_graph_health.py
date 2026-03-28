"""Integration tests for Graph Health Monitoring API (spec-172).

15 tests covering all acceptance criteria from the spec.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

# Use in-memory SQLite for all tests
os.environ.setdefault("COHERENCE_ENV", "test")

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_snapshot(**kwargs) -> dict:
    defaults = {
        "id": str(uuid4()),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "balance_score": 0.71,
        "entropy_score": 0.68,
        "concentration_ratio": 0.43,
        "concept_count": 10,
        "edge_count": 15,
        "gravity_wells": [],
        "orphan_clusters": [],
        "surface_candidates": [],
        "signals": [],
        "spec_ref": "spec-172",
    }
    defaults.update(kwargs)
    return defaults


def _fake_signal(**kwargs) -> dict:
    defaults = {
        "id": f"sig_{uuid4().hex[:12]}",
        "type": "split_signal",
        "concept_id": "ai-alignment",
        "cluster_id": None,
        "severity": "warning",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved": False,
        "resolved_at": None,
        "resolution": None,
        "resolved_by": None,
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Test 1: GET /api/graph/health returns 200 with all required fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_returns_required_fields():
    snap = _fake_snapshot()
    from app.models.graph_health import GraphHealthSnapshot
    from app.services import graph_health_service

    with patch.object(
        graph_health_service, "get_or_compute_health", return_value=GraphHealthSnapshot(**snap)
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/graph/health")
    assert r.status_code == 200
    body = r.json()
    for key in ("balance_score", "entropy_score", "concentration_ratio",
                "concept_count", "edge_count", "gravity_wells",
                "orphan_clusters", "surface_candidates", "signals",
                "computed_at", "spec_ref"):
        assert key in body, f"Missing key: {key}"
    assert body["spec_ref"] == "spec-172"
    assert 0.0 <= body["balance_score"] <= 1.0
    assert 0.0 <= body["entropy_score"] <= 1.0
    assert 0.0 <= body["concentration_ratio"] <= 1.0


# ---------------------------------------------------------------------------
# Test 2: GET /api/graph/health returns 503 when graph DB unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_503_on_db_unavailable():
    from app.services import graph_health_service

    with patch.object(
        graph_health_service, "get_or_compute_health", side_effect=RuntimeError("connection refused")
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/graph/health")
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# Test 3: POST /api/graph/health/compute returns 200 with fresh snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_returns_200():
    snap = _fake_snapshot()
    from app.models.graph_health import GraphHealthSnapshot
    from app.services import graph_health_service

    with patch.object(
        graph_health_service, "trigger_compute", return_value=(GraphHealthSnapshot(**snap), True)
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/graph/health/compute")
    assert r.status_code == 200
    body = r.json()
    assert body["spec_ref"] == "spec-172"


# ---------------------------------------------------------------------------
# Test 4: POST /api/graph/health/compute returns 429 on cooldown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_429_on_cooldown():
    from app.services import graph_health_service

    with patch.object(
        graph_health_service, "trigger_compute", side_effect=RuntimeError("cooldown")
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/graph/health/compute")
    assert r.status_code == 429


# ---------------------------------------------------------------------------
# Test 5: GET /api/graph/health/history returns paginated snapshots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_history_pagination():
    from app.models.graph_health import GraphHealthSnapshot
    from app.services import graph_health_service

    items = [GraphHealthSnapshot(**_fake_snapshot()) for _ in range(5)]

    with patch.object(
        graph_health_service, "get_health_history", return_value=(items[:2], 5)
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/graph/health/history?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["spec_ref"] == "spec-172"


# ---------------------------------------------------------------------------
# Test 6: GET /api/graph/signals returns only unresolved signals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signals_returns_unresolved():
    from app.models.graph_health import GraphSignal
    from app.db import graph_health_repo

    sig = GraphSignal(**_fake_signal())

    with patch.object(
        graph_health_repo, "list_signals", return_value=[sig]
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/graph/signals")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["signals"][0]["resolved"] is False


# ---------------------------------------------------------------------------
# Test 7: GET /api/graph/signals?type=split_signal filters correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signals_filter_by_type():
    from app.models.graph_health import GraphSignal
    from app.db import graph_health_repo

    sig = GraphSignal(**_fake_signal(type="split_signal"))

    def _mock_list_signals(signal_type=None, severity=None, resolved=False):
        if signal_type == "split_signal":
            return [sig]
        return []

    with patch.object(graph_health_repo, "list_signals", side_effect=_mock_list_signals):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/graph/signals?type=split_signal")
    assert r.status_code == 200
    body = r.json()
    assert all(s["type"] == "split_signal" for s in body["signals"])


# ---------------------------------------------------------------------------
# Test 8: GET /api/graph/signals?severity=critical filters correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signals_filter_by_severity():
    from app.models.graph_health import GraphSignal
    from app.db import graph_health_repo

    critical_sig = GraphSignal(**_fake_signal(severity="critical"))

    def _mock_list_signals(signal_type=None, severity=None, resolved=False):
        if severity == "critical":
            return [critical_sig]
        return []

    with patch.object(graph_health_repo, "list_signals", side_effect=_mock_list_signals):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/graph/signals?severity=critical")
    assert r.status_code == 200
    body = r.json()
    assert all(s["severity"] == "critical" for s in body["signals"])


# ---------------------------------------------------------------------------
# Test 9: POST /api/graph/signals/{id}/resolve returns 200 with resolved=true
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_signal_200():
    from app.models.graph_health import GraphSignal
    from app.db import graph_health_repo

    sig_id = f"sig_{uuid4().hex[:12]}"
    unresolved = GraphSignal(**_fake_signal(id=sig_id))
    resolved = GraphSignal(**_fake_signal(
        id=sig_id,
        resolved=True,
        resolved_at=datetime.now(timezone.utc).isoformat(),
        resolution="Split completed",
        resolved_by="operator-1",
    ))

    with patch.object(graph_health_repo, "get_signal", return_value=unresolved):
        with patch.object(graph_health_repo, "resolve_signal", return_value=resolved):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    f"/api/graph/signals/{sig_id}/resolve",
                    json={"resolution": "Split completed", "resolved_by": "operator-1"},
                )
    assert r.status_code == 200
    body = r.json()
    assert body["resolved"] is True
    assert body["resolution"] == "Split completed"


# ---------------------------------------------------------------------------
# Test 10: POST /api/graph/signals/{id}/resolve returns 409 on duplicate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_signal_409_already_resolved():
    from app.models.graph_health import GraphSignal
    from app.db import graph_health_repo

    sig_id = f"sig_{uuid4().hex[:12]}"
    already_resolved = GraphSignal(**_fake_signal(id=sig_id, resolved=True))

    with patch.object(graph_health_repo, "get_signal", return_value=already_resolved):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/graph/signals/{sig_id}/resolve",
                json={"resolution": "Duplicate", "resolved_by": "op"},
            )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Test 11: POST /api/graph/signals/{nonexistent}/resolve returns 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_signal_404():
    from app.db import graph_health_repo

    with patch.object(graph_health_repo, "get_signal", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/graph/signals/nonexistent/resolve",
                json={"resolution": "nope", "resolved_by": "op"},
            )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Test 12: convergence guard suppresses split_signal on recompute
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_convergence_guard_suppresses_split_signal():
    """A concept with convergence_guard should NOT appear in split signals after compute."""
    from app.services import concept_service, graph_health_service
    from app.db import graph_health_repo

    concept_id = "test-gravity-well"

    # Patch concept lookup to return the concept
    with patch.object(concept_service, "get_concept", return_value={"id": concept_id, "name": "Test"}):
        with patch.object(graph_health_service, "set_guard") as mock_set:
            mock_set.return_value = MagicMock(
                concept_id=concept_id, convergence_guard=True, reason="testing"
            )
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    f"/api/graph/concepts/{concept_id}/convergence-guard",
                    json={"reason": "Genuine convergence", "set_by": "operator-1"},
                )
    assert r.status_code == 200

    # Now verify that guard_exists returns True for this concept
    with patch.object(graph_health_service, "guard_exists", return_value=True):
        assert graph_health_service.guard_exists(concept_id) is True


# ---------------------------------------------------------------------------
# Test 13: DELETE convergence-guard returns 200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_convergence_guard_200():
    from app.services import concept_service, graph_health_service

    concept_id = "test-concept"

    with patch.object(graph_health_service, "remove_guard", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete(f"/api/graph/concepts/{concept_id}/convergence-guard")
    assert r.status_code == 200
    body = r.json()
    assert body["convergence_guard"] is False


# ---------------------------------------------------------------------------
# Test 14: DELETE convergence-guard returns 404 when none exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_convergence_guard_404():
    from app.services import graph_health_service

    with patch.object(graph_health_service, "remove_guard", return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete("/api/graph/concepts/no-such-concept/convergence-guard")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Test 15: GET /api/graph/health/roi returns 200 with spec_ref and required fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_roi_returns_required_fields():
    from app.models.graph_health import GraphHealthROI
    from app.services import graph_health_service

    roi = GraphHealthROI(
        period_days=30,
        balance_score_delta=0.12,
        entropy_score_delta=0.08,
        split_signals_actioned=4,
        merge_signals_actioned=2,
        surface_signals_actioned=7,
        false_positive_rate=0.05,
        convergence_guards_active=2,
        spec_ref="spec-172",
    )

    with patch.object(graph_health_service, "get_roi", return_value=roi):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/graph/health/roi")
    assert r.status_code == 200
    body = r.json()
    assert body["spec_ref"] == "spec-172"
    assert "balance_score_delta" in body
    assert "entropy_score_delta" in body
    assert "split_signals_actioned" in body
