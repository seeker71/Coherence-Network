"""Shared run-state lease tracking for agent workers.

Thin facade: implementation lives in app.services.agent_run_state.
Re-exports public API and _repo_root for backward compatibility (e.g. tests patching _repo_root).
"""

from app.services.agent_run_state import (
    _repo_root,
    claim_run_state,
    get_run_state,
    heartbeat_run_state,
    update_run_state,
)

__all__ = [
    "claim_run_state",
    "get_run_state",
    "heartbeat_run_state",
    "update_run_state",
    "_repo_root",
]
