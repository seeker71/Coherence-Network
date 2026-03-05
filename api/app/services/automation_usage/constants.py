"""Constants and config maps for automation usage service."""

from __future__ import annotations

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

# Overview cache
CACHE_TTL_SECONDS = 1800.0
CACHE_REFRESH_LOCK = threading.Lock()

# Endpoint cache
ENDPOINT_CACHE_NAMESPACE = "automation_endpoint_cache_v1"
ENDPOINT_CACHE_MAX_STALE_SECONDS = 7 * 24 * 60 * 60
ENDPOINT_CACHE_DEFAULT_TTL_SECONDS = 180.0
ENDPOINT_CACHE_REFRESH_FUTURES: dict[str, Future[Any]] = {}
ENDPOINT_CACHE_REFRESH_LOCK = threading.Lock()
ENDPOINT_CACHE_REFRESH_POOL = ThreadPoolExecutor(
    max_workers=max(2, min(int(os.getenv("AUTOMATION_ENDPOINT_CACHE_MAX_WORKERS", "4")), 8)),
    thread_name_prefix="automation-endpoint-cache-refresh",
)

# DB host egress cache
DB_HOST_EGRESS_SAMPLE_CACHE_TTL_SECONDS = 60.0
DB_HOST_EGRESS_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None}

# Codex / runner caches
CODEX_PROVIDER_USAGE_CACHE_TTL_SECONDS = 90.0
RUNNER_PROVIDER_TELEMETRY_CACHE_TTL_SECONDS = 20.0
RUNNER_PROVIDER_TELEMETRY_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "openai": ("openai", "codex", "openai-codex"),
    "claude": ("claude", "anthropic"),
    "cursor": ("cursor",),
    "gemini": ("gemini", "google", "google-gemini", "google_gemini"),
}

# Provider config rules
PROVIDER_CONFIG_RULES: dict[str, dict[str, Any]] = {
    "coherence-internal": {"kind": "internal", "all_of": []},
    "openai-codex": {"kind": "subscription_window", "all_of": []},
    "claude": {"kind": "subscription_window", "all_of": []},
    "claude-code": {"kind": "subscription_window", "all_of": []},
    "gemini": {"kind": "subscription_window", "all_of": []},
    "openai": {"kind": "subscription_window", "all_of": []},
    "github": {"kind": "github", "any_of": ["GITHUB_TOKEN", "GH_TOKEN"]},
    "openrouter": {"kind": "custom", "all_of": ["OPENROUTER_API_KEY"]},
    "anthropic": {"kind": "subscription_window", "all_of": []},
    "cursor": {"kind": "subscription_window", "all_of": []},
    "openclaw": {"kind": "custom", "all_of": ["OPENCLAW_API_KEY"]},
    "railway": {"kind": "custom", "all_of": ["RAILWAY_TOKEN", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE"]},
    "supabase": {"kind": "custom", "any_of": ["SUPABASE_ACCESS_TOKEN", "SUPABASE_TOKEN"]},
    "db-host": {"kind": "custom", "any_of": ["RUNTIME_DATABASE_URL", "DATABASE_URL"]},
}

DEFAULT_REQUIRED_PROVIDERS = ("openai", "claude", "cursor", "gemini", "railway")
DEFAULT_PROVIDER_VALIDATION_REQUIRED = ("openai", "claude", "cursor", "gemini", "railway")

PROVIDER_ALIASES: dict[str, str] = {
    "anthropic": "claude",
    "clawwork": "openclaw",
    "codex": "openai",
    "openai-codex": "openai",
}

PROVIDER_FAMILY_ALIASES: dict[str, str] = {
    "anthropic": "claude",
    "codex": "openai",
    "openai-codex": "openai",
    "claude-code": "claude",
}

READINESS_REQUIRED_PROVIDER_ALLOWLIST = frozenset({"openai", "claude", "cursor", "railway", "gemini"})
OPTIONAL_REQUIRED_PROVIDER_CANDIDATES = ("railway",)
LIMIT_TELEMETRY_REQUIRED_PROVIDER_ALLOWLIST = frozenset({"openai", "claude", "cursor", "gemini"})
LIMIT_COVERAGE_EXCLUDED_PROVIDERS = frozenset({"coherence-internal", "railway"})
LLM_PROVIDER_ALLOWLIST = frozenset({"openai", "claude", "cursor", "gemini"})

CURSOR_SUBSCRIPTION_LIMITS_BY_TIER: dict[str, tuple[int, int]] = {
    "free": (10, 70),
    "pro": (50, 500),
    "pro_plus": (100, 1000),
}

CLAUDE_SUBSCRIPTION_LIMITS_BY_TIER: dict[str, tuple[int, int]] = {
    "free": (10, 70),
    "pro": (45, 315),
    "max": (120, 840),
    "team": (120, 840),
}

GEMINI_SUBSCRIPTION_LIMITS_BY_TIER: dict[str, tuple[int, int]] = {
    "free": (10, 70),
    "pro": (50, 500),
    "advanced": (120, 840),
}

PROVIDER_WINDOW_GUARD_DEFAULT_RATIO_BY_WINDOW: dict[str, float] = {
    "hourly": 0.1,
    "weekly": 0.1,
    "monthly": 0.1,
}

USAGE_ALERT_MESSAGE_MAX_LEN = 480
