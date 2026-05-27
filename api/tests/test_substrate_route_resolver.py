"""Pins the route → page.tsx resolver behind GET /api/substrate/page.

The substrate badge in the web layout calls this endpoint to reveal what
cells compose the current page. The API container ships `api/` + `scripts/`
only — `web/app/` is not present at runtime — so the resolver must work
from the committed JSON manifest at `api/app/data/web_routes.json`. This
test asserts both paths: filesystem walking (dev, where the tree exists)
and manifest lookup (prod, where it doesn't).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.routers.substrate import (
    _load_route_manifest,
    _normalize_route,
    _resolve_route_to_page_path,
    _resolve_via_manifest,
)


def test_manifest_present_and_includes_root_and_dynamic_routes() -> None:
    manifest = _load_route_manifest()
    assert manifest, "web_routes.json missing — run scripts/generate_repo_indexes.py"
    assert manifest.get("/") == "web/app/page.tsx"
    assert manifest.get("/ideas/[idea_id]") == "web/app/ideas/[idea_id]/page.tsx"


@pytest.mark.parametrize(
    "route,expected",
    [
        ("/", "web/app/page.tsx"),
        ("/come-in", "web/app/come-in/page.tsx"),
        ("/ideas", "web/app/ideas/page.tsx"),
        # Static segment wins over a sibling dynamic segment.
        ("/ideas/new", "web/app/ideas/new/page.tsx"),
        # Dynamic segment fills in when no static sibling matches.
        ("/ideas/foo-bar", "web/app/ideas/[idea_id]/page.tsx"),
        # Composed: dynamic + nested static.
        ("/assets/abc/proof", "web/app/assets/[asset_id]/proof/page.tsx"),
        # Composed: dynamic + nested dynamic + …no, just dynamic + static.
        ("/ideas/foo-bar/resonance", "web/app/ideas/[idea_id]/resonance/page.tsx"),
        # Normalization: query strings and trailing slashes.
        ("/?utm=x", "web/app/page.tsx"),
        ("/come-in/", "web/app/come-in/page.tsx"),
        # Unknown route → None, not a crash.
        ("/this-route-does-not-exist", None),
    ],
)
def test_resolver_handles_static_dynamic_and_normalization(
    route: str, expected: str | None
) -> None:
    # The unified entry point — works in dev (filesystem present) and
    # prod (manifest fallback).
    assert _resolve_route_to_page_path(route) == expected

    # The manifest path explicitly — proves the prod container is covered
    # even though the filesystem branch happens to win in this test env.
    segments = _normalize_route(route)
    assert _resolve_via_manifest(segments) == expected


def test_normalize_route_strips_query_fragment_and_trailing_slash() -> None:
    assert _normalize_route("/foo/bar?x=1") == ["foo", "bar"]
    assert _normalize_route("/foo/bar#anchor") == ["foo", "bar"]
    assert _normalize_route("/foo/bar/") == ["foo", "bar"]
    assert _normalize_route("/") == []
