"""Import stack routes — spec 022."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from app.adapters.graph_store import GraphStore
from app.models.import_stack import ImportStackResponse
from app.services.import_stack_service import (
    parse_lockfile,
    parse_requirements,
    process_lockfile,
    process_requirements,
)

router = APIRouter()


def get_graph_store(request: Request) -> GraphStore:
    """Dependency: GraphStore from app state."""
    return request.app.state.graph_store


@router.post("/import/stack", response_model=ImportStackResponse)
async def import_stack(
    store: GraphStore = Depends(get_graph_store),
    file: Optional[UploadFile] = None,
):
    """POST /api/import/stack: upload package-lock.json or requirements.txt — spec 022, 025."""
    content: str | None = None
    is_requirements = False
    if file:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Expected filename")
        fn = file.filename.lower()
        if fn.endswith(".json"):
            is_requirements = False
        elif fn.endswith(".txt"):
            is_requirements = True
        else:
            raise HTTPException(
                status_code=400,
                detail="Expected package-lock.json or requirements.txt",
            )
        try:
            raw = await file.read()
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Invalid encoding")
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Provide multipart file (package-lock.json or requirements.txt)",
        )
    if is_requirements:
        pkgs = parse_requirements(content)
        if not pkgs:
            raise HTTPException(
                status_code=400,
                detail="No packages found in requirements.txt",
            )
        data = process_requirements(store, content)
    else:
        try:
            pkgs = parse_lockfile(content)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
        if not pkgs:
            raise HTTPException(
                status_code=400,
                detail="No packages found in lockfile (expected packages or dependencies)",
            )
        data = process_lockfile(store, content)
    return ImportStackResponse(**data)
