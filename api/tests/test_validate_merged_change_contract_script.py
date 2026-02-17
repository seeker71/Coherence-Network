from __future__ import annotations

from scripts.validate_merged_change_contract import _default_endpoints


def test_default_endpoints_exclude_web_root() -> None:
    endpoints = _default_endpoints(
        "https://coherence-network-production.up.railway.app",
        "https://coherence-web-production.up.railway.app",
    )
    assert "https://coherence-web-production.up.railway.app/" not in endpoints
    assert "https://coherence-web-production.up.railway.app/gates" in endpoints
    assert "https://coherence-web-production.up.railway.app/api-health" in endpoints
