"""Shared state and helpers for the agent pipeline loop (spec 139)."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.idea import IdeaStage

DEFAULT_POLL_INTERVAL = int(os.getenv("PIPELINE_POLL_INTERVAL", "60"))
DEFAULT_CONCURRENCY = max(1, int(os.getenv("PIPELINE_CONCURRENCY", "1")))
RETRY_BACKOFF_SECONDS = (2, 8, 32)
STATE_FILE = Path(__file__).resolve().parents[2] / "logs" / "agent_pipeline_state.json"
LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "agent_pipeline.log"

_STAGE_TO_TASK_TYPE: dict[str, str] = {
    IdeaStage.NONE.value: "spec",
    IdeaStage.SPECCED.value: "impl",
    IdeaStage.IMPLEMENTING.value: "test",
    IdeaStage.TESTING.value: "review",
    IdeaStage.REVIEWING.value: "review",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return ts.isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


@dataclass
class PipelineState:
    running: bool = False
    started_at: datetime | None = None
    current_idea_id: str | None = None
    cycle_count: int = 0
    ideas_advanced: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_cycle_at: datetime | None = None
    needs_attention_ideas: set[str] = field(default_factory=set)

    def snapshot(self) -> dict[str, Any]:
        now = _utc_now()
        uptime = 0
        if self.running and self.started_at is not None:
            uptime = max(0, int((now - self.started_at).total_seconds()))
        return {
            "running": self.running,
            "uptime_seconds": uptime,
            "current_idea_id": self.current_idea_id,
            "cycle_count": self.cycle_count,
            "ideas_advanced": self.ideas_advanced,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "last_cycle_at": _iso(self.last_cycle_at),
        }

    def to_persisted(self) -> dict[str, Any]:
        payload = self.snapshot()
        payload["started_at"] = _iso(self.started_at)
        payload["needs_attention_ideas"] = sorted(self.needs_attention_ideas)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PipelineState":
        state = cls()
        state.running = bool(payload.get("running", False))
        state.started_at = _parse_iso(payload.get("started_at"))
        state.current_idea_id = payload.get("current_idea_id")
        state.cycle_count = int(payload.get("cycle_count", 0))
        state.ideas_advanced = int(payload.get("ideas_advanced", 0))
        state.tasks_completed = int(payload.get("tasks_completed", 0))
        state.tasks_failed = int(payload.get("tasks_failed", 0))
        state.last_cycle_at = _parse_iso(payload.get("last_cycle_at"))
        raw_attention = payload.get("needs_attention_ideas") or []
        state.needs_attention_ideas = {str(item) for item in raw_attention if str(item).strip()}
        return state


_LOCK = threading.Lock()
_STATE = PipelineState()


def start() -> None:
    with _LOCK:
        _STATE.running = True
        _STATE.started_at = _utc_now()
        _STATE.current_idea_id = None


def stop() -> None:
    with _LOCK:
        _STATE.running = False
        _STATE.current_idea_id = None


def set_current_idea(idea_id: str | None) -> None:
    with _LOCK:
        _STATE.current_idea_id = idea_id


def mark_cycle() -> None:
    with _LOCK:
        _STATE.cycle_count += 1
        _STATE.last_cycle_at = _utc_now()


def mark_task_completed() -> None:
    with _LOCK:
        _STATE.tasks_completed += 1


def mark_task_failed() -> None:
    with _LOCK:
        _STATE.tasks_failed += 1


def mark_idea_advanced() -> None:
    with _LOCK:
        _STATE.ideas_advanced += 1


def mark_needs_attention(idea_id: str) -> None:
    with _LOCK:
        _STATE.needs_attention_ideas.add(idea_id)


def is_needs_attention(idea_id: str) -> bool:
    with _LOCK:
        return idea_id in _STATE.needs_attention_ideas


def reset_for_tests() -> None:
    with _LOCK:
        global _STATE
        _STATE = PipelineState()


def _compute_phase_stats() -> dict[str, Any]:
    """Aggregate per-phase completion stats for Spec 159 (code-review → deploy → verify)."""
    try:
        from app.services import agent_service
    except Exception:
        return {}

    try:
        all_tasks, _total, _backfill = agent_service.list_tasks(limit=2000, offset=0)
    except Exception:
        return {}

    phase_keys = ("code-review", "deploy", "verify-production")
    buckets: dict[str, dict[str, Any]] = {
        k: {"completed": 0, "failed": 0, "retry_sum": 0, "retry_n": 0} for k in phase_keys
    }

    def _phase_for(tt: str) -> str | None:
        if tt == "code-review":
            return "code-review"
        if tt == "deploy":
            return "deploy"
        if tt in ("verify", "verify-production"):
            return "verify-production"
        return None

    for t in all_tasks:
        raw = t.get("task_type", "")
        if hasattr(raw, "value"):
            raw = raw.value
        phase = _phase_for(str(raw))
        if not phase:
            continue
        st = t.get("status", "")
        if hasattr(st, "value"):
            st = st.value
        st = str(st)
        if st == "completed":
            buckets[phase]["completed"] += 1
        elif st in ("failed", "timed_out", "needs_decision"):
            buckets[phase]["failed"] += 1
        ctx = t.get("context") or {}
        try:
            rc = int(ctx.get("retry_count", 0))
        except (TypeError, ValueError):
            rc = 0
        if rc > 0:
            buckets[phase]["retry_sum"] += rc
            buckets[phase]["retry_n"] += 1

    out: dict[str, Any] = {}
    for phase, b in buckets.items():
        done = int(b["completed"])
        failed = int(b["failed"])
        total = done + failed
        pass_rate = round(done / total, 4) if total else None
        avg_retries = (
            round(b["retry_sum"] / b["retry_n"], 4) if b["retry_n"] else 0.0
        )
        out[phase] = {
            "completed": done,
            "failed": failed,
            "pass_rate": pass_rate,
            "avg_retries": avg_retries,
        }
    return out


def get_status() -> dict[str, Any]:
    with _LOCK:
        snap = _STATE.snapshot()
    snap["phase_stats"] = _compute_phase_stats()
    return snap


def persist_state(path: Path | None = None) -> None:
    target = path or STATE_FILE
    with _LOCK:
        payload = _STATE.to_persisted()
    _atomic_write_json(target, payload)


def load_state(path: Path | None = None) -> None:
    target = path or STATE_FILE
    if not target.exists():
        return
    try:
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    with _LOCK:
        global _STATE
        _STATE = PipelineState.from_payload(payload)


def append_cycle_log(entry: dict[str, Any], path: Path | None = None) -> None:
    target = path or LOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True))
        handle.write("\n")


def task_type_for_stage(stage: str) -> str | None:
    return _STAGE_TO_TASK_TYPE.get(str(stage or "").strip().lower())


def roi_score(idea: dict[str, Any]) -> float:
    coherence = idea.get("coherence_score")
    if coherence is None:
        coherence = idea.get("free_energy_score", 0.0)
    urgency = idea.get("urgency_weight")
    if urgency is None:
        urgency = 1.0
    try:
        return float(coherence) * float(urgency)
    except (TypeError, ValueError):
        return 0.0


def rank_candidate_ideas(ideas: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    actionable = [idea for idea in ideas if str(idea.get("stage", "")).lower() != IdeaStage.COMPLETE.value]
    ranked = sorted(actionable, key=roi_score, reverse=True)
    return ranked[: max(1, int(top_n))]
