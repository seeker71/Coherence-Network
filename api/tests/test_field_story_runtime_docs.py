from __future__ import annotations

import json

from app.services import field_story_service


def test_field_story_service_uses_container_field_doc_fallback(tmp_path, monkeypatch):
    field_root = tmp_path / "docs" / "field"
    story_dir = field_root / "probe"
    story_dir.mkdir(parents=True)
    (story_dir / "manifest.json").write_text(
        json.dumps(
            {
                "slug": "runtime-field-doc-probe",
                "title": "Runtime Field Doc Probe",
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(field_story_service, "FIELD_ROOT_CANDIDATES", (tmp_path / "missing", field_root))

    stories = field_story_service.list_field_stories()

    assert stories == [
        {
            "slug": "runtime-field-doc-probe",
            "title": "Runtime Field Doc Probe",
            "contributor_id": None,
            "status": "published",
            "summary": "",
            "artifact_count": 0,
            "web": None,
            "read_api": None,
        }
    ]
