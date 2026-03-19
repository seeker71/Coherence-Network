"""Tests for grounded idea portfolio metrics (spec 116).

All tests use real data structures — no mocks, no placeholders.
Every assertion verifies exact computed values from known inputs.
"""

from __future__ import annotations

import inspect

import pytest

from app.services.grounded_idea_metrics_service import (
    compute_all_idea_metrics,
    compute_idea_metrics,
    collect_all_data,
    _estimate_commit_cost_sum,
    _filter_by_idea_id,
    _filter_commits_by_idea,
)


# ---------------------------------------------------------------------------
# Helper: build realistic data objects as dicts
# ---------------------------------------------------------------------------

def _make_spec(
    spec_id: str,
    idea_id: str,
    actual_cost: float = 0.0,
    actual_value: float = 0.0,
    estimated_cost: float = 0.0,
    potential_value: float = 0.0,
) -> dict:
    return {
        "spec_id": spec_id,
        "idea_id": idea_id,
        "actual_cost": actual_cost,
        "actual_value": actual_value,
        "estimated_cost": estimated_cost,
        "potential_value": potential_value,
    }


def _make_runtime_summary(
    idea_id: str,
    event_count: int = 0,
    runtime_cost_estimate: float = 0.0,
    total_runtime_ms: float = 0.0,
) -> dict:
    return {
        "idea_id": idea_id,
        "event_count": event_count,
        "runtime_cost_estimate": runtime_cost_estimate,
        "total_runtime_ms": total_runtime_ms,
    }


def _make_lineage_link(
    link_id: str,
    idea_id: str,
    estimated_cost: float = 0.0,
) -> dict:
    return {"id": link_id, "idea_id": idea_id, "estimated_cost": estimated_cost}


def _make_valuation(
    lineage_id: str,
    idea_id: str,
    measured_value_total: float = 0.0,
    event_count: int = 0,
) -> dict:
    return {
        "lineage_id": lineage_id,
        "idea_id": idea_id,
        "measured_value_total": measured_value_total,
        "event_count": event_count,
    }


def _make_commit(idea_ids: list[str], change_files: int = 3, lines_added: int = 50) -> dict:
    return {
        "idea_ids": idea_ids,
        "change_files": change_files,
        "lines_added": lines_added,
    }


def _make_friction_event(idea_id: str, cost_of_delay: float = 0.0) -> dict:
    return {"idea_id": idea_id, "cost_of_delay": cost_of_delay}


# ===========================================================================
# TestActualCostComputation
# ===========================================================================

class TestActualCostComputation:
    """Test that computed_actual_cost aggregates from real sources."""

    def test_cost_from_specs_only(self):
        """Spec actual_cost flows into computed_actual_cost."""
        specs = [
            _make_spec("s1", "idea-a", actual_cost=5.0),
            _make_spec("s2", "idea-a", actual_cost=3.0),
            _make_spec("s3", "idea-b", actual_cost=10.0),  # Different idea
        ]
        result = compute_idea_metrics("idea-a", specs=specs)
        assert result["computed_actual_cost"] == 8.0
        assert result["grounding_sources"]["spec_actual_cost_sum"] == 8.0
        assert result["grounding_sources"]["spec_count"] == 2

    def test_cost_from_runtime_only(self):
        """Runtime cost flows into computed_actual_cost."""
        runtime = [_make_runtime_summary("idea-a", runtime_cost_estimate=2.5)]
        result = compute_idea_metrics("idea-a", runtime_summaries=runtime)
        assert result["computed_actual_cost"] == 2.5
        assert result["grounding_sources"]["runtime_cost_estimate"] == 2.5

    def test_cost_from_commits_only(self):
        """Commit cost flows into computed_actual_cost using real formula."""
        # 3 files, 50 lines → 0.10 + 3*0.15 + 50*0.002 = 0.10 + 0.45 + 0.10 = 0.65
        commits = [_make_commit(["idea-a"], change_files=3, lines_added=50)]
        result = compute_idea_metrics("idea-a", commit_records=commits)
        assert result["computed_actual_cost"] == 0.65
        assert result["grounding_sources"]["commit_cost_sum"] == 0.65
        assert result["grounding_sources"]["commit_count"] == 1

    def test_cost_aggregates_all_sources(self):
        """All three cost sources sum together."""
        specs = [_make_spec("s1", "idea-a", actual_cost=5.0)]
        runtime = [_make_runtime_summary("idea-a", runtime_cost_estimate=1.5)]
        commits = [_make_commit(["idea-a"], change_files=1, lines_added=10)]
        # Commit cost: 0.10 + 1*0.15 + 10*0.002 = 0.10 + 0.15 + 0.02 = 0.27
        result = compute_idea_metrics(
            "idea-a", specs=specs, runtime_summaries=runtime, commit_records=commits
        )
        assert result["computed_actual_cost"] == 5.0 + 1.5 + 0.27

    def test_zero_cost_with_no_data(self):
        """No data → zero cost."""
        result = compute_idea_metrics("idea-empty")
        assert result["computed_actual_cost"] == 0.0


# ===========================================================================
# TestActualValueComputation
# ===========================================================================

class TestActualValueComputation:
    """Test that computed_actual_value uses the strongest signal."""

    def test_value_from_lineage_measured(self):
        """Lineage measured value is the strongest signal."""
        links = [_make_lineage_link("lnk-1", "idea-a")]
        vals = {"lnk-1": _make_valuation("lnk-1", "idea-a", measured_value_total=50.0, event_count=3)}
        specs = [_make_spec("s1", "idea-a", actual_value=10.0)]
        result = compute_idea_metrics("idea-a", specs=specs, lineage_links=links, lineage_valuations=vals)
        # max(50.0, 0.0 revenue, 10.0 spec) = 50.0
        assert result["computed_actual_value"] == 50.0
        assert result["grounding_sources"]["lineage_measured_value"] == 50.0

    def test_value_from_usage_revenue(self):
        """Usage revenue can be the strongest signal."""
        runtime = [_make_runtime_summary("idea-a", event_count=5000)]
        # 5000 * 0.001 = 5.0
        result = compute_idea_metrics("idea-a", runtime_summaries=runtime)
        assert result["computed_actual_value"] == 5.0
        assert result["grounding_sources"]["usage_revenue_usd"] == 5.0

    def test_value_from_spec_actual(self):
        """Spec actual value can be the strongest signal."""
        specs = [
            _make_spec("s1", "idea-a", actual_value=20.0),
            _make_spec("s2", "idea-a", actual_value=15.0),
        ]
        result = compute_idea_metrics("idea-a", specs=specs)
        # max(0.0 lineage, 0.0 revenue, 35.0 spec sum) = 35.0
        assert result["computed_actual_value"] == 35.0
        assert result["grounding_sources"]["spec_actual_value_sum"] == 35.0

    def test_value_takes_max_across_sources(self):
        """The strongest signal wins, not the sum."""
        specs = [_make_spec("s1", "idea-a", actual_value=8.0)]
        runtime = [_make_runtime_summary("idea-a", event_count=20000)]
        # Revenue = 20000 * 0.001 = 20.0
        links = [_make_lineage_link("lnk-1", "idea-a")]
        vals = {"lnk-1": _make_valuation("lnk-1", "idea-a", measured_value_total=15.0)}
        result = compute_idea_metrics(
            "idea-a", specs=specs, runtime_summaries=runtime,
            lineage_links=links, lineage_valuations=vals,
        )
        # max(15.0, 20.0, 8.0) = 20.0
        assert result["computed_actual_value"] == 20.0

    def test_zero_value_with_no_data(self):
        """No data → zero value."""
        result = compute_idea_metrics("idea-empty")
        assert result["computed_actual_value"] == 0.0


# ===========================================================================
# TestConfidenceComputation
# ===========================================================================

class TestConfidenceComputation:
    """Test that confidence reflects data coverage, not hand-typed guesses."""

    def test_zero_data_gives_minimum_confidence(self):
        """No data → minimum confidence (0.05 floor)."""
        result = compute_idea_metrics("idea-empty")
        assert result["computed_confidence"] == 0.05

    def test_full_data_gives_high_confidence(self):
        """All data sources present → high confidence."""
        specs = [_make_spec("s1", "idea-a", actual_cost=5.0, actual_value=10.0)]
        runtime = [_make_runtime_summary("idea-a", event_count=100)]
        links = [_make_lineage_link("lnk-1", "idea-a")]
        vals = {"lnk-1": _make_valuation("lnk-1", "idea-a", measured_value_total=20.0)}
        commits = [_make_commit(["idea-a"]) for _ in range(5)]
        friction = [_make_friction_event("idea-a", cost_of_delay=5.0)]

        result = compute_idea_metrics(
            "idea-a", specs=specs, runtime_summaries=runtime,
            lineage_links=links, lineage_valuations=vals,
            commit_records=commits, friction_events=friction,
        )
        # Specs: 1.0 * 0.30 = 0.30
        # Runtime: min(1.0, 100/10) = 1.0 * 0.25 = 0.25
        # Lineage: 1.0 * 0.25 = 0.25
        # Commits: min(1.0, 5/5) = 1.0 * 0.10 = 0.10
        # Friction: 1.0 * 0.10 = 0.10
        # Total = 1.0, clamped to 0.95
        assert result["computed_confidence"] == 0.95

    def test_partial_data_gives_medium_confidence(self):
        """Specs + some runtime → moderate confidence."""
        specs = [_make_spec("s1", "idea-a", actual_cost=3.0)]
        runtime = [_make_runtime_summary("idea-a", event_count=5)]

        result = compute_idea_metrics("idea-a", specs=specs, runtime_summaries=runtime)
        # Specs: 1.0 * 0.30 = 0.30 (has actual data)
        # Runtime: min(1.0, 5/10) = 0.5 * 0.25 = 0.125
        # Lineage: 0.0 * 0.25 = 0.0
        # Commits: 0.0 * 0.10 = 0.0
        # Friction: 0.0 * 0.10 = 0.0
        # Total = 0.425
        assert result["computed_confidence"] == 0.425

    def test_specs_without_data_give_half_credit(self):
        """Specs exist but have zero actual_cost/value → 0.5 weight."""
        specs = [_make_spec("s1", "idea-a", estimated_cost=10.0)]  # No actual data
        result = compute_idea_metrics("idea-a", specs=specs)
        # Specs: 0.5 * 0.30 = 0.15
        assert result["computed_confidence"] == 0.15

    def test_lineage_without_value_gives_half_credit(self):
        """Lineage exists but no measured value → 0.5 weight."""
        links = [_make_lineage_link("lnk-1", "idea-a")]
        result = compute_idea_metrics("idea-a", lineage_links=links)
        # Lineage: 0.5 * 0.25 = 0.125
        assert result["computed_confidence"] == 0.125


# ===========================================================================
# TestValueRealization
# ===========================================================================

class TestValueRealization:
    """Test value_realization_pct = actual / potential."""

    def test_realization_from_spec_values(self):
        """actual_value / potential_value from specs."""
        specs = [_make_spec("s1", "idea-a", actual_value=30.0, potential_value=100.0)]
        links = [_make_lineage_link("lnk-1", "idea-a")]
        vals = {"lnk-1": _make_valuation("lnk-1", "idea-a", measured_value_total=30.0)}
        result = compute_idea_metrics(
            "idea-a", specs=specs, lineage_links=links, lineage_valuations=vals,
        )
        assert result["value_realization_pct"] == 0.3

    def test_realization_capped_at_one(self):
        """Cannot exceed 100% realization."""
        specs = [_make_spec("s1", "idea-a", actual_value=120.0, potential_value=100.0)]
        result = compute_idea_metrics("idea-a", specs=specs)
        assert result["value_realization_pct"] == 1.0

    def test_zero_potential_gives_zero_realization(self):
        """No potential_value → zero realization (avoid division by zero)."""
        result = compute_idea_metrics("idea-empty")
        assert result["value_realization_pct"] == 0.0


# ===========================================================================
# TestEstimatedCostComputation
# ===========================================================================

class TestEstimatedCostComputation:
    """Test that computed_estimated_cost uses the best available estimate."""

    def test_from_spec_estimated_costs(self):
        specs = [
            _make_spec("s1", "idea-a", estimated_cost=10.0),
            _make_spec("s2", "idea-a", estimated_cost=5.0),
        ]
        result = compute_idea_metrics("idea-a", specs=specs)
        assert result["computed_estimated_cost"] == 15.0

    def test_from_lineage_when_higher(self):
        """Lineage estimated cost wins when higher than spec sum."""
        specs = [_make_spec("s1", "idea-a", estimated_cost=5.0)]
        links = [_make_lineage_link("lnk-1", "idea-a", estimated_cost=20.0)]
        result = compute_idea_metrics("idea-a", specs=specs, lineage_links=links)
        assert result["computed_estimated_cost"] == 20.0


# ===========================================================================
# TestCommitCostEstimation
# ===========================================================================

class TestCommitCostEstimation:
    """Test the commit cost estimation helper."""

    def test_single_commit_formula(self):
        """Exact formula: BASE + files*0.15 + lines*0.002."""
        # 10 files, 200 lines → 0.10 + 10*0.15 + 200*0.002 = 0.10 + 1.50 + 0.40 = 2.00
        commits = [_make_commit(["x"], change_files=10, lines_added=200)]
        assert _estimate_commit_cost_sum(commits) == 2.0

    def test_cost_clamped_to_max(self):
        """Large commits capped at 10.0."""
        commits = [_make_commit(["x"], change_files=100, lines_added=10000)]
        # 0.10 + 100*0.15 + 10000*0.002 = 0.10 + 15.00 + 20.00 = 35.10 → capped to 10.0
        assert _estimate_commit_cost_sum(commits) == 10.0

    def test_zero_commit_gets_minimum(self):
        """Empty commit still gets minimum cost (0.05)."""
        commits = [_make_commit(["x"], change_files=0, lines_added=0)]
        # 0.10 + 0 + 0 = 0.10
        assert _estimate_commit_cost_sum(commits) == 0.10

    def test_multiple_commits_sum(self):
        """Multiple commits sum their individual costs."""
        commits = [
            _make_commit(["x"], change_files=2, lines_added=20),
            _make_commit(["x"], change_files=5, lines_added=100),
        ]
        # Commit 1: 0.10 + 2*0.15 + 20*0.002 = 0.10 + 0.30 + 0.04 = 0.44
        # Commit 2: 0.10 + 5*0.15 + 100*0.002 = 0.10 + 0.75 + 0.20 = 1.05
        assert _estimate_commit_cost_sum(commits) == 0.44 + 1.05


# ===========================================================================
# TestFilterHelpers
# ===========================================================================

class TestFilterHelpers:
    """Test that data filtering by idea_id is correct."""

    def test_filter_by_idea_id_dict(self):
        items = [{"idea_id": "a"}, {"idea_id": "b"}, {"idea_id": "a"}]
        assert len(_filter_by_idea_id(items, "a")) == 2

    def test_filter_commits_by_idea(self):
        commits = [
            {"idea_ids": ["a", "b"]},
            {"idea_ids": ["c"]},
            {"idea_ids": ["a"]},
        ]
        assert len(_filter_commits_by_idea(commits, "a")) == 2
        assert len(_filter_commits_by_idea(commits, "c")) == 1

    def test_filter_empty_list(self):
        assert _filter_by_idea_id([], "any") == []
        assert _filter_commits_by_idea([], "any") == []


# ===========================================================================
# TestBulkComputation
# ===========================================================================

class TestBulkComputation:
    """Test compute_all_idea_metrics processes multiple ideas."""

    def test_multiple_ideas(self):
        specs = [
            _make_spec("s1", "idea-a", actual_cost=5.0, actual_value=10.0),
            _make_spec("s2", "idea-b", actual_cost=3.0, actual_value=20.0),
        ]
        results = compute_all_idea_metrics(
            ["idea-a", "idea-b"], specs=specs
        )
        assert len(results) == 2
        assert results[0]["idea_id"] == "idea-a"
        assert results[0]["computed_actual_cost"] == 5.0
        assert results[0]["computed_actual_value"] == 10.0
        assert results[1]["idea_id"] == "idea-b"
        assert results[1]["computed_actual_cost"] == 3.0
        assert results[1]["computed_actual_value"] == 20.0


# ===========================================================================
# TestGroundingSourcesAudit
# ===========================================================================

class TestGroundingSourcesAudit:
    """Test that grounding_sources contains all expected keys."""

    def test_all_source_keys_present(self):
        result = compute_idea_metrics("idea-a")
        sources = result["grounding_sources"]
        expected_keys = {
            "spec_count", "spec_actual_cost_sum", "spec_actual_value_sum",
            "spec_estimated_cost_sum", "spec_potential_value_sum",
            "runtime_event_count", "runtime_cost_estimate", "usage_revenue_usd",
            "lineage_measured_value", "lineage_link_count", "lineage_event_count",
            "commit_count", "commit_cost_sum",
            "friction_cost_of_delay", "friction_event_count",
        }
        assert set(sources.keys()) == expected_keys

    def test_all_sources_are_numeric(self):
        """Every grounding source is a number, not None or string."""
        result = compute_idea_metrics("idea-a")
        for key, val in result["grounding_sources"].items():
            assert isinstance(val, (int, float)), f"{key} is {type(val)}, expected number"


# ===========================================================================
# TestServiceAPIContracts
# ===========================================================================

class TestServiceAPIContracts:
    """Verify upstream service methods exist with correct signatures."""

    def test_spec_registry_list_specs_exists(self):
        from app.services import spec_registry_service
        assert hasattr(spec_registry_service, "list_specs")
        sig = inspect.signature(spec_registry_service.list_specs)
        assert "limit" in sig.parameters

    def test_runtime_summarize_by_idea_exists(self):
        from app.services import runtime_service
        assert hasattr(runtime_service, "summarize_by_idea")
        sig = inspect.signature(runtime_service.summarize_by_idea)
        assert "seconds" in sig.parameters

    def test_value_lineage_list_links_exists(self):
        from app.services import value_lineage_service
        assert hasattr(value_lineage_service, "list_links")
        sig = inspect.signature(value_lineage_service.list_links)
        assert "limit" in sig.parameters

    def test_value_lineage_valuation_exists(self):
        from app.services import value_lineage_service
        assert hasattr(value_lineage_service, "valuation")
        sig = inspect.signature(value_lineage_service.valuation)
        assert "lineage_id" in sig.parameters

    def test_commit_evidence_list_records_exists(self):
        from app.services import commit_evidence_service
        assert hasattr(commit_evidence_service, "list_records")
        sig = inspect.signature(commit_evidence_service.list_records)
        assert "limit" in sig.parameters

    def test_telemetry_list_friction_events_exists(self):
        from app.services import telemetry_persistence_service
        assert hasattr(telemetry_persistence_service, "list_friction_events")
        sig = inspect.signature(telemetry_persistence_service.list_friction_events)
        assert "limit" in sig.parameters

    def test_collect_all_data_exists(self):
        """The I/O function exists and has the right signature."""
        assert callable(collect_all_data)
        sig = inspect.signature(collect_all_data)
        assert len(sig.parameters) == 0  # No arguments — self-contained
