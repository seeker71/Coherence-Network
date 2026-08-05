"""Two properties of federation carrier selection that CI cannot see itself.

The federation tests already prove the common case: on a Linux runner, a
carrier built for another host raises ``Exec format error`` and they go red.
They are the regression test, and nothing here repeats them.

What they cannot reach is the production shape. CI runs as a source
checkout, so it only ever exercises the receipt path; the image path — one
carrier shipped beside its digest authority — is never executed in CI, and
breaking it would leave CI green while production lost its carrier.
"""
from __future__ import annotations

import json
import stat

from app.services import native_federation_graph_service as carrier


def _executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _receipt(root, native_path):
    receipt = root / ".cache" / "form-cli-native" / "selected.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps(
            {
                "schema": "selected-form-cli-carrier-v1",
                "native_path": str(native_path),
                "binary_sha256": "0" * 64,
                "source_sha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )


def test_a_production_image_uses_the_carrier_shipped_beside_its_digest():
    """The path CI never runs: one carrier, its sha256 beside it, no receipt."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shipped = _executable(root / "form" / "form" / "form-cli")
        (root / "form" / "form-cli.sha256").write_text("0" * 64, encoding="utf-8")
        # Even with a receipt present, the image's own carrier is the answer.
        _receipt(root, _executable(root / ".cache" / "form-cli-native" / "x" / "form-cli"))
        assert carrier._host_native_carrier(root) == shipped


def test_a_receipt_may_not_name_a_carrier_outside_the_cache_it_owns():
    """The receipt names a path we then execute, so its reach stays bounded."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _receipt(root, _executable(root / "elsewhere" / "form-cli"))
        assert carrier._host_native_carrier(root) is None
