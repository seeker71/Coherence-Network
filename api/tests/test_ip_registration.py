"""Flow tests for ip_registration_service — story-protocol-integration R1, R7.

Exercises the three named functions the spec's `source:` block claims:
register_ip_asset, get_ip_status, record_derivative. The service holds
state in module-level dicts in this iteration; each test starts fresh
via the autouse reset fixture.
"""

from __future__ import annotations

import pytest

from app.services import ip_registration_service


@pytest.fixture(autouse=True)
def _reset():
    ip_registration_service._reset_for_tests()
    yield
    ip_registration_service._reset_for_tests()


def test_register_ip_asset_returns_sp_ip_id():
    result = ip_registration_service.register_ip_asset(
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890", {"type": "BLUEPRINT"}
    )
    assert result["ip_status"] == "registered"
    assert result["sp_ip_id"] == "sp:mock:a1b2c3d4"
    assert result["registered_at"] is not None
    assert result["asset_id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_register_ip_asset_failure_with_malformed_metadata():
    result = ip_registration_service.register_ip_asset(
        "asset-xyz", "not-a-dict"  # type: ignore[arg-type]
    )
    assert result["ip_status"] == "failed"
    assert result["sp_ip_id"] is None
    assert "dict" in result["reason"]


def test_register_ip_asset_failure_via_force_sentinel():
    result = ip_registration_service.register_ip_asset(
        "asset-zzz", {"_force_failure": True, "_force_failure_reason": "SDK timeout"}
    )
    assert result["ip_status"] == "failed"
    assert result["reason"] == "SDK timeout"


def test_get_ip_status_unregistered():
    status = ip_registration_service.get_ip_status("never-seen")
    assert status == {"asset_id": "never-seen", "ip_status": "not_registered"}


def test_get_ip_status_after_registration():
    ip_registration_service.register_ip_asset("asset-001", {"type": "ARTICLE"})
    status = ip_registration_service.get_ip_status("asset-001")
    assert status["ip_status"] == "registered"
    assert status["sp_ip_id"] == "sp:mock:asset-00"


def test_record_derivative_default_royalty_split():
    result = ip_registration_service.record_derivative(
        "parent-asset", "child-asset", "improvement"
    )
    assert result["royalty_split"] == {"parent": 0.15, "derivative": 0.85}
    assert result["derivative_type"] == "improvement"
    assert result["parent_asset_id"] == "parent-asset"
    assert result["derivative_asset_id"] == "child-asset"


def test_record_derivative_custom_royalty_split():
    result = ip_registration_service.record_derivative(
        "parent-asset",
        "child-asset",
        "translation",
        royalty_split={"parent": 0.30, "derivative": 0.70},
    )
    assert result["royalty_split"] == {"parent": 0.30, "derivative": 0.70}


def test_record_derivative_rejects_self_parent():
    with pytest.raises(ValueError, match="own parent"):
        ip_registration_service.record_derivative("same", "same", "remix")


def test_record_derivative_rejects_unbalanced_split():
    with pytest.raises(ValueError, match="sum to 1.0"):
        ip_registration_service.record_derivative(
            "p", "d", "extension", royalty_split={"parent": 0.5, "derivative": 0.4}
        )


def test_register_is_idempotent():
    first = ip_registration_service.register_ip_asset("asset-idem", {"v": 1})
    second = ip_registration_service.register_ip_asset("asset-idem", {"v": 2})
    assert first["sp_ip_id"] == second["sp_ip_id"]
    assert first["registered_at"] == second["registered_at"]
    # Re-registration returns the existing record; second metadata is ignored.
    assert second["metadata"] == {"v": 1}


def test_register_rejects_empty_asset_id():
    with pytest.raises(ValueError, match="asset_id"):
        ip_registration_service.register_ip_asset("", {})
