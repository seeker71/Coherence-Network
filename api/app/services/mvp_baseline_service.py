"""Helpers for local MVP baseline artifact discovery."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min


def list_local_mvp_baselines(limit: int = 20) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    root = _repo_root() / "docs" / "system_audit"
    files = sorted(root.glob("mvp_acceptance_*.json"), reverse=True)

    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        out.append(
            {
                "file": str(path.relative_to(_repo_root())),
                "generated_at_utc": payload.get("generated_at_utc"),
                "run_id": payload.get("run_id"),
                "branch": payload.get("branch"),
                "origin_main_sha": payload.get("origin_main_sha"),
                "validation_scope": payload.get("validation_scope"),
                "result": payload.get("result"),
                "check_count": len((payload.get("checks") or {}).get("api", {}))
                + len((payload.get("checks") or {}).get("web", {})),
            }
        )

    out.sort(key=lambda row: _parse_iso(str(row.get("generated_at_utc") or "")), reverse=True)
    clipped = out[: max(1, min(limit, 100))]
    return {"count": len(clipped), "runs": clipped}
