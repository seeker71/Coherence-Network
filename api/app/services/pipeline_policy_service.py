"""Pipeline policy service — data-driven pipeline configuration.

Replaces hardcoded constants in pipeline_advance_service.py and
failure_taxonomy_service.py with DB-backed policies that the pipeline
can read AND update at runtime.

Architecture:
  - DB table `pipeline_policies`: key-value store with JSON values
  - In-memory cache with TTL (60s) to avoid DB hit on every task
  - Code defaults as fallback when DB is empty or unavailable
  - API endpoints for CRUD (see routers/pipeline_policies.py)

AutoAgent-inspired: agents can update policies via the API,
closing the loop between observed outcomes and pipeline behavior.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.services.unified_db import Base

log = logging.getLogger(__name__)


# ============================================================================
# ORM Model
# ============================================================================


class PipelinePolicyRecord(Base):
    __tablename__ = "pipeline_policies"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ============================================================================
# Cache
# ============================================================================

_CACHE_TTL_SECONDS = 60.0
_cache: dict[str, Any] = {}
_cache_loaded_at: float = 0.0
_cache_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def invalidate_cache() -> None:
    global _cache_loaded_at
    with _cache_lock:
        _cache.clear()
        _cache_loaded_at = 0.0


def _refresh_cache_if_stale() -> dict[str, Any]:
    global _cache, _cache_loaded_at
    now = time.monotonic()
    if _cache and (now - _cache_loaded_at) < _CACHE_TTL_SECONDS:
        return _cache
    with _cache_lock:
        # Double-check after acquiring lock
        if _cache and (time.monotonic() - _cache_loaded_at) < _CACHE_TTL_SECONDS:
            return _cache
        try:
            from app.services import unified_db as _udb
            _udb.ensure_schema()
            with _udb.session() as session:
                rows = session.query(PipelinePolicyRecord).all()
                fresh: dict[str, Any] = {}
                for row in rows:
                    try:
                        fresh[row.key] = json.loads(row.value_json)
                    except Exception:
                        fresh[row.key] = row.value_json
                _cache = fresh
                _cache_loaded_at = time.monotonic()
        except Exception:
            # DB unavailable — keep existing cache or empty
            if not _cache:
                _cache = {}
                _cache_loaded_at = time.monotonic()
    return _cache


# ============================================================================
# Code defaults — used when the DB has no value for a key
# ============================================================================


_CODE_DEFAULTS: dict[str, Any] = {
    # Phase chain: maps each phase to its next phase (null = terminal)
    "phase_chain": {
        "spec": "impl",
        "impl": "test",
        "test": "code-review",
        "code-review": "deploy",
        "deploy": "verify-production",
        "verify-production": "reflect",
        "reflect": None,
        "review": None,
        "verify": None,
        "heal": None,
    },
    # Max retries before escalation
    "max_retries": 2,
    # Minimum output characters to consider a task genuinely completed
    "min_output_chars": {
        "spec": 100,
        "impl": 200,
        "test": 100,
        "code-review": 30,
        "deploy": 50,
        "verify-production": 50,
        "reflect": 100,
    },
    # Pass-gate tokens: output must contain this string to advance
    "pass_gate_tokens": {
        "code-review": "CODE_REVIEW_PASSED",
    },
    # Failure classification patterns: list of {regex, bucket, signature, summary, action}
    "failure_patterns": [
        {
            "regex": "refresh_token_reused|failed to refresh token|codex_core::auth.*401 unauthorized",
            "bucket": "auth",
            "signature": "oauth_refresh_token_reused",
            "summary": "OAuth refresh token became invalid/reused; session refresh and relogin path required.",
            "action": "Refresh OAuth session on the runner, then retry with the same task id and preserved context.",
        },
        {
            "regex": "paid provider and agent_allow_paid_providers is disabled",
            "bucket": "paid_provider_blocked",
            "signature": "paid_provider_policy_disabled",
            "summary": "Paid provider route blocked by explicit policy flag.",
            "action": "Route to an allowed OAuth CLI provider or explicitly set paid-provider override when intended.",
        },
        {
            "regex": "paid-provider usage blocked by provider quota policy",
            "bucket": "rate_limit",
            "signature": "paid_provider_quota_blocked",
            "summary": "Paid provider blocked by quota telemetry guard.",
            "action": "Switch to an alternate model/provider with remaining quota and record a cooldown for the exhausted model.",
        },
        {
            "regex": "paid-provider usage blocked by window policy",
            "bucket": "rate_limit",
            "signature": "paid_provider_window_budget_blocked",
            "summary": "Paid provider blocked by configured usage window budget.",
            "action": "Delay until the usage window resets or route to a cheaper model that still has budget.",
        },
        {
            "regex": "unauthorized|forbidden|invalid api key|api key is not configured|status[=: ]40[13]|authentication",
            "bucket": "auth",
            "signature": "auth_unauthorized_or_missing_credentials",
            "summary": "Authentication or authorization failed for required provider/session.",
            "action": "Repair OAuth credentials/session for the target CLI and re-run a readiness check before retrying.",
        },
        {
            "regex": "permission denied|errno 13|operation not permitted|read-only file system",
            "bucket": "permissions",
            "signature": "file_or_runtime_permission_denied",
            "summary": "Runtime permission denied while reading/writing required files or directories.",
            "action": "Fix workspace/runtime permissions (writable paths, ownership, or mount mode) and retry.",
        },
        {
            "regex": "rate limit|too many requests|status[=: ]429|http 429|quota exceeded|insufficient_quota|quota metric|usage exhausted|resource has been exhausted",
            "bucket": "rate_limit",
            "signature": "provider_rate_limit_or_quota",
            "summary": "Provider rate-limit or quota condition blocked execution.",
            "action": "Apply backoff or route to a different model/provider with available quota.",
        },
        {
            "regex": "timeout|timed out|gateway timeout",
            "bucket": "timeout",
            "signature": "timeout_runtime_or_dependency",
            "summary": "Execution timed out before completion.",
            "action": "Reduce task scope, keep one concrete goal, and rerun targeted verification commands.",
        },
        {
            "regex": "merge conflict|rebase|conflict \\(content\\)",
            "bucket": "git_conflict",
            "signature": "git_conflict_or_rebase",
            "summary": "Git conflict or rebase conflict prevented execution progress.",
            "action": "Resolve merge/rebase conflicts in the worktree, then retry from the same task context.",
        },
        {
            "regex": "assertionerror|test failed|pytest",
            "bucket": "test_failure",
            "signature": "test_or_assertion_failure",
            "summary": "Validation/test assertion failed.",
            "action": "Use failing assertion output to patch implementation/spec verification and rerun focused tests.",
        },
        {
            "regex": "command not found|module not found|no module named|no such file or directory",
            "bucket": "dependency_or_tooling",
            "signature": "missing_dependency_or_tool",
            "summary": "Missing dependency/tooling blocked execution.",
            "action": "Install or configure the missing tool/dependency and verify command availability before retry.",
        },
        {
            "regex": "empty direction|validation|status[=: ]422|unprocessable entity",
            "bucket": "validation",
            "signature": "input_validation_failure",
            "summary": "Input validation failed before execution could proceed.",
            "action": "Provide required task inputs (direction, spec path, command contract) and retry.",
        },
        {
            "regex": "model_not_found|model not found|does not have access to model",
            "bucket": "model_not_found",
            "signature": "model_unavailable_or_access_denied",
            "summary": "Requested model was unavailable or access was denied.",
            "action": "Switch to an accessible model and store the remap in model cooldown/selection metadata.",
        },
        {
            "regex": "lease_owner_mismatch|lease_owned_by_other_worker|claim_failed|claim_conflict",
            "bucket": "orchestration",
            "signature": "lease_or_claim_conflict",
            "summary": "Task lease/claim conflict prevented execution.",
            "action": "Wait for existing lease expiry or reclaim with the same worker identity before retrying.",
        },
    ],
    # Error categories that should never be retried
    "no_retry_categories": ["impl_branch_missing", "worktree_failed"],
    # Preferred provider/executor per pipeline phase
    "provider_per_phase": {
        "spec": "claude",
        "impl": "claude",
        "test": "claude",
        "code-review": "claude",
        "deploy": "cursor",
        "verify-production": "cursor",
        "reflect": "claude",
    },
}


# ============================================================================
# Public API — get / set / list
# ============================================================================


def get_policy(key: str, default: Any = None) -> Any:
    """Get a policy value by key.

    Resolution order:
      1. DB-backed cache (refreshed every 60s)
      2. Code defaults
      3. Caller-provided default
    """
    cache = _refresh_cache_if_stale()
    if key in cache:
        return cache[key]
    if key in _CODE_DEFAULTS:
        return _CODE_DEFAULTS[key]
    return default


def set_policy(key: str, value: Any, *, updated_by: str = "system", description: str | None = None) -> dict[str, Any]:
    """Set a policy value. Creates or updates the DB record and invalidates cache."""
    try:
        from app.services import unified_db as _udb
        _udb.ensure_schema()
        now = _now()
        value_str = json.dumps(value, default=str)
        with _udb.session() as session:
            row = session.get(PipelinePolicyRecord, key)
            if row is None:
                row = PipelinePolicyRecord(
                    key=key,
                    value_json=value_str,
                    description=description,
                    updated_by=updated_by,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.value_json = value_str
                row.updated_by = updated_by
                row.updated_at = now
                if description is not None:
                    row.description = description
        invalidate_cache()
        log.info("POLICY_SET key=%s by=%s", key, updated_by)
        return {"key": key, "value": value, "updated_by": updated_by}
    except Exception as e:
        log.warning("POLICY_SET_FAILED key=%s: %s", key, e)
        raise


def delete_policy(key: str) -> bool:
    """Delete a policy (reverts to code default). Returns True if deleted."""
    try:
        from app.services import unified_db as _udb
        _udb.ensure_schema()
        with _udb.session() as session:
            row = session.get(PipelinePolicyRecord, key)
            if row is None:
                return False
            session.delete(row)
        invalidate_cache()
        log.info("POLICY_DELETE key=%s", key)
        return True
    except Exception as e:
        log.warning("POLICY_DELETE_FAILED key=%s: %s", key, e)
        return False


def list_policies() -> list[dict[str, Any]]:
    """List all policies (DB + code defaults merged)."""
    cache = _refresh_cache_if_stale()
    # Start with code defaults
    merged: dict[str, dict[str, Any]] = {}
    for key, value in _CODE_DEFAULTS.items():
        merged[key] = {
            "key": key,
            "value": value,
            "source": "code_default",
            "updated_by": None,
            "updated_at": None,
        }
    # Overlay DB values
    try:
        from app.services import unified_db as _udb
        _udb.ensure_schema()
        with _udb.session() as session:
            rows = session.query(PipelinePolicyRecord).all()
            for row in rows:
                try:
                    val = json.loads(row.value_json)
                except Exception:
                    val = row.value_json
                merged[row.key] = {
                    "key": row.key,
                    "value": val,
                    "source": "database",
                    "description": row.description,
                    "updated_by": row.updated_by,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
    except Exception:
        pass
    return sorted(merged.values(), key=lambda x: x["key"])


def seed_defaults() -> int:
    """Write code defaults to DB for any keys not already present.

    Returns the number of policies seeded. Idempotent — safe to call
    on every startup.
    """
    seeded = 0
    try:
        from app.services import unified_db as _udb
        _udb.ensure_schema()
        now = _now()
        with _udb.session() as session:
            for key, value in _CODE_DEFAULTS.items():
                existing = session.get(PipelinePolicyRecord, key)
                if existing is not None:
                    continue
                session.add(PipelinePolicyRecord(
                    key=key,
                    value_json=json.dumps(value, default=str),
                    description=f"Auto-seeded from code default",
                    updated_by="system:seed",
                    created_at=now,
                    updated_at=now,
                ))
                seeded += 1
        if seeded:
            invalidate_cache()
            log.info("POLICY_SEED seeded %d defaults", seeded)
    except Exception as e:
        log.warning("POLICY_SEED_FAILED: %s", e)
    return seeded


# ============================================================================
# Convenience helpers for specific policy types
# ============================================================================


def get_phase_chain() -> dict[str, str | None]:
    """Get the phase chain mapping (phase → next_phase)."""
    return get_policy("phase_chain", _CODE_DEFAULTS["phase_chain"])


def get_max_retries() -> int:
    """Get the maximum retry count before escalation."""
    return int(get_policy("max_retries", _CODE_DEFAULTS["max_retries"]))


def get_min_output_chars() -> dict[str, int]:
    """Get minimum output character requirements per phase."""
    return get_policy("min_output_chars", _CODE_DEFAULTS["min_output_chars"])


def get_pass_gate_tokens() -> dict[str, str]:
    """Get pass-gate token requirements per phase."""
    return get_policy("pass_gate_tokens", _CODE_DEFAULTS["pass_gate_tokens"])


def get_failure_patterns() -> list[dict[str, str]]:
    """Get failure classification patterns."""
    return get_policy("failure_patterns", _CODE_DEFAULTS["failure_patterns"])


def get_no_retry_categories() -> list[str]:
    """Get error categories that should never be retried."""
    return get_policy("no_retry_categories", _CODE_DEFAULTS["no_retry_categories"])


def get_provider_per_phase() -> dict[str, str]:
    """Get preferred provider/executor per pipeline phase."""
    return get_policy("provider_per_phase", _CODE_DEFAULTS["provider_per_phase"])
