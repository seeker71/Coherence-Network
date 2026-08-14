"""Selection witnesses for the direct fkwu federation admission carrier."""
from __future__ import annotations

import stat

from app.services import form_kernel_bridge
from app.services import native_federation_graph_service as carrier


def _executable(path):
    path.write_bytes(b"#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_federation_selects_the_direct_fkwu_carrier(tmp_path, monkeypatch):
    native = _executable(tmp_path / "fkwu")
    monkeypatch.setattr(form_kernel_bridge, "kernel_bin_path", lambda: native)
    assert carrier._binary() == native


def test_federation_admission_recipe_is_static_and_present():
    assert carrier._RECIPE.is_file()
    source = carrier._RECIPE.read_text(encoding="utf-8")
    assert "pfgc-admit" in source
    assert "1111" not in source
