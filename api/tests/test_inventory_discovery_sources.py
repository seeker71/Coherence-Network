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


def test_inventory_uses_github_commit_evidence_when_local_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inventory_service, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(inventory_service, "_tracking_repository", lambda: "seeker71/Coherence-Network")
    monkeypatch.setattr(inventory_service, "_tracking_ref", lambda: "main")
    inventory_service._EVIDENCE_DISCOVERY_CACHE["expires_at"] = 0.0
    inventory_service._EVIDENCE_DISCOVERY_CACHE["items"] = []

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
                            "name": "commit_evidence_remote.json",
                            "path": "docs/system_audit/commit_evidence_remote.json",
                            "download_url": "https://example.test/commit_evidence_remote.json",
                        }
                    ],
                )
            if url == "https://example.test/commit_evidence_remote.json":
                return FakeResponse(
                    200,
                    {
                        "idea_ids": ["portfolio-governance"],
                        "spec_ids": ["089"],
                        "change_files": ["api/app/routers/inventory.py"],
                    },
                )
            return FakeResponse(404, {"detail": "not found"})

    monkeypatch.setattr(inventory_service.httpx, "Client", FakeClient)

    records = inventory_service._read_commit_evidence_records(limit=20)

    assert len(records) == 1
    assert records[0]["idea_ids"] == ["portfolio-governance"]
    assert records[0]["spec_ids"] == ["089"]
    assert str(records[0]["_evidence_file"]).endswith("commit_evidence_remote.json")


def test_inventory_limits_remote_commit_evidence_fetch_without_token(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inventory_service, "_project_root", lambda: tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "")
    inventory_service._EVIDENCE_DISCOVERY_CACHE["expires_at"] = 0.0
    inventory_service._EVIDENCE_DISCOVERY_CACHE["items"] = []

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
            self.download_calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            if url.endswith("/contents/docs/system_audit"):
                rows = [
                    {
                        "name": f"commit_evidence_{i:03d}.json",
                        "path": f"docs/system_audit/commit_evidence_{i:03d}.json",
                        "download_url": f"https://example.test/evidence/{i:03d}.json",
                    }
                    for i in range(60)
                ]
                return FakeResponse(200, rows)
            if url.startswith("https://example.test/evidence/"):
                self.download_calls += 1
                return FakeResponse(
                    200,
                    {
                        "idea_ids": ["portfolio-governance"],
                        "spec_ids": ["089"],
                        "change_files": ["api/app/routers/inventory.py"],
                    },
                )
            return FakeResponse(404, {"detail": "not found"})

    fake_client = FakeClient()
    monkeypatch.setattr(inventory_service.httpx, "Client", lambda *args, **kwargs: fake_client)

    records = inventory_service._read_commit_evidence_records(limit=1000)

    assert len(records) == 20
    assert fake_client.download_calls == 20


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
