from __future__ import annotations

import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import audit_vision_image_candidates as audit_candidates  # noqa: E402


def _write_png(path: Path, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"padding" * 20
    )


def test_audit_records_reports_present_candidate(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidates"
    rel_path = "web/public/visuals/generated/lc-space-0.jpg"
    candidate = candidate_dir / rel_path
    _write_png(candidate, 512, 384)

    report = audit_candidates.audit_records(
        [{"id": "lc-space-0", "path": rel_path, "prompt": "living space"}],
        candidate_dir,
        profile_id="fast-sample-v1",
        min_bytes=64,
    )

    assert report["summary"] == {
        "total": 1,
        "present": 1,
        "missing": 0,
        "too_small": 0,
        "unreadable_dimensions": 0,
        "pass": True,
    }
    item = report["items"][0]
    assert item["width"] == 512
    assert item["height"] == 384
    assert item["profile"] == "fast-sample-v1"
    assert item["passes_min_bytes"] is True
    assert item["passes_dimensions"] is True


def test_audit_records_reports_missing_candidate(tmp_path: Path) -> None:
    report = audit_candidates.audit_records(
        [{"id": "lc-space-0", "path": "web/public/visuals/generated/lc-space-0.jpg", "prompt": "living space"}],
        tmp_path / "candidates",
        profile_id="fast-sample-v1",
        min_bytes=64,
    )

    assert report["summary"]["present"] == 0
    assert report["summary"]["missing"] == 1
    assert report["summary"]["pass"] is False
    assert report["items"][0]["exists"] is False


def test_select_records_matches_mirror_path() -> None:
    records = [
        {
            "id": "life-morning-circle",
            "path": "docs/visuals/life-morning-circle.png",
            "mirror_paths": ["web/public/visuals/life-morning-circle.png"],
        }
    ]

    selected = audit_candidates._select_records(
        records,
        "web/public/visuals/life-morning-circle.png",
    )

    assert selected == records
