"""Geolocation service — city-level contributor location storage and proximity search."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.geolocation import (
    ContributorLocation,
    ContributorLocationSet,
    LocalNewsResonance,
    LocalNewsResonanceResponse,
    NearbyContributor,
    NearbyIdea,
    NearbyResult,
)
from app.services import graph_service

# Property key inside the node's JSON properties blob
_GEO_KEY = "geo_location"
_MAX_LOCATION_NODES = 10_000  # cap for O(n) scan


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return approximate great-circle distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_all_contributors() -> list[dict[str, Any]]:
    """Return all contributor nodes (up to _MAX_LOCATION_NODES)."""
    result = graph_service.list_nodes(type="contributor", limit=_MAX_LOCATION_NODES)
    return result.get("items", [])


def _get_all_ideas() -> list[dict[str, Any]]:
    """Return all idea nodes (up to _MAX_LOCATION_NODES)."""
    result = graph_service.list_nodes(type="idea", limit=_MAX_LOCATION_NODES)
    return result.get("items", [])


def _resolve_node(contributor_id: str) -> Optional[dict[str, Any]]:
    """Resolve a contributor by node-id or legacy UUID."""
    node = graph_service.get_node(f"contributor:{contributor_id}")
    if node:
        return node
    # Search all contributors for matching legacy_id
    for n in _get_all_contributors():
        if n.get("legacy_id") == contributor_id:
            return n
    return None


def set_contributor_location(
    contributor_id: str, payload: ContributorLocationSet
) -> ContributorLocation:
    """Store or update city-level location for a contributor.

    The location is written as a nested dict into the graph node's
    JSON properties under the ``geo_location`` key.
    """
    node = _resolve_node(contributor_id)
    if not node:
        raise ValueError(f"Contributor '{contributor_id}' not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    geo_data = {
        "city": payload.city,
        "region": payload.region,
        "country": payload.country,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "visibility": payload.visibility.value,
        "updated_at": now_iso,
    }

    graph_service.update_node(node["id"], properties={_GEO_KEY: geo_data})

    return ContributorLocation(
        contributor_id=contributor_id,
        city=payload.city,
        region=payload.region,
        country=payload.country,
        latitude=payload.latitude,
        longitude=payload.longitude,
        visibility=payload.visibility,
        updated_at=datetime.fromisoformat(now_iso),
    )


def get_contributor_location(contributor_id: str) -> Optional[ContributorLocation]:
    """Return stored location for a contributor, or None if not set."""
    node = _resolve_node(contributor_id)
    if not node:
        return None
    properties = node.get("properties") or {}
    geo = properties.get(_GEO_KEY)
    if not geo or not isinstance(geo, dict):
        return None
    return ContributorLocation(
        contributor_id=contributor_id,
        city=geo.get("city", ""),
        region=geo.get("region"),
        country=geo.get("country", ""),
        latitude=float(geo.get("latitude", 0.0)),
        longitude=float(geo.get("longitude", 0.0)),
        visibility=geo.get("visibility", "contributors_only"),
        updated_at=datetime.fromisoformat(geo["updated_at"]) if geo.get("updated_at") else datetime.now(timezone.utc),
    )


def delete_contributor_location(contributor_id: str) -> bool:
    """Remove location data for a contributor (opt-out)."""
    node = _resolve_node(contributor_id)
    if not node:
        return False
    properties = dict(node.get("properties") or {})
    properties.pop(_GEO_KEY, None)
    # Replace properties entirely to remove the key
    graph_service.update_node(node["id"], properties=properties)
    return True


def find_nearby(
    lat: float, lon: float, radius_km: float = 100.0, limit: int = 50
) -> NearbyResult:
    """Find contributors and their ideas within *radius_km* of (lat, lon).

    Only contributors with ``visibility`` set to ``public`` or
    ``contributors_only`` are included.  Iteration is O(n) over stored
    nodes; city-level data keeps N small in practice.
    """
    radius_km = max(1.0, min(radius_km, 20_000.0))

    nearby_contributors: list[NearbyContributor] = []
    contributor_id_set: set[str] = set()
    contributor_geo_map: dict[str, NearbyContributor] = {}

    for node in _get_all_contributors():
        props = node.get("properties") or {}
        geo = props.get(_GEO_KEY)
        if not geo or not isinstance(geo, dict):
            continue
        visibility = geo.get("visibility", "private")
        if visibility == "private":
            continue

        try:
            node_lat = float(geo["latitude"])
            node_lon = float(geo["longitude"])
        except (KeyError, TypeError, ValueError):
            continue

        dist = _haversine_km(lat, lon, node_lat, node_lon)
        if dist > radius_km:
            continue

        # Use legacy_id (UUID) or node name as stable contributor reference
        cid = (
            (node.get("properties") or {}).get("legacy_id")
            or node.get("name", "")
        )
        name = node.get("name", "unknown")
        entry = NearbyContributor(
            contributor_id=cid,
            name=name,
            city=geo.get("city", ""),
            country=geo.get("country", ""),
            distance_km=round(dist, 2),
            coherence_score=props.get("coherence_score"),
        )
        nearby_contributors.append(entry)
        contributor_id_set.add(cid)
        contributor_geo_map[cid] = entry
        # Also index by node name so idea author matching works
        contributor_geo_map[name] = entry

    nearby_contributors.sort(key=lambda c: c.distance_km)
    nearby_contributors = nearby_contributors[:limit]

    # Rebuild contributor_geo_map from capped list
    contributor_geo_map_capped: dict[str, NearbyContributor] = {}
    for entry in nearby_contributors:
        contributor_geo_map_capped[entry.contributor_id] = entry
        contributor_geo_map_capped[entry.name] = entry

    # Collect ideas from nearby contributors
    nearby_ideas: list[NearbyIdea] = []
    for idea in _get_all_ideas():
        props = idea.get("properties") or {}
        author = props.get("author") or props.get("contributor_id") or idea.get("name", "")
        if author not in contributor_geo_map_capped:
            continue
        c_info = contributor_geo_map_capped[author]
        nearby_ideas.append(
            NearbyIdea(
                idea_id=idea.get("id", ""),
                title=idea.get("name") or idea.get("description", "")[:80],
                contributor_id=c_info.contributor_id,
                contributor_name=c_info.name,
                city=c_info.city,
                country=c_info.country,
                distance_km=c_info.distance_km,
            )
        )

    nearby_ideas.sort(key=lambda i: i.distance_km)
    nearby_ideas = nearby_ideas[:limit]

    return NearbyResult(
        contributors=nearby_contributors,
        ideas=nearby_ideas,
        query_lat=lat,
        query_lon=lon,
        radius_km=radius_km,
        total_contributors=len(nearby_contributors),
        total_ideas=len(nearby_ideas),
    )


def local_news_resonance(location: str, limit: int = 20) -> LocalNewsResonanceResponse:
    """Return news items that resonate with a given location string.

    Matches city/country tokens against cached news headlines/summaries
    and computes a simple keyword-overlap resonance score (0–1).
    """
    try:
        from app.services import news_ingestion_service  # noqa: PLC0415

        articles: list[dict[str, Any]] = news_ingestion_service.get_recent_articles(limit=200)
    except Exception:
        articles = []

    location_lower = location.lower()
    location_tokens = {
        tok for tok in location_lower.replace(",", " ").split() if len(tok) > 2
    }

    results: list[LocalNewsResonance] = []
    for article in articles:
        title = (article.get("title") or "").lower()
        summary = (article.get("summary") or "").lower()
        text_blob = f"{title} {summary}"

        matched = [tok for tok in location_tokens if tok in text_blob]
        if not matched:
            continue

        score = min(1.0, len(matched) / max(1, len(location_tokens)))

        pub_dt: Optional[datetime] = None
        pub_raw = article.get("published_at") or article.get("published")
        if pub_raw:
            try:
                pub_dt = datetime.fromisoformat(str(pub_raw))
            except ValueError:
                pass

        results.append(
            LocalNewsResonance(
                article_id=str(article.get("id") or article.get("article_id", "")),
                title=article.get("title", ""),
                url=article.get("url"),
                source=article.get("source"),
                published_at=pub_dt,
                resonance_score=round(score, 4),
                local_keywords=matched,
                location_match=location,
            )
        )

    results.sort(key=lambda r: r.resonance_score, reverse=True)
    return LocalNewsResonanceResponse(
        location=location,
        items=results[:limit],
        total=len(results[:limit]),
    )
