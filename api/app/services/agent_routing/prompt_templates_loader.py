"""Load direction templates and role-wrapper lines from config. No prompt data in code.

Prompt variant slots (a, b, c):
  - Each slot is a config file: prompt_templates.json, prompt_templates_b.json, prompt_templates_c.json
  - Selection via Thompson Sampling — no implicit default, data determines ranking
  - Each config has a "version" field; measurements from a stale version are ignored
  - To test a new candidate: replace the weakest slot's config file (bump version)
  - Override: PROMPT_VARIANT=a|b|c environment variable
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from pathlib import Path
from typing import Any

from app.models.agent import TaskType

logger = logging.getLogger(__name__)

_CACHE: dict[str, dict[str, Any]] = {}  # keyed by variant_id

_DIRECTION_SNIPPET_MAX = 2000

_VARIANT_SLOTS = ["a", "b", "c"]


def _config_path(variant: str = "a") -> Path:
    env_value = os.environ.get("PROMPT_TEMPLATES_CONFIG_PATH", "").strip()
    if env_value and variant == "a":
        return Path(env_value)

    suffix = "" if variant == "a" else f"_{variant}"
    filename = f"prompt_templates{suffix}.json"

    for base_dir in [
        Path(__file__).resolve().parents[3] / "config",
        Path(__file__).resolve().parents[2] / "config",
    ]:
        candidate = base_dir / filename
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parents[2] / "config" / filename


def _config_version(variant: str) -> str:
    """Read the version field from a variant's config file. Returns '' if missing."""
    path = _config_path(variant)
    if not path.exists():
        return ""
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("version", ""))
    except (OSError, json.JSONDecodeError):
        return ""


def _active_variant() -> str:
    """Determine which prompt variant to use. Order: env override → Thompson Sampling → uniform random.

    There is no implicit default — selection always comes from the probability curve.
    """
    env_variant = os.environ.get("PROMPT_VARIANT", "").strip().lower()
    if env_variant in _VARIANT_SLOTS:
        return env_variant

    available = [v for v in _VARIANT_SLOTS if _config_path(v).exists()]
    if not available:
        return "a"  # no config files at all — nothing to sample

    if len(available) == 1:
        return available[0]  # only one variant exists

    # Build version map so TS can filter stale measurements
    version_map = {v: _config_version(v) for v in available}

    # Thompson Sampling across all available slots (lazy import to avoid circular deps)
    try:
        from app.services.slot_selection_service import SlotSelector
        selector = SlotSelector("prompt_template")
        selected = selector.select(available, version_map=version_map)
        if selected:
            return selected
    except Exception:
        logger.warning("Thompson Sampling failed, falling back to uniform random", exc_info=True)

    # All variants blocked or TS error — uniform random, never a hardcoded default
    return random.choice(available)


def _load(variant: str | None = None) -> dict[str, Any]:
    """Load config for a variant. If variant is None, Thompson Sampling picks fresh each call."""
    vid = variant or _active_variant()
    if vid in _CACHE:
        # Config data is cached, but variant *selection* happens fresh each call
        return _CACHE[vid]

    path = _config_path(vid)
    if not path.exists():
        # Fall back to variant a
        if vid != "a":
            logger.warning("Prompt variant '%s' not found at %s, falling back to 'a'", vid, path)
            return _load("a")
        _CACHE[vid] = _empty_cache(vid)
        return _CACHE[vid]
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        _CACHE[vid] = _empty_cache(vid)
        return _CACHE[vid]
    if not isinstance(data, dict):
        _CACHE[vid] = _empty_cache(vid)
        return _CACHE[vid]
    templates = data.get("direction_templates") if isinstance(data.get("direction_templates"), dict) else {}
    role_wrapper = data.get("role_wrapper") if isinstance(data.get("role_wrapper"), dict) else {}
    unblock = data.get("unblock_direction") if isinstance(data.get("unblock_direction"), dict) else {}
    cli_flow = data.get("cli_flow_directions") if isinstance(data.get("cli_flow_directions"), dict) else {}
    task_card_defaults = data.get("task_card_defaults") if isinstance(data.get("task_card_defaults"), dict) else {}
    task_card_path_templates = (
        data.get("task_card_path_templates") if isinstance(data.get("task_card_path_templates"), dict) else {}
    )
    _CACHE[vid] = {
        "variant_id": vid,
        "config_version": str(data.get("version", "")),
        "direction_templates": templates,
        "role_wrapper": role_wrapper,
        "unblock_direction": unblock,
        "idea_progress_direction": (data.get("idea_progress_direction") or "").strip(),
        "idea_progress_gap_hint": (data.get("idea_progress_gap_hint") or "").strip(),
        "spec_progress_direction": (data.get("spec_progress_direction") or "").strip(),
        "cli_flow_directions": cli_flow,
        "task_card_defaults": task_card_defaults,
        "task_card_path_templates": task_card_path_templates,
    }
    return _CACHE[vid]


def _empty_cache(variant_id: str = "a") -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "config_version": "",
        "direction_templates": {},
        "role_wrapper": {"common": [], "by_task_type": {}},
        "unblock_direction": {},
        "idea_progress_direction": "",
        "idea_progress_gap_hint": "",
        "spec_progress_direction": "",
        "cli_flow_directions": {},
        "task_card_defaults": {},
        "task_card_path_templates": {},
    }


def reset_prompt_templates_cache() -> None:
    global _CACHE
    _CACHE = {}


def get_active_variant_id() -> str:
    """Return the variant ID currently in use (for measurement recording)."""
    data = _load()
    return data.get("variant_id", "a")


def get_active_variant_version() -> str:
    """Return the config version of the active variant (for measurement recording)."""
    data = _load()
    return data.get("config_version", "")


def weakest_slot() -> str | None:
    """Return the slot with the worst Thompson Sampling performance, or None if <2 slots exist.

    Use this to decide which slot to replace when introducing a new candidate.
    """
    available = [v for v in _VARIANT_SLOTS if _config_path(v).exists()]
    if len(available) < 2:
        # Only 0-1 slots occupied — return first empty slot instead
        for s in _VARIANT_SLOTS:
            if s not in available:
                return s
        return None

    version_map = {v: _config_version(v) for v in available}

    try:
        from app.services.slot_selection_service import SlotSelector
        selector = SlotSelector("prompt_template")
        return selector.weakest_slot(available, _VARIANT_SLOTS, version_map=version_map)
    except Exception:
        # No data — return last available slot
        return available[-1]


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


def _task_type_key(task_type: TaskType | str) -> str:
    return task_type.value if hasattr(task_type, "value") else str(task_type)


def _compact_text(value: Any, *, max_chars: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def _safe_slug(value: Any, *, fallback: str = "task") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug[:80].strip("-") or fallback


def _format_config_value(value: Any, tokens: dict[str, str]) -> Any:
    if isinstance(value, str):
        return value.format_map(tokens)
    if isinstance(value, list):
        return [_format_config_value(item, tokens) for item in value]
    if isinstance(value, dict):
        return {str(k): _format_config_value(v, tokens) for k, v in value.items()}
    return value


def build_default_task_card_context(
    task_type: TaskType,
    direction: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Fill missing task-card fields from prompt config while preserving caller-provided values."""
    ctx = dict(context or {})
    card = dict(ctx.get("task_card") or {}) if isinstance(ctx.get("task_card"), dict) else {}
    key = _task_type_key(task_type)
    data = _load()
    defaults_by_type = data.get("task_card_defaults") if isinstance(data.get("task_card_defaults"), dict) else {}
    defaults = defaults_by_type.get(key)
    if not isinstance(defaults, dict):
        return ctx

    direction_summary = _compact_text(direction)
    idea_id = str(ctx.get("idea_id") or "").strip()
    spec_id = str(ctx.get("spec_id") or "").strip()
    slug_seed = idea_id or spec_id or direction_summary
    spec_slug = _safe_slug(slug_seed)
    path_templates = data.get("task_card_path_templates") if isinstance(data.get("task_card_path_templates"), dict) else {}
    spec_path = str(ctx.get("spec_path") or ctx.get("spec_file") or "").strip()
    if not spec_path:
        path_template = str(path_templates.get(key) or "").strip()
        if path_template:
            spec_path = path_template.format_map({"spec_slug": spec_slug})

    tokens = {
        "task_type": key,
        "direction_summary": direction_summary,
        "idea_id": idea_id,
        "idea_name": str(ctx.get("idea_name") or "").strip(),
        "spec_id": spec_id,
        "spec_title": str(ctx.get("spec_title") or "").strip(),
        "spec_slug": spec_slug,
        "spec_path": spec_path,
    }
    for field, value in defaults.items():
        if field in ctx and ctx.get(field):
            continue
        if field in card and card.get(field):
            continue
        formatted = _format_config_value(value, tokens)
        card[field] = formatted
        if field == "files_allowed":
            ctx[field] = formatted

    if card:
        ctx["task_card"] = card
        ctx.setdefault("task_card_autofill", {"source": "prompt_templates", "version": data.get("config_version", "")})
    return ctx


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
