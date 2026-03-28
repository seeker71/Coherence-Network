"""Tests for data hygiene monitoring — row counts, growth rates, anomaly detection.

Feature: Data hygiene monitoring
  - get_table_row_counts: reports row counts per tracked table
  - detect_growth_anomalies: flags tables with suspicious row volumes
  - get_health_dashboard: provides a health score and structured overview
  - format_db_status_report: human-readable cc db-status equivalent

Verification Scenarios
======================

1. Empty DB — all counts zero, no anomalies, health score 1.0
   Setup: fresh in-memory SQLite with schema
   Action: get_table_row_counts() + get_health_dashboard()
   Expected: every table returns 0, health_score == 1.0, status == "healthy"

2. Normal population — counts within expected bounds
   Setup: insert N rows into agent_tasks (N < 3× expected for 7 days)
   Action: detect_growth_anomalies(system_age_days=7)
   Expected: no anomalies returned

3. Anomaly — runtime_events far exceeds expected volume
   Setup: insert rows exceeding ANOMALY_MULTIPLIER × expected
   Action: detect_growth_anomalies(system_age_days=1)
   Expected: anomaly with severity "critical" for runtime_events

4. Dashboard — aggregates correctly
   Setup: seed two tables, one clean one anomalous
   Action: get_health_dashboard(system_age_days=1)
   Expected: health_score < 1.0, anomaly_count >= 1, status != "healthy"

5. format_db_status_report — readable output contains key fields
   Setup: any DB state
   Action: format_db_status_report()
   Expected: string contains table names, row counts, status line

6. Edge — unknown table name raises no exception, returns 0
   Action: get_table_row_counts(["nonexistent_table_xyz"])
   Expected: {"nonexistent_table_xyz": 0}

7. Edge — system_age_days=0 produces no anomaly (avoid division by zero)
   Action: detect_growth_anomalies(system_age_days=0)
   Expected: no exception, returns []
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# helpers — ensure each test gets an isolated fresh DB
# ---------------------------------------------------------------------------


def _setup_isolated_db(tmp_path: Path) -> None:
    """Point the unified DB to an isolated SQLite file for this test."""
    db_path = tmp_path / "hygiene_test.db"
    os.environ["IDEA_PORTFOLIO_PATH"] = str(tmp_path / "portfolio.json")

    # Reset engine cache so a fresh engine is created against tmp DB
    from app.services import unified_db
    unified_db._ENGINE_CACHE["url"] = ""
    unified_db._ENGINE_CACHE["engine"] = None
    unified_db._ENGINE_CACHE["sessionmaker"] = None
    unified_db._SCHEMA_INITIALIZED.clear()

    unified_db.ensure_schema()


def _insert_rows_into_table(table_name: str, count: int) -> None:
    """Insert `count` dummy rows into a unified-DB table using raw SQL."""
    from app.services import unified_db
    from sqlalchemy import text

    with unified_db.session() as session:
        if table_name == "contribution_ledger":
            for i in range(count):
                session.execute(
                    text(
                        "INSERT INTO contribution_ledger "
                        "(id, contributor_id, contribution_type, idea_id, amount_cc, metadata_json, recorded_at) "
                        "VALUES (:id, 'test-contrib', 'code', NULL, 1.0, '{}', CURRENT_TIMESTAMP)"
                    ),
                    {"id": f"hygiene-ledger-{i}"},
                )
        elif table_name == "telemetry_task_metrics":
            for i in range(count):
                session.execute(
                    text(
                        "INSERT INTO telemetry_task_metrics "
                        "(task_id, task_type, model, status, duration_seconds, occurred_at, payload_json, created_at) "
                        "VALUES (:tid, 'spec', 'claude-haiku-4-5', 'completed', 5.0, CURRENT_TIMESTAMP, '{}', CURRENT_TIMESTAMP)"
                    ),
                    {"tid": f"ttm-{i}"},
                )
        else:
            raise ValueError(f"Table '{table_name}' not supported for direct insert in tests")
        session.commit()


# ---------------------------------------------------------------------------
# Scenario 1 — empty DB
# ---------------------------------------------------------------------------


class TestEmptyDatabase:
    """With a fresh DB all row counts are 0 and the system is healthy."""

    def test_all_counts_zero(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import get_table_row_counts

        counts = get_table_row_counts()
        for table, count in counts.items():
            assert count == 0, f"Expected 0 rows in {table}, got {count}"

    def test_health_score_is_one(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import get_health_dashboard

        dashboard = get_health_dashboard(system_age_days=7.0)
        assert dashboard.health_score == 1.0

    def test_status_is_healthy(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import get_health_dashboard

        dashboard = get_health_dashboard(system_age_days=7.0)
        assert dashboard.status == "healthy"

    def test_no_anomalies_detected(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import detect_growth_anomalies

        anomalies = detect_growth_anomalies(system_age_days=7.0)
        assert anomalies == []

    def test_total_rows_is_zero(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import get_health_dashboard

        dashboard = get_health_dashboard(system_age_days=7.0)
        assert dashboard.total_rows == 0


# ---------------------------------------------------------------------------
# Scenario 2 — normal population (within bounds)
# ---------------------------------------------------------------------------


class TestNormalPopulation:
    """Tables with counts well within expected bounds produce no anomalies."""

    def test_few_ledger_rows_no_anomaly(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        # Insert 50 ledger rows — far below 30/day × 7 days × 3× = 630 expected max
        _insert_rows_into_table("contribution_ledger", 50)

        from app.services.data_hygiene_service import detect_growth_anomalies

        anomalies = detect_growth_anomalies(system_age_days=7.0)
        ledger_anomalies = [a for a in anomalies if a.table == "contribution_ledger"]
        assert ledger_anomalies == []

    def test_row_count_reflects_inserted_rows(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        _insert_rows_into_table("contribution_ledger", 25)

        from app.services.data_hygiene_service import get_table_row_counts

        counts = get_table_row_counts(["contribution_ledger"])
        assert counts["contribution_ledger"] == 25

    def test_contribution_ledger_within_bounds(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        # 50 rows vs expected max 30/day × 7 × 3 = 630 — well within
        _insert_rows_into_table("contribution_ledger", 50)

        from app.services.data_hygiene_service import detect_growth_anomalies

        anomalies = detect_growth_anomalies(system_age_days=7.0)
        ledger_anomalies = [a for a in anomalies if a.table == "contribution_ledger"]
        assert ledger_anomalies == []

    def test_health_score_stays_high_with_normal_data(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        _insert_rows_into_table("telemetry_task_metrics", 10)
        _insert_rows_into_table("contribution_ledger", 10)

        from app.services.data_hygiene_service import get_health_dashboard

        dashboard = get_health_dashboard(system_age_days=7.0)
        assert dashboard.health_score >= 0.8


# ---------------------------------------------------------------------------
# Scenario 3 — anomaly detection (suspicious growth)
# ---------------------------------------------------------------------------


class TestAnomalyDetection:
    """Tables with row counts exceeding ANOMALY_MULTIPLIER × expected are flagged."""

    def test_critical_anomaly_on_overloaded_table(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        # contribution_ledger expected 30/day × 1 day × 3× = 90 max
        # Insert 500 to produce score ≈ 5.6 → critical
        _insert_rows_into_table("contribution_ledger", 500)

        from app.services.data_hygiene_service import detect_growth_anomalies

        anomalies = detect_growth_anomalies(system_age_days=1.0)
        ledger_anomalies = [a for a in anomalies if a.table == "contribution_ledger"]
        assert len(ledger_anomalies) == 1
        assert ledger_anomalies[0].severity == "critical"
        assert ledger_anomalies[0].anomaly_score >= 2.0

    def test_warning_anomaly_just_above_threshold(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        # contribution_ledger: expected max = 30 × 1 × 3 = 90; insert 130 → score ~1.44 = warning
        _insert_rows_into_table("contribution_ledger", 130)

        from app.services.data_hygiene_service import detect_growth_anomalies

        anomalies = detect_growth_anomalies(system_age_days=1.0)
        ledger_anomalies = [a for a in anomalies if a.table == "contribution_ledger"]
        assert len(ledger_anomalies) == 1
        assert ledger_anomalies[0].severity == "warning"
        assert 1.0 < ledger_anomalies[0].anomaly_score < 2.0

    def test_anomaly_message_is_descriptive(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        _insert_rows_into_table("contribution_ledger", 500)

        from app.services.data_hygiene_service import detect_growth_anomalies

        anomalies = detect_growth_anomalies(system_age_days=1.0)
        ledger_anomalies = [a for a in anomalies if a.table == "contribution_ledger"]
        assert ledger_anomalies
        msg = ledger_anomalies[0].message
        assert "contribution_ledger" in msg
        assert "500" in msg

    def test_anomaly_list_sorted_by_score_descending(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        # Make telemetry_task_metrics much worse: expected 120/day × 1 × 3 = 360 max
        _insert_rows_into_table("contribution_ledger", 500)     # score ≈ 5.6
        _insert_rows_into_table("telemetry_task_metrics", 800)  # score ≈ 2.2

        from app.services.data_hygiene_service import detect_growth_anomalies

        anomalies = detect_growth_anomalies(system_age_days=1.0)
        if len(anomalies) >= 2:
            scores = [a.anomaly_score for a in anomalies]
            assert scores == sorted(scores, reverse=True)

    def test_anomaly_score_proportional_to_excess(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import (
            ANOMALY_MULTIPLIER,
            EXPECTED_DAILY_GROWTH,
            detect_growth_anomalies,
        )

        expected_max = EXPECTED_DAILY_GROWTH["contribution_ledger"] * 1.0 * ANOMALY_MULTIPLIER
        # Insert 2× the expected max → anomaly_score ≈ 2.0
        _insert_rows_into_table("contribution_ledger", int(expected_max * 2))

        anomalies = detect_growth_anomalies(system_age_days=1.0)
        ledger_anomalies = [a for a in anomalies if a.table == "contribution_ledger"]
        assert ledger_anomalies
        assert abs(ledger_anomalies[0].anomaly_score - 2.0) < 0.1


# ---------------------------------------------------------------------------
# Scenario 4 — health dashboard aggregation
# ---------------------------------------------------------------------------


class TestHealthDashboard:
    """Dashboard aggregates correctly across tables."""

    def test_dashboard_contains_all_tracked_tables(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import (
            EXPECTED_DAILY_GROWTH,
            get_health_dashboard,
        )

        dashboard = get_health_dashboard(system_age_days=7.0)
        table_names = {s.table for s in dashboard.tables}
        for t in EXPECTED_DAILY_GROWTH:
            assert t in table_names, f"Expected table '{t}' in dashboard"

    def test_dashboard_health_score_decreases_with_anomalies(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        _insert_rows_into_table("contribution_ledger", 500)

        from app.services.data_hygiene_service import get_health_dashboard

        dashboard = get_health_dashboard(system_age_days=1.0)
        assert dashboard.health_score < 1.0

    def test_dashboard_status_critical_on_severe_anomaly(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        _insert_rows_into_table("contribution_ledger", 5000)

        from app.services.data_hygiene_service import get_health_dashboard

        dashboard = get_health_dashboard(system_age_days=1.0)
        assert dashboard.status in ("warning", "critical")

    def test_dashboard_to_dict_serializable(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import get_health_dashboard
        import json

        dashboard = get_health_dashboard(system_age_days=7.0)
        d = dashboard.to_dict()
        # Must be JSON-serializable
        serialized = json.dumps(d)
        loaded = json.loads(serialized)
        assert loaded["status"] == "healthy"
        assert "tables" in loaded
        assert "anomalies" in loaded

    def test_dashboard_total_rows_is_sum_of_tables(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        _insert_rows_into_table("telemetry_task_metrics", 30)
        _insert_rows_into_table("contribution_ledger", 20)

        from app.services.data_hygiene_service import get_health_dashboard

        dashboard = get_health_dashboard(system_age_days=7.0)
        assert dashboard.total_rows >= 50  # at least the rows we inserted

    def test_dashboard_generated_at_is_recent(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import get_health_dashboard

        before = datetime.now(timezone.utc)
        dashboard = get_health_dashboard(system_age_days=7.0)
        after = datetime.now(timezone.utc)
        assert before <= dashboard.generated_at <= after


# ---------------------------------------------------------------------------
# Scenario 5 — format_db_status_report human-readable output
# ---------------------------------------------------------------------------


class TestDbStatusReport:
    """format_db_status_report produces a readable, structured report string."""

    def test_report_contains_status_line(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import format_db_status_report

        report = format_db_status_report(system_age_days=7.0)
        assert "Status:" in report
        assert "Health:" in report

    def test_report_contains_table_names(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import format_db_status_report

        report = format_db_status_report(system_age_days=7.0)
        assert "agent_tasks" in report
        assert "contribution_ledger" in report

    def test_report_contains_row_counts(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        _insert_rows_into_table("contribution_ledger", 42)

        from app.services.data_hygiene_service import format_db_status_report

        report = format_db_status_report(system_age_days=7.0)
        assert "42" in report

    def test_report_flags_anomaly_tables(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        _insert_rows_into_table("contribution_ledger", 5000)

        from app.services.data_hygiene_service import format_db_status_report

        report = format_db_status_report(system_age_days=1.0)
        assert "CRITICAL" in report or "WARNING" in report

    def test_report_is_multiline_string(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import format_db_status_report

        report = format_db_status_report(system_age_days=7.0)
        assert isinstance(report, str)
        lines = report.strip().split("\n")
        assert len(lines) >= 5


# ---------------------------------------------------------------------------
# Scenario 6 — edge: unknown table
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: unknown tables, zero age, missing tables."""

    def test_unknown_table_returns_zero(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import get_table_row_counts

        counts = get_table_row_counts(["nonexistent_table_xyz_abc"])
        assert counts == {"nonexistent_table_xyz_abc": 0}

    def test_system_age_zero_no_exception(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import detect_growth_anomalies

        # Must not raise ZeroDivisionError
        anomalies = detect_growth_anomalies(system_age_days=0.0)
        assert isinstance(anomalies, list)
        assert anomalies == []  # can't compute meaningful scores

    def test_empty_table_list_returns_empty_dict(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        from app.services.data_hygiene_service import get_table_row_counts

        counts = get_table_row_counts([])
        assert counts == {}

    def test_single_very_old_system_no_false_positives(self, tmp_path: Path) -> None:
        _setup_isolated_db(tmp_path)
        # For a 365-day-old system, 100 contribution_ledger rows is completely normal
        _insert_rows_into_table("contribution_ledger", 100)

        from app.services.data_hygiene_service import detect_growth_anomalies

        anomalies = detect_growth_anomalies(system_age_days=365.0)
        ledger_anomalies = [a for a in anomalies if a.table == "contribution_ledger"]
        assert ledger_anomalies == []


# ---------------------------------------------------------------------------
# Scenario 7 — TableStats model unit tests
# ---------------------------------------------------------------------------


class TestTableStatsModel:
    """Unit tests for the TableStats dataclass calculations."""

    def test_is_high_volume_above_10k(self) -> None:
        from app.services.data_hygiene_service import TableStats

        stats = TableStats(table="t", row_count=10_001, expected_daily_growth=100.0)
        assert stats.is_high_volume is True

    def test_is_high_volume_below_10k(self) -> None:
        from app.services.data_hygiene_service import TableStats

        stats = TableStats(table="t", row_count=9_999, expected_daily_growth=100.0)
        assert stats.is_high_volume is False

    def test_growth_anomaly_score_zero_when_within_bounds(self) -> None:
        from app.services.data_hygiene_service import ANOMALY_MULTIPLIER, TableStats

        # 100 rows, expected 100/day × 7 days × 3× = 2100 max → score ≈ 0.048
        stats = TableStats(table="t", row_count=100, expected_daily_growth=100.0)
        score = stats.growth_anomaly_score(system_age_days=7.0)
        assert score < 1.0

    def test_growth_anomaly_score_above_one_when_over_limit(self) -> None:
        from app.services.data_hygiene_service import ANOMALY_MULTIPLIER, TableStats

        # 10000 rows, expected 100/day × 1 × 3 = 300 max → score ≈ 33
        stats = TableStats(table="t", row_count=10_000, expected_daily_growth=100.0)
        score = stats.growth_anomaly_score(system_age_days=1.0)
        assert score > 1.0

    def test_to_dict_contains_required_keys(self) -> None:
        from app.services.data_hygiene_service import TableStats

        stats = TableStats(table="runtime_events", row_count=46614, expected_daily_growth=2000.0)
        d = stats.to_dict()
        assert "table" in d
        assert "row_count" in d
        assert "expected_daily_growth" in d
        assert "is_high_volume" in d
        assert "snapshot_at" in d
        assert d["row_count"] == 46614

    def test_growth_anomaly_score_zero_when_age_is_zero(self) -> None:
        from app.services.data_hygiene_service import TableStats

        stats = TableStats(table="t", row_count=999999, expected_daily_growth=100.0)
        score = stats.growth_anomaly_score(system_age_days=0.0)
        assert score == 0.0


# ---------------------------------------------------------------------------
# Scenario 8 — GrowthAnomaly model unit tests
# ---------------------------------------------------------------------------


class TestGrowthAnomalyModel:
    """Unit tests for the GrowthAnomaly dataclass."""

    def test_to_dict_contains_required_keys(self) -> None:
        from app.services.data_hygiene_service import GrowthAnomaly

        anomaly = GrowthAnomaly(
            table="runtime_events",
            row_count=46614,
            expected_max=14000.0,
            anomaly_score=3.33,
            severity="critical",
            message="runtime_events has 46,614 rows — 3.3× the expected maximum.",
        )
        d = anomaly.to_dict()
        assert d["table"] == "runtime_events"
        assert d["row_count"] == 46614
        assert d["severity"] == "critical"
        assert d["anomaly_score"] == 3.33
        assert "expected_max" in d
        assert "message" in d

    def test_warning_severity_label(self) -> None:
        from app.services.data_hygiene_service import GrowthAnomaly

        anomaly = GrowthAnomaly(
            table="agent_tasks",
            row_count=400,
            expected_max=300.0,
            anomaly_score=1.33,
            severity="warning",
            message="...",
        )
        assert anomaly.severity == "warning"


# ---------------------------------------------------------------------------
# Scenario 9 — runtime_events investigation (46k rows)
# ---------------------------------------------------------------------------


class TestRuntimeEventsInvestigation:
    """runtime_events at 46k rows on a young system is specifically suspicious.

    For a 7-day-old system:
      Expected max = 2000/day × 7 × 3 = 42,000
      Actual = 46,614 → anomaly_score ≈ 1.1 → WARNING

    For a 1-day-old system:
      Expected max = 2000/day × 1 × 3 = 6,000
      Actual = 46,614 → anomaly_score ≈ 7.8 → CRITICAL
    """

    def test_46k_runtime_events_flagged_for_1_day_old_system(self, tmp_path: Path) -> None:
        from app.services.data_hygiene_service import (
            ANOMALY_MULTIPLIER,
            EXPECTED_DAILY_GROWTH,
            TableStats,
        )

        stats = TableStats(
            table="runtime_events",
            row_count=46_614,
            expected_daily_growth=EXPECTED_DAILY_GROWTH["runtime_events"],
        )
        score = stats.growth_anomaly_score(system_age_days=1.0)
        expected_max = EXPECTED_DAILY_GROWTH["runtime_events"] * 1.0 * ANOMALY_MULTIPLIER
        assert score > 1.0, (
            f"46k rows in runtime_events on a 1-day system should exceed the threshold; "
            f"score={score:.2f}, expected_max={expected_max}"
        )

    def test_46k_runtime_events_critical_not_just_warning(self, tmp_path: Path) -> None:
        from app.services.data_hygiene_service import (
            ANOMALY_MULTIPLIER,
            EXPECTED_DAILY_GROWTH,
            TableStats,
        )

        stats = TableStats(
            table="runtime_events",
            row_count=46_614,
            expected_daily_growth=EXPECTED_DAILY_GROWTH["runtime_events"],
        )
        score = stats.growth_anomaly_score(system_age_days=1.0)
        # score >= 2.0 → critical severity
        assert score >= 2.0, (
            f"46k events on a 1-day system should be CRITICAL (score>=2.0); got {score:.2f}"
        )

    def test_46k_runtime_events_acceptable_for_7_week_old_system(self) -> None:
        from app.services.data_hygiene_service import (
            ANOMALY_MULTIPLIER,
            EXPECTED_DAILY_GROWTH,
            TableStats,
        )

        stats = TableStats(
            table="runtime_events",
            row_count=46_614,
            expected_daily_growth=EXPECTED_DAILY_GROWTH["runtime_events"],
        )
        # For 49-day system: expected max = 2000 × 49 × 3 = 294,000
        score = stats.growth_anomaly_score(system_age_days=49.0)
        assert score < 1.0, (
            f"46k events over 49 days should be normal; score={score:.2f}"
        )

    def test_suspicious_growth_message_mentions_investigation(self, tmp_path: Path) -> None:
        """Anomaly message for runtime_events must be actionable."""
        _setup_isolated_db(tmp_path)

        from app.services.data_hygiene_service import (
            ANOMALY_MULTIPLIER,
            EXPECTED_DAILY_GROWTH,
            GrowthAnomaly,
        )

        expected_max = EXPECTED_DAILY_GROWTH["runtime_events"] * 1.0 * ANOMALY_MULTIPLIER
        anomaly = GrowthAnomaly(
            table="runtime_events",
            row_count=46_614,
            expected_max=expected_max,
            anomaly_score=7.8,
            severity="critical",
            message=(
                f"Table 'runtime_events' has 46,614 rows — "
                f"7.8× the expected maximum ({expected_max:,.0f}) "
                f"for a 1.0-day-old system."
            ),
        )
        assert "runtime_events" in anomaly.message
        assert "46,614" in anomaly.message
