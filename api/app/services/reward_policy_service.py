"""Reward policy service — community-configurable reward formulas.

Each community (workspace) decides its own reward formulas. The system
ships with sensible defaults; communities override whatever they want.

Architecture follows the pipeline_policy_service pattern:
  - DB table `reward_policies`: workspace-scoped key-value store
  - In-memory cache with TTL (60s), keyed by workspace_id
  - Code defaults as fallback
  - Every reward event records which policy version produced it (traceability)

Policy keys:
  discovery.view_reward_cc         — CC per qualified view referral
  discovery.transaction_fee_rate   — fraction of transaction CC to referrer
  discovery.max_view_rewards_daily — daily cap per referrer
  distribution.contribution_weight — how contributions weight payouts
  distribution.coherence_bonus     — bonus for high coherence score
  staking.cooldown_tiers           — unstake cooldown per amount tier
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


class RewardPolicyRecord(Base):
    """Workspace-scoped reward policy. One row per workspace per key."""
    __tablename__ = "reward_policies"

    workspace_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    # version counter for traceability — every update increments
    version: Mapped[int] = mapped_column(default=1)


# ============================================================================
# Cache — workspace-scoped
# ============================================================================

_CACHE_TTL_SECONDS = 60.0
# {workspace_id: {key: value}}
_cache: dict[str, dict[str, Any]] = {}
_cache_loaded_at: dict[str, float] = {}
_cache_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def invalidate_cache(workspace_id: str | None = None) -> None:
    """Invalidate cache for a workspace, or all workspaces."""
    with _cache_lock:
        if workspace_id:
            _cache.pop(workspace_id, None)
            _cache_loaded_at.pop(workspace_id, None)
        else:
            _cache.clear()
            _cache_loaded_at.clear()


def _refresh_cache_if_stale(workspace_id: str) -> dict[str, Any]:
    now = time.monotonic()
    loaded_at = _cache_loaded_at.get(workspace_id, 0.0)
    if workspace_id in _cache and (now - loaded_at) < _CACHE_TTL_SECONDS:
        return _cache[workspace_id]

    with _cache_lock:
        loaded_at = _cache_loaded_at.get(workspace_id, 0.0)
        if workspace_id in _cache and (time.monotonic() - loaded_at) < _CACHE_TTL_SECONDS:
            return _cache[workspace_id]
        try:
            from app.services import unified_db as _udb
            _udb.ensure_schema()
            with _udb.session() as session:
                rows = session.query(RewardPolicyRecord).filter_by(
                    workspace_id=workspace_id,
                ).all()
                fresh: dict[str, Any] = {}
                for row in rows:
                    try:
                        fresh[row.key] = json.loads(row.value_json)
                    except Exception:
                        fresh[row.key] = row.value_json
                _cache[workspace_id] = fresh
                _cache_loaded_at[workspace_id] = time.monotonic()
        except Exception:
            if workspace_id not in _cache:
                _cache[workspace_id] = {}
                _cache_loaded_at[workspace_id] = time.monotonic()
    return _cache.get(workspace_id, {})


# ============================================================================
# Code defaults — community starting point, overridable per workspace
# ============================================================================

_CODE_DEFAULTS: dict[str, Any] = {
    # --- Discovery rewards ---
    "discovery.view_reward_cc": {
        "value": 0.01,
        "unit": "CC",
        "description": "CC earned per qualified view referral",
    },
    "discovery.transaction_fee_rate": {
        "value": 0.02,
        "unit": "fraction",
        "description": "Fraction of transaction CC awarded to the referrer (e.g. 0.02 = 2%)",
    },
    "discovery.max_view_rewards_daily": {
        "value": 100,
        "unit": "count",
        "description": "Maximum view rewards a single referrer can earn per day",
    },

    # --- Contribution distribution ---
    "distribution.contribution_weight_formula": {
        "value": "cost * (0.5 + coherence_score)",
        "description": "Formula for weighting contributor payouts. Variables: cost, coherence_score",
    },
    "distribution.coherence_bonus_threshold": {
        "value": 0.9,
        "unit": "score",
        "description": "Coherence score above which contributors receive a bonus multiplier",
    },
    "distribution.coherence_bonus_multiplier": {
        "value": 1.25,
        "unit": "multiplier",
        "description": "Multiplier applied to contributions with coherence above threshold",
    },

    # --- Staking ---
    "staking.cooldown_tiers": {
        "value": [
            {"max_cc": 100, "hours": 0, "label": "Instant"},
            {"max_cc": 1000, "hours": 24, "label": "1 day"},
            {"max_cc": None, "hours": 72, "label": "3 days"},
        ],
        "description": "Unstaking cooldown periods by CC amount tier",
    },

    # --- View tracking ---
    "views.sensing_sample_rate": {
        "value": 10,
        "unit": "1-in-N",
        "description": "Sample rate for tier-2 (sampled) asset read sensing",
    },
    "views.full_promote_threshold": {
        "value": 100,
        "unit": "reads",
        "description": "Reads required before an asset promotes from sampled to full tracking",
    },
}

# Default workspace for communities that haven't customized
DEFAULT_WORKSPACE = "coherence-network"


# ============================================================================
# Public API
# ============================================================================


def get_policy(key: str, workspace_id: str = DEFAULT_WORKSPACE, default: Any = None) -> Any:
    """Get a reward policy value for a workspace.

    Resolution order:
      1. Workspace-specific DB override
      2. Default workspace DB override (if different workspace)
      3. Code defaults
      4. Caller-provided default
    """
    # Check workspace-specific
    ws_cache = _refresh_cache_if_stale(workspace_id)
    if key in ws_cache:
        return ws_cache[key]

    # Fall through to default workspace if this is a different workspace
    if workspace_id != DEFAULT_WORKSPACE:
        default_cache = _refresh_cache_if_stale(DEFAULT_WORKSPACE)
        if key in default_cache:
            return default_cache[key]

    # Code defaults
    if key in _CODE_DEFAULTS:
        return _CODE_DEFAULTS[key]

    return default


def get_policy_value(key: str, workspace_id: str = DEFAULT_WORKSPACE) -> Any:
    """Get just the 'value' field of a policy (unwraps the envelope).

    Most policies are stored as {value: X, unit: Y, description: Z}.
    This returns X directly for use in calculations.
    """
    policy = get_policy(key, workspace_id)
    if isinstance(policy, dict) and "value" in policy:
        return policy["value"]
    return policy


def set_policy(
    key: str,
    value: Any,
    workspace_id: str = DEFAULT_WORKSPACE,
    *,
    updated_by: str = "community",
    description: str | None = None,
) -> dict[str, Any]:
    """Set a reward policy for a workspace. Creates or updates."""
    try:
        from app.services import unified_db as _udb
        _udb.ensure_schema()
        now = _now()
        value_str = json.dumps(value, default=str)

        with _udb.session() as session:
            row = session.query(RewardPolicyRecord).filter_by(
                workspace_id=workspace_id, key=key,
            ).first()

            if row is None:
                row = RewardPolicyRecord(
                    workspace_id=workspace_id,
                    key=key,
                    value_json=value_str,
                    description=description,
                    updated_by=updated_by,
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
                session.add(row)
            else:
                row.value_json = value_str
                row.updated_by = updated_by
                row.updated_at = now
                row.version = (row.version or 0) + 1
                if description is not None:
                    row.description = description

            version = row.version
            session.commit()

        invalidate_cache(workspace_id)
        log.info(
            "REWARD_POLICY_SET workspace=%s key=%s by=%s version=%d",
            workspace_id, key, updated_by, version,
        )
        return {
            "workspace_id": workspace_id,
            "key": key,
            "value": value,
            "version": version,
            "updated_by": updated_by,
        }
    except Exception as e:
        log.warning("REWARD_POLICY_SET_FAILED workspace=%s key=%s: %s", workspace_id, key, e)
        raise


def delete_policy(key: str, workspace_id: str = DEFAULT_WORKSPACE) -> bool:
    """Delete a workspace policy (reverts to code default)."""
    try:
        from app.services import unified_db as _udb
        _udb.ensure_schema()
        with _udb.session() as session:
            row = session.query(RewardPolicyRecord).filter_by(
                workspace_id=workspace_id, key=key,
            ).first()
            if row is None:
                return False
            session.delete(row)
            session.commit()
        invalidate_cache(workspace_id)
        log.info("REWARD_POLICY_DELETE workspace=%s key=%s", workspace_id, key)
        return True
    except Exception as e:
        log.warning("REWARD_POLICY_DELETE_FAILED: %s", e)
        return False


def list_policies(workspace_id: str = DEFAULT_WORKSPACE) -> list[dict[str, Any]]:
    """List all reward policies for a workspace (DB merged with defaults)."""
    merged: dict[str, dict[str, Any]] = {}

    # Start with code defaults
    for key, value in _CODE_DEFAULTS.items():
        merged[key] = {
            "workspace_id": workspace_id,
            "key": key,
            "value": value,
            "source": "code_default",
            "version": 0,
            "updated_by": None,
            "updated_at": None,
        }

    # Overlay DB values
    try:
        from app.services import unified_db as _udb
        _udb.ensure_schema()
        with _udb.session() as session:
            # Get default workspace policies first
            if workspace_id != DEFAULT_WORKSPACE:
                default_rows = session.query(RewardPolicyRecord).filter_by(
                    workspace_id=DEFAULT_WORKSPACE,
                ).all()
                for row in default_rows:
                    try:
                        val = json.loads(row.value_json)
                    except Exception:
                        val = row.value_json
                    merged[row.key] = {
                        "workspace_id": DEFAULT_WORKSPACE,
                        "key": row.key,
                        "value": val,
                        "source": "default_workspace",
                        "version": row.version,
                        "description": row.description,
                        "updated_by": row.updated_by,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }

            # Then workspace-specific overrides
            ws_rows = session.query(RewardPolicyRecord).filter_by(
                workspace_id=workspace_id,
            ).all()
            for row in ws_rows:
                try:
                    val = json.loads(row.value_json)
                except Exception:
                    val = row.value_json
                merged[row.key] = {
                    "workspace_id": workspace_id,
                    "key": row.key,
                    "value": val,
                    "source": "community_override",
                    "version": row.version,
                    "description": row.description,
                    "updated_by": row.updated_by,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
    except Exception:
        pass

    return sorted(merged.values(), key=lambda x: x["key"])


def get_policy_snapshot(workspace_id: str = DEFAULT_WORKSPACE) -> dict[str, Any]:
    """Get a frozen snapshot of all active policies for traceability.

    This is what gets embedded in every reward event so anyone can
    verify: "this reward was calculated using these exact formulas
    at this moment."
    """
    policies = list_policies(workspace_id)
    return {
        "workspace_id": workspace_id,
        "snapshot_at": _now().isoformat(),
        "policies": {
            p["key"]: {
                "value": p["value"],
                "source": p["source"],
                "version": p.get("version", 0),
            }
            for p in policies
        },
    }


def seed_defaults(workspace_id: str = DEFAULT_WORKSPACE) -> int:
    """Write code defaults to DB for any keys not already present. Idempotent."""
    seeded = 0
    try:
        from app.services import unified_db as _udb
        _udb.ensure_schema()
        now = _now()
        with _udb.session() as session:
            for key, value in _CODE_DEFAULTS.items():
                existing = session.query(RewardPolicyRecord).filter_by(
                    workspace_id=workspace_id, key=key,
                ).first()
                if existing is not None:
                    continue
                session.add(RewardPolicyRecord(
                    workspace_id=workspace_id,
                    key=key,
                    value_json=json.dumps(value, default=str),
                    description=value.get("description") if isinstance(value, dict) else None,
                    updated_by="system:seed",
                    created_at=now,
                    updated_at=now,
                    version=1,
                ))
                seeded += 1
            session.commit()
        if seeded:
            invalidate_cache(workspace_id)
            log.info("REWARD_POLICY_SEED workspace=%s seeded=%d", workspace_id, seeded)
    except Exception as e:
        log.warning("REWARD_POLICY_SEED_FAILED: %s", e)
    return seeded
