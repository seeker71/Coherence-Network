from __future__ import annotations

import json
from pathlib import Path

from app.services import idea_service, inventory_service


def test_idea_service_derives_missing_ideas_from_commit_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "commit_evidence_2026-02-16_test.json").write_text(
        json.dumps({"idea_ids": ["derived-runtime-observability"]}),
        encoding="utf-8",
    )

    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))
    monkeypatch.setenv("IDEA_COMMIT_EVIDENCE_DIR", str(evidence_dir))

    listed = idea_service.list_ideas()
    idea_ids = [item.id for item in listed.ideas]

    assert "derived-runtime-observability" in idea_ids
    assert portfolio_path.exists()
    assert "derived-runtime-observability" in idea_service.list_tracked_idea_ids()


def test_inventory_uses_github_spec_discovery_when_local_specs_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    monkeypatch.setattr(inventory_service, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        inventory_service,
        "_discover_specs_from_github",
        lambda limit=300, timeout=8.0: [
            {
                "spec_id": "900",
                "title": "remote inventory source",
                "path": "specs/900-remote-inventory-source.md",
            }
        ],
    )
    monkeypatch.setattr(idea_service, "list_tracked_idea_ids", lambda: ["portfolio-governance"])

    inventory = inventory_service.build_system_lineage_inventory(runtime_window_seconds=60)

    assert inventory["specs"]["count"] == 1
    assert inventory["specs"]["source"] == "github"
    assert inventory["specs"]["items"][0]["spec_id"] == "900"
