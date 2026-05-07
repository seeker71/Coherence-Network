"""Published field-story artifacts and contribution hooks.

The canonical source lives in ``docs/field/<person>/`` so agents can inspect
the same material through git, API, CLI content views, or MCP tools.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[3]
FIELD_ROOT = REPO_ROOT / "docs" / "field"
CONTRIBUTION_LOG = REPO_ROOT / "api" / "data" / "field_story_contributions.jsonl"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _story_dir_for_slug(slug: str) -> Path:
    for manifest_path in FIELD_ROOT.glob("*/manifest.json"):
        manifest = _load_json(manifest_path)
        if manifest.get("slug") == slug:
            return manifest_path.parent
    raise KeyError(f"Unknown field story: {slug}")


def _load_manifest(story_dir: Path) -> dict[str, Any]:
    manifest = _load_json(story_dir / "manifest.json")
    manifest["artifact_count"] = len(manifest.get("artifacts", []))
    return manifest


def _safe_artifact_path(story_dir: Path, relative_path: str) -> Path:
    candidate = (story_dir / relative_path).resolve()
    root = story_dir.resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Artifact path escapes field story directory")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate


def list_field_stories() -> list[dict[str, Any]]:
    stories: list[dict[str, Any]] = []
    for manifest_path in sorted(FIELD_ROOT.glob("*/manifest.json")):
        manifest = _load_manifest(manifest_path.parent)
        stories.append(
            {
                "slug": manifest["slug"],
                "title": manifest.get("title", ""),
                "contributor_id": manifest.get("contributor_id"),
                "status": manifest.get("status", "published"),
                "summary": manifest.get("summary", ""),
                "artifact_count": manifest.get("artifact_count", 0),
                "web": manifest.get("agent_use", {}).get("web"),
                "read_api": manifest.get("agent_use", {}).get("read_api"),
            }
        )
    return stories


def get_field_story(slug: str, *, include_story: bool = True) -> dict[str, Any]:
    story_dir = _story_dir_for_slug(slug)
    manifest = _load_manifest(story_dir)
    result = dict(manifest)
    if include_story:
        canonical = manifest.get("canonical_story") or {}
        story_path = canonical.get("path")
        result["story_markdown"] = (
            _safe_artifact_path(story_dir, story_path).read_text(encoding="utf-8")
            if story_path
            else ""
        )
    return result


def get_field_story_artifact(slug: str, artifact_id: str) -> dict[str, Any]:
    story_dir = _story_dir_for_slug(slug)
    manifest = _load_manifest(story_dir)
    artifact = next(
        (item for item in manifest.get("artifacts", []) if item.get("artifact_id") == artifact_id),
        None,
    )
    if not artifact:
        raise KeyError(f"Unknown artifact '{artifact_id}' for story '{slug}'")
    path = _safe_artifact_path(story_dir, artifact["path"])
    return {
        "story_slug": slug,
        "artifact": artifact,
        "content": path.read_text(encoding="utf-8"),
    }


def get_field_story_spectrum(slug: str) -> dict[str, Any]:
    story = get_field_story(slug, include_story=False)
    summaries: dict[str, Any] = {}
    for artifact in story.get("artifacts", []):
        if artifact.get("kind") != "summary":
            continue
        content = get_field_story_artifact(slug, artifact["artifact_id"])["content"]
        summaries[artifact["artifact_id"]] = json.loads(content)
    return {
        "slug": slug,
        "frequency_bands": story.get("frequency_bands", []),
        "summaries": summaries,
    }


def record_field_story_contribution(
    *,
    slug: str,
    contributor_id: str,
    artifact_id: str,
    contribution_type: str,
    summary: str,
    content_markdown: str = "",
) -> dict[str, Any]:
    story = get_field_story(slug, include_story=False)
    artifact_ids = {item["artifact_id"] for item in story.get("artifacts", [])}
    if artifact_id not in artifact_ids:
        raise KeyError(f"Unknown artifact '{artifact_id}' for story '{slug}'")

    from app.services import contribution_ledger_service

    now = datetime.now(timezone.utc)
    proposal_id = f"field_story_{uuid4().hex[:12]}"
    ledger = contribution_ledger_service.record_contribution(
        contributor_id=contributor_id,
        contribution_type="field_story_update",
        amount_cc=1.0,
        idea_id="profile-contribution-derived-data",
        metadata={
            "proposal_id": proposal_id,
            "story_slug": slug,
            "artifact_id": artifact_id,
            "contribution_type": contribution_type,
            "summary": summary,
            "content_markdown": content_markdown,
            "recorded_at": now.isoformat(),
        },
    )
    record = {
        "id": proposal_id,
        "story_slug": slug,
        "artifact_id": artifact_id,
        "contributor_id": contributor_id,
        "contribution_type": contribution_type,
        "summary": summary,
        "content_markdown": content_markdown,
        "source_contribution_id": ledger["id"],
        "recorded_at": now.isoformat(),
    }
    CONTRIBUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CONTRIBUTION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record
