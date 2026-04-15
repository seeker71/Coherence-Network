"""Contributor key management — Ed25519 keypairs for verifiable identity.

Every contributor who wants to participate in the CC economy needs a
public/private keypair:
  - Public key: their verifiable identity, stored on their graph node
  - Private key: stays with them, signs their contributions

Reads: contributor ID is voluntary. Anonymous reads are free but untracked
for CC purposes. Identified reads build the reading history that enables
future CC earning.

Writes: contributor ID + signature required. Every contribution (asset,
article, blueprint, renderer) must be signed to prove authorship.

NFT assets: identified reads encouraged — every tracked view flows CC
back to the creator.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


def generate_keypair() -> dict[str, str]:
    """Generate a new Ed25519 keypair for a contributor.

    Returns {public_key_hex, private_key_hex, fingerprint}.
    The private key should be given to the contributor and never stored
    on the server. The public key is stored on their graph node.
    """
    try:
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

        fingerprint = hashlib.sha256(pub_bytes).hexdigest()[:16]

        return {
            "public_key_hex": pub_bytes.hex(),
            "private_key_hex": priv_bytes.hex(),
            "fingerprint": fingerprint,
            "algorithm": "Ed25519",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except ImportError:
        log.warning("cryptography package not installed — using hash-based identity")
        # Fallback: hash-based identity (less secure but functional)
        import secrets
        secret = secrets.token_hex(32)
        pub = hashlib.sha256(secret.encode()).hexdigest()
        return {
            "public_key_hex": pub,
            "private_key_hex": secret,
            "fingerprint": pub[:16],
            "algorithm": "sha256-fallback",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def register_public_key(contributor_id: str, public_key_hex: str) -> dict[str, Any]:
    """Store a contributor's public key on their graph node.

    The public key becomes part of their verifiable identity.
    """
    try:
        from app.services import graph_service

        node = graph_service.get_node(contributor_id)
        if not node:
            # Create contributor node if it doesn't exist
            node = graph_service.create_node(
                id=contributor_id,
                type="contributor",
                name=contributor_id,
                description="",
                properties={
                    "public_key": public_key_hex,
                    "key_registered_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            # Update existing node with public key
            graph_service.update_node(
                contributor_id,
                properties={
                    **node.get("properties", {}),
                    "public_key": public_key_hex,
                    "key_registered_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        return {
            "contributor_id": contributor_id,
            "public_key": public_key_hex,
            "fingerprint": hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:16],
            "registered": True,
        }
    except Exception as e:
        return {"error": str(e), "registered": False}


def get_public_key(contributor_id: str) -> str | None:
    """Get a contributor's public key from their graph node."""
    try:
        from app.services import graph_service
        node = graph_service.get_node(contributor_id)
        if node:
            return node.get("public_key") or node.get("properties", {}).get("public_key")
    except Exception:
        pass
    return None


def verify_signature(contributor_id: str, message: str, signature_hex: str) -> bool:
    """Verify a message was signed by the claimed contributor.

    Fetches their public key from the graph and checks the signature.
    """
    pub_key_hex = get_public_key(contributor_id)
    if not pub_key_hex:
        return False

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_key_hex))
        pub_key.verify(bytes.fromhex(signature_hex), message.encode("utf-8"))
        return True
    except Exception:
        return False


def sign_contribution(contributor_id: str, private_key_hex: str,
                      asset_id: str, content_hash: str) -> dict[str, str]:
    """Sign a contribution claim: "I (contributor) created this (asset)."

    The contributor signs: contributor_id|asset_id|content_hash|timestamp
    This proves authorship without revealing the private key.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    message = f"{contributor_id}|{asset_id}|{content_hash}|{timestamp}"

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        sig = private_key.sign(message.encode("utf-8"))
        return {
            "message": message,
            "signature": sig.hex(),
            "timestamp": timestamp,
            "valid": True,
        }
    except Exception as e:
        return {"error": str(e), "valid": False}
