"""Workspace membership routes — team edges between contributors and workspaces.

Follows the same style as workspaces.py: thin adapter layer over the service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.auth import require_api_key
from app.models.membership import (
    InviteResponse,
    MemberRole,
    MyWorkspacesResponse,
    WorkspaceInvite,
    WorkspaceMember,
    WorkspaceMembersResponse,
)
from app.services import membership_service

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMembersResponse,
    summary="List all members of a workspace",
)
async def list_members(workspace_id: str) -> WorkspaceMembersResponse:
    """List all members of a workspace."""
    try:
        members = membership_service.list_members(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return WorkspaceMembersResponse(
        workspace_id=workspace_id,
        members=[WorkspaceMember(**m) for m in members],
        total=len(members),
    )


@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMember,
    status_code=201,
    summary="Add a contributor directly as a member of a workspace",
)
async def add_member(
    workspace_id: str,
    invite: WorkspaceInvite,
    _api_key: str = Depends(require_api_key),
) -> WorkspaceMember:
    """Add a contributor directly as a member of a workspace."""
    try:
        member = membership_service.add_member(
            workspace_id=workspace_id,
            contributor_id=invite.contributor_id,
            role=invite.role.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return WorkspaceMember(**member)


@router.post(
    "/workspaces/{workspace_id}/invite",
    response_model=InviteResponse,
    status_code=201,
    summary="Invite a contributor to a workspace (status=pending)",
)
async def invite_member(
    workspace_id: str,
    invite: WorkspaceInvite,
    _api_key: str = Depends(require_api_key),
) -> InviteResponse:
    """Invite a contributor to a workspace (status=pending)."""
    try:
        result = membership_service.invite_member(
            workspace_id=workspace_id,
            contributor_id=invite.contributor_id,
            role=invite.role.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return InviteResponse(**result)


@router.post(
    "/workspaces/{workspace_id}/invite/{contributor_id}/accept",
    response_model=WorkspaceMember,
    summary="Accept a pending invite to a workspace",
)
async def accept_invite(
    workspace_id: str,
    contributor_id: str,
    _api_key: str = Depends(require_api_key),
) -> WorkspaceMember:
    """Accept a pending invite to a workspace."""
    try:
        result = membership_service.accept_invite(
            workspace_id=workspace_id,
            contributor_id=contributor_id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return WorkspaceMember(**result)


@router.delete(
    "/workspaces/{workspace_id}/members/{contributor_id}",
    status_code=204,
    summary="Remove a contributor from a workspace",
)
async def remove_member(
    workspace_id: str,
    contributor_id: str,
    _api_key: str = Depends(require_api_key),
):
    """Remove a contributor from a workspace."""
    removed = membership_service.remove_member(workspace_id, contributor_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Membership not found")
    return None


@router.get(
    "/contributors/{contributor_id}/workspaces",
    response_model=MyWorkspacesResponse,
    summary="List all workspaces a contributor belongs to",
)
async def list_workspaces_for_contributor(
    contributor_id: str,
) -> MyWorkspacesResponse:
    """List all workspaces a contributor belongs to."""
    workspaces = membership_service.list_workspaces_for_contributor(contributor_id)
    return MyWorkspacesResponse(
        workspaces=workspaces,
        total=len(workspaces),
    )


@router.get(
    "/workspaces/{workspace_id}/members/{contributor_id}",
    summary="Get a contributor's role in a workspace",
)
async def get_member_role(workspace_id: str, contributor_id: str):
    """Get a contributor's role in a workspace."""
    role = membership_service.get_member_role(workspace_id, contributor_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    return {"workspace_id": workspace_id, "contributor_id": contributor_id, "role": role}
