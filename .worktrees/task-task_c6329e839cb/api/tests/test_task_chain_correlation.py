"""Cross-task-outcome-correlation (6 requirements in 3 flows).

  · Recording + resolution: record_chain_link persists, invalid
    link_type defaults to 'continuation', resolve_chain returns
    ordered links, cycle protection prevents loops, max depth
    bounds chain length
  · Effectiveness scoring across the requirement matrix: root
    failed / unvalidated / review passed / review failed / heal
    succeeded / test passed
  · Measurement enrichment (with + without chain) + chain stats
    (populated + empty)
"""

import json
from pathlib import Path

import pytest

from app.services.task_chain_correlation_service import (
    record_chain_link,
    resolve_chain,
    compute_chain_effectiveness,
    enrich_upstream_measurement,
    get_chain_stats,
)


@pytest.fixture()
def tmp_chain_store(tmp_path: Path) -> Path:
    return tmp_path / "task_chain_links.json"


@pytest.fixture()
def tmp_measurement_store(tmp_path: Path) -> Path:
    store = tmp_path / "slot_measurements" / "test.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps([
        {
            "slot_id": "variant-a", "task_id": "task-root",
            "value_score": 0.8, "resource_cost": 0.01,
            "raw_signals": {"status": "completed", "execution_quality": 0.8},
        },
    ], indent=2))
    return store


def test_chain_record_and_resolution(tmp_chain_store: Path) -> None:
    """R1+R2: record creates the link with timestamp + persists,
    invalid types default to 'continuation', resolve returns chain
    in order with cycle protection and max-depth bounding."""
    link = record_chain_link("task-A", "task-B", "heal", "pending",
                             store_path=tmp_chain_store)
    assert link["upstream_task_id"] == "task-A"
    assert link["downstream_task_id"] == "task-B"
    assert link["link_type"] == "heal"
    assert link["downstream_status"] == "pending"
    assert "created_at" in link
    # Persisted to file.
    stored = json.loads(tmp_chain_store.read_text())
    assert len(stored) == 1 and stored[0]["upstream_task_id"] == "task-A"

    # Invalid type defaults.
    invalid = record_chain_link("task-X", "task-Y", "bogus",
                                store_path=tmp_chain_store)
    assert invalid["link_type"] == "continuation"

    # Fresh store for resolve tests.
    order_store = tmp_chain_store.parent / "order.json"
    record_chain_link("root", "mid", "heal", "completed", store_path=order_store)
    record_chain_link("mid", "leaf", "test", "completed", store_path=order_store)
    chain = resolve_chain("root", store_path=order_store)
    assert len(chain) == 2
    assert chain[0]["upstream_task_id"] == "root"
    assert chain[0]["downstream_task_id"] == "mid"
    assert chain[1]["upstream_task_id"] == "mid"
    assert chain[1]["downstream_task_id"] == "leaf"

    # Cycle protection: A→B→C→A, resolve from A follows A→B→C and stops.
    cycle_store = tmp_chain_store.parent / "cycle.json"
    for u, d in [("A", "B"), ("B", "C"), ("C", "A")]:
        record_chain_link(u, d, "continuation", "completed", store_path=cycle_store)
    cycle_chain = resolve_chain("A", store_path=cycle_store)
    assert len(cycle_chain) == 2
    downstreams = [link["downstream_task_id"] for link in cycle_chain]
    assert "B" in downstreams and "C" in downstreams
    assert downstreams.count("A") == 0

    # Max depth bounds chains to 10.
    deep_store = tmp_chain_store.parent / "deep.json"
    for i in range(15):
        record_chain_link(f"t{i}", f"t{i+1}", "continuation", "completed",
                          store_path=deep_store)
    assert len(resolve_chain("t0", store_path=deep_store)) <= 10


def test_chain_effectiveness_matrix() -> None:
    """R3+R4: every terminal state the scoring matrix covers —
    root failed → 0.0, unvalidated → 0.5, review/test passed → 1.0
    (validated), review failed → 0.2, heal succeeded → 0.6."""
    # Root failed — short-circuits regardless of downstream.
    failed = compute_chain_effectiveness(
        [{"link_type": "test", "downstream_status": "completed"}],
        root_task_status="failed",
    )
    assert failed["chain_effectiveness"] == 0.0
    assert failed["value_validated"] is False
    assert failed["terminal_status"] == "failed"

    # Root succeeded, no downstream — 0.5, chain_length 1.
    unvalidated = compute_chain_effectiveness([], root_task_status="completed")
    assert unvalidated["chain_effectiveness"] == 0.5
    assert unvalidated["value_validated"] is False
    assert unvalidated["chain_length"] == 1

    # Review passed → 1.0.
    review_ok = compute_chain_effectiveness(
        [{"upstream_task_id": "root", "downstream_task_id": "review-1",
          "link_type": "review", "downstream_status": "completed"}],
        root_task_status="completed",
    )
    assert review_ok["chain_effectiveness"] == 1.0
    assert review_ok["value_validated"] is True
    assert review_ok["chain_length"] == 2

    # Review failed → 0.2.
    review_bad = compute_chain_effectiveness(
        [{"upstream_task_id": "root", "downstream_task_id": "review-1",
          "link_type": "review", "downstream_status": "failed"}],
        root_task_status="completed",
    )
    assert review_bad["chain_effectiveness"] == 0.2
    assert review_bad["value_validated"] is False

    # Heal succeeded → 0.6.
    heal_ok = compute_chain_effectiveness(
        [{"upstream_task_id": "root", "downstream_task_id": "heal-1",
          "link_type": "heal", "downstream_status": "completed"}],
        root_task_status="completed",
    )
    assert heal_ok["chain_effectiveness"] == 0.6
    assert heal_ok["value_validated"] is False

    # Test passed — same 1.0 treatment as review.
    test_ok = compute_chain_effectiveness(
        [{"upstream_task_id": "root", "downstream_task_id": "test-1",
          "link_type": "test", "downstream_status": "completed"}],
        root_task_status="completed",
    )
    assert test_ok["chain_effectiveness"] == 1.0
    assert test_ok["value_validated"] is True


def test_measurement_enrichment_and_stats(
    tmp_chain_store: Path, tmp_measurement_store: Path,
) -> None:
    """R5: enrich_upstream_measurement writes chain_effectiveness +
    value_validated onto the measurement's raw_signals, preserving
    original signals. No-chain case lands 0.5 / unvalidated.

    R6: get_chain_stats aggregates with shape (totals, averages,
    validation rate, per-link-type breakdown with pass rates), and
    returns the empty shape when no chains exist."""
    # Enrichment with a chain — 1.0 review_passed lands on measurement.
    record_chain_link("task-root", "task-review", "review", "completed",
                      store_path=tmp_chain_store)
    enriched = enrich_upstream_measurement(
        "task-root",
        store_path=tmp_chain_store,
        measurement_store_path=tmp_measurement_store,
    )
    assert enriched is not None
    assert enriched["root_task_id"] == "task-root"
    assert enriched["chain_effectiveness"] == 1.0
    assert enriched["value_validated"] is True

    # Measurement file carries the new signals, original signals preserved.
    measurement = json.loads(tmp_measurement_store.read_text())[0]
    assert measurement["raw_signals"]["chain_effectiveness"] == 1.0
    assert measurement["raw_signals"]["value_validated"] is True
    assert measurement["raw_signals"]["status"] == "completed"
    assert measurement["raw_signals"]["execution_quality"] == 0.8

    # Enrichment without a chain — 0.5 / unvalidated.
    no_chain_store = tmp_chain_store.parent / "no_chain.json"
    no_chain_measurement = tmp_measurement_store.parent / "no_chain.json"
    no_chain_measurement.write_text(json.dumps([{
        "slot_id": "v", "task_id": "task-root", "value_score": 0.5,
        "resource_cost": 0.0, "raw_signals": {"status": "completed"},
    }]))
    no_chain_result = enrich_upstream_measurement(
        "task-root",
        store_path=no_chain_store,
        measurement_store_path=no_chain_measurement,
    )
    assert no_chain_result is not None
    assert no_chain_result["chain_effectiveness"] == 0.5
    assert no_chain_result["value_validated"] is False

    # Chain stats shape with three mixed link types.
    stats_store = tmp_chain_store.parent / "stats.json"
    for u, d, kind, status in [
        ("r1", "d1", "review", "completed"),
        ("r2", "d2", "heal", "failed"),
        ("r3", "d3", "test", "completed"),
    ]:
        record_chain_link(u, d, kind, status, store_path=stats_store)
    stats = get_chain_stats(store_path=stats_store)
    assert stats["total_chains"] == 3
    assert isinstance(stats["avg_chain_length"], float)
    assert isinstance(stats["avg_effectiveness"], float)
    assert isinstance(stats["validation_rate"], float)
    assert {"review", "heal", "test"} <= stats["by_link_type"].keys()
    assert stats["by_link_type"]["review"]["count"] == 1
    assert stats["by_link_type"]["review"]["pass_rate"] == 1.0
    assert stats["by_link_type"]["heal"]["pass_rate"] == 0.0

    # Empty store returns the null shape.
    empty_store = tmp_chain_store.parent / "empty.json"
    assert get_chain_stats(store_path=empty_store) == {
        "total_chains": 0, "avg_chain_length": 0.0, "avg_effectiveness": 0.0,
        "validation_rate": 0.0, "by_link_type": {},
    }
