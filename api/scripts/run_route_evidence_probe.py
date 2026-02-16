#!/usr/bin/env python3
"""Probe canonical API and web routes and write evidence artifact."""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.services import route_registry_service


def _materialize_path(path_template: str) -> str:
    path = str(path_template or "").strip()
    if not path:
        return "/"
    path = re.sub(r"\{[^{}]+\}", "sample", path)
    path = re.sub(r"\[[^\[\]]+\]", "sample", path)
    if not path.startswith("/"):
        path = f"/{path}"
    return path


def _json_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        return len(value) > 0
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _data_present_for_response(response: httpx.Response, probe_method: str) -> bool | None:
    method = str(probe_method or "").upper()
    if method != "GET":
        return None

    body_text = response.text or ""
    if not body_text.strip():
        return False

    content_type = str(response.headers.get("content-type") or "").lower()
    if "json" in content_type:
        try:
            payload = response.json()
        except ValueError:
            return False
        return _json_non_empty(payload)
    return True


def _probe_ok(status_code: int | None, probe_method: str, data_present: bool | None) -> bool:
    if status_code is None:
        return False
    method = str(probe_method or "").upper()
    if method == "GET":
        return int(status_code) < 400 and bool(data_present)
    return int(status_code) in {200, 204, 405}


def _request(
    client: httpx.Client, method: str, url: str, timeout_seconds: float
) -> tuple[int | None, float, str | None, str | None, int | None, bool | None]:
    started = time.perf_counter()
    try:
        response = client.request(method, url, timeout=timeout_seconds, follow_redirects=True)
        elapsed = round((time.perf_counter() - started) * 1000.0, 3)
        content_type = str(response.headers.get("content-type") or "").strip() or None
        body_bytes = len(response.content) if response.content is not None else 0
        data_present = _data_present_for_response(response, method)
        return int(response.status_code), elapsed, None, content_type, body_bytes, data_present
    except Exception as exc:  # noqa: BLE001
        elapsed = round((time.perf_counter() - started) * 1000.0, 3)
        return None, elapsed, str(exc), None, None, None


def run_probe(api_base_url: str, web_base_url: str, timeout_seconds: float) -> dict[str, Any]:
    registry = route_registry_service.get_canonical_routes()
    api_routes = registry.get("api_routes") if isinstance(registry.get("api_routes"), list) else []
    web_routes = registry.get("web_routes") if isinstance(registry.get("web_routes"), list) else []

    api_rows: list[dict[str, Any]] = []
    web_rows: list[dict[str, Any]] = []

    with httpx.Client() as client:
        for row in api_routes:
            if not isinstance(row, dict):
                continue
            path_template = str(row.get("path") or "").strip()
            methods = [
                str(m).strip().upper()
                for m in (row.get("methods") if isinstance(row.get("methods"), list) else [])
                if str(m).strip()
            ]
            if not path_template or not methods:
                continue
            path = _materialize_path(path_template)
            for method in methods:
                probe_method = "GET" if method == "GET" else "OPTIONS"
                url = f"{api_base_url.rstrip('/')}{path}"
                status_code, elapsed_ms, error, content_type, body_bytes, data_present = _request(
                    client, probe_method, url, timeout_seconds
                )
                api_rows.append(
                    {
                        "path_template": path_template,
                        "path": path,
                        "method": method,
                        "probe_method": probe_method,
                        "url": url,
                        "status_code": status_code,
                        "probe_ok": _probe_ok(status_code, probe_method, data_present),
                        "expects_real_data": method == "GET",
                        "data_present": data_present,
                        "content_type": content_type,
                        "body_bytes": body_bytes,
                        "runtime_ms": elapsed_ms,
                        "error": error,
                    }
                )

        for row in web_routes:
            if not isinstance(row, dict):
                continue
            path_template = str(row.get("path") or "").strip()
            if not path_template:
                continue
            path = _materialize_path(path_template)
            url = f"{web_base_url.rstrip('/')}{path}"
            status_code, elapsed_ms, error, content_type, body_bytes, data_present = _request(
                client, "GET", url, timeout_seconds
            )
            web_rows.append(
                {
                    "path_template": path_template,
                    "path": path,
                    "url": url,
                    "status_code": status_code,
                    "probe_ok": _probe_ok(status_code, "GET", data_present),
                    "expects_real_data": True,
                    "data_present": data_present,
                    "content_type": content_type,
                    "body_bytes": body_bytes,
                    "runtime_ms": elapsed_ms,
                    "error": error,
                }
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base_url": api_base_url,
        "web_base_url": web_base_url,
        "registry_version": registry.get("version"),
        "api": api_rows,
        "web": web_rows,
        "summary": {
            "api_total": len(api_rows),
            "api_probe_ok": sum(1 for row in api_rows if bool(row.get("probe_ok"))),
            "api_probe_data_present": sum(1 for row in api_rows if bool(row.get("data_present"))),
            "web_total": len(web_rows),
            "web_probe_ok": sum(1 for row in web_rows if bool(row.get("probe_ok"))),
            "web_probe_data_present": sum(1 for row in web_rows if bool(row.get("data_present"))),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base-url", type=str, default="https://coherence-network-production.up.railway.app")
    parser.add_argument("--web-base-url", type=str, default="https://coherence-network.vercel.app")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run_probe(
        api_base_url=args.api_base_url,
        web_base_url=args.web_base_url,
        timeout_seconds=max(1.0, min(float(args.timeout_seconds), 60.0)),
    )

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json or not args.output:
        print(json.dumps(report, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
