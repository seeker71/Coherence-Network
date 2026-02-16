"""Governance review and voting API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.governance import ChangeRequest, ChangeRequestCreate, ChangeRequestVoteCreate
from app.services import governance_service

router = APIRouter()


@router.get("/governance/change-requests", response_model=list[ChangeRequest])
async def list_change_requests(limit: int = Query(200, ge=1, le=1000)) -> list[ChangeRequest]:
    return governance_service.list_change_requests(limit=limit)


@router.get("/governance/change-requests/{change_request_id}", response_model=ChangeRequest)
async def get_change_request(change_request_id: str) -> ChangeRequest:
    found = governance_service.get_change_request(change_request_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Change request not found")
    return found


@router.post("/governance/change-requests", response_model=ChangeRequest, status_code=201)
async def create_change_request(data: ChangeRequestCreate) -> ChangeRequest:
    return governance_service.create_change_request(data)


@router.post("/governance/change-requests/{change_request_id}/votes", response_model=ChangeRequest)
async def cast_vote(change_request_id: str, data: ChangeRequestVoteCreate) -> ChangeRequest:
    updated = governance_service.cast_vote(change_request_id, data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Change request not found")
    return updated
