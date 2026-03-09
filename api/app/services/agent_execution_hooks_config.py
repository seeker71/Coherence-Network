"""Lifecycle hook configuration: env flags, subscribers, and paths."""

from __future__ import annotations

import os
from pathlib import Path


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _runtime_telemetry_enabled() -> bool:
    return _truthy(os.getenv("AGENT_LIFECYCLE_TELEMETRY_ENABLED", "1"))


def _jsonl_telemetry_enabled() -> bool:
    return _truthy(os.getenv("AGENT_LIFECYCLE_JSONL_ENABLED", "1"))


def jsonl_path() -> Path:
    configured = str(os.getenv("AGENT_LIFECYCLE_JSONL_PATH", "")).strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "agent_lifecycle_events.jsonl"


def jsonl_max_lines() -> int | None:
    raw = str(os.getenv("AGENT_LIFECYCLE_JSONL_MAX_LINES", "")).strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return min(parsed, 1_000_000)


def _parse_subscribers(raw: str | None) -> set[str]:
    value = str(raw or "").strip().lower()
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
    subscribers = _parse_subscribers(os.getenv("AGENT_LIFECYCLE_SUBSCRIBERS"))
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
