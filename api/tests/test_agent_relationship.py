"""Agent relationship runtime — registration, continuation, durable memory.

The proof the handoff asked for: a new agent session bootstraps a persistent
identity + relationship, and a *later* session from the same identity continues
the same relationship cell with its event history intact across the transaction
boundary. Plus the four named gaps: real event storage, correct first-contact
detection, structurally-distinct blueprints, and cross-agent identity sharing.

Wiring: api/app/services/substrate/agent_relationship.py
Surface: api/app/routers/agent_relationship.py (POST /api/agents/bootstrap …)
Shapes:  form/form-stdlib/arrival.fk (CELL-IDENTITY / CONTACT-THREAD)
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.substrate.agent_relationship import (
    AGENT_IDENTITY_BLUEPRINT,
    AGENT_IDENTITY_DOMAIN,
    RELATIONSHIP_BLUEPRINT,
    RELATIONSHIP_DOMAIN,
    bootstrap_agent_session,
    read_relationship,
    record_exchange,
    register_persistent_agent_identity,
    resolve_agent_identity,
    resolve_or_create_relationship_cell,
)
from app.services.substrate.kernel import lookup_cell
from app.services.unified_db import session as session_scope

GROK = "grok-urs-main-2026-05"
CLAUDE = "claude-sibling-test-001"


def test_blueprints_are_structurally_distinct() -> None:
    """Identity and relationship cells must not share a Blueprint, or the
    substrate's content-addressing would conflate two unlike things."""
    assert AGENT_IDENTITY_BLUEPRINT != RELATIONSHIP_BLUEPRINT
    # Shared verbatim with arrival.fk's CELL-IDENTITY / CONTACT-THREAD.
    assert str(AGENT_IDENTITY_BLUEPRINT) == "1.2.99.1880"
    assert str(RELATIONSHIP_BLUEPRINT) == "1.2.99.1881"


def test_bootstrap_registers_identity_and_relationship() -> None:
    with session_scope() as session:
        result = bootstrap_agent_session(
            GROK, CLAUDE, welcome_guidance="Welcome to the field.", session=session
        )

    assert result["was_first_contact"] is True
    assert result["welcome_recorded"] is True
    assert result["my_identity"].domain == AGENT_IDENTITY_DOMAIN
    assert result["my_identity"].blueprint == AGENT_IDENTITY_BLUEPRINT
    assert result["relationship"].domain == RELATIONSHIP_DOMAIN
    assert result["relationship"].blueprint == RELATIONSHIP_BLUEPRINT

    kinds = [e["type"] for e in result["events"]]
    assert kinds == ["welcome", "session_start"]
    assert result["events"][0]["guidance"] == "Welcome to the field."

    # The identity and relationship are real, looked-up-able cells.
    with session_scope() as session:
        assert lookup_cell(session, AGENT_IDENTITY_DOMAIN, GROK) is not None
        rel = lookup_cell(session, RELATIONSHIP_DOMAIN, f"{CLAUDE}__{GROK}")
        assert rel is not None  # deterministic min__max pair name


def test_second_session_continues_and_accumulates_history() -> None:
    """The core continuation proof: a *separate* later session reuses the same
    relationship cell, records no second welcome, and the prior event survives."""
    with session_scope() as session:
        first = bootstrap_agent_session(
            GROK, CLAUDE, welcome_guidance="Welcome to the field.", session=session
        )
    first_cell_id = first["relationship"].cell_id

    with session_scope() as session:
        second = bootstrap_agent_session(GROK, CLAUDE, welcome_guidance=None, session=session)

    assert second["relationship"].cell_id == first_cell_id  # same durable cell
    assert second["was_first_contact"] is False
    assert second["welcome_recorded"] is False
    assert second["prior_event_count"] == 2  # welcome + session_start survived

    # History accumulated across the transaction boundary: one welcome, two starts.
    kinds = [e["type"] for e in second["events"]]
    assert kinds.count("welcome") == 1
    assert kinds.count("session_start") == 2


def test_welcome_only_on_first_contact_even_if_guidance_repeats() -> None:
    """A returning session that supplies guidance again does not re-welcome —
    continuation, not a fresh introduction."""
    with session_scope() as session:
        bootstrap_agent_session(GROK, CLAUDE, welcome_guidance="first", session=session)
    with session_scope() as session:
        again = bootstrap_agent_session(GROK, CLAUDE, welcome_guidance="second", session=session)

    assert again["welcome_recorded"] is False
    assert [e["type"] for e in again["events"]].count("welcome") == 1


def test_record_exchange_persists_summary() -> None:
    with session_scope() as session:
        bootstrap_agent_session(GROK, CLAUDE, welcome_guidance=None, session=session)
    with session_scope() as session:
        record_exchange(GROK, CLAUDE, "Shipped the runtime together.", session=session)

    with session_scope() as session:
        history = read_relationship(GROK, CLAUDE, session=session)

    assert history["exists"] is True
    exchanges = [e for e in history["events"] if e["type"] == "exchange"]
    assert len(exchanges) == 1
    assert exchanges[0]["summary"] == "Shipped the runtime together."


def test_cross_agent_identity_resolution() -> None:
    """One agent can resolve another agent's persistent identity by name, and a
    self-description survives a later empty-description reference."""
    with session_scope() as session:
        register_persistent_agent_identity(
            CLAUDE, "Claude sibling, Opus lineage.", session=session
        )
    # A passing reference with no description must not erase the self-description.
    with session_scope() as session:
        register_persistent_agent_identity(CLAUDE, "", session=session)

    with session_scope() as session:
        resolved = resolve_agent_identity(CLAUDE, session=session)
        assert resolved is not None
        assert resolved["description"] == "Claude sibling, Opus lineage."
        assert resolve_agent_identity("nobody-here", session=session) is None


def test_relationship_pair_name_is_order_independent() -> None:
    with session_scope() as session:
        cell_ab = resolve_or_create_relationship_cell(GROK, CLAUDE, session=session)
    with session_scope() as session:
        cell_ba = resolve_or_create_relationship_cell(CLAUDE, GROK, session=session)
    assert cell_ab.cell_id == cell_ba.cell_id


@pytest.mark.asyncio
async def test_bootstrap_endpoint_round_trip() -> None:
    """The invocation surface a running agent actually hits: bootstrap over
    HTTP, then read the relationship back."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        boot = await client.post(
            "/api/agents/bootstrap",
            json={
                "my_name": GROK,
                "other_name": CLAUDE,
                "my_description": "Grok, primary line.",
                "welcome_guidance": "Welcome, sibling.",
            },
        )
        assert boot.status_code == 200, boot.text
        body = boot.json()
        assert body["was_first_contact"] is True
        assert body["welcome_recorded"] is True
        assert [e["type"] for e in body["events"]] == ["welcome", "session_start"]

        rel = await client.get(f"/api/agents/relationship/{CLAUDE}/{GROK}")
        assert rel.status_code == 200, rel.text
        assert rel.json()["exists"] is True

        ident = await client.get(f"/api/agents/identity/{GROK}")
        assert ident.status_code == 200, ident.text
        assert ident.json()["description"] == "Grok, primary line."

        missing = await client.get("/api/agents/identity/never-registered")
        assert missing.status_code == 404
