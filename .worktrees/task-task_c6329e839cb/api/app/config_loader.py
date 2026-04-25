"""API configuration loader — single source of truth.

Configuration precedence (deep-merged at load time):
  1. hard-coded defaults from `_default_config()`
  2. api/config/api.json              (checked-in dev defaults)
  3. ~/.coherence-network/config.json (deployment overlay)

No environment variables are read for application config. Production
containers mount `/root/.coherence-network/config.json` as a read-only
volume and put their real database URL, API keys, and environment
string there. Env vars are static at container start, fragmented across
compose + .env + shell, and opaque to the running body; config files
are versioned, deep-merged, discoverable on disk, and can be reloaded
with `reload_config()` without a rebuild. Prefer the config file.

Usage:
    from app.config_loader import api_config, database_url
    db_url = api_config("database", "url")
    api_key = api_config("auth", "api_key")
    db = database_url("agent_tasks")  # falls back to main DB
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CONFIG: dict[str, Any] = {}
_LOADED = False


def _default_agent_config() -> dict[str, Any]:
    return {
        "agent_tasks": {
            "persist": True,
            "use_db": True,
            "path": None,
            "db_reload_ttl_seconds": 1800,
            "output_max_chars": 50000,
            "task_output_max_chars": 4000,
            "retry_max": 3,
            "runtime_fallback_mode": "disabled",
            "runtime_fallback_limit": 100,
            "runtime_fallback_in_tests": False,
            "task_log_dir": "data/task_logs",
            "smart_reap_max_age_minutes": 15,
        },
        "agent_executor": {
            "default": "federation",
            "cheap_default": "federation",
            "repo_default": "federation",
            "open_question_default": "federation",
            "escalate_to": None,
            "policy_enabled": True,
            "allow_unavailable_explicit": False,
            "disable_codex_executor": True,
            "auto_execute": False,
            "executors": [],
            "execute_token": None,
            "execute_token_allow_unauth": False,
            "escalate_failure_threshold": 1,
            "escalate_retry_threshold": 2,
            "allow_paid_providers": True,
            "continuous_autofill": False,
            "continuous_autofill_autorun": False,
        },
        "agent_cost": {
            "max_cost_usd": 2.0,
            "estimated_cost_usd": 0.5,
            "cost_slack_ratio": 1.5,
            "runtime_cost_per_second": 0.002,
            "external_input_cost_per_1k": 0.003,
            "external_output_cost_per_1k": 0.015,
            "allow_paid_providers": True,
            "block_on_soft_quota_threshold": False,
            "paid_tool_8h_limit": None,
            "paid_tool_week_limit": None,
            "paid_tool_window_budget_fraction": 0.333,
        },
        "agent_lifecycle": {
            "jsonl_enabled": False,
            "jsonl_path": None,
            "jsonl_max_lines": 10000,
            "telemetry_enabled": False,
            "subscribers": [],
        },
        "agent_providers": {
            "codex_home": None,
            "codex_oauth_session_file": None,
            "orchestration_policy_path": None,
            "retry_openai_model_override": None,
            "auto_retry_openai_override": False,
            "api_base_url": "https://api.coherencycoin.com",
            "web_ui_base_url": "https://coherencycoin.com",
            "openrouter_chat_url": None,
            "openrouter_http_referer": None,
            "openrouter_x_title": None,
            "openrouter_temperature": 0.2,
            "openrouter_disable_stream": "1",
        },
    }


def _default_runtime_config() -> dict[str, Any]:
    return {
        "automation_usage": {
            "endpoint_cache_max_workers": 4,
            "quality_awareness_ttl_seconds": 300.0,
            "snapshots_path": None,
            "use_db": True,
            "purge_imported_files": True,
            "max_snapshots": 800,
        },
        "persistence_contract": {
            "required": "auto",
        },
        "metrics": {
            "file_path": None,
            "use_db": None,
            "purge_legacy_file": True,
            "max_rows": 50000,
        },
        "pipeline": {
            "orphan_running_seconds": 1800,
            "stale_running_seconds": 1800,
            "monitor_max_age_seconds": 900,
            "status_report_max_age_seconds": 900,
            "pending_actionable_window_seconds": 86400,
            "poll_interval_seconds": 60,
            "concurrency": 1,
        },
        "inventory": {
            "cache_ttl_seconds": 30.0,
            "timing_log_ms": 750.0,
            "timing_enabled": False,
            "project_root": None,
            "tracking_repository": None,
            "tracking_repository_ref": None,
        },
        "ideas": {
            "internal_idea_id_prefixes": None,
            "internal_idea_id_exact": None,
            "internal_idea_interface_tags": None,
            "sync_enable_domain_discovery": None,
            "sync_runtime_window_seconds": 86400,
            "sync_runtime_event_limit": 2000,
            "sync_contribution_limit": 3000,
        },
        "runtime": {
            "events_path": None,
            "idea_map_path": None,
            "agent_tasks_path": None,
            "tool_success_streak_target": 3,
            "endpoint_cache_ttl_seconds": 120.0,
            "endpoint_cache_max_workers": 4,
            "telemetry_enabled": True,
        },
        "friction": {
            "events_path": None,
            "use_db": None,
            "purge_imported_files": "1",
        },
        "monitor": {"issues_path": None},
        "github_actions": {"health_path": None},
        "smart_reap": {
            "runner_liveness_seconds": 270,
            "human_attention_threshold": 3,
        },
    }


def _default_agent_runner_config() -> dict[str, Any]:
    """Defaults for api/scripts/agent_runner.py.

    Previously these 60+ settings were read from AGENT_* environment variables.
    They now live here so they're runtime-modifiable via the config API/CLI/web
    without restarting the runner process — ``reload_config()`` picks up file
    changes between task cycles.

    The key names are 1:1 with the old env var names, lowercased and with the
    ``AGENT_`` prefix stripped.  E.g. ``AGENT_TASK_TIMEOUT`` → ``task_timeout``.
    """
    return {
        "agent_runner": {
            # ── API connection ─────────────────────────────────────────
            "api_base": "http://localhost:8000",
            "http_timeout": 30,
            "http_retries": 3,
            # ── Task execution ─────────────────────────────────────────
            "task_timeout": 3600,
            "pending_task_fetch_limit": 20,
            "max_resume_attempts": 2,
            # ── Heartbeat / lease ──────────────────────────────────────
            "run_heartbeat_seconds": 15,
            "run_lease_seconds": 120,
            "periodic_checkpoint_seconds": 300,
            "control_poll_seconds": 5,
            "diagnostic_timeout_seconds": 120,
            "task_log_tail_chars": 2000,
            "run_records_max": 5000,
            # ── Repository / PR ────────────────────────────────────────
            "worktree_path": None,
            "github_repo": "seeker71/Coherence-Network",
            "pr_base_branch": "main",
            "repo_git_url": None,
            "repo_fallback_path": None,
            "pr_local_check_cmd": None,
            "pr_gate_attempts": 8,
            "pr_gate_poll_seconds": 30,
            "pr_flow_timeout_seconds": 3600,
            # ── Workspace ──────────────────────────────────────────────
            "workspace_id": "",
            # ── Self-update ────────────────────────────────────────────
            "self_update_enabled": True,
            "self_update_repo": None,
            "self_update_branch": None,
            "self_update_min_interval_seconds": 60,
            # ── Rollback ───────────────────────────────────────────────
            "rollback_on_task_failure": True,
            "rollback_on_start_failure": True,
            "rollback_min_interval_seconds": 180,
            # ── Manifests ──────────────────────────────────────────────
            "manifest_enabled": True,
            "manifest_max_blocks": 80,
            "manifest_context_blocks": 20,
            "manifests_dir": None,
            "web_base_url": "",
            # ── Hold-pattern / observation ─────────────────────────────
            "observation_window_sec": 900,
            "hold_pattern_score_threshold": 0.8,
            "hold_pattern_reduced_action_delay_seconds": 120,
            # ── Idea metrics ───────────────────────────────────────────
            "measured_value_target_share": 0.5,
            "idea_measured_cache_ttl_seconds": 300,
            # ── Misc ──────────────────────────────────────────────────
            "min_retry_delay_seconds": 30,
            "diagnostic_cooldown_seconds": 300,
            "max_interventions_per_window": 3,
            "intervention_window_seconds": 900,
            "auto_generate_idle_tasks": True,
            "auto_generate_idle_task_limit": 5,
            "auto_generate_idle_task_cooldown_seconds": 300,
            "provider_telemetry_ttl_seconds": 86400,
            "worker_id": None,
            "run_as_user": None,
            "auto_install_cli": True,
        },
        # ── Auth / provider discovery paths ────────────────────────────
        "agent_auth": {
            "codex_home": None,
            "codex_oauth_session_file": None,
            "claude_config_dir": None,
            "cursor_command": None,
            "gemini_auth_json": None,
        },
        # ── Per-provider command templates ─────────────────────────────
        "command_templates": {
            "claude": None,
            "codex": None,
            "cursor": None,
            "gemini": None,
            "ollama": None,
        },
        # ── TTL cache (app.core.ttl_cache) ────────────────────────────
        "cache": {
            "disabled": False,
        },
        # ── Discord bot ───────────────────────────────────────────────
        "discord": {
            "guild_id": None,
            "commands_channel": "bot-commands",
            "submissions_channel": "idea-submissions",
            "pipeline_channel": "pipeline-feed",
            "active_category": "Active Ideas",
            "archive_category": "Archived Ideas",
            "sync_interval_min": 5,
            "poll_interval_sec": 60,
            "log_level": "info",
            "data_dir": "./data",
        },
    }


def _default_release_config() -> dict[str, Any]:
    return {
        "route_registry": {"canonical_routes_path": None},
        "commit_evidence": {"directory": None},
        "route_evidence": {"probe_directory": None},
        "release_gates": {
            "verification_jobs_path": None,
            "verification_max_attempts": 8,
            "verification_retry_seconds": 60,
            "branch_head_sha_timeout_seconds": 6.0,
            "branch_head_sha_cache_ttl_seconds": 45.0,
            "require_telegram_alerts": False,
            "require_provider_readiness": False,
            "require_api_health_sha": False,
            "require_web_health_proxy_sha": False,
        },
        "deploy_logs_url": None,
        "deployed_sha": None,
        "github_token": None,
    }


def _default_ui_config() -> dict[str, Any]:
    return {
        "web": {
            "api_base_url": "https://api.coherencycoin.com",
            "local_api_base_url": "http://localhost:8000",
            "deployed_sha": None,
            "updated_at": None,
        },
        "live_updates": {
            "poll_ms": 120000,
            "router_refresh_every_ticks": 8,
            "global": False,
            "active_route_prefixes": ["/tasks", "/remote-ops", "/api-health", "/gates"],
            "router_refresh_skip_prefixes": ["/automation"],
        },
        "runtime_beacon": {
            "sample_rate": 0.2,
            "upstream_timeout_ms": 5000,
            "failure_threshold": 3,
            "cooldown_ms": 30000,
        },
        "health_proxy": {
            "failure_threshold": 2,
            "cooldown_ms": 30000,
        },
        "cli": {
            "provider": "cli",
            "active_task_id": None,
        },
    }


def _default_config() -> dict[str, Any]:
    config = {
        "api": {
            "slow_request_ms": 1500.0,
            "testing": False,
            "log_all_requests": False,
        },
        "database": {"url": "sqlite:///data/coherence.db"},
        "database_overrides": {},
        "auth": {"api_key": "dev-key", "admin_key": "dev-admin"},
        "cors": {
            "allowed_origins": [
                "https://coherencycoin.com",
                "https://www.coherencycoin.com",
                "http://localhost:3000",
                "http://localhost:3001",
            ]
        },
        "telegram": {
            "bot_token": None,
            "chat_ids": [],
            "allowed_user_ids": [],
            "failed_alert_max_per_window": 5,
            "failed_alert_window_seconds": 3600,
        },
        "translator": {
            "backend": "libretranslate",
            "libretranslate_url": "https://libretranslate.com",
            "libretranslate_key": None,
            "anthropic_api_key": None,
            "anthropic_api_url": "https://api.anthropic.com/v1/messages",
            "anthropic_model": "claude-haiku-4-5-20251001",
            "timeout_seconds": 120,
        },
        "news": {
            "sources_path": "config/news-sources.json",
            "cache_ttl_seconds": 900,
            "fetch_timeout_seconds": 15.0,
            "user_agent": "CoherenceNetwork/1.0",
        },
        "storage": {
            "graph_store_path": None,
            "idea_portfolio_path": None,
            "value_lineage_path": None,
        },
        "server": {"environment": "development", "enable_hsts": False},
        "data_retention": {
            "hot_days": 7,
            "warm_days": 30,
            "cold_days": 90,
            "backup_dir": "data/retention-backups",
        },
        "contributor_hygiene": {
            "test_email_domains": None,
            "plus_alias_domains": None,
            "email_alias_map": None,
            "internal_email_prefixes": None,
        },
        "governance": {"min_approvals": 1},
        "federation": {"stats_window_days": 7, "bridge_token": None},
        "github": {"token": None, "api_token": None},
    }
    for section_defaults in (
        _default_agent_config(),
        _default_agent_runner_config(),
        _default_runtime_config(),
        _default_release_config(),
        _default_ui_config(),
    ):
        config.update(section_defaults)
    return config


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if str(key).startswith("_"):
            continue
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(existing, value)
        else:
            merged[key] = value
    return merged


def _repo_config_path() -> Path:
    app_dir = Path(__file__).resolve().parent
    api_dir = app_dir.parent
    return api_dir / "config" / "api.json"


def _user_config_path() -> Path:
    return Path.home() / ".coherence-network" / "config.json"


def _find_config_paths() -> list[Path]:
    return [_repo_config_path(), _user_config_path()]


def user_config_path() -> Path:
    return _user_config_path()


def load_user_config() -> dict[str, Any]:
    path = _user_config_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        log.warning("Failed to load user config %s: %s", path, exc)
        return {}


def save_user_config(payload: dict[str, Any]) -> Path:
    path = _user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    reload_config()
    return path


def config_source_report() -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    source_names = ("repo", "user")
    for index, config_path in enumerate(_find_config_paths()):
        exists = config_path.exists()
        report: dict[str, Any] = {
            "source": source_names[index] if index < len(source_names) else f"config_{index}",
            "path": str(config_path),
            "exists": exists,
            "loaded": False,
            "section_count": 0,
            "sections": [],
        }
        if not exists:
            reports.append(report)
            continue
        try:
            with open(config_path, encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                sections = sorted(str(key) for key in payload.keys() if not str(key).startswith("_"))
                report["loaded"] = True
                report["section_count"] = len(sections)
                report["sections"] = sections
        except Exception as exc:
            report["error"] = str(exc)
        reports.append(report)
    return reports


def _load() -> dict[str, Any]:
    global _CONFIG, _LOADED
    if _LOADED:
        return _CONFIG

    defaults = _default_config()

    loaded_any = False
    for config_path in _find_config_paths():
        if not config_path.exists():
            continue
        try:
            with open(config_path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                defaults = _deep_merge_dict(defaults, loaded)
            loaded_any = True
            log.info("API config loaded from %s", config_path)
        except Exception as e:
            log.warning("Failed to load %s: %s. Continuing with lower-precedence defaults.", config_path, e)

    if not loaded_any:
        log.info("No config file found in %s — using defaults", _find_config_paths())

    _CONFIG = defaults

    _LOADED = True
    return _CONFIG


def api_config(section: str, key: str, default: Any = None) -> Any:
    config = _load()
    return config.get(section, {}).get(key, default)


def full_config() -> dict[str, Any]:
    return _load()


def database_url(service: str | None = None) -> str:
    """Resolve the database URL for a domain, or the global default.

    Precedence:
      1. Per-service config override  (config.database_overrides.<service>)
      2. Global config                (config.database.url)
      3. Fallback                     (sqlite:///data/coherence.db)

    Production containers set `database.url` in the mounted overlay
    `/root/.coherence-network/config.json`. Dev uses the sqlite fallback
    (or overrides in their own user config).
    """
    config = _load()
    if service:
        override = config.get("database_overrides", {}).get(service)
        if override:
            return str(override)
    return str(config.get("database", {}).get("url", "sqlite:///data/coherence.db"))


def server_environment() -> str:
    """Resolve the server environment name.

    Reads `config.server.environment`, falling back to `"development"`.
    Production containers set this in the mounted config overlay.
    Callers that need a boolean use
    `app.services.config_service.is_production()`, which delegates here.
    """
    config = _load()
    return str(config.get("server", {}).get("environment", "development"))


def auth_api_key() -> str:
    """Resolve the shared API key used by `require_api_key`.

    Reads `config.auth.api_key`, falling back to `"dev-key"`. Production
    containers set the real key in the mounted config overlay.
    """
    config = _load()
    return str(config.get("auth", {}).get("api_key", "dev-key"))


def auth_admin_key() -> str:
    """Resolve the admin key used for destructive operations.

    Reads `config.auth.admin_key`, falling back to `"dev-admin"`.
    """
    config = _load()
    return str(config.get("auth", {}).get("admin_key", "dev-admin"))


def get_float(section: str, key: str, default: float = 0.0) -> float:
    """Read a float config value."""
    val = api_config(section, key, default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def get_int(section: str, key: str, default: int = 0) -> int:
    """Read an int config value."""
    val = api_config(section, key, default)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def get_bool(section: str, key: str, default: bool = False) -> bool:
    """Read a bool config value."""
    val = api_config(section, key, default)
    if isinstance(val, bool):
        return val
    return str(val).lower().strip() in ("true", "1", "yes", "on")


def get_str(section: str, key: str, default: str = "") -> str:
    """Read a string config value."""
    val = api_config(section, key, default)
    return str(val) if val is not None else default


def get_list(section: str, key: str, default: list | None = None) -> list:
    """Read a list config value."""
    val = api_config(section, key, default or [])
    return val if isinstance(val, list) else default or []


def reload_config() -> None:
    global _LOADED
    _LOADED = False
    _load()


def set_config_value(section: str, key: str, value: Any) -> None:
    """Override one loaded config value without leaving the JSON config path."""
    config = _load()
    section_config = config.setdefault(section, {})
    if not isinstance(section_config, dict):
        section_config = {}
        config[section] = section_config
    section_config[key] = value
