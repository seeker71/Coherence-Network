"""Form runtime bridge to the agent question SSE channel."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.services.agent_question_service import (
    answer_question,
    get_question_events,
    list_questions,
    reset_agent_questions,
)
from app.services.substrate.form_runtime import (
    form_execute_text,
    reset_runtime_registries,
)
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


@pytest.fixture
def session():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(eng, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(eng, checkfirst=True)
    from app.services.substrate.substrate_strings import SubstrateStringORM

    SubstrateStringORM.__table__.create(eng, checkfirst=True)
    db_session = sessionmaker(bind=eng, expire_on_commit=False)()
    reset_runtime_registries()
    reset_agent_questions()
    try:
        yield db_session
        db_session.commit()
    finally:
        db_session.close()
        reset_runtime_registries()
        reset_agent_questions()


@pytest.fixture(autouse=True)
def clean_agent_questions():
    reset_agent_questions()
    try:
        yield
    finally:
        reset_agent_questions()


def test_form_ask_opens_question_and_emits_sse_event(session) -> None:
    question = form_execute_text(
        session,
        (
            'ask("form-subagent", "Should the Form runtime ask the human?", '
            '["yes", "no"], {task_id: "task_1", thread_id: "thread_1"})'
        ),
    )

    assert question["agent_id"] == "form-subagent"
    assert question["question"] == "Should the Form runtime ask the human?"
    assert question["choices"] == ["yes", "no"]
    assert question["task_id"] == "task_1"
    assert question["thread_id"] == "thread_1"
    assert question["status"] == "open"

    open_questions = list_questions(status="open")
    assert [item["id"] for item in open_questions] == [question["id"]]

    events = get_question_events()
    assert [(event["sequence"], event["event_type"]) for event in events] == [
        (1, "question_opened")
    ]
    assert events[0]["question_id"] == question["id"]


def test_form_await_answer_reads_answer_when_present(session) -> None:
    question = form_execute_text(session, 'ask("form-subagent", "Continue?")')

    assert form_execute_text(session, f'await_answer("{question["id"]}")') is None

    answer_question(
        question_id=question["id"],
        answer="continue",
        answered_by="test",
    )

    assert form_execute_text(session, f'await_answer("{question["id"]}")') == "continue"


@pytest.mark.asyncio
async def test_substrate_form_run_mode_returns_question_value() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form",
            json={
                "mode": "run",
                "expression": (
                    'ask("api-form-subagent", "Which answer?", '
                    '["alpha", "beta"], {task_id: "task_api"})'
                ),
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "value"
    assert body["value"]["agent_id"] == "api-form-subagent"
    assert body["value"]["question"] == "Which answer?"
    assert body["value"]["choices"] == ["alpha", "beta"]
    assert body["value"]["task_id"] == "task_api"
    assert body["value"]["status"] == "open"

    events = get_question_events()
    assert events[-1]["event_type"] == "question_opened"
    assert events[-1]["question_id"] == body["value"]["id"]
