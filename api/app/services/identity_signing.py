"""Ed25519 signing helpers for contributor identity.

A contributor's identity is the public key they hold. Possession of the
matching private key is proven by signing — never by trusting a central
registry. These helpers are the small, deterministic kernel that the
cross-instance identity service composes with.

The functions here do not store keys, do not call the DB, do not reach
the network. They sign and verify canonical JSON payloads with ed25519.
That keeps the cryptographic primitive separate from the surrounding
service layer, where storage and trust decisions live.
"""

from __future__ import annotations

import json
from typing import Any


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic JSON encoding for signing/verifying.

    Sorted keys, no whitespace — every encoder produces the same bytes
    for the same payload, so two instances signing the same dict get
    bit-identical signatures.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def generate_keypair() -> tuple[str, str]:
    """Return (private_key_hex, public_key_hex) for a fresh ed25519 keypair.

    The private key NEVER leaves the contributor's machine in any
    real-world flow. This helper exists for tests and for the rare
    case where the CLI bootstraps a new identity for a user.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    private_key = Ed25519PrivateKey.generate()
    priv_bytes = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    pub_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return priv_bytes.hex(), pub_bytes.hex()


def sign_payload(payload: dict[str, Any], private_key_hex: str) -> str:
    """Return the hex-encoded ed25519 signature over canonical_json(payload)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    message = canonical_json(payload).encode("utf-8")
    return priv.sign(message).hex()


def verify_signature(
    payload: dict[str, Any],
    signature_hex: str,
    public_key_hex: str,
) -> bool:
    """Verify a hex-encoded ed25519 signature over canonical_json(payload).

    Returns True only when the signature is valid for the exact pubkey.
    Any failure mode — bad hex, wrong length, signature mismatch —
    returns False; no exception leaks to the caller.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        message = canonical_json(payload).encode("utf-8")
        pub.verify(bytes.fromhex(signature_hex), message)
        return True
    except Exception:
        return False


__all__ = [
    "canonical_json",
    "generate_keypair",
    "sign_payload",
    "verify_signature",
]
