"""Thin byte carrier for the native Form federation graph.

Python owns process transport and the SQL projection. Form owns message
identity, edge composition, durable graph indexes, and traversal.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_IMAGE_ROOT = Path("/app")
_LOCK = threading.Lock()
_ID = re.compile(r"^msg_[0-9a-f]{64}$")


def _binary() -> Path:
    for path in (_IMAGE_ROOT / "form" / "form-cli", _REPO_ROOT / "form" / "form-cli"):
        if path.is_file() and os.access(path, os.X_OK):
            return path
    raise RuntimeError("native Form federation carrier is unavailable")


def store_path() -> Path:
    raw = os.environ.get("COHERENCE_FORM_GRAPH_STORE")
    path = Path(raw).expanduser() if raw else Path(tempfile.gettempdir()) / "coherence-federation-graph"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _token(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=") or "_"


def _run(command: str) -> str:
    with _LOCK:
        proc = subprocess.run(
            [str(_binary())], input=f"fsh {command}\n", text=True,
            capture_output=True, check=False, timeout=10,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"native Form federation command failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def offer(*, from_node: str, to_node: str | None, kind: str, text: str,
          payload: dict[str, Any], timestamp: str) -> dict[str, str]:
    # Variable-width user bytes are encoded only for the space-delimited carrier;
    # Form still receives and hashes every byte and makes every graph decision.
    command = " ".join((
        "federation-offer", str(store_path()), _token(from_node),
        "-" if to_node is None else _token(to_node), _token(kind), _token(text),
        _token(json.dumps(payload, sort_keys=True, separators=(",", ":"))), _token(timestamp),
    ))
    fields = dict(part.split("=", 1) for part in _run(command).split("|") if "=" in part)
    message_id = fields.get("message_id", "")
    if fields.get("ack") != "node" or not _ID.fullmatch(message_id):
        raise RuntimeError(f"native Form federation offer was not witnessed: {fields}")
    for required in ("persisted", "traversable", "observed"):
        if fields.get(required) != "1":
            raise RuntimeError(f"native Form federation receipt lacks {required}=1")
    return fields


def _ids(command: str) -> list[str]:
    values = [line for line in _run(command).splitlines() if line]
    if any(not _ID.fullmatch(value) for value in values):
        raise RuntimeError("native Form federation traversal returned an invalid node id")
    return values


def visible_ids(node_id: str) -> list[str]:
    store = str(store_path())
    direct = _ids(f"federation-incoming {store} {_token(node_id)}")
    broadcasts = _ids(f"federation-broadcasts {store}")
    return list(dict.fromkeys(direct + broadcasts))


def has(message_id: str) -> bool:
    if not _ID.fullmatch(message_id):
        return False
    return _run(f"federation-has {store_path()} {message_id}") == "1"
