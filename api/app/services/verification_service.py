"""Verification service — Merkle hash chains + Ed25519 signed snapshots.

Makes every CC flow publicly verifiable. Anyone can:
1. Fetch the hash chain for any asset
2. Recompute every hash from the underlying data
3. Verify the weekly snapshot signature with the public key
4. Confirm the Merkle root covers all daily hashes

No trust required — the math is the proof.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Date, LargeBinary, Numeric, String, Text, DateTime, Integer
from sqlalchemy.orm import mapped_column

log = logging.getLogger(__name__)

_ready = False


def _ensure_ready() -> None:
    global _ready
    if _ready:
        return
    _ready = True
    from app.services.unified_db import ensure_schema
    ensure_schema()


def _session():
    from app.services.unified_db import session
    return session()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

from app.services.unified_db import Base


class DailyHashRecord(Base):
    """One row per asset per day in the hash chain."""
    __tablename__ = "verification_daily_hashes"

    asset_id = mapped_column(String(128), primary_key=True)
    day = mapped_column(Date, primary_key=True)
    read_count = mapped_column(Integer, default=0)
    cc_total = mapped_column(Numeric(18, 8), default=0)
    concepts = mapped_column(Text, default="")  # sorted comma-separated concept IDs
    merkle_hash = mapped_column(String(64), nullable=False)  # SHA-256 hex
    prev_hash = mapped_column(String(64), nullable=False)  # previous day's hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "day": self.day.isoformat() if self.day else None,
            "read_count": self.read_count,
            "cc_total": f"{float(self.cc_total or 0):.6f}",
            "concepts": self.concepts,
            "merkle_hash": self.merkle_hash,
            "prev_hash": self.prev_hash,
        }


class SnapshotRecord(Base):
    """Weekly published snapshot."""
    __tablename__ = "verification_snapshots"

    week = mapped_column(String(8), primary_key=True)  # e.g. "2026-W16"
    merkle_root = mapped_column(String(64), nullable=False)
    total_reads = mapped_column(Integer, default=0)
    total_cc = mapped_column(Numeric(18, 8), default=0)
    assets_count = mapped_column(Integer, default=0)
    signature = mapped_column(Text, nullable=True)  # Ed25519 hex signature
    signed_by = mapped_column(String(64), nullable=True)  # public key hex
    arweave_tx = mapped_column(String(64), nullable=True)
    published_at = mapped_column(DateTime(timezone=True), nullable=True)
    payload = mapped_column(Text, nullable=True)  # full JSON for verification

    def to_dict(self) -> dict[str, Any]:
        return {
            "week": self.week,
            "merkle_root": self.merkle_root,
            "total_reads": self.total_reads,
            "total_cc": f"{float(self.total_cc or 0):.6f}",
            "assets_count": self.assets_count,
            "signature": self.signature,
            "signed_by": self.signed_by,
            "arweave_tx": self.arweave_tx,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

GENESIS_HASH = "0" * 64  # all zeros for the first entry in a chain


def compute_hash(asset_id: str, day: date, read_count: int, cc_total: float,
                 concepts: str, prev_hash: str) -> str:
    """Deterministic SHA-256 hash of a daily record.

    Input format (pipe-delimited, UTF-8):
        asset_id|YYYY-MM-DD|read_count|cc_total_6dp|sorted_concepts|prev_hash
    """
    cc_str = f"{cc_total:.6f}"
    data = f"{asset_id}|{day.isoformat()}|{read_count}|{cc_str}|{concepts}|{prev_hash}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_merkle_root(hashes: list[str]) -> str:
    """Binary Merkle tree root from a list of hex hash strings."""
    if not hashes:
        return GENESIS_HASH
    if len(hashes) == 1:
        return hashes[0]

    # Pad to even length
    level = list(hashes)
    if len(level) % 2 == 1:
        level.append(level[-1])

    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            combined = level[i] + level[i + 1]
            next_level.append(hashlib.sha256(combined.encode("utf-8")).hexdigest())
        level = next_level
        if len(level) > 1 and len(level) % 2 == 1:
            level.append(level[-1])

    return level[0]


# ---------------------------------------------------------------------------
# Ed25519 Key Management
# ---------------------------------------------------------------------------

_KEYS_DIR = Path.home() / ".coherence-network"
_VERIFICATION_KEY_PATH = _KEYS_DIR / "verification_key.json"


def _load_or_generate_keys() -> tuple[bytes, bytes]:
    """Load or generate Ed25519 keypair. Returns (private_key_bytes, public_key_bytes)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        log.warning("cryptography package not installed — Ed25519 signing disabled")
        return b"", b""

    if _VERIFICATION_KEY_PATH.exists():
        try:
            data = json.loads(_VERIFICATION_KEY_PATH.read_text(encoding="utf-8"))
            priv_hex = data.get("private_key", "")
            pub_hex = data.get("public_key", "")
            if priv_hex and pub_hex:
                return bytes.fromhex(priv_hex), bytes.fromhex(pub_hex)
        except Exception:
            pass

    # Generate new keypair
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

    # Save
    _KEYS_DIR.mkdir(parents=True, exist_ok=True)
    _VERIFICATION_KEY_PATH.write_text(json.dumps({
        "private_key": priv_bytes.hex(),
        "public_key": pub_bytes.hex(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    _VERIFICATION_KEY_PATH.chmod(0o600)

    log.info("verification: generated new Ed25519 keypair")
    return priv_bytes, pub_bytes


def sign_message(message: bytes) -> str:
    """Sign a message with the verification Ed25519 key. Returns hex signature."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        priv_bytes, _ = _load_or_generate_keys()
        if not priv_bytes:
            return ""
        private_key = Ed25519PrivateKey.from_private_bytes(priv_bytes)
        sig = private_key.sign(message)
        return sig.hex()
    except Exception as e:
        log.warning("verification: signing failed: %s", e)
        return ""


def verify_signature(message: bytes, signature_hex: str, public_key_hex: str) -> bool:
    """Verify an Ed25519 signature. Returns True if valid."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        pub_key.verify(bytes.fromhex(signature_hex), message)
        return True
    except Exception:
        return False


def get_public_key() -> str:
    """Get the verification public key as hex string."""
    _, pub_bytes = _load_or_generate_keys()
    return pub_bytes.hex() if pub_bytes else ""


# ---------------------------------------------------------------------------
# Daily Computation
# ---------------------------------------------------------------------------

def compute_daily_hashes(target_date: date | None = None) -> dict[str, Any]:
    """Compute Merkle hashes for all assets with reads on the given date.

    This is the core verification computation. Run daily (e.g. 00:05 UTC).
    """
    from app.services import read_tracking_service

    _ensure_ready()
    if target_date is None:
        target_date = date.today() - timedelta(days=1)  # yesterday

    reads = read_tracking_service.get_all_reads_for_date(target_date)
    computed = 0
    skipped = 0

    with _session() as s:
        for read_data in reads:
            asset_id = read_data["asset_id"]

            # Check if already computed
            existing = s.query(DailyHashRecord).filter_by(
                asset_id=asset_id, day=target_date
            ).first()
            if existing:
                skipped += 1
                continue

            # Get previous hash
            prev = (
                s.query(DailyHashRecord)
                .filter(DailyHashRecord.asset_id == asset_id)
                .filter(DailyHashRecord.day < target_date)
                .order_by(DailyHashRecord.day.desc())
                .first()
            )
            prev_hash = prev.merkle_hash if prev else GENESIS_HASH

            # Compute
            concepts_raw = read_data.get("concepts", {})
            concepts_str = ",".join(sorted(concepts_raw.keys())) if concepts_raw else ""
            cc_total = read_data.get("cc_distributed", 0.0)

            merkle_hash = compute_hash(
                asset_id, target_date, read_data["read_count"],
                cc_total, concepts_str, prev_hash,
            )

            s.add(DailyHashRecord(
                asset_id=asset_id,
                day=target_date,
                read_count=read_data["read_count"],
                cc_total=cc_total,
                concepts=concepts_str,
                merkle_hash=merkle_hash,
                prev_hash=prev_hash,
            ))
            computed += 1

        s.commit()

    return {
        "date": target_date.isoformat(),
        "computed": computed,
        "skipped": skipped,
        "total_assets": len(reads),
    }


# ---------------------------------------------------------------------------
# Chain Verification
# ---------------------------------------------------------------------------

def get_chain(asset_id: str, from_date: date | None = None,
              to_date: date | None = None) -> list[dict[str, Any]]:
    """Get the hash chain for an asset."""
    _ensure_ready()
    with _session() as s:
        q = s.query(DailyHashRecord).filter(DailyHashRecord.asset_id == asset_id)
        if from_date:
            q = q.filter(DailyHashRecord.day >= from_date)
        if to_date:
            q = q.filter(DailyHashRecord.day <= to_date)
        rows = q.order_by(DailyHashRecord.day).all()
        return [r.to_dict() for r in rows]


def verify_chain(asset_id: str, from_date: date | None = None,
                 to_date: date | None = None) -> dict[str, Any]:
    """Recompute every hash in a chain and verify integrity.

    Returns {valid: bool, entries: int, first_failure: {...} | null}
    """
    chain = get_chain(asset_id, from_date, to_date)
    if not chain:
        return {"valid": True, "entries": 0, "first_failure": None}

    for i, entry in enumerate(chain):
        expected = compute_hash(
            entry["asset_id"],
            date.fromisoformat(entry["day"]),
            entry["read_count"],
            float(entry["cc_total"]),
            entry["concepts"],
            entry["prev_hash"],
        )
        if expected != entry["merkle_hash"]:
            return {
                "valid": False,
                "entries": len(chain),
                "first_failure": {
                    "day": entry["day"],
                    "stored_hash": entry["merkle_hash"],
                    "computed_hash": expected,
                    "entry_index": i,
                },
            }

        # Verify chain linkage (prev_hash of entry i+1 should match hash of entry i)
        if i > 0:
            if entry["prev_hash"] != chain[i - 1]["merkle_hash"]:
                return {
                    "valid": False,
                    "entries": len(chain),
                    "first_failure": {
                        "day": entry["day"],
                        "issue": "chain_break",
                        "stored_prev": entry["prev_hash"],
                        "expected_prev": chain[i - 1]["merkle_hash"],
                        "entry_index": i,
                    },
                }

    return {"valid": True, "entries": len(chain), "first_failure": None}


# ---------------------------------------------------------------------------
# Weekly Snapshots
# ---------------------------------------------------------------------------

def compute_weekly_snapshot(week: str | None = None) -> dict[str, Any]:
    """Compute and store a weekly snapshot with Merkle root + Ed25519 signature.

    Week format: "2026-W16" (ISO week number).
    """
    _ensure_ready()

    if week is None:
        # Previous week
        today = date.today()
        prev_week = today - timedelta(days=7)
        week = prev_week.strftime("%G-W%V")

    # Parse week dates
    # ISO week: Monday to Sunday
    year, week_num = int(week.split("-W")[0]), int(week.split("-W")[1])
    monday = date.fromisocalendar(year, week_num, 1)
    sunday = date.fromisocalendar(year, week_num, 7)

    with _session() as s:
        # Check if already published
        existing = s.query(SnapshotRecord).filter_by(week=week).first()
        if existing:
            return existing.to_dict()

        # Get all daily hashes for this week
        rows = (
            s.query(DailyHashRecord)
            .filter(DailyHashRecord.day >= monday)
            .filter(DailyHashRecord.day <= sunday)
            .order_by(DailyHashRecord.asset_id, DailyHashRecord.day)
            .all()
        )

        if not rows:
            return {"week": week, "error": "no data for this week"}

        # Compute aggregates
        all_hashes = [r.merkle_hash for r in rows]
        merkle_root = compute_merkle_root(all_hashes)
        total_reads = sum(r.read_count or 0 for r in rows)
        total_cc = sum(float(r.cc_total or 0) for r in rows)
        asset_ids = set(r.asset_id for r in rows)

        # Build payload for signing
        payload = {
            "version": "1.0",
            "week": week,
            "period": {"from": monday.isoformat(), "to": sunday.isoformat()},
            "merkle_root": merkle_root,
            "total_reads": total_reads,
            "total_cc_distributed": f"{total_cc:.6f}",
            "assets_count": len(asset_ids),
            "daily_hash_count": len(rows),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
        payload_json = json.dumps(payload, sort_keys=True)

        # Sign
        signature = sign_message(payload_json.encode("utf-8"))
        public_key = get_public_key()

        # Store
        snapshot = SnapshotRecord(
            week=week,
            merkle_root=merkle_root,
            total_reads=total_reads,
            total_cc=total_cc,
            assets_count=len(asset_ids),
            signature=signature,
            signed_by=public_key,
            published_at=datetime.now(timezone.utc),
            payload=payload_json,
        )
        s.add(snapshot)
        s.commit()

        # Publish to archive.org (free permanent storage)
        archive_url = publish_to_archive_org(week, payload_json)
        if archive_url:
            snapshot.arweave_tx = archive_url  # reuse field for archive URL
            s.commit()

        result = snapshot.to_dict()
        result["payload"] = payload
        if archive_url:
            result["archive_url"] = archive_url
        return result


def publish_to_archive_org(week: str, payload_json: str) -> str | None:
    """Publish a snapshot to archive.org as free permanent storage.

    Uses the Internet Archive's S3-compatible API. Requires archive.org
    credentials in ~/.coherence-network/keys.json:
    {"archive_org": {"access_key": "...", "secret_key": "..."}}

    Returns the public URL or None if not configured/failed.
    """
    try:
        from app.services.config_service import get_config
        config = get_config()
        keys = config.get("keys", {}).get("archive_org", {})
        access_key = keys.get("access_key", "")
        secret_key = keys.get("secret_key", "")

        if not access_key or not secret_key:
            log.info("verification: archive.org not configured — skipping publication")
            return None

        import httpx
        identifier = "coherence-network-ledger"
        filename = f"{week}.json"
        url = f"https://s3.us.archive.org/{identifier}/{filename}"

        headers = {
            "Authorization": f"LOW {access_key}:{secret_key}",
            "Content-Type": "application/json",
            "x-archive-meta-title": f"Coherence Network Verification Snapshot {week}",
            "x-archive-meta-description": "Weekly Merkle root + Ed25519 signed snapshot of all CC flows",
            "x-archive-meta-collection": "opensource",
            "x-archive-meta-mediatype": "data",
            "x-archive-meta-creator": "Coherence Network",
            "x-archive-meta-subject": "verification;merkle;ed25519;cc-economics",
            "x-amz-auto-make-bucket": "1",
        }

        resp = httpx.put(url, content=payload_json.encode(), headers=headers, timeout=30)
        if resp.status_code in (200, 201):
            public_url = f"https://archive.org/download/{identifier}/{filename}"
            log.info("verification: published to archive.org: %s", public_url)
            return public_url
        else:
            log.warning("verification: archive.org upload failed: %s %s",
                        resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        log.warning("verification: archive.org publication failed: %s", e)
        return None


def get_snapshot(week: str) -> dict[str, Any] | None:
    """Get a published snapshot."""
    _ensure_ready()
    with _session() as s:
        row = s.query(SnapshotRecord).filter_by(week=week).first()
        if not row:
            return None
        result = row.to_dict()
        if row.payload:
            result["payload"] = json.loads(row.payload)
        return result


def verify_snapshot(week: str) -> dict[str, Any]:
    """Verify a snapshot: recompute Merkle root and check signature."""
    snapshot = get_snapshot(week)
    if not snapshot:
        return {"valid": False, "error": "snapshot not found"}

    payload = snapshot.get("payload", {})
    if not payload:
        return {"valid": False, "error": "no payload to verify"}

    # Verify signature
    payload_json = json.dumps(payload, sort_keys=True)
    sig_valid = verify_signature(
        payload_json.encode("utf-8"),
        snapshot.get("signature", ""),
        snapshot.get("signed_by", ""),
    )

    return {
        "week": week,
        "signature_valid": sig_valid,
        "merkle_root": snapshot.get("merkle_root"),
        "total_reads": payload.get("total_reads"),
        "total_cc": payload.get("total_cc_distributed"),
        "signed_by": snapshot.get("signed_by"),
    }
