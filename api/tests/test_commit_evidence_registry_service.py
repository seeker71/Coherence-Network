from __future__ import annotations

import json
from pathlib import Path

from app.services import commit_evidence_registry_service


def test_commit_evidence_registry_import_and_tracked_ideas(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "commit_evidence.db"
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    (evidence_dir / "commit_evidence_2026-02-17_a.json").write_text(
        json.dumps(
            {
                "date": "2026-02-17",
                "commit_scope": "alpha",
                "idea_ids": ["idea-a", "idea-b"],
            }
        ),
        encoding="utf-8",
    )
    (evidence_dir / "commit_evidence_2026-02-17_b.json").write_text(
        json.dumps(
            {
                "date": "2026-02-17",
                "commit_scope": "beta",
                "idea_ids": ["idea-b", "idea-c"],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("COMMIT_EVIDENCE_DATABASE_URL", f"sqlite+pysqlite:///{db_path}")

    report = commit_evidence_registry_service.import_from_dir(evidence_dir, limit=100)
    records = commit_evidence_registry_service.list_records(limit=100)
    tracked = commit_evidence_registry_service.tracked_idea_ids(limit=100)

    assert report["imported"] >= 2
    assert len(records) >= 2
    assert tracked == ["idea-a", "idea-b", "idea-c"]
