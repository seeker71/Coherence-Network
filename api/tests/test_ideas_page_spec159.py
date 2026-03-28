"""Tests for Spec 159 (idea-e92e6d043871): Ideas page API contract.

Verifies that GET /api/ideas returns stage, open_questions, actual_value,
and potential_value on every idea, and that GET /api/ideas/progress returns
a valid ProgressDashboard — the data the frontend needs to render the
restructured Ideas page (stage badges, open-question counts, value bars,
lifecycle dashboard).

No frontend tests — this is a pure frontend spec; these tests guard the
API contract the frontend depends on.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pathlib import Path

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_idea(client: AsyncClient, **overrides) -> dict:
    payload = {
        "id": "test-spec159-base",
        "name": "Spec159 Base Idea",
        "description": "Base idea for spec 159 tests.",
        "potential_value": 100.0,
        "estimated_cost": 20.0,
        "confidence": 0.7,
    }
    payload.update(overrides)
    resp = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# R7 — API contract: stage field present on every listed idea
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_ideas_includes_stage_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GET /api/ideas returns a 'stage' field on each idea."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(client, id="stage-field-idea")

        resp = await client.get("/api/ideas")
    assert resp.status_code == 200
    data = resp.json()
    assert "ideas" in data
    for idea in data["ideas"]:
        assert "stage" in idea, f"Idea {idea.get('id')} missing 'stage' field"


@pytest.mark.asyncio
async def test_list_ideas_default_stage_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ideas created without an explicit stage default to 'none'."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(client, id="default-stage-idea")

        resp = await client.get("/api/ideas")
    data = resp.json()
    stages = [idea["stage"] for idea in data["ideas"]]
    assert "none" in stages, "Expected at least one idea with stage='none'"


# ---------------------------------------------------------------------------
# R2 — Stage badge: every valid stage value is accepted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["none", "specced", "implementing", "testing", "reviewing", "complete"])
async def test_set_idea_stage_accepts_all_valid_stages(
    stage: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """POST /api/ideas/{id}/stage accepts all six valid stage values."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / f"ideas-{stage}.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        idea_id = f"stage-test-{stage}"
        await _create_idea(client, id=idea_id)

        resp = await client.post(
            f"/api/ideas/{idea_id}/stage",
            json={"stage": stage},
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == stage


@pytest.mark.asyncio
async def test_set_idea_stage_invalid_value_returns_422(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """POST /api/ideas/{id}/stage with an invalid stage value returns HTTP 422."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(client, id="invalid-stage-idea")

        resp = await client.post(
            "/api/ideas/invalid-stage-idea/stage",
            json={"stage": "mythical"},
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_set_idea_stage_not_found_returns_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """POST /api/ideas/{id}/stage for a non-existent idea returns HTTP 404."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/does-not-exist/stage",
            json={"stage": "specced"},
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# R7 — API contract: open_questions present with correct structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_ideas_includes_open_questions_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GET /api/ideas returns an 'open_questions' list on each idea."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(client, id="oq-field-idea")

        resp = await client.get("/api/ideas")
    data = resp.json()
    for idea in data["ideas"]:
        assert "open_questions" in idea, f"Idea {idea.get('id')} missing 'open_questions'"
        assert isinstance(idea["open_questions"], list)


@pytest.mark.asyncio
async def test_idea_with_questions_persists_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An answered question is returned with its answer in GET /api/ideas."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    question_text = "Will this work?"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(
            client,
            id="answered-q-idea",
            open_questions=[
                {"question": question_text, "value_to_whole": 10.0, "estimated_cost": 1.0},
                {"question": "What is the cost?", "value_to_whole": 5.0, "estimated_cost": 0.5},
            ],
        )

        # Answer the first explicit question via POST /questions/answer
        r = await client.post(
            "/api/ideas/answered-q-idea/questions/answer",
            json={"question": question_text, "answer": "Yes, it will work."},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 200, r.text

        resp = await client.get("/api/ideas/answered-q-idea")
    assert resp.status_code == 200
    data = resp.json()
    questions = data.get("open_questions", [])
    answered = [q for q in questions if q.get("answer")]
    assert len(answered) >= 1
    answered_texts = {q["question"] for q in answered}
    assert question_text in answered_texts


@pytest.mark.asyncio
async def test_open_question_answered_count_derivable_from_api(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The frontend can derive answered/total from open_questions on GET /api/ideas.

    Spec 159 R3: answered = count where answer is non-empty; total = len(open_questions).
    Note: the service injects a default question on idea creation, so total >= len(explicit).
    """
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    q1 = "Q1 explicit"
    q2 = "Q2 explicit"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(
            client,
            id="oq-count-idea",
            open_questions=[
                {"question": q1, "value_to_whole": 8.0, "estimated_cost": 1.0},
                {"question": q2, "value_to_whole": 4.0, "estimated_cost": 1.0},
            ],
        )

        # Answer both explicit questions
        for q_text in (q1, q2):
            r = await client.post(
                "/api/ideas/oq-count-idea/questions/answer",
                json={"question": q_text, "answer": f"Answer for {q_text}"},
                headers=AUTH_HEADERS,
            )
            assert r.status_code == 200, r.text

        resp = await client.get("/api/ideas/oq-count-idea")
    data = resp.json()
    questions = data.get("open_questions", [])
    total = len(questions)
    answered = sum(1 for q in questions if q.get("answer"))
    # Two explicit questions answered; default may be unanswered
    assert total >= 2
    assert answered >= 2  # at minimum both explicit questions are answered


@pytest.mark.asyncio
async def test_idea_open_questions_field_is_a_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """open_questions is always a list (never null/missing) — frontend can safely call .length.

    Spec 159 R3 edge case: frontend checks total === 0 to suppress the count line.
    """
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(client, id="no-questions-idea")

        resp = await client.get("/api/ideas/no-questions-idea")
    data = resp.json()
    assert "open_questions" in data
    assert isinstance(data["open_questions"], list)


# ---------------------------------------------------------------------------
# R7 — API contract: actual_value + potential_value present (value bar)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_ideas_includes_value_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GET /api/ideas includes 'actual_value' and 'potential_value' on each idea."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(client, id="value-fields-idea", actual_value=25.0, potential_value=100.0)

        resp = await client.get("/api/ideas")
    data = resp.json()
    for idea in data["ideas"]:
        assert "actual_value" in idea
        assert "potential_value" in idea
        assert idea["actual_value"] >= 0.0
        assert idea["potential_value"] >= 0.0


@pytest.mark.asyncio
async def test_value_bar_ratio_derivable_from_api(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """actual_value / potential_value is derivable; non-zero ratio is preserved."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(
            client, id="value-ratio-idea", actual_value=30.0, potential_value=100.0
        )

        resp = await client.get("/api/ideas/value-ratio-idea")
    data = resp.json()
    assert data["actual_value"] == 30.0
    assert data["potential_value"] == 100.0
    ratio = data["actual_value"] / data["potential_value"]
    assert abs(ratio - 0.3) < 0.001


# ---------------------------------------------------------------------------
# R4/R5 — GET /api/ideas/progress: ProgressDashboard contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_progress_dashboard_returns_valid_structure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GET /api/ideas/progress returns ProgressDashboard with required fields."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_ideas" in data
    assert "completion_pct" in data
    assert "by_stage" in data
    assert "snapshot_at" in data
    assert isinstance(data["by_stage"], dict)
    assert 0.0 <= data["completion_pct"] <= 1.0


@pytest.mark.asyncio
async def test_progress_dashboard_includes_all_stages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GET /api/ideas/progress by_stage covers all six stage keys."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    expected_stages = {"none", "specced", "implementing", "testing", "reviewing", "complete"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas/progress")
    data = resp.json()
    assert expected_stages.issubset(set(data["by_stage"].keys()))


@pytest.mark.asyncio
async def test_progress_dashboard_completion_pct_reflects_complete_ideas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """completion_pct = complete_count / total_ideas when ideas exist."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create 3 ideas, advance 1 to complete
        for idx in range(3):
            await _create_idea(client, id=f"pct-idea-{idx}", name=f"Pct Idea {idx}")

        await client.post(
            "/api/ideas/pct-idea-0/stage",
            json={"stage": "complete"},
            headers=AUTH_HEADERS,
        )

        resp = await client.get("/api/ideas/progress")
    data = resp.json()
    # 1 complete out of 3 → ~0.3333
    assert abs(data["completion_pct"] - round(1 / 3, 4)) < 0.001
    assert data["by_stage"]["complete"]["count"] == 1
    assert data["total_ideas"] == 3


@pytest.mark.asyncio
async def test_progress_dashboard_empty_store_returns_zeros(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GET /api/ideas/progress with no ideas returns zero totals."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas-empty.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas/progress")
    data = resp.json()
    assert data["total_ideas"] == 0
    assert data["completion_pct"] == 0.0


# ---------------------------------------------------------------------------
# advance endpoint — sequential stage advancement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advance_idea_stage_increments_sequentially(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """POST /api/ideas/{id}/advance moves stage forward one step."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(client, id="advance-idea")

        r1 = await client.post("/api/ideas/advance-idea/advance", headers=AUTH_HEADERS)
        assert r1.status_code == 200
        assert r1.json()["stage"] == "specced"

        r2 = await client.post("/api/ideas/advance-idea/advance", headers=AUTH_HEADERS)
        assert r2.status_code == 200
        assert r2.json()["stage"] == "implementing"


@pytest.mark.asyncio
async def test_advance_complete_idea_returns_409(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """POST /api/ideas/{id}/advance on an already-complete idea returns HTTP 409."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(client, id="complete-idea")
        await client.post(
            "/api/ideas/complete-idea/stage",
            json={"stage": "complete"},
            headers=AUTH_HEADERS,
        )

        resp = await client.post("/api/ideas/complete-idea/advance", headers=AUTH_HEADERS)
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Stage persists in GET /api/ideas list (stage badge data contract)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage_visible_in_list_after_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Stage set via POST /api/ideas/{id}/stage is reflected in GET /api/ideas list.

    Spec 159 R2: stage badge on every idea card must use live stage from the API.
    """
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_idea(client, id="stage-in-list-idea")
        await client.post(
            "/api/ideas/stage-in-list-idea/stage",
            json={"stage": "reviewing"},
            headers=AUTH_HEADERS,
        )

        resp = await client.get("/api/ideas")
    data = resp.json()
    matching = [i for i in data["ideas"] if i["id"] == "stage-in-list-idea"]
    assert matching, "Idea not found in list"
    assert matching[0]["stage"] == "reviewing"
