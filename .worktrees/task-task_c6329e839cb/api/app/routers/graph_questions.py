"""Graph node open-questions router (Spec 182).

POST  /api/graph/nodes/{node_id}/questions              — add a question
PATCH /api/graph/nodes/{node_id}/questions/{question_id} — resolve/re-open
"""

from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse

from app.models.graph_zoom import AddQuestionRequest, PatchQuestionRequest, QuestionResponse
from app.services import zoom_service

router = APIRouter()


@router.post(
    "/graph/nodes/{node_id}/questions",
    response_model=QuestionResponse,
    status_code=201,
    tags=["graph"],
    summary="Add an open question to a node",
)
async def add_question(node_id: str, body: AddQuestionRequest):
    """Add an open question to a node."""
    try:
        result = zoom_service.add_question(node_id, body.question)
        return JSONResponse(status_code=201, content=result.model_dump())
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_id}' not found",
        )


@router.patch(
    "/graph/nodes/{node_id}/questions/{question_id}",
    response_model=QuestionResponse,
    tags=["graph"],
    summary="Resolve or re-open an open question on a node",
)
async def patch_question(node_id: str, question_id: str, body: PatchQuestionRequest):
    """Resolve or re-open an open question on a node."""
    try:
        return zoom_service.resolve_question(node_id, question_id, body.resolved)
    except KeyError as exc:
        key = str(exc)
        if key.startswith("'node:") or "node:" in key:
            raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
        raise HTTPException(
            status_code=404,
            detail=f"Question '{question_id}' not found on node '{node_id}'",
        )
