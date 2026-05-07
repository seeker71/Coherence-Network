"""Field story router — source-backed narrative and frequency artifacts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import field_story_service

router = APIRouter()


class FieldStoryContributionIn(BaseModel):
    contributor_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    contribution_type: str = Field(default="addition", min_length=1)
    summary: str = Field(min_length=1)
    content_markdown: str = ""


@router.get("/field-stories", summary="List published field stories")
async def list_field_stories() -> dict:
    return {"items": field_story_service.list_field_stories()}


@router.get("/field-stories/{slug}", summary="Get a published field story")
async def get_field_story(slug: str) -> dict:
    try:
        return field_story_service.get_field_story(slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/field-stories/{slug}/artifacts/{artifact_id}",
    summary="Get a single field story artifact",
)
async def get_field_story_artifact(slug: str, artifact_id: str) -> dict:
    try:
        return field_story_service.get_field_story_artifact(slug, artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Artifact file not found: {exc}") from exc


@router.get(
    "/field-stories/{slug}/spectrum",
    summary="Get field story frequency spectrum summaries",
)
async def get_field_story_spectrum(slug: str) -> dict:
    try:
        return field_story_service.get_field_story_spectrum(slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/field-stories/{slug}/contributions",
    status_code=201,
    summary="Record an attributed field story contribution proposal",
)
async def contribute_field_story(slug: str, body: FieldStoryContributionIn) -> dict:
    try:
        return field_story_service.record_field_story_contribution(
            slug=slug,
            contributor_id=body.contributor_id,
            artifact_id=body.artifact_id,
            contribution_type=body.contribution_type,
            summary=body.summary,
            content_markdown=body.content_markdown,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
