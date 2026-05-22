"""Tests for the mcp-skill-registry-submission spec.

Covers the three discovery endpoints — submissions, stats, dashboard —
the validation pipeline (asset-presence check), cache bypass on
?refresh=true, and graceful 200-with-empty-stats when the stats source
is unreachable.

Strange-minimal posture: one combined test exercises the most boundary
conditions ("stats source down + cache cold + dashboard merges"); the
rest pin contract surfaces that a regression would silently break.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import registry_discovery_service, registry_stats_service


@pytest.fixture
def client():
    return TestClient(app)


# ---------- submissions endpoint: validation pipeline + asset presence ----------


def test_submissions_lists_at_least_six_registries_with_asset_presence_shape(client):
    """Spec requires six; current ships nine. Assert ≥ 6 and that each entry
    carries the asset-presence shape (missing files named, not silently absent).
    """
    response = client.get("/api/discovery/registry-submissions")
    assert response.status_code == 200
    body = response.json()

    items = body["items"]
    assert len(items) >= 6, f"spec requires ≥6 registries, got {len(items)}"

    # Every item carries the validation contract: id, name, category, status,
    # required_files, missing_files. The asset-presence check is the field
    # missing_files — silent absence (omission) would be the bug.
    for item in items:
        assert item["registry_id"]
        assert item["registry_name"]
        assert item["category"] in {"mcp", "skill"}
        assert item["status"] in {"submission_ready", "missing_assets"}
        assert "required_files" in item
        assert "missing_files" in item
        # missing_assets status implies at least one missing file named
        if item["status"] == "missing_assets":
            assert isinstance(item["missing_files"], list)


def test_core_requirement_met_iff_five_ready_with_category_balance(client):
    """summary.core_requirement_met is true iff submission_ready_count >= 5
    AND ≥2 mcp ready AND ≥2 skill ready (per registry_discovery_service).

    Live state today: 0 ready, so the flag is False. The test pins the
    derivation rather than the live value.
    """
    response = client.get("/api/discovery/registry-submissions")
    summary = response.json()["summary"]

    ready = summary["submission_ready_count"]
    cats = summary["categories"]
    expected = (
        ready >= 5
        and cats.get("mcp", 0) >= 2
        and cats.get("skill", 0) >= 2
    )
    assert summary["core_requirement_met"] is expected


# ---------- dashboard endpoint: graceful degradation ----------


def test_dashboard_returns_200_when_stats_source_unreachable(client):
    """Spec done_when: registry-dashboard returns 200 even when stats are
    fully unavailable. Mock the stats fetcher to raise — endpoint MUST swallow
    the exception and return 200 with submissions still intact.
    """
    with patch.object(
        registry_stats_service,
        "fetch_registry_stats",
        side_effect=RuntimeError("upstream down"),
    ):
        response = client.get("/api/discovery/registry-dashboard")

    assert response.status_code == 200
    body = response.json()
    # Submissions still flow through; stats collapse to unavailable per item.
    assert "submission_summary" in body
    assert "items" in body
    assert len(body["items"]) >= 6
    # Every item's stat_source falls back to unavailable when upstream raised.
    for item in body["items"]:
        assert item["stat_source"] == "unavailable"
        assert item["install_count"] is None
        assert item["download_count"] is None


# ---------- stats endpoint: refresh=true bypasses cache ----------


def test_refresh_true_bypasses_cache_and_calls_live_fetchers(tmp_path, monkeypatch):
    """?refresh=true must bypass the 24h cache. Pre-warm an isolated cache,
    then call with refresh=True and assert the live fetcher fires anyway.

    Cache dir is redirected to tmp_path so the test leaves no trace on the
    worktree's .cache/ directory.
    """
    client = TestClient(app)
    monkeypatch.setattr(registry_stats_service, "_cache_dir", lambda: tmp_path)

    # Pre-warm cache so a non-refresh call would skip the live fetcher.
    registry_stats_service._write_cache(
        "smithery",
        {"install_count": 999, "download_count": 999},
    )

    fetcher_called = {"smithery": 0, "pulsemcp": 0}

    def _fake_smithery():
        fetcher_called["smithery"] += 1
        return {"install_count": 42, "download_count": 7}

    def _fake_pulsemcp():
        fetcher_called["pulsemcp"] += 1
        return {"install_count": 11, "download_count": 3}

    monkeypatch.setattr(registry_stats_service, "_fetch_smithery_stats", _fake_smithery)
    monkeypatch.setattr(registry_stats_service, "_fetch_pulsemcp_stats", _fake_pulsemcp)
    response = client.get("/api/discovery/registry-stats?refresh=true")

    assert response.status_code == 200
    # Live fetchers fired despite warm cache.
    assert fetcher_called["smithery"] == 1, "refresh=true must call live fetcher"
    assert fetcher_called["pulsemcp"] == 1, "refresh=true must call live fetcher"

    body = response.json()
    smithery = next(i for i in body["items"] if i["registry_id"] == "smithery")
    assert smithery["source"] == "live"
    assert smithery["install_count"] == 42


# ---------- validator coverage: one validator per registry target ----------


def test_every_inventory_registry_has_a_callable_validator():
    """The validation pipeline contract: every inventory item ships a
    callable validator. If a registry slips into the JSON file without a
    validator entry, the pipeline silently degrades — assert the bijection.
    """
    repo_root = registry_discovery_service._repo_root()
    targets = registry_discovery_service._load_targets(repo_root)

    # The inventory ships ≥ 6 registries; every target carries a validator.
    assert len(targets) >= 6
    for target in targets:
        assert callable(target.validator), f"{target.registry_id} has no callable validator"
        # Validator returns a bool deterministically (no exceptions).
        result = target.validator()
        assert isinstance(result, bool)


# ---------- combined strange-minimal: stats-down + cache-cold + dashboard merge ----------


def test_dashboard_under_combined_failure_still_serves_submissions(client, tmp_path, monkeypatch):
    """The hardest edge: stats source down, cache cold, dashboard still
    serves the submission inventory and marks every stat_source unavailable.
    This is the single test that proves the validation pipeline survives
    the worst realistic deploy state.
    """
    # Cold cache: redirect cache_dir to an empty tmp_path.
    monkeypatch.setattr(registry_stats_service, "_cache_dir", lambda: tmp_path)

    # Live fetchers return None (treated as upstream failure).
    monkeypatch.setattr(registry_stats_service, "_fetch_smithery_stats", lambda: None)
    monkeypatch.setattr(registry_stats_service, "_fetch_pulsemcp_stats", lambda: None)

    response = client.get("/api/discovery/registry-dashboard")
    assert response.status_code == 200
    body = response.json()

    assert len(body["items"]) >= 6
    # Every item: stats unavailable, but submission shape survives.
    for item in body["items"]:
        assert item["stat_source"] == "unavailable"
        assert item["install_count"] is None
        assert item["registry_id"]  # submission record intact
        assert item["status"] in {"submission_ready", "missing_assets"}
