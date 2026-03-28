"""Tests for spec 037: POST /api/agent/tasks with invalid task_type returns 422.

Spec 037: Ensure that creating an agent task with an invalid task_type is rejected
with 422 so clients receive predictable validation behavior.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_post_task_invalid_task_type_returns_422() -> None:
    """POST /api/agent/tasks with invalid task_type returns 422.

    Spec 037: task_type not in {spec, test, impl, review, heal, code-review, merge,
    deploy, verify, reflect} must be rejected with HTTP 422.
    Response body must have a 'detail' key (array of validation items per spec 009).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/agent/tasks",
            json={"direction": "do something", "task_type": "invalid"},
        )

    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
    body = r.json()
    assert "detail" in body, f"Expected 'detail' key in 422 response, got: {body}"
    assert isinstance(body["detail"], list), (
        f"Expected 'detail' to be a list (Pydantic validation errors), got: {type(body['detail'])}"
    )
    assert len(body["detail"]) > 0, "Expected at least one validation error in 'detail'"

    # At least one error should reference task_type
    task_type_error = next(
        (item for item in body["detail"] if "task_type" in str(item.get("loc", ""))),
        None,
    )
    assert task_type_error is not None, (
        f"Expected a validation error referencing 'task_type' in detail, got: {body['detail']}"
    )


@pytest.mark.asyncio
async def test_post_task_foo_task_type_returns_422() -> None:
    """POST /api/agent/tasks with task_type='foo' returns 422.

    Spec 037: Any value not in the allowed enum is rejected with 422 and detail array.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/agent/tasks",
            json={"direction": "run pipeline", "task_type": "foo"},
        )

    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
    body = r.json()
    assert "detail" in body, f"Expected 'detail' key in 422 response body"
    assert isinstance(body["detail"], list), "Expected 'detail' to be a list"


@pytest.mark.asyncio
async def test_post_task_valid_task_types_do_not_return_422() -> None:
    """POST /api/agent/tasks with valid task_type values does not return 422.

    Spec 037 (negative): valid task_type values must be accepted (not rejected).
    Checks that 422 is specific to invalid values, not a blanket rejection.
    """
    valid_types = ["spec", "test", "impl", "review", "heal"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for task_type in valid_types:
            r = await client.post(
                "/api/agent/tasks",
                json={"direction": f"task for {task_type}", "task_type": task_type},
            )
            assert r.status_code != 422, (
                f"Valid task_type '{task_type}' should not return 422, got {r.status_code}: {r.text}"
            )
