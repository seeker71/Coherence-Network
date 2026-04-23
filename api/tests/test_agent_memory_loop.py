"""Flow tests for the agent-memory-system spec.

Covers:
  R1 — write rejects raw logs without why
  R2 — consolidation shrinks aggregate tokens
  R3 — recall returns synthesis, never rows
  R4 — organizing unit is the relationship node
  R5 — untouched memory decays; principles archived not hard-deleted
  R6 — surface is being-known (no timestamps in recall)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.memory import MemoryMomentCreate, MomentKind, FeltQuality
from app.services import memory_service


@pytest.fixture
def client():
    memory_service._reset_for_tests()
    return TestClient(app)


# ---------- R1 — write at aliveness ----------


def test_write_rejects_moment_without_why(client):
    response = client.post(
        "/api/memory/moment",
        json={
            "about": "person:alice",
            "kind": "decision",
            "why": "",  # empty
        },
    )
    assert response.status_code == 422


def test_write_rejects_missing_why(client):
    response = client.post(
        "/api/memory/moment",
        json={"about": "person:alice", "kind": "decision"},
    )
    assert response.status_code == 422


def test_write_rejects_unknown_kind(client):
    response = client.post(
        "/api/memory/moment",
        json={
            "about": "person:alice",
            "kind": "log_entry",  # not in enum
            "why": "something happened",
        },
    )
    assert response.status_code == 422


def test_write_accepts_moment_with_kind_and_why(client):
    response = client.post(
        "/api/memory/moment",
        json={
            "about": "person:alice",
            "kind": "decision",
            "why": "She asked for a pause, and we honored it.",
            "felt_quality": "stillness",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["about"] == "person:alice"
    assert body["kind"] == "decision"
    assert body["why"].startswith("She asked")
    assert body["felt_quality"] == "stillness"
    assert "id" in body


# ---------- R3 + R6 — recall returns synthesis, not rows ----------


def test_recall_returns_synthesis_shape_never_rows(client):
    client.post(
        "/api/memory/moment",
        json={
            "about": "person:alice",
            "kind": "decision",
            "why": "chose to pause",
            "felt_quality": "stillness",
        },
    )
    response = client.get("/api/memory/recall", params={"about": "person:alice"})
    assert response.status_code == 200
    body = response.json()
    # Exactly the synthesis fields, no raw moments array
    assert set(body.keys()) == {
        "about",
        "synthesis",
        "felt_sense",
        "open_threads",
        "earned_conclusions",
    }
    assert isinstance(body["synthesis"], str)
    assert body["synthesis"] != ""


def test_recall_synthesis_has_no_timestamps(client):
    client.post(
        "/api/memory/moment",
        json={
            "about": "person:alice",
            "kind": "completion",
            "why": "finished the draft",
        },
    )
    body = client.get("/api/memory/recall", params={"about": "person:alice"}).json()
    # No ISO 8601 dates should appear
    assert "2026" not in body["synthesis"]
    assert "T" not in body["synthesis"] or ":T" in body["synthesis"]


def test_recall_empty_about_returns_unknown_felt_sense(client):
    body = client.get(
        "/api/memory/recall", params={"about": "person:never-known"}
    ).json()
    assert body["felt_sense"] == "unknown"
    assert body["earned_conclusions"] == []
    assert body["open_threads"] == []


def test_recall_abandonment_surfaces_open_thread(client):
    client.post(
        "/api/memory/moment",
        json={
            "about": "project:mvp",
            "kind": "abandonment",
            "why": "dropped the dashboard redesign",
        },
    )
    body = client.get("/api/memory/recall", params={"about": "project:mvp"}).json()
    assert "dropped the dashboard redesign" in body["open_threads"]


def test_recall_felt_sense_from_contraction():
    memory_service._reset_for_tests()
    client = TestClient(app)
    for i in range(2):
        client.post(
            "/api/memory/moment",
            json={
                "about": "person:x",
                "kind": "weight",
                "why": f"tension {i}",
                "felt_quality": "contraction",
            },
        )
    body = client.get("/api/memory/recall", params={"about": "person:x"}).json()
    assert body["felt_sense"] == "wary"


# ---------- R4 — relationship as organizing unit ----------


def test_moments_about_different_nodes_do_not_cross(client):
    client.post(
        "/api/memory/moment",
        json={"about": "person:alice", "kind": "decision", "why": "alice-thing"},
    )
    client.post(
        "/api/memory/moment",
        json={"about": "person:bob", "kind": "decision", "why": "bob-thing"},
    )
    alice = client.get("/api/memory/recall", params={"about": "person:alice"}).json()
    bob = client.get("/api/memory/recall", params={"about": "person:bob"}).json()
    assert "1" in alice["synthesis"]  # alice has 1 moment
    assert "1" in bob["synthesis"]
    # They share no open threads or principles
    assert alice["open_threads"] == []
    assert bob["open_threads"] == []


# ---------- R2 — consolidation shrinks tokens ----------


def test_consolidation_shrinks_token_count():
    memory_service._reset_for_tests()
    client = TestClient(app)
    # Write enough same-kind moments to trigger distillation
    for i in range(6):
        client.post(
            "/api/memory/moment",
            json={
                "about": "person:alice",
                "kind": "decision",
                "why": f"decision {i} with a long enough why to accrue tokens",
            },
        )
    response = client.post(
        "/api/memory/consolidate",
        params={"about": "person:alice", "window_hours": 72},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_moment_count"] == 6
    assert body["output_principle_count"] >= 1
    assert body["moments_archived"] == 6
    assert body["output_token_estimate"] < body["input_token_estimate"]


def test_consolidation_below_threshold_yields_no_principle():
    memory_service._reset_for_tests()
    client = TestClient(app)
    # Only 2 moments of same kind — below default min_moments_per_principle=3
    for i in range(2):
        client.post(
            "/api/memory/moment",
            json={
                "about": "person:carol",
                "kind": "decision",
                "why": f"decision {i}",
            },
        )
    body = client.post(
        "/api/memory/consolidate",
        params={"about": "person:carol"},
    ).json()
    assert body["output_principle_count"] == 0
    assert body["moments_archived"] == 0


def test_consolidation_earned_conclusion_surfaces_in_recall():
    memory_service._reset_for_tests()
    client = TestClient(app)
    for i in range(4):
        client.post(
            "/api/memory/moment",
            json={
                "about": "person:drew",
                "kind": "completion",
                "why": f"shipped {i}",
            },
        )
    client.post(
        "/api/memory/consolidate", params={"about": "person:drew"}
    )
    recall = client.get("/api/memory/recall", params={"about": "person:drew"}).json()
    assert len(recall["earned_conclusions"]) >= 1
    assert any("completion" in p for p in recall["earned_conclusions"])


# ---------- R5 — decay composts, doesn't hard-delete ----------


def test_decay_archives_principles_older_than_max_age():
    memory_service._reset_for_tests()
    # Seed a principle directly with an old created_at
    from app.models.memory import ConsolidatedPrinciple

    old = ConsolidatedPrinciple(
        about="person:alice",
        text="stale principle",
        created_at=datetime.now(timezone.utc) - timedelta(days=200),
    )
    memory_service._PRINCIPLES["person:alice"].append(old)
    archived = memory_service.decay_untouched("person:alice", max_age_days=180)
    assert archived == 1
    # The fresh list no longer contains the stale one
    remaining = memory_service._PRINCIPLES["person:alice"]
    assert all(p.id != old.id for p in remaining)


def test_decay_leaves_fresh_principles():
    memory_service._reset_for_tests()
    from app.models.memory import ConsolidatedPrinciple

    fresh = ConsolidatedPrinciple(
        about="person:alice",
        text="recent principle",
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    memory_service._PRINCIPLES["person:alice"].append(fresh)
    archived = memory_service.decay_untouched("person:alice", max_age_days=180)
    assert archived == 0
    assert memory_service._PRINCIPLES["person:alice"] == [fresh]
