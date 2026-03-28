"""Persistence for normalized Open Responses call evidence (route + model + schema)."""

from __future__ import annotations

from typing import Any

# In-process store for operator audits and tests; no DB migration required for MVP.
_normalized_evidence_rows: list[dict[str, Any]] = []


def record_normalized_open_responses_evidence(row: dict[str, Any]) -> None:
    """Append one normalized call record (route + model + request_schema + output snippet)."""
    if not row:
        return
    _normalized_evidence_rows.append(dict(row))


def list_normalized_open_responses_evidence(*, limit: int = 500) -> list[dict[str, Any]]:
    """Return recent evidence rows (oldest first within the tail window)."""
    cap = max(1, min(int(limit), 5000))
    return list(_normalized_evidence_rows[-cap:])


def clear_normalized_open_responses_evidence() -> None:
    """Test helper: reset the in-memory evidence log."""
    _normalized_evidence_rows.clear()
