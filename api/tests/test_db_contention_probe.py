"""Stone: the DB write-lane contention leading-indicator (2026-07-02).

Completes the wedge-fix arc. After closing the wedge (DB timeouts + atomic
count bump), this probe lets a monitor SEE lock contention building before it
bites — the oldest open transaction's age and the count of lock-waiters. On
sqlite (the test backend) there is no pg_stat_activity, so it returns nulls
gracefully with backend='sqlite' and healthy=True.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_db_contention_probe_shape_on_sqlite():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/health/db-contention")
    assert r.status_code == 200, r.text
    body = r.json()
    # stable shape a monitor can rely on
    for key in ("timestamp", "backend", "max_txn_age_seconds", "lock_waiters", "healthy"):
        assert key in body
    # sqlite has no pg_stat_activity: metrics are null, backend named honestly,
    # and 'healthy' is True (no pg lock contention is possible on sqlite).
    assert body["backend"] == "sqlite"
    assert body["max_txn_age_seconds"] is None
    assert body["lock_waiters"] is None
    assert body["healthy"] is True
