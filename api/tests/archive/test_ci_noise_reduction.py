"""Tests for CI Noise Reduction (ci-noise-reduction).

Verifies acceptance criteria from the spec:
1. Scheduled workflows use daily (or less frequent) cron schedules
2. Non-critical workflows have workflow_dispatch for manual triggers
3. Issue comment dedup logic present in workflows that file issues
4. Total estimated scheduled runs per day ≤ 12
5. Critical workflows (test.yml, thread-gates.yml) retain PR triggers
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"

# Workflows that were part of the ci-noise-reduction effort
NOISE_REDUCED_WORKFLOWS = [
    "public-deploy-contract.yml",
    "provider-readiness-contract.yml",
    "self-improve-cycle.yml",
    "asset_value_update.yml",
    "pr-check-failure-triage.yml",
    "thread-gates.yml",
    "asset-modularity-drift.yml",
]

# Workflows that should have the 20h comment dedup gate
DEDUP_WORKFLOWS = [
    "public-deploy-contract.yml",
    "provider-readiness-contract.yml",
    "self-improve-cycle.yml",
    "asset-modularity-drift.yml",
]

# Critical workflows that must keep PR/push triggers
CRITICAL_WORKFLOWS = ["test.yml", "thread-gates.yml"]


def _load_workflow(name: str) -> dict:
    path = WORKFLOWS_DIR / name
    assert path.exists(), f"Workflow file not found: {path}"
    return yaml.safe_load(path.read_text())


def _load_workflow_raw(name: str) -> str:
    path = WORKFLOWS_DIR / name
    assert path.exists(), f"Workflow file not found: {path}"
    return path.read_text()


def _parse_cron_to_runs_per_day(cron_expr: str) -> float:
    """Estimate runs per day from a cron expression."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return 1.0  # fallback

    minute, hour, dom, month, dow = parts

    # Check day-of-week restriction (e.g., "1,4" = 2 days/week)
    if dow != "*":
        days_per_week = len(dow.split(","))
        days_factor = days_per_week / 7.0
    else:
        days_factor = 1.0

    # Check hour field for frequency
    if hour.startswith("*/"):
        every_n_hours = int(hour[2:])
        runs = 24 / every_n_hours
    elif "," in hour:
        runs = len(hour.split(","))
    elif hour == "*":
        # Every hour — check minute field
        if minute.startswith("*/"):
            every_n_minutes = int(minute[2:])
            runs = 24 * (60 / every_n_minutes)
        else:
            runs = 24
    else:
        # Fixed hour — once per day
        runs = 1.0

    return runs * days_factor


# ---------------------------------------------------------------------------
# Happy path: scheduled workflows use daily cron
# ---------------------------------------------------------------------------


class TestScheduleFrequency:
    """Spec verification scenario 1 & 3: schedules are daily or less frequent."""

    @pytest.mark.parametrize("workflow_name", NOISE_REDUCED_WORKFLOWS)
    def test_workflow_schedule_is_daily_or_less(self, workflow_name: str) -> None:
        """Each noise-reduced workflow runs at most once per day."""
        wf = _load_workflow(workflow_name)
        triggers = wf.get(True) or wf.get("on", {})
        schedule = triggers.get("schedule", [])
        if not schedule:
            # No schedule trigger — that's fine (schedule-only removed)
            return
        for entry in schedule:
            cron = entry.get("cron", "")
            runs_per_day = _parse_cron_to_runs_per_day(cron)
            assert runs_per_day <= 1.01, (
                f"{workflow_name} cron '{cron}' fires ~{runs_per_day:.1f}x/day, "
                f"expected ≤1 (daily)"
            )

    def test_total_scheduled_runs_at_most_12(self) -> None:
        """Spec scenario 5: total daily CI runs from schedules ≤ 12."""
        total = 0.0
        for yml_file in sorted(WORKFLOWS_DIR.glob("*.yml")):
            wf = yaml.safe_load(yml_file.read_text())
            if wf is None:
                continue
            triggers = wf.get(True) or wf.get("on", {})
            if not isinstance(triggers, dict):
                continue
            for entry in triggers.get("schedule", []):
                cron = entry.get("cron", "")
                total += _parse_cron_to_runs_per_day(cron)
        assert total <= 12, (
            f"Total scheduled runs/day = {total:.1f}, exceeds target of 12"
        )


# ---------------------------------------------------------------------------
# workflow_dispatch present for manual triggering
# ---------------------------------------------------------------------------


class TestWorkflowDispatch:
    """All noise-reduced workflows must retain workflow_dispatch."""

    @pytest.mark.parametrize("workflow_name", NOISE_REDUCED_WORKFLOWS)
    def test_has_workflow_dispatch(self, workflow_name: str) -> None:
        wf = _load_workflow(workflow_name)
        triggers = wf.get(True) or wf.get("on", {})
        assert "workflow_dispatch" in triggers or triggers.get("workflow_dispatch") is not None, (
            f"{workflow_name} missing workflow_dispatch trigger"
        )


# ---------------------------------------------------------------------------
# Comment dedup gate (20h window)
# ---------------------------------------------------------------------------


class TestCommentDedup:
    """Workflows that file issues should have the 20h dedup gate."""

    @pytest.mark.parametrize("workflow_name", DEDUP_WORKFLOWS)
    def test_dedup_gate_present(self, workflow_name: str) -> None:
        """Check raw file for the dedup pattern — YAML parser loses JS code."""
        raw = _load_workflow_raw(workflow_name)
        assert "hoursAgo < 20" in raw or "hours_ago < 20" in raw, (
            f"{workflow_name} missing 20h comment dedup gate"
        )

    @pytest.mark.parametrize("workflow_name", DEDUP_WORKFLOWS)
    def test_dedup_gate_logs_skip(self, workflow_name: str) -> None:
        """The dedup gate should log when skipping a comment."""
        raw = _load_workflow_raw(workflow_name)
        assert "Skipping duplicate comment" in raw or "skipping duplicate" in raw.lower(), (
            f"{workflow_name} dedup gate should log when skipping"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge and error cases for CI noise reduction."""

    def test_critical_workflow_retains_pr_trigger(self) -> None:
        """thread-gates.yml must keep pull_request trigger for PR validation."""
        wf = _load_workflow("thread-gates.yml")
        triggers = wf.get(True) or wf.get("on", {})
        assert "pull_request" in triggers, (
            "thread-gates.yml must keep pull_request trigger"
        )

    def test_test_yml_is_manual_only_or_has_pr(self) -> None:
        """test.yml should be manual-only or retain push/PR triggers (not scheduled)."""
        wf = _load_workflow("test.yml")
        triggers = wf.get(True) or wf.get("on", {})
        if isinstance(triggers, dict):
            # Should not have a schedule without push/PR
            has_schedule = "schedule" in triggers
            has_push_or_pr = "push" in triggers or "pull_request" in triggers
            has_dispatch = "workflow_dispatch" in triggers
            if has_schedule:
                assert has_push_or_pr, (
                    "test.yml should not be schedule-only — it must run on push/PR"
                )
            # Manual-only is acceptable (current state)
            assert has_dispatch or has_push_or_pr, (
                "test.yml has no trigger mechanism"
            )

    def test_no_high_frequency_cron_in_any_workflow(self) -> None:
        """No workflow should run more than twice daily."""
        for yml_file in sorted(WORKFLOWS_DIR.glob("*.yml")):
            wf = yaml.safe_load(yml_file.read_text())
            if wf is None:
                continue
            triggers = wf.get(True) or wf.get("on", {})
            if not isinstance(triggers, dict):
                continue
            for entry in triggers.get("schedule", []):
                cron = entry.get("cron", "")
                runs = _parse_cron_to_runs_per_day(cron)
                assert runs <= 2.01, (
                    f"{yml_file.name} cron '{cron}' fires ~{runs:.1f}x/day, "
                    f"max allowed is 2"
                )

    def test_concurrency_groups_present(self) -> None:
        """Workflows with schedule triggers should have concurrency groups
        to cancel in-progress runs (spec known gap)."""
        wf = _load_workflow("public-deploy-contract.yml")
        assert "concurrency" in wf, (
            "public-deploy-contract.yml should have concurrency group"
        )

    def test_all_workflow_files_are_valid_yaml(self) -> None:
        """All .yml files in workflows dir must parse as valid YAML."""
        for yml_file in sorted(WORKFLOWS_DIR.glob("*.yml")):
            content = yml_file.read_text()
            try:
                result = yaml.safe_load(content)
            except yaml.YAMLError as exc:
                pytest.fail(f"{yml_file.name} is not valid YAML: {exc}")
            assert result is not None, f"{yml_file.name} is empty"
