"""MCP registry entries for published field stories."""

from __future__ import annotations

from typing import Any


def _json_safe(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_json_safe(item) for item in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj


def get_field_story_handler(arguments: dict[str, Any]) -> Any:
    from app.services import field_story_service

    slug = str(arguments.get("slug", "urs-field-story"))
    return _json_safe(field_story_service.get_field_story(slug))


def get_field_story_artifact_handler(arguments: dict[str, Any]) -> Any:
    from app.services import field_story_service

    return _json_safe(
        field_story_service.get_field_story_artifact(
            str(arguments.get("slug", "urs-field-story")),
            str(arguments["artifact_id"]),
        )
    )


def contribute_field_story_handler(arguments: dict[str, Any]) -> Any:
    from app.services import field_story_service

    return _json_safe(
        field_story_service.record_field_story_contribution(
            slug=str(arguments.get("slug", "urs-field-story")),
            contributor_id=str(arguments["contributor_id"]),
            artifact_id=str(arguments["artifact_id"]),
            contribution_type=str(arguments.get("contribution_type", "addition")),
            summary=str(arguments["summary"]),
            content_markdown=str(arguments.get("content_markdown", "")),
        )
    )


def get_field_story_trace_handler(arguments: dict[str, Any]) -> Any:
    from app.services import field_story_service

    return _json_safe(
        field_story_service.get_field_story_trace_slice(
            str(arguments.get("slug", "urs-field-story")),
            str(arguments["selector"]),
            str(arguments["value"]),
        )
    )


FIELD_STORY_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_field_story",
        "description": "Read a published field story with canonical narrative, anchors, reports, and agent contribution surfaces.",
        "input_schema": {
            "type": "object",
            "properties": {"slug": {"type": "string", "default": "urs-field-story"}},
        },
        "handler": get_field_story_handler,
    },
    {
        "name": "get_field_story_artifact",
        "description": "Read one artifact from a published field story: anchors, summaries, reports, or event traces.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "default": "urs-field-story"},
                "artifact_id": {"type": "string"},
            },
            "required": ["artifact_id"],
        },
        "handler": get_field_story_artifact_handler,
    },
    {
        "name": "contribute_field_story",
        "description": "Record an attributed correction, addition, or interpretation proposal for a published field story.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "default": "urs-field-story"},
                "contributor_id": {"type": "string"},
                "artifact_id": {"type": "string"},
                "contribution_type": {"type": "string", "default": "addition"},
                "summary": {"type": "string"},
                "content_markdown": {"type": "string"},
            },
            "required": ["contributor_id", "artifact_id", "summary"],
        },
        "handler": contribute_field_story_handler,
    },
    {
        "name": "get_field_story_trace",
        "description": "Read one compact influence trace slice for a field story by month, author, work, significant-work, or concept.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "default": "urs-field-story"},
                "selector": {"type": "string", "enum": ["month", "author", "work", "significant-work", "concept"]},
                "value": {"type": "string"},
            },
            "required": ["selector", "value"],
        },
        "handler": get_field_story_trace_handler,
    },
]
