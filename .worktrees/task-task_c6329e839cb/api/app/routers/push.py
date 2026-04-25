"""Web Push router — subscribe, unsubscribe, send.

Three endpoints:
  · GET  /api/push/vapid-public-key  — the browser needs this to subscribe
  · POST /api/push/subscribe         — browser registers after subscribe()
  · POST /api/push/send              — admin-only, triggers a push

The send endpoint uses the existing API-key auth so only authorized
callers can fire pushes to a specific contributor.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.middleware.auth import require_api_key
from app.services import push_subscription_service as push_svc

router = APIRouter()


class SubscriptionIn(BaseModel):
    """Matches the shape the browser's PushManager returns, plus
    optional identity hooks so the server can route pushes to a
    specific contributor or device."""
    subscription: dict = Field(..., description="The browser PushSubscription.toJSON() payload")
    contributor_id: str | None = None
    fingerprint: str | None = None
    user_agent: str | None = None
    locale: str | None = None


class SendIn(BaseModel):
    contributor_id: str | None = None
    fingerprint: str | None = None
    title: str
    body: str
    url: str = "/feed/you"
    icon: str = "/icon.svg"


@router.get(
    "/push/vapid-public-key",
    summary="Return the VAPID public key the browser needs to subscribe",
)
async def get_vapid_public_key() -> dict:
    key = push_svc.vapid_public_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Push notifications are not configured on this server",
        )
    return {"public_key": key, "configured": True}


@router.post(
    "/push/subscribe",
    status_code=201,
    summary="Register a browser's push subscription",
)
async def subscribe(body: SubscriptionIn) -> dict:
    try:
        rec = push_svc.upsert_subscription(
            subscription=body.subscription,
            contributor_id=body.contributor_id,
            fingerprint=body.fingerprint,
            user_agent=body.user_agent,
            locale=body.locale,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "subscription_id": rec["id"]}


class UnsubscribeIn(BaseModel):
    endpoint: str = Field(..., description="The browser's PushSubscription.endpoint URL")


@router.post(
    "/push/unsubscribe",
    summary="Forget a browser's push subscription (called when the user toggles off)",
)
async def unsubscribe(body: UnsubscribeIn) -> dict:
    """Remove the subscription for the given endpoint. Idempotent —
    returns ok even if the row was already gone, since the user's
    intent ("don't push me") doesn't depend on the row's current state.
    """
    removed = push_svc.remove_subscription(endpoint=body.endpoint)
    return {"ok": True, "removed": removed}


@router.post(
    "/push/send",
    summary="Trigger a push to a contributor or device (admin-only)",
)
async def send(body: SendIn, _key: str = Depends(require_api_key)) -> dict:
    if not body.contributor_id and not body.fingerprint:
        raise HTTPException(
            status_code=400,
            detail="Must specify contributor_id or fingerprint",
        )
    if not push_svc.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Push notifications are not configured on this server",
        )
    try:
        return push_svc.send_push(
            contributor_id=body.contributor_id,
            fingerprint=body.fingerprint,
            title=body.title,
            body=body.body,
            url=body.url,
            icon=body.icon,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
