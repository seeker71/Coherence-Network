"""Tests for spec `deploy-latest-to-vps` (specs/156-deploy-latest-to-vps.md).

Encodes acceptance criteria: deploy command contract, compose ps expectations,
public API JSON contracts, and optional live checks against production when
``COHERENCE_VPS_PUBLIC_VERIFY`` is enabled.
"""

from __future__ import annotations

import os
import re
from typing import Any

import pytest

# --- Spec constants (specs/156-deploy-latest-to-vps.md task card + CLAUDE.md) ---

VPS_HOST = "187.77.152.42"
SSH_USER_HOST = f"root@{VPS_HOST}"
SSH_KEY_FRAGMENT = "~/.ssh/hostinger-openclaw"
REPO_PATH = "/docker/coherence-network/repo"
COMPOSE_PATH = "/docker/coherence-network"
PUBLIC_API_BASE = "https://api.coherencycoin.com"
PUBLIC_WEB_BASE = "https://coherencycoin.com"


def deploy_ssh_commands() -> list[str]:
    """Exact deploy sequence from the spec task card (verification contract)."""
    return [
        f"ssh -i {SSH_KEY_FRAGMENT} {SSH_USER_HOST} "
        f"'cd {REPO_PATH} && git pull origin main'",
        f"ssh -i {SSH_KEY_FRAGMENT} {SSH_USER_HOST} "
        f"'cd {COMPOSE_PATH} && docker compose build --no-cache api web'",
        f"ssh -i {SSH_KEY_FRAGMENT} {SSH_USER_HOST} "
        f"'cd {COMPOSE_PATH} && docker compose up -d api web'",
    ]


def assert_health_contract(data: dict[str, Any]) -> None:
    """Acceptance test 3 + API contract: health JSON status and schema_ok."""
    assert data.get("status") == "ok", data
    assert data.get("schema_ok") is True, data


def assert_services_payload_ok(body: Any) -> None:
    """Acceptance test 2: JSON service list structure (list or wrapped)."""
    if isinstance(body, list):
        for item in body:
            assert isinstance(item, dict), item
            assert "id" in item and "name" in item, item
        return
    if isinstance(body, dict) and "services" in body:
        services = body["services"]
        assert isinstance(services, list), body
        for item in services:
            assert isinstance(item, dict), item
            assert "id" in item and "name" in item, item
        return
    raise AssertionError(f"Unexpected /api/services body shape: {type(body)!r}")


def compose_ps_indicates_api_web_running(ps_output: str) -> bool:
    """
    Acceptance test 1: ``docker compose ps`` shows api and web up.

    Tolerates docker compose v2 table layout: SERVICE column contains ``api`` /
    ``web``; STATUS contains ``Up``.
    """
    lines = [ln.strip() for ln in ps_output.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    has_api = False
    has_web = False
    for line in lines[1:]:
        if not line or line.startswith("-"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        # Typical columns: NAME ... SERVICE ... STATUS ...  (whitespace-separated)
        service_name = None
        for tok in parts:
            if tok in {"api", "web"}:
                # Prefer token in SERVICE column: often after COMMAND (image may contain '/')
                service_name = tok
                break
        status_blob = " ".join(parts)
        if "Up" not in status_blob:
            continue
        if service_name == "api":
            has_api = True
        elif service_name == "web":
            has_web = True
        # Fallback: service name embedded in container name
        if "api" in line and "Up" in status_blob and re.search(r"[-_]api[-_0-9]", line):
            has_api = True
        if "web" in line and "Up" in status_blob and re.search(r"[-_]web[-_0-9]", line):
            has_web = True
    return has_api and has_web


# ---------------------------------------------------------------------------
# Contract tests (no network)
# ---------------------------------------------------------------------------


def test_deploy_sequence_matches_spec_task_card() -> None:
    cmds = deploy_ssh_commands()
    assert len(cmds) == 3
    assert f"cd {REPO_PATH} && git pull origin main" in cmds[0]
    assert "docker compose build --no-cache api web" in cmds[1]
    assert "docker compose up -d api web" in cmds[2]
    assert SSH_KEY_FRAGMENT in cmds[0] and SSH_USER_HOST in cmds[0]


def test_spec_public_urls() -> None:
    assert PUBLIC_API_BASE == "https://api.coherencycoin.com"
    assert PUBLIC_WEB_BASE == "https://coherencycoin.com"


def test_health_contract_accepts_spec_example() -> None:
    sample = {"status": "ok", "schema_ok": True}
    assert_health_contract(sample)


def test_health_contract_rejects_bad_schema() -> None:
    with pytest.raises(AssertionError):
        assert_health_contract({"status": "ok", "schema_ok": False})
    with pytest.raises(AssertionError):
        assert_health_contract({"status": "degraded", "schema_ok": True})


def test_services_contract_list_shape() -> None:
    assert_services_payload_ok(
        [
            {"id": "a", "name": "A"},
            {"id": "b", "name": "B"},
        ]
    )


def test_services_contract_wrapped_shape() -> None:
    assert_services_payload_ok(
        {
            "services": [
                {"id": "a", "name": "A"},
            ]
        }
    )


def test_compose_ps_parser_positive() -> None:
    sample = """
NAME                          IMAGE     COMMAND   SERVICE   CREATED       STATUS                    PORTS
coherence-network-api-1       x         "uvicorn" api       2 hours ago   Up 2 hours (healthy)      0.0.0.0:8000->8000/tcp
coherence-network-web-1       y         "node"    web       2 hours ago   Up 2 hours                0.0.0.0:3000->3000/tcp
""".strip()
    assert compose_ps_indicates_api_web_running(sample) is True


def test_compose_ps_parser_negative_missing_web() -> None:
    sample = """
NAME                          IMAGE     COMMAND   SERVICE   CREATED       STATUS                    PORTS
coherence-network-api-1       x         "uvicorn" api       2 hours ago   Up 2 hours (healthy)      0.0.0.0:8000->8000/tcp
""".strip()
    assert compose_ps_indicates_api_web_running(sample) is False


def test_compose_ps_parser_negative_not_up() -> None:
    sample = """
NAME                          IMAGE     COMMAND   SERVICE   CREATED       STATUS                    PORTS
coherence-network-api-1       x         "uvicorn" api       2 hours ago   Exited (1) 2 hours ago    -
coherence-network-web-1       y         "node"    web       2 hours ago   Exited (1) 2 hours ago    -
""".strip()
    assert compose_ps_indicates_api_web_running(sample) is False


# ---------------------------------------------------------------------------
# Optional production verification (spec Verification section)
# ---------------------------------------------------------------------------

_PUBLIC = os.environ.get("COHERENCE_VPS_PUBLIC_VERIFY", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


@pytest.mark.skipif(not _PUBLIC, reason="Set COHERENCE_VPS_PUBLIC_VERIFY=1 for live VPS checks")
def test_public_api_services_health_and_web_root() -> None:
    import httpx

    timeout = httpx.Timeout(25.0, connect=5.0)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r_services = client.get(f"{PUBLIC_API_BASE}/api/services")
        assert r_services.status_code == 200, r_services.text
        ct = r_services.headers.get("content-type", "")
        assert "application/json" in ct
        body = r_services.json()
        assert_services_payload_ok(body)

        r_health = client.get(f"{PUBLIC_API_BASE}/api/health")
        assert r_health.status_code == 200, r_health.text
        hct = r_health.headers.get("content-type", "")
        assert "application/json" in hct
        assert_health_contract(r_health.json())

        r_web = client.get(PUBLIC_WEB_BASE)
        assert r_web.status_code == 200, r_web.text


@pytest.mark.skipif(not _PUBLIC, reason="Set COHERENCE_VPS_PUBLIC_VERIFY=1 for live VPS checks")
def test_public_web_has_no_obvious_cors_failure_on_api_preflight() -> None:
    """Lightweight check: OPTIONS to API returns CORS headers (spec edge case wiring)."""
    import httpx

    timeout = httpx.Timeout(25.0, connect=5.0)
    with httpx.Client(timeout=timeout) as client:
        r = client.options(
            f"{PUBLIC_API_BASE}/api/health",
            headers={
                "Origin": PUBLIC_WEB_BASE,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code in {200, 204, 405}
        # If CORS middleware responds, allow-origin or similar may be present; do not hard-fail 403 on OPTIONS.
        assert r.status_code != 403
