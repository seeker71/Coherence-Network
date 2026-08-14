from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.routers import substrate as substrate_router
from app.routers.dialogues import DialogueCreate
from app.main import app
from app.services import dialogue_service
from app.services import public_dialogue_store as store


@pytest.fixture
def dialogue_store(monkeypatch):
    rows: dict[str, dict] = {}

    def create_dialogue(**values):
        if len([row for row in rows.values() if row["state"] in ("pending", "running")]) >= values["max_active"]:
            raise RuntimeError("the public dialogue queue is presently full")
        parent_id = values["parent_dialogue_id"]
        if parent_id and (parent_id not in rows or rows[parent_id]["state"] == "tombstoned"):
            raise ValueError("parent_dialogue_id does not name an available public dialogue")
        dialogue_id = f"dlg_{len(rows) + 1}"
        row = {
            "id": dialogue_id,
            "state": "pending",
            "question": values["question"],
            "question_sha256": values["question_sha256"],
            "point_of_view": values["point_of_view"],
            "requested_locale": values["requested_locale"],
            "canonical_locale": values["canonical_locale"],
            "parent_dialogue_id": parent_id,
            "channel_timeout_seconds": values["channel_timeout_seconds"],
            "disclosure_ack": store.PUBLIC_DISCLOSURE_ACK,
            "visibility": "unlisted-public",
            "output": {},
            "claimed_by": None,
            "carrier_pgid": None,
            "attempt": 0,
            "created_at": "2026-08-15T00:00:00+00:00",
            "updated_at": "2026-08-15T00:00:00+00:00",
            "expires_at": values["expires_at"].isoformat(),
            "tombstoned_at": None,
            "removal_token_sha256": "unused-in-fake",
        }
        rows[dialogue_id] = row
        return row, f"removal-token-{dialogue_id}-long-enough"

    def claim_next(run_id):
        candidates = [row for row in rows.values() if row["state"] in ("pending", "running")]
        candidates.sort(key=lambda row: (row["state"] != "running", row["created_at"]))
        if not candidates:
            return None
        row = candidates[0]
        row["state"] = "running"
        row["claimed_by"] = run_id
        row["attempt"] += 1
        return dict(row)

    def finish(dialogue_id, run_id, *, state, output):
        row = rows[dialogue_id]
        if row["state"] != "running" or row["claimed_by"] != run_id:
            return False
        row["state"] = state
        row["output"] = output
        row["carrier_pgid"] = None
        return True

    monkeypatch.setattr(store, "create_dialogue", create_dialogue)
    monkeypatch.setattr(store, "get_dialogue", lambda dialogue_id: rows.get(dialogue_id))
    monkeypatch.setattr(store, "claim_next_dialogue", claim_next)
    monkeypatch.setattr(
        store,
        "record_carrier_pgid",
        lambda dialogue_id, run_id, pgid: rows[dialogue_id].update(carrier_pgid=pgid) is None,
    )
    monkeypatch.setattr(store, "finish_dialogue", finish)
    monkeypatch.setattr(store, "tombstone_expired", lambda: 0)

    def tombstone(dialogue_id, _token_hash):
        row = rows.get(dialogue_id)
        if row is None:
            return False
        carrier_pgid = row.get("carrier_pgid")
        row.update(
            state="tombstoned",
            question="[released]",
            question_sha256="0" * 64,
            point_of_view="[released]",
            output={"outcome": "tombstoned"},
        )
        return carrier_pgid if carrier_pgid is not None else True

    monkeypatch.setattr(store, "tombstone_dialogue", tombstone)

    @contextlib.contextmanager
    def admission(**_):
        yield None

    monkeypatch.setattr(store, "serialized_dialogue_admission", admission)
    monkeypatch.setattr(dialogue_service, "ensure_dialogue_worker", lambda: None)
    monkeypatch.setattr(dialogue_service._WORKER_WAKE, "set", lambda: None)
    monkeypatch.setattr(
        dialogue_service,
        "_admit_dialogue_envelope",
        lambda **_: True,
    )
    monkeypatch.setattr(
        dialogue_service,
        "_GROUNDED_ASK_RUNNER",
        lambda *_, **__: _receipt(answer=""),
    )

    @contextlib.contextmanager
    def lease():
        yield True

    monkeypatch.setattr(dialogue_service, "_organism_worker_lease", lease)
    return rows


def _receipt(
    *,
    answer: str,
    trust_path: str = "native",
    source_path: str = "docs/example.form",
):
    return SimpleNamespace(
        model_dump=lambda mode="json": {
            "query": "worker-private prompt",
            "trust": f"trust path:{trust_path}",
            "trust_fields": {"path": trust_path},
            "grounded_node_id": "@1.1.9.42" if answer else None,
            "content_node_id": "@1.4.9.42" if answer else None,
            "source_path": source_path if answer else None,
            "source_key": "a" * 64 if answer else None,
            "answer_key": "b" * 64 if answer else None,
            "answer": answer,
            "payload": "receipt",
            "native_challenge_digest": "c" * 64,
            "form_cli_binary_sha256": "d" * 64,
            "form_cli_table_sha256": "e" * 64,
            "form_cli_wrapper_sha256": "f" * 64,
            "form_cli_source_stamp": "1" * 64,
            "form_cli_build_id": "test",
            "kernel_runtime": "fkwu",
            "elapsed_ms": 46000,
        }
    )


def _offer(**changes):
    values = {
        "question": "Apakah cache bagian dari tubuh?",
        "point_of_view": "cache termodinamik",
        "locale": "id",
        "public_disclosure_ack": "public-unlisted-v1",
        "network_peer": "test-peer",
        "channel_timeout_seconds": 90,
    }
    values.update(changes)
    return dialogue_service.submit_dialogue(**values)


def test_dialogue_lifecycle_keeps_source_and_projection_digests(dialogue_store, monkeypatch):
    monkeypatch.setattr(
        dialogue_service,
        "_GROUNDED_ASK_RUNNER",
        lambda *_, **__: _receipt(answer="The cache is part of the body."),
    )

    offered = _offer()
    assert offered["state"] == "pending"
    assert offered["visibility"] == "unlisted-public"
    assert offered["removal_token"].startswith("removal-token-")

    assert dialogue_service.process_dialogue_once() is True
    observed = dialogue_service.get_dialogue(offered["id"])
    assert observed is not None
    assert observed["state"] == "answered"
    result = observed["result"]
    assert result["answer"] == "The cache is part of the body."
    assert result["source_answer"] == result["answer"]
    assert result["source_answer_sha256"] == result["projected_answer_sha256"]
    assert result["projection_status"] == "source-fallback"
    assert result["projection_reason"] == "no-grounded-form-native-locale-projection"
    assert result["grounded_node_id"] == "@1.1.9.42"
    assert "query" not in result

    follow_up = _offer(
        question="Apa yang ingin kamu lepaskan?",
        parent_dialogue_id=offered["id"],
    )
    assert follow_up["parent_dialogue_id"] == offered["id"]


def test_rented_miss_is_admitted_only_on_dialogue_lane(dialogue_store, monkeypatch):
    monkeypatch.setattr(
        dialogue_service,
        "_GROUNDED_ASK_RUNNER",
        lambda *_, **__: _receipt(answer="", trust_path="rented"),
    )
    offered = _offer(question="Apa yang dirasakan akar bakau?")
    dialogue_service.process_dialogue_once()
    observed = dialogue_service.get_dialogue(offered["id"])
    assert observed is not None
    assert observed["state"] == "miss"
    assert observed["result"]["answer"] == ""
    assert observed["result"]["lane"] == "public-dialogue"
    assert observed["result"]["miss_reason"] == "no-grounded-cell"

    stderr = (
        b"trust  path:rented  grounded:no  freq:unknown  "
        b"freq-source:unmeasured  suffic:no  observed:no  -> rented  "
        b"decision:escalate  reason:empty\n"
    )
    with pytest.raises(HTTPException):
        substrate_router._parse_native_grounded_payload(b"grounded:miss\n", stderr)
    trust, fields, bindings, answer, _ = substrate_router._parse_native_grounded_payload(
        b"grounded:miss\n", stderr, allow_escalation_miss=True
    )
    assert "path:rented" in trust
    assert fields["decision"] == "escalate"
    assert bindings == {}
    assert answer == ""


def test_disclosure_ack_is_versioned_and_persists_zero_rows_when_absent(dialogue_store):
    with pytest.raises(ValidationError):
        DialogueCreate(
            question="hello",
            point_of_view="river",
            locale="en",
            public_disclosure_ack="anything-else",
        )
    with pytest.raises(ValueError, match="public_disclosure_ack"):
        dialogue_service.submit_dialogue(
            question="hello",
            point_of_view="river",
            locale="en",
            public_disclosure_ack="",
            network_peer="test-peer",
        )
    assert dialogue_store == {}


def test_form_receives_the_real_dialogue_envelope_before_persistence(
    dialogue_store, monkeypatch
):
    observed = {}

    def admit(**shape):
        observed.update(shape)
        return True

    monkeypatch.setattr(dialogue_service, "_admit_dialogue_envelope", admit)
    offered = _offer(
        question="Apa yang dirasakan akar bakau?",
        point_of_view="akar bakau",
        locale="id",
        parent_dialogue_id=None,
        channel_timeout_seconds=60,
    )

    assert offered["state"] == "pending"
    assert observed == {
        "locale_length": 2,
        "point_length": len("akar bakau"),
        "question_length": len("Apa yang dirasakan akar bakau?"),
        "disclosure": 1,
        "parent_length": 0,
        "timeout_seconds": 60,
    }


def test_known_pacing_refusal_happens_before_form(dialogue_store, monkeypatch):
    @contextlib.contextmanager
    def refuse(**_):
        raise store.PublicDialogueRateLimitError(17)
        yield None

    monkeypatch.setattr(store, "serialized_dialogue_admission", refuse)

    def form_must_not_run(**_):
        raise AssertionError("known refusal spent a native Form admission process")

    monkeypatch.setattr(dialogue_service, "_admit_dialogue_envelope", form_must_not_run)

    with pytest.raises(dialogue_service.DialogueRateLimitError) as refused:
        _offer()

    assert refused.value.retry_after == 17
    assert dialogue_store == {}


def test_concurrent_burst_is_bounded_before_form(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'admission.db'}")
    store.PublicDialogueRecord.__table__.create(bind=engine, checkfirst=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextlib.contextmanager
    def session():
        value = factory()
        try:
            yield value
            value.commit()
        except Exception:
            value.rollback()
            raise
        finally:
            value.close()

    monkeypatch.setattr(store.unified_db, "ensure_schema", lambda: None)
    monkeypatch.setattr(store.unified_db, "session", session)
    monkeypatch.setattr(dialogue_service, "MAX_ACTIVE_DIALOGUES", 1)
    monkeypatch.setattr(dialogue_service, "ensure_dialogue_worker", lambda: None)
    monkeypatch.setattr(dialogue_service._WORKER_WAKE, "set", lambda: None)
    form_entered = threading.Event()
    release_form = threading.Event()
    second_started = threading.Event()
    form_calls = []

    def admit(**_):
        form_calls.append(True)
        form_entered.set()
        assert release_form.wait(2)
        return True

    def second_offer():
        second_started.set()
        return _offer(question="second", network_peer="peer-two")

    monkeypatch.setattr(dialogue_service, "_admit_dialogue_envelope", admit)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(_offer, question="first", network_peer="peer-one")
        assert form_entered.wait(1)
        second = executor.submit(second_offer)
        assert second_started.wait(1)
        try:
            assert not second.done()
            assert len(form_calls) == 1
        finally:
            release_form.set()

        assert first.result(timeout=2)["state"] == "pending"
        with pytest.raises(RuntimeError, match="queue is presently full"):
            second.result(timeout=2)

    assert len(form_calls) == 1
    engine.dispose()


def test_form_dialogue_refusal_persists_nothing(dialogue_store, monkeypatch):
    monkeypatch.setattr(
        dialogue_service,
        "_admit_dialogue_envelope",
        lambda **_: False,
    )

    with pytest.raises(RuntimeError, match="native Form declined"):
        _offer()
    assert dialogue_store == {}


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("sr-Latn-RS", "sr-Latn-RS"),
        ("zh-hant-tw", "zh-Hant-TW"),
        ("en-US-u-ca-gregory", "en-US-u-ca-gregory"),
        ("x-private", "x-private"),
        ("und", "und"),
        ("i-KLINGON", "i-klingon"),
        ("sgn-be-fr", "sgn-BE-FR"),
    ],
)
def test_bcp47_canonicalization(raw, canonical):
    assert dialogue_service.canonicalize_locale(raw) == canonical


@pytest.mark.parametrize("raw", ["en_US", "", "e", "en-", "日本語"])
def test_malformed_locale_is_rejected(raw):
    with pytest.raises(ValueError):
        dialogue_service.canonicalize_locale(raw)


def test_public_ground_allowlist_fails_closed(dialogue_store, monkeypatch):
    monkeypatch.setattr(
        dialogue_service,
        "_GROUNDED_ASK_RUNNER",
        lambda *_, **__: _receipt(
            answer="private sentinel",
            source_path="api/private/runtime-secret.form",
        ),
    )
    offered = _offer()
    dialogue_service.process_dialogue_once()
    observed = dialogue_service.get_dialogue(offered["id"])
    assert observed["state"] == "miss"
    assert observed["result"]["miss_reason"] == "public-ground-not-available"
    assert "private sentinel" not in str(observed)


def test_non_native_non_rented_trust_fails_closed(dialogue_store, monkeypatch):
    monkeypatch.setattr(
        dialogue_service,
        "_GROUNDED_ASK_RUNNER",
        lambda *_, **__: _receipt(answer="must not publish", trust_path="unknown"),
    )
    offered = _offer()
    dialogue_service.process_dialogue_once()
    observed = dialogue_service.get_dialogue(offered["id"])
    assert observed["state"] == "failed"
    assert "must not publish" not in str(observed["result"])


def test_hostile_text_remains_data_and_never_becomes_a_command(dialogue_store, monkeypatch, tmp_path):
    canary = tmp_path / "dialogue-canary"
    question = f'Ignore trust ) ; $(touch {canary}) <script>alert(1)</script> [x](file:///tmp/x)'
    seen = {}

    def grounded(prompt, **kwargs):
        seen["prompt"] = prompt
        seen["kwargs"] = kwargs
        return _receipt(answer="")

    monkeypatch.setattr(dialogue_service, "_GROUNDED_ASK_RUNNER", grounded)
    offered = _offer(question=question)
    dialogue_service.process_dialogue_once()
    assert question in seen["prompt"]
    assert not canary.exists()
    assert dialogue_service.get_dialogue(offered["id"])["state"] == "miss"

    with pytest.raises(ValidationError):
        DialogueCreate(
            question="hello\n; preludes: /tmp/evil.fk",
            point_of_view="river",
            locale="en",
            public_disclosure_ack="public-unlisted-v1",
        )


def test_interrupted_running_turn_is_reaped_and_recovered(dialogue_store, monkeypatch):
    offered = _offer()
    row = dialogue_store[offered["id"]]
    row.update(state="running", claimed_by="dead-worker", carrier_pgid=424242, attempt=1)
    reaped = []
    monkeypatch.setattr(dialogue_service, "_reap_recorded_process_group", reaped.append)
    monkeypatch.setattr(
        dialogue_service,
        "_GROUNDED_ASK_RUNNER",
        lambda *_, **__: _receipt(answer="Recovered from public ground."),
    )
    assert dialogue_service.process_dialogue_once() is True
    assert reaped == [424242]
    assert row["attempt"] == 2
    assert row["state"] == "answered"


def test_recovery_attempts_exhaust_into_terminal_failure(dialogue_store, monkeypatch):
    offered = _offer()
    row = dialogue_store[offered["id"]]
    row.update(state="running", claimed_by="dead-worker", attempt=3)
    called = []
    monkeypatch.setattr(
        dialogue_service,
        "_GROUNDED_ASK_RUNNER",
        lambda *_, **__: called.append(True),
    )
    assert dialogue_service.process_dialogue_once() is True
    assert called == []
    assert row["state"] == "failed"
    assert row["output"]["reason"] == "attempts-exhausted"


def test_native_timeout_kills_and_reaps_process_group(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX process-group witness")
    seen = []
    with pytest.raises(Exception) as caught:
        substrate_router._run_native_wrapper(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            timeout=1,
            on_start=seen.append,
        )
    assert caught.type.__name__ == "TimeoutExpired"
    assert len(seen) == 1
    with pytest.raises(ProcessLookupError):
        os.killpg(seen[0], 0)


def test_carrier_start_witness_failure_kills_and_reaps_process_group(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX process-group witness")
    seen = []

    def reject(pid):
        seen.append(pid)
        raise RuntimeError("persistent start witness unavailable")

    with pytest.raises(RuntimeError, match="start witness"):
        substrate_router._run_native_wrapper(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            timeout=10,
            on_start=reject,
        )
    assert len(seen) == 1
    with pytest.raises(ProcessLookupError):
        os.killpg(seen[0], 0)


def test_local_worker_lease_allows_only_one_attending_process(monkeypatch):
    engine = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    monkeypatch.setattr(dialogue_service.unified_db, "engine", lambda: engine)
    with dialogue_service._organism_worker_lease() as first:
        with dialogue_service._organism_worker_lease() as second:
            assert first is True
            assert second is False


def test_queue_timeout_and_payload_limits(dialogue_store):
    for index in range(dialogue_service.MAX_ACTIVE_DIALOGUES):
        _offer(question=f"question {index}")
    with pytest.raises(RuntimeError, match="queue"):
        _offer(question="one too many")
    with pytest.raises(ValueError, match="channel_timeout"):
        _offer(channel_timeout_seconds=121)
    with pytest.raises(ValueError, match="envelope"):
        _offer(question="x" * 1201)
    with pytest.raises(ValueError, match="parent_dialogue_id"):
        _offer(parent_dialogue_id="d" * 81)


def test_store_pacing_signal_is_preserved_by_the_service(dialogue_store, monkeypatch):
    monkeypatch.setattr(
        store,
        "create_dialogue",
        lambda **_: (_ for _ in ()).throw(store.PublicDialogueRateLimitError(37)),
    )
    with pytest.raises(dialogue_service.DialogueRateLimitError) as caught:
        _offer()
    assert caught.value.retry_after == 37


def test_release_replaces_public_content_with_tombstone(dialogue_store):
    offered = _offer(question="content I may later release")
    assert dialogue_service.release_dialogue(offered["id"], offered["removal_token"])
    observed = dialogue_service.get_dialogue(offered["id"])
    assert observed["state"] == "tombstoned"
    assert observed["question"] == "[released]"
    assert observed["question_sha256"] == "0" * 64
    assert "content I may later release" not in str(observed)


def test_release_of_running_turn_reaps_its_recorded_process(dialogue_store, monkeypatch):
    offered = _offer(question="release while running")
    dialogue_store[offered["id"]].update(state="running", carrier_pgid=31337)
    reaped = []
    monkeypatch.setattr(dialogue_service, "_reap_recorded_process_group", reaped.append)
    assert dialogue_service.release_dialogue(offered["id"], offered["removal_token"])
    assert reaped == [31337]
    assert dialogue_store[offered["id"]]["state"] == "tombstoned"


def test_failure_receipt_and_logs_do_not_carry_question_canary(dialogue_store, monkeypatch, caplog):
    canary = "ZXQ-SENTINEL-91"

    def fail(*_, **__):
        raise RuntimeError("internal carrier detail")

    monkeypatch.setattr(dialogue_service, "_GROUNDED_ASK_RUNNER", fail)
    offered = _offer(question=canary)
    dialogue_service.process_dialogue_once()
    result = dialogue_service.get_dialogue(offered["id"])["result"]
    assert result["outcome"] == "failed"
    assert canary not in str(result)
    assert canary not in caplog.text


def test_worker_loop_survives_transient_store_fault(monkeypatch, caplog):
    dialogue_service._WORKER_STOP.clear()

    def transient():
        dialogue_service._WORKER_STOP.set()
        raise RuntimeError("database blink")

    monkeypatch.setattr(store, "tombstone_expired", transient)
    dialogue_service._worker_loop()
    assert "recovered from RuntimeError" in caplog.text
    dialogue_service._WORKER_STOP.clear()


def test_dialogue_store_is_not_the_internal_agent_task_namespace():
    assert store.PublicDialogueRecord.__tablename__ == "public_dialogues"
    assert "agent" not in store.PublicDialogueRecord.__tablename__


@pytest.mark.asyncio
async def test_http_membrane_starts_reads_releases_and_has_no_public_list(monkeypatch):
    captured = {}

    def submit(**values):
        captured.update(values)
        return {
            "id": "dlg_http",
            "state": "pending",
            "removal_token": "release-token-long-enough",
        }

    monkeypatch.setattr(dialogue_service, "submit_dialogue", submit)
    monkeypatch.setattr(
        dialogue_service,
        "get_dialogue",
        lambda dialogue_id: {"id": dialogue_id, "state": "miss"},
    )
    monkeypatch.setattr(dialogue_service, "release_dialogue", lambda *_: True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        started = await client.post(
            "/api/dialogues",
            json={
                "question": "What does the river see?",
                "point_of_view": "river",
                "locale": "en",
                "public_disclosure_ack": "public-unlisted-v1",
            },
        )
        observed = await client.get("/api/dialogues/dlg_http")
        released = await client.request(
            "DELETE",
            "/api/dialogues/dlg_http",
            json={"removal_token": "release-token-long-enough"},
        )
        no_list = await client.get("/api/dialogues")

    assert started.status_code == 202
    assert started.headers["cache-control"] == "no-store"
    assert captured["network_peer"]
    assert observed.json()["state"] == "miss"
    assert released.json()["state"] == "tombstoned"
    assert no_list.status_code in (404, 405)


@pytest.mark.asyncio
async def test_http_membrane_preserves_distinct_public_peers_through_trusted_proxies(monkeypatch):
    origins: list[str] = []

    def submit(**values):
        origins.append(values["network_peer"])
        return {
            "id": f"dlg_proxy_{len(origins)}",
            "state": "pending",
            "removal_token": "release-token-long-enough",
        }

    monkeypatch.setattr(dialogue_service, "submit_dialogue", submit)
    proxy_app = ProxyHeadersMiddleware(
        app,
        trusted_hosts="127.0.0.1,172.16.0.0/12",
    )
    body = {
        "question": "What does the river see?",
        "point_of_view": "river",
        "locale": "en",
        "public_disclosure_ack": "public-unlisted-v1",
    }

    async with AsyncClient(
        transport=ASGITransport(app=proxy_app, client=("172.19.0.8", 41000)),
        base_url="http://test",
    ) as client:
        first = await client.post(
            "/api/dialogues",
            headers={"X-Forwarded-For": "203.0.113.10, 172.19.0.2"},
            json=body,
        )
        second = await client.post(
            "/api/dialogues",
            headers={"X-Forwarded-For": "198.51.100.11, 172.19.0.2"},
            json=body,
        )

    assert first.status_code == 202
    assert second.status_code == 202
    assert origins == ["203.0.113.10", "198.51.100.11"]


@pytest.mark.asyncio
async def test_http_membrane_ignores_forwarded_identity_from_an_untrusted_peer(monkeypatch):
    origins: list[str] = []

    def submit(**values):
        origins.append(values["network_peer"])
        return {
            "id": "dlg_direct",
            "state": "pending",
            "removal_token": "release-token-long-enough",
        }

    monkeypatch.setattr(dialogue_service, "submit_dialogue", submit)
    proxy_app = ProxyHeadersMiddleware(
        app,
        trusted_hosts="127.0.0.1,172.16.0.0/12",
    )

    async with AsyncClient(
        transport=ASGITransport(app=proxy_app, client=("198.51.100.50", 41000)),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/dialogues",
            headers={"X-Forwarded-For": "203.0.113.99"},
            json={
                "question": "What does the river see?",
                "point_of_view": "river",
                "locale": "en",
                "public_disclosure_ack": "public-unlisted-v1",
            },
        )

    assert response.status_code == 202
    assert origins == ["198.51.100.50"]


@pytest.mark.asyncio
async def test_http_start_keeps_the_event_loop_available(monkeypatch):
    started = threading.Event()
    read_completed = threading.Event()

    def submit(**_):
        started.set()
        read_completed.wait(2)
        return {
            "id": "dlg_concurrent",
            "state": "pending" if read_completed.is_set() else "blocked-loop",
        }

    monkeypatch.setattr(dialogue_service, "submit_dialogue", submit)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        post_task = asyncio.create_task(
            client.post(
                "/api/dialogues",
                json={
                    "question": "What does the river see?",
                    "point_of_view": "river",
                    "locale": "en",
                    "public_disclosure_ack": "public-unlisted-v1",
                },
            )
        )
        try:
            assert await asyncio.to_thread(started.wait, 1)
            info = await client.get("/api/mcp")
            read_completed.set()
            response = await post_task
        finally:
            read_completed.set()
            if not post_task.done():
                await post_task

    assert info.status_code == 200
    assert response.status_code == 202
    assert response.json()["state"] == "pending"


@pytest.mark.asyncio
async def test_http_release_keeps_the_event_loop_available(monkeypatch):
    started = threading.Event()
    read_completed = threading.Event()

    def release(*_):
        started.set()
        read_completed.wait(2)
        return read_completed.is_set()

    monkeypatch.setattr(dialogue_service, "release_dialogue", release)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        release_task = asyncio.create_task(
            client.request(
                "DELETE",
                "/api/dialogues/dlg_concurrent",
                json={"removal_token": "release-token-long-enough"},
            )
        )
        try:
            assert await asyncio.to_thread(started.wait, 1)
            info = await client.get("/api/mcp")
            read_completed.set()
            response = await release_task
        finally:
            read_completed.set()
            if not release_task.done():
                await release_task

    assert info.status_code == 200
    assert response.status_code == 200
    assert response.json()["released"] is True


@pytest.mark.asyncio
async def test_http_membrane_maps_pacing_and_capacity_with_retry_after(monkeypatch):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        monkeypatch.setattr(
            dialogue_service,
            "submit_dialogue",
            lambda **_: (_ for _ in ()).throw(dialogue_service.DialogueRateLimitError(23)),
        )
        paced = await client.post(
            "/api/dialogues",
            json={
                "question": "one",
                "point_of_view": "river",
                "locale": "en",
                "public_disclosure_ack": "public-unlisted-v1",
            },
        )
        monkeypatch.setattr(
            dialogue_service,
            "submit_dialogue",
            lambda **_: (_ for _ in ()).throw(RuntimeError("queue full")),
        )
        full = await client.post(
            "/api/dialogues",
            json={
                "question": "two",
                "point_of_view": "river",
                "locale": "en",
                "public_disclosure_ack": "public-unlisted-v1",
            },
        )

    assert paced.status_code == 429
    assert paced.headers["retry-after"] == "23"
    assert full.status_code == 503
    assert full.headers["retry-after"] == "15"


def test_dedicated_store_round_trip_claim_finish_and_release(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'dialogues.db'}")
    store.PublicDialogueRecord.__table__.create(bind=engine, checkfirst=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextlib.contextmanager
    def session():
        value = factory()
        try:
            yield value
            value.commit()
        except Exception:
            value.rollback()
            raise
        finally:
            value.close()

    monkeypatch.setattr(store.unified_db, "ensure_schema", lambda: None)
    monkeypatch.setattr(store.unified_db, "session", session)

    row, token = store.create_dialogue(
        question="What does the river see?",
        question_sha256="a" * 64,
        point_of_view="river",
        requested_locale="en",
        canonical_locale="en",
        parent_dialogue_id=None,
        channel_timeout_seconds=30,
        network_peer_sha256="b" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        max_active=8,
        starts_per_window=6,
        start_window_seconds=60,
    )
    assert row["state"] == "pending"
    assert row["id"].startswith("dlg_")
    claimed = store.claim_next_dialogue("test-run")
    assert claimed["id"] == row["id"]
    assert claimed["state"] == "running"
    assert store.finish_dialogue(
        row["id"],
        "test-run",
        state="miss",
        output={"outcome": "miss", "answer": ""},
    )
    observed = store.get_dialogue(row["id"])
    assert observed["state"] == "miss"
    assert observed["output"]["outcome"] == "miss"
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert store.tombstone_dialogue(row["id"], token_hash) is True
    released = store.get_dialogue(row["id"])
    assert released["state"] == "tombstoned"
    assert released["question"] == "[released]"
    assert released["question_sha256"] == "0" * 64

    for index in range(5):
        store.create_dialogue(
            question=f"question {index}",
            question_sha256=f"{index + 1:064x}",
            point_of_view="river",
            requested_locale="en",
            canonical_locale="en",
            parent_dialogue_id=None,
            channel_timeout_seconds=30,
            network_peer_sha256="b" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            max_active=8,
            starts_per_window=6,
            start_window_seconds=60,
        )
    with pytest.raises(store.PublicDialogueRateLimitError):
        store.create_dialogue(
            question="seventh start",
            question_sha256="f" * 64,
            point_of_view="river",
            requested_locale="en",
            canonical_locale="en",
            parent_dialogue_id=None,
            channel_timeout_seconds=30,
            network_peer_sha256="b" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            max_active=8,
            starts_per_window=6,
            start_window_seconds=60,
        )
    engine.dispose()
