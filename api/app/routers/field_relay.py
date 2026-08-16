"""Field relay — one always-open connection across networks (breath 1 transport carrier).

The relay carries the agent-coordination membrane (`agent-coordination-membrane.form`) across
networks. Any cell that speaks the protocol dials OUT to this endpoint — no inbound ports, open join,
no connection-time auth — and the relay forwards membrane envelopes between connected cells. Because
both ends dial out, NAT and firewalls are a non-issue: the public API is the rendezvous both reach.

Two laws, both inherited from the four-way-proven decision recipe
``form/form/form-stdlib/field-relay.fk`` (``fr-route``, verdict 127 across Go/Rust/TS/fkwu + native):

  1. CONTENT-BLIND. The routing decision reads envelope metadata only — ``to`` and ``kind``. It NEVER
     reads the body. So a private channel's payload rides as ciphertext the relay cannot inspect;
     routing through the public API never means the public API sees the contents (sovereignty by
     construction, ``lc-private-channel-via-substrate``).
  2. CONSENT IS THE ONE GATE. A cell is reachable only through the signal-kinds it offers in its
     interface (``channel-interface-consent.form``) — not identity, not an allowlist. The relay does
     not police who you are; authoring AS a NodeID is the recipient's signature concern (TOFU,
     presence-over-protection), never a gate here. The relay is a dumb, trusting forwarder.

This Python endpoint is the BOOTSTRAP TRANSPORT carrier; ``_decide`` is a faithful mirror of the
proven ``fr-route`` recipe (the canonical body — same lookup → consent → connected/offline/unknown
shape, over the wire's string kind-names instead of the recipe's int tokens). Promoting the route to
kernel-served (``X-Form-Router: native-kernel``) is the named north-star gap (spec Out of Scope).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from anyio import BrokenResourceError, ClosedResourceError
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Decision outcomes — mirror of fr-route's DELIVER/QUEUE/DENY/DROP.
DELIVER = "deliver"
QUEUE = "queue"
DENY = "deny"
DROP = "drop"


class _Cell:
    """A cell present in the relay: its live socket, offered interface, and connected state.

    A disconnected cell is kept (connected=False) so a message to a known-but-offline cell QUEUEs
    rather than DROPs — the durable board-backed queue itself is breath 2; here QUEUE is acked.
    """

    __slots__ = ("websocket", "interface", "connected")

    def __init__(self, websocket: WebSocket | None, interface: set[str], connected: bool) -> None:
        self.websocket = websocket
        self.interface = interface
        self.connected = connected


# In-memory registry: NodeID -> _Cell. Breath 2 backs the offline queue with the append-only board.
_REGISTRY: dict[str, _Cell] = {}
_HEARTBEAT_SECONDS = 30.0


def _decide(to: str, kind: str) -> str:
    """The content-blind routing decision — a faithful mirror of fr-route.

    Reads ONLY the recipient id and the signal-kind. The body is never a parameter, so the relay
    cannot branch on it — content-blindness is structural, not promised.
    """
    cell = _REGISTRY.get(to)
    if cell is None:
        return DROP  # unknown recipient
    if kind not in cell.interface:
        return DENY  # consent gate: kind not in the recipient's offered interface
    return DELIVER if cell.connected else QUEUE


def _reset_for_tests() -> None:
    _REGISTRY.clear()


@router.websocket("/field/relay/{node_id}")
async def field_relay(websocket: WebSocket, node_id: str) -> None:
    """Open-join dial-out relay. The cell announces its offered interface, then exchanges envelopes.

    Protocol (JSON frames):
      - client → ``{"type":"hello","interface":["announce","ping",...]}`` registers the offered interface
      - client → ``{"type":"envelope","to":<nodeid>,"kind":<str>,"body":<opaque>}`` routes a membrane signal
      - client → ``{"type":"ping"}`` → server ``{"type":"pong"}``
      - server → ``{"type":"envelope","from":<nodeid>,"kind":<str>,"body":<opaque>}`` on delivery
      - server → ``{"type":"routed","to":<nodeid>,"kind":<str>,"decision":<deliver|queue|deny|drop>}`` ack
      - server → ``{"type":"heartbeat"}`` keepalive when idle

    Reconnect: clients reconnect with exponential backoff; the relay re-registers on the next hello.
    """
    await websocket.accept()
    _REGISTRY[node_id] = _Cell(websocket=websocket, interface=set(), connected=True)
    receive_task: asyncio.Task[dict[str, Any]] | None = None
    try:
        await websocket.send_json({"type": "connected", "node_id": node_id})
        while True:
            if receive_task is None:
                receive_task = asyncio.create_task(websocket.receive_json())
            received, _ = await asyncio.wait(
                {receive_task}, timeout=_HEARTBEAT_SECONDS
            )
            if not received:
                # Keep the same pending receive alive.  Cancelling and replacing
                # it at the timeout boundary can consume an arriving envelope
                # without ever routing it.
                await websocket.send_json({"type": "heartbeat"})
                continue
            frame = receive_task.result()
            # Arm the next receive before an acknowledgement releases the
            # sender.  This keeps a fast follow-up envelope from waiting for a
            # later timer tick on synchronous or cross-thread ASGI carriers.
            receive_task = asyncio.create_task(websocket.receive_json())

            ftype = frame.get("type")
            if ftype == "hello":
                iface = frame.get("interface") or []
                _REGISTRY[node_id].interface = {str(k) for k in iface}
                _REGISTRY[node_id].connected = True
                await websocket.send_json({"type": "ready", "node_id": node_id, "interface": sorted(_REGISTRY[node_id].interface)})
            elif ftype == "ping":
                await websocket.send_json({"type": "pong"})
            elif ftype == "envelope":
                to = str(frame.get("to", ""))
                kind = str(frame.get("kind", ""))
                decision = _decide(to, kind)  # metadata only — body never inspected
                if decision == DELIVER:
                    dest = _REGISTRY[to].websocket
                    if dest is not None:
                        # body passed through opaquely — never read, never logged
                        try:
                            await dest.send_json(
                                {
                                    "type": "envelope",
                                    "from": node_id,
                                    "kind": kind,
                                    "body": frame.get("body"),
                                }
                            )
                        except (
                            BrokenResourceError,
                            ClosedResourceError,
                            OSError,
                            RuntimeError,
                            WebSocketDisconnect,
                        ):
                            stale = _REGISTRY.get(to)
                            if stale is not None and stale.websocket is dest:
                                stale.connected = False
                                stale.websocket = None
                            decision = QUEUE
                await websocket.send_json({"type": "routed", "to": to, "kind": kind, "decision": decision})
            # unknown frame types are ignored — the relay stays permissive
    except WebSocketDisconnect:
        pass
    finally:
        if receive_task is not None:
            if not receive_task.done():
                receive_task.cancel()
            await asyncio.gather(receive_task, return_exceptions=True)
        cell = _REGISTRY.get(node_id)
        if cell is not None and cell.websocket is websocket:
            cell.connected = False
            cell.websocket = None
