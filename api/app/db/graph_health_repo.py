"""In-memory store for graph health snapshots, signals, guards, and ROI counters."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.graph_health import GraphHealthSnapshot, GraphSignal

_latest: GraphHealthSnapshot | None = None
_previous_balance: float | None = None
_convergence_guards: dict[str, dict] = {}
_signal_log: list[GraphSignal] = []
_split_actioned = 0
_merge_actioned = 0
_surface_actioned = 0


def get_snapshot() -> GraphHealthSnapshot | None:
    return _latest


def set_snapshot(snap: GraphHealthSnapshot) -> None:
    global _latest, _previous_balance
    if _latest is not None:
        _previous_balance = _latest.balance_score
    _latest = snap


def get_previous_balance() -> float | None:
    return _previous_balance


def upsert_signal(sig: GraphSignal) -> None:
    _signal_log.append(sig)
    global _split_actioned, _merge_actioned, _surface_actioned
    if sig.type == "split_signal" and sig.resolved:
        _split_actioned += 1
    elif sig.type == "merge_signal" and sig.resolved:
        _merge_actioned += 1
    elif sig.type == "surface_signal" and sig.resolved:
        _surface_actioned += 1


def set_guard(concept_id: str, reason: str, set_by: str) -> None:
    _convergence_guards[concept_id] = {
        "reason": reason,
        "set_by": set_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def remove_guard(concept_id: str) -> None:
    _convergence_guards.pop(concept_id, None)


def get_guard(concept_id: str) -> dict | None:
    return _convergence_guards.get(concept_id)


def list_guards() -> dict[str, dict]:
    return dict(_convergence_guards)


def roi_counts() -> tuple[int, int, int]:
    return _split_actioned, _merge_actioned, _surface_actioned


def reset_for_tests() -> None:
    global _latest, _previous_balance, _convergence_guards, _signal_log
    global _split_actioned, _merge_actioned, _surface_actioned
    _latest = None
    _previous_balance = None
    _convergence_guards = {}
    _signal_log = []
    _split_actioned = 0
    _merge_actioned = 0
    _surface_actioned = 0
