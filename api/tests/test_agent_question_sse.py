import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.agent_question_service import reset_agent_questions


BASE = "http://test"


@pytest.fixture(autouse=True)
def clear_questions():
    reset_agent_questions()
    yield
    reset_agent_questions()


@pytest.mark.asyncio
async def test_agent_question_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        created = await client.post(
            "/api/agent/questions",
            json={
                "agent_id": "sub-agent-1",
                "task_id": "task_123",
                "question": "Which path should this sub-agent take?",
                "choices": ["continue", "pause"],
                "context": {"form": "(ask human ...)"},
            },
        )
        assert created.status_code == 201
        question = created.json()
        assert question["status"] == "open"
        assert question["choices"] == ["continue", "pause"]

        listed = await client.get("/api/agent/questions", params={"status": "open"})
        assert listed.status_code == 200
        assert listed.json()["questions"][0]["id"] == question["id"]

        answered = await client.post(
            f"/api/agent/questions/{question['id']}/answer",
            json={"answer": "continue", "answered_by": "human"},
        )
        assert answered.status_code == 200
        assert answered.json()["status"] == "answered"
        assert answered.json()["answer"] == "continue"

        open_list = await client.get("/api/agent/questions", params={"status": "open"})
        assert open_list.status_code == 200
        assert open_list.json()["questions"] == []


@pytest.mark.asyncio
async def test_agent_question_sse_replays_opened_event():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        created = await client.post(
            "/api/agent/questions",
            json={"agent_id": "sub-agent-2", "question": "Can I ask from the web organ?"},
        )
        assert created.status_code == 201

        async with client.stream(
            "GET",
            "/api/agent/questions/stream",
            params={"max_events": 1, "timeout_seconds": 0.1},
        ) as response:
            assert response.status_code == 200
            body = await response.aread()

    frames = [
        line.removeprefix("data: ")
        for line in body.decode().splitlines()
        if line.startswith("data: ")
    ]
    event = json.loads(frames[0])
    assert event["event_type"] == "question_opened"
    assert event["question_id"] == created.json()["id"]
    assert event["question"]["question"] == "Can I ask from the web organ?"
