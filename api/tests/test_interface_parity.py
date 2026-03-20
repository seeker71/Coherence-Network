"""Interface parity tests: verify API responses match what web pages consume.

These contract tests ensure the 3 critical page-API pairs stay in sync.
If a field is renamed or removed from the API, these tests catch it before
the web page breaks.

Pairs tested:
  1. GET /api/health   <-> web/app/page.tsx + web/app/api-health/page.tsx
  2. GET /api/ideas     <-> web/app/ideas/page.tsx  (list + summary)
  3. GET /api/ideas/{id} <-> web/app/ideas/[idea_id]/page.tsx  (detail)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ── helpers ──────────────────────────────────────────────────────────

async def _seed_idea(client: AsyncClient, idea_id: str = "parity-test-1") -> dict:
    """Create a minimal idea and return its JSON."""
    resp = await client.post("/api/ideas", json={
        "id": idea_id,
        "name": "Interface Parity Idea",
        "description": "Seeded for contract tests.",
        "potential_value": 100.0,
        "estimated_cost": 20.0,
        "confidence": 0.7,
        "interfaces": ["web", "api"],
        "open_questions": [
            {
                "question": "Is the parity contract enforced?",
                "value_to_whole": 10.0,
                "estimated_cost": 2.0,
            }
        ],
    })
    assert resp.status_code == 201, f"Seed failed: {resp.status_code} {resp.text}"
    return resp.json()


# ── Pair 1: Health / Landing ─────────────────────────────────────────

class TestHealthLandingParity:
    """Pair 1: GET /api/health <-> web/app/page.tsx + web/app/api-health/page.tsx

    The api-health page renders the full JSON blob.  The landing page does
    not directly call /api/health, but the health endpoint shape must stay
    stable for the proxy page that dumps it verbatim.
    """

    @pytest.mark.asyncio
    async def test_health_response_has_status_field(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_response_has_expected_shape(self) -> None:
        """All fields the web api-health page may render (it dumps the whole object)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/health")
        data = resp.json()
        required_fields = {
            "status",
            "version",
            "timestamp",
            "started_at",
            "uptime_seconds",
            "uptime_human",
        }
        missing = required_fields - set(data.keys())
        assert not missing, f"Health response missing fields consumed by web: {missing}"

    @pytest.mark.asyncio
    async def test_health_field_types(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/health")
        data = resp.json()
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["started_at"], str)
        assert isinstance(data["uptime_seconds"], int)
        assert isinstance(data["uptime_human"], str)
        # Optional fields present but may be null
        assert "deployed_sha" in data
        assert "deployed_sha_source" in data


# ── Pair 2: Ideas List ──────────────────────────────────────────────

class TestIdeasListParity:
    """Pair 2: GET /api/ideas <-> web/app/ideas/page.tsx

    The ideas page reads:
      data.ideas[]   — array of IdeaWithScore
      data.summary   — aggregate counters

    Each idea row accesses:
      id, name, description, potential_value, actual_value, estimated_cost,
      actual_cost, confidence, resistance_risk, manifestation_status,
      interfaces, open_questions, free_energy_score, value_gap
    """

    @pytest.mark.asyncio
    async def test_ideas_response_has_ideas_array_and_summary(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _seed_idea(client)
            resp = await client.get("/api/ideas")

        assert resp.status_code == 200
        data = resp.json()
        assert "ideas" in data and isinstance(data["ideas"], list)
        assert "summary" in data and isinstance(data["summary"], dict)
        assert len(data["ideas"]) >= 1

    @pytest.mark.asyncio
    async def test_each_idea_has_fields_web_renders(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """Every field accessed by web/app/ideas/page.tsx must be present."""
        monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _seed_idea(client)
            resp = await client.get("/api/ideas")

        # Fields the ideas list page reads on each idea
        required_idea_fields = {
            "id",
            "name",
            "description",
            "potential_value",
            "actual_value",
            "estimated_cost",
            "actual_cost",
            "confidence",
            "resistance_risk",
            "manifestation_status",
            "interfaces",
            "open_questions",
            "free_energy_score",
            "value_gap",
        }

        for idea in resp.json()["ideas"]:
            missing = required_idea_fields - set(idea.keys())
            assert not missing, (
                f"Idea '{idea.get('id', '?')}' missing fields the ideas page renders: {missing}"
            )

    @pytest.mark.asyncio
    async def test_idea_field_types(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _seed_idea(client)
            resp = await client.get("/api/ideas")

        idea = resp.json()["ideas"][0]
        assert isinstance(idea["id"], str)
        assert isinstance(idea["name"], str)
        assert isinstance(idea["description"], str)
        assert isinstance(idea["potential_value"], (int, float))
        assert isinstance(idea["actual_value"], (int, float))
        assert isinstance(idea["estimated_cost"], (int, float))
        assert isinstance(idea["confidence"], (int, float))
        assert isinstance(idea["manifestation_status"], str)
        assert isinstance(idea["interfaces"], list)
        assert isinstance(idea["open_questions"], list)
        assert isinstance(idea["free_energy_score"], (int, float))
        assert isinstance(idea["value_gap"], (int, float))

    @pytest.mark.asyncio
    async def test_summary_has_fields_web_renders(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """The ideas page reads summary.total_ideas, total_potential_value,
        total_actual_value, total_value_gap.  The landing page reads the same
        four plus the full summary object.
        """
        monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _seed_idea(client)
            resp = await client.get("/api/ideas")

        summary = resp.json()["summary"]
        required_summary_fields = {
            "total_ideas",
            "total_potential_value",
            "total_actual_value",
            "total_value_gap",
        }
        missing = required_summary_fields - set(summary.keys())
        assert not missing, f"Summary missing fields the web pages render: {missing}"

        # Type checks
        assert isinstance(summary["total_ideas"], int)
        assert isinstance(summary["total_potential_value"], (int, float))
        assert isinstance(summary["total_actual_value"], (int, float))
        assert isinstance(summary["total_value_gap"], (int, float))

    @pytest.mark.asyncio
    async def test_open_question_shape(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """The detail and list pages both access question.question,
        question.value_to_whole, question.estimated_cost, question.answer,
        question.measured_delta.
        """
        monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _seed_idea(client)
            resp = await client.get("/api/ideas")

        idea = resp.json()["ideas"][0]
        assert len(idea["open_questions"]) >= 1
        q = idea["open_questions"][0]
        for field in ("question", "value_to_whole", "estimated_cost"):
            assert field in q, f"Question missing '{field}'"
        # answer and measured_delta are optional but keys must exist
        assert "answer" in q
        assert "measured_delta" in q


# ── Pair 3: Idea Detail ─────────────────────────────────────────────

class TestIdeaDetailParity:
    """Pair 3: GET /api/ideas/{id} <-> web/app/ideas/[idea_id]/page.tsx

    The detail page reads all the same fields as the list page plus:
      actual_cost, resistance_risk, interfaces, open_questions (full),
      free_energy_score, value_gap

    It also passes fields to child components:
      IdeaProgressEditor  -> actual_value, actual_cost, confidence, manifestation_status
      IdeaTaskQuickCreate -> open_questions (unanswered)
      IdeaDsssSpecBuilder -> potential_value, estimated_cost, open_questions
    """

    @pytest.mark.asyncio
    async def test_idea_detail_has_all_rendered_fields(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _seed_idea(client, "detail-parity-1")
            resp = await client.get("/api/ideas/detail-parity-1")

        assert resp.status_code == 200
        idea = resp.json()

        # Every field the detail page reads directly or passes to components
        required = {
            "id",
            "name",
            "description",
            "potential_value",
            "actual_value",
            "estimated_cost",
            "actual_cost",
            "confidence",
            "resistance_risk",
            "manifestation_status",
            "interfaces",
            "open_questions",
            "free_energy_score",
            "value_gap",
        }
        missing = required - set(idea.keys())
        assert not missing, f"Detail response missing fields the detail page renders: {missing}"

    @pytest.mark.asyncio
    async def test_idea_detail_has_score_fields(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """Score fields consumed or potentially rendered by the detail page."""
        monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _seed_idea(client, "score-parity-1")
            resp = await client.get("/api/ideas/score-parity-1")

        idea = resp.json()
        score_fields = {
            "free_energy_score",
            "marginal_cc_score",
            "value_gap",
            "selection_weight",
        }
        missing = score_fields - set(idea.keys())
        assert not missing, f"Detail missing score fields: {missing}"

        for field in score_fields:
            assert isinstance(idea[field], (int, float)), f"{field} must be numeric"

    @pytest.mark.asyncio
    async def test_idea_detail_has_cc_fields(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """CC (Coherence Credit) fields on the detail response."""
        monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _seed_idea(client, "cc-parity-1")
            resp = await client.get("/api/ideas/cc-parity-1")

        idea = resp.json()
        cc_fields = {
            "remaining_cost_cc",
            "value_gap_cc",
            "roi_cc",
        }
        missing = cc_fields - set(idea.keys())
        assert not missing, f"Detail missing CC fields: {missing}"

        # cost_vector and value_vector must be present (may be null)
        assert "cost_vector" in idea, "cost_vector key must exist"
        assert "value_vector" in idea, "value_vector key must exist"

    @pytest.mark.asyncio
    async def test_idea_detail_field_types_for_components(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """Verify types match what child components expect."""
        monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _seed_idea(client, "types-parity-1")
            resp = await client.get("/api/ideas/types-parity-1")

        idea = resp.json()

        # IdeaProgressEditor expects these exact types
        assert isinstance(idea["actual_value"], (int, float))
        assert isinstance(idea["actual_cost"], (int, float))
        assert isinstance(idea["confidence"], (int, float))
        assert isinstance(idea["manifestation_status"], str)
        assert idea["manifestation_status"] in {"none", "partial", "validated"}

        # IdeaDsssSpecBuilder expects these
        assert isinstance(idea["potential_value"], (int, float))
        assert isinstance(idea["estimated_cost"], (int, float))
        assert isinstance(idea["open_questions"], list)

        # IdeaTaskQuickCreate filters unanswered questions
        for q in idea["open_questions"]:
            assert "question" in q
            assert "answer" in q
