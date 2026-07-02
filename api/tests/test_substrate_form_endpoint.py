"""Smoke tests for POST /api/substrate/form — the substrate-native query DSL
exposed as REST so outside agents can ask the lattice in its own language."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import substrate as substrate_router
from app.services.substrate.kernel import NodeID


@pytest.mark.asyncio
async def test_form_endpoint_evaluates_empty_query_against_substrate() -> None:
    """A well-formed Form expression returns a discriminated result.

    Asking for cells in a domain that has no entries should still parse,
    evaluate, and return kind="cells" with an empty list — proving the
    endpoint is live, not just registered.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form",
            json={"expression": '?cells where domain == "no_such_domain_for_test"'},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "cells"
    assert body["cells"] == []


@pytest.mark.asyncio
async def test_form_endpoint_streaming_mode_emits_same_recipe_node() -> None:
    """Streaming mode exposes the direct Recipe emitter through the same API."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ast_response = await client.post(
            "/api/substrate/form",
            json={"expression": "1 + 2 * 3"},
        )
        streaming_response = await client.post(
            "/api/substrate/form",
            json={"expression": "1 + 2 * 3", "mode": "streaming"},
        )

    assert ast_response.status_code == 200, ast_response.text
    assert streaming_response.status_code == 200, streaming_response.text
    ast_body = ast_response.json()
    streaming_body = streaming_response.json()
    assert ast_body["kind"] == "recipe"
    assert streaming_body["kind"] == "recipe"
    assert streaming_body["node_id"] == ast_body["node_id"]


def test_form_endpoint_access_bootstrap_gap_falls_back_to_runtime(monkeypatch) -> None:
    """Default AST mode stays breathing when old bootstrap Access eval regresses."""

    def broken_ast(_session, _expression):
        raise TypeError("Form: cannot evaluate Access")

    def runtime_value(_session, _expression):
        return NodeID(1, 5, 4, 1)

    monkeypatch.setattr(substrate_router, "form_evaluate_text", broken_ast)
    monkeypatch.setattr(substrate_router, "form_execute_text", runtime_value)

    result = substrate_router.evaluate_form(
        substrate_router.FormRequest(expression="@concept(lc-pulse).blueprint")
    )

    assert result.kind == "node_id"
    assert result.node_id is not None
    assert result.node_id.package == 1
    assert result.node_id.level == 5
    assert result.node_id.type_ == 4
    assert result.node_id.instance == 1


@pytest.mark.asyncio
async def test_form_endpoint_rejects_unknown_mode() -> None:
    """Mode stays explicit so callers know which parser path they exercised."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form",
            json={"expression": "1 + 2", "mode": "direct"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_form_endpoint_rejects_syntactically_broken_expression() -> None:
    """Parse / eval failures return HTTP 400 with the failure reason.

    The substrate stays read-only; bad expressions never silently succeed.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form",
            json={"expression": "?? this is not Form notation @@@"},
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "form parse/eval failed" in detail


@pytest.mark.asyncio
async def test_form_endpoint_requires_expression() -> None:
    """Empty payload returns 422 from Pydantic validation; not 500."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/substrate/form", json={})

    assert response.status_code == 422

# ----- GET lane — form-cli for guests who cannot POST -----------------------


@pytest.mark.asyncio
async def test_form_get_lane_evaluates_same_as_post() -> None:
    """GET /api/substrate/form?expression=... returns the same result as POST.

    Chat assistants (Grok, ChatGPT browsing) can only fetch URLs; the GET
    lane is their form-cli. Same expression, same evaluator, same shape.
    """
    expr = '?cells where domain == "no_such_domain_for_test"'
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_response = await client.get(
            "/api/substrate/form", params={"expression": expr}
        )
        post_response = await client.post(
            "/api/substrate/form", json={"expression": expr}
        )

    assert get_response.status_code == 200, get_response.text
    assert get_response.json() == post_response.json()


@pytest.mark.asyncio
async def test_form_get_lane_holds_streaming_to_post() -> None:
    """The GET lane offers ast + run (compute is the point) but refuses
    'streaming' Recipe emission — that write path stays POST-only. An
    out-of-pattern mode is a 422 before any evaluation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/substrate/form",
            params={"expression": "1 + 2", "mode": "streaming"},
        )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_form_get_lane_requires_expression() -> None:
    """GET without ?expression= is a 422, mirroring the POST contract."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/substrate/form")
    assert response.status_code == 422

# ----- public-door host-effect guard + GET run compute ----------------------

import pytest as _pytest


@_pytest.mark.parametrize(
    "expression",
    [
        'file_exists("README.md")',
        'file_contains("README.md", "x")',
        'file_size("README.md")',
        'symbol_in_file("README.md", "x")',
        'pytest_passes("tests/x.py")',
        'map(file_exists, list("README.md"))',  # impure passed by name
    ],
)
@pytest.mark.asyncio
async def test_public_form_refuses_host_effect_verbs_post(expression) -> None:
    """No public caller can reach the filesystem, subprocess, or oracle."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form", json={"expression": expression, "mode": "run"}
        )
    assert response.status_code == 400, response.text
    assert "host machine" in response.json()["detail"]


@pytest.mark.asyncio
async def test_public_form_refuses_host_effect_verbs_get() -> None:
    """The guard covers the GET lane too — same boundary, both doors."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/substrate/form",
            params={"expression": 'file_exists("README.md")', "mode": "run"},
        )
    assert response.status_code == 400, response.text
    assert "host machine" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_run_lane_computes_a_value() -> None:
    """A guest can RUN code they know the grammar for and get a value back."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/substrate/form",
            params={"expression": "1 + 2 * 3", "mode": "run"},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "value"
    assert body["value"] == 7


@pytest.mark.asyncio
async def test_get_run_lane_runs_recursion() -> None:
    """Recursion through a user defn computes natively on the public door."""
    expr = "do { defn fib(n) = if n <= 1 then n else fib(n - 1) + fib(n - 2); fib(10) }"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/substrate/form", params={"expression": expr, "mode": "run"}
        )
    assert response.status_code == 200, response.text
    assert response.json()["value"] == 55


@pytest.mark.asyncio
async def test_public_form_bounds_range_allocation() -> None:
    """The range amplifier is capped so a public caller can't OOM a worker."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form",
            json={"expression": "range(100000000)", "mode": "run"},
        )
    assert response.status_code == 400, response.text
    assert "range too large" in response.json()["detail"]


@pytest.mark.parametrize(
    "expression",
    [
        "[0] * 20000000",      # list repetition — the 14-char memory bomb
        '"AAAAAAAAAA" * 100000000',  # string repetition
        "([0] * 5000) * 5000",  # nested amplification
    ],
)
@pytest.mark.asyncio
async def test_public_form_bounds_sequence_multiplication(expression) -> None:
    """Sequence repetition can't OOM a worker — the amplifier `range`'s cap
    missed. Pure int arithmetic is untouched (tested elsewhere)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form", json={"expression": expression, "mode": "run"}
        )
    assert response.status_code == 400, response.text
    assert "too large" in response.json()["detail"]


@pytest.mark.asyncio
async def test_public_form_still_computes_ordinary_arithmetic() -> None:
    """The sequence bound does not touch int math or small lists."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post("/api/substrate/form", json={"expression": "7 * 6", "mode": "run"})
        r2 = await client.post("/api/substrate/form", json={"expression": "[1, 2] * 3", "mode": "run"})
    assert r1.json()["value"] == 42
    assert r2.json()["value"] == [1, 2, 1, 2, 1, 2]
