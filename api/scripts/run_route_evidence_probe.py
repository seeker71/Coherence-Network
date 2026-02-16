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


def _request(client: httpx.Client, method: str, url: str, timeout_seconds: float) -> tuple[int | None, float, str | None]:
    started = time.perf_counter()
    try:
        response = client.request(method, url, timeout=timeout_seconds, follow_redirects=True)
        elapsed = round((time.perf_counter() - started) * 1000.0, 3)
        return int(response.status_code), elapsed, None
    except Exception as exc:  # noqa: BLE001
        elapsed = round((time.perf_counter() - started) * 1000.0, 3)
        return None, elapsed, str(exc)


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
                status_code, elapsed_ms, error = _request(client, probe_method, url, timeout_seconds)
                api_rows.append(
                    {
                        "path_template": path_template,
                        "path": path,
                        "method": method,
                        "probe_method": probe_method,
                        "url": url,
                        "status_code": status_code,
                        "probe_ok": (status_code is not None and int(status_code) < 500),
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
            status_code, elapsed_ms, error = _request(client, "GET", url, timeout_seconds)
            web_rows.append(
                {
                    "path_template": path_template,
                    "path": path,
                    "url": url,
                    "status_code": status_code,
                    "probe_ok": (status_code is not None and int(status_code) < 500),
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
            "web_total": len(web_rows),
            "web_probe_ok": sum(1 for row in web_rows if bool(row.get("probe_ok"))),
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
