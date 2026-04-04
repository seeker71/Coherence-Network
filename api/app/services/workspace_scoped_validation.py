"""Layer 1 guardrails — API-boundary validation for workspace-scoped writes.

These checks run on every POST/PATCH that touches ideas, specs, or tasks.
They enforce that:
  1. The workspace_id resolves to an existing workspace.
  2. The pillar (if provided) is in that workspace's declared taxonomy.
  3. The parent_idea_id (if provided) resolves AND belongs to the same workspace.
  4. The linked idea_id (for specs) resolves AND belongs to the same workspace.

The rules are pure — they raise ``ValidationError`` with a specific ``code``
that routers translate to HTTP 400/404/409. This keeps service-layer code
unchanged while giving every public write path the same protections.

Applicable universally across all agent provider CLIs (claude, codex, cursor,
gemini, openrouter): they all post to the API, so they all pass through here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class ValidationError(Exception):
    """Raised when a workspace-scoped invariant is violated."""

    def __init__(self, code: str, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class IdeaCreateValidationContext:
    """Minimal set of fields needed to validate idea creation."""
    workspace_id: str
    pillar: Optional[str]
    parent_idea_id: Optional[str]


@dataclass(frozen=True)
class SpecCreateValidationContext:
    """Minimal set of fields needed to validate spec creation."""
    workspace_id: str
    idea_id: Optional[str]


def resolve_workspace_id(requested: Optional[str]) -> str:
    """Normalize None/blank to the default workspace id."""
    if not requested or not requested.strip():
        return "coherence-network"
    return requested.strip()


def _workspace_exists(workspace_id: str) -> bool:
    from app.services import workspace_service
    return workspace_service.get_workspace(workspace_id) is not None


def _workspace_pillars(workspace_id: str) -> list[str]:
    from app.services import workspace_service
    return workspace_service.get_pillars_for_workspace(workspace_id)


def _get_idea_workspace(idea_id: str) -> Optional[str]:
    """Return the workspace_id of an idea, or None if the idea doesn't resolve."""
    from app.services import idea_service
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        return None
    return getattr(idea, "workspace_id", None) or "coherence-network"


def validate_idea_create(ctx: IdeaCreateValidationContext) -> None:
    """Enforce workspace-scoped rules on idea creation.

    Raises ``ValidationError`` with specific codes:
      - ``workspace_not_found`` (404)
      - ``pillar_not_in_workspace`` (400)
      - ``parent_idea_not_found`` (404)
      - ``parent_idea_cross_workspace`` (400)
    """
    ws_id = resolve_workspace_id(ctx.workspace_id)

    if not _workspace_exists(ws_id):
        raise ValidationError(
            code="workspace_not_found",
            message=f"Workspace '{ws_id}' does not exist.",
            status=404,
        )

    if ctx.pillar:
        allowed = _workspace_pillars(ws_id)
        # Empty pillar list means the workspace has no declared taxonomy yet —
        # allow any value in that case, otherwise enforce membership.
        if allowed and ctx.pillar not in allowed:
            raise ValidationError(
                code="pillar_not_in_workspace",
                message=(
                    f"Pillar '{ctx.pillar}' is not declared by workspace '{ws_id}'. "
                    f"Allowed: {', '.join(allowed)}."
                ),
                status=400,
            )

    if ctx.parent_idea_id:
        parent_ws = _get_idea_workspace(ctx.parent_idea_id)
        if parent_ws is None:
            raise ValidationError(
                code="parent_idea_not_found",
                message=f"Parent idea '{ctx.parent_idea_id}' does not exist.",
                status=404,
            )
        if parent_ws != ws_id:
            raise ValidationError(
                code="parent_idea_cross_workspace",
                message=(
                    f"Parent idea '{ctx.parent_idea_id}' belongs to workspace "
                    f"'{parent_ws}', not '{ws_id}'. Cross-workspace parenting is "
                    "not permitted."
                ),
                status=400,
            )


def validate_spec_create(ctx: SpecCreateValidationContext) -> None:
    """Enforce workspace-scoped rules on spec creation.

    Raises ``ValidationError`` with specific codes:
      - ``workspace_not_found`` (404)
      - ``linked_idea_not_found`` (404)
      - ``linked_idea_cross_workspace`` (400)
    """
    ws_id = resolve_workspace_id(ctx.workspace_id)

    if not _workspace_exists(ws_id):
        raise ValidationError(
            code="workspace_not_found",
            message=f"Workspace '{ws_id}' does not exist.",
            status=404,
        )

    if ctx.idea_id:
        idea_ws = _get_idea_workspace(ctx.idea_id)
        if idea_ws is None:
            raise ValidationError(
                code="linked_idea_not_found",
                message=f"Linked idea '{ctx.idea_id}' does not exist.",
                status=404,
            )
        if idea_ws != ws_id:
            raise ValidationError(
                code="linked_idea_cross_workspace",
                message=(
                    f"Idea '{ctx.idea_id}' belongs to workspace '{idea_ws}', "
                    f"not '{ws_id}'. Specs must share their idea's workspace."
                ),
                status=400,
            )
