"""Attunement scheduler — re-attune every presence so newly added concepts
get woven into existing presences' resonance graphs.

The on-demand attune endpoint (POST /api/presences/{id}/resonances/attune)
fires only when a presence is first minted or claimed. After that the
edges sit frozen. When new concepts later land in the Living Collective KB,
existing presences never feel them — leaving otherwise-active people with
empty Resonates-With sections months after their attunement.

This module walks every presence-type node and re-runs ``attune`` for each.
Idempotent (existing edges stay, new ones get added, stale ones get pruned),
tolerant of per-presence errors (one bad node never poisons the whole run),
and persists a summary of the most recent run to ``api/output/last_attunement_run.json``
so cron observers can see when it last ran and what changed.

Designed for weekly cron / scheduled task. Runs in-process — no separate
worker required.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import graph_service, resonance_service

logger = logging.getLogger(__name__)


# Presence node types this scheduler walks. Matches the subset of
# resonance_service.PRESENCE_TYPES that represent actual living
# presences (people / communities / organizations / interest signals)
# rather than artifacts (assets, events, scenes), per the
# attunement-scheduler spec.
SCHEDULER_PRESENCE_TYPES: tuple[str, ...] = (
    "contributor",
    "community",
    "network-org",
    "interested-person",
)

# Cap on how many per-presence detail rows the summary keeps. Keeps the
# summary file readable on a system with thousands of presences while
# still surfacing the most-changed for inspection.
MAX_DETAILS = 20

# Where the last-run summary lives. Read by ops, overwritten each run.
_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"
_LAST_RUN_PATH = _OUTPUT_DIR / "last_attunement_run.json"


def _iter_presence_nodes(limit: int | None = None) -> list[dict[str, Any]]:
    """All presence-type nodes in the graph, capped by ``limit``.

    Iterates the explicit set of presence types so a future expansion
    of NodeType doesn't silently widen the scheduler's scope.
    """
    nodes: list[dict[str, Any]] = []
    for ntype in SCHEDULER_PRESENCE_TYPES:
        # 500 is the same upper bound resonance_service uses when
        # listing concepts — large enough for any reasonable presence
        # count today, small enough that pagination stays unnecessary.
        page = graph_service.list_nodes(type=ntype, limit=500)
        nodes.extend(page.get("items", []))
        if limit is not None and len(nodes) >= limit:
            break
    if limit is not None:
        nodes = nodes[:limit]
    return nodes


def _existing_resonance_count(presence_id: str) -> int:
    """How many resonates-with edges this presence already carries.

    Used to compute ``gained_count`` — how many new concept edges the
    most recent attune actually added — without trusting the
    ``existed`` list size, which mixes pre-existing edges with edges
    that survived from an earlier run of the same scheduler pass.
    """
    edges = graph_service.list_edges(
        from_id=presence_id,
        edge_type="resonates-with",
        limit=200,
    ).get("items", [])
    return len(edges)


def run_one(node_id: str) -> dict[str, Any]:
    """Attune a single presence and report the gained-edge delta.

    Wraps ``resonance_service.attune`` and adds:
      · ``gained_count``  — how many resonates-with edges were newly
                            written this call (delta against the edges
                            that existed before the attune ran)
      · ``error``         — populated only if attune raised; ``result``
                            is then None

    Never raises — callers iterate many presences and want one bad node
    to log instead of poison the loop.
    """
    if not graph_service.get_node(node_id):
        return {
            "node_id": node_id,
            "result": None,
            "gained_count": 0,
            "error": "node-not-found",
        }
    try:
        result = resonance_service.attune(node_id)
    except Exception as exc:  # noqa: BLE001 — tolerate any per-presence failure
        logger.exception("attune failed for %s", node_id)
        return {
            "node_id": node_id,
            "result": None,
            "gained_count": 0,
            "error": str(exc) or exc.__class__.__name__,
        }
    # Truthful gained_count comes directly from attune's "written"
    # bucket. Earlier versions diffed before/after edge counts and
    # clamped to zero — but when attune prunes more stale edges than
    # it writes new ones, the delta goes negative and a presence that
    # genuinely gained edges was reported as unchanged. The service
    # already tells us exactly which edges were written; trust it.
    written = result.get("written") if isinstance(result, dict) else None
    gained = len(written) if isinstance(written, list) else 0
    return {
        "node_id": node_id,
        "result": result,
        "gained_count": gained,
        "error": None,
    }


def _persist_summary(summary: dict[str, Any]) -> Path | None:
    """Write the run summary to api/output/last_attunement_run.json.

    Returns the path on success, ``None`` if persistence failed (which
    is logged but never raised — the run itself succeeded).
    """
    try:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        _LAST_RUN_PATH.write_text(
            json.dumps(summary, indent=2, default=str),
            encoding="utf-8",
        )
        return _LAST_RUN_PATH
    except Exception:  # noqa: BLE001
        logger.exception("failed to persist attunement run summary")
        return None


def run_all(*, limit: int | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Walk every presence node and attune each.

    Aggregates a summary keyed for cron-friendly observation:
      · ``total_scanned``         — presences considered this run
      · ``total_with_new_edges``  — presences whose attune wrote at least one new edge
      · ``total_unchanged``       — presences whose attune wrote nothing new
      · ``total_errors``          — presences whose attune raised
      · ``errors``                — list of {node_id, error} for failed presences
      · ``details``               — top ``MAX_DETAILS`` most-changed presence
                                    summaries (sorted by gained_count desc), each:
                                    {node_id, written, existed, pruned, gained_count}
      · ``dry_run``               — flag echoed back so the caller can audit
      · ``started_at``/``finished_at``/``duration_seconds``

    Persists the summary to ``api/output/last_attunement_run.json`` so
    "when did we last run" is answerable by reading one file.

    ``dry_run=True`` runs ``compute_resonance`` instead of ``attune``,
    so nothing is written. Limitation: ``attune()`` itself doesn't
    accept a dry_run flag, so the dry-run path can't observe the
    pruning step. Reported gained_count under dry-run is the
    *would-write* count: scored - already-existing edges.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    t_start = time.monotonic()

    presences = _iter_presence_nodes(limit=limit)

    total_with_new_edges = 0
    total_unchanged = 0
    total_errors = 0
    errors: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for node in presences:
        node_id = node.get("id")
        if not node_id:
            continue

        if dry_run:
            # Read-only path: compute would-write set without mutating
            # the graph. attune() has no dry_run parameter today; this
            # is the documented limitation in the docstring above.
            try:
                scored = resonance_service.compute_resonance(node_id)
                existing_targets = {
                    e["to_id"]
                    for e in graph_service.list_edges(
                        from_id=node_id,
                        edge_type="resonates-with",
                        limit=200,
                    ).get("items", [])
                    if e.get("to_id")
                }
                would_write = [
                    s for s in scored if s["concept_id"] not in existing_targets
                ]
                gained = len(would_write)
                detail = {
                    "node_id": node_id,
                    "written": [],
                    "existed": [s for s in scored if s["concept_id"] in existing_targets],
                    "pruned": [],
                    "gained_count": gained,
                    "would_write": [s["concept_id"] for s in would_write],
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("dry-run compute failed for %s", node_id)
                total_errors += 1
                errors.append({"node_id": node_id, "error": str(exc) or exc.__class__.__name__})
                continue

            if gained > 0:
                total_with_new_edges += 1
            else:
                total_unchanged += 1
            details.append(detail)
            continue

        # Real attune path
        outcome = run_one(node_id)
        if outcome["error"]:
            total_errors += 1
            errors.append({"node_id": node_id, "error": outcome["error"]})
            continue

        result = outcome["result"] or {}
        gained = outcome["gained_count"]
        if gained > 0:
            total_with_new_edges += 1
        else:
            total_unchanged += 1
        details.append({
            "node_id": node_id,
            "written": result.get("written", []),
            "existed": result.get("existed", []),
            "pruned": result.get("pruned", []),
            "gained_count": gained,
        })

    # Sort by most-changed first, cap to MAX_DETAILS so the summary
    # stays readable on systems with thousands of presences.
    details.sort(key=lambda d: d.get("gained_count", 0), reverse=True)
    details_top = details[:MAX_DETAILS]

    finished_at = datetime.now(timezone.utc).isoformat()
    duration = round(time.monotonic() - t_start, 3)

    summary = {
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration,
        "dry_run": dry_run,
        "total_scanned": len(presences),
        "total_with_new_edges": total_with_new_edges,
        "total_unchanged": total_unchanged,
        "total_errors": total_errors,
        "errors": errors,
        "details": details_top,
    }

    persisted = _persist_summary(summary)
    if persisted:
        summary["summary_path"] = str(persisted)

    return summary


def last_run_path() -> Path:
    """Where the last-run summary is persisted. Exposed for tooling."""
    return _LAST_RUN_PATH
