"""Worldview lens registry — spec-181."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.auth import require_api_key
from app.models.lens_translation import WorldviewLensCreate, lens_public_dict
from app.services import translate_service
from app.services import lens_translation_service

router = APIRouter()


@router.get("/lenses/roi", summary="Aggregate lens engagement metrics")
def lenses_roi() -> dict:
    """Aggregate lens engagement metrics."""
    return lens_translation_service.get_roi_payload()


@router.get("/lenses", summary="List all registered worldview and discipline lenses")
def list_lenses() -> dict:
    """List all registered worldview and discipline lenses."""
    lenses = []
    for lid in translate_service.list_all_lens_ids():
        meta = translate_service.get_lens_meta(lid)
        if not meta:
            continue
        lenses.append(lens_public_dict(lid, meta))
    return {"lenses": lenses, "total": len(lenses)}


@router.get("/lenses/{lens_id}", summary="Get Lens")
def get_lens(lens_id: str) -> dict:
    meta = translate_service.get_lens_meta(lens_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Lens '{lens_id}' not found")
    return lens_public_dict(lens_id, meta)


@router.post("/lenses", status_code=201, summary="Create Lens")
def create_lens(body: WorldviewLensCreate, _key: str = Depends(require_api_key)) -> dict:
    if translate_service.get_lens_meta(body.lens_id):
        raise HTTPException(status_code=409, detail=f"Lens '{body.lens_id}' already exists")
    translate_service.register_lens_definition(
        body.lens_id,
        body.name,
        body.description,
        body.archetype_axes,
    )
    merged = translate_service.get_lens_meta(body.lens_id)
    assert merged is not None
    return lens_public_dict(body.lens_id, merged)
