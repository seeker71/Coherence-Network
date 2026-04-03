"""Agent diagnostics routes."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import config_loader
from app.middleware.auth import require_admin_key
from app.routers import health as health_router
from app.services import (
    auto_heal_service,
    agent_execution_hooks,
    agent_runner_registry_service,
    agent_service,
    context_hygiene_service,
    failed_task_diagnostics_service,
    friction_service,
    persistence_contract_service,
    runtime_service,
)
from app.services.agent_service import list_tasks
from app.services.config_service import reset_config_cache

router = APIRouter()

_API_ROOT = Path(__file__).resolve().parents[2]


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _secret_preview(value: str | None) -> dict[str, Any]:
    raw = str(value or "").strip()
    if not raw:
        return {"configured": False, "preview": None}
    if len(raw) <= 6:
        return {"configured": True, "preview": "*" * len(raw)}
    return {"configured": True, "preview": f"{raw[:2]}***{raw[-2:]}"}


def _redact_database_url(url: str | None) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        return raw
    scheme, remainder = raw.split("://", 1)
    if "@" not in remainder or ":" not in remainder.split("@", 1)[0]:
        return raw
    creds, tail = remainder.split("@", 1)
    username, _password = creds.split(":", 1)
    return f"{scheme}://{username}:***@{tail}"


def _database_backend(url: str | None) -> str:
    raw = str(url or "").strip().lower()
    if raw.startswith("postgres"):
        return "postgresql"
    if raw.startswith("sqlite"):
        return "sqlite"
    if not raw:
        return "unknown"
    return raw.split(":", 1)[0]


def _resolve_path(value: str | None, default: Path) -> Path:
    raw = str(value or "").strip()
    path = Path(raw) if raw else default
    if not path.is_absolute():
        path = (_API_ROOT / path).resolve()
    return path


def _path_status(path: Path, *, kind: str = "file") -> dict[str, Any]:
    exists = path.exists()
    if kind == "directory":
        exists = path.exists() and path.is_dir()
    return {
        "path": str(path),
        "exists": exists,
        "kind": kind,
    }


def _task_log_preview(task: dict[str, Any], *, max_chars: int = 1200) -> dict[str, Any]:
    task_id = str(task.get("id") or "").strip()
    task_log_dir = _resolve_path(
        config_loader.api_config("agent_tasks", "task_log_dir", "logs"),
        _API_ROOT / "logs",
    )
    log_path = task_log_dir / f"task_{task_id}.log"
    if log_path.is_file():
        text = log_path.read_text(encoding="utf-8")[:max_chars]
        return {
            "task_id": task_id,
            "path": str(log_path),
            "source": "file",
            "preview": text,
        }

    snapshot_parts: list[str] = []
    for key in ("status", "current_step", "updated_at"):
        value = task.get(key)
        if value:
            snapshot_parts.append(f"{key}: {value}")
    output = str(task.get("output") or "").strip()
    if output:
        snapshot_parts.append("")
        snapshot_parts.append(output[:max_chars])
    preview = "\n".join(snapshot_parts).strip() or "No task log file is available yet."
    return {
        "task_id": task_id,
        "path": str(log_path),
        "source": "task_snapshot",
        "preview": preview,
    }


def _serialize_runtime_event(row: Any) -> dict[str, Any]:
    if hasattr(row, "model_dump"):
        return row.model_dump(mode="json")
    if isinstance(row, dict):
        return dict(row)
    return {"value": row}


async def _resolve_payload(value: Any) -> Any:
    if inspect.isawaitable(value):
        value = await value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _deep_set(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node = target
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[path[-1]] = value


def _normalize_string_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        trimmed = str(value).strip()
        if trimmed:
            cleaned.append(trimmed)
    return cleaned


class DiagnosticsConfigEditorResponse(BaseModel):
    generated_at: str
    config_path: str
    fields: dict[str, Any]


class DiagnosticsConfigEditorUpdate(BaseModel):
    server_environment: str | None = Field(default=None)
    database_url: str | None = Field(default=None)
    cors_allowed_origins: list[str] | None = Field(default=None)
    api_base_url: str | None = Field(default=None)
    web_ui_base_url: str | None = Field(default=None)
    execute_token: str | None = Field(default=None)
    clear_execute_token: bool = Field(default=False)
    execute_token_allow_unauth: bool | None = Field(default=None)
    telegram_bot_token: str | None = Field(default=None)
    clear_telegram_bot_token: bool = Field(default=False)
    telegram_chat_ids: list[str] | None = Field(default=None)
    task_log_dir: str | None = Field(default=None)
    runtime_events_path: str | None = Field(default=None)
    friction_events_path: str | None = Field(default=None)
    live_updates_poll_ms: int | None = Field(default=None)
    live_updates_router_refresh_every_ticks: int | None = Field(default=None)
    live_updates_global: bool | None = Field(default=None)
    runtime_beacon_sample_rate: float | None = Field(default=None)
    health_proxy_failure_threshold: int | None = Field(default=None)
    health_proxy_cooldown_ms: int | None = Field(default=None)
    cli_provider: str | None = Field(default=None)
    cli_active_task_id: str | None = Field(default=None)


def _config_editor_fields() -> dict[str, Any]:
    return {
        "server_environment": config_loader.api_config("server", "environment", "development"),
        "database_url": config_loader.database_url(),
        "cors_allowed_origins": config_loader.get_list("cors", "allowed_origins", []),
        "api_base_url": config_loader.api_config("agent_providers", "api_base_url", ""),
        "web_ui_base_url": config_loader.api_config("agent_providers", "web_ui_base_url", ""),
        "execute_token_configured": bool(config_loader.api_config("agent_executor", "execute_token", "")),
        "execute_token_allow_unauth": bool(
            config_loader.api_config("agent_executor", "execute_token_allow_unauth", False)
        ),
        "telegram_bot_token_configured": bool(config_loader.api_config("telegram", "bot_token", "")),
        "telegram_chat_ids": config_loader.get_list("telegram", "chat_ids", []),
        "task_log_dir": str(config_loader.api_config("agent_tasks", "task_log_dir", "logs") or ""),
        "runtime_events_path": str(config_loader.api_config("runtime", "events_path", "") or ""),
        "friction_events_path": str(config_loader.api_config("friction", "events_path", "") or ""),
        "live_updates_poll_ms": config_loader.get_int("live_updates", "poll_ms", 120000),
        "live_updates_router_refresh_every_ticks": config_loader.get_int(
            "live_updates",
            "router_refresh_every_ticks",
            8,
        ),
        "live_updates_global": config_loader.get_bool("live_updates", "global", False),
        "runtime_beacon_sample_rate": config_loader.get_float("runtime_beacon", "sample_rate", 0.2),
        "health_proxy_failure_threshold": config_loader.get_int("health_proxy", "failure_threshold", 2),
        "health_proxy_cooldown_ms": config_loader.get_int("health_proxy", "cooldown_ms", 30000),
        "cli_provider": str(config_loader.api_config("cli", "provider", "cli") or "cli"),
        "cli_active_task_id": str(config_loader.api_config("cli", "active_task_id", "") or ""),
    }


def _diagnostics_config_payload() -> dict[str, Any]:
    runtime_events_path = _resolve_path(
        config_loader.api_config("runtime", "events_path", ""),
        _API_ROOT / "data" / "runtime_events.json",
    )
    task_log_dir = _resolve_path(
        config_loader.api_config("agent_tasks", "task_log_dir", "logs"),
        _API_ROOT / "logs",
    )
    return {
        "sources": config_loader.config_source_report(),
        "environment": config_loader.api_config("server", "environment", "development"),
        "database": {
            "backend": _database_backend(config_loader.database_url()),
            "url": _redact_database_url(config_loader.database_url()),
            "override_services": sorted(
                key
                for key, value in (config_loader.api_config("database_overrides", "", {}) or {}).items()
                if value
            ),
        },
        "auth": {
            "api_key": _secret_preview(config_loader.api_config("auth", "api_key", "")),
            "admin_key": _secret_preview(config_loader.api_config("auth", "admin_key", "")),
            "execute_token": _secret_preview(config_loader.api_config("agent_executor", "execute_token", "")),
            "execute_token_allow_unauth": bool(
                config_loader.api_config("agent_executor", "execute_token_allow_unauth", False)
            ),
        },
        "telegram": {
            "bot_token": _secret_preview(config_loader.api_config("telegram", "bot_token", "")),
            "chat_ids_count": len(config_loader.get_list("telegram", "chat_ids", [])),
            "allowed_user_ids_count": len(config_loader.get_list("telegram", "allowed_user_ids", [])),
        },
        "cors": {
            "allowed_origins": config_loader.get_list("cors", "allowed_origins", []),
        },
        "files": {
            "runtime_events": _path_status(runtime_events_path),
            "friction_events": _path_status(friction_service.friction_file_path()),
            "monitor_issues": _path_status(friction_service.monitor_issues_file_path()),
            "github_actions_health": _path_status(friction_service.github_actions_health_file_path()),
            "task_logs_dir": _path_status(task_log_dir, kind="directory"),
        },
        "provider_surfaces": {
            "api_base_url": config_loader.api_config("agent_providers", "api_base_url", ""),
            "web_ui_base_url": config_loader.api_config("agent_providers", "web_ui_base_url", ""),
        },
        "web_controls": {
            "live_updates_poll_ms": config_loader.get_int("live_updates", "poll_ms", 120000),
            "live_updates_router_refresh_every_ticks": config_loader.get_int(
                "live_updates",
                "router_refresh_every_ticks",
                8,
            ),
            "live_updates_global": config_loader.get_bool("live_updates", "global", False),
            "runtime_beacon_sample_rate": config_loader.get_float("runtime_beacon", "sample_rate", 0.2),
            "health_proxy_failure_threshold": config_loader.get_int("health_proxy", "failure_threshold", 2),
            "health_proxy_cooldown_ms": config_loader.get_int("health_proxy", "cooldown_ms", 30000),
        },
        "cli_defaults": {
            "provider": str(config_loader.api_config("cli", "provider", "cli") or "cli"),
            "active_task_id": str(config_loader.api_config("cli", "active_task_id", "") or ""),
        },
    }


def _diagnostics_task_payload(
    *,
    counts: dict[str, Any],
    recent_rows: list[dict[str, Any]],
    recent_total: int,
    attention_rows: list[dict[str, Any]],
    attention_total: int,
    runner_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    active_rows = [
        row for row in recent_rows
        if str(row.get("status") or "").strip().lower() == "running"
    ]
    runner_gap = auto_heal_service.summarize_runner_gap(
        task_counts=counts,
        runner_rows=runner_rows,
        running_tasks=active_rows,
    )
    return {
        "counts": counts,
        "recent_total": recent_total,
        "recent": recent_rows,
        "active": active_rows,
        "context_budget": context_hygiene_service.summarize_recent_tasks(recent_rows),
        "anomalies": [runner_gap] if runner_gap["open"] else [],
        "attention_total": attention_total,
        "attention": attention_rows,
        "log_previews": [_task_log_preview(row) for row in recent_rows[:3]],
    }


def _diagnostics_runner_payload(runner_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(runner_rows),
        "stale": sum(1 for row in runner_rows if bool(row.get("is_stale"))),
        "running": sum(1 for row in runner_rows if str(row.get("status") or "").lower() == "running"),
        "items": runner_rows,
    }


@router.get("/diagnostics/overview")
async def get_diagnostics_overview(
    request: Request,
    _admin_key: str = Depends(require_admin_key),
) -> dict:
    counts = agent_service.get_task_count()
    attention_rows, attention_total = agent_service.get_attention_tasks(limit=5)
    recent_rows, recent_total, _runtime_backfill = agent_service.list_tasks(limit=8, offset=0)
    runner_rows = agent_runner_registry_service.list_runners(include_stale=True, limit=20)
    runtime_events = runtime_service.list_events(limit=12)
    friction_events, _ignored = friction_service.load_events()
    friction_summary = friction_service.summarize(friction_events, window_days=7)
    endpoint_attention = runtime_service.summarize_endpoint_attention(
        seconds=21600,
        min_event_count=1,
        attention_threshold=40.0,
        limit=8,
    ).model_dump(mode="json")
    lifecycle = agent_execution_hooks.summarize_lifecycle_events(
        seconds=21600,
        limit=200,
        source="auto",
    )
    health_payload = await _resolve_payload(health_router.health())
    persistence_payload = await _resolve_payload(persistence_contract_service.evaluate(request.app))
    return {
        "generated_at": _iso_utc_now(),
        "config": _diagnostics_config_payload(),
        "health": health_payload,
        "persistence": persistence_payload,
        "tasks": _diagnostics_task_payload(
            counts=counts,
            recent_rows=recent_rows,
            recent_total=recent_total,
            attention_rows=attention_rows,
            attention_total=attention_total,
            runner_rows=runner_rows,
        ),
        "runners": _diagnostics_runner_payload(runner_rows),
        "lifecycle": lifecycle,
        "runtime": {
            "endpoint_attention": endpoint_attention,
            "recent_events": [_serialize_runtime_event(row) for row in runtime_events],
        },
        "friction": {
            "summary": friction_summary,
            "events": [event.model_dump(mode="json") for event in friction_events[:8]],
        },
    }


@router.get("/diagnostics/config-editor", response_model=DiagnosticsConfigEditorResponse)
async def get_diagnostics_config_editor(_admin_key: str = Depends(require_admin_key)) -> DiagnosticsConfigEditorResponse:
    return DiagnosticsConfigEditorResponse(
        generated_at=_iso_utc_now(),
        config_path=str(config_loader.user_config_path()),
        fields=_config_editor_fields(),
    )


@router.patch("/diagnostics/config-editor", response_model=DiagnosticsConfigEditorResponse)
async def update_diagnostics_config_editor(
    payload: DiagnosticsConfigEditorUpdate,
    _admin_key: str = Depends(require_admin_key),
) -> DiagnosticsConfigEditorResponse:
    user_config = config_loader.load_user_config()
    if not isinstance(user_config, dict):
        user_config = {}

    if payload.server_environment is not None:
        environment = str(payload.server_environment).strip().lower()
        if environment not in {"development", "production", "test"}:
            raise HTTPException(status_code=422, detail="server_environment must be development, production, or test")
        _deep_set(user_config, ("server", "environment"), environment)

    if payload.database_url is not None:
        database_url = str(payload.database_url).strip()
        if not database_url:
            raise HTTPException(status_code=422, detail="database_url cannot be empty")
        _deep_set(user_config, ("database", "url"), database_url)

    if payload.cors_allowed_origins is not None:
        _deep_set(user_config, ("cors", "allowed_origins"), _normalize_string_list(payload.cors_allowed_origins))

    if payload.api_base_url is not None:
        _deep_set(user_config, ("agent_providers", "api_base_url"), str(payload.api_base_url).strip())

    if payload.web_ui_base_url is not None:
        _deep_set(user_config, ("agent_providers", "web_ui_base_url"), str(payload.web_ui_base_url).strip())

    if payload.clear_execute_token:
        _deep_set(user_config, ("agent_executor", "execute_token"), None)
    elif payload.execute_token is not None and str(payload.execute_token).strip():
        _deep_set(user_config, ("agent_executor", "execute_token"), str(payload.execute_token).strip())

    if payload.execute_token_allow_unauth is not None:
        _deep_set(
            user_config,
            ("agent_executor", "execute_token_allow_unauth"),
            bool(payload.execute_token_allow_unauth),
        )

    if payload.clear_telegram_bot_token:
        _deep_set(user_config, ("telegram", "bot_token"), None)
    elif payload.telegram_bot_token is not None and str(payload.telegram_bot_token).strip():
        _deep_set(user_config, ("telegram", "bot_token"), str(payload.telegram_bot_token).strip())

    if payload.telegram_chat_ids is not None:
        _deep_set(user_config, ("telegram", "chat_ids"), _normalize_string_list(payload.telegram_chat_ids))

    if payload.task_log_dir is not None:
        _deep_set(user_config, ("agent_tasks", "task_log_dir"), str(payload.task_log_dir).strip())

    if payload.runtime_events_path is not None:
        _deep_set(user_config, ("runtime", "events_path"), str(payload.runtime_events_path).strip())

    if payload.friction_events_path is not None:
        _deep_set(user_config, ("friction", "events_path"), str(payload.friction_events_path).strip())

    if payload.live_updates_poll_ms is not None:
        _deep_set(user_config, ("live_updates", "poll_ms"), max(30000, int(payload.live_updates_poll_ms)))

    if payload.live_updates_router_refresh_every_ticks is not None:
        _deep_set(
            user_config,
            ("live_updates", "router_refresh_every_ticks"),
            max(1, int(payload.live_updates_router_refresh_every_ticks)),
        )

    if payload.live_updates_global is not None:
        _deep_set(user_config, ("live_updates", "global"), bool(payload.live_updates_global))

    if payload.runtime_beacon_sample_rate is not None:
        sample_rate = max(0.0, min(1.0, float(payload.runtime_beacon_sample_rate)))
        _deep_set(user_config, ("runtime_beacon", "sample_rate"), sample_rate)

    if payload.health_proxy_failure_threshold is not None:
        _deep_set(
            user_config,
            ("health_proxy", "failure_threshold"),
            max(1, int(payload.health_proxy_failure_threshold)),
        )

    if payload.health_proxy_cooldown_ms is not None:
        _deep_set(
            user_config,
            ("health_proxy", "cooldown_ms"),
            max(1000, int(payload.health_proxy_cooldown_ms)),
        )

    if payload.cli_provider is not None:
        _deep_set(user_config, ("cli", "provider"), str(payload.cli_provider).strip() or "cli")

    if payload.cli_active_task_id is not None:
        _deep_set(user_config, ("cli", "active_task_id"), str(payload.cli_active_task_id).strip() or None)

    config_loader.save_user_config(user_config)
    reset_config_cache()
    return DiagnosticsConfigEditorResponse(
        generated_at=_iso_utc_now(),
        config_path=str(config_loader.user_config_path()),
        fields=_config_editor_fields(),
    )


@router.get("/diagnostics-completeness")
async def get_diagnostics_completeness() -> dict:
    """Diagnostics completeness across all failed tasks."""
    items, _total, _runtime_backfill = list_tasks()
    task_dicts = [dict(task) for task in items if isinstance(task, dict)]
    return failed_task_diagnostics_service.compute_diagnostics_completeness(task_dicts)
