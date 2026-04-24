from __future__ import annotations

from pathlib import Path

from app.services import smart_reap_service, smart_reaper_service


def test_legacy_smart_reap_module_reexports_canonical_service() -> None:
    assert smart_reap_service.aggregate_reap_history is smart_reaper_service.aggregate_reap_history
    assert smart_reap_service.smart_reap_task is smart_reaper_service.smart_reap_task


def test_legacy_smart_reap_module_is_a_thin_shim() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    shim = repo_root / "api" / "app" / "services" / "smart_reap_service.py"
    canonical = repo_root / "api" / "app" / "services" / "smart_reaper_service.py"

    assert shim.stat().st_size < canonical.stat().st_size
    assert "smart_reaper_service import *" in shim.read_text(encoding="utf-8")
