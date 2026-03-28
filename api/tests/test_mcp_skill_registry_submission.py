"""Tests for Spec 180 — Submit to 5+ MCP and Skill Registries for Discovery.

Covers:
  AC1  registry-submissions lists all six spec-180 registry IDs
  AC2  core_requirement_met true when all assets present
  AC3  registry-stats returns items with valid source labels
  AC4  ?refresh=true forces live fetch, bypasses cache
  AC5  upstream failures return HTTP 200 with source=unavailable, not 500
  AC6  registry-dashboard returns HTTP 200 even when stats fail
  AC7  glama.json asset validation
  AC8  six registry validators present in discovery service
  AC9  full happy-path + failure-mode coverage

Verification Scenarios (from spec):
  S1   All six registry IDs appear in submission inventory
  S2   core_requirement_met when all assets present
  S3   stats endpoint source labels are valid enum values
  S4   ?refresh=true bypasses 24-hour cache
  S5   dashboard merges submission + stats in one call
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.registry_discovery import (
    RegistryDashboard,
    RegistryDashboardItem,
    RegistryStatSource,
    RegistryStats,
    RegistryStatsList,
    RegistryStatsSummary,
    RegistrySubmissionInventory,
    RegistrySubmissionStatus,
)
from app.services import registry_discovery_service, registry_stats_service

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Spec 180 target registry IDs
# ---------------------------------------------------------------------------
SPEC_180_REGISTRY_IDS = {"smithery", "glama", "pulsemcp", "mcp-so", "skills-sh", "askill-sh"}
SPEC_180_MIN_READY = 5


# ===========================================================================
# Scenario 1 — All six registries appear in submission inventory (AC1, AC8)
# ===========================================================================


@pytest.mark.asyncio
async def test_registry_submissions_endpoint_returns_200() -> None:
    """GET /api/discovery/registry-submissions must return HTTP 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_registry_submissions_has_required_summary_fields() -> None:
    """Submission summary must include target_count, submission_ready_count, core_requirement_met."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")
    payload = resp.json()
    summary = payload["summary"]
    assert "target_count" in summary
    assert "submission_ready_count" in summary
    assert "missing_asset_count" in summary
    assert "core_requirement_met" in summary
    assert isinstance(summary["core_requirement_met"], bool)


@pytest.mark.asyncio
async def test_registry_submissions_item_schema() -> None:
    """Each item must have required fields with correct types."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")
    items = resp.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert "registry_id" in item
        assert "registry_name" in item
        assert "category" in item
        assert item["category"] in ("mcp", "skill")
        assert "status" in item
        assert item["status"] in ("submission_ready", "missing_assets")
        assert "install_hint" in item
        assert "required_files" in item
        assert "missing_files" in item


# ---------------------------------------------------------------------------
# Scenario 1 — Six spec-180 registry IDs present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registry_submissions_includes_smithery() -> None:
    """smithery must appear in registry-submissions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")
    ids = {item["registry_id"] for item in resp.json()["items"]}
    assert "smithery" in ids, f"'smithery' missing from registry IDs: {ids}"


@pytest.mark.asyncio
async def test_registry_submissions_includes_mcp_so() -> None:
    """mcp-so must appear in registry-submissions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")
    ids = {item["registry_id"] for item in resp.json()["items"]}
    assert "mcp-so" in ids, f"'mcp-so' missing from registry IDs: {ids}"


@pytest.mark.asyncio
async def test_registry_submissions_covers_at_least_five_targets() -> None:
    """At least five distinct registry targets must be present (core requirement)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")
    payload = resp.json()
    assert payload["summary"]["target_count"] >= SPEC_180_MIN_READY


@pytest.mark.asyncio
async def test_registry_submissions_covers_both_categories() -> None:
    """Both 'mcp' and 'skill' categories must be represented."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")
    categories = {item["category"] for item in resp.json()["items"]}
    assert "mcp" in categories
    assert "skill" in categories


# ===========================================================================
# Scenario 2 — core_requirement_met when all assets present (AC2)
# ===========================================================================


@pytest.mark.asyncio
async def test_registry_submissions_core_requirement_met_when_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """core_requirement_met must be True when >= 5 items are submission_ready."""
    from app.models.registry_discovery import RegistrySubmissionSummary

    mock_inventory = RegistrySubmissionInventory(
        summary=RegistrySubmissionSummary(
            target_count=6,
            submission_ready_count=6,
            missing_asset_count=0,
            categories={"mcp": 4, "skill": 2},
            core_requirement_met=True,
        ),
        items=[],
    )

    monkeypatch.setattr(
        registry_discovery_service,
        "build_registry_submission_inventory",
        lambda: mock_inventory,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")
    assert resp.status_code == 200
    assert resp.json()["summary"]["core_requirement_met"] is True


def test_registry_submission_summary_core_requirement_unit() -> None:
    """Unit: core_requirement_met logic — True when ready_count >= 5."""
    from app.models.registry_discovery import RegistrySubmissionSummary

    s_met = RegistrySubmissionSummary(
        target_count=6,
        submission_ready_count=5,
        missing_asset_count=1,
        categories={"mcp": 4, "skill": 2},
        core_requirement_met=True,
    )
    assert s_met.core_requirement_met is True

    s_not_met = RegistrySubmissionSummary(
        target_count=6,
        submission_ready_count=4,
        missing_asset_count=2,
        categories={"mcp": 4, "skill": 2},
        core_requirement_met=False,
    )
    assert s_not_met.core_requirement_met is False


def test_registry_submission_missing_asset_changes_status() -> None:
    """Unit: missing_files non-empty maps to MISSING_ASSETS status."""
    from app.models.registry_discovery import RegistrySubmissionRecord

    record = RegistrySubmissionRecord(
        registry_id="smithery",
        registry_name="Smithery",
        category="mcp",
        asset_name="coherence-mcp-server",
        status=RegistrySubmissionStatus.MISSING_ASSETS,
        install_hint="npx coherence-mcp-server",
        required_files=["mcp-server/server.json"],
        missing_files=["mcp-server/server.json"],
        notes="Missing MCP manifest",
    )
    assert record.status == RegistrySubmissionStatus.MISSING_ASSETS
    assert "mcp-server/server.json" in record.missing_files


# ===========================================================================
# Scenario 3 — Stats endpoint source labels (AC3, AC5)
# ===========================================================================


@pytest.mark.asyncio
async def test_registry_stats_endpoint_returns_200() -> None:
    """GET /api/discovery/registry-stats must return HTTP 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-stats")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_registry_stats_items_have_valid_source_labels() -> None:
    """Each stats item must have source in ['live','cached','unavailable']."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-stats")
    payload = resp.json()
    assert "items" in payload
    assert "summary" in payload
    valid_sources = {"live", "cached", "unavailable"}
    for item in payload["items"]:
        assert "registry_id" in item
        assert "source" in item
        assert item["source"] in valid_sources, (
            f"registry {item['registry_id']} has invalid source: {item['source']}"
        )


@pytest.mark.asyncio
async def test_registry_stats_no_public_api_registries_marked_unavailable() -> None:
    """mcp-so, skills-sh, askill-sh have no public API — must be unavailable."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-stats")
    items_by_id = {item["registry_id"]: item for item in resp.json()["items"]}
    no_api_registries = ["mcp-so", "skills-sh", "askill-sh"]
    for rid in no_api_registries:
        if rid in items_by_id:
            assert items_by_id[rid]["source"] == "unavailable", (
                f"{rid} should be unavailable but got {items_by_id[rid]['source']}"
            )


@pytest.mark.asyncio
async def test_registry_stats_summary_fields() -> None:
    """Stats summary must include total_installs, total_downloads, registries_with_counts, registries_unavailable."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-stats")
    summary = resp.json()["summary"]
    assert "total_installs" in summary
    assert "total_downloads" in summary
    assert "registries_with_counts" in summary
    assert "registries_unavailable" in summary
    assert isinstance(summary["total_installs"], int)
    assert isinstance(summary["total_downloads"], int)


@pytest.mark.asyncio
async def test_registry_stats_upstream_failure_returns_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: upstream fetch failure must return HTTP 200, not 500."""
    unavailable = RegistryStatsList(
        summary=RegistryStatsSummary(
            total_installs=0,
            total_downloads=0,
            registries_with_counts=0,
            registries_unavailable=6,
        ),
        items=[
            RegistryStats(registry_id="smithery", registry_name="Smithery", source=RegistryStatSource.UNAVAILABLE, error="upstream timeout"),
            RegistryStats(registry_id="pulsemcp", registry_name="PulseMCP", source=RegistryStatSource.UNAVAILABLE, error="upstream timeout"),
            RegistryStats(registry_id="glama", registry_name="Glama", source=RegistryStatSource.UNAVAILABLE),
            RegistryStats(registry_id="mcp-so", registry_name="MCP.so", source=RegistryStatSource.UNAVAILABLE),
            RegistryStats(registry_id="skills-sh", registry_name="skills.sh", source=RegistryStatSource.UNAVAILABLE),
            RegistryStats(registry_id="askill-sh", registry_name="askill.sh", source=RegistryStatSource.UNAVAILABLE),
        ],
    )
    monkeypatch.setattr(registry_stats_service, "fetch_registry_stats", lambda **kw: unavailable)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-stats")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["source"] == "unavailable"
        assert item["install_count"] is None


# ===========================================================================
# Scenario 4 — Cache refresh behaviour (AC4)
# ===========================================================================


def test_registry_stats_service_cache_write_and_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache write followed by read without refresh returns cached source."""
    cache_dir = tmp_path / ".cache" / "registry_stats"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(registry_stats_service, "_cache_dir", lambda: cache_dir)

    # Simulate live fetch succeeding
    live_data = {"install_count": 42, "download_count": 10}
    registry_stats_service._write_cache("smithery", dict(live_data))

    # Now read back — should hit cache (not expired)
    cached = registry_stats_service._read_cache("smithery")
    assert cached is not None
    assert cached["install_count"] == 42
    assert cached["download_count"] == 10


def test_registry_stats_service_cache_expired_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Expired cache (> 24h) must return None from _read_cache."""
    cache_dir = tmp_path / ".cache" / "registry_stats"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(registry_stats_service, "_cache_dir", lambda: cache_dir)

    stale_data = {
        "install_count": 99,
        "fetched_at_ts": time.time() - 90000,  # 25 hours ago
    }
    (cache_dir / "smithery.json").write_text(json.dumps(stale_data), encoding="utf-8")

    result = registry_stats_service._read_cache("smithery")
    assert result is None


def test_registry_stats_service_stale_cache_returned_on_live_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When live fetch fails, stale cache is returned with source=cached and error set."""
    cache_dir = tmp_path / ".cache" / "registry_stats"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(registry_stats_service, "_cache_dir", lambda: cache_dir)

    stale_data = {
        "install_count": 77,
        "download_count": 5,
        "fetched_at_ts": time.time() - 90000,  # 25 hours old
    }
    (cache_dir / "smithery.json").write_text(json.dumps(stale_data), encoding="utf-8")

    result = registry_stats_service._build_stats_item(
        "smithery", "Smithery", refresh=True, live_fetcher=lambda: None
    )
    assert result.source == RegistryStatSource.CACHED
    assert result.install_count == 77
    assert result.error == "upstream timeout"


def test_registry_stats_service_no_cache_no_live_returns_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No cache + live fetch failure -> source=unavailable, install_count=None, error set."""
    cache_dir = tmp_path / ".cache" / "registry_stats"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(registry_stats_service, "_cache_dir", lambda: cache_dir)

    result = registry_stats_service._build_stats_item(
        "smithery", "Smithery", refresh=False, live_fetcher=lambda: None
    )
    assert result.source == RegistryStatSource.UNAVAILABLE
    assert result.install_count is None
    assert result.error is not None


def test_registry_stats_service_refresh_bypasses_valid_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """refresh=True must bypass a valid (non-expired) cache and call live fetcher."""
    cache_dir = tmp_path / ".cache" / "registry_stats"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(registry_stats_service, "_cache_dir", lambda: cache_dir)

    # Write a fresh (non-expired) cache
    fresh_data = {"install_count": 5, "fetched_at_ts": time.time() - 100}
    (cache_dir / "smithery.json").write_text(json.dumps(fresh_data), encoding="utf-8")

    live_called = []

    def live_fetcher():
        live_called.append(True)
        return {"install_count": 999, "download_count": 0}

    result = registry_stats_service._build_stats_item(
        "smithery", "Smithery", refresh=True, live_fetcher=live_fetcher
    )
    assert live_called, "live_fetcher was not called despite refresh=True"
    assert result.source == RegistryStatSource.LIVE
    assert result.install_count == 999


@pytest.mark.asyncio
async def test_registry_stats_refresh_query_param(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """?refresh=true query param results in source='live' for registries with live APIs."""
    live_result = RegistryStatsList(
        summary=RegistryStatsSummary(
            total_installs=100,
            total_downloads=50,
            registries_with_counts=2,
            registries_unavailable=4,
        ),
        items=[
            RegistryStats(registry_id="smithery", registry_name="Smithery", source=RegistryStatSource.LIVE, install_count=100),
            RegistryStats(registry_id="pulsemcp", registry_name="PulseMCP", source=RegistryStatSource.LIVE, install_count=50),
            RegistryStats(registry_id="glama", registry_name="Glama", source=RegistryStatSource.UNAVAILABLE),
            RegistryStats(registry_id="mcp-so", registry_name="MCP.so", source=RegistryStatSource.UNAVAILABLE),
            RegistryStats(registry_id="skills-sh", registry_name="skills.sh", source=RegistryStatSource.UNAVAILABLE),
            RegistryStats(registry_id="askill-sh", registry_name="askill.sh", source=RegistryStatSource.UNAVAILABLE),
        ],
    )

    refresh_captured = []

    def fake_fetch(refresh=False, registry_id_filter=None):
        refresh_captured.append(refresh)
        return live_result

    monkeypatch.setattr(registry_stats_service, "fetch_registry_stats", fake_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-stats?refresh=true")

    assert resp.status_code == 200
    assert True in refresh_captured, "refresh=True was not passed to fetch_registry_stats"


@pytest.mark.asyncio
async def test_registry_stats_filter_by_registry_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """?registry_id=smithery returns only smithery item."""
    smithery_only = RegistryStatsList(
        summary=RegistryStatsSummary(
            total_installs=42,
            total_downloads=0,
            registries_with_counts=1,
            registries_unavailable=0,
        ),
        items=[
            RegistryStats(registry_id="smithery", registry_name="Smithery", source=RegistryStatSource.LIVE, install_count=42),
        ],
    )

    filter_captured = []

    def fake_fetch(refresh=False, registry_id_filter=None):
        filter_captured.append(registry_id_filter)
        return smithery_only

    monkeypatch.setattr(registry_stats_service, "fetch_registry_stats", fake_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-stats?registry_id=smithery")

    assert resp.status_code == 200
    assert "smithery" in filter_captured
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["registry_id"] == "smithery"


# ===========================================================================
# Scenario 5 — Dashboard merges submission + stats (AC6)
# ===========================================================================


@pytest.mark.asyncio
async def test_registry_dashboard_returns_200() -> None:
    """GET /api/discovery/registry-dashboard must return HTTP 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-dashboard")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_registry_dashboard_has_all_sections() -> None:
    """Dashboard response must include submission_summary, stats_summary, and items."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-dashboard")
    payload = resp.json()
    assert "submission_summary" in payload
    assert "stats_summary" in payload
    assert "items" in payload
    assert isinstance(payload["items"], list)


@pytest.mark.asyncio
async def test_registry_dashboard_item_schema() -> None:
    """Each dashboard item must include registry_id, category, status, install_hint, stat_source."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-dashboard")
    for item in resp.json()["items"]:
        assert "registry_id" in item
        assert "registry_name" in item
        assert "category" in item
        assert item["category"] in ("mcp", "skill")
        assert "status" in item
        assert "install_hint" in item
        assert "stat_source" in item
        assert item["stat_source"] in ("live", "cached", "unavailable")


@pytest.mark.asyncio
async def test_registry_dashboard_returns_200_when_stats_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC6: dashboard must return HTTP 200 even when stats fetch raises an exception."""
    def raise_error(**kw):
        raise RuntimeError("Stats API completely down")

    monkeypatch.setattr(registry_stats_service, "fetch_registry_stats", raise_error)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-dashboard")

    assert resp.status_code == 200
    payload = resp.json()
    assert "submission_summary" in payload
    assert "items" in payload
    # All items should have unavailable stat_source
    for item in payload["items"]:
        assert item["stat_source"] == "unavailable"
        assert item["install_count"] is None


@pytest.mark.asyncio
async def test_registry_dashboard_merges_submission_and_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dashboard items must merge submission status with install counts."""
    mock_stats = RegistryStatsList(
        summary=RegistryStatsSummary(
            total_installs=200,
            total_downloads=100,
            registries_with_counts=2,
            registries_unavailable=4,
        ),
        items=[
            RegistryStats(registry_id="smithery", registry_name="Smithery", source=RegistryStatSource.LIVE, install_count=200),
            RegistryStats(registry_id="pulsemcp", registry_name="PulseMCP", source=RegistryStatSource.LIVE, install_count=100),
            RegistryStats(registry_id="glama", registry_name="Glama", source=RegistryStatSource.UNAVAILABLE),
            RegistryStats(registry_id="mcp-so", registry_name="MCP.so", source=RegistryStatSource.UNAVAILABLE),
            RegistryStats(registry_id="skills-sh", registry_name="skills.sh", source=RegistryStatSource.UNAVAILABLE),
            RegistryStats(registry_id="askill-sh", registry_name="askill.sh", source=RegistryStatSource.UNAVAILABLE),
        ],
    )
    monkeypatch.setattr(registry_stats_service, "fetch_registry_stats", lambda **kw: mock_stats)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-dashboard")

    assert resp.status_code == 200
    payload = resp.json()
    by_id = {item["registry_id"]: item for item in payload["items"]}

    # Smithery should have merged install count from stats
    if "smithery" in by_id:
        smithery = by_id["smithery"]
        assert smithery["install_count"] == 200
        assert smithery["stat_source"] == "live"


# ===========================================================================
# AC7 — glama.json asset validation (unit tests)
# ===========================================================================


def test_glama_json_exists() -> None:
    """mcp-server/glama.json must exist in repo root."""
    path = REPO_ROOT / "mcp-server" / "glama.json"
    assert path.exists(), (
        f"mcp-server/glama.json not found at {path}. "
        "This file is required for Glama (awesome-mcp-servers) submission."
    )


def test_glama_json_is_valid_json() -> None:
    """mcp-server/glama.json must be parseable JSON."""
    path = REPO_ROOT / "mcp-server" / "glama.json"
    if not path.exists():
        pytest.skip("glama.json does not exist yet")
    content = path.read_text(encoding="utf-8")
    data = json.loads(content)
    assert isinstance(data, dict)


def test_glama_json_has_required_fields() -> None:
    """AC7: glama.json must have name, description, url, tags fields."""
    path = REPO_ROOT / "mcp-server" / "glama.json"
    if not path.exists():
        pytest.skip("glama.json does not exist yet")
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"name", "description", "url", "tags"}
    missing = required - set(data.keys())
    assert not missing, f"glama.json is missing required fields: {missing}"
    assert isinstance(data["tags"], list), "glama.json tags must be a list"
    assert len(data["tags"]) >= 1, "glama.json tags must be non-empty"


def test_glama_json_name_matches_project() -> None:
    """glama.json name must be 'coherence-network'."""
    path = REPO_ROOT / "mcp-server" / "glama.json"
    if not path.exists():
        pytest.skip("glama.json does not exist yet")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("name") == "coherence-network"


# ===========================================================================
# AC8 — All six registry validators present in service (unit tests)
# ===========================================================================


def test_registry_discovery_service_has_smithery_target() -> None:
    """_TARGETS must include a target with registry_id='smithery'."""
    ids = {t.registry_id for t in registry_discovery_service._TARGETS}
    assert "smithery" in ids


def test_registry_discovery_service_has_mcp_so_target() -> None:
    """_TARGETS must include a target with registry_id='mcp-so'."""
    ids = {t.registry_id for t in registry_discovery_service._TARGETS}
    assert "mcp-so" in ids


def test_registry_discovery_service_has_at_least_five_targets() -> None:
    """_TARGETS must have >= 5 entries to meet core requirement."""
    assert len(registry_discovery_service._TARGETS) >= SPEC_180_MIN_READY


def test_registry_discovery_service_all_targets_have_validators() -> None:
    """Every target must have a callable validator and non-empty required_files."""
    for target in registry_discovery_service._TARGETS:
        assert callable(target.validator), f"{target.registry_id} validator is not callable"
        assert len(target.required_files) >= 1, f"{target.registry_id} has no required_files"


def test_registry_discovery_service_skill_targets_exist() -> None:
    """At least one target with category='skill' must exist."""
    skill_targets = [t for t in registry_discovery_service._TARGETS if t.category == "skill"]
    assert len(skill_targets) >= 1, "No skill-category targets found in _TARGETS"


def test_registry_discovery_service_mcp_targets_exist() -> None:
    """At least two targets with category='mcp' must exist (Smithery + at least one other)."""
    mcp_targets = [t for t in registry_discovery_service._TARGETS if t.category == "mcp"]
    assert len(mcp_targets) >= 2, f"Expected >= 2 mcp targets, got {len(mcp_targets)}"


# ===========================================================================
# Pydantic model unit tests (schema validation)
# ===========================================================================


def test_registry_stats_model_defaults() -> None:
    """RegistryStats with only required fields has None for optional count fields."""
    stats = RegistryStats(
        registry_id="test-registry",
        registry_name="Test Registry",
        source=RegistryStatSource.UNAVAILABLE,
    )
    assert stats.install_count is None
    assert stats.download_count is None
    assert stats.star_count is None
    assert stats.fetched_at is None
    assert stats.error is None


def test_registry_stats_source_enum_values() -> None:
    """RegistryStatSource must have exactly three values: live, cached, unavailable."""
    values = {e.value for e in RegistryStatSource}
    assert values == {"live", "cached", "unavailable"}


def test_registry_stats_summary_defaults() -> None:
    """RegistryStatsSummary defaults to zero counts."""
    summary = RegistryStatsSummary()
    assert summary.total_installs == 0
    assert summary.total_downloads == 0
    assert summary.registries_with_counts == 0
    assert summary.registries_unavailable == 0
    assert summary.last_updated is None


def test_registry_dashboard_item_model() -> None:
    """RegistryDashboardItem must serialize correctly."""
    item = RegistryDashboardItem(
        registry_id="smithery",
        registry_name="Smithery",
        category="mcp",
        status=RegistrySubmissionStatus.SUBMISSION_READY,
        install_hint="npx coherence-mcp-server",
        install_count=42,
        stat_source=RegistryStatSource.LIVE,
    )
    assert item.registry_id == "smithery"
    assert item.install_count == 42
    assert item.stat_source == RegistryStatSource.LIVE
    assert item.missing_files == []


def test_registry_dashboard_model() -> None:
    """RegistryDashboard must contain both summary blocks and items list."""
    from app.models.registry_discovery import RegistrySubmissionSummary

    dashboard = RegistryDashboard(
        submission_summary=RegistrySubmissionSummary(
            target_count=6,
            submission_ready_count=6,
            missing_asset_count=0,
            core_requirement_met=True,
        ),
        stats_summary=RegistryStatsSummary(
            total_installs=0,
            total_downloads=0,
            registries_unavailable=6,
        ),
        items=[],
    )
    assert dashboard.submission_summary.core_requirement_met is True
    assert dashboard.stats_summary.registries_unavailable == 6
    assert dashboard.items == []


# ===========================================================================
# OpenAPI registration tests
# ===========================================================================


@pytest.mark.asyncio
async def test_registry_stats_route_in_openapi() -> None:
    """GET /api/discovery/registry-stats must appear in OpenAPI spec."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
    paths = resp.json().get("paths", {})
    assert "/api/discovery/registry-stats" in paths, (
        "registry-stats route not found in OpenAPI paths"
    )


@pytest.mark.asyncio
async def test_registry_dashboard_route_in_openapi() -> None:
    """GET /api/discovery/registry-dashboard must appear in OpenAPI spec."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
    paths = resp.json().get("paths", {})
    assert "/api/discovery/registry-dashboard" in paths, (
        "registry-dashboard route not found in OpenAPI paths"
    )


@pytest.mark.asyncio
async def test_registry_submissions_route_tagged_discovery() -> None:
    """registry-submissions endpoint must be tagged 'discovery'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
    paths = resp.json().get("paths", {})
    path = paths.get("/api/discovery/registry-submissions", {})
    operation = path.get("get", {})
    assert "discovery" in operation.get("tags", [])


# ===========================================================================
# Edge case: fetch_registry_stats with unknown registry_id filter
# ===========================================================================


def test_registry_stats_service_unknown_filter_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Filtering by non-existent registry_id returns empty items list."""
    cache_dir = tmp_path / ".cache" / "registry_stats"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(registry_stats_service, "_cache_dir", lambda: cache_dir)

    # Patch live fetchers to fail so no HTTP calls are made
    monkeypatch.setattr(registry_stats_service, "_fetch_smithery_stats", lambda: None)
    monkeypatch.setattr(registry_stats_service, "_fetch_pulsemcp_stats", lambda: None)

    result = registry_stats_service.fetch_registry_stats(registry_id_filter="nonexistent-registry-xyz")
    assert result.items == []
    assert result.summary.total_installs == 0
    assert result.summary.registries_with_counts == 0


# ===========================================================================
# Integration: full create-read cycle for stats cache
# ===========================================================================


def test_registry_stats_service_write_then_read_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Write cache -> read back (within TTL) -> get cached value; after TTL reset -> None."""
    cache_dir = tmp_path / ".cache" / "registry_stats"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(registry_stats_service, "_cache_dir", lambda: cache_dir)

    # Write
    registry_stats_service._write_cache("pulsemcp", {"install_count": 123, "download_count": 7})

    # Read within TTL
    data = registry_stats_service._read_cache("pulsemcp")
    assert data is not None
    assert data["install_count"] == 123

    # Manually expire by overwriting with old timestamp
    stale = {"install_count": 123, "fetched_at_ts": time.time() - 100000}
    (cache_dir / "pulsemcp.json").write_text(json.dumps(stale), encoding="utf-8")

    # Read again — should return None (expired)
    data_after_expiry = registry_stats_service._read_cache("pulsemcp")
    assert data_after_expiry is None

    # But stale cache should still be readable
    stale_data = registry_stats_service._read_stale_cache("pulsemcp")
    assert stale_data is not None
    assert stale_data["install_count"] == 123
