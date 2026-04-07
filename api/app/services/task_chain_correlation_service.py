"""Cross-task outcome correlation — chain linkage, resolution, and effectiveness scoring.

Links related tasks into chains via source_task_id, computes downstream-validated
effectiveness scores, and feeds them back into grounded measurements.

Spec: cross-task-outcome-correlation
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_DEFAULT_STORE = Path(__file__).resolve().parent.parent.parent / "logs" / "task_chain_links.json"
_MAX_CHAIN_DEPTH = 10

# Valid link types
_LINK_TYPES = {"heal", "review", "test", "continuation"}

# Platform-aware file locking (same pattern as slot_selection_service)
if sys.platform == "win32":
    import msvcrt

    def _lock(f: Any) -> None:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(f: Any) -> None:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _lock(f: Any) -> None:
        fcntl.flock(f, fcntl.LOCK_EX)

    def _unlock(f: Any) -> None:
        fcntl.flock(f, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

def _make_chain_link(
    upstream_task_id: str,
    downstream_task_id: str,
    link_type: str,
    downstream_status: str = "pending",
) -> dict[str, Any]:
    """Create a TaskChainLink dict."""
    if link_type not in _LINK_TYPES:
        link_type = "continuation"
    return {
        "upstream_task_id": upstream_task_id,
        "downstream_task_id": downstream_task_id,
        "link_type": link_type,
        "downstream_status": downstream_status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# JSON file store
# ---------------------------------------------------------------------------

def _load_links(store_path: Path | None = None) -> list[dict[str, Any]]:
    path = store_path or _DEFAULT_STORE
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_links(links: list[dict[str, Any]], store_path: Path | None = None) -> None:
    path = store_path or _DEFAULT_STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a+" if path.exists() else "w+"
    with open(path, mode) as f:
        _lock(f)
        try:
            f.seek(0)
            f.truncate()
            json.dump(links, f, indent=2)
        finally:
            _unlock(f)


# ---------------------------------------------------------------------------
# R1: Record chain link
# ---------------------------------------------------------------------------

def record_chain_link(
    upstream_task_id: str,
    downstream_task_id: str,
    link_type: str,
    downstream_status: str = "pending",
    *,
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Record a TaskChainLink when downstream task has source_task_id.

    R1: When a task's context contains a source_task_id, record a link
    associating the upstream task to the downstream task.
    """
    link = _make_chain_link(upstream_task_id, downstream_task_id, link_type, downstream_status)
    path = store_path or _DEFAULT_STORE
    path.parent.mkdir(parents=True, exist_ok=True)

    mode = "a+" if path.exists() else "w+"
    with open(path, mode) as f:
        _lock(f)
        try:
            f.seek(0)
            content = f.read().strip()
            links: list[dict] = json.loads(content) if content else []
            links.append(link)
            f.seek(0)
            f.truncate()
            json.dump(links, f, indent=2)
        finally:
            _unlock(f)

    return link


def update_link_status(
    downstream_task_id: str,
    new_status: str,
    *,
    store_path: Path | None = None,
) -> None:
    """Update the downstream_status of an existing link."""
    links = _load_links(store_path)
    changed = False
    for link in links:
        if link.get("downstream_task_id") == downstream_task_id:
            link["downstream_status"] = new_status
            changed = True
    if changed:
        _save_links(links, store_path)


# ---------------------------------------------------------------------------
# R2: Chain resolution
# ---------------------------------------------------------------------------

def resolve_chain(
    task_id: str,
    *,
    store_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return the full ordered chain of tasks linked from a root task.

    R2: Follows source_task_id references forward from the root.
    Max depth 10 to prevent cycles.
    """
    links = _load_links(store_path)

    # Build index: upstream_task_id -> list of links
    by_upstream: dict[str, list[dict]] = {}
    for link in links:
        uid = link.get("upstream_task_id", "")
        by_upstream.setdefault(uid, []).append(link)

    chain: list[dict[str, Any]] = []
    visited: set[str] = {task_id}
    current_ids = [task_id]
    depth = 0

    while current_ids and depth < _MAX_CHAIN_DEPTH:
        next_ids: list[str] = []
        for cid in current_ids:
            for link in by_upstream.get(cid, []):
                did = link.get("downstream_task_id", "")
                if did in visited:
                    continue  # cycle protection
                visited.add(did)
                chain.append(link)
                next_ids.append(did)
        current_ids = next_ids
        depth += 1

    return chain


# ---------------------------------------------------------------------------
# R3 + R4: Chain effectiveness
# ---------------------------------------------------------------------------

def compute_chain_effectiveness(
    chain: list[dict[str, Any]],
    root_task_status: str = "completed",
) -> dict[str, Any]:
    """Compute chain effectiveness score based on terminal task outcomes.

    R3: Produces chain_effectiveness, downstream_pass_rate, chain_length,
        terminal_status, value_validated.
    R4: Scoring rules based on root/downstream outcomes.
    """
    # chain_length includes the root task
    chain_length = 1 + len(chain)

    # R4: Root task failed -> 0.0
    if root_task_status != "completed":
        return {
            "root_task_id": "",  # caller should set this
            "chain_effectiveness": 0.0,
            "downstream_pass_rate": 0.0,
            "chain_length": chain_length,
            "terminal_status": root_task_status,
            "value_validated": False,
            "links": chain,
        }

    # No downstream tasks -> 0.5 (unvalidated)
    if not chain:
        return {
            "root_task_id": "",
            "chain_effectiveness": 0.5,
            "downstream_pass_rate": 0.0,
            "chain_length": 1,
            "terminal_status": root_task_status,
            "value_validated": False,
            "links": [],
        }

    # Compute downstream pass rate
    completed_count = sum(1 for l in chain if l.get("downstream_status") == "completed")
    downstream_pass_rate = completed_count / len(chain) if chain else 0.0

    # Determine terminal status (last link in chain)
    terminal_status = chain[-1].get("downstream_status", "pending")

    # Check for review/test links that passed
    review_test_passed = any(
        l.get("link_type") in ("review", "test") and l.get("downstream_status") == "completed"
        for l in chain
    )

    # Check for review/test links that failed
    review_test_failed = any(
        l.get("link_type") in ("review", "test") and l.get("downstream_status") == "failed"
        for l in chain
    )

    # Check for heal links that succeeded
    heal_succeeded = any(
        l.get("link_type") == "heal" and l.get("downstream_status") == "completed"
        for l in chain
    )

    # R4 scoring rules (in priority order)
    if review_test_passed:
        # Root succeeded, downstream review/test passed -> 1.0
        chain_effectiveness = 1.0
        value_validated = True
    elif review_test_failed:
        # Root succeeded, downstream review/test failed -> 0.2
        chain_effectiveness = 0.2
        value_validated = False
    elif heal_succeeded:
        # Root succeeded, downstream heal was needed and succeeded -> 0.6
        chain_effectiveness = 0.6
        value_validated = False
    else:
        # Root succeeded, downstream tasks exist but no review/test/heal completed
        chain_effectiveness = 0.5
        value_validated = False

    return {
        "root_task_id": "",
        "chain_effectiveness": chain_effectiveness,
        "downstream_pass_rate": round(downstream_pass_rate, 4),
        "chain_length": chain_length,
        "terminal_status": terminal_status,
        "value_validated": value_validated,
        "links": chain,
    }


# ---------------------------------------------------------------------------
# R5: Measurement enrichment
# ---------------------------------------------------------------------------

def enrich_upstream_measurement(
    source_task_id: str,
    *,
    store_path: Path | None = None,
    measurement_store_path: Path | None = None,
) -> dict[str, Any] | None:
    """Update upstream task's grounded measurement with chain_effectiveness.

    R5: Resolves the chain, computes effectiveness, and updates the
    upstream measurement's raw_signals with chain_effectiveness and
    value_validated fields.

    Returns the ChainEffectiveness dict or None if no chain found.
    """
    chain = resolve_chain(source_task_id, store_path=store_path)

    # Determine root task status — try to look it up
    root_status = "completed"  # default assumption
    try:
        from app.services import agent_service
        task = agent_service.get_task(source_task_id)
        if isinstance(task, dict):
            root_status = task.get("status", "completed")
            if hasattr(root_status, "value"):
                root_status = root_status.value
    except Exception:
        _log.debug("Could not look up task %s for root status", source_task_id)

    effectiveness = compute_chain_effectiveness(chain, root_task_status=root_status)
    effectiveness["root_task_id"] = source_task_id

    # Update measurement in slot_measurements store
    _update_measurement_raw_signals(
        source_task_id,
        {
            "chain_effectiveness": effectiveness["chain_effectiveness"],
            "value_validated": effectiveness["value_validated"],
            "chain_length": effectiveness["chain_length"],
            "downstream_pass_rate": effectiveness["downstream_pass_rate"],
        },
        measurement_store_path=measurement_store_path,
    )

    return effectiveness


def _update_measurement_raw_signals(
    task_id: str,
    new_fields: dict[str, Any],
    *,
    measurement_store_path: Path | None = None,
) -> bool:
    """Update raw_signals in a stored measurement for a task.

    Scans slot measurement files to find the measurement for this task_id,
    then appends/updates the specified fields in raw_signals.
    """
    if measurement_store_path:
        search_paths = [measurement_store_path]
    else:
        store_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "slot_measurements"
        if not store_dir.exists():
            _log.debug("No slot_measurements dir found, skipping enrichment")
            return False
        search_paths = list(store_dir.glob("*.json"))

    for mpath in search_paths:
        if not mpath.exists():
            continue
        try:
            with open(mpath, "r") as f:
                measurements = json.load(f)
            if not isinstance(measurements, list):
                continue

            updated = False
            for m in measurements:
                if m.get("task_id") == task_id:
                    if "raw_signals" not in m:
                        m["raw_signals"] = {}
                    m["raw_signals"].update(new_fields)
                    updated = True

            if updated:
                with open(mpath, "w") as f:
                    _lock(f)
                    try:
                        json.dump(measurements, f, indent=2)
                    finally:
                        _unlock(f)
                return True
        except (OSError, json.JSONDecodeError):
            _log.debug("Could not read/update measurement file %s", mpath, exc_info=True)

    _log.debug("No measurement found for task %s — enrichment skipped", task_id)
    return False


# ---------------------------------------------------------------------------
# R6: Chain stats
# ---------------------------------------------------------------------------

def get_chain_stats(*, store_path: Path | None = None) -> dict[str, Any]:
    """Return aggregate chain metrics.

    R6: total_chains, avg_chain_length, avg_effectiveness, validation_rate,
    by_link_type with count and pass_rate per type.
    """
    links = _load_links(store_path)

    if not links:
        return {
            "total_chains": 0,
            "avg_chain_length": 0.0,
            "avg_effectiveness": 0.0,
            "validation_rate": 0.0,
            "by_link_type": {},
        }

    # Find all root task IDs (upstream tasks that are never downstream)
    all_downstream = {l.get("downstream_task_id") for l in links}
    all_upstream = {l.get("upstream_task_id") for l in links}
    root_ids = all_upstream - all_downstream

    if not root_ids:
        # All tasks are both upstream and downstream — pick upstream tasks as roots
        root_ids = all_upstream

    # Compute per-chain stats
    chain_lengths: list[int] = []
    effectiveness_scores: list[float] = []
    validated_count = 0

    for root_id in root_ids:
        chain = resolve_chain(root_id, store_path=store_path)
        eff = compute_chain_effectiveness(chain)
        eff["root_task_id"] = root_id
        chain_lengths.append(eff["chain_length"])
        effectiveness_scores.append(eff["chain_effectiveness"])
        if eff["value_validated"]:
            validated_count += 1

    total_chains = len(root_ids)
    avg_chain_length = round(sum(chain_lengths) / total_chains, 1) if total_chains else 0.0
    avg_effectiveness = round(
        sum(effectiveness_scores) / total_chains, 2
    ) if total_chains else 0.0
    validation_rate = round(validated_count / total_chains, 2) if total_chains else 0.0

    # by_link_type stats
    by_link_type: dict[str, dict[str, Any]] = {}
    for link in links:
        lt = link.get("link_type", "continuation")
        if lt not in by_link_type:
            by_link_type[lt] = {"count": 0, "passed": 0}
        by_link_type[lt]["count"] += 1
        if link.get("downstream_status") == "completed":
            by_link_type[lt]["passed"] += 1

    # Convert to pass_rate
    for lt, stats in by_link_type.items():
        count = stats["count"]
        passed = stats.pop("passed")
        stats["pass_rate"] = round(passed / count, 2) if count else 0.0

    return {
        "total_chains": total_chains,
        "avg_chain_length": avg_chain_length,
        "avg_effectiveness": avg_effectiveness,
        "validation_rate": validation_rate,
        "by_link_type": by_link_type,
    }
