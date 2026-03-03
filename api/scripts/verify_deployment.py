#!/usr/bin/env python3
"""Verify deployed API availability and contribution tracking flow.

Usage:
  python scripts/verify_deployment.py --base-url http://127.0.0.1:8000
  python scripts/verify_deployment.py --base-url https://api.example.com --skip-write-check
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _request_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        status = resp.status
        data = json.loads(resp.read().decode("utf-8"))
        return status, data


def _check_get(base_url: str, path: str, expected_code: int = 200, optional: bool = False) -> CheckResult:
    url = f"{base_url}{path}"
    try:
        status, data = _request_json("GET", url)
        if status != expected_code:
            return CheckResult(f"GET {path}", False, f"expected {expected_code}, got {status}")
        return CheckResult(f"GET {path}", True, f"status={status}, keys={sorted(data.keys())}")
    except urllib.error.HTTPError as exc:
        if optional and exc.code == 404:
            return CheckResult(f"GET {path}", True, "optional endpoint not present (404)")
        return CheckResult(f"GET {path}", False, f"HTTP error: {exc}")
    except urllib.error.URLError as exc:
        return CheckResult(f"GET {path}", False, f"connection failed: {exc}")


def _check_contribution_flow(base_url: str) -> CheckResult:
    try:
        _, contributor = _request_json(
            "POST",
            f"{base_url}/v1/contributors",
            {
                "type": "HUMAN",
                "name": "Deployment Verifier",
                "email": "deploy-verifier@example.com",
                "wallet_address": "0xverify",
                "hourly_rate": "120",
            },
        )
        _, asset = _request_json(
            "POST",
            f"{base_url}/v1/assets",
            {"type": "CODE", "description": "Deployment verification asset"},
        )
        _, contribution = _request_json(
            "POST",
            f"{base_url}/v1/contributions",
            {
                "contributor_id": contributor["id"],
                "asset_id": asset["id"],
                "cost_amount": "25.5",
                "metadata": {"has_tests": True, "has_docs": True, "complexity": "low"},
            },
        )
        _, asset_after = _request_json("GET", f"{base_url}/v1/assets/{asset['id']}")

        cost_ok = str(asset_after.get("total_cost")) in {"25.5", "25.50"}
        if not cost_ok:
            return CheckResult(
                "POST /v1/* contribution flow",
                False,
                f"asset total_cost mismatch: {asset_after.get('total_cost')}",
            )

        return CheckResult(
            "POST /v1/* contribution flow",
            True,
            f"contribution_id={contribution['id']} coherence_score={contribution['coherence_score']}",
        )
    except (KeyError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        return CheckResult("POST /v1/* contribution flow", False, f"failed: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deployed Coherence API and write-path")
    parser.add_argument("--base-url", required=True, help="API base URL, e.g. https://api.example.com")
    parser.add_argument(
        "--skip-write-check",
        action="store_true",
        help="Skip POST-based contribution tracking verification",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    checks = [
        _check_get(base_url, "/api/health"),
        _check_get(base_url, "/api/ready"),
        _check_get(base_url, "/api/version", optional=True),
    ]
    if not args.skip_write_check:
        checks.append(_check_contribution_flow(base_url))

    any_failed = False
    print("\nDeployment verification results")
    print("=" * 32)
    for c in checks:
        icon = "✅" if c.ok else "❌"
        print(f"{icon} {c.name}: {c.detail}")
        if not c.ok:
            any_failed = True

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
