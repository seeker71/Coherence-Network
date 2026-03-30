"""Forward geocoding: OpenCage → Nominatim → static fallback (Living Codex–style chain).

OpenCage is used when ``OPENCAGE_API_KEY`` is set. Nominatim (OpenStreetMap) is the
secondary provider; requests use a descriptive User-Agent per OSM usage policy.
If both fail, a tiny built-in city table provides coarse centers for demos/tests.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

import httpx

from app.models.geocoding import GeocodeForwardResponse, GeocodeSource

logger = logging.getLogger(__name__)

# Identifying app for Nominatim (https://operations.osmfoundation.org/policies/nominatim/)
_NOMINATIM_UA = "CoherenceNetwork/1.0 (geocoding; https://github.com/seeker71/Coherence-Network)"

# Coarse city centers (~ administrative), 2-decimal precision. Offline / CI fallback only.
_FALLBACK_CENTERS: dict[str, tuple[float, float, str]] = {
    "berlin": (52.52, 13.41, "Berlin, Germany"),
    "paris": (48.86, 2.35, "Paris, France"),
    "london": (51.51, -0.13, "London, United Kingdom"),
    "tokyo": (35.68, 139.69, "Tokyo, Japan"),
    "sydney": (-33.87, 151.21, "Sydney, Australia"),
    "new york": (40.71, -74.01, "New York, United States"),
}


def _round_coord(value: float) -> float:
    return round(float(value), 2)


def _normalize_key(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return s


def _fallback_lookup(query: str) -> Optional[GeocodeForwardResponse]:
    """Try static city centers when remote providers fail."""
    nq = _normalize_key(query)
    for key, (lat, lon, label) in _FALLBACK_CENTERS.items():
        if key in nq or nq in key:
            return GeocodeForwardResponse(
                query=query.strip(),
                found=True,
                latitude=_round_coord(lat),
                longitude=_round_coord(lon),
                display_name=label,
                source=GeocodeSource.FALLBACK.value,
            )
    return None


def _opencage_geocode(query: str, api_key: str, client: httpx.Client) -> Optional[GeocodeForwardResponse]:
    url = "https://api.opencagedata.com/geocode/v1/json"
    try:
        r = client.get(
            url,
            params={"q": query, "key": api_key, "limit": 1},
            timeout=8.0,
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        logger.debug("OpenCage geocode failed: %s", exc)
        return None

    results = data.get("results") or []
    if not results:
        return None
    geom = (results[0].get("geometry") or {})
    lat = geom.get("lat")
    lon = geom.get("lng")
    if lat is None or lon is None:
        return None
    formatted = (results[0].get("formatted") or query)[:500]
    return GeocodeForwardResponse(
        query=query.strip(),
        found=True,
        latitude=_round_coord(float(lat)),
        longitude=_round_coord(float(lon)),
        display_name=formatted,
        source=GeocodeSource.OPENCAGE.value,
    )


def _nominatim_geocode(query: str, client: httpx.Client) -> Optional[GeocodeForwardResponse]:
    url = "https://nominatim.openstreetmap.org/search"
    try:
        r = client.get(
            url,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": _NOMINATIM_UA, "Accept-Language": "en"},
            timeout=8.0,
        )
        r.raise_for_status()
        rows = r.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        logger.debug("Nominatim geocode failed: %s", exc)
        return None

    if not isinstance(rows, list) or not rows:
        return None
    first: dict[str, Any] = rows[0]
    lat_str, lon_str = first.get("lat"), first.get("lon")
    if lat_str is None or lon_str is None:
        return None
    display = (first.get("display_name") or query)[:500]
    return GeocodeForwardResponse(
        query=query.strip(),
        found=True,
        latitude=_round_coord(float(lat_str)),
        longitude=_round_coord(float(lon_str)),
        display_name=display,
        source=GeocodeSource.NOMINATIM.value,
    )


def forward_geocode(query: str, client: Optional[httpx.Client] = None) -> GeocodeForwardResponse:
    """Resolve *query* to coordinates. Never raises for HTTP failures — returns ``found=False``."""
    q = (query or "").strip()
    if len(q) < 2:
        return GeocodeForwardResponse(query=q, found=False)

    owns_client = client is None
    hc = client or httpx.Client(timeout=10.0)

    try:
        key = os.getenv("OPENCAGE_API_KEY", "").strip()
        if key:
            oc = _opencage_geocode(q, key, hc)
            if oc and oc.found:
                return oc

        nom = _nominatim_geocode(q, hc)
        if nom and nom.found:
            return nom

        fb = _fallback_lookup(q)
        if fb:
            return fb

        return GeocodeForwardResponse(query=q, found=False)
    finally:
        if owns_client:
            hc.close()
