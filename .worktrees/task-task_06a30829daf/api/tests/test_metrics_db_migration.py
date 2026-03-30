from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.services import metrics_service


def test_metrics_imports_from_file_to_db_and_purges_legacy_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    metrics_file = tmp_path / "metrics.jsonl"
    metrics_file.write_text(
        json.dumps(
            {
                "task_id": "task-migrate-1",
                "task_type": "impl",
                "model": "openai-codex",
                "duration_seconds": 12.5,
                "status": "completed",
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("METRICS_USE_DB", "1")
    monkeypatch.setenv("METRICS_FILE_PATH", str(metrics_file))
    monkeypatch.setenv("METRICS_PURGE_IMPORTED_FILE", "1")
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'telemetry.db'}")

    aggregates = metrics_service.get_aggregates()

    assert aggregates["success_rate"]["total"] == 1
    assert aggregates["success_rate"]["completed"] == 1
    assert not metrics_file.exists()
