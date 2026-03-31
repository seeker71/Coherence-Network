"""Route matching and endpoint normalization for runtime telemetry."""

from __future__ import annotations

import re
from typing import Any

from app.services import route_registry_service


def normalize_path(endpoint: str) -> str:
    cleaned = str(endpoint or "").strip()
    if not cleaned:
        return "/"
    path = cleaned.split("?", 1)[0].strip()
    if not path:
        return "/"
    return path if path.startswith("/") else f"/{path}"


def canonical_api_routes() -> list[dict]:
    routes = route_registry_service.get_canonical_routes().get("api_routes", [])
    if not isinstance(routes, list):
        return []
    return [row for row in routes if isinstance(row, dict) and isinstance(row.get("path"), str)]


def template_regex(template: str) -> str:
    escaped = re.escape(template)
    return "^" + re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", escaped) + "$"


def method_allowed(route: dict, method: str | None) -> bool:
    if not method:
        return True
    methods = route.get("methods")
    if not isinstance(methods, list) or not methods:
        return True
    normalized = method.strip().upper()
    return normalized in {
        m.strip().upper() for m in methods if isinstance(m, str) and m.strip()
    }


def match_canonical_route(endpoint: str, method: str | None = None) -> dict | None:
    path = normalize_path(endpoint)
    routes = canonical_api_routes()

    for row in routes:
        template = str(row.get("path") or "").strip()
        if template == path and method_allowed(row, method):
            return row

    for row in routes:
        template = str(row.get("path") or "").strip()
        if "{" not in template or "}" not in template:
            continue
        if not method_allowed(row, method):
            continue
        if re.match(template_regex(template), path):
            return row

    return None


def normalize_endpoint(endpoint: str, method: str | None = None) -> str:
    path = normalize_path(endpoint)
    canonical = match_canonical_route(path, method=method)
    if isinstance(canonical, dict):
        canonical_path = str(canonical.get("path") or "").strip()
        if canonical_path:
            return canonical_path
    return path
