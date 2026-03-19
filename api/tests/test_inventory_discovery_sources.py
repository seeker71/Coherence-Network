from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services import (
    commit_evidence_service,
    idea_service,
    inventory_service,
    runtime_service,
    spec_registry_service,
    value_lineage_service,
)


def test_idea_service_derives_missing_ideas_from_commit_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))
    commit_evidence_service.upsert_record(
        {"idea_ids": ["derived-runtime-observability"], "thread_branch": "codex/test"},
        "memory:test",
    )

    listed = idea_service.list_ideas()
    idea_ids = [item.id for item in listed.ideas]

    assert "derived-runtime-observability" in idea_ids
    assert portfolio_path.exists()
    assert "derived-runtime-observability" in idea_service.list_tracked_idea_ids()


def test_idea_service_includes_store_tracked_ids_when_db_is_configured(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    commit_evidence_service.upsert_record(
        {"idea_ids": ["unexpected-local"], "thread_branch": "codex/test"},
        "memory:test",
    )
    monkeypatch.delenv("IDEA_COMMIT_EVIDENCE_DIR", raising=False)

    assert idea_service.list_tracked_idea_ids() == ["unexpected-local"]


def test_idea_service_includes_store_tracked_ids_when_database_url_is_configured(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    commit_evidence_service.upsert_record(
        {"idea_ids": ["database-url-tracked"], "thread_branch": "codex/test"},
        "memory:test",
    )
    monkeypatch.delenv("IDEA_COMMIT_EVIDENCE_DIR", raising=False)

    assert idea_service.list_tracked_idea_ids() == ["database-url-tracked"]


def test_idea_service_reads_tracked_ids_from_commit_evidence_store(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    commit_evidence_service.upsert_record({"idea_ids": ["tracked-main"]}, "memory:first")
    commit_evidence_service.upsert_record({"idea_ids": ["tracked-alt"]}, "memory:second")
    monkeypatch.setenv("IDEA_COMMIT_EVIDENCE_DIR", str(tmp_path / "system_audit"))
    tracked = idea_service.list_tracked_idea_ids()
    assert tracked == ["tracked-alt", "tracked-main"]


def test_idea_service_derives_missing_ideas_from_other_registry_domains(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("IDEA_SYNC_ENABLE_DOMAIN_DISCOVERY", "1")
    monkeypatch.delenv("IDEA_COMMIT_EVIDENCE_DIR", raising=False)

    monkeypatch.setattr(
        spec_registry_service,
        "list_specs",
        lambda limit=200, offset=0: [SimpleNamespace(idea_id="derived-from-spec-registry")],
    )
    monkeypatch.setattr(
        value_lineage_service,
        "list_links",
        lambda limit=200: [SimpleNamespace(idea_id="derived-from-lineage")],
    )
    monkeypatch.setattr(
        runtime_service,
        "summarize_by_idea",
        lambda seconds=3600, event_limit=2000, summary_limit=500, summary_offset=0, event_rows=None: [
            SimpleNamespace(idea_id="derived-from-runtime")
        ],
    )

    listed = idea_service.list_ideas(include_internal=True)
    idea_ids = {item.id for item in listed.ideas}

    assert "derived-from-spec-registry" in idea_ids
    assert "derived-from-lineage" in idea_ids
    assert "derived-from-runtime" in idea_ids


def test_idea_service_domain_discovery_default_on_outside_pytest(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.delenv("IDEA_SYNC_ENABLE_DOMAIN_DISCOVERY", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("IDEA_COMMIT_EVIDENCE_DIR", raising=False)

    monkeypatch.setattr(
        spec_registry_service,
        "list_specs",
        lambda limit=200, offset=0: [SimpleNamespace(idea_id="derived-prod-default")],
    )
    monkeypatch.setattr(
        value_lineage_service,
        "list_links",
        lambda limit=200: [],
    )
    monkeypatch.setattr(
        runtime_service,
        "summarize_by_idea",
        lambda seconds=3600, event_limit=2000, summary_limit=500, summary_offset=0, event_rows=None: [],
    )

    listed = idea_service.list_ideas(include_internal=True)
    idea_ids = {item.id for item in listed.ideas}

    assert "derived-prod-default" in idea_ids


def test_idea_service_derives_missing_ideas_from_contribution_metadata_domain(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("IDEA_SYNC_ENABLE_DOMAIN_DISCOVERY", "1")
    monkeypatch.delenv("IDEA_COMMIT_EVIDENCE_DIR", raising=False)

    monkeypatch.setattr(spec_registry_service, "list_specs", lambda limit=200, offset=0: [])
    monkeypatch.setattr(value_lineage_service, "list_links", lambda limit=200: [])
    monkeypatch.setattr(
        runtime_service,
        "summarize_by_idea",
        lambda seconds=3600, event_limit=2000, summary_limit=500, summary_offset=0, event_rows=None: [],
    )
    monkeypatch.setattr(
        idea_service,
        "_contribution_metadata_idea_ids",
        lambda: ["derived-from-contribution-meta"],
    )

    listed = idea_service.list_ideas(include_internal=True)
    idea_ids = {item.id for item in listed.ideas}

    assert "derived-from-contribution-meta" in idea_ids


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


def test_inventory_does_not_emit_fake_spec_rows_when_all_sources_missing(
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
        lambda limit=300, timeout=8.0: [],
    )
    monkeypatch.setattr(idea_service, "list_tracked_idea_ids", lambda: ["portfolio-governance"])

    inventory = inventory_service.build_system_lineage_inventory(runtime_window_seconds=60)

    assert inventory["specs"]["count"] == 0
    assert inventory["specs"]["source"] == "none"
    assert inventory["specs"]["items"] == []


def test_inventory_reads_commit_evidence_from_store(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    commit_evidence_service.upsert_record(
        {
            "idea_ids": ["portfolio-governance"],
            "spec_ids": ["089"],
            "change_files": ["api/app/routers/inventory.py"],
        },
        "memory:remote",
    )

    records = inventory_service._read_commit_evidence_records(limit=20)

    assert len(records) == 1
    assert records[0]["idea_ids"] == ["portfolio-governance"]
    assert records[0]["spec_ids"] == ["089"]
    assert str(records[0]["_evidence_file"]) == "memory:remote"


def test_inventory_reads_commit_evidence_from_store_when_database_url_configured(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    commit_evidence_service.upsert_record(
        {
            "idea_ids": ["database-url-evidence"],
            "spec_ids": ["091"],
        },
        "memory:database-url",
    )

    records = inventory_service._read_commit_evidence_records(limit=20)

    assert len(records) == 1
    assert records[0]["idea_ids"] == ["database-url-evidence"]
    assert records[0]["spec_ids"] == ["091"]
    assert str(records[0]["_evidence_file"]) == "memory:database-url"


def test_inventory_commit_evidence_returns_empty_when_store_and_files_empty(
    monkeypatch, tmp_path: Path
) -> None:
    """With unified DB, empty DB + no local files → empty results."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    # Point evidence dir to an empty directory so file fallback also returns nothing
    monkeypatch.setattr(inventory_service, "_commit_evidence_dir", lambda: tmp_path / "empty_evidence")
    monkeypatch.setattr(inventory_service, "_read_commit_evidence_records_from_github", lambda limit=400: [])

    records = inventory_service._read_commit_evidence_records(limit=1000)

    assert records == []


def test_inventory_commit_evidence_bootstraps_from_files_when_db_empty(
    monkeypatch, tmp_path: Path
) -> None:
    """With unified DB, empty DB + local files → bootstraps from files."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "commit_evidence_2026-03-03_fake.json").write_text(
        '{"idea_ids": ["bootstrap-from-file"], "spec_ids": ["999"]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(inventory_service, "_commit_evidence_dir", lambda: evidence_dir)

    records = inventory_service._read_commit_evidence_records(limit=1000)

    assert len(records) == 1
    assert records[0]["idea_ids"] == ["bootstrap-from-file"]


def test_source_aliases_normalize_deployed_double_app_prefix() -> None:
    aliases = inventory_service._source_path_aliases("/app/app/routers/inventory.py")

    assert "app/routers/inventory.py" in aliases
    assert "api/app/routers/inventory.py" in aliases


def test_route_evidence_probe_uses_github_when_local_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inventory_service, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(inventory_service, "_tracking_repository", lambda: "seeker71/Coherence-Network")
    monkeypatch.setattr(inventory_service, "_tracking_ref", lambda: "main")
    inventory_service._ROUTE_PROBE_DISCOVERY_CACHE["expires_at"] = 0.0
    inventory_service._ROUTE_PROBE_DISCOVERY_CACHE["item"] = None

    class FakeResponse:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError("http error")

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            if url.endswith("/contents/docs/system_audit"):
                return FakeResponse(
                    200,
                    [
                        {
                            "name": "route_evidence_probe_2026-02-16_public.json",
                            "path": "docs/system_audit/route_evidence_probe_2026-02-16_public.json",
                            "download_url": "https://example.test/route_probe.json",
                        }
                    ],
                )
            if url == "https://example.test/route_probe.json":
                return FakeResponse(
                    200,
                    {
                        "generated_at": "2026-02-16T00:00:00+00:00",
                        "api": [
                            {"path_template": "/api/inventory/system-lineage", "method": "GET", "status_code": 200}
                        ],
                        "web": [{"path_template": "/flow", "status_code": 200}],
                    },
                )
            return FakeResponse(404, {"detail": "not found"})

    monkeypatch.setattr(inventory_service.httpx, "Client", FakeClient)

    payload = inventory_service._read_latest_route_evidence_probe()

    assert isinstance(payload, dict)
    assert payload["api"][0]["path_template"] == "/api/inventory/system-lineage"
    assert str(payload["_probe_file"]).endswith("route_evidence_probe_2026-02-16_public.json")


def test_route_evidence_probe_uses_github_raw_latest_when_available(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inventory_service, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(inventory_service, "_tracking_repository", lambda: "seeker71/Coherence-Network")
    monkeypatch.setattr(inventory_service, "_tracking_ref", lambda: "main")
    inventory_service._ROUTE_PROBE_DISCOVERY_CACHE["expires_at"] = 0.0
    inventory_service._ROUTE_PROBE_DISCOVERY_CACHE["item"] = None

    class FakeResponse:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError("http error")

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            if "raw.githubusercontent.com" in url:
                return FakeResponse(
                    200,
                    {
                        "generated_at": "2026-02-16T00:00:00+00:00",
                        "api": [
                            {"path_template": "/api/inventory/system-lineage", "method": "GET", "status_code": 200}
                        ],
                        "web": [{"path_template": "/flow", "status_code": 200}],
                    },
                )
            return FakeResponse(404, {"detail": "not found"})

    monkeypatch.setattr(inventory_service.httpx, "Client", FakeClient)

    payload = inventory_service._read_latest_route_evidence_probe()

    assert isinstance(payload, dict)
    assert payload["api"][0]["path_template"] == "/api/inventory/system-lineage"
    assert payload["_probe_file"] == "docs/system_audit/route_evidence_probe_latest.json"
