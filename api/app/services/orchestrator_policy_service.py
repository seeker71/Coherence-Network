"""Data-driven orchestrator policy configuration."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_POLICY: dict[str, Any] = {
    "version": "default",
    "executors": {
        "ab_candidate_priority": ["claude", "cursor", "gemini", "openrouter"],
        "forced_challenger_priority": ["claude", "cursor", "gemini", "openrouter"],
    },
    "prompt_variants": {
        "control": "baseline_v1",
        "by_task_type": {
            "spec": "spec_structure_v2",
            "test": "verification_focus_v2",
            "impl": "patch_preservation_v2",
            "review": "verification_focus_v2",
            "heal": "patch_preservation_v2",
        },
    },
    "ab": {
        "regression_cooldown_seconds": 4 * 60 * 60,
        "regression_min_samples": 3,
        "regression_margin": 0.15,
        "target_challenger_pct": {
            "initial": 30,
            "high_control_share": 45,
            "mid_control_share": 35,
            "base": 20,
        },
        "control_share_thresholds": {
            "high": 0.7,
            "mid": 0.55,
        },
    },
}
_VALID_EXECUTORS = {"claude", "codex", "cursor", "gemini", "openrouter"}


def _policy_path() -> Path:
    env_value = str(os.getenv("AGENT_ORCHESTRATION_POLICY_PATH", "")).strip()
    if env_value:
        return Path(env_value)

    repo_level = Path(__file__).resolve().parents[3] / "config" / "orchestrator_policy.json"
    if repo_level.exists():
        return repo_level

    api_level = Path(__file__).resolve().parents[2] / "config" / "orchestrator_policy.json"
    if api_level.exists():
        return api_level

    return repo_level


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


def _to_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _to_float(value: Any, default: float, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _normalize_executor_priority(raw: Any, fallback: list[str]) -> list[str]:
    if not isinstance(raw, list):
        return list(fallback)
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in raw:
        candidate = str(value or "").strip().lower()
        if not candidate or candidate in seen or candidate not in _VALID_EXECUTORS:
            continue
        seen.add(candidate)
        cleaned.append(candidate)
    return cleaned or list(fallback)


def _normalize_prompt_variants(raw: Any, fallback: dict[str, str]) -> dict[str, str]:
    if not isinstance(raw, dict):
        return dict(fallback)
    merged = dict(fallback)
    for key, value in raw.items():
        normalized_key = str(key or "").strip().lower()
        normalized_value = str(value or "").strip().lower()
        if not normalized_key or not normalized_value:
            continue
        merged[normalized_key] = normalized_value
    return merged


def _load_raw_policy() -> dict[str, Any]:
    path = _policy_path()
    if not path.exists():
        return dict(_DEFAULT_POLICY)
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULT_POLICY)
    if not isinstance(payload, dict):
        return dict(_DEFAULT_POLICY)
    return _deep_merge(_DEFAULT_POLICY, payload)


def _normalize_policy(raw: dict[str, Any]) -> dict[str, Any]:
    executors = raw.get("executors") if isinstance(raw.get("executors"), dict) else {}
    prompt_variants = raw.get("prompt_variants") if isinstance(raw.get("prompt_variants"), dict) else {}
    ab = raw.get("ab") if isinstance(raw.get("ab"), dict) else {}

    default_executors = _DEFAULT_POLICY["executors"]
    default_prompt = _DEFAULT_POLICY["prompt_variants"]
    default_ab = _DEFAULT_POLICY["ab"]

    by_task = prompt_variants.get("by_task_type") if isinstance(prompt_variants.get("by_task_type"), dict) else {}
    target_pct = ab.get("target_challenger_pct") if isinstance(ab.get("target_challenger_pct"), dict) else {}
    thresholds = ab.get("control_share_thresholds") if isinstance(ab.get("control_share_thresholds"), dict) else {}

    normalized = {
        "version": str(raw.get("version") or "default").strip() or "default",
        "executors": {
            "ab_candidate_priority": _normalize_executor_priority(
                executors.get("ab_candidate_priority"),
                list(default_executors["ab_candidate_priority"]),
            ),
            "forced_challenger_priority": _normalize_executor_priority(
                executors.get("forced_challenger_priority"),
                list(default_executors["forced_challenger_priority"]),
            ),
        },
        "prompt_variants": {
            "control": str(prompt_variants.get("control") or default_prompt["control"]).strip().lower()
            or default_prompt["control"],
            "by_task_type": _normalize_prompt_variants(by_task, dict(default_prompt["by_task_type"])),
        },
        "ab": {
            "regression_cooldown_seconds": _to_int(
                ab.get("regression_cooldown_seconds"),
                int(default_ab["regression_cooldown_seconds"]),
                minimum=60,
                maximum=7 * 24 * 60 * 60,
            ),
            "regression_min_samples": _to_int(
                ab.get("regression_min_samples"),
                int(default_ab["regression_min_samples"]),
                minimum=1,
                maximum=100,
            ),
            "regression_margin": _to_float(
                ab.get("regression_margin"),
                float(default_ab["regression_margin"]),
                minimum=0.0,
                maximum=1.0,
            ),
            "target_challenger_pct": {
                "initial": _to_int(target_pct.get("initial"), int(default_ab["target_challenger_pct"]["initial"]), minimum=0, maximum=100),
                "high_control_share": _to_int(
                    target_pct.get("high_control_share"),
                    int(default_ab["target_challenger_pct"]["high_control_share"]),
                    minimum=0,
                    maximum=100,
                ),
                "mid_control_share": _to_int(
                    target_pct.get("mid_control_share"),
                    int(default_ab["target_challenger_pct"]["mid_control_share"]),
                    minimum=0,
                    maximum=100,
                ),
                "base": _to_int(target_pct.get("base"), int(default_ab["target_challenger_pct"]["base"]), minimum=0, maximum=100),
            },
            "control_share_thresholds": {
                "high": _to_float(
                    thresholds.get("high"),
                    float(default_ab["control_share_thresholds"]["high"]),
                    minimum=0.0,
                    maximum=1.0,
                ),
                "mid": _to_float(
                    thresholds.get("mid"),
                    float(default_ab["control_share_thresholds"]["mid"]),
                    minimum=0.0,
                    maximum=1.0,
                ),
            },
        },
    }

    high = float(normalized["ab"]["control_share_thresholds"]["high"])
    mid = float(normalized["ab"]["control_share_thresholds"]["mid"])
    if mid > high:
        normalized["ab"]["control_share_thresholds"]["mid"] = high
    return normalized


@lru_cache(maxsize=1)
def get_orchestrator_policy() -> dict[str, Any]:
    return _normalize_policy(_load_raw_policy())


def reset_orchestrator_policy_cache() -> None:
    get_orchestrator_policy.cache_clear()


def prompt_variant_control() -> str:
    policy = get_orchestrator_policy()
    prompt = policy.get("prompt_variants") if isinstance(policy.get("prompt_variants"), dict) else {}
    return str(prompt.get("control") or "baseline_v1").strip().lower() or "baseline_v1"


def prompt_variant_for_task(task_type_value: str, default: str = "execution_focus_v2") -> str:
    policy = get_orchestrator_policy()
    prompt = policy.get("prompt_variants") if isinstance(policy.get("prompt_variants"), dict) else {}
    by_task = prompt.get("by_task_type") if isinstance(prompt.get("by_task_type"), dict) else {}
    key = str(task_type_value or "").strip().lower()
    variant = str(by_task.get(key) or default).strip().lower()
    return variant or default


def ab_candidate_executor_priority() -> tuple[str, ...]:
    policy = get_orchestrator_policy()
    executors = policy.get("executors") if isinstance(policy.get("executors"), dict) else {}
    raw = executors.get("ab_candidate_priority") if isinstance(executors.get("ab_candidate_priority"), list) else []
    return tuple(str(value) for value in raw if str(value).strip())


def forced_challenger_executor_priority() -> tuple[str, ...]:
    policy = get_orchestrator_policy()
    executors = policy.get("executors") if isinstance(policy.get("executors"), dict) else {}
    raw = executors.get("forced_challenger_priority") if isinstance(executors.get("forced_challenger_priority"), list) else []
    return tuple(str(value) for value in raw if str(value).strip())


def regression_policy() -> dict[str, Any]:
    policy = get_orchestrator_policy()
    ab = policy.get("ab") if isinstance(policy.get("ab"), dict) else {}
    return {
        "cooldown_seconds": int(ab.get("regression_cooldown_seconds") or 4 * 60 * 60),
        "min_samples": int(ab.get("regression_min_samples") or 3),
        "margin": float(ab.get("regression_margin") or 0.15),
    }


def target_challenger_pct(total_observed: int, control_count: int) -> int:
    policy = get_orchestrator_policy()
    ab = policy.get("ab") if isinstance(policy.get("ab"), dict) else {}
    target = ab.get("target_challenger_pct") if isinstance(ab.get("target_challenger_pct"), dict) else {}
    thresholds = ab.get("control_share_thresholds") if isinstance(ab.get("control_share_thresholds"), dict) else {}

    if total_observed <= 0:
        return int(target.get("initial") or 30)

    control_share = float(control_count) / float(total_observed)
    high_threshold = float(thresholds.get("high") or 0.7)
    mid_threshold = float(thresholds.get("mid") or 0.55)
    if control_share >= high_threshold:
        return int(target.get("high_control_share") or 45)
    if control_share >= mid_threshold:
        return int(target.get("mid_control_share") or 35)
    return int(target.get("base") or 20)
