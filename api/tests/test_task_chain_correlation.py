"""Tests for cross-task-outcome-correlation spec — all 6 requirements."""

import json
import pytest
from pathlib import Path

from app.services.task_chain_correlation_service import (
    record_chain_link,
    resolve_chain,
    compute_chain_effectiveness,
    enrich_upstream_measurement,
    get_chain_stats,
)


@pytest.fixture()
def tmp_chain_store(tmp_path: Path) -> Path:
    """Return a temp path for chain link storage."""
    return tmp_path / "task_chain_links.json"


@pytest.fixture()
def tmp_measurement_store(tmp_path: Path) -> Path:
    """Return a temp path with a pre-seeded measurement file."""
    store = tmp_path / "slot_measurements" / "test.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    measurements = [
        {
            "slot_id": "variant-a",
            "task_id": "task-root",
            "value_score": 0.8,
            "resource_cost": 0.01,
            "raw_signals": {
                "status": "completed",
                "execution_quality": 0.8,
            },
        },
    ]
    store.write_text(json.dumps(measurements, indent=2))
    return store


# ── R1: Record chain link ──────────────────────────────────────────


def test_record_chain_link(tmp_chain_store: Path) -> None:
    """R1: TaskChainLink recorded when downstream task has source_task_id."""
    link = record_chain_link(
        "task-A", "task-B", "heal", "pending", store_path=tmp_chain_store
    )
    assert link["upstream_task_id"] == "task-A"
    assert link["downstream_task_id"] == "task-B"
    assert link["link_type"] == "heal"
    assert link["downstream_status"] == "pending"
    assert "created_at" in link

    # Verify persisted to file
    data = json.loads(tmp_chain_store.read_text())
    assert len(data) == 1
    assert data[0]["upstream_task_id"] == "task-A"


def test_record_chain_link_invalid_type_defaults(tmp_chain_store: Path) -> None:
    """Invalid link_type defaults to 'continuation'."""
    link = record_chain_link(
        "task-X", "task-Y", "bogus", store_path=tmp_chain_store
    )
    assert link["link_type"] == "continuation"


# ── R2: Chain resolution ───────────────────────────────────────────


def test_resolve_chain_ordered(tmp_chain_store: Path) -> None:
    """R2: resolve_chain returns ordered chain from root."""
    record_chain_link("root", "mid", "heal", "completed", store_path=tmp_chain_store)
    record_chain_link("mid", "leaf", "test", "completed", store_path=tmp_chain_store)

    chain = resolve_chain("root", store_path=tmp_chain_store)
    assert len(chain) == 2
    assert chain[0]["upstream_task_id"] == "root"
    assert chain[0]["downstream_task_id"] == "mid"
    assert chain[1]["upstream_task_id"] == "mid"
    assert chain[1]["downstream_task_id"] == "leaf"


def test_resolve_chain_cycle_protection(tmp_chain_store: Path) -> None:
    """R2: Cycle protection — does not loop forever."""
    record_chain_link("A", "B", "continuation", "completed", store_path=tmp_chain_store)
    record_chain_link("B", "C", "continuation", "completed", store_path=tmp_chain_store)
    record_chain_link("C", "A", "continuation", "completed", store_path=tmp_chain_store)

    chain = resolve_chain("A", store_path=tmp_chain_store)
    # Should find A->B and B->C but NOT C->A (cycle back to root)
    assert len(chain) == 2
    downstream_ids = [l["downstream_task_id"] for l in chain]
    assert "B" in downstream_ids
    assert "C" in downstream_ids
    assert downstream_ids.count("A") == 0  # no cycle back


def test_resolve_chain_max_depth(tmp_chain_store: Path) -> None:
    """R2: Max depth 10 prevents deep chains."""
    # Create a chain of depth 15
    for i in range(15):
        record_chain_link(
            f"t{i}", f"t{i+1}", "continuation", "completed", store_path=tmp_chain_store
        )

    chain = resolve_chain("t0", store_path=tmp_chain_store)
    # Max depth 10 means at most 10 links
    assert len(chain) <= 10


# ── R3 + R4: Chain effectiveness scoring ───────────────────────────


def test_effectiveness_root_failed() -> None:
    """R4: Root task failed -> 0.0."""
    chain = [{"link_type": "test", "downstream_status": "completed"}]
    result = compute_chain_effectiveness(chain, root_task_status="failed")
    assert result["chain_effectiveness"] == 0.0
    assert result["value_validated"] is False
    assert result["terminal_status"] == "failed"


def test_effectiveness_unvalidated() -> None:
    """R4: Root succeeded, no downstream tasks -> 0.5."""
    result = compute_chain_effectiveness([], root_task_status="completed")
    assert result["chain_effectiveness"] == 0.5
    assert result["value_validated"] is False
    assert result["chain_length"] == 1


def test_effectiveness_review_passed() -> None:
    """R4: Root succeeded, downstream review passed -> 1.0."""
    chain = [
        {
            "upstream_task_id": "root",
            "downstream_task_id": "review-1",
            "link_type": "review",
            "downstream_status": "completed",
        }
    ]
    result = compute_chain_effectiveness(chain, root_task_status="completed")
    assert result["chain_effectiveness"] == 1.0
    assert result["value_validated"] is True
    assert result["chain_length"] == 2


def test_effectiveness_review_failed() -> None:
    """R4: Root succeeded, downstream review failed -> 0.2."""
    chain = [
        {
            "upstream_task_id": "root",
            "downstream_task_id": "review-1",
            "link_type": "review",
            "downstream_status": "failed",
        }
    ]
    result = compute_chain_effectiveness(chain, root_task_status="completed")
    assert result["chain_effectiveness"] == 0.2
    assert result["value_validated"] is False


def test_effectiveness_heal_succeeded() -> None:
    """R4: Root succeeded, heal needed and succeeded -> 0.6."""
    chain = [
        {
            "upstream_task_id": "root",
            "downstream_task_id": "heal-1",
            "link_type": "heal",
            "downstream_status": "completed",
        }
    ]
    result = compute_chain_effectiveness(chain, root_task_status="completed")
    assert result["chain_effectiveness"] == 0.6
    assert result["value_validated"] is False


def test_effectiveness_test_passed() -> None:
    """R4: Root succeeded, downstream test passed -> 1.0 (same as review)."""
    chain = [
        {
            "upstream_task_id": "root",
            "downstream_task_id": "test-1",
            "link_type": "test",
            "downstream_status": "completed",
        }
    ]
    result = compute_chain_effectiveness(chain, root_task_status="completed")
    assert result["chain_effectiveness"] == 1.0
    assert result["value_validated"] is True


# ── R5: Measurement enrichment ─────────────────────────────────────


def test_enrich_upstream_measurement(
    tmp_chain_store: Path, tmp_measurement_store: Path
) -> None:
    """R5: enrich_upstream_measurement updates raw_signals with chain_effectiveness."""
    # Create a chain: root -> review (passed)
    record_chain_link(
        "task-root", "task-review", "review", "completed", store_path=tmp_chain_store
    )

    result = enrich_upstream_measurement(
        "task-root",
        store_path=tmp_chain_store,
        measurement_store_path=tmp_measurement_store,
    )

    assert result is not None
    assert result["root_task_id"] == "task-root"
    assert result["chain_effectiveness"] == 1.0
    assert result["value_validated"] is True

    # Verify the measurement file was updated
    data = json.loads(tmp_measurement_store.read_text())
    m = data[0]
    assert m["raw_signals"]["chain_effectiveness"] == 1.0
    assert m["raw_signals"]["value_validated"] is True
    # Original signals still present
    assert m["raw_signals"]["status"] == "completed"
    assert m["raw_signals"]["execution_quality"] == 0.8


def test_enrich_upstream_measurement_no_chain(
    tmp_chain_store: Path, tmp_measurement_store: Path
) -> None:
    """R5: enrich_upstream_measurement with no chain -> 0.5 (unvalidated)."""
    result = enrich_upstream_measurement(
        "task-root",
        store_path=tmp_chain_store,
        measurement_store_path=tmp_measurement_store,
    )
    assert result is not None
    assert result["chain_effectiveness"] == 0.5
    assert result["value_validated"] is False


# ── R6: Chain stats endpoint ───────────────────────────────────────


def test_chain_stats_shape(tmp_chain_store: Path) -> None:
    """R6: Stats returns correct shape with real data."""
    record_chain_link("r1", "d1", "review", "completed", store_path=tmp_chain_store)
    record_chain_link("r2", "d2", "heal", "failed", store_path=tmp_chain_store)
    record_chain_link("r3", "d3", "test", "completed", store_path=tmp_chain_store)

    stats = get_chain_stats(store_path=tmp_chain_store)

    assert stats["total_chains"] == 3
    assert isinstance(stats["avg_chain_length"], float)
    assert isinstance(stats["avg_effectiveness"], float)
    assert isinstance(stats["validation_rate"], float)
    assert "review" in stats["by_link_type"]
    assert "heal" in stats["by_link_type"]
    assert "test" in stats["by_link_type"]
    assert stats["by_link_type"]["review"]["count"] == 1
    assert stats["by_link_type"]["review"]["pass_rate"] == 1.0
    assert stats["by_link_type"]["heal"]["pass_rate"] == 0.0


def test_chain_stats_empty(tmp_chain_store: Path) -> None:
    """R6: Stats returns empty shape when no chains exist."""
    stats = get_chain_stats(store_path=tmp_chain_store)

    assert stats == {
        "total_chains": 0,
        "avg_chain_length": 0.0,
        "avg_effectiveness": 0.0,
        "validation_rate": 0.0,
        "by_link_type": {},
    }
