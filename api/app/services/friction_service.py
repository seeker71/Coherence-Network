"""Friction ledger service for API and scripts."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.models.friction import FrictionEvent
from app.services import metrics_service, telemetry_persistence_service


def _default_path() -> Path:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    return logs_dir / "friction_events.jsonl"


def friction_file_path() -> Path:
    configured = os.getenv("FRICTION_EVENTS_PATH")
    return Path(configured) if configured else _default_path()


def _use_db_events() -> bool:
    override = str(os.getenv("FRICTION_USE_DB", "")).strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    if os.getenv("FRICTION_EVENTS_PATH"):
        return False
    return True


def monitor_issues_file_path() -> Path:
    configured = os.getenv("MONITOR_ISSUES_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "monitor_issues.json"


def github_actions_health_file_path() -> Path:
    configured = os.getenv("GITHUB_ACTIONS_HEALTH_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "github_actions_health.json"


def _parse_iso_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_events(path: Path | None = None) -> tuple[list[FrictionEvent], int]:
    if _use_db_events():
        telemetry_persistence_service.ensure_schema()
        legacy_path = friction_file_path()
        report = telemetry_persistence_service.import_friction_events_from_file(legacy_path)
        if int(report.get("imported") or 0) > 0:
            purge_raw = str(os.getenv("TRACKING_PURGE_IMPORTED_FILES", "1")).strip().lower()
            if purge_raw not in {"0", "false", "no", "off"}:
                try:
                    legacy_path.unlink(missing_ok=True)
                except OSError:
                    pass
        events: list[FrictionEvent] = []
        ignored = 0
        for payload in telemetry_persistence_service.list_friction_events(limit=10000):
            try:
                events.append(FrictionEvent(**payload))
            except Exception:
                ignored += 1
                continue
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events, ignored
    path = path or friction_file_path()
    if not path.exists():
        return [], 0
    events: list[FrictionEvent] = []
    ignored = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                ignored += 1
                continue
            events.append(FrictionEvent(**payload))
        except Exception:
            ignored += 1
            continue
    events.sort(key=lambda e: e.timestamp, reverse=True)
    return events, ignored


def append_event(event: FrictionEvent, path: Path | None = None) -> None:
    if _use_db_events():
        telemetry_persistence_service.append_friction_event(event.model_dump(mode="json"))
        return
    path = path or friction_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(event.model_dump(mode="json"))
    with path.open("a", encoding="utf-8") as f:
        f.write(serialized + "\n")


def summarize(events: list[FrictionEvent], window_days: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=max(1, window_days))
    in_window = [e for e in events if e.timestamp >= since]
    open_events = [e for e in in_window if e.status == "open"]

    by_block_type: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"count": 0, "energy_loss": 0.0, "cost_of_delay": 0.0}
    )
    by_stage: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"count": 0, "energy_loss": 0.0}
    )

    for event in in_window:
        bt = by_block_type[event.block_type]
        bt["count"] += 1
        bt["energy_loss"] += event.energy_loss_estimate
        bt["cost_of_delay"] += event.cost_of_delay

        st = by_stage[event.stage]
        st["count"] += 1
        st["energy_loss"] += event.energy_loss_estimate

    top_block_types = sorted(
        (
            {
                "key": block_type,
                "count": int(vals["count"]),
                "energy_loss": round(float(vals["energy_loss"]), 4),
                "cost_of_delay": round(float(vals["cost_of_delay"]), 4),
            }
            for block_type, vals in by_block_type.items()
        ),
        key=lambda item: item["energy_loss"],
        reverse=True,
    )

    top_stages = sorted(
        (
            {
                "key": stage,
                "count": int(vals["count"]),
                "energy_loss": round(float(vals["energy_loss"]), 4),
            }
            for stage, vals in by_stage.items()
        ),
        key=lambda item: item["energy_loss"],
        reverse=True,
    )

    return {
        "window_days": max(1, window_days),
        "from": _parse_iso_utc(since.isoformat()).isoformat().replace("+00:00", "Z"),
        "to": _parse_iso_utc(now.isoformat()).isoformat().replace("+00:00", "Z"),
        "total_events": len(in_window),
        "open_events": len(open_events),
        "total_energy_loss": round(sum(e.energy_loss_estimate for e in in_window), 4),
        "total_cost_of_delay": round(sum(e.cost_of_delay for e in in_window), 4),
        "top_block_types": top_block_types,
        "top_stages": top_stages,
    }


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _severity_rank(value: str) -> int:
    normalized = str(value or "").strip().lower()
    if normalized == "critical":
        return 4
    if normalized == "high":
        return 3
    if normalized == "medium":
        return 2
    if normalized == "low":
        return 1
    return 0


def _severity_from_rank(rank: int) -> str:
    if rank >= 4:
        return "critical"
    if rank >= 3:
        return "high"
    if rank >= 2:
        return "medium"
    if rank >= 1:
        return "low"
    return "info"


def _semantic_domain_for_entry(*, key: str, title: str, recommended_action: str) -> str:
    text = f"{key} {title} {recommended_action}".lower()
    if any(token in text for token in ("auth", "oauth", "token", "session")):
        return "auth_stability"
    if any(token in text for token in ("orphan", "runner", "heartbeat", "stale_running")):
        return "runner_stability"
    if any(
        token in text
        for token in ("provider", "readiness", "openrouter", "openai", "cursor", "railway", "quota", "limit")
    ):
        return "provider_readiness"
    if key.startswith("failed-tasks:") or "tool_failure" in text or "task_failure" in text:
        return "execution_quality"
    if any(token in text for token in ("spec", "backlog", "queue", "triage", "review")):
        return "spec_first_flow"
    if any(token in text for token in ("github-actions", "workflow", "ci")):
        return "ci_reliability"
    return "flow_friction"


def _roi_calibration_by_domain(events: list[FrictionEvent], *, since: datetime) -> dict[str, float]:
    ratios_by_domain: dict[str, list[float]] = defaultdict(list)
    for event in events:
        if event.timestamp < since or str(event.status).strip().lower() != "resolved":
            continue
        estimated = max(0.0, float(event.energy_loss_estimate)) + max(0.0, float(event.cost_of_delay))
        measured = max(0.0, float(event.time_open_hours or 0.0))
        if estimated <= 0.0 or measured <= 0.0:
            continue
        domain = _semantic_domain_for_entry(
            key=f"friction:{event.block_type}",
            title=f"Friction block: {event.block_type}",
            recommended_action=event.unblock_condition,
        )
        ratios_by_domain[domain].append(measured / estimated)
    calibrated: dict[str, float] = {}
    for domain, ratios in ratios_by_domain.items():
        if not ratios:
            continue
        mean_ratio = sum(ratios) / len(ratios)
        calibrated[domain] = round(max(0.2, min(mean_ratio, 5.0)), 4)
    return calibrated


def _cheap_model_split_hint(*, domain: str, event_count: int, wasted_minutes: float) -> str:
    if event_count >= 5 or wasted_minutes >= 45.0:
        return (
            f"Split {domain} into small specs (detect, policy, verify) so a cheap model can execute each step deterministically."
        )
    return f"Keep {domain} as one scoped spec + one implementation card for cheap-model execution."


def _potential_roi(*, event_count: int, energy_loss: float, cost_of_delay: float, wasted_minutes: float, calibration: float) -> float:
    impact = max(0.0, float(energy_loss)) + max(0.0, float(cost_of_delay)) + max(0.0, float(wasted_minutes))
    effort = max(1.0, 0.8 + (0.35 * max(1, int(event_count))))
    return round((impact / effort) * max(0.2, float(calibration or 1.0)), 4)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_monitor_issues() -> dict[str, Any]:
    path = monitor_issues_file_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_github_actions_health() -> dict[str, Any]:
    path = github_actions_health_file_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_metric_records(window_days: int) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=max(1, window_days))
    records = metrics_service._load_records()  # type: ignore[attr-defined]
    out: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        ts = _parse_time(row.get("created_at"))
        if ts is None or ts < since:
            continue
        out.append(row)
    return out


def friction_entry_points(window_days: int = 7, limit: int = 20) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=max(1, window_days))
    events, ignored = load_events()

    entries: dict[str, dict[str, Any]] = {}

    def upsert(
        *,
        key: str,
        title: str,
        severity: str,
        status: str,
        event_count: int,
        energy_loss: float,
        cost_of_delay: float,
        wasted_minutes: float,
        recommended_action: str,
        evidence_links: list[str],
        source: str,
    ) -> None:
        row = entries.get(key)
        if row is None:
            row = {
                "key": key,
                "title": title,
                "severity_rank": _severity_rank(severity),
                "status": status,
                "event_count": 0,
                "energy_loss": 0.0,
                "cost_of_delay": 0.0,
                "wasted_minutes": 0.0,
                "recommended_action": recommended_action,
                "evidence_links": [],
                "sources": [],
            }
            entries[key] = row
        row["severity_rank"] = max(int(row.get("severity_rank") or 0), _severity_rank(severity))
        if status == "open":
            row["status"] = "open"
        row["event_count"] = _safe_int(row.get("event_count")) + max(0, int(event_count))
        row["energy_loss"] = _safe_float(row.get("energy_loss")) + max(0.0, float(energy_loss))
        row["cost_of_delay"] = _safe_float(row.get("cost_of_delay")) + max(0.0, float(cost_of_delay))
        row["wasted_minutes"] = _safe_float(row.get("wasted_minutes")) + max(0.0, float(wasted_minutes))
        if recommended_action and (not row.get("recommended_action") or status == "open"):
            row["recommended_action"] = recommended_action
        links = [str(item).strip() for item in evidence_links if str(item).strip()]
        row["evidence_links"] = list(dict.fromkeys([*list(row.get("evidence_links") or []), *links]))
        row["sources"] = list(dict.fromkeys([*list(row.get("sources") or []), source]))

    # 1) Direct friction ledger events.
    for event in events:
        if event.timestamp < since:
            continue
        upsert(
            key=f"friction:{event.block_type}",
            title=f"Friction block: {event.block_type}",
            severity=event.severity,
            status=event.status,
            event_count=1,
            energy_loss=event.energy_loss_estimate,
            cost_of_delay=event.cost_of_delay,
            wasted_minutes=event.time_open_hours * 60.0 if event.time_open_hours else 0.0,
            recommended_action=event.unblock_condition,
            evidence_links=["/api/friction/events?status=open", "/friction"],
            source="friction_events",
        )

    # 2) Monitor issues (pipeline failures, CI failures, provider failures, etc).
    monitor = _load_monitor_issues()
    monitor_rows = monitor.get("issues") if isinstance(monitor.get("issues"), list) else []
    for row in monitor_rows:
        if not isinstance(row, dict):
            continue
        condition = str(row.get("condition") or "").strip()
        if not condition:
            continue
        severity = str(row.get("severity") or "medium")
        action = str(row.get("suggested_action") or "Triage and resolve this pipeline issue.")
        links: list[str] = ["/api/agent/monitor-issues", "/agent"]
        if "http" in action:
            links.extend(
                [chunk for chunk in action.split() if chunk.startswith("http://") or chunk.startswith("https://")]
            )
        upsert(
            key=f"monitor:{condition}",
            title=f"Pipeline condition: {condition}",
            severity=severity,
            status="open",
            event_count=1,
            energy_loss=0.0,
            cost_of_delay=0.0,
            wasted_minutes=0.0,
            recommended_action=action,
            evidence_links=links,
            source="monitor_issues",
        )

    # 3) Failed task runtime records (time cost with no value delivered).
    failed_rows = [row for row in _load_metric_records(window_days) if str(row.get("status")) == "failed"]
    by_task_type: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "duration": 0.0})
    for row in failed_rows:
        task_type = str(row.get("task_type") or "unknown")
        by_task_type[task_type]["count"] += 1.0
        by_task_type[task_type]["duration"] += _safe_float(row.get("duration_seconds"))
    for task_type, vals in by_task_type.items():
        failed_count = int(vals["count"])
        failed_minutes = vals["duration"] / 60.0
        severity = "high" if failed_minutes >= 20 or failed_count >= 5 else "medium"
        upsert(
            key=f"failed-tasks:{task_type}",
            title=f"Failed task executions: {task_type}",
            severity=severity,
            status="open",
            event_count=failed_count,
            energy_loss=round(failed_minutes, 4),
            cost_of_delay=round(failed_minutes, 4),
            wasted_minutes=round(failed_minutes, 4),
            recommended_action="Reduce repeated failures for this task type before running more CI-heavy iterations.",
            evidence_links=["/api/agent/metrics", "/usage"],
            source="metrics",
        )

    # 4) GitHub Actions health (includes official run links + failure-rate cost).
    gha = _load_github_actions_health()
    if gha.get("available"):
        failed_runs = _safe_int(gha.get("failed_runs"))
        completed_runs = _safe_int(gha.get("completed_runs"))
        failure_rate = _safe_float(gha.get("failure_rate"))
        wasted_minutes = _safe_float(gha.get("wasted_minutes_failed"))
        if completed_runs > 0:
            severity = "high" if failure_rate >= 0.5 else ("medium" if failure_rate >= 0.2 else "low")
            recommended = (
                f"Triage the top failing workflow first and cut GitHub Actions failure rate "
                f"(current {round(failure_rate * 100.0, 1)}%)."
            )
            links = [
                "/api/agent/monitor-issues",
                "/api/friction/entry-points",
                *([str(item) for item in gha.get("official_records", []) if isinstance(item, str)]),
                *([str(item) for item in gha.get("sample_failed_run_links", []) if isinstance(item, str)]),
            ]
            upsert(
                key="github-actions:failure-rate",
                title="GitHub Actions failure-rate friction",
                severity=severity,
                status="open" if failure_rate >= 0.2 else "monitoring",
                event_count=failed_runs,
                energy_loss=wasted_minutes,
                cost_of_delay=wasted_minutes,
                wasted_minutes=wasted_minutes,
                recommended_action=recommended,
                evidence_links=links,
                source="github_actions_health",
            )

    calibration_by_domain = _roi_calibration_by_domain(events, since=since)
    rows: list[dict[str, Any]] = []
    for row in entries.values():
        severity_rank = int(row.get("severity_rank") or 0)
        key = str(row.get("key") or "")
        title = str(row.get("title") or "")
        recommended_action = str(row.get("recommended_action") or "Investigate and resolve.")
        event_count = _safe_int(row.get("event_count"))
        energy_loss = round(_safe_float(row.get("energy_loss")), 4)
        cost_of_delay = round(_safe_float(row.get("cost_of_delay")), 4)
        wasted_minutes = round(_safe_float(row.get("wasted_minutes")), 4)
        domain = _semantic_domain_for_entry(
            key=key,
            title=title,
            recommended_action=recommended_action,
        )
        calibration_ratio = calibration_by_domain.get(domain, 1.0)
        rows.append(
            {
                "key": key,
                "title": title,
                "severity": _severity_from_rank(severity_rank),
                "status": str(row.get("status") or "open"),
                "event_count": event_count,
                "energy_loss": energy_loss,
                "cost_of_delay": cost_of_delay,
                "wasted_minutes": wasted_minutes,
                "recommended_action": recommended_action,
                "evidence_links": [str(item) for item in row.get("evidence_links", [])],
                "sources": [str(item) for item in row.get("sources", [])],
                "semantic_domain": domain,
                "potential_roi": _potential_roi(
                    event_count=event_count,
                    energy_loss=energy_loss,
                    cost_of_delay=cost_of_delay,
                    wasted_minutes=wasted_minutes,
                    calibration=calibration_ratio,
                ),
                "roi_estimator": "friction_energy_cost_minutes_v2",
                "roi_calibration_ratio": round(float(calibration_ratio), 4),
                "cheap_model_split_hint": _cheap_model_split_hint(
                    domain=domain,
                    event_count=event_count,
                    wasted_minutes=wasted_minutes,
                ),
                "_severity_rank": severity_rank,
            }
        )

    rows.sort(
        key=lambda item: (
            int(item.get("_severity_rank") or 0),
            _safe_float(item.get("wasted_minutes"))
            + _safe_float(item.get("energy_loss"))
            + _safe_float(item.get("cost_of_delay")),
            _safe_int(item.get("event_count")),
        ),
        reverse=True,
    )
    for row in rows:
        row.pop("_severity_rank", None)
    if not rows:
        rows = [
            {
                "key": "tracking:no-friction-telemetry",
                "title": "No friction telemetry detected",
                "severity": "high",
                "status": "open",
                "event_count": 1,
                "energy_loss": 0.0,
                "cost_of_delay": 0.0,
                "wasted_minutes": 0.0,
                "recommended_action": (
                    "Enable monitor pipeline and runtime metrics collection so failures and high-cost tasks become visible as friction entry points."
                ),
                "evidence_links": ["/api/agent/monitor-issues", "/api/agent/metrics", "/api/friction/events"],
                "sources": ["friction_gap_detector"],
                "semantic_domain": "flow_friction",
                "potential_roi": 0.0,
                "roi_estimator": "friction_energy_cost_minutes_v2",
                "roi_calibration_ratio": 1.0,
                "cheap_model_split_hint": (
                    "Create one setup spec (telemetry enablement) and one verification spec so a cheap model can run both."
                ),
            }
        ]
    limited = rows[: max(1, min(limit, 200))]
    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "window_days": max(1, window_days),
        "total_entry_points": len(rows),
        "open_entry_points": sum(1 for row in rows if row.get("status") == "open"),
        "entry_points": limited,
        "source_files": [
            str(friction_file_path()),
            str(monitor_issues_file_path()),
            str(metrics_service.METRICS_FILE),
            str(github_actions_health_file_path()),
        ],
        "ignored_lines": ignored,
    }


def _entry_point_category(key: str) -> str:
    normalized = str(key or "").strip()
    if not normalized:
        return "unknown"
    if ":" in normalized:
        return normalized.split(":", 1)[0].strip() or "unknown"
    return normalized


def _new_category_rollup(key: str) -> dict[str, Any]:
    return {
        "key": key,
        "_severity_rank": 0,
        "entry_point_count": 0,
        "open_entry_points": 0,
        "event_count": 0,
        "energy_loss": 0.0,
        "cost_of_delay": 0.0,
        "wasted_minutes": 0.0,
        "top_entry_keys": [],
        "recommended_actions": [],
    }


def _merge_category_rollup(category: dict[str, Any], row: dict[str, Any]) -> None:
    severity_rank = _severity_rank(str(row.get("severity") or ""))
    category["_severity_rank"] = max(int(category.get("_severity_rank") or 0), severity_rank)
    category["entry_point_count"] = _safe_int(category.get("entry_point_count")) + 1
    if str(row.get("status") or "").strip().lower() == "open":
        category["open_entry_points"] = _safe_int(category.get("open_entry_points")) + 1
    category["event_count"] = _safe_int(category.get("event_count")) + _safe_int(row.get("event_count"))
    category["energy_loss"] = _safe_float(category.get("energy_loss")) + _safe_float(row.get("energy_loss"))
    category["cost_of_delay"] = _safe_float(category.get("cost_of_delay")) + _safe_float(row.get("cost_of_delay"))
    category["wasted_minutes"] = _safe_float(category.get("wasted_minutes")) + _safe_float(row.get("wasted_minutes"))

    entry_key = str(row.get("key") or "").strip()
    if entry_key:
        keys = list(category.get("top_entry_keys") or [])
        if entry_key not in keys:
            keys.append(entry_key)
        category["top_entry_keys"] = keys[:5]

    action = str(row.get("recommended_action") or "").strip()
    if action:
        actions = list(category.get("recommended_actions") or [])
        if action not in actions:
            actions.append(action)
        category["recommended_actions"] = actions[:4]


def _render_sorted_category_rows(categories: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in categories.values():
        severity_rank = int(row.get("_severity_rank") or 0)
        rows.append(
            {
                "key": str(row.get("key") or "unknown"),
                "severity": _severity_from_rank(severity_rank),
                "entry_point_count": _safe_int(row.get("entry_point_count")),
                "open_entry_points": _safe_int(row.get("open_entry_points")),
                "event_count": _safe_int(row.get("event_count")),
                "energy_loss": round(_safe_float(row.get("energy_loss")), 4),
                "cost_of_delay": round(_safe_float(row.get("cost_of_delay")), 4),
                "wasted_minutes": round(_safe_float(row.get("wasted_minutes")), 4),
                "top_entry_keys": [str(item) for item in (row.get("top_entry_keys") or [])],
                "recommended_actions": [str(item) for item in (row.get("recommended_actions") or [])],
                "_severity_rank": severity_rank,
            }
        )

    rows.sort(
        key=lambda item: (
            int(item.get("_severity_rank") or 0),
            _safe_float(item.get("wasted_minutes"))
            + _safe_float(item.get("energy_loss"))
            + _safe_float(item.get("cost_of_delay")),
            _safe_int(item.get("event_count")),
        ),
        reverse=True,
    )
    for row in rows:
        row.pop("_severity_rank", None)
    return rows


def friction_categories(window_days: int = 7, limit: int = 20) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    base = friction_entry_points(window_days=window_days, limit=max(200, limit * 10))
    entry_points = base.get("entry_points") if isinstance(base.get("entry_points"), list) else []

    categories: dict[str, dict[str, Any]] = {}
    for row in entry_points:
        if not isinstance(row, dict):
            continue
        key = _entry_point_category(str(row.get("key") or ""))
        category = categories.setdefault(key, _new_category_rollup(key))
        _merge_category_rollup(category, row)

    rows = _render_sorted_category_rows(categories)
    limited = rows[: max(1, min(limit, 200))]
    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "window_days": max(1, window_days),
        "total_categories": len(rows),
        "categories": limited,
        "source_files": [str(item) for item in (base.get("source_files") or []) if str(item).strip()],
    }
