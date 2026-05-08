"""Influence teaching translator for field story traces."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import field_story_service, organism_influence_cc_service


SCHEMA_VERSION = "influence-teaching-translator/v1"


def get_influence_teaching_translator(slug: str, *, limit: int = 40) -> dict[str, Any]:
    """Return lesson/frequency/network-shape shards joined with current CC."""

    limit = max(1, min(int(limit), 250))
    story_dir = field_story_service._story_dir_for_slug(slug)  # noqa: SLF001
    artifact = _load_json(story_dir / "trace" / "influence_teaching_translator.json")
    cc = organism_influence_cc_service.compute_organism_influence_cc(slug, limit=250, cc_pool=1000.0)
    cc_by_id = {row["influencer_id"]: row for row in cc.get("top_influencers", [])}

    rows = []
    for row in artifact.get("rows", []):
        merged = dict(row)
        cc_row = cc_by_id.get(str(row.get("influencer_id", "")))
        if cc_row:
            merged["current_cc"] = cc_row.get("computed_cc", 0.0)
            merged["cc_rank"] = cc_row.get("rank")
            merged["cc_pool_id"] = cc_row.get("pool_id")
        else:
            merged["current_cc"] = 0.0
            merged["cc_rank"] = None
            merged["cc_pool_id"] = None
        rows.append(merged)

    rows.sort(key=lambda item: (-(float(item.get("current_cc") or 0.0)), str(item.get("name", "")).lower()))
    coverage_kinds = sorted({str(row.get("kind")) for row in rows if row.get("kind")})
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": artifact.get("policy_id", "influence-teaching-translator:v1"),
        "story_slug": slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_crypto_root": artifact.get("source_crypto_root", ""),
        "coverage_boundary": artifact.get("coverage_boundary", ""),
        "row_shape": artifact.get("row_shape", ""),
        "totals": {
            "available_rows": len(rows),
            "returned_count": min(limit, len(rows)),
            "joined_cc_rows": sum(1 for row in rows if row.get("current_cc")),
            "coverage_kinds": coverage_kinds,
        },
        "rows": rows[:limit],
        "dynamic_access": {
            "api": f"/api/field-stories/{slug}/influence-teaching-translator",
            "mcp_tool": "get_influence_teaching_translator",
            "artifact": f"/api/field-stories/{slug}/artifacts/trace-influence-teaching-translator",
            "cc": f"/api/field-stories/{slug}/organism-influence-cc",
        },
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
