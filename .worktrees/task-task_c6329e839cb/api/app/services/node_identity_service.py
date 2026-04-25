"""Node identity derivation and local persistence.

Derives a stable node_id from hostname + MAC address and persists it
to ~/.coherence-network/node_id for reuse across process restarts.
"""

from __future__ import annotations

import hashlib
import platform
import socket
from pathlib import Path
from uuid import getnode

from app.services.capability_probe import CapabilityProbe


IDENTITY_DIR = Path.home() / ".coherence-network"
IDENTITY_FILE = IDENTITY_DIR / "node_id"


def _get_mac_address() -> str:
    """Return the MAC address as a hex string."""
    mac_int = getnode()
    return format(mac_int, "012x")


def _derive_node_id(hostname: str, mac_address: str) -> str:
    """Deterministically derive a 16-char hex node_id."""
    raw = hostname + mac_address
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_or_create_node_id() -> str:
    """Return the persisted node_id, creating it if necessary."""
    if IDENTITY_FILE.exists():
        stored = IDENTITY_FILE.read_text().strip()
        if stored:
            return stored

    hostname = socket.gethostname()
    mac = _get_mac_address()
    node_id = _derive_node_id(hostname, mac)

    IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    IDENTITY_FILE.write_text(node_id)
    return node_id


def get_node_metadata() -> dict:
    """Return metadata about the current node."""
    os_map = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}
    os_type = os_map.get(platform.system(), "linux")
    capabilities = CapabilityProbe.probe()
    return {
        "node_id": get_or_create_node_id(),
        "hostname": socket.gethostname(),
        "os_type": os_type,
        "providers": capabilities.executors,
        "capabilities": capabilities.model_dump(mode="json"),
    }
