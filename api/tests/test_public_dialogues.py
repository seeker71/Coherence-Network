from __future__ import annotations

import asyncio
import contextlib
import json
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
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.routers import substrate as substrate_router
from app.routers.dialogues import DialogueCreate
from app.main import app
from app.services import dialogue_service
from app.services import form_kernel_bridge
from app.services import public_dialogue_store as store


@pytest.fixture
def dialogue_store(monkeypatch):
    rows: dict[str, dict] = {}

    def create_dialogue(**values):
        if len(
            [
                row
                for row in rows.values()
                if row["state"] in ("pending", "running", "releasing")
            ]
        ) >= values["max_active"]:
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
            "disclosure_ack": values.get(
                "public_disclosure_ack", store.PUBLIC_DISCLOSURE_ACK
            ),
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
        candidates = [
            row
            for row in rows.values()
            if row["state"] in ("pending", "running", "releasing")
        ]
        priority = {"releasing": 0, "running": 1, "pending": 2}
        candidates.sort(key=lambda row: (priority[row["state"]], row["created_at"]))
        if not candidates:
            return None
        row = candidates[0]
        if row["state"] == "releasing":
            return dict(row)
        recovered = row["state"] == "running"
        row["state"] = "running"
        row["claimed_by"] = run_id
        if not recovered:
            row["attempt"] += 1
        claimed = dict(row)
        claimed["recovered"] = recovered
        return claimed

    def begin_recovered(dialogue_id, run_id):
        row = rows[dialogue_id]
        if row["state"] != "running" or row["claimed_by"] != run_id:
            return None
        row["carrier_pgid"] = None
        row["attempt"] += 1
        return row["attempt"]

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
    monkeypatch.setattr(store, "begin_recovered_dialogue_attempt", begin_recovered)
    monkeypatch.setattr(
        store,
        "record_carrier_pgid",
        lambda dialogue_id, run_id, pgid: rows[dialogue_id].update(carrier_pgid=pgid) is None,
    )
    monkeypatch.setattr(store, "finish_dialogue", finish)

    def finish_releasing(dialogue_id, carrier_pgid):
        row = rows[dialogue_id]
        if row["state"] != "releasing" or row["carrier_pgid"] != carrier_pgid:
            return False
        row.update(state="tombstoned", claimed_by=None, carrier_pgid=None)
        return True

    monkeypatch.setattr(store, "finish_releasing_dialogue", finish_releasing)
    monkeypatch.setattr(store, "tombstone_expired", lambda: 0)

    def tombstone(dialogue_id, _token_hash):
        row = rows.get(dialogue_id)
        if row is None:
            return False
        if row["state"] == "tombstoned":
            return True
        carrier_pgid = row.get("carrier_pgid")
        if row["state"] == "releasing":
            return carrier_pgid if carrier_pgid is not None else True
        next_state = "releasing" if row["state"] == "running" and carrier_pgid else "tombstoned"
        row.update(
            state=next_state,
            question="[released]",
            question_sha256="0" * 64,
            point_of_view="[released]",
            output={"outcome": "tombstoned"},
        )
        return carrier_pgid if next_state == "releasing" else True

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
        "public_disclosure_ack": "public-unlisted-thread-v2",
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


def test_single_turn_disclosure_advertises_only_single_turn_actions(dialogue_store):
    offered = _offer(
        question="This receipt stays one turn.",
        public_disclosure_ack=store.PUBLIC_SINGLE_TURN_DISCLOSURE_ACK,
    )

    assert offered["public_disclosure_ack"] == store.PUBLIC_SINGLE_TURN_DISCLOSURE_ACK
    assert "reply_url" not in offered
    assert "thread_url" not in offered
    assert offered["poll_url"].endswith(offered["id"])
    assert offered["release_url"].endswith(offered["id"])


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
        "locale": "id",
        "point": "akar bakau",
        "question": "Apa yang dirasakan akar bakau?",
        "disclosure": "public-unlisted-thread-v2",
        "parent": "",
        "timeout_seconds": 60,
    }


def test_form_receipt_is_bound_to_same_length_dialogue_values(monkeypatch):
    original_run_recipe = form_kernel_bridge.run_recipe
    sources = []

    def observed_run(source, *, timeout):
        sources.append(source)
        return original_run_recipe(source, timeout=timeout)

    monkeypatch.setattr(form_kernel_bridge, "run_recipe", observed_run)

    assert dialogue_service._admit_dialogue_envelope(
        locale="en",
        point="river",
        question="hello",
        disclosure="public-unlisted-v1",
        parent="",
        timeout_seconds=60,
    )
    assert dialogue_service._admit_dialogue_envelope(
        locale="fr",
        point="ocean",
        question="world",
        disclosure="public-unlisted-v1",
        parent="",
        timeout_seconds=60,
    )

    assert len(sources) == 2
    assert sources[0] != sources[1]
    assert '"656e" "7269766572" "68656c6c6f"' in sources[0]
    assert '"6672" "6f6365616e" "776f726c64"' in sources[1]
    assert "dialogue-envelope-receipt" in sources[0]


def test_form_dialogue_receipt_rejects_a_digest_not_bound_to_the_offer(monkeypatch):
    monkeypatch.setattr(
        form_kernel_bridge,
        "run_recipe",
        lambda *_, **__: "1|" + "0" * 64,
    )

    with pytest.raises(RuntimeError, match="did not bind"):
        dialogue_service._admit_dialogue_envelope(
            locale="en",
            point="river",
            question="hello",
            disclosure="public-unlisted-v1",
            parent="",
            timeout_seconds=60,
        )


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
            with pytest.raises(store.PublicDialogueAdmissionBusyError, match="presently attending"):
                second.result(timeout=1)
            assert len(form_calls) == 1
        finally:
            release_form.set()

        assert first.result(timeout=2)["state"] == "pending"

    assert len(form_calls) == 1
    engine.dispose()


def test_postgres_admission_contention_is_nonblocking_and_explicit():
    observed = {}

    def scalar(statement, params):
        observed.update(statement=str(statement), params=params)
        return False

    session = SimpleNamespace(
        bind=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        scalar=scalar,
    )

    with pytest.raises(store.PublicDialogueAdmissionBusyError, match="presently attending"):
        store._admission_lock(session)

    assert "pg_try_advisory_xact_lock" in observed["statement"]
    assert "pg_advisory_xact_lock" not in observed["statement"].replace(
        "pg_try_advisory_xact_lock",
        "",
    )
    assert observed["params"] == {"lock_key": store._ADMISSION_LOCK_KEY}


def test_thread_planner_contention_is_bounded_locally(monkeypatch):
    @contextlib.contextmanager
    def session():
        yield SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))

    monkeypatch.setattr(store.unified_db, "session", session)
    entered = threading.Event()
    release = threading.Event()

    def hold_planner():
        with store._thread_planning_slot():
            entered.set()
            assert release.wait(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(hold_planner)
        assert entered.wait(1)
        try:
            with pytest.raises(
                store.PublicDialogueThreadPlannerBusyError,
                match="presently attending",
            ):
                with store._thread_planning_slot():
                    pass
        finally:
            release.set()
        first.result(timeout=2)


def test_postgres_thread_planner_contention_is_nonblocking_and_explicit(monkeypatch):
    observed = {}

    def scalar(statement, params):
        observed.update(statement=str(statement), params=params)
        return False

    @contextlib.contextmanager
    def session():
        yield SimpleNamespace(
            bind=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
            scalar=scalar,
        )

    monkeypatch.setattr(store.unified_db, "session", session)
    with pytest.raises(
        store.PublicDialogueThreadPlannerBusyError,
        match="presently attending",
    ):
        with store._thread_planning_slot():
            pass

    assert "pg_try_advisory_xact_lock" in observed["statement"]
    assert observed["params"] == {"lock_key": store._THREAD_PLANNER_LOCK_KEY}


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


def test_interrupted_running_turn_waits_when_reaping_is_not_acknowledged(
    dialogue_store,
    monkeypatch,
):
    offered = _offer()
    row = dialogue_store[offered["id"]]
    row.update(state="running", claimed_by="dead-worker", carrier_pgid=424242, attempt=1)
    called = []
    monkeypatch.setattr(
        dialogue_service,
        "_reap_recorded_process_group",
        lambda _pgid: False,
    )
    monkeypatch.setattr(
        dialogue_service,
        "_GROUNDED_ASK_RUNNER",
        lambda *_, **__: called.append(True),
    )

    assert dialogue_service.process_dialogue_once() is False
    assert called == []
    assert row["state"] == "running"
    assert row["attempt"] == 1
    assert row["carrier_pgid"] == 424242
    assert row["claimed_by"] == dialogue_service._RUN_ID


def test_reaping_retries_do_not_spend_execution_attempts(dialogue_store, monkeypatch):
    offered = _offer()
    row = dialogue_store[offered["id"]]
    row.update(state="running", claimed_by="dead-worker", carrier_pgid=424242, attempt=1)
    reap_results = iter((False, False, True))
    monkeypatch.setattr(
        dialogue_service,
        "_reap_recorded_process_group",
        lambda _pgid: next(reap_results),
    )
    monkeypatch.setattr(
        dialogue_service,
        "_GROUNDED_ASK_RUNNER",
        lambda *_, **__: _receipt(answer="Recovered after observation returned."),
    )

    assert dialogue_service.process_dialogue_once() is False
    assert dialogue_service.process_dialogue_once() is False
    assert row["attempt"] == 1
    assert row["carrier_pgid"] == 424242
    assert dialogue_service.process_dialogue_once() is True
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
    row = dialogue_store[offered["id"]]
    row.update(state="running", claimed_by="active-worker", carrier_pgid=31337)
    reaped = []

    def reap(pgid):
        reaped.append(pgid)
        assert row["state"] == "releasing"
        assert row["claimed_by"] == "active-worker"
        assert row["carrier_pgid"] == 31337
        assert row["question"] == "[released]"
        return True

    monkeypatch.setattr(dialogue_service, "_reap_recorded_process_group", reap)
    assert dialogue_service.release_dialogue(offered["id"], offered["removal_token"])
    assert reaped == [31337]
    assert row["state"] == "tombstoned"
    assert row["claimed_by"] is None
    assert row["carrier_pgid"] is None


def test_releasing_turn_is_reaped_and_completed_after_restart(dialogue_store, monkeypatch):
    offered = _offer(question="release interrupted by API restart")
    row = dialogue_store[offered["id"]]
    row.update(
        state="releasing",
        question="[released]",
        question_sha256="0" * 64,
        point_of_view="[released]",
        output={"outcome": "tombstoned"},
        claimed_by="stopped-worker",
        carrier_pgid=424242,
    )
    reaped = []

    def reap(pgid):
        reaped.append(pgid)
        return True

    monkeypatch.setattr(dialogue_service, "_reap_recorded_process_group", reap)

    assert dialogue_service.process_dialogue_once() is True
    assert reaped == [424242]
    assert row["state"] == "tombstoned"
    assert row["claimed_by"] is None
    assert row["carrier_pgid"] is None


def test_release_keeps_durable_ownership_when_process_inspection_fails(
    dialogue_store,
    monkeypatch,
):
    offered = _offer(question="retain ownership until the process can be observed")
    row = dialogue_store[offered["id"]]
    row.update(state="running", claimed_by="active-worker", carrier_pgid=616161)
    monkeypatch.setattr(
        dialogue_service,
        "_reap_recorded_process_group",
        lambda _pgid: False,
    )

    assert dialogue_service.release_dialogue(offered["id"], offered["removal_token"])
    assert row["state"] == "releasing"
    assert row["question"] == "[released]"
    assert row["claimed_by"] == "active-worker"
    assert row["carrier_pgid"] == 616161
    assert dialogue_service.process_dialogue_once() is False
    assert row["state"] == "releasing"
    assert row["claimed_by"] == "active-worker"
    assert row["carrier_pgid"] == 616161


def test_windows_release_verifies_and_terminates_the_native_process_tree(monkeypatch):
    calls = []

    def run(command, **_):
        calls.append(command)
        if command[0] == "powershell.exe":
            return SimpleNamespace(stdout="python form_cli_rag.py --native form-cli")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(dialogue_service, "_windows_host", lambda: True)
    monkeypatch.setattr(dialogue_service.subprocess, "run", run)

    assert dialogue_service._reap_recorded_process_group(31337) is True

    assert calls[0][0:4] == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
    ]
    assert calls[1] == ["taskkill", "/PID", "31337", "/T", "/F"]


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


def test_worker_shutdown_waits_and_restart_gets_a_fresh_thread(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    restarted = threading.Event()

    def blocking_tombstone():
        entered.set()
        release.wait()

    monkeypatch.setattr(store, "tombstone_expired", blocking_tombstone)
    monkeypatch.setattr(dialogue_service, "process_dialogue_once", lambda: False)
    dialogue_service._WORKER_STOP.clear()
    dialogue_service._WORKER_THREAD = None
    dialogue_service.ensure_dialogue_worker()
    assert entered.wait(timeout=1)
    first_thread = dialogue_service._WORKER_THREAD

    stopper = threading.Thread(target=dialogue_service.stop_dialogue_worker)
    stopper.start()
    assert stopper.is_alive()
    release.set()
    stopper.join(timeout=1)
    assert not stopper.is_alive()
    assert dialogue_service._WORKER_THREAD is None

    def observe_restart():
        restarted.set()
        dialogue_service._WORKER_STOP.set()

    monkeypatch.setattr(store, "tombstone_expired", observe_restart)
    dialogue_service.ensure_dialogue_worker()
    second_thread = dialogue_service._WORKER_THREAD
    assert second_thread is not None
    assert second_thread is not first_thread
    assert restarted.wait(timeout=1)
    dialogue_service.stop_dialogue_worker()
    assert dialogue_service._WORKER_THREAD is None


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
async def test_http_reply_fixes_parent_and_thread_read_exposes_no_capabilities(monkeypatch):
    captured = {}

    def submit(**values):
        captured.update(values)
        return {
            "id": "dlg_reply",
            "state": "pending",
            "parent_dialogue_id": values["parent_dialogue_id"],
            "removal_token": "reply-removal-token-long-enough",
        }

    monkeypatch.setattr(dialogue_service, "submit_dialogue", submit)
    monkeypatch.setattr(
        dialogue_service,
        "get_dialogue_thread",
        lambda dialogue_id: {
            "root_dialogue_id": "dlg_root",
            "anchor_dialogue_id": dialogue_id,
            "turns": [
                {"id": "dlg_root", "parent_dialogue_id": None},
                {"id": "dlg_reply", "parent_dialogue_id": "dlg_root"},
            ],
            "turn_count": 2,
            "truncated": False,
        },
    )
    body = {
        "question": "The river replies.",
        "point_of_view": "river",
        "locale": "en",
        "public_disclosure_ack": "public-unlisted-thread-v2",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        rejected_override = await client.post(
            "/api/dialogues/dlg_root/replies",
            json={**body, "parent_dialogue_id": "dlg_other"},
        )
        replied = await client.post(
            "/api/dialogues/dlg_root/replies",
            json=body,
        )
        observed = await client.get("/api/dialogues/dlg_reply/thread")

    assert rejected_override.status_code == 422
    assert replied.status_code == 202
    assert replied.headers["cache-control"] == "no-store"
    assert captured["parent_dialogue_id"] == "dlg_root"
    assert observed.status_code == 200
    assert observed.headers["cache-control"] == "no-store"
    assert observed.json()["turn_count"] == 2
    assert "removal_token" not in json.dumps(observed.json())


@pytest.mark.asyncio
async def test_http_thread_read_contains_native_planner_failure(monkeypatch):
    monkeypatch.setattr(
        dialogue_service,
        "get_dialogue_thread",
        lambda _dialogue_id: (_ for _ in ()).throw(
            RuntimeError("private native carrier detail")
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/dialogues/dlg_native/thread")

    assert response.status_code == 503
    assert response.headers["retry-after"] == "15"
    assert response.json()["detail"] == (
        "Native dialogue thread planning is presently unavailable"
    )
    assert "private native carrier detail" not in response.text


@pytest.mark.asyncio
async def test_http_legacy_disclosure_stays_single_turn_only(monkeypatch):
    monkeypatch.setattr(
        dialogue_service,
        "get_dialogue_thread",
        lambda _dialogue_id: (_ for _ in ()).throw(
            dialogue_service.DialogueThreadDisclosureError()
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/dialogues/dlg_legacy/thread")

    assert response.status_code == 403
    assert response.json()["detail"] == "This turn grants single-turn access only"


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
async def test_http_poll_keeps_the_event_loop_available(monkeypatch):
    started = threading.Event()
    read_completed = threading.Event()

    def get_dialogue(dialogue_id):
        started.set()
        read_completed.wait(2)
        return {
            "id": dialogue_id,
            "state": "miss" if read_completed.is_set() else "blocked-loop",
        }

    monkeypatch.setattr(dialogue_service, "get_dialogue", get_dialogue)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        poll_task = asyncio.create_task(client.get("/api/dialogues/dlg_concurrent"))
        try:
            assert await asyncio.to_thread(started.wait, 1)
            info = await client.get("/api/mcp")
            read_completed.set()
            response = await poll_task
        finally:
            read_completed.set()
            if not poll_task.done():
                await poll_task

    assert info.status_code == 200
    assert response.status_code == 200
    assert response.json()["state"] == "miss"


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
    real_now = store._now
    first_release = datetime(2026, 8, 15, 1, 2, 3, tzinfo=timezone.utc)
    retry_release = datetime(2026, 8, 15, 4, 5, 6, tzinfo=timezone.utc)
    monkeypatch.setattr(store, "_now", lambda: first_release)
    assert dialogue_service.release_dialogue(row["id"], token) is True
    released_once = store.get_dialogue(row["id"])
    monkeypatch.setattr(store, "_now", lambda: retry_release)
    assert dialogue_service.release_dialogue(row["id"], token) is True
    assert dialogue_service.release_dialogue(row["id"], "different-capability-token-long-enough") is False
    released = store.get_dialogue(row["id"])
    assert released["state"] == "tombstoned"
    assert released["question"] == "[released]"
    assert released["question_sha256"] == "0" * 64
    assert released["updated_at"] == released_once["updated_at"]
    assert released["tombstoned_at"] == released_once["tombstoned_at"]
    assert released["tombstoned_at"] == first_release.isoformat()
    monkeypatch.setattr(store, "_now", real_now)

    legacy, legacy_token = store.create_dialogue(
        question="This id grants one-turn access only.",
        question_sha256="9" * 64,
        point_of_view="legacy disclosure",
        requested_locale="en",
        canonical_locale="en",
        parent_dialogue_id=None,
        public_disclosure_ack=store.PUBLIC_SINGLE_TURN_DISCLOSURE_ACK,
        channel_timeout_seconds=30,
        network_peer_sha256="9" * 64,
        expires_at=real_now() + timedelta(days=7),
        max_active=8,
        starts_per_window=6,
        start_window_seconds=60,
    )
    assert store.get_dialogue(legacy["id"])["disclosure_ack"] == (
        store.PUBLIC_SINGLE_TURN_DISCLOSURE_ACK
    )
    with pytest.raises(store.PublicDialogueThreadDisclosureError):
        store.get_dialogue_thread(legacy["id"])
    with pytest.raises(ValueError, match="single-turn-only"):
        store.create_dialogue(
            question="A reply cannot widen the earlier disclosure.",
            question_sha256="8" * 64,
            point_of_view="consent boundary",
            requested_locale="en",
            canonical_locale="en",
            parent_dialogue_id=legacy["id"],
            channel_timeout_seconds=30,
            network_peer_sha256="8" * 64,
            expires_at=real_now() + timedelta(days=7),
            max_active=8,
            starts_per_window=6,
            start_window_seconds=60,
        )
    assert dialogue_service.release_dialogue(legacy["id"], legacy_token) is True

    expiry_boundary = datetime(2026, 8, 22, 1, 2, 3, tzinfo=timezone.utc)
    expiring_row, _ = store.create_dialogue(
        question="What remains visible at the expiry boundary?",
        question_sha256="e" * 64,
        point_of_view="river",
        requested_locale="en",
        canonical_locale="en",
        parent_dialogue_id=None,
        channel_timeout_seconds=30,
        network_peer_sha256="c" * 64,
        expires_at=expiry_boundary,
        max_active=8,
        starts_per_window=6,
        start_window_seconds=60,
    )
    claimed = store.claim_next_dialogue("expiry-test-run")
    assert claimed["id"] == expiring_row["id"]
    assert store.finish_dialogue(
        expiring_row["id"],
        "expiry-test-run",
        state="miss",
        output={"outcome": "miss", "answer": ""},
    )
    monkeypatch.setattr(store, "_now", lambda: expiry_boundary)
    expired = store.get_dialogue(expiring_row["id"])
    assert expired["state"] == "tombstoned"
    assert expired["question"] == "[released]"
    assert expired["question_sha256"] == "0" * 64
    assert expired["point_of_view"] == "[released]"
    assert expired["tombstoned_at"] == expiry_boundary.isoformat()
    monkeypatch.setattr(
        store,
        "_now",
        lambda: expiry_boundary + timedelta(minutes=5),
    )
    assert store.get_dialogue(expiring_row["id"])["tombstoned_at"] == expired["tombstoned_at"]
    monkeypatch.setattr(store, "_now", real_now)

    running_expiry = datetime(2026, 8, 22, 6, 7, 8, tzinfo=timezone.utc)
    running_row, _ = store.create_dialogue(
        question="Who owns cleanup after public visibility expires?",
        question_sha256="d" * 64,
        point_of_view="native carrier",
        requested_locale="en",
        canonical_locale="en",
        parent_dialogue_id=None,
        channel_timeout_seconds=30,
        network_peer_sha256="d" * 64,
        expires_at=running_expiry,
        max_active=8,
        starts_per_window=6,
        start_window_seconds=60,
    )
    claimed = store.claim_next_dialogue("running-expiry-test-run")
    assert claimed["id"] == running_row["id"]
    assert store.record_carrier_pgid(
        running_row["id"], "running-expiry-test-run", 424242
    )
    monkeypatch.setattr(store, "_now", lambda: running_expiry)
    public_expiry = store.get_dialogue(running_row["id"])
    assert public_expiry["state"] == "tombstoned"
    assert public_expiry["question"] == "[released]"
    assert public_expiry["question_sha256"] == "0" * 64
    assert public_expiry["point_of_view"] == "[released]"
    assert public_expiry["output"]["outcome"] == "tombstoned"
    with factory() as check_session:
        still_owned = check_session.get(store.PublicDialogueRecord, running_row["id"])
        assert still_owned.state == "running"
        assert still_owned.claimed_by == "running-expiry-test-run"
        assert still_owned.carrier_pgid == 424242
        assert still_owned.question == running_row["question"]
    with pytest.raises(ValueError, match="parent_dialogue_id"):
        store.create_dialogue(
            question="May a new edge attach after the parent expired?",
            question_sha256="1" * 64,
            point_of_view="child turn",
            requested_locale="en",
            canonical_locale="en",
            parent_dialogue_id=running_row["id"],
            channel_timeout_seconds=30,
            network_peer_sha256="1" * 64,
            expires_at=running_expiry + timedelta(days=7),
            max_active=8,
            starts_per_window=6,
            start_window_seconds=60,
        )
    with factory() as check_session:
        rejected_parent = check_session.get(
            store.PublicDialogueRecord, running_row["id"]
        )
        assert rejected_parent.state == "running"
        assert rejected_parent.claimed_by == "running-expiry-test-run"
        assert rejected_parent.carrier_pgid == 424242
    assert store.finish_dialogue(
        running_row["id"],
        "running-expiry-test-run",
        state="miss",
        output={"outcome": "miss", "answer": ""},
    )
    completed_expiry = store.get_dialogue(running_row["id"])
    assert completed_expiry["state"] == "tombstoned"
    assert completed_expiry["tombstoned_at"] == running_expiry.isoformat()
    with factory() as check_session:
        released_after_cleanup = check_session.get(
            store.PublicDialogueRecord, running_row["id"]
        )
        assert released_after_cleanup.state == "tombstoned"
        assert released_after_cleanup.claimed_by is None
        assert released_after_cleanup.carrier_pgid is None
    monkeypatch.setattr(store, "_now", real_now)

    release_row, release_token = store.create_dialogue(
        question="Can release survive between commit and process reaping?",
        question_sha256="2" * 64,
        point_of_view="restart boundary",
        requested_locale="en",
        canonical_locale="en",
        parent_dialogue_id=None,
        channel_timeout_seconds=30,
        network_peer_sha256="2" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        max_active=8,
        starts_per_window=6,
        start_window_seconds=60,
    )
    claimed = store.claim_next_dialogue("release-test-run")
    assert claimed["id"] == release_row["id"]
    assert store.record_carrier_pgid(release_row["id"], "release-test-run", 515151)

    def observe_release_handoff(pgid):
        assert pgid == 515151
        public_release = store.get_dialogue(release_row["id"])
        assert public_release["state"] == "tombstoned"
        assert public_release["question"] == "[released]"
        with factory() as check_session:
            releasing = check_session.get(
                store.PublicDialogueRecord, release_row["id"]
            )
            assert releasing.state == "releasing"
            assert releasing.claimed_by == "release-test-run"
            assert releasing.carrier_pgid == 515151
        return True

    monkeypatch.setattr(
        dialogue_service,
        "_reap_recorded_process_group",
        observe_release_handoff,
    )
    assert dialogue_service.release_dialogue(release_row["id"], release_token)
    with factory() as check_session:
        released = check_session.get(store.PublicDialogueRecord, release_row["id"])
        assert released.state == "tombstoned"
        assert released.claimed_by is None
        assert released.carrier_pgid is None

    terminal_parent_expiry = datetime(2026, 8, 23, 7, 8, 9, tzinfo=timezone.utc)
    terminal_parent, _ = store.create_dialogue(
        question="Can an unswept expired terminal turn receive a child?",
        question_sha256="3" * 64,
        point_of_view="terminal parent",
        requested_locale="en",
        canonical_locale="en",
        parent_dialogue_id=None,
        channel_timeout_seconds=30,
        network_peer_sha256="3" * 64,
        expires_at=terminal_parent_expiry,
        max_active=8,
        starts_per_window=6,
        start_window_seconds=60,
    )
    claimed = store.claim_next_dialogue("terminal-parent-test-run")
    assert claimed["id"] == terminal_parent["id"]
    assert store.finish_dialogue(
        terminal_parent["id"],
        "terminal-parent-test-run",
        state="miss",
        output={"outcome": "miss", "answer": ""},
    )
    monkeypatch.setattr(store, "_now", lambda: terminal_parent_expiry)
    with pytest.raises(ValueError, match="parent_dialogue_id"):
        store.create_dialogue(
            question="This child must not persist.",
            question_sha256="4" * 64,
            point_of_view="child turn",
            requested_locale="en",
            canonical_locale="en",
            parent_dialogue_id=terminal_parent["id"],
            channel_timeout_seconds=30,
            network_peer_sha256="4" * 64,
            expires_at=terminal_parent_expiry + timedelta(days=7),
            max_active=8,
            starts_per_window=6,
            start_window_seconds=60,
        )
    with factory() as check_session:
        no_child = check_session.scalar(
            select(store.PublicDialogueRecord).where(
                store.PublicDialogueRecord.parent_dialogue_id == terminal_parent["id"]
            )
        )
        assert no_child is None
    assert store.get_dialogue(terminal_parent["id"])["state"] == "tombstoned"
    monkeypatch.setattr(store, "_now", real_now)

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


def test_dialogue_thread_survives_database_restart_and_keeps_expiry_boundary(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "dialogue-thread.db"
    first_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    store.PublicDialogueRecord.__table__.create(bind=first_engine, checkfirst=True)

    def session_for(engine):
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

        return session

    monkeypatch.setattr(store.unified_db, "ensure_schema", lambda: None)
    monkeypatch.setattr(store.unified_db, "session", session_for(first_engine))
    expiry_boundary = datetime.now(timezone.utc) + timedelta(seconds=30)
    root, root_token = store.create_dialogue(
        question="What does the river see?",
        question_sha256="a" * 64,
        point_of_view="river",
        requested_locale="en",
        canonical_locale="en",
        parent_dialogue_id=None,
        channel_timeout_seconds=30,
        network_peer_sha256="a" * 64,
        expires_at=expiry_boundary,
        max_active=8,
        starts_per_window=6,
        start_window_seconds=60,
    )
    reply, reply_token = store.create_dialogue(
        question="I see the banks that let me move.",
        question_sha256="b" * 64,
        point_of_view="water",
        requested_locale="en",
        canonical_locale="en",
        parent_dialogue_id=root["id"],
        channel_timeout_seconds=30,
        network_peer_sha256="b" * 64,
        expires_at=expiry_boundary + timedelta(days=7),
        max_active=8,
        starts_per_window=6,
        start_window_seconds=60,
    )
    assert root_token != reply_token
    first_engine.dispose()

    restarted_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setattr(store.unified_db, "session", session_for(restarted_engine))
    persisted = store.get_dialogue_thread(reply["id"])
    assert persisted is not None
    assert persisted["root_dialogue_id"] == root["id"]
    assert persisted["anchor_dialogue_id"] == reply["id"]
    assert [turn["id"] for turn in persisted["turns"]] == [root["id"], reply["id"]]
    assert persisted["turns"][1]["parent_dialogue_id"] == root["id"]
    assert "removal_token" not in json.dumps(persisted)

    monkeypatch.setattr(store, "_now", lambda: expiry_boundary)
    expired = store.get_dialogue_thread(reply["id"])
    assert expired is not None
    assert expired["turns"][0]["state"] == "tombstoned"
    assert expired["turns"][0]["question"] == "[released]"
    assert expired["turns"][1]["question"] == reply["question"]
    bounded = store.get_dialogue_thread(root["id"], max_turns=1)
    assert bounded is not None
    assert bounded["turn_count"] == 1
    assert bounded["truncated"] is True

    third, _ = store.create_dialogue(
        question="The banks answer the water.",
        question_sha256="c" * 64,
        point_of_view="riverbank",
        requested_locale="en",
        canonical_locale="en",
        parent_dialogue_id=reply["id"],
        channel_timeout_seconds=30,
        network_peer_sha256="c" * 64,
        expires_at=expiry_boundary + timedelta(days=7),
        max_active=8,
        starts_per_window=6,
        start_window_seconds=60,
    )
    with session_for(restarted_engine)() as skewed_session:
        skewed_session.get(store.PublicDialogueRecord, root["id"]).created_at = (
            expiry_boundary + timedelta(seconds=3)
        )
        skewed_session.get(store.PublicDialogueRecord, reply["id"]).created_at = (
            expiry_boundary + timedelta(seconds=2)
        )
        skewed_session.get(store.PublicDialogueRecord, third["id"]).created_at = (
            expiry_boundary + timedelta(seconds=1)
        )
    skewed_clock_thread = store.get_dialogue_thread(third["id"])
    assert [turn["id"] for turn in skewed_clock_thread["turns"]] == [
        root["id"],
        reply["id"],
        third["id"],
    ]
    ancestry_window = store.get_dialogue_thread(third["id"], max_turns=2)
    assert ancestry_window is not None
    assert ancestry_window["root_dialogue_id"] is None
    assert ancestry_window["continuation_parent_dialogue_id"] == root["id"]
    assert [turn["id"] for turn in ancestry_window["turns"]] == [
        reply["id"],
        third["id"],
    ]
    assert ancestry_window["anchor_dialogue_id"] == third["id"]
    assert ancestry_window["truncated"] is True
    restarted_engine.dispose()


def test_dialogue_thread_window_semantics_execute_on_native_fkwu():
    created = datetime(2026, 8, 17, tzinfo=timezone.utc)
    candidates = [
        SimpleNamespace(id="dlg_root", parent_dialogue_id=None, created_at=created),
        SimpleNamespace(
            id="dlg_anchor",
            parent_dialogue_id="dlg_root",
            created_at=created + timedelta(seconds=1),
        ),
        SimpleNamespace(
            id="dlg_sibling",
            parent_dialogue_id="dlg_root",
            created_at=created + timedelta(seconds=2),
        ),
        SimpleNamespace(
            id="dlg_child",
            parent_dialogue_id="dlg_anchor",
            created_at=created + timedelta(seconds=3),
        ),
    ]

    plan = store._native_thread_window(candidates, "dlg_anchor", 3)

    assert form_kernel_bridge.active_runtime() == "fkwu"
    assert plan == {
        "root_dialogue_id": "dlg_root",
        "oldest_observed_dialogue_id": "dlg_root",
        "continuation_parent_dialogue_id": None,
        "anchor_dialogue_id": "dlg_anchor",
        "selected_ids": ["dlg_root", "dlg_anchor", "dlg_sibling"],
        "truncated": True,
    }
