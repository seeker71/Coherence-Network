from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.models.contributor_recognition import ContributorRecognitionSnapshot
from app.models.error import ErrorDetail
from app.services import contributor_recognition_service

router = APIRouter()


@router.get(
    "/contributors/{contributor_id}/recognition",
    response_model=ContributorRecognitionSnapshot,
    summary="Get contributor recognition snapshot",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def get_contributor_recognition(contributor_id: UUID, request: Request) -> ContributorRecognitionSnapshot:
    snapshot = contributor_recognition_service.get_contributor_recognition_snapshot(
        contributor_id,
        store=getattr(request.app.state, "graph_store", None),
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return snapshot
