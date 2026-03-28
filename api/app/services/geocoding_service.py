"""GeocodingService — forward geocoding with OpenCage + Nominatim + fallback.

Converts human-readable location strings (city names, addresses) into
lat/lon coordinates.  The resolution chain is:

  1. OpenCage Geocoding API  (preferred; needs OPENCAGE_API_KEY)
  2. Nominatim / OpenStreetMap (free; rate-limited to 1 req/s)
  3. Return None             (graceful degradation)

Usage::

    svc = GeocodingService()
    result = svc.geocode("Berlin, Germany")
    if result:
        print(result.latitude, result.longitude, result.city)
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class GeocodingResult:
    """Resolved location from a geocoding query."""

    latitude: float
    longitude: float
    city: str
    region: Optional[str]
    country: str
    country_code: str
    formatted: str
    provider: str  # "opencage" | "nominatim" | "fallback"


# ---------------------------------------------------------------------------
# HTTP helper (thin wrapper so tests can monkeypatch easily)
# ---------------------------------------------------------------------------

_NOMINATIM_UA = "CoherenceNetwork/1.0 (contact@coherencycoin.com)"
_OPENCAGE_BASE = "https://api.opencagedata.com/geocode/v1/json"
_NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"

# Minimum seconds to wait between Nominatim requests (policy: max 1 req/s)
_NOMINATIM_MIN_INTERVAL = 1.0
_last_nominatim_call: float = 0.0


def _http_get_json(url: str, headers: Optional[dict] = None) -> dict:
    """Perform a simple GET request and return parsed JSON.

    Raises ``RuntimeError`` on HTTP error or JSON parse failure.
    Separated into its own function so tests can monkeypatch it.
    """
    import urllib.request, urllib.error, json  # noqa: E401

    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url}") from exc
    except Exception as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc

    try:
        return json.loads(body)
    except Exception as exc:
        raise RuntimeError(f"JSON parse error: {exc}") from exc


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


def _geocode_opencage(query: str, api_key: str) -> Optional[GeocodingResult]:
    """Try OpenCage Geocoding API.

    Returns a ``GeocodingResult`` on success, ``None`` on zero results.
    Propagates ``RuntimeError`` on HTTP / network failure.
    """
    url = (
        f"{_OPENCAGE_BASE}"
        f"?q={quote_plus(query)}&key={api_key}&limit=1&no_annotations=1"
    )
    data = _http_get_json(url)
    results = data.get("results") or []
    if not results:
        return None

    hit = results[0]
    geo = hit.get("geometry", {})
    components = hit.get("components", {})

    city = (
        components.get("city")
        or components.get("town")
        or components.get("village")
        or components.get("municipality")
        or query
    )
    return GeocodingResult(
        latitude=float(geo.get("lat", 0.0)),
        longitude=float(geo.get("lng", 0.0)),
        city=city,
        region=components.get("state") or components.get("region"),
        country=components.get("country", ""),
        country_code=(components.get("country_code") or "").upper(),
        formatted=hit.get("formatted", query),
        provider="opencage",
    )


def _geocode_nominatim(query: str) -> Optional[GeocodingResult]:
    """Try Nominatim / OSM geocoding (free, no API key).

    Enforces a 1-second inter-request delay to comply with usage policy.
    Returns a ``GeocodingResult`` on success, ``None`` on zero results.
    """
    global _last_nominatim_call  # noqa: PLW0603

    elapsed = time.monotonic() - _last_nominatim_call
    if elapsed < _NOMINATIM_MIN_INTERVAL:
        time.sleep(_NOMINATIM_MIN_INTERVAL - elapsed)

    url = (
        f"{_NOMINATIM_BASE}"
        f"?q={quote_plus(query)}&format=json&limit=1&addressdetails=1"
    )
    headers = {"User-Agent": _NOMINATIM_UA}
    _last_nominatim_call = time.monotonic()

    data = _http_get_json(url, headers=headers)
    if not data or not isinstance(data, list):
        return None

    hit = data[0]
    address = hit.get("address", {})
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or query
    )
    return GeocodingResult(
        latitude=float(hit.get("lat", 0.0)),
        longitude=float(hit.get("lon", 0.0)),
        city=city,
        region=address.get("state"),
        country=address.get("country", ""),
        country_code=(address.get("country_code") or "").upper(),
        formatted=hit.get("display_name", query),
        provider="nominatim",
    )


# ---------------------------------------------------------------------------
# Public service class
# ---------------------------------------------------------------------------


class GeocodingService:
    """Forward geocoding with OpenCage → Nominatim → None fallback chain.

    Parameters
    ----------
    opencage_api_key:
        OpenCage API key.  If ``None``, the environment variable
        ``OPENCAGE_API_KEY`` is used.  If neither is set, OpenCage is
        skipped and Nominatim is tried directly.
    use_nominatim_fallback:
        Whether to try Nominatim when OpenCage is unavailable or returns no
        results.  Defaults to ``True``.
    """

    def __init__(
        self,
        opencage_api_key: Optional[str] = None,
        use_nominatim_fallback: bool = True,
    ) -> None:
        self._opencage_key = opencage_api_key or os.environ.get("OPENCAGE_API_KEY") or ""
        self._use_nominatim = use_nominatim_fallback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def geocode(self, query: str) -> Optional[GeocodingResult]:
        """Resolve *query* to coordinates using the configured provider chain.

        Resolution order:
          1. OpenCage (if API key present)
          2. Nominatim (if enabled)
          3. ``None``
        """
        query = query.strip()
        if not query:
            return None

        # Try OpenCage first
        if self._opencage_key:
            try:
                result = _geocode_opencage(query, self._opencage_key)
                if result is not None:
                    return result
            except RuntimeError:
                pass  # fall through to Nominatim

        # Try Nominatim
        if self._use_nominatim:
            try:
                result = _geocode_nominatim(query)
                if result is not None:
                    return result
            except RuntimeError:
                pass

        return None

    def geocode_batch(self, queries: list[str]) -> dict[str, Optional[GeocodingResult]]:
        """Geocode multiple location strings.

        Returns a mapping ``{query: GeocodingResult | None}``.
        Nominatim rate-limiting is respected between calls.
        """
        return {q: self.geocode(q) for q in queries}

    def enrich_contributor_location(
        self, contributor_id: str, city_or_address: str
    ) -> Optional[dict]:
        """Geocode *city_or_address* and store it on the contributor.

        Returns the enriched location dict on success, ``None`` on failure.
        Delegates storage to the geolocation_service.
        """
        from app.models.geolocation import ContributorLocationSet
        from app.services import geolocation_service

        result = self.geocode(city_or_address)
        if result is None:
            return None

        payload = ContributorLocationSet(
            city=result.city,
            region=result.region,
            country=result.country_code or result.country,
            latitude=round(result.latitude, 2),
            longitude=round(result.longitude, 2),
        )
        try:
            location = geolocation_service.set_contributor_location(contributor_id, payload)
            return {
                "contributor_id": contributor_id,
                "city": location.city,
                "country": location.country,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "provider": result.provider,
            }
        except ValueError:
            return None
