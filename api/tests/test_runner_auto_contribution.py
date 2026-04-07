"""Tests for runner auto-contribution spec.

Covers:
  1. _auto_record_contribution idempotency key
  2. Retry queue on POST failure
  3. Partial contributions for failed/timed-out tasks
  4. GET /api/contributions/ledger/{contributor_id} auto_only filter
  5. GET /api/contributions/ledger/{contributor_id} since filter
  6. DIF score multiplier on amount_cc
  7. _NODE_ID in metadata.node_id
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import contribution_ledger_service

BASE = "http://test"


def _uid(prefix: str = "test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Unit tests for _auto_record_contribution logic
# ---------------------------------------------------------------------------


def _make_task(
    task_type: str = "impl",
    idea_id: str = "",
    dif_score: float | None = None,
    attempt_number: int = 1,
) -> dict:
    """Build a minimal task dict that _auto_record_contribution accepts."""
    ctx: dict = {}
    if idea_id:
        ctx["idea_id"] = idea_id
    if dif_score is not None:
        ctx["dif_score"] = dif_score
    ctx["attempt_number"] = attempt_number
    return {
        "id": _uid("task"),
        "task_type": task_type,
        "context": ctx,
    }


class TestAutoRecordContributionUnit:
    """Direct unit tests against the _auto_record_contribution function.

    These tests monkey-patch the ``api()`` helper used by the runner to
    capture the payload without hitting a real API.
    """

    def test_idempotency_key_format(self):
        """Idempotency key must be 'auto:<task_id>:<attempt_number>'."""
        import api.scripts.local_runner as runner

        captured: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                captured.append(body)
                return {"id": "clr_fake"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            task = _make_task(task_type="spec", attempt_number=3)
            runner._auto_record_contribution(task, "claude", 60.0)
        finally:
            runner.api = orig_api

        assert len(captured) == 1
        meta = captured[0]["metadata"]
        expected_key = f"auto:{task['id']}:3"
        assert meta["idempotency_key"] == expected_key

    def test_node_id_in_metadata(self):
        """metadata.node_id must equal the module-level _NODE_ID verbatim."""
        import api.scripts.local_runner as runner

        captured: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                captured.append(body)
                return {"id": "clr_fake"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            task = _make_task()
            runner._auto_record_contribution(task, "claude", 30.0)
        finally:
            runner.api = orig_api

        assert len(captured) == 1
        meta = captured[0]["metadata"]
        assert meta["node_id"] == runner._NODE_ID
        assert meta["auto_recorded"] is True

    def test_dif_multiplier_halves_at_zero(self):
        """DIF=0.0 should halve the amount_cc."""
        import api.scripts.local_runner as runner

        captured: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                captured.append(body)
                return {"id": "clr_fake"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            # impl base=8, duration=0 => bonus=0, total=8.0
            # DIF=0.0: 8.0 * (0.5 + 0.5*0.0) = 4.0
            task = _make_task(task_type="impl", dif_score=0.0)
            runner._auto_record_contribution(task, "claude", 0.0)
        finally:
            runner.api = orig_api

        assert captured[0]["amount_cc"] == 4.0

    def test_dif_multiplier_unchanged_at_one(self):
        """DIF=1.0 should leave the amount_cc unchanged."""
        import api.scripts.local_runner as runner

        captured: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                captured.append(body)
                return {"id": "clr_fake"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            # impl base=8, duration=0 => bonus=0, total=8.0
            # DIF=1.0: 8.0 * (0.5 + 0.5*1.0) = 8.0
            task = _make_task(task_type="impl", dif_score=1.0)
            runner._auto_record_contribution(task, "claude", 0.0)
        finally:
            runner.api = orig_api

        assert captured[0]["amount_cc"] == 8.0

    def test_dif_multiplier_intermediate(self):
        """DIF=0.6 should scale amount by 0.8."""
        import api.scripts.local_runner as runner

        captured: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                captured.append(body)
                return {"id": "clr_fake"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            # spec base=3, duration=120s => bonus=2.0, total=5.0
            # DIF=0.6: 5.0 * (0.5 + 0.5*0.6) = 5.0 * 0.8 = 4.0
            task = _make_task(task_type="spec", dif_score=0.6)
            runner._auto_record_contribution(task, "claude", 120.0)
        finally:
            runner.api = orig_api

        assert captured[0]["amount_cc"] == 4.0

    def test_no_dif_score_leaves_amount_unchanged(self):
        """When no DIF score is present, amount should not be modified."""
        import api.scripts.local_runner as runner

        captured: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                captured.append(body)
                return {"id": "clr_fake"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            # impl base=8, duration=0 => 8.0
            task = _make_task(task_type="impl", dif_score=None)
            runner._auto_record_contribution(task, "claude", 0.0)
        finally:
            runner.api = orig_api

        assert captured[0]["amount_cc"] == 8.0
        assert "dif_score" not in captured[0]["metadata"]

    def test_partial_contribution_half_amount(self):
        """Partial contributions should be capped at 50% and metadata.partial=True."""
        import api.scripts.local_runner as runner

        captured: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                captured.append(body)
                return {"id": "clr_fake"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            # impl base=8, duration=0 => 8.0; partial => 4.0
            task = _make_task(task_type="impl")
            runner._auto_record_contribution(task, "claude", 0.0, partial=True)
        finally:
            runner.api = orig_api

        assert captured[0]["amount_cc"] == 4.0
        assert captured[0]["metadata"]["partial"] is True

    def test_retry_queue_on_api_failure(self):
        """On POST failure, the payload should be queued for retry."""
        import api.scripts.local_runner as runner

        # Clear the queue
        with runner._contribution_retry_lock:
            runner._contribution_retry_queue.clear()

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                return None  # Simulate failure
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            task = _make_task()
            runner._auto_record_contribution(task, "claude", 30.0)
        finally:
            runner.api = orig_api

        with runner._contribution_retry_lock:
            assert len(runner._contribution_retry_queue) == 1
            queued = runner._contribution_retry_queue[0]
            assert queued["metadata"]["task_id"] == task["id"]
            runner._contribution_retry_queue.clear()

    def test_retry_queue_cap(self):
        """Retry queue must be capped at 100 entries."""
        import api.scripts.local_runner as runner

        with runner._contribution_retry_lock:
            runner._contribution_retry_queue.clear()

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                return None  # Always fail
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            for i in range(110):
                task = _make_task()
                task["id"] = f"task-{i:04d}"
                runner._auto_record_contribution(task, "claude", 1.0)
        finally:
            runner.api = orig_api

        with runner._contribution_retry_lock:
            assert len(runner._contribution_retry_queue) <= 100
            runner._contribution_retry_queue.clear()

    def test_flush_retry_queue_resubmits(self):
        """_flush_contribution_retry_queue should resubmit and clear on success."""
        import api.scripts.local_runner as runner

        with runner._contribution_retry_lock:
            runner._contribution_retry_queue.clear()
            runner._contribution_retry_queue.append({
                "contributor_id": "test-node",
                "type": "code",
                "amount_cc": 5.0,
                "metadata": {"task_id": "retry-task-001", "auto_recorded": True},
            })

        submitted: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                submitted.append(body)
                return {"id": "clr_retried"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            runner._flush_contribution_retry_queue()
        finally:
            runner.api = orig_api

        assert len(submitted) == 1
        assert submitted[0]["metadata"]["task_id"] == "retry-task-001"
        with runner._contribution_retry_lock:
            assert len(runner._contribution_retry_queue) == 0

    def test_spec_task_produces_docs_type(self):
        """A spec task should produce a 'docs' contribution type."""
        import api.scripts.local_runner as runner

        captured: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                captured.append(body)
                return {"id": "clr_fake"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            task = _make_task(task_type="spec")
            runner._auto_record_contribution(task, "claude", 30.0)
        finally:
            runner.api = orig_api

        assert captured[0]["type"] == "docs"

    def test_duration_bonus(self):
        """Duration bonus should be min(duration/60, 5)."""
        import api.scripts.local_runner as runner

        captured: list[dict] = []

        def fake_api(method, path, body=None, **kw):
            if method == "POST" and "/contributions/record" in path:
                captured.append(body)
                return {"id": "clr_fake"}
            return None

        orig_api = runner.api
        try:
            runner.api = fake_api
            # impl base=8, duration=480s => bonus=min(480/60,5)=5 => 13.0
            task = _make_task(task_type="impl", dif_score=1.0)
            runner._auto_record_contribution(task, "claude", 480.0)
        finally:
            runner.api = orig_api

        assert captured[0]["amount_cc"] == 13.0


# ---------------------------------------------------------------------------
# Integration tests for ledger endpoint filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ledger_auto_only_filter():
    """GET /api/contributions/ledger/{id}?auto_only=true filters to auto-recorded entries."""
    cid = _uid("contrib")

    # Record one auto-recorded and one manual
    contribution_ledger_service.record_contribution(
        contributor_id=cid,
        contribution_type="code",
        amount_cc=5.0,
        metadata={"auto_recorded": True, "node_id": "test-node"},
    )
    contribution_ledger_service.record_contribution(
        contributor_id=cid,
        contribution_type="direction",
        amount_cc=2.0,
        metadata={"manual": True},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Without filter: both entries
        r = await c.get(f"/api/contributions/ledger/{cid}")
        assert r.status_code == 200
        all_history = r.json()["history"]
        assert len(all_history) == 2

        # With auto_only: only the auto-recorded one
        r = await c.get(f"/api/contributions/ledger/{cid}?auto_only=true")
        assert r.status_code == 200
        filtered = r.json()["history"]
        assert len(filtered) == 1
        meta = json.loads(filtered[0]["metadata_json"])
        assert meta["auto_recorded"] is True


@pytest.mark.asyncio
async def test_ledger_since_filter():
    """GET /api/contributions/ledger/{id}?since=... filters by timestamp."""
    from app.services.contribution_ledger_service import (
        ContributionLedgerRecord, _ensure_schema, _session,
    )
    from uuid import uuid4 as _uuid4

    cid = _uid("contrib")
    _ensure_schema()

    # Insert an "old" record with an explicit past timestamp
    old_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    # Use Z suffix which is URL-safe (no '+' that gets decoded as space)
    since_ts = "2026-01-01T00:00:00Z"

    with _session() as s:
        s.add(ContributionLedgerRecord(
            id=f"clr_{_uuid4().hex[:12]}",
            contributor_id=cid,
            contribution_type="code",
            idea_id=None,
            amount_cc=3.0,
            metadata_json=json.dumps({"batch": "old"}),
            recorded_at=old_time,
        ))

    # Record a "new" one at current time (always after since_ts in 2026)
    contribution_ledger_service.record_contribution(
        contributor_id=cid,
        contribution_type="docs",
        amount_cc=2.0,
        metadata={"batch": "new"},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Without since: both
        r = await c.get(f"/api/contributions/ledger/{cid}")
        assert r.status_code == 200
        assert len(r.json()["history"]) == 2

        # With since: only the newer one
        r = await c.get(f"/api/contributions/ledger/{cid}", params={"since": since_ts})
        assert r.status_code == 200
        filtered = r.json()["history"]
        assert len(filtered) == 1
        meta = json.loads(filtered[0]["metadata_json"])
        assert meta["batch"] == "new"


@pytest.mark.asyncio
async def test_ledger_combined_filters():
    """Combined auto_only=true and since filters work together."""
    from app.services.contribution_ledger_service import (
        ContributionLedgerRecord, _ensure_schema, _session,
    )
    from uuid import uuid4 as _uuid4

    cid = _uid("contrib")
    _ensure_schema()

    old_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    since_ts = "2026-01-01T00:00:00Z"

    # Insert old records with explicit past timestamp
    with _session() as s:
        s.add(ContributionLedgerRecord(
            id=f"clr_{_uuid4().hex[:12]}",
            contributor_id=cid,
            contribution_type="code",
            idea_id=None,
            amount_cc=1.0,
            metadata_json=json.dumps({"auto_recorded": True, "tag": "old_auto"}),
            recorded_at=old_time,
        ))
        s.add(ContributionLedgerRecord(
            id=f"clr_{_uuid4().hex[:12]}",
            contributor_id=cid,
            contribution_type="code",
            idea_id=None,
            amount_cc=1.0,
            metadata_json=json.dumps({"tag": "old_manual"}),
            recorded_at=old_time,
        ))

    # Record new entries at current time (2026+)
    contribution_ledger_service.record_contribution(
        contributor_id=cid, contribution_type="code", amount_cc=1.0,
        metadata={"auto_recorded": True, "tag": "new_auto"},
    )
    contribution_ledger_service.record_contribution(
        contributor_id=cid, contribution_type="code", amount_cc=1.0,
        metadata={"tag": "new_manual"},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get(
            f"/api/contributions/ledger/{cid}",
            params={"auto_only": "true", "since": since_ts},
        )
        assert r.status_code == 200
        filtered = r.json()["history"]
        assert len(filtered) == 1
        meta = json.loads(filtered[0]["metadata_json"])
        assert meta["tag"] == "new_auto"
