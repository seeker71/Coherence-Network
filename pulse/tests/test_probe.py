"""Probe layer tests — mock transport for httpx, no real network."""

from __future__ import annotations

import json

import httpx
import pytest

from pulse_app.probe import probe_all


HEALTHY_HEALTH = {
    "status": "ok",
    "version": "1.0.0",
    "timestamp": "2026-04-15T12:00:00Z",
    "started_at": "2026-04-14T12:00:00Z",
    "uptime_seconds": 86400,
    "uptime_human": "1d 0h 0m 0s",
    "deployed_sha": "deadbeef",
    "deployed_sha_source": "GIT_COMMIT_SHA",
    "integrity_compromised": False,
    "schema_ok": True,
    "opencode_enabled": True,
    "smart_reap_available": True,
    "smart_reap_import_error": None,
}

HEALTHY_READY = {
    "status": "ready",
    "version": "1.0.0",
    "timestamp": "2026-04-15T12:00:00Z",
    "started_at": "2026-04-14T12:00:00Z",
    "uptime_seconds": 86400,
    "uptime_human": "1d 0h 0m 0s",
    "deployed_sha": "deadbeef",
    "deployed_sha_source": "GIT_COMMIT_SHA",
    "db_connected": True,
    "integrity_compromised": False,
}


def _handler(api_health_body=None, ready_body=None, ready_status=200, web_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/health":
            return httpx.Response(
                200,
                content=json.dumps(api_health_body or HEALTHY_HEALTH),
                headers={"content-type": "application/json"},
            )
        if path == "/api/ready":
            return httpx.Response(
                ready_status,
                content=json.dumps(ready_body or HEALTHY_READY),
                headers={"content-type": "application/json"},
            )
        if path == "/":
            return httpx.Response(web_status, content="<html></html>")
        return httpx.Response(404, content="not found")

    return handler


async def _run(handler) -> dict[str, object]:
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        samples = await probe_all("http://api.test", "http://web.test", client=client)
    return {s.organ: s for s in samples}


@pytest.mark.asyncio
async def test_all_healthy():
    by = await _run(_handler())
    assert set(by.keys()) == {"api", "web", "postgres", "neo4j", "schema", "audit_integrity"}
    for s in by.values():
        assert s.ok is True, f"{s.organ} not ok: {s.detail}"


@pytest.mark.asyncio
async def test_api_status_not_ok():
    bad = {**HEALTHY_HEALTH, "status": "degraded"}
    by = await _run(_handler(api_health_body=bad))
    assert by["api"].ok is False
    # Schema and audit still read from same body — they should still be OK.
    assert by["schema"].ok is True
    assert by["audit_integrity"].ok is True


@pytest.mark.asyncio
async def test_integrity_compromised_flags_audit_only():
    bad = {**HEALTHY_HEALTH, "integrity_compromised": True}
    by = await _run(_handler(api_health_body=bad))
    assert by["api"].ok is True         # status=="ok" still
    assert by["audit_integrity"].ok is False
    assert "integrity" in (by["audit_integrity"].detail or "")


@pytest.mark.asyncio
async def test_schema_not_ok():
    bad = {**HEALTHY_HEALTH, "schema_ok": False}
    by = await _run(_handler(api_health_body=bad))
    assert by["schema"].ok is False
    assert by["api"].ok is True


@pytest.mark.asyncio
async def test_ready_503_graph_store_missing_flags_neo4j():
    # FastAPI HTTPException with plain detail='not ready' when graph_store is None.
    body = {"detail": "not ready"}
    by = await _run(_handler(ready_status=503, ready_body=body))
    assert by["neo4j"].ok is False
    assert "graph_store" in (by["neo4j"].detail or "")
    # API organ reads a different upstream, so it's unaffected.
    assert by["api"].ok is True


@pytest.mark.asyncio
async def test_ready_503_persistence_contract_flags_postgres_not_neo4j():
    # The real shape seen in prod: detail is a dict with persistence_contract_failed.
    body = {
        "detail": {
            "error": "persistence_contract_failed",
            "failures": ["some_domain_not_postgresql"],
            "domains": {},
        }
    }
    by = await _run(_handler(ready_status=503, ready_body=body))
    assert by["postgres"].ok is False
    assert "persistence" in (by["postgres"].detail or "")
    # neo4j is not implicated by this 503 cause.
    assert by["neo4j"].ok is True


@pytest.mark.asyncio
async def test_db_disconnected_flags_postgres_only():
    bad = {**HEALTHY_READY, "db_connected": False}
    by = await _run(_handler(ready_body=bad))
    assert by["postgres"].ok is False
    assert by["neo4j"].ok is True


@pytest.mark.asyncio
async def test_web_down():
    by = await _run(_handler(web_status=503))
    assert by["web"].ok is False
    assert by["api"].ok is True


@pytest.mark.asyncio
async def test_network_error_marks_everything_down():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("could not connect")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        samples = await probe_all("http://api.test", "http://web.test", client=client)
    for s in samples:
        assert s.ok is False
        assert s.detail is not None
