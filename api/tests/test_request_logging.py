"""Tests for the api-request-logging-middleware spec
(specs/api-request-logging-middleware.md).

The spec source: lists RequestDurationMiddleware in
api/app/middleware/request_duration.py and its registration in
api/app/main.py. The middleware logs slow requests above a threshold
without interfering with other middleware.
"""
from __future__ import annotations

import asyncio
import logging

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.request_duration import RequestDurationMiddleware


def _make_app(threshold: float, route_handler):
    routes = [Route("/sample", endpoint=route_handler)]
    app = Starlette(routes=routes)
    app.add_middleware(RequestDurationMiddleware, threshold_seconds=threshold)
    return app


def test_request_duration_middleware_init_clamps_negative_to_zero():
    """The middleware accepts a threshold; negative is clamped to 0."""
    mw = RequestDurationMiddleware(app=None, threshold_seconds=-1.0)
    assert mw.threshold_seconds == 0.0


def test_request_duration_middleware_init_default_is_one_second():
    """Default threshold is 1.0s per the source."""
    mw = RequestDurationMiddleware(app=None)
    assert mw.threshold_seconds == 1.0


def test_fast_request_does_not_emit_warning(caplog):
    """Request faster than threshold → no slow_request warning logged."""
    async def fast(_request):
        return PlainTextResponse("ok")

    app = _make_app(threshold=0.5, route_handler=fast)
    client = TestClient(app)
    with caplog.at_level(logging.WARNING, logger="coherence.api.duration"):
        response = client.get("/sample")
    assert response.status_code == 200
    assert all("slow_request" not in r.message for r in caplog.records)


def test_slow_request_emits_warning_with_metadata(caplog):
    """Request slower than threshold → warning with method, path, status, duration."""
    async def slow(_request):
        await asyncio.sleep(0.05)
        return PlainTextResponse("delayed")

    # Threshold below the actual sleep so the warning fires
    app = _make_app(threshold=0.01, route_handler=slow)
    client = TestClient(app)
    with caplog.at_level(logging.WARNING, logger="coherence.api.duration"):
        response = client.get("/sample")
    assert response.status_code == 200
    slow_records = [r for r in caplog.records if "slow_request" in r.message]
    assert slow_records, "expected at least one slow_request warning"
    msg = slow_records[0].getMessage()
    assert "method=GET" in msg
    assert "path=/sample" in msg
    assert "status=200" in msg
    assert "duration_s=" in msg


def test_middleware_passes_through_response_unchanged():
    """The middleware doesn't alter the response body or status."""
    async def echo(_request):
        return PlainTextResponse("echo-body", status_code=201)

    app = _make_app(threshold=10.0, route_handler=echo)
    client = TestClient(app)
    response = client.get("/sample")
    assert response.status_code == 201
    assert response.text == "echo-body"
