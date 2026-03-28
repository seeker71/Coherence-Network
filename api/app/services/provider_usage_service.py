"""Provider usage service: persist normalized request schema and route evidence (spec 109).

Stores a log of NormalizedResponseCall records in-memory so that operator audits
can verify the actual execution path (provider, model, schema) for each task
without requiring a schema migration.
"""

from __future__ import annotations

from typing import Any

from app.models.schemas import NormalizedResponseCall

# In-memory call log — persists for the lifetime of the process.
# No DB migration required; suitable for MVP audit queries.
_call_log: list[dict[str, Any]] = []


def record_normalized_call(call: NormalizedResponseCall) -> None:
    """Append a normalized call record to the in-memory log."""
    _call_log.append(call.model_dump())


def get_call_log() -> list[dict[str, Any]]:
    """Return a copy of all recorded normalized call entries."""
    return list(_call_log)


def get_call_log_for_task(task_id: str) -> list[dict[str, Any]]:
    """Return all normalized call entries for a specific task_id."""
    return [entry for entry in _call_log if entry.get("task_id") == task_id]


def clear_call_log() -> None:
    """Clear the in-memory log (primarily for test isolation)."""
    _call_log.clear()
