from __future__ import annotations

import json
import sys
from pathlib import Path


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts"


def test_extract_spec_metadata_parses_idea_and_cost(tmp_path: Path) -> None:
    sys.path.insert(0, str(_scripts_dir()))
    try:
        from extract_spec_metadata import extract_estimated_cost, extract_idea_id_from_content, extract_spec_id
    finally:
        sys.path.pop(0)

    spec_path = tmp_path / "072-sample.md"
    spec_path.write_text(
        "# Spec 072\n\n**Idea**: `traceability-maturity-governance`\n\nEstimated cost: 3.5 hours\n",
        encoding="utf-8",
    )

    assert extract_spec_id(str(spec_path)) == "072-sample"
    assert extract_idea_id_from_content(str(spec_path)) == "traceability-maturity-governance"
    assert extract_estimated_cost(str(spec_path)) == 3.5


def test_auto_create_lineage_dry_run_reports_needs_idea(tmp_path: Path) -> None:
    sys.path.insert(0, str(_scripts_dir()))
    try:
        from auto_create_lineage import extract_spec_metadata
    finally:
        sys.path.pop(0)

    spec_path = tmp_path / "073-no-idea.md"
    spec_path.write_text("# Spec 073\n\nNo idea annotation yet.\n", encoding="utf-8")

    metadata = extract_spec_metadata(str(spec_path))
    assert metadata["spec_id"] == "073-no-idea"
    assert metadata["idea_id"] is None
    assert metadata["estimated_cost"] is None


def test_check_existing_lineage_detects_known_spec(tmp_path: Path, monkeypatch) -> None:
    sys.path.insert(0, str(_scripts_dir()))
    try:
        from auto_create_lineage import check_existing_lineage
    finally:
        sys.path.pop(0)

    monkeypatch.chdir(tmp_path)
    lineage_dir = tmp_path / "api" / "logs"
    lineage_dir.mkdir(parents=True)
    payload = {"links": [{"spec_id": "074-known"}, {"spec_id": "075-other"}]}
    (lineage_dir / "value_lineage.json").write_text(json.dumps(payload), encoding="utf-8")

    assert check_existing_lineage("074-known") is True
    assert check_existing_lineage("076-missing") is False
