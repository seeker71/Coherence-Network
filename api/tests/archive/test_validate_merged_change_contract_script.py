from __future__ import annotations

from scripts.validate_merged_change_contract import _default_endpoints


def test_default_endpoints_exclude_web_root() -> None:
    endpoints = _default_endpoints(
        "https://api.coherencycoin.com",
        "https://coherencycoin.com",
    )
    assert "https://coherencycoin.com/" not in endpoints
    assert "https://coherencycoin.com/gates" in endpoints
    assert "https://coherencycoin.com/api-health" in endpoints
