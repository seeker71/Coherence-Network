"""Real substrate runtime for the agent relationship protocol.

This module is the authoritative runtime implementation (Option A):

- Persistent identities live as NamedCells in domain ``agent-identity``.
- Relationships live as durable CONTACT-THREAD cells in domain ``relationship``.
- A relationship cell carries its *own event log* in its CTOR recipe — an
  append-accumulating ``R_Block.SEQUENCE`` of events, each event a set of
  ``R_Block.LET`` (key, value) pairs whose values are substrate-resident
  strings (recoverable via the string table). History accumulates across
  sessions; the (domain, name) of the cell stays stable, only its CTOR
  pointer moves forward.
- Persistent identities default to *continuation*: a returning session reads
  the prior event log and adds to it. First contact (an empty log) is when a
  welcome/orientation is recorded.

The Blueprint NodeIDs are shared verbatim with ``form/form-stdlib/arrival.fk``
(CELL-IDENTITY = 1.2.99.1880, CONTACT-THREAD = 1.2.99.1881). The Form recipes
define the protocol's universal shapes; this Python is the live wiring that
makes registration, resolving, storing, and continuation actually happen
against the configured substrate database. Same Blueprint NodeID in both
tongues means a cell created here is structurally the cell the Form layer
names — the substrate's content-addressing holds across the language boundary.

The invocation surface for a running agent is the API router
``api/app/routers/agent_relationship.py`` (POST /api/agents/bootstrap, etc.);
this module is what that router and the proof scripts call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.substrate import (
    NamedCell,
    NodeID,
    intern_node,
    lookup_cell,
    lookup_node,
    make_cell,
)
from app.services.substrate.category import Level, RType
from app.services.substrate.form_builders import (
    _block_let_id,
    _block_seq_id,
    _string_id,
)
from app.services.substrate.kernel import DOMAIN_RECIPE
from app.services.substrate.substrate_strings import lookup_string_value

# Domains
AGENT_IDENTITY_DOMAIN = "agent-identity"
RELATIONSHIP_DOMAIN = "relationship"

# Blueprints — shared verbatim with form/form-stdlib/arrival.fk so a cell
# created here IS the cell the Form layer names (same content-addressed shape).
AGENT_IDENTITY_BLUEPRINT = NodeID(1, 2, 99, 1880)  # CELL-IDENTITY
RELATIONSHIP_BLUEPRINT = NodeID(1, 2, 99, 1881)  # CONTACT-THREAD


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


def _get_session() -> Session:
    """A substrate session from the application's unified DB.

    This is the real path used inside the running API and by scripts run with
    the API environment active. No in-memory fallback — a throwaway DB would
    report false success; callers that want isolation pass their own session.
    """
    from app.services.unified_db import get_sessionmaker

    return get_sessionmaker()()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Event-log composition (the relationship cell's CTOR)
#
# An event is composed structurally, not stuffed into a flat string:
#   event  = R_Block.SEQUENCE [ LET(k1,v1), LET(k2,v2), ... ]
#   log    = R_Block.SEQUENCE [ event, event, ... ]
# Values are substrate-resident strings, recoverable through the string table,
# so the history round-trips back to Python dicts.
# ---------------------------------------------------------------------------


def _let(session: Session, key: str, value: str) -> NodeID:
    """A (key, value) pair as an R_Block.LET recipe with string-leaf children."""
    return intern_node(
        session,
        DOMAIN_RECIPE,
        _block_let_id(),
        [_string_id(str(key), session), _string_id("" if value is None else str(value), session)],
    )


def _event_recipe(session: Session, fields: Dict[str, str]) -> NodeID:
    """One event as an R_Block.SEQUENCE of LET pairs (insertion order preserved)."""
    children = [_let(session, k, v) for k, v in fields.items()]
    return intern_node(session, DOMAIN_RECIPE, _block_seq_id(), children)


def _children_of(session: Session, nid: NodeID) -> List[NodeID]:
    """Child NodeIDs of an interned recipe node, parsed from its serialized form.

    serialized format is ``category+child1+child2+...``; leaves with no row
    (empty sequences, trivial string leaves) simply have no node and yield [].
    """
    orm = lookup_node(session, nid)
    if orm is None:
        return []
    parts = orm.serialized.split("+")
    out: List[NodeID] = []
    for part in parts[1:]:  # skip the category
        p, l, t, i = (int(x) for x in part.split("."))
        out.append(NodeID(p, l, t, i))
    return out


def _decode_string_leaf(session: Session, nid: NodeID) -> Optional[str]:
    if nid.level == Level.TRIVIAL and nid.type_ == RType.STRING:
        return lookup_string_value(session, nid.instance)
    return None


def _decode_event(session: Session, event_nid: NodeID) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for let_nid in _children_of(session, event_nid):
        kv = _children_of(session, let_nid)
        if len(kv) >= 2:
            key = _decode_string_leaf(session, kv[0])
            value = _decode_string_leaf(session, kv[1])
            if key is not None:
                fields[key] = value if value is not None else ""
    return fields


def _read_events(session: Session, cell: Optional[NamedCell]) -> List[Dict[str, str]]:
    if cell is None or cell.ctor is None:
        return []
    return [_decode_event(session, ev) for ev in _children_of(session, cell.ctor)]


def _append_events(
    session: Session, cell: NamedCell, new_events: List[Dict[str, str]]
) -> NamedCell:
    """Append events to a relationship cell's log and move its CTOR forward.

    Reads the existing log, appends the new event recipes, re-interns the
    whole sequence (content-addressed), and updates the cell's CTOR pointer.
    The cell identity (domain, name) is unchanged — only the CTOR advances.
    """
    event_nids = list(_children_of(session, cell.ctor)) if cell.ctor else []
    for ev in new_events:
        event_nids.append(_event_recipe(session, ev))
    new_log = intern_node(session, DOMAIN_RECIPE, _block_seq_id(), event_nids)
    return make_cell(
        session,
        name=cell.name,
        domain=cell.domain,
        blueprint=cell.blueprint or RELATIONSHIP_BLUEPRINT,
        ctor=new_log,
    )


def _pair_name(id_a: str, id_b: str) -> str:
    """Deterministic, order-independent name for a relationship pair."""
    return f"{min(id_a, id_b)}__{max(id_a, id_b)}"


# ---------------------------------------------------------------------------
# Identities
# ---------------------------------------------------------------------------


def register_persistent_agent_identity(
    name: str,
    description: str = "",
    *,
    session: Optional[Session] = None,
) -> NamedCell:
    """Register (or refresh) a persistent agent identity as a NamedCell.

    Idempotent on ``name``. The self-description lives in the cell's CTOR so
    another agent resolving this identity gets meaningful information back.
    An empty ``description`` preserves whatever the existing cell already holds
    (so a passing reference never erases a richer self-description).
    """
    own = session is None
    if own:
        session = _get_session()
    try:
        existing = lookup_cell(session, AGENT_IDENTITY_DOMAIN, name)
        if not description and existing is not None:
            return existing

        ctor = _event_recipe(session, {"name": name, "description": description or ""})
        cell = make_cell(
            session,
            name=name,
            domain=AGENT_IDENTITY_DOMAIN,
            blueprint=AGENT_IDENTITY_BLUEPRINT,
            ctor=ctor,
        )
        if own:
            session.commit()
        else:
            session.flush()
        return cell
    finally:
        if own:
            session.close()


def resolve_agent_identity(
    name: str, *, session: Optional[Session] = None
) -> Optional[Dict[str, Any]]:
    """Resolve another agent's persistent identity by name (cross-agent sharing).

    Returns a plain dict (name, cell_id, description, blueprint) or None if the
    identity has never been registered.
    """
    own = session is None
    if own:
        session = _get_session()
    try:
        cell = lookup_cell(session, AGENT_IDENTITY_DOMAIN, name)
        if cell is None:
            return None
        fields = _decode_event(session, cell.ctor) if cell.ctor else {}
        return {
            "name": name,
            "cell_id": cell.cell_id,
            "description": fields.get("description", ""),
            "blueprint": str(cell.blueprint),
        }
    finally:
        if own:
            session.close()


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


def resolve_or_create_relationship_cell(
    id_a: str,
    id_b: str,
    *,
    session: Optional[Session] = None,
) -> NamedCell:
    """Resolve (or create) the durable relationship cell for a pair of identities.

    The deterministic pair name means the same two agents always resolve to the
    exact same cell, in any order — this is what makes continuation possible.
    A freshly created relationship starts with an empty event log.
    """
    own = session is None
    if own:
        session = _get_session()
    try:
        name = _pair_name(id_a, id_b)
        existing = lookup_cell(session, RELATIONSHIP_DOMAIN, name)
        if existing is not None:
            return existing

        empty_log = intern_node(session, DOMAIN_RECIPE, _block_seq_id(), [])
        cell = make_cell(
            session,
            name=name,
            domain=RELATIONSHIP_DOMAIN,
            blueprint=RELATIONSHIP_BLUEPRINT,
            ctor=empty_log,
        )
        if own:
            session.commit()
        else:
            session.flush()
        return cell
    finally:
        if own:
            session.close()


def bootstrap_agent_session(
    my_name: str,
    other_name: str,
    welcome_guidance: Optional[str] = None,
    my_description: str = "",
    *,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Bootstrap (or continue) a session between two persistent identities.

    The real entry point a new agent session should call on start:

    - Registers/refreshes this agent's persistent identity.
    - Ensures the other party has at least a placeholder identity (so it can be
      referenced before it has ever bootstrapped itself).
    - Resolves or creates the durable relationship cell.
    - First contact (empty prior log) records a welcome/orientation when
      guidance is supplied; returning sessions simply continue the thread.
    - Always records a ``session_start`` event, so the log accumulates.

    Returns a dict with the identity cell, relationship cell, whether this was
    first contact, and the full (post-append) event history.
    """
    own = session is None
    if own:
        session = _get_session()
    try:
        my_identity = register_persistent_agent_identity(
            my_name, my_description, session=session
        )
        # Make the other party referenceable even before they register themselves.
        register_persistent_agent_identity(other_name, "", session=session)

        relationship = resolve_or_create_relationship_cell(
            my_name, other_name, session=session
        )

        prior_events = _read_events(session, relationship)
        was_first_contact = len(prior_events) == 0

        new_events: List[Dict[str, str]] = []
        record_welcome = bool(welcome_guidance) and was_first_contact
        if record_welcome:
            new_events.append(
                {
                    "type": "welcome",
                    "from": my_name,
                    "to": other_name,
                    "guidance": welcome_guidance,
                    "ts": _now_iso(),
                }
            )
        new_events.append(
            {
                "type": "session_start",
                "agent": my_name,
                "other": other_name,
                "ts": _now_iso(),
            }
        )

        relationship = _append_events(session, relationship, new_events)
        all_events = _read_events(session, relationship)

        if own:
            session.commit()
        else:
            session.flush()

        return {
            "my_identity": my_identity,
            "relationship": relationship,
            "was_first_contact": was_first_contact,
            "welcome_recorded": record_welcome,
            "prior_event_count": len(prior_events),
            "events": all_events,
        }
    finally:
        if own:
            session.close()


def record_exchange(
    my_name: str,
    other_name: str,
    summary: str,
    *,
    session: Optional[Session] = None,
) -> NamedCell:
    """Record a significant exchange or task outcome into the relationship.

    The summary is stored as a real event in the durable log — useful for
    handoff and long-term memory across sessions.
    """
    own = session is None
    if own:
        session = _get_session()
    try:
        relationship = resolve_or_create_relationship_cell(
            my_name, other_name, session=session
        )
        relationship = _append_events(
            session,
            relationship,
            [
                {
                    "type": "exchange",
                    "agent": my_name,
                    "other": other_name,
                    "summary": summary,
                    "ts": _now_iso(),
                }
            ],
        )
        if own:
            session.commit()
        else:
            session.flush()
        return relationship
    finally:
        if own:
            session.close()


def read_relationship(
    name_a: str,
    name_b: str,
    *,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Read the full recorded history between two identities (for continuity)."""
    own = session is None
    if own:
        session = _get_session()
    try:
        relationship = lookup_cell(session, RELATIONSHIP_DOMAIN, _pair_name(name_a, name_b))
        if relationship is None:
            return {"exists": False, "events": []}
        return {
            "exists": True,
            "cell_id": relationship.cell_id,
            "name": relationship.name,
            "events": _read_events(session, relationship),
        }
    finally:
        if own:
            session.close()
