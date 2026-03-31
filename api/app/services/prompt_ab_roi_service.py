"""Backward-compatible wrapper around SlotSelector for prompt variant selection.

All new code should use SlotSelector directly. This module exists so existing
callers (grounded_measurement_service, tests, etc.) don't break.
"""
from __future__ import annotations

from pathlib import Path

from app.services.slot_selection_service import SlotSelector


def _selector(task_type: str, store_path: Path | None = None) -> SlotSelector:
    # When store_path is overridden, multiple task_types may share one file,
    # so we need task_type_filter to scope measurements
    return SlotSelector(
        task_type,
        store_path=store_path,
        task_type_filter=task_type if store_path else None,
    )


def record_prompt_outcome(
    variant_id: str,
    task_type: str,
    value_score: float,
    resource_cost: float,
    *,
    config_version: str = "",
    store_path: Path | None = None,
    task_id: str | None = None,
    raw_signals: dict | None = None,
) -> dict:
    """Record a prompt outcome. Delegates to SlotSelector.

    Returns a dict with both slot_id and variant_id keys for backward compatibility.
    """
    result = _selector(task_type, store_path).record(
        variant_id,
        value_score,
        resource_cost,
        config_version=config_version,
        task_id=task_id,
        raw_signals=raw_signals,
    )
    # Backward compat: existing callers expect variant_id and task_type keys
    result["variant_id"] = result.get("slot_id", variant_id)
    result["task_type"] = task_type
    return result


def get_variant_stats(
    store_path: Path | None = None,
    task_type: str | None = None,
    version_map: dict[str, str] | None = None,
) -> dict:
    """Get per-variant stats. Delegates to SlotSelector."""
    # When task_type is None, don't filter — read all measurements
    selector = SlotSelector(
        task_type or "default",
        store_path=store_path,
        task_type_filter=task_type if (store_path and task_type) else None,
    )
    st = selector.stats(version_map=version_map)
    # Remap keys for backward compatibility
    return {
        "variants": st.get("slots", {}),
        "total_measurements": st.get("total_measurements", 0),
        "active_variants": st.get("active_slots", 0),
        "blocked_variants": st.get("blocked_slots", 0),
    }


def select_variant(
    task_type: str,
    available_variants: list[str],
    *,
    store_path: Path | None = None,
    version_map: dict[str, str] | None = None,
) -> str | None:
    """Select a variant. Delegates to SlotSelector."""
    return _selector(task_type, store_path).select(
        available_variants, version_map=version_map
    )
