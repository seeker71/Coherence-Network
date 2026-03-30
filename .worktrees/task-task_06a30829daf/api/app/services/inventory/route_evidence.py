"""Route evidence: probe dir, probe read, endpoint normalization, build route evidence inventory."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services import route_registry_service, runtime_service
from app.services.inventory.evidence import _read_commit_evidence_records
from app.services.inventory.spec_discovery import (
    _github_headers,
    _project_root,
    _tracking_ref,
    _tracking_repository,
)

_ROUTE_PROBE_DISCOVERY_CACHE: dict[str, Any] = {"expires_at": 0.0, "item": None, "source": "none"}
_ROUTE_PROBE_DISCOVERY_CACHE_TTL_SECONDS = 180.0
_ROUTE_PROBE_LATEST_FILE = "route_evidence_probe_latest.json"


def _route_evidence_probe_dir() -> Path:
    custom = os.getenv("ROUTE_EVIDENCE_PROBE_DIR")
    if custom:
        return Path(custom)
    return _project_root() / "docs" / "system_audit"


def _read_latest_route_evidence_probe() -> dict[str, Any] | None:
    probe_dir = _route_evidence_probe_dir()
    if not probe_dir.exists():
        local_payload = None
    else:
        files = sorted(probe_dir.glob("route_evidence_probe_*.json"))
        if not files:
            local_payload = None
        else:
            latest = max(files, key=lambda path: path.stat().st_mtime)
            try:
                payload = json.loads(latest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                local_payload = None
            else:
                if isinstance(payload, dict):
                    payload["_probe_file"] = str(latest)
                    local_payload = payload
                else:
                    local_payload = None
    if local_payload is not None:
        return local_payload

    now = time.time()
    cached = _ROUTE_PROBE_DISCOVERY_CACHE.get("item")
    if isinstance(cached, dict) and _ROUTE_PROBE_DISCOVERY_CACHE.get("expires_at", 0.0) > now:
        return dict(cached)

    repository = _tracking_repository()
    ref = _tracking_ref()
    raw_latest_url = (
        f"https://raw.githubusercontent.com/{repository}/{ref}/docs/system_audit/{_ROUTE_PROBE_LATEST_FILE}"
    )
    list_url = f"https://api.github.com/repos/{repository}/contents/docs/system_audit"
    remote_payload: dict[str, Any] | None = None
    try:
        with httpx.Client(timeout=8.0, headers=_github_headers()) as client:
            raw_latest = client.get(raw_latest_url)
            if raw_latest.status_code == 200:
                try:
                    payload = raw_latest.json()
                except ValueError:
                    payload = None
                if isinstance(payload, dict):
                    payload["_probe_file"] = f"docs/system_audit/{_ROUTE_PROBE_LATEST_FILE}"
                    remote_payload = payload
            if remote_payload is not None:
                _ROUTE_PROBE_DISCOVERY_CACHE["item"] = dict(remote_payload)
                _ROUTE_PROBE_DISCOVERY_CACHE["expires_at"] = now + _ROUTE_PROBE_DISCOVERY_CACHE_TTL_SECONDS
                _ROUTE_PROBE_DISCOVERY_CACHE["source"] = "github-raw-latest"
                return remote_payload

            response = client.get(list_url, params={"ref": ref})
            response.raise_for_status()
            rows = response.json()
            if isinstance(rows, list):
                probes = [
                    row
                    for row in rows
                    if isinstance(row, dict)
                    and isinstance(row.get("name"), str)
                    and row["name"].startswith("route_evidence_probe_")
                    and row["name"].endswith(".json")
                ]
                probes.sort(key=lambda row: str(row.get("name") or ""), reverse=True)
                for row in probes[:5]:
                    download_url = row.get("download_url")
                    if not isinstance(download_url, str) or not download_url:
                        continue
                    payload_resp = client.get(download_url)
                    if payload_resp.status_code != 200:
                        continue
                    try:
                        payload = payload_resp.json()
                    except ValueError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    payload["_probe_file"] = str(row.get("path") or row.get("name") or "github")
                    remote_payload = payload
                    break
    except httpx.HTTPError:
        remote_payload = None

    _ROUTE_PROBE_DISCOVERY_CACHE["item"] = dict(remote_payload) if isinstance(remote_payload, dict) else None
    _ROUTE_PROBE_DISCOVERY_CACHE["expires_at"] = now + _ROUTE_PROBE_DISCOVERY_CACHE_TTL_SECONDS
    _ROUTE_PROBE_DISCOVERY_CACHE["source"] = "github" if remote_payload is not None else "none"
    return remote_payload


def _normalize_endpoint_path(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme else raw
    path = path.split("?", 1)[0].strip()
    if not path:
        return "/"
    if not path.startswith("/"):
        path = f"/{path}"
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def _path_template_matches(path_template: str, concrete_path: str) -> bool:
    template = _normalize_endpoint_path(path_template)
    concrete = _normalize_endpoint_path(concrete_path)
    if not template or not concrete:
        return False
    if template == concrete:
        return True
    escaped = re.escape(template)
    escaped = re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", escaped)
    escaped = re.sub(r"\\\[[^\[\]]+\\\]", r"[^/]+", escaped)
    pattern = f"^{escaped}$"
    return re.match(pattern, concrete) is not None


def _public_endpoint_reference_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        e2e = record.get("e2e_validation")
        if not isinstance(e2e, dict):
            continue
        endpoints = e2e.get("public_endpoints")
        if not isinstance(endpoints, list):
            continue
        for endpoint in endpoints:
            normalized = _normalize_endpoint_path(str(endpoint))
            if not normalized:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def _count_matching_public_references(path_template: str, reference_counts: dict[str, int]) -> int:
    if not reference_counts:
        return 0
    total = 0
    for path, count in reference_counts.items():
        if _path_template_matches(path_template, path):
            total += int(count)
    return total


def _probe_api_rows_by_key(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    rows = payload.get("api")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        method = str(row.get("method") or "").strip().upper()
        path = _normalize_endpoint_path(str(row.get("path_template") or row.get("path") or ""))
        if not method or not path:
            continue
        status = row.get("status_code")
        status_code = int(status) if isinstance(status, int) else None
        probe_method = str(row.get("probe_method") or ("GET" if method == "GET" else "OPTIONS")).strip().upper()
        data_present_raw = row.get("data_present")
        data_present = bool(data_present_raw) if isinstance(data_present_raw, bool) else None
        probe_ok = bool(row.get("probe_ok")) if isinstance(row.get("probe_ok"), bool) else False
        out[(method, path)] = {
            "status_code": status_code,
            "probe_method": probe_method,
            "data_present": data_present,
            "probe_ok": probe_ok,
        }
    return out


def _probe_web_rows_by_path(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    rows = payload.get("web")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = _normalize_endpoint_path(str(row.get("path_template") or row.get("path") or ""))
        if not path:
            continue
        status = row.get("status_code")
        status_code = int(status) if isinstance(status, int) else None
        data_present_raw = row.get("data_present")
        data_present = bool(data_present_raw) if isinstance(data_present_raw, bool) else None
        probe_ok = bool(row.get("probe_ok")) if isinstance(row.get("probe_ok"), bool) else False
        out[path] = {"status_code": status_code, "data_present": data_present, "probe_ok": probe_ok}
    return out


def _api_method_expects_real_data(method: str) -> bool:
    return str(method or "").strip().upper() == "GET"


def _is_probe_real_data_ok(expect_real_data: bool, probe_ok: bool, data_present: bool | None) -> bool:
    if not probe_ok:
        return False
    if not expect_real_data:
        return True
    return bool(data_present)


def _build_api_route_evidence_items(
    api_routes: list[dict[str, Any]],
    runtime_by_endpoint: dict[str, Any],
    public_reference_counts: dict[str, int],
    probe_api: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    api_items: list[dict[str, Any]] = []
    for row in api_routes:
        if not isinstance(row, dict):
            continue
        path_template = _normalize_endpoint_path(str(row.get("path") or ""))
        methods = [
            str(item).strip().upper()
            for item in (row.get("methods") if isinstance(row.get("methods"), list) else [])
            if str(item).strip()
        ]
        if not path_template or not methods:
            continue
        runtime_entry = runtime_by_endpoint.get(path_template)
        runtime_event_count = int(getattr(runtime_entry, "event_count", 0)) if runtime_entry else 0
        public_refs = _count_matching_public_references(path_template, public_reference_counts)
        method_items: list[dict[str, Any]] = []
        has_evidence_for_route = False
        route_missing_real_data_count = 0
        for method in methods:
            probe_row = probe_api.get((method, path_template)) or {}
            probe_status = probe_row.get("status_code")
            probe_ok = bool(probe_row.get("probe_ok"))
            data_present = probe_row.get("data_present") if isinstance(probe_row.get("data_present"), bool) else None
            expect_real_data = _api_method_expects_real_data(method)
            probe_real_data_ok = _is_probe_real_data_ok(expect_real_data, probe_ok, data_present)
            has_evidence = runtime_event_count > 0 or public_refs > 0 or probe_real_data_ok
            missing_real_data = expect_real_data and probe_ok and not bool(data_present)
            if has_evidence:
                has_evidence_for_route = True
            if missing_real_data:
                route_missing_real_data_count += 1
            method_items.append(
                {
                    "method": method,
                    "probe_status_code": probe_status,
                    "probe_ok": probe_ok,
                    "expects_real_data": expect_real_data,
                    "probe_data_present": data_present,
                    "probe_real_data_ok": probe_real_data_ok,
                    "missing_real_data": missing_real_data,
                    "has_actual_evidence": has_evidence,
                }
            )
        api_items.append(
            {
                "path": path_template,
                "methods": methods,
                "idea_id": str(row.get("idea_id") or "").strip() or None,
                "purpose": str(row.get("purpose") or "").strip() or None,
                "runtime_event_count": runtime_event_count,
                "public_reference_count": public_refs,
                "methods_evidence": method_items,
                "missing_real_data_count": route_missing_real_data_count,
                "has_actual_evidence": has_evidence_for_route,
            }
        )
    api_items.sort(key=lambda item: (not item["has_actual_evidence"], item["path"]))
    return api_items


def _build_web_route_evidence_items(
    web_routes: list[dict[str, Any]],
    runtime_by_endpoint: dict[str, Any],
    public_reference_counts: dict[str, int],
    probe_web: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    web_items: list[dict[str, Any]] = []
    for row in web_routes:
        if not isinstance(row, dict):
            continue
        path_template = _normalize_endpoint_path(str(row.get("path") or ""))
        if not path_template:
            continue
        runtime_entry = runtime_by_endpoint.get(path_template)
        runtime_event_count = int(getattr(runtime_entry, "event_count", 0)) if runtime_entry else 0
        public_refs = _count_matching_public_references(path_template, public_reference_counts)
        probe_row = probe_web.get(path_template) or {}
        probe_status = probe_row.get("status_code")
        probe_ok = bool(probe_row.get("probe_ok"))
        data_present = probe_row.get("data_present") if isinstance(probe_row.get("data_present"), bool) else None
        expect_real_data = True
        probe_real_data_ok = _is_probe_real_data_ok(expect_real_data, probe_ok, data_present)
        missing_real_data = expect_real_data and probe_ok and not bool(data_present)
        has_evidence = runtime_event_count > 0 or public_refs > 0 or probe_real_data_ok
        web_items.append(
            {
                "path": path_template,
                "idea_id": str(row.get("idea_id") or "").strip() or None,
                "purpose": str(row.get("purpose") or "").strip() or None,
                "runtime_event_count": runtime_event_count,
                "public_reference_count": public_refs,
                "probe_status_code": probe_status,
                "probe_ok": probe_ok,
                "expects_real_data": expect_real_data,
                "probe_data_present": data_present,
                "probe_real_data_ok": probe_real_data_ok,
                "missing_real_data": missing_real_data,
                "has_actual_evidence": has_evidence,
            }
        )
    web_items.sort(key=lambda item: (not item["has_actual_evidence"], item["path"]))
    return web_items


def _route_evidence_summary(api_items: list[dict[str, Any]], web_items: list[dict[str, Any]]) -> dict[str, int]:
    missing_api = sum(1 for item in api_items if not item["has_actual_evidence"])
    missing_web = sum(1 for item in web_items if not item["has_actual_evidence"])
    missing_real_data_api = sum(int(item.get("missing_real_data_count") or 0) for item in api_items)
    missing_real_data_web = sum(1 for item in web_items if bool(item.get("missing_real_data")))
    return {
        "api_total": len(api_items),
        "api_with_actual_evidence": len(api_items) - missing_api,
        "api_missing_actual_evidence": missing_api,
        "api_missing_real_data": missing_real_data_api,
        "web_total": len(web_items),
        "web_with_actual_evidence": len(web_items) - missing_web,
        "web_missing_actual_evidence": missing_web,
        "web_missing_real_data": missing_real_data_web,
    }


def build_route_evidence_inventory(runtime_window_seconds: int = 86400) -> dict[str, Any]:
    canonical = route_registry_service.get_canonical_routes()
    api_routes = canonical.get("api_routes") if isinstance(canonical.get("api_routes"), list) else []
    web_routes = canonical.get("web_routes") if isinstance(canonical.get("web_routes"), list) else []
    runtime_rows = runtime_service.summarize_by_endpoint(seconds=runtime_window_seconds)
    runtime_by_endpoint = {str(row.endpoint): row for row in runtime_rows}
    commit_records = _read_commit_evidence_records(limit=1200)
    public_reference_counts = _public_endpoint_reference_counts(commit_records)
    probe_payload = _read_latest_route_evidence_probe() or {}
    probe_api = _probe_api_rows_by_key(probe_payload)
    probe_web = _probe_web_rows_by_path(probe_payload)
    api_items = _build_api_route_evidence_items(api_routes, runtime_by_endpoint, public_reference_counts, probe_api)
    web_items = _build_web_route_evidence_items(web_routes, runtime_by_endpoint, public_reference_counts, probe_web)
    missing_api = [item for item in api_items if not bool(item.get("has_actual_evidence"))]
    missing_web = [item for item in web_items if not bool(item.get("has_actual_evidence"))]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_window_seconds": runtime_window_seconds,
        "probe": {
            "available": bool(probe_payload),
            "source_file": probe_payload.get("_probe_file"),
            "generated_at": probe_payload.get("generated_at"),
        },
        "summary": _route_evidence_summary(api_items, web_items),
        "api_routes": api_items,
        "web_routes": web_items,
        "missing": {
            "api_routes": missing_api[:200],
            "web_routes": missing_web[:200],
        },
    }
