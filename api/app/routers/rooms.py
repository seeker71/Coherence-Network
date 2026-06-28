"""Encrypted-room dead-drop carrier — a thin, opaque ciphertext key-value store.

This is a CARRIER, not a body. It holds end-to-end-encrypted blobs keyed by
(room_id, addr) and never decrypts them — the cipher, the addressing, the
membership, and the sync logic all live in Form (form-stdlib/conversation-sync.fk
over storage-port.fk; the encrypt-before-publish layer over sha256/hmac-sha256).
The server only ever sees ciphertext it cannot read, so a leak here exposes no
content. This is the "sovereign API KV" storage-port backend: a device PUBLISHES a
sealed blob, another device PULLS it and decrypts with the room key it alone holds.

Surface (mounted at /api/rooms):
  PUT  /api/rooms/{room_id}/{addr}   body = ciphertext text  -> {"stored": addr}
  GET  /api/rooms/{room_id}          -> {"room": id, "keys": [addr, ...]}   (the OFFER set)
  GET  /api/rooms/{room_id}/{addr}   -> ciphertext text (text/plain)

room_id / addr are opaque content-addresses; only [A-Za-z0-9_-] up to 128 chars are
accepted, so no value can escape the carrier's storage root (no path traversal).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response

router = APIRouter()

# Opaque blob store root. A mounted volume in production keeps it durable across
# deploys; defaults under the home dir for local runs.
_ROOT = Path(
    os.environ.get("COHERENCE_ROOMS_DIR")
    or (Path.home() / ".coherence-network" / "rooms-carrier")
).expanduser()

# Content-addresses and room ids are opaque tokens; this charset cannot traverse.
_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# A single sealed blob is small (one room's ciphertext); cap to refuse abuse.
_MAX_BLOB = 1_048_576  # 1 MiB of ciphertext text


def _safe(token: str, what: str) -> str:
    if not _SAFE.match(token or ""):
        raise HTTPException(status_code=400, detail=f"invalid {what}")
    return token


def _room_dir(room_id: str) -> Path:
    d = _ROOT / _safe(room_id, "room_id")
    # resolve() + containment check is belt-and-suspenders over the charset gate.
    rd = d.resolve()
    if not str(rd).startswith(str(_ROOT.resolve())):
        raise HTTPException(status_code=400, detail="invalid room_id")
    return rd


@router.put("/{room_id}/{addr}")
async def put_blob(room_id: str, addr: str, request: Request) -> dict:
    _safe(addr, "addr")
    body = await request.body()
    if len(body) > _MAX_BLOB:
        raise HTTPException(status_code=413, detail="blob too large")
    rd = _room_dir(room_id)
    rd.mkdir(parents=True, exist_ok=True)
    # Last-write-wins on re-put, matching conversation-sync's storage-put contract.
    (rd / _safe(addr, "addr")).write_bytes(body)
    return {"stored": addr}


@router.get("/{room_id}")
def list_keys(room_id: str) -> dict:
    rd = _room_dir(room_id)
    keys = sorted(p.name for p in rd.iterdir() if p.is_file()) if rd.exists() else []
    return {"room": room_id, "keys": keys}


@router.get("/{room_id}/{addr}")
def get_blob(room_id: str, addr: str) -> Response:
    rd = _room_dir(room_id)
    p = rd / _safe(addr, "addr")
    if not p.is_file():
        raise HTTPException(status_code=404, detail="not found")
    # The carrier returns opaque ciphertext; it never parses or decrypts it.
    return Response(content=p.read_bytes(), media_type="text/plain")
