"""Application runtime mode helpers backed by config, not environment."""

from __future__ import annotations

from app.config_loader import get_bool, get_str


def test_context_id() -> str:
    return str(get_str("api", "test_context_id", "") or "").strip()


def running_under_test() -> bool:
    return bool(get_bool("api", "testing", False) or test_context_id())


def debug_audit_enabled() -> bool:
    return get_bool("audit_ledger", "debug", False)
