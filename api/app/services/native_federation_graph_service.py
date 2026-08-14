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
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOCK = threading.RLock()
_ID = re.compile(r"^msg_[0-9a-f]{64}$")
_RECIPE = _REPO_ROOT / "api" / "app" / "form_recipes" / "public_federation_graph_cli.fk"
_ADMITTED = False


def _binary() -> Path:
    from app.services.form_kernel_bridge import kernel_bin_path

    selected = kernel_bin_path()
    if selected.is_file() and os.access(selected, os.X_OK):
        return selected
    raise RuntimeError("native Form federation carrier is unavailable")


def store_path() -> Path:
    raw = os.environ.get("COHERENCE_FORM_GRAPH_STORE")
    path = Path(raw).expanduser() if raw else Path(tempfile.gettempdir()) / "coherence-federation-graph"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _token(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=") or "_"


def _admit() -> None:
    global _ADMITTED
    with _LOCK:
        if _ADMITTED:
            return
        with tempfile.TemporaryDirectory(prefix="coherence-federation-form-") as tmp:
            staged_recipe = Path(tmp) / _RECIPE.name
            staged_recipe.write_bytes(_RECIPE.read_bytes())
            proc = subprocess.run(
                [str(_binary()), str(staged_recipe)], text=True,
                capture_output=True, check=False, timeout=10,
            )
        if proc.returncode != 0 or proc.stdout.strip() != "1111":
            raise RuntimeError("native Form federation admission was not witnessed")
        _ADMITTED = True


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


def _append_id(path: Path, message_id: str) -> None:
    ids = _read_ids(path)
    if message_id not in ids:
        path.write_text("".join(f"{value}\n" for value in [*ids, message_id]), encoding="ascii")


def offer(*, from_node: str, to_node: str | None, kind: str, text: str,
          payload: dict[str, Any], timestamp: str) -> dict[str, str]:
    # Variable-width user bytes remain opaque, path-safe payloads in this membrane;
    # the static Form cell admits the carrier before any durable write occurs.
    _admit()
    encoded_from = _token(from_node)
    encoded_to = "" if to_node is None else _token(to_node)
    encoded_kind = _token(kind)
    encoded_text = _token(text)
    encoded_payload = _token(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    encoded_timestamp = _token(timestamp)
    message_id = _message_id(
        encoded_from, encoded_to, encoded_kind, encoded_text, encoded_payload, encoded_timestamp
    )
    with _LOCK:
        message_path = _path(f"message-{message_id}")
        if not message_path.is_file():
            message_path.write_text(
                "\n".join((
                    f"id={message_id}", f"from_node={encoded_from}", f"to_node={encoded_to}",
                    f"type={encoded_kind}", f"text={encoded_text}",
                    f"payload={encoded_payload}", f"timestamp={encoded_timestamp}",
                )),
                encoding="ascii",
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
    _admit()
    direct = _read_ids(_path(f"in-{_token(node_id)}"))
    broadcasts = _read_ids(_path("broadcast"))
    return list(dict.fromkeys(direct + broadcasts))


def has(message_id: str) -> bool:
    if not _ID.fullmatch(message_id):
        return False
    _admit()
    return _path(f"message-{message_id}").is_file()
