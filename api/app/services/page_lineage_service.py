"""Page lineage ontology service for page->idea->spec->process traceability."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _config_path() -> Path:
    return _project_root() / "api" / "config" / "page_lineage.json"


def _repo_url() -> str:
    return os.getenv("REPO_URL", "https://github.com/seeker71/Coherence-Network").rstrip("/")


def _normalize_page_path(path: str) -> str:
    out = (path or "").strip()
    if not out:
        return "/"
    if "?" in out:
        out = out.split("?", 1)[0]
    if not out.startswith("/"):
        out = "/" + out
    out = re.sub(r"/{2,}", "/", out).rstrip("/")
    return out or "/"


def _discover_web_pages() -> list[str]:
    app_dir = _project_root() / "web" / "app"
    if not app_dir.exists():
        return []
    pages: list[str] = []
    for file in sorted(app_dir.rglob("page.tsx")):
        rel = file.parent.relative_to(app_dir)
        if rel.parts and rel.parts[0] == "api":
            continue
        if str(rel) == ".":
            pages.append("/")
            continue
        route = "/" + "/".join(rel.parts)
        pages.append(route)
    return sorted(set(pages))


def _load_registry_rows() -> list[dict[str, Any]]:
    path = _config_path()
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        page_path = _normalize_page_path(str(item.get("page_path") or ""))
        if not page_path:
            continue
        enriched = dict(item)
        enriched["page_path"] = page_path
        spec_path = str((item.get("spec") or {}).get("path") or "").strip()
        if spec_path:
            enriched["spec_url"] = f"{_repo_url()}/blob/main/{spec_path}"
        process_doc = str(item.get("process_doc") or "").strip()
        if process_doc:
            enriched["process_doc_url"] = f"{_repo_url()}/blob/main/{process_doc}"
        out.append(enriched)
    return out


def _template_matches(template_path: str, actual_path: str) -> bool:
    if template_path == actual_path:
        return True
    pattern = "^" + re.escape(template_path) + "$"
    pattern = re.sub(r"\\\[[^/]+\\\]", r"[^/]+", pattern)
    return bool(re.match(pattern, actual_path))


def _resolve_entry_for_path(rows: list[dict[str, Any]], page_path: str) -> dict[str, Any] | None:
    normalized = _normalize_page_path(page_path)
    for row in rows:
        if _template_matches(str(row.get("page_path") or ""), normalized):
            return row
    return None


def get_page_lineage(page_path: str | None = None) -> dict[str, Any]:
    rows = _load_registry_rows()
    web_pages = _discover_web_pages()
    mapped_paths = {str(row.get("page_path") or "") for row in rows}
    missing_pages = [path for path in web_pages if not any(_template_matches(t, path) for t in mapped_paths)]

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "principle": "Each page must be traceable to idea/root/spec/process/pseudocode/source/endpoints.",
        "web_pages_total": len(web_pages),
        "mapped_pages_total": len(web_pages) - len(missing_pages),
        "missing_pages": missing_pages,
        "entries": rows,
    }
    if page_path:
        payload["requested_page_path"] = _normalize_page_path(page_path)
        payload["entry"] = _resolve_entry_for_path(rows, page_path)
    return payload

