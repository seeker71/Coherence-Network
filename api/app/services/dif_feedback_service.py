"""DIF feedback instrumentation — tracks verification results for accuracy analysis.

Every DIF verification during task execution is recorded so we can measure:
- True positives: DIF flagged concern → agent fixed → production works
- False positives: DIF flagged concern → fix was unnecessary (code was fine)
- True negatives: DIF said clear → code is indeed good
- False negatives: DIF said clear → code had issues found later

Data flows to the API for dashboard visibility and feeds back to DIF improvement.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# In-memory buffer — flushed to API periodically
_FEEDBACK_BUFFER: list[dict[str, Any]] = []
_FEEDBACK_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "dif_feedback.jsonl"


def record_verification(
    *,
    task_id: str,
    task_type: str,
    file_path: str,
    language: str,
    dif_result: dict[str, Any],
    agent_action: str = "pending",  # pending | fixed | ignored | no_finding
    idea_id: str = "",
    provider: str = "",
) -> dict[str, Any]:
    """Record a single DIF verification result.

    agent_action:
        pending   — DIF ran but we don't know yet if agent acted on it
        fixed     — agent fixed the issue DIF found
        ignored   — agent saw the finding but didn't change code
        no_finding — DIF found no concerns (clear/positive)
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "task_type": task_type,
        "idea_id": idea_id,
        "provider": provider,
        "file_path": file_path,
        "language": language,
        "dif_stream": dif_result.get("stream", "?"),
        "dif_verdict": dif_result.get("verdict", "?"),
        "dif_trust": dif_result.get("trust_signal", "?"),
        "dif_verification": dif_result.get("scores", {}).get("verification"),
        "dif_semantic_support": dif_result.get("scores", {}).get("semantic_support"),
        "dif_model_support": dif_result.get("scores", {}).get("model_support"),
        "dif_complexity": dif_result.get("scores", {}).get("statement_complexity"),
        "dif_structural_cost": dif_result.get("scores", {}).get("structural_cost"),
        "dif_tags": dif_result.get("tags", []),
        "dif_top_finding_kind": (dif_result.get("top_finding") or {}).get("kind"),
        "dif_top_finding_excerpt": (dif_result.get("top_finding") or {}).get("excerpt", "")[:100],
        "dif_latency_ms": dif_result.get("meta", {}).get("latency_ms"),
        "dif_schema_version": dif_result.get("schema_version"),
        "agent_action": agent_action,
        "outcome": "pending",  # pending | success | failure — set after task completes
    }

    _FEEDBACK_BUFFER.append(entry)

    # Append to local log file
    try:
        _FEEDBACK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_FEEDBACK_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log.warning("DIF feedback log write failed: %s", e)

    return entry


def update_outcome(task_id: str, outcome: str) -> int:
    """Update all feedback entries for a task with the final outcome.

    outcome: success | failure | timeout
    """
    updated = 0
    for entry in _FEEDBACK_BUFFER:
        if entry["task_id"] == task_id and entry["outcome"] == "pending":
            entry["outcome"] = outcome
            updated += 1
    return updated


def get_stats() -> dict[str, Any]:
    """Get DIF feedback statistics."""
    total = len(_FEEDBACK_BUFFER)
    if total == 0:
        return {"total": 0, "message": "No DIF verifications recorded yet"}

    by_trust = {}
    by_language = {}
    by_outcome = {}
    true_positives = 0
    false_positives = 0
    true_negatives = 0

    for e in _FEEDBACK_BUFFER:
        trust = e.get("dif_trust", "?")
        lang = e.get("language", "?")
        outcome = e.get("outcome", "pending")
        action = e.get("agent_action", "pending")

        by_trust[trust] = by_trust.get(trust, 0) + 1
        by_language[lang] = by_language.get(lang, 0) + 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1

        # Classify accuracy
        is_concern = trust in ("concern", "review") and e.get("dif_stream") == "anomaly"
        if outcome == "success":
            if is_concern and action == "fixed":
                true_positives += 1  # DIF found issue, agent fixed, code works
            elif not is_concern:
                true_negatives += 1  # DIF said ok, code is ok
        elif outcome == "failure":
            if not is_concern:
                pass  # false_negative — DIF missed it (hardest to track)
        if is_concern and action == "ignored" and outcome == "success":
            false_positives += 1  # DIF flagged but code was fine anyway

    return {
        "total": total,
        "by_trust_signal": by_trust,
        "by_language": by_language,
        "by_outcome": by_outcome,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "false_positive_rate": round(false_positives / max(true_positives + false_positives, 1), 3),
        "accuracy": round((true_positives + true_negatives) / max(total, 1), 3),
    }


def get_recent(limit: int = 20) -> list[dict[str, Any]]:
    """Get recent DIF feedback entries."""
    return list(reversed(_FEEDBACK_BUFFER[-limit:]))


def flush_to_api() -> int:
    """Flush feedback buffer to the CC API for persistent storage."""
    try:
        from app.services.graph_service import create_node
        flushed = 0
        for entry in _FEEDBACK_BUFFER:
            if entry.get("_flushed"):
                continue
            create_node(
                id=f"dif-feedback:{entry['task_id']}:{entry['file_path'][-30:]}",
                type="dif_feedback",
                name=f"DIF {entry['dif_trust']} on {entry['file_path'][-40:]}",
                description=f"{entry['dif_stream']} v={entry['dif_verification']} {entry['language']}",
                phase="ice",
                properties=entry,
            )
            entry["_flushed"] = True
            flushed += 1
        return flushed
    except Exception as e:
        log.warning("DIF feedback flush failed: %s", e)
        return 0
