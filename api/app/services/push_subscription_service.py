"""Web Push subscription storage + send.

Flow:
  1. Client calls /api/push/vapid-public-key → gets the public key
  2. Client registers a service worker, calls pushManager.subscribe() with
     the VAPID public key, sends the resulting PushSubscription JSON +
     its contributor_id (or fingerprint) to /api/push/subscribe
  3. Server stores the subscription in push_subscriptions table
  4. Server can send a push via send_push(contributor_id, body)

VAPID keys live in ~/.coherence-network/keys.json or env vars so the
private key is never in git.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pywebpush import WebPushException, webpush
from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base

log = logging.getLogger("coherence.push")


class PushSubscriptionRecord(Base):
    """One browser's push subscription, tied loosely to a contributor.

    The subscription JSON contains endpoint + keys (p256dh, auth) that
    the browser generates; we store it verbatim and replay it when we
    want to send a push.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    contributor_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    fingerprint: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # The endpoint URL doubles as a natural uniqueness key — the browser
    # returns the same endpoint for a given subscription until it is
    # rotated or revoked.
    endpoint: Mapped[str] = mapped_column(String, nullable=False, index=True)
    subscription_json: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    locale: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


def _session():
    return _udb.session()


def _ensure_schema() -> None:
    _udb.engine()


# ---------------------------------------------------------------------------
# VAPID key loading
# ---------------------------------------------------------------------------

_VAPID_CACHE: dict[str, str] | None = None


def _load_vapid() -> dict[str, str]:
    """Load VAPID keys from config. Prefer mounted keystore, fall back to
    env vars. Returns {'public': <base64url>, 'private': <PEM>, 'subject': <mailto>}.

    Never logs the private key. Returns an empty dict if keys aren't set
    so push endpoints can respond with a clear "not configured" error
    rather than a traceback.
    """
    global _VAPID_CACHE
    if _VAPID_CACHE is not None:
        return _VAPID_CACHE

    keys: dict[str, str] = {}
    keystore_path = Path.home() / ".coherence-network" / "keys.json"
    if keystore_path.exists():
        try:
            data = json.loads(keystore_path.read_text())
            vp = data.get("vapid") or {}
            if isinstance(vp, dict):
                if vp.get("public"):
                    keys["public"] = vp["public"]
                if vp.get("private"):
                    keys["private"] = vp["private"]
                if vp.get("subject"):
                    keys["subject"] = vp["subject"]
        except Exception as e:
            log.warning("vapid: keystore read failed: %s", type(e).__name__)

    # Env-var overrides (allow the VPS to inject via docker compose)
    if os.environ.get("VAPID_PUBLIC_KEY"):
        keys["public"] = os.environ["VAPID_PUBLIC_KEY"]
    if os.environ.get("VAPID_PRIVATE_KEY"):
        # Accept either a PEM (with \n literals) or a path to a PEM file
        val = os.environ["VAPID_PRIVATE_KEY"]
        if val.strip().startswith("-----BEGIN"):
            keys["private"] = val.replace("\\n", "\n")
        elif Path(val).exists():
            try:
                keys["private"] = Path(val).read_text()
            except Exception:
                pass
    if os.environ.get("VAPID_SUBJECT"):
        keys["subject"] = os.environ["VAPID_SUBJECT"]

    if "subject" not in keys:
        keys["subject"] = "mailto:push@coherencycoin.com"

    _VAPID_CACHE = keys
    return keys


def vapid_public_key() -> str | None:
    """Safe to expose to clients — the browser needs this to subscribe."""
    return _load_vapid().get("public")


def is_configured() -> bool:
    keys = _load_vapid()
    return bool(keys.get("public") and keys.get("private"))


# ---------------------------------------------------------------------------
# Subscription storage
# ---------------------------------------------------------------------------


def upsert_subscription(
    *,
    subscription: dict,
    contributor_id: Optional[str] = None,
    fingerprint: Optional[str] = None,
    user_agent: Optional[str] = None,
    locale: Optional[str] = None,
) -> dict:
    """Store (or refresh) a browser's push subscription."""
    _ensure_schema()
    endpoint = (subscription or {}).get("endpoint")
    if not endpoint:
        raise ValueError("subscription.endpoint is required")
    payload = json.dumps(subscription)
    with _session() as s:
        existing = s.execute(
            select(PushSubscriptionRecord).where(PushSubscriptionRecord.endpoint == endpoint)
        ).scalar_one_or_none()
        if existing:
            existing.subscription_json = payload
            existing.contributor_id = contributor_id or existing.contributor_id
            existing.fingerprint = fingerprint or existing.fingerprint
            existing.user_agent = user_agent or existing.user_agent
            existing.locale = locale or existing.locale
            s.commit()
            s.refresh(existing)
            return _to_dict(existing)
        rec = PushSubscriptionRecord(
            id=uuid4().hex,
            contributor_id=contributor_id,
            fingerprint=fingerprint,
            endpoint=endpoint,
            subscription_json=payload,
            user_agent=user_agent,
            locale=locale,
        )
        s.add(rec)
        s.commit()
        s.refresh(rec)
        return _to_dict(rec)


def _to_dict(rec: PushSubscriptionRecord) -> dict:
    return {
        "id": rec.id,
        "contributor_id": rec.contributor_id,
        "fingerprint": rec.fingerprint,
        "endpoint": rec.endpoint,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "locale": rec.locale,
    }


def subscriptions_for(
    contributor_id: Optional[str] = None,
    fingerprint: Optional[str] = None,
) -> list[dict]:
    _ensure_schema()
    with _session() as s:
        q = select(PushSubscriptionRecord)
        if contributor_id:
            q = q.where(PushSubscriptionRecord.contributor_id == contributor_id)
        elif fingerprint:
            q = q.where(PushSubscriptionRecord.fingerprint == fingerprint)
        else:
            return []
        rows = s.execute(q).scalars().all()
    return [
        {**_to_dict(r), "subscription_json": r.subscription_json} for r in rows
    ]


# ---------------------------------------------------------------------------
# Send a push
# ---------------------------------------------------------------------------


def send_push(
    *,
    contributor_id: Optional[str] = None,
    fingerprint: Optional[str] = None,
    title: str,
    body: str,
    url: str = "/feed/you",
    icon: str = "/icon.svg",
) -> dict:
    """Send a push to every subscription matching the selector.

    Returns {sent, failed, endpoints_removed} — any 404/410 endpoint is
    treated as a rotated subscription and pruned.
    """
    keys = _load_vapid()
    if not (keys.get("public") and keys.get("private")):
        raise RuntimeError("VAPID keys not configured")

    subs = subscriptions_for(contributor_id=contributor_id, fingerprint=fingerprint)
    if not subs:
        return {"sent": 0, "failed": 0, "endpoints_removed": 0, "note": "no subscriptions"}

    sent = 0
    failed = 0
    removed = 0
    payload = json.dumps({"title": title, "body": body, "url": url, "icon": icon})

    for s in subs:
        try:
            webpush(
                subscription_info=json.loads(s["subscription_json"]),
                data=payload,
                vapid_private_key=keys["private"],
                vapid_claims={"sub": keys["subject"]},
            )
            sent += 1
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                # Subscription is gone — drop it
                _ensure_schema()
                with _session() as db:
                    rec = db.execute(
                        select(PushSubscriptionRecord).where(
                            PushSubscriptionRecord.endpoint == s["endpoint"]
                        )
                    ).scalar_one_or_none()
                    if rec:
                        db.delete(rec)
                        db.commit()
                        removed += 1
            else:
                log.warning("push send failed: status=%s type=%s", status, type(e).__name__)
                failed += 1
        except Exception as e:
            log.warning("push send failed: %s", type(e).__name__)
            failed += 1

    return {"sent": sent, "failed": failed, "endpoints_removed": removed}
