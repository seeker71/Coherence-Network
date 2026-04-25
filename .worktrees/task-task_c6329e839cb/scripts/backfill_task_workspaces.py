#!/usr/bin/env python3
"""Backfill agent_tasks.workspace_id from linked idea.context.idea_id.

For every task whose workspace_id is NULL, look up its idea via
context.idea_id and copy the idea's workspace_id. Tasks whose idea
cannot be resolved get "coherence-network" (the default workspace).

Idempotent: rows already populated are skipped. Safe to re-run after
every deploy to catch legacy tasks.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running from repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services import agent_task_store_service  # noqa: E402
from app.services.agent_task_store_service import AgentTaskRecord, _session, ensure_schema  # noqa: E402

DEFAULT_WORKSPACE_ID = "coherence-network"


def _build_idea_workspace_lookup() -> dict[str, str]:
    from app.services import idea_service

    ideas = idea_service._read_ideas(persist_ensures=False)
    lookup: dict[str, str] = {}
    for idea in ideas:
        ws = getattr(idea, "workspace_id", None) or DEFAULT_WORKSPACE_ID
        lookup[str(idea.id)] = str(ws)
    return lookup


def _context_idea_id(context_json: str) -> str:
    if not context_json:
        return ""
    try:
        ctx = json.loads(context_json)
    except Exception:
        return ""
    if not isinstance(ctx, dict):
        return ""
    raw = ctx.get("idea_id")
    return str(raw or "").strip()


def backfill(dry_run: bool = False) -> dict[str, int]:
    if not agent_task_store_service.enabled():
        print("[backfill] agent_task_store_service not enabled (no DB configured)")
        return {"updated": 0, "skipped": 0, "defaulted": 0}
    ensure_schema()
    lookup = _build_idea_workspace_lookup()
    print(f"[backfill] loaded {len(lookup)} ideas for workspace resolution")

    updated = 0
    defaulted = 0
    skipped = 0
    with _session() as session:
        rows = session.query(AgentTaskRecord).filter(AgentTaskRecord.workspace_id.is_(None)).all()
        print(f"[backfill] found {len(rows)} tasks with NULL workspace_id")
        for row in rows:
            idea_id = _context_idea_id(row.context_json or "")
            resolved = lookup.get(idea_id) if idea_id else None
            if not resolved:
                resolved = DEFAULT_WORKSPACE_ID
                defaulted += 1
            else:
                updated += 1
            if not dry_run:
                row.workspace_id = resolved
        if dry_run:
            print(f"[backfill] DRY RUN — would update {updated} matched + {defaulted} defaulted")
            session.rollback()
        else:
            print(f"[backfill] committing {updated} matched + {defaulted} defaulted rows")
    return {"updated": updated, "skipped": skipped, "defaulted": defaulted}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv or os.getenv("DRY_RUN") in {"1", "true", "yes"}
    result = backfill(dry_run=dry)
    print(f"[backfill] done: {result}")
