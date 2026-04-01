"""Lifecycle hook configuration: config flags, subscribers, and paths."""

from __future__ import annotations

from pathlib import Path

from app.config_loader import get_bool, get_int, get_list, get_str


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _runtime_telemetry_enabled() -> bool:
    return get_bool("agent_lifecycle", "telemetry_enabled", default=True)


def _jsonl_telemetry_enabled() -> bool:
    return get_bool("agent_lifecycle", "jsonl_enabled", default=True)


def jsonl_path() -> Path:
    configured = get_str("agent_lifecycle", "jsonl_path", default="")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "agent_lifecycle_events.jsonl"


def jsonl_max_lines() -> int | None:
    raw = get_int("agent_lifecycle", "jsonl_max_lines", default=None)
    if raw is None or raw <= 0:
        return None
    return min(raw, 1_000_000)


def _parse_subscribers(value: str | None) -> set[str]:
    value = str(value or "").strip().lower()
    if not value:
        return {"runtime"}

    tokens = {piece.strip().lower() for piece in value.split(",") if piece.strip()}
    if not tokens:
        return {"runtime"}
    if "all" in tokens:
        return {"runtime", "jsonl"}
    if tokens.intersection({"none", "off", "0", "false"}):
        return set()

    allowed = {"runtime", "jsonl", "audit"}
    return {token for token in tokens if token in allowed}


def enabled_subscribers() -> dict[str, bool]:
    subscribers_str = get_str("agent_lifecycle", "subscribers", default="runtime")
    subscribers = _parse_subscribers(subscribers_str)
    jsonl_enabled = ("jsonl" in subscribers or "audit" in subscribers) and _jsonl_telemetry_enabled()
    return {
        "runtime": ("runtime" in subscribers) and _runtime_telemetry_enabled(),
        "jsonl": jsonl_enabled,
    }


def runtime_subscriber_enabled() -> bool:
    return bool(enabled_subscribers().get("runtime"))


def jsonl_subscriber_enabled() -> bool:
    return bool(enabled_subscribers().get("jsonl"))


def event_status_code(task_status: str | None) -> int:
    status = str(task_status or "").strip().lower()
    if status == "failed":
        return 500
    return 200
