"""Places router — where presences are rooted.

Endpoints:
  POST   /api/presences/{id}/places           Root a presence in a place
  DELETE /api/presences/{id}/places/{place}   Unroot a presence
  GET    /api/presences/{id}/places           List a presence's places
  GET    /api/places/{id}/presences           List presences at a place

The body of POST accepts a free-form name ("Boulder") or an existing
place id ("place:boulder"). The service layer ensures place nodes are
idempotent on slug — two visitors typing "Boulder" land on the same
node, so co-located lists emerge naturally from the graph.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.services import graph_service, place_service


router = APIRouter()


class AtPlaceCreate(BaseModel):
    place: str = Field(..., min_length=1, max_length=200, description="Place id (place:foo) or free-form name")
    role: str | None = Field(None, max_length=20, description="home | based | frequent | founded — defaults to based")
    since: str | None = Field(None, max_length=40, description="Free-text date or year, e.g. '2019'")
    region: str | None = Field(None, max_length=100, description="State/canton (only used when place is a name and the place is being created)")
    country: str | None = Field(None, max_length=100, description="ISO country (only used when place is a name and the place is being created)")


@router.post(
    "/presences/{identity_id}/places",
    status_code=201,
    summary="Root a presence in a place",
)
async def add_at_place(identity_id: str, body: AtPlaceCreate) -> dict[str, Any]:
    presence = graph_service.get_node(identity_id)
    if not presence:
        raise HTTPException(status_code=404, detail=f"Presence '{identity_id}' not found")

    text = body.place.strip()
    # If the caller passes a region/country with a name (not an id), let
    # ensure_place stamp them onto the node before set_at_place runs.
    if not text.startswith("place:") and (body.region or body.country):
        place_service.ensure_place(text, region=body.region, country=body.country)

    try:
        result = place_service.set_at_place(
            identity_id,
            text,
            role=body.role or "based",
            since=body.since,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.delete(
    "/presences/{identity_id}/places/{place_id:path}",
    status_code=204,
    summary="Unroot a presence from a place",
)
async def remove_at_place(identity_id: str, place_id: str) -> Response:
    presence = graph_service.get_node(identity_id)
    if not presence:
        raise HTTPException(status_code=404, detail=f"Presence '{identity_id}' not found")
    place_service.clear_at_place(identity_id, place_id)
    return Response(status_code=204)


@router.get(
    "/presences/{identity_id}/places",
    summary="List the places a presence is rooted in",
)
async def list_places_for_presence(identity_id: str) -> dict[str, Any]:
    # Treat "no presence" as "no places" so the page can render
    # without a 404 dance — same shape the kindred and met-at endpoints
    # use for consistency.
    presence = graph_service.get_node(identity_id)
    if not presence:
        return {"presence_id": identity_id, "items": []}
    return {
        "presence_id": identity_id,
        "items": place_service.places_for(identity_id),
    }


@router.get(
    "/places/{place_id:path}/presences",
    summary="List presences rooted at a place",
)
async def list_presences_at_place(place_id: str, limit: int = 50) -> dict[str, Any]:
    place = graph_service.get_node(place_id)
    if not place:
        return {"place_id": place_id, "place_name": None, "items": []}
    return {
        "place_id": place_id,
        "place_name": place.get("name"),
        "region": place.get("region"),
        "country": place.get("country"),
        "items": place_service.presences_at(place_id, limit=limit),
    }
