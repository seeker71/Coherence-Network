"""Vision content routes backed by graph records."""

from __future__ import annotations

from fastapi import APIRouter

from app.services import vision_content_service


router = APIRouter()


@router.get("/vision/aligned", summary="Graph-backed aligned vision catalog")
def get_aligned_content() -> dict:
    return vision_content_service.get_aligned_content()


@router.get("/vision/{domain}/hub", summary="Graph-backed vision hub content")
def get_hub_content(domain: str) -> dict:
    return vision_content_service.get_hub_content(domain)


@router.get("/vision/{domain}/realize", summary="Graph-backed vision realize content")
def get_realize_content(domain: str) -> dict:
    return vision_content_service.get_realize_content(domain)
