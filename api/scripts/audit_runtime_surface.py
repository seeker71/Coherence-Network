#!/usr/bin/env python3
"""Audit mounted API routes vs declared routers and web client expectations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from app.main import app
from app.routers import agent as agent_router

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_APP_DIR = PROJECT_ROOT / "web" / "app"

FETCH_PATH_RE = re.compile(r"fetch\([^)]*?\$\{API_URL\}(/api/[^\s`\"')]+)")


def _mounted_routes() -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for route in app.router.routes:
        path = getattr(route, "path", None)
        methods = sorted(m for m in (getattr(route, "methods", set()) or set()) if m != "HEAD")
        if not path or not methods:
            continue
        out.append({"path": path, "methods": methods})
    return sorted(out, key=lambda x: x["path"])


def _declared_agent_paths() -> set[str]:
    out: set[str] = set()
    for route in agent_router.router.routes:
        path = getattr(route, "path", None)
        if path:
            out.add(path)
    return out


def _web_expected_paths(files: Iterable[Path]) -> set[str]:
    expected: set[str] = set()
    for f in files:
        text = f.read_text(encoding="utf-8")
        for match in FETCH_PATH_RE.findall(text):
            cleaned = match.split("${", 1)[0].rstrip()
            expected.add(cleaned)
    return expected


def _normalize(path: str) -> str:
    # Compare only stable prefix for dynamic project paths.
    if path.startswith("/api/projects/"):
        return "/api/projects/*"
    if path.startswith("/api/search"):
        return "/api/search"
    if path.startswith("/api/import/stack"):
        return "/api/import/stack"
    return path


def main() -> None:
    mounted = _mounted_routes()
    mounted_paths = {r["path"] for r in mounted}
    mounted_normalized = {_normalize(p) for p in mounted_paths}

    web_files = sorted(WEB_APP_DIR.rglob("*.tsx"))
    web_expected = _web_expected_paths(web_files)
    web_expected_normalized = {_normalize(p) for p in web_expected}

    missing_for_web = sorted(p for p in web_expected if _normalize(p) not in mounted_normalized)

    declared_agent = _declared_agent_paths()
    mounted_agent = sorted(p for p in mounted_paths if p.startswith("/api/agent/"))
    unmounted_agent = sorted(p for p in declared_agent if p not in mounted_paths)

    result = {
        "mounted_route_count": len(mounted),
        "mounted_routes": mounted,
        "web_expected_paths": sorted(web_expected),
        "missing_for_web": missing_for_web,
        "agent_router": {
            "declared_count": len(declared_agent),
            "mounted_count": len(mounted_agent),
            "unmounted_paths": unmounted_agent,
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
