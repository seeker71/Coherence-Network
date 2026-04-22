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

HEALTHY_IDEAS = {
    "ideas": [
        {"id": "idea-1", "name": "First idea", "description": "..."},
        {"id": "idea-2", "name": "Second idea", "description": "..."},
    ],
    "pagination": {"total": 2, "page": 1, "page_size": 50},
    "summary": {"count": 2},
}

HEALTHY_VITALITY = {
    "workspace_id": "coherence-network",
    "vitality_score": 0.69,
    "health_description": "Growing",
    "signals": {
        "diversity_index": 0.5,
        "resonance_density": 0.8,
        "flow_rate": 0.7,
        "breath_rhythm": {"gas": 0.3, "water": 0.4, "ice": 0.3},
        "connection_strength": 0.6,
        "activity_pulse": 0.55,
    },
    "generated_at": "2026-04-15T12:00:00Z",
}

HEALTHY_HOME_HTML = """<!DOCTYPE html><html><body>
<a href="/">Coherence Network</a>
<main>welcome to the living network</main>
</body></html>"""

HEALTHY_PULSE_HTML = """<!DOCTYPE html><html><body>
<h1>Pulse</h1>
<p>The breath of our living body, remembered.</p>
<section>All organs breathing</section>
</body></html>"""

HEALTHY_VITALITY_HTML = """<!DOCTYPE html><html><body>
<h1>Vitality</h1>
<p>Network Vitality 69%</p>
<h3>Diversity Index</h3><h3>Resonance Density</h3>
</body></html>"""

# Marker Next.js emits when an error boundary catches a render failure.
# The real error.tsx wraps its main in role="alert" aria-live="assertive" —
# uniquely the error page, never just a locale string in the page data.
ERROR_BOUNDARY_HTML = """<!DOCTYPE html><html><body>
<main role="alert" aria-live="assertive">
<h1>Something went wrong</h1>
</main>
</body></html>"""


def _handler(
    api_health_body=None,
    ready_body=None,
    ready_status=200,
    ideas_body=None,
    ideas_status=200,
    vitality_api_body=None,
    vitality_api_status=200,
    web_status=200,
    web_body=HEALTHY_HOME_HTML,
    web_pulse_status=200,
    web_pulse_body=HEALTHY_PULSE_HTML,
    web_vitality_status=200,
    web_vitality_body=HEALTHY_VITALITY_HTML,
):
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
        if path == "/api/ideas":
            return httpx.Response(
                ideas_status,
                content=json.dumps(ideas_body if ideas_body is not None else HEALTHY_IDEAS),
                headers={"content-type": "application/json"},
            )
        if path == "/api/workspaces/coherence-network/vitality":
            return httpx.Response(
                vitality_api_status,
                content=json.dumps(vitality_api_body if vitality_api_body is not None else HEALTHY_VITALITY),
                headers={"content-type": "application/json"},
            )
        if path == "/":
            return httpx.Response(web_status, content=web_body, headers={"content-type": "text/html"})
        if path == "/pulse":
            return httpx.Response(web_pulse_status, content=web_pulse_body, headers={"content-type": "text/html"})
        if path == "/vitality":
            return httpx.Response(web_vitality_status, content=web_vitality_body, headers={"content-type": "text/html"})
        return httpx.Response(404, content="not found")

    return handler


async def _run(handler) -> dict[str, object]:
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        samples = await probe_all("http://api.test", "http://web.test", client=client)
    return {s.organ: s for s in samples}


# ----- infrastructure organs ------------------------------------------------

@pytest.mark.asyncio
async def test_all_healthy():
    by = await _run(_handler())
    expected = {
        "api", "web", "postgres", "neo4j", "schema", "audit_integrity",
        "page_pulse", "page_vitality", "endpoint_ideas", "endpoint_vitality",
    }
    assert set(by.keys()) == expected
    for name, sample in by.items():
        assert sample.ok is True, f"{name} not ok: {sample.detail}"


@pytest.mark.asyncio
async def test_api_flags_strained_on_recent_5xx():
    """Real-user 5xx count surfaces as strain on the api organ."""
    body = {**HEALTHY_HEALTH, "recent_outcomes": {
        "last_1m": {"2xx": 100, "3xx": 0, "4xx": 2, "5xx": 3, "total": 105},
        "last_5m": {"2xx": 500, "3xx": 0, "4xx": 5, "5xx": 3, "total": 508},
        "as_of_minute": 29000000,
    }}
    by = await _run(_handler(api_health_body=body))
    api_sample = by["api"]
    assert api_sample.ok is True  # the probe itself succeeded
    assert api_sample.detail is not None
    assert api_sample.detail.startswith("slow: ")
    assert "5xx" in api_sample.detail
    assert "last 1m" in api_sample.detail


@pytest.mark.asyncio
async def test_api_flags_strained_on_heavy_4xx_rate():
    """When most recent traffic is 4xx, flag the api as straining."""
    body = {**HEALTHY_HEALTH, "recent_outcomes": {
        "last_1m": {"2xx": 5, "3xx": 0, "4xx": 25, "5xx": 0, "total": 30},
        "last_5m": {"2xx": 20, "3xx": 0, "4xx": 80, "5xx": 0, "total": 100},
        "as_of_minute": 29000000,
    }}
    by = await _run(_handler(api_health_body=body))
    api_sample = by["api"]
    assert api_sample.ok is True
    assert api_sample.detail is not None
    assert "4xx" in api_sample.detail


@pytest.mark.asyncio
async def test_api_does_not_strain_on_small_4xx_count():
    """A handful of 4xx is normal user error — don't flag."""
    body = {**HEALTHY_HEALTH, "recent_outcomes": {
        "last_1m": {"2xx": 100, "3xx": 0, "4xx": 3, "5xx": 0, "total": 103},
        "last_5m": {"2xx": 500, "3xx": 0, "4xx": 10, "5xx": 0, "total": 510},
        "as_of_minute": 29000000,
    }}
    by = await _run(_handler(api_health_body=body))
    assert by["api"].ok is True
    assert by["api"].detail is None


@pytest.mark.asyncio
async def test_api_status_not_ok():
    bad = {**HEALTHY_HEALTH, "status": "degraded"}
    by = await _run(_handler(api_health_body=bad))
    assert by["api"].ok is False
    assert by["schema"].ok is True
    assert by["audit_integrity"].ok is True


@pytest.mark.asyncio
async def test_integrity_compromised_flags_audit_only():
    bad = {**HEALTHY_HEALTH, "integrity_compromised": True}
    by = await _run(_handler(api_health_body=bad))
    assert by["api"].ok is True
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
    body = {"detail": "not ready"}
    by = await _run(_handler(ready_status=503, ready_body=body))
    assert by["neo4j"].ok is False
    assert "graph_store" in (by["neo4j"].detail or "")
    assert by["api"].ok is True


@pytest.mark.asyncio
async def test_ready_503_persistence_contract_flags_postgres_not_neo4j():
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
    assert by["neo4j"].ok is True


@pytest.mark.asyncio
async def test_db_disconnected_flags_postgres_only():
    bad = {**HEALTHY_READY, "db_connected": False}
    by = await _run(_handler(ready_body=bad))
    assert by["postgres"].ok is False
    assert by["neo4j"].ok is True


# ----- web root organ ------------------------------------------------------

@pytest.mark.asyncio
async def test_web_down():
    by = await _run(_handler(web_status=503))
    assert by["web"].ok is False
    assert by["api"].ok is True


@pytest.mark.asyncio
async def test_web_missing_branding():
    by = await _run(_handler(web_body="<html><body>different site</body></html>"))
    assert by["web"].ok is False
    assert "Coherence Network" in (by["web"].detail or "")


@pytest.mark.asyncio
async def test_web_error_boundary_flags_silent():
    by = await _run(_handler(web_body=ERROR_BOUNDARY_HTML))
    assert by["web"].ok is False
    assert "error boundary" in (by["web"].detail or "")


@pytest.mark.asyncio
async def test_locale_messages_dont_trigger_false_positive():
    """Regression: the witness used to flag any page with the raw
    string 'Something went wrong' as 'error boundary rendered' —
    but that string appears verbatim in every page's embedded
    locale messages JSON (`"error":"Something went wrong"`). Real
    error pages wrap their main in `role="alert" aria-live=
    "assertive"` — that's the marker now. Pages with the locale
    blob but no actual error UI must read as healthy."""
    locale_blob_html = """<!DOCTYPE html><html><body>
    <h1>Coherence Network</h1>
    <div>Pulse</div>
    <h1>Vitality</h1>
    <h3>Diversity Index</h3>
    <script>{"common":{"error":"Something went wrong","tryAgain":"Try again"}}</script>
    </body></html>"""
    by = await _run(_handler(
        web_body=locale_blob_html,
        web_pulse_body=locale_blob_html,
        web_vitality_body=locale_blob_html,
    ))
    assert by["web"].ok is True, by["web"].detail
    assert by["page_pulse"].ok is True, by["page_pulse"].detail
    assert by["page_vitality"].ok is True, by["page_vitality"].detail


# ----- outcome organs: pages ------------------------------------------------

@pytest.mark.asyncio
async def test_page_pulse_error_boundary():
    """This is the class of bug the outcome organs were built to catch."""
    by = await _run(_handler(web_pulse_body=ERROR_BOUNDARY_HTML))
    assert by["page_pulse"].ok is False
    assert "error boundary" in (by["page_pulse"].detail or "")
    # Infrastructure organs are unaffected — this is a page-level sensing win.
    assert by["api"].ok is True
    assert by["web"].ok is True


@pytest.mark.asyncio
async def test_page_pulse_missing_h1():
    body = "<html><body>Pulse is broken — no h1 here</body></html>"
    by = await _run(_handler(web_pulse_body=body))
    assert by["page_pulse"].ok is False
    assert "Pulse h1" in (by["page_pulse"].detail or "")


@pytest.mark.asyncio
async def test_page_vitality_error_boundary_catches_signals_map_crash():
    """The exact class of bug this session hit: /vitality renders an error boundary."""
    by = await _run(_handler(web_vitality_body=ERROR_BOUNDARY_HTML))
    assert by["page_vitality"].ok is False
    assert "error boundary" in (by["page_vitality"].detail or "")


@pytest.mark.asyncio
async def test_page_vitality_missing_diversity_signal():
    body = "<html><body><h1>Vitality</h1><p>but no signals</p></body></html>"
    by = await _run(_handler(web_vitality_body=body))
    assert by["page_vitality"].ok is False
    assert "Diversity" in (by["page_vitality"].detail or "")


# ----- outcome organs: api shape -------------------------------------------

@pytest.mark.asyncio
async def test_endpoint_ideas_missing_ideas_key():
    body = {"pagination": {}, "summary": {}}  # no ideas key at all
    by = await _run(_handler(ideas_body=body))
    assert by["endpoint_ideas"].ok is False
    assert "ideas" in (by["endpoint_ideas"].detail or "")


@pytest.mark.asyncio
async def test_endpoint_ideas_wrong_type():
    body = {"ideas": {"not": "a list"}}
    by = await _run(_handler(ideas_body=body))
    assert by["endpoint_ideas"].ok is False
    assert "list" in (by["endpoint_ideas"].detail or "")


@pytest.mark.asyncio
async def test_endpoint_ideas_http_error():
    by = await _run(_handler(ideas_status=500))
    assert by["endpoint_ideas"].ok is False
    assert "500" in (by["endpoint_ideas"].detail or "")


@pytest.mark.asyncio
async def test_endpoint_vitality_shape_drift():
    """Signals is an array, not a dict — the historical drift this session hit."""
    body = {**HEALTHY_VITALITY, "signals": ["array", "instead", "of", "dict"]}
    by = await _run(_handler(vitality_api_body=body))
    assert by["endpoint_vitality"].ok is False
    assert "signals" in (by["endpoint_vitality"].detail or "")


@pytest.mark.asyncio
async def test_endpoint_vitality_missing_diversity_index():
    partial_signals = {k: v for k, v in HEALTHY_VITALITY["signals"].items() if k != "diversity_index"}
    body = {**HEALTHY_VITALITY, "signals": partial_signals}
    by = await _run(_handler(vitality_api_body=body))
    assert by["endpoint_vitality"].ok is False
    assert "diversity_index" in (by["endpoint_vitality"].detail or "")


# ----- network errors ------------------------------------------------------

@pytest.mark.asyncio
async def test_slow_probe_flags_strained_not_silent(monkeypatch):
    """A successful probe that crossed the threshold is ok=True with a slow detail."""
    from pulse_app import organs, probe

    # Rewrite the test to inject a slow latency by monkey-patching the probe helper.
    original = probe._probe_upstream

    async def slow_probe(client, url, kind):
        r = await original(client, url, kind)
        # Replace with a 3-second latency on the api_health upstream
        if url.endswith("/api/health"):
            return probe.UpstreamResult(
                status=r.status, body=r.body, text=r.text,
                latency_ms=3500, error=None,
            )
        return r

    monkeypatch.setattr(probe, "_probe_upstream", slow_probe)

    by = await _run(_handler())
    # api organ's default threshold is 2000ms, so 3500ms is flagged
    api_sample = by["api"]
    assert api_sample.ok is True  # the body was fine
    assert api_sample.detail is not None
    assert api_sample.detail.startswith("slow: ")
    assert "3500ms" in api_sample.detail
    assert "2000ms" in api_sample.detail


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
