"""Load executor list, aliases, and per-executor keys from config. No hardcoded models or executor names in code."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_CACHE: dict[str, Any] | None = None


def _config_path() -> Path:
    env_value = os.environ.get("EXECUTOR_ROUTING_CONFIG_PATH", "").strip()
    if env_value:
        return Path(env_value)
    for base in [
        Path(__file__).resolve().parents[3] / "config" / "executor_routing.json",
        Path(__file__).resolve().parents[2] / "config" / "executor_routing.json",
    ]:
        if base.exists():
            return base
    return Path(__file__).resolve().parents[2] / "config" / "executor_routing.json"


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    path = _config_path()
    if not path.exists():
        _CACHE = {
            "executors": [],
            "executor_aliases": {},
            "runner_auth_context_key_by_executor": {},
            "model_prefix_by_executor": {},
        }
        return _CACHE
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        _CACHE = {
            "executors": [],
            "executor_aliases": {},
            "runner_auth_context_key_by_executor": {},
            "model_prefix_by_executor": {},
        }
        return _CACHE
    if not isinstance(data, dict):
        _CACHE = {"executors": [], "executor_aliases": {}, "runner_auth_context_key_by_executor": {}, "model_prefix_by_executor": {}}
        return _CACHE
    _CACHE = {
        "executors": data.get("executors") if isinstance(data.get("executors"), list) else [],
        "executor_aliases": data.get("executor_aliases") if isinstance(data.get("executor_aliases"), dict) else {},
        "runner_auth_context_key_by_executor": data.get("runner_auth_context_key_by_executor") if isinstance(data.get("runner_auth_context_key_by_executor"), dict) else {},
        "model_prefix_by_executor": data.get("model_prefix_by_executor") if isinstance(data.get("model_prefix_by_executor"), dict) else {},
    }
    return _CACHE


def reset_executor_routing_cache() -> None:
    global _CACHE
    _CACHE = None


def get_executors() -> tuple[str, ...]:
    return tuple(_load()["executors"])


def get_executor_aliases() -> dict[str, str]:
    return dict(_load()["executor_aliases"])


def get_runner_auth_context_key(executor: str) -> str | None:
    key = (_load()["runner_auth_context_key_by_executor"] or {}).get(executor)
    return str(key).strip() if key else None


def get_model_prefix(executor: str) -> str:
    prefix = (_load()["model_prefix_by_executor"] or {}).get(executor)
    return str(prefix) if prefix is not None else ""
