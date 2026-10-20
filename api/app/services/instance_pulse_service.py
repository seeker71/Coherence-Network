"""Instance pulse service — each coherence instance shows its own breath.

Federation honors sovereignty: each instance exposes its breath to whoever
chooses to look, but no central monitor controls it. The pulse endpoint is a
window, not a hook. Other instances and external observers can sense an
instance's aliveness without becoming its controller.

"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Index, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.services import unified_db
from app.services.unified_db import Base

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Peer pulse persistence — what we have observed from peers we chose to watch
# ---------------------------------------------------------------------------

class PeerPulseRecord(Base):
    """Most-recent pulse observed from a peer instance.

    Each instance decides which peers to watch via existing federation flows;
    this table holds whatever the (separate) peer-poll job has captured. The
    GET /api/pulse/peers endpoint reads from here without making any outbound
    calls — readers see what the body has chosen to see, nothing forced.
    """

    __tablename__ = "peer_pulse_records"

    peer_instance_id: Mapped[str] = mapped_column(String, primary_key=True)
    last_pulse_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (Index("idx_ppr_observed_at", "observed_at"),)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Peer pulse reads + writes
# ---------------------------------------------------------------------------

def record_peer_pulse(peer_id: str, pulse: dict[str, Any]) -> None:
    """Store an observed pulse from a peer.

    Used by the (out-of-scope) peer-poll job and by tests. Upserts a single
    row per peer — only the most-recent observation is kept.
    """
    import json

    payload = json.dumps(pulse, default=str)
    now = datetime.now(timezone.utc)
    with unified_db.session() as sess:
        existing = sess.get(PeerPulseRecord, peer_id)
        if existing is None:
            sess.add(PeerPulseRecord(
                peer_instance_id=peer_id,
                last_pulse_json=payload,
                observed_at=now,
            ))
        else:
            existing.last_pulse_json = payload
            existing.observed_at = now
        sess.commit()


def list_peer_pulses() -> list[dict[str, Any]]:
    """Return the most-recent observed pulse from each watched peer."""
    import json

    out: list[dict[str, Any]] = []
    try:
        with unified_db.session() as sess:
            rows = sess.query(PeerPulseRecord).order_by(
                PeerPulseRecord.observed_at.desc()
            ).all()
            for row in rows:
                try:
                    pulse = json.loads(row.last_pulse_json or "{}")
                except Exception:
                    pulse = {}
                out.append({
                    "peer_instance_id": row.peer_instance_id,
                    "observed_at": _iso(row.observed_at) if row.observed_at else None,
                    "pulse": pulse,
                })
    except Exception as exc:
        logger.warning("Failed to read peer pulses: %s", exc)
    return out
