from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_task_log_endpoint_returns_snapshot_when_log_file_missing() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "task log fallback coverage", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"current_step": "running fallback check", "output": "snapshot output text"},
        )

        log_path = Path(__file__).resolve().parents[1] / "logs" / f"task_{task_id}.log"
        if log_path.exists():
            log_path.unlink()

        response = await client.get(f"/api/agent/tasks/{task_id}/log")
        assert response.status_code == 200
        body = response.json()
        assert body["task_id"] == task_id
        assert body["log_source"] == "task_snapshot"
        assert "running fallback check" in body["log"]
        assert "snapshot output text" in body["log"]


@pytest.mark.asyncio
async def test_task_log_endpoint_prefers_file_when_available() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "task log file coverage", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        log_path = Path(__file__).resolve().parents[1] / "logs" / f"task_{task_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("line-1\nline-2\n", encoding="utf-8")

        try:
            response = await client.get(f"/api/agent/tasks/{task_id}/log")
            assert response.status_code == 200
            body = response.json()
            assert body["task_id"] == task_id
            assert body["log_source"] == "file"
            assert body["log"] == "line-1\nline-2\n"
        finally:
            if log_path.exists():
                log_path.unlink()
