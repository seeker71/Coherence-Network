"""Idea portfolio API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.idea import (
    IdeaPortfolioResponse,
    IdeaQuestionAnswerUpdate,
    IdeaUpdate,
    IdeaWithScore,
)
from app.services import idea_service

router = APIRouter()


@router.get(
    "/ideas",
    response_model=IdeaPortfolioResponse,
    summary="List ideas ranked by free energy score (ROI)",
    description="""
**Purpose**: Portfolio-based prioritization using free energy scoring to rank ideas by ROI.

**Spec**: [053-ideas-prioritization.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/053-ideas-prioritization.md)
**Idea**: `portfolio-governance` - Unified idea portfolio governance
**Tests**: `api/tests/test_ideas.py::test_list_ideas_returns_ranked_scores_and_summary`

**Free Energy Formula**: `(potential_value × confidence) / (estimated_cost + resistance_risk)`
- Higher score = better ROI
- Ideas sorted by score descending

**Use Case**: Machines can query this endpoint to understand system priorities and decide what to work on next.

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (add/modify ideas)
2. **Spec**: Update `/specs/053-ideas-prioritization.md` (if changing API contract)
3. **Tests**: Update `/api/tests/test_ideas.py` (add/modify tests)
4. **Implementation**: Update `/api/app/routers/ideas.py` (this file)
5. **Validation**: Run `pytest api/tests/test_ideas.py -v`
    """,
    responses={
        200: {
            "description": "Portfolio with ranked ideas and summary",
            "content": {
                "application/json": {
                    "example": {
                        "ideas": [
                            {
                                "id": "portfolio-governance",
                                "name": "Unified idea portfolio governance",
                                "description": "Track potential value, actual value, cost, and open questions for all ideas.",
                                "potential_value": 82.0,
                                "actual_value": 12.0,
                                "estimated_cost": 10.0,
                                "actual_cost": 0.0,
                                "resistance_risk": 2.0,
                                "confidence": 0.75,
                                "manifestation_status": "partial",
                                "interfaces": ["machine:api", "human:docs"],
                                "open_questions": [],
                                "free_energy_score": 5.125,
                                "value_gap": 70.0
                            }
                        ],
                        "summary": {
                            "total_ideas": 3,
                            "unvalidated_ideas": 2,
                            "validated_ideas": 1,
                            "total_potential_value": 250.0,
                            "total_actual_value": 30.0,
                            "total_value_gap": 220.0
                        }
                    }
                }
            }
        }
    },
    openapi_extra={
        "x-spec-file": "specs/053-ideas-prioritization.md",
        "x-idea-id": "portfolio-governance",
        "x-test-file": "api/tests/test_ideas.py",
        "x-implementation-file": "api/app/routers/ideas.py",
        "x-scoring-formula": "(potential_value × confidence) / (estimated_cost + resistance_risk)"
    }
)
async def list_ideas(
    only_unvalidated: bool = Query(False, description="When true, only return ideas not yet validated."),
) -> IdeaPortfolioResponse:
    """List ideas ranked by free energy score (ROI)."""
    return idea_service.list_ideas(only_unvalidated=only_unvalidated)


@router.get(
    "/ideas/{idea_id}",
    response_model=IdeaWithScore,
    summary="Retrieve specific idea with free energy score",
    description="""
**Purpose**: Fetch details for a single idea including computed free energy score and value gap.

**Spec**: [053-ideas-prioritization.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/053-ideas-prioritization.md)
**Idea**: `portfolio-governance`
**Tests**: `api/tests/test_ideas.py::test_get_idea_by_id_and_404`

**Use Case**: Machines can retrieve full context for an idea to understand motivation, open questions, and current progress.

**Change Process**: See GET /ideas for full change process.
    """,
    responses={
        200: {
            "description": "Idea found with score",
            "content": {
                "application/json": {
                    "example": {
                        "id": "portfolio-governance",
                        "name": "Unified idea portfolio governance",
                        "description": "Track potential value, actual value, cost, and open questions for all ideas.",
                        "potential_value": 82.0,
                        "actual_value": 12.0,
                        "estimated_cost": 10.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 2.0,
                        "confidence": 0.75,
                        "manifestation_status": "partial",
                        "interfaces": ["machine:api", "human:docs"],
                        "open_questions": [],
                        "free_energy_score": 5.125,
                        "value_gap": 70.0
                    }
                }
            }
        },
        404: {"description": "Idea not found"}
    },
    openapi_extra={
        "x-spec-file": "specs/053-ideas-prioritization.md",
        "x-idea-id": "portfolio-governance",
        "x-test-file": "api/tests/test_ideas.py"
    }
)
async def get_idea(idea_id: str) -> IdeaWithScore:
    """Retrieve specific idea with free energy score."""
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.patch(
    "/ideas/{idea_id}",
    response_model=IdeaWithScore,
    summary="Update idea validation fields after implementation",
    description="""
**Purpose**: Update actual_value, actual_cost, confidence, or manifestation_status after implementing/measuring an idea.

**Spec**: [053-ideas-prioritization.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/053-ideas-prioritization.md)
**Idea**: `portfolio-governance`
**Tests**: `api/tests/test_ideas.py::test_patch_idea_updates_fields`

**Typical Workflow**:
1. Implement idea
2. Measure actual value delivered
3. PATCH this endpoint with actual_value, actual_cost
4. Update manifestation_status to "validated"
5. Free energy score recalculates automatically

**Use Case**: Machines can update ideas as they complete work, enabling real-time ROI tracking.

**Change Process**: See GET /ideas for full change process.
    """,
    responses={
        200: {
            "description": "Idea updated with recalculated score",
            "content": {
                "application/json": {
                    "example": {
                        "id": "portfolio-governance",
                        "name": "Unified idea portfolio governance",
                        "potential_value": 82.0,
                        "actual_value": 34.5,
                        "estimated_cost": 10.0,
                        "actual_cost": 8.0,
                        "confidence": 0.75,
                        "manifestation_status": "validated",
                        "free_energy_score": 3.068,
                        "value_gap": 47.5
                    }
                }
            }
        },
        400: {"description": "At least one field required"},
        404: {"description": "Idea not found"}
    },
    openapi_extra={
        "x-spec-file": "specs/053-ideas-prioritization.md",
        "x-idea-id": "portfolio-governance",
        "x-test-file": "api/tests/test_ideas.py"
    }
)
async def update_idea(idea_id: str, data: IdeaUpdate) -> IdeaWithScore:
    """Update idea validation fields after implementation."""
    if all(
        field is None
        for field in (
            data.actual_value,
            data.actual_cost,
            data.confidence,
            data.manifestation_status,
        )
    ):
        raise HTTPException(status_code=400, detail="At least one field required")

    updated = idea_service.update_idea(
        idea_id=idea_id,
        actual_value=data.actual_value,
        actual_cost=data.actual_cost,
        confidence=data.confidence,
        manifestation_status=data.manifestation_status,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return updated


@router.post(
    "/ideas/{idea_id}/questions/answer",
    response_model=IdeaWithScore,
    summary="Answer an open question for an idea",
    description="""
**Purpose**: Record answers to open questions that help refine idea estimates and reduce uncertainty.

**Spec**: [053-ideas-prioritization.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/053-ideas-prioritization.md)
**Idea**: `portfolio-governance`
**Tests**: `api/tests/test_ideas.py`

**Typical Workflow**:
1. Idea has open_questions with estimated value_to_whole
2. Research/implement to answer question
3. POST to this endpoint with answer + measured_delta
4. Question is marked answered, idea confidence may increase

**Use Case**: Machines can systematically answer open questions to de-risk ideas before full implementation.

**Change Process**: See GET /ideas for full change process.
    """,
    responses={
        200: {
            "description": "Question answered, idea updated",
            "content": {
                "application/json": {
                    "example": {
                        "id": "portfolio-governance",
                        "name": "Unified idea portfolio governance",
                        "open_questions": [
                            {
                                "question": "Which leading indicators best represent energy flow?",
                                "value_to_whole": 28.0,
                                "estimated_cost": 2.0,
                                "answer": "Use runtime event_count and cost by idea",
                                "measured_delta": 3.0
                            }
                        ],
                        "free_energy_score": 5.125
                    }
                }
            }
        },
        404: {"description": "Idea not found or Question not found for idea"}
    },
    openapi_extra={
        "x-spec-file": "specs/053-ideas-prioritization.md",
        "x-idea-id": "portfolio-governance",
        "x-test-file": "api/tests/test_ideas.py"
    }
)
async def answer_idea_question(idea_id: str, data: IdeaQuestionAnswerUpdate) -> IdeaWithScore:
    """Answer an open question for an idea."""
    updated, question_found = idea_service.answer_question(
        idea_id=idea_id,
        question=data.question,
        answer=data.answer,
        measured_delta=data.measured_delta,
        answered_by=data.answered_by,
        evidence_refs=data.evidence_refs,
        evolved_from_answer_of=data.evolved_from_answer_of,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    if not question_found:
        raise HTTPException(status_code=404, detail="Question not found for idea")
    return updated
