"""Load direction templates and role-wrapper lines from config. No prompt data in code."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.models.agent import TaskType

_CACHE: dict[str, Any] | None = None

_DIRECTION_SNIPPET_MAX = 2000


def _config_path() -> Path:
    env_value = os.environ.get("PROMPT_TEMPLATES_CONFIG_PATH", "").strip()
    if env_value:
        return Path(env_value)
    for base in [
        Path(__file__).resolve().parents[3] / "config" / "prompt_templates.json",
        Path(__file__).resolve().parents[2] / "config" / "prompt_templates.json",
    ]:
        if base.exists():
            return base
    return Path(__file__).resolve().parents[2] / "config" / "prompt_templates.json"


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    path = _config_path()
    if not path.exists():
        _CACHE = _empty_cache()
        return _CACHE
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        _CACHE = _empty_cache()
        return _CACHE
    if not isinstance(data, dict):
        _CACHE = _empty_cache()
        return _CACHE
    templates = data.get("direction_templates") if isinstance(data.get("direction_templates"), dict) else {}
    role_wrapper = data.get("role_wrapper") if isinstance(data.get("role_wrapper"), dict) else {}
    unblock = data.get("unblock_direction") if isinstance(data.get("unblock_direction"), dict) else {}
    cli_flow = data.get("cli_flow_directions") if isinstance(data.get("cli_flow_directions"), dict) else {}
    _CACHE = {
        "direction_templates": templates,
        "role_wrapper": role_wrapper,
        "unblock_direction": unblock,
        "idea_progress_direction": (data.get("idea_progress_direction") or "").strip(),
        "idea_progress_gap_hint": (data.get("idea_progress_gap_hint") or "").strip(),
        "spec_progress_direction": (data.get("spec_progress_direction") or "").strip(),
        "cli_flow_directions": cli_flow,
    }
    return _CACHE


def _empty_cache() -> dict[str, Any]:
    return {
        "direction_templates": {},
        "role_wrapper": {"common": [], "by_task_type": {}},
        "unblock_direction": {},
        "idea_progress_direction": "",
        "idea_progress_gap_hint": "",
        "spec_progress_direction": "",
        "cli_flow_directions": {},
    }


def reset_prompt_templates_cache() -> None:
    global _CACHE
    _CACHE = None


def get_direction_template(phase: str, *, iteration: int = 1) -> str:
    """Raw template string for phase. For impl with iteration > 1 use impl_iteration."""
    templates = _load().get("direction_templates") or {}
    if phase == "impl" and iteration > 1:
        return str(templates.get("impl_iteration") or "{item}").strip()
    return str(templates.get(phase) or templates.get("impl") or "{item}").strip()


def build_direction(phase: str, item: str, iteration: int = 1, last_output: str = "") -> str:
    """Build direction text from config. Placeholders: {item}, {iteration}, {last_output}. last_output capped for length."""
    template = get_direction_template(phase, iteration=iteration)
    snippet = (last_output or "").strip()[:_DIRECTION_SNIPPET_MAX]
    return template.format(
        item=item,
        iteration=iteration,
        last_output=snippet,
    )


def get_role_wrapper_common() -> list[str]:
    """Common lines applied to every task type (from config role_wrapper.common)."""
    rw = _load().get("role_wrapper") or {}
    common = rw.get("common")
    if isinstance(common, list):
        return [str(x).strip() for x in common if str(x).strip()]
    return []


def get_role_wrapper_for_task_type(task_type: TaskType) -> list[str]:
    """Task-type-specific contract lines (from config role_wrapper.by_task_type)."""
    rw = _load().get("role_wrapper") or {}
    by_type = rw.get("by_task_type") or {}
    if not isinstance(by_type, dict):
        return []
    key = task_type.value if hasattr(task_type, "value") else str(task_type)
    lines = by_type.get(key)
    if isinstance(lines, list):
        return [str(x).strip() for x in lines if str(x).strip()]
    return []


def build_direction_with_roles(
    direction: str,
    task_type: TaskType,
    primary_agent: str | None = None,
    guard_agents: list[str] | None = None,
) -> str:
    """Build full direction: optional role/guard lines, task type, common + by_task_type lines from config, then Direction: <direction>."""
    lines: list[str] = []
    if primary_agent:
        lines.append(f"Role agent: {primary_agent}.")
    if guard_agents:
        lines.append(f"Guard agents: {', '.join(guard_agents)}.")
    lines.append(f"Task type: {task_type.value}.")
    lines.extend(get_role_wrapper_common())
    lines.extend(get_role_wrapper_for_task_type(task_type))
    lines.append(f"Direction: {direction}")
    return " ".join(lines)


def get_unblock_direction(
    blocking_stage: str,
    idea_id: str,
    idea_name: str,
    blocked_text: str,
    spec_hint: str = "",
) -> str:
    """Build unblock direction from config (unblock_direction by blocking_stage)."""
    data = _load().get("unblock_direction") or {}
    template = str(data.get(blocking_stage) or data.get("validation") or "{idea_id}").strip()
    return template.format(
        idea_id=idea_id,
        idea_name=idea_name,
        blocked_text=blocked_text,
        spec_hint=spec_hint or "linked spec",
    )


def get_idea_progress_direction(idea_id: str, idea_name: str, has_linked_spec: bool) -> str:
    """Build idea progress direction from config."""
    data = _load()
    template = str(data.get("idea_progress_direction") or "").strip()
    gap_hint = str(data.get("idea_progress_gap_hint") or "") if not has_linked_spec else ""
    if not template:
        return f"Advance high-ROI idea '{idea_id}' ({idea_name})."
    return template.format(idea_id=idea_id, idea_name=idea_name, gap_hint=gap_hint).replace(" .", ".")


def get_spec_progress_direction(
    spec_id: str,
    title: str,
    chunk_index: int,
    chunk_total: int,
    chunk_label: str,
    chunk_goal: str,
) -> str:
    """Build spec progress direction from config."""
    data = _load()
    template = str(data.get("spec_progress_direction") or "").strip()
    if not template:
        return f"Advance high-ROI spec '{spec_id}' ({title}) part {chunk_index}/{chunk_total}."
    return template.format(
        spec_id=spec_id,
        title=title,
        chunk_index=chunk_index,
        chunk_total=chunk_total,
        chunk_label=chunk_label,
        chunk_goal=chunk_goal,
    )


def get_cli_flow_direction(
    stage: str,
    spec_path: str,
    impl_path: str,
    verify_path: str,
    review_output: str = "",
) -> str:
    """Build CLI flow matrix direction from config (cli_flow_directions). review_output clipped by caller if needed."""
    data = _load().get("cli_flow_directions") or {}
    template = str(data.get(stage) or "").strip()
    if not template:
        return f"Spec: {spec_path}, Impl: {impl_path}, Verify: {verify_path}"
    return template.format(
        spec_path=spec_path,
        impl_path=impl_path,
        verify_path=verify_path,
        review_output=review_output,
    )
