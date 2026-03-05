from __future__ import annotations

import json

from app.services import orchestrator_policy_service


def test_policy_defaults_load_with_expected_shape(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_ORCHESTRATION_POLICY_PATH", raising=False)
    orchestrator_policy_service.reset_orchestrator_policy_cache()

    policy = orchestrator_policy_service.get_orchestrator_policy()
    assert isinstance(policy, dict)
    assert "ab" in policy
    assert "executors" in policy
    assert "prompt_variants" in policy
    assert orchestrator_policy_service.prompt_variant_control() == "baseline_v1"


def test_policy_can_be_overridden_via_json(monkeypatch, tmp_path) -> None:
    override = {
        "prompt_variants": {
            "control": "baseline_v3",
            "by_task_type": {"impl": "impl_variant_x"},
        },
        "ab": {
            "target_challenger_pct": {"initial": 55, "high_control_share": 60, "mid_control_share": 50, "base": 40},
            "control_share_thresholds": {"high": 0.8, "mid": 0.5},
        },
        "executors": {
            "ab_candidate_priority": ["gemini", "codex", "claude"],
            "forced_challenger_priority": ["cursor", "codex"],
        },
    }
    path = tmp_path / "orchestrator_policy_override.json"
    path.write_text(json.dumps(override), encoding="utf-8")

    monkeypatch.setenv("AGENT_ORCHESTRATION_POLICY_PATH", str(path))
    orchestrator_policy_service.reset_orchestrator_policy_cache()

    assert orchestrator_policy_service.prompt_variant_control() == "baseline_v3"
    assert orchestrator_policy_service.prompt_variant_for_task("impl") == "impl_variant_x"
    assert orchestrator_policy_service.ab_candidate_executor_priority() == ("gemini", "codex", "claude")
    assert orchestrator_policy_service.forced_challenger_executor_priority() == ("cursor", "codex")

    # total_observed=0 uses initial target
    assert orchestrator_policy_service.target_challenger_pct(total_observed=0, control_count=0) == 55


def test_policy_invalid_entries_are_safely_normalized(monkeypatch, tmp_path) -> None:
    override = {
        "executors": {
            "ab_candidate_priority": ["bad", "", "codex", "codex"],
        },
        "ab": {
            "regression_min_samples": -100,
            "regression_margin": "not-a-float",
            "control_share_thresholds": {"high": 0.4, "mid": 0.9},
        },
    }
    path = tmp_path / "orchestrator_policy_invalid.json"
    path.write_text(json.dumps(override), encoding="utf-8")

    monkeypatch.setenv("AGENT_ORCHESTRATION_POLICY_PATH", str(path))
    orchestrator_policy_service.reset_orchestrator_policy_cache()

    policy = orchestrator_policy_service.get_orchestrator_policy()
    assert policy["executors"]["ab_candidate_priority"] == ["codex"]
    assert policy["ab"]["regression_min_samples"] == 1
    # mid gets clamped to high when misconfigured
    assert policy["ab"]["control_share_thresholds"]["mid"] == policy["ab"]["control_share_thresholds"]["high"]
