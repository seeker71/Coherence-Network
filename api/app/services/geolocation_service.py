"""Geolocation service — city-level contributor location storage and proximity search."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

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

# Graph-node key prefix for location data stored as node properties
_LOCATION_PROP = "geo_location"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return approximate great-circle distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def set_contributor_location(
    contributor_id: str, payload: ContributorLocationSet
) -> ContributorLocation:
    """Store or update city-level location for a contributor.

    The location is written as a JSON-serialisable dict into the graph node's
    properties under the ``geo_location`` key.  Only the node owner can update
    the location — authorisation is enforced at the router layer.
    """
    node_id = f"contributor:{contributor_id}"
    node = graph_service.get_node(node_id)
    if not node:
        # Fallback: try legacy UUID lookup
        all_nodes = graph_service.get_nodes_by_type("contributor")
        node = next(
            (n for n in all_nodes if n.get("legacy_id") == contributor_id),
            None,
        )
        if not node:
            raise ValueError(f"Contributor '{contributor_id}' not found")

    location = ContributorLocation(
        contributor_id=contributor_id,
        city=payload.city,
        region=payload.region,
        country=payload.country,
        latitude=payload.latitude,
        longitude=payload.longitude,
        visibility=payload.visibility,
        updated_at=datetime.now(timezone.utc),
    )

    # Persist location data inside the node properties
    graph_service.update_node_property(
        node_id,
        _LOCATION_PROP,
        {
            "city": location.city,
            "region": location.region,
            "country": location.country,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "visibility": location.visibility.value,
            "updated_at": location.updated_at.isoformat(),
        },
    )
    return location


def get_contributor_location(contributor_id: str) -> Optional[ContributorLocation]:
    """Return stored location for a contributor, or None if not set."""
    node_id = f"contributor:{contributor_id}"
    node = graph_service.get_node(node_id)
    if not node:
        return None
    geo = node.get(_LOCATION_PROP)
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
    node_id = f"contributor:{contributor_id}"
    node = graph_service.get_node(node_id)
    if not node:
        return False
    graph_service.update_node_property(node_id, _LOCATION_PROP, None)
    return True


def find_nearby(
    lat: float, lon: float, radius_km: float = 100.0, limit: int = 50
) -> NearbyResult:
    """Find contributors and their ideas within *radius_km* of (lat, lon).

    Iterates all contributor nodes that have a public/contributors_only location
    stored and computes haversine distance.  For performance on large networks
    a spatial index should replace this O(n) scan; city-level data means N is
    bounded to hundreds of cities anyway.
    """
    radius_km = max(1.0, min(radius_km, 20_000.0))

    all_contributors = graph_service.get_nodes_by_type("contributor")

    nearby_contributors: list[NearbyContributor] = []
    contributor_ids_nearby: list[str] = []

    for node in all_contributors:
        geo = node.get(_LOCATION_PROP)
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
        if dist <= radius_km:
            cid = node.get("legacy_id") or node.get("id", "")
            name = node.get("name", "unknown")
            nearby_contributors.append(
                NearbyContributor(
                    contributor_id=cid,
                    name=name,
                    city=geo.get("city", ""),
                    country=geo.get("country", ""),
                    distance_km=round(dist, 2),
                    coherence_score=node.get("coherence_score"),
                )
            )
            contributor_ids_nearby.append(cid)

    # Sort by distance, cap to limit
    nearby_contributors.sort(key=lambda c: c.distance_km)
    nearby_contributors = nearby_contributors[:limit]
    contributor_ids_nearby = [c.contributor_id for c in nearby_contributors]

    # Fetch ideas authored by nearby contributors
    nearby_ideas: list[NearbyIdea] = []
    if contributor_ids_nearby:
        all_ideas = graph_service.get_nodes_by_type("idea")
        contributor_geo_map = {c.contributor_id: c for c in nearby_contributors}

        for idea in all_ideas:
            author = idea.get("author") or idea.get("contributor_id") or ""
            if author in contributor_geo_map:
                c_info = contributor_geo_map[author]
                nearby_ideas.append(
                    NearbyIdea(
                        idea_id=idea.get("id", ""),
                        title=idea.get("title") or idea.get("name", ""),
                        contributor_id=author,
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

    Matches city/country keywords against cached news headlines and computes
    a simple keyword-overlap resonance score.
    """
    try:
        from app.services import news_ingestion_service  # noqa: PLC0415

        articles = news_ingestion_service.get_recent_articles(limit=200)
    except Exception:
        articles = []

    location_lower = location.lower()
    location_tokens = set(location_lower.replace(",", " ").split())

    results: list[LocalNewsResonance] = []
    for article in articles:
        title = (article.get("title") or "").lower()
        summary = (article.get("summary") or "").lower()
        text_blob = f"{title} {summary}"

        matched_keywords = [tok for tok in location_tokens if tok and len(tok) > 2 and tok in text_blob]
        if not matched_keywords:
            continue

        score = min(1.0, len(matched_keywords) / max(1, len(location_tokens)))

        pub_raw = article.get("published_at") or article.get("published")
        pub_dt: Optional[datetime] = None
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
                local_keywords=matched_keywords,
                location_match=location,
            )
        )

    results.sort(key=lambda r: r.resonance_score, reverse=True)
    results = results[:limit]

    return LocalNewsResonanceResponse(
        location=location,
        items=results,
        total=len(results),
    )
