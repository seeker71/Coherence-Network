"""Thin durable carrier admitted by the native Form federation recipe.

Form owns which operation shapes enter. Python carries content-addressed bytes
and filesystem indexes without interpreting message text.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.services import form_kernel_bridge

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOCK = threading.RLock()
_ID = re.compile(r"^msg_[0-9a-f]{64}$")
_RECIPE = _REPO_ROOT / "api" / "app" / "form_recipes" / "public_federation_graph_cli.fk"
_BAND_ENTRY = "(pfgc-band))"

if sys.platform == "win32":
    import msvcrt

    def _lock_file(stream: Any) -> None:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock_file(stream: Any) -> None:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_file(stream: Any) -> None:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)

    def _unlock_file(stream: Any) -> None:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def store_path() -> Path:
    raw = os.environ.get("COHERENCE_FORM_GRAPH_STORE")
    path = Path(raw).expanduser() if raw else Path(tempfile.gettempdir()) / "coherence-federation-graph"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _token(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=") or "_"


def _admit(operation: int, *shape: int) -> None:
    """Offer the actual operation and encoded message shape to Form."""
    if len(shape) != 6 or any(value < 0 for value in shape):
        raise RuntimeError("native Form federation admission shape is invalid")
    source = _RECIPE.read_text(encoding="utf-8")
    if source.count(_BAND_ENTRY) != 1:
        raise RuntimeError("native Form federation admission entry is unavailable")
    invocation = f"(pfgc-admit {operation} {' '.join(str(value) for value in shape)}))"
    admitted = form_kernel_bridge.run_recipe(
        source.replace(_BAND_ENTRY, invocation),
        timeout=10,
    )
    if admitted != "1":
        raise RuntimeError("native Form federation admission was not witnessed")


def _field(value: str) -> str:
    return f"{len(value)}:{value}"


def _message_id(*values: str) -> str:
    canonical = "federation-message-v1|" + "".join(_field(value) for value in values)
    digest = hashlib.sha256(
        b"form-cli-carrier-challenge-v1\n" + canonical.encode("ascii")
    ).hexdigest()
    return f"msg_{digest}"


def _path(name: str) -> Path:
    return store_path() / name


def _read_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [value for value in path.read_text(encoding="ascii").splitlines() if _ID.fullmatch(value)]


@contextmanager
def _index_transaction():
    """Serialize one index mutation across threads and API processes."""
    lock_path = _path(".index.lock")
    with _LOCK, lock_path.open("a+b") as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"\0")
            stream.flush()
        _lock_file(stream)
        try:
            yield
        finally:
            _unlock_file(stream)


def _append_id(path: Path, message_id: str) -> None:
    with _index_transaction():
        ids = _read_ids(path)
        if message_id not in ids:
            _atomic_write_ascii(
                path,
                "".join(f"{value}\n" for value in [*ids, message_id]),
            )


def _atomic_write_ascii(path: Path, content: str) -> None:
    """Publish one complete carrier file or leave the previous value intact."""
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="ascii", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def offer(*, from_node: str, to_node: str | None, kind: str, text: str,
          payload: dict[str, Any], timestamp: str) -> dict[str, str]:
    # Variable-width user bytes remain opaque, path-safe payloads in this membrane;
    # Form receives the concrete operation and encoded field widths before a write.
    encoded_from = _token(from_node)
    encoded_to = "" if to_node is None else _token(to_node)
    encoded_kind = _token(kind)
    encoded_text = _token(text)
    encoded_payload = _token(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    encoded_timestamp = _token(timestamp)
    _admit(
        1,
        len(encoded_from),
        len(encoded_to),
        len(encoded_kind),
        len(encoded_text),
        len(encoded_payload),
        len(encoded_timestamp),
    )
    message_id = _message_id(
        encoded_from, encoded_to, encoded_kind, encoded_text, encoded_payload, encoded_timestamp
    )
    with _LOCK:
        message_path = _path(f"message-{message_id}")
        if not message_path.is_file():
            _atomic_write_ascii(
                message_path,
                "\n".join((
                    f"id={message_id}", f"from_node={encoded_from}", f"to_node={encoded_to}",
                    f"type={encoded_kind}", f"text={encoded_text}",
                    f"payload={encoded_payload}", f"timestamp={encoded_timestamp}",
                )),
            )
        _append_id(_path(f"out-{encoded_from}"), message_id)
        _append_id(
            _path("broadcast" if not encoded_to else f"in-{encoded_to}"), message_id
        )
    return {
        "ack": "node",
        "message_id": message_id,
        "message_node": "content-addressed",
        "edge_node": "content-addressed",
        "persisted": "1",
        "traversable": "1",
        "observed": "1",
    }


def visible_ids(node_id: str) -> list[str]:
    encoded_node = _token(node_id)
    _admit(2, len(encoded_node), 0, 0, 0, 0, 0)
    direct = _read_ids(_path(f"in-{encoded_node}"))
    broadcasts = _read_ids(_path("broadcast"))
    return list(dict.fromkeys(direct + broadcasts))


def has(message_id: str) -> bool:
    if not _ID.fullmatch(message_id):
        return False
    _admit(3, len(message_id), 0, 0, 0, 0, 0)
    return _path(f"message-{message_id}").is_file()
