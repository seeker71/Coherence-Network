#!/usr/bin/env python3
"""Verify that DB content hashes match their source files.

Exits 0 if all hashes match, 1 if any mismatch or missing.

Usage:
    python3 scripts/verify_hashes.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.services import unified_db  # noqa: E402
from app.services import spec_registry_service  # noqa: E402
from app.services import commit_evidence_service  # noqa: E402


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def verify_specs() -> tuple[int, int, int, int]:
    """Verify spec content hashes. Returns (matched, mismatched, missing_file, missing_hash)."""
    matched = mismatched = missing_file = missing_hash = 0

    specs = spec_registry_service.list_specs(limit=5000)
    for spec in specs:
        content_path = getattr(spec, "content_path", None)
        content_hash = getattr(spec, "content_hash", None)

        if not content_hash:
            missing_hash += 1
            continue

        if not content_path:
            missing_hash += 1
            continue

        file_path = ROOT / content_path
        if not file_path.exists():
            missing_file += 1
            print(f"  MISSING FILE: {content_path} (spec {spec.spec_id})")
            continue

        actual_hash = sha256_of(file_path.read_bytes())
        if actual_hash == content_hash:
            matched += 1
        else:
            mismatched += 1
            print(f"  MISMATCH: {content_path} (spec {spec.spec_id})")
            print(f"    DB:   {content_hash}")
            print(f"    File: {actual_hash}")

    return matched, mismatched, missing_file, missing_hash


def verify_evidence() -> tuple[int, int, int, int]:
    """Verify evidence content hashes. Returns (matched, mismatched, missing_file, missing_hash)."""
    matched = mismatched = missing_file = missing_hash = 0

    records = commit_evidence_service.list_records(limit=5000)
    for record in records:
        source_file = record.get("_evidence_file", "")
        if not source_file:
            continue

        # Get the content_hash from the DB record directly
        with unified_db.session() as s:
            from app.services.commit_evidence_service import CommitEvidenceRecord
            row = (
                s.query(CommitEvidenceRecord)
                .filter(CommitEvidenceRecord.source_file == source_file)
                .first()
            )
            if row is None:
                continue
            content_hash = getattr(row, "content_hash", None)

        if not content_hash:
            missing_hash += 1
            continue

        file_path = ROOT / source_file
        if not file_path.exists():
            missing_file += 1
            print(f"  MISSING FILE: {source_file}")
            continue

        actual_hash = sha256_of(file_path.read_bytes())
        if actual_hash == content_hash:
            matched += 1
        else:
            mismatched += 1
            print(f"  MISMATCH: {source_file}")
            print(f"    DB:   {content_hash}")
            print(f"    File: {actual_hash}")

    return matched, mismatched, missing_file, missing_hash


def main() -> int:
    print(f"DB: {unified_db.database_url()}")

    print("\nVerifying specs...")
    s_matched, s_mismatch, s_missing_file, s_missing_hash = verify_specs()
    print(f"  {s_matched} matched, {s_mismatch} mismatched, {s_missing_file} missing file, {s_missing_hash} no hash")

    print("\nVerifying evidence...")
    e_matched, e_mismatch, e_missing_file, e_missing_hash = verify_evidence()
    print(f"  {e_matched} matched, {e_mismatch} mismatched, {e_missing_file} missing file, {e_missing_hash} no hash")

    total_mismatched = s_mismatch + e_mismatch
    total_missing = s_missing_file + e_missing_file
    total_matched = s_matched + e_matched

    print(f"\nTotal: {total_matched} matched, {total_mismatched} mismatched, {total_missing} missing files")

    if total_mismatched > 0 or total_missing > 0:
        print("\nFAILED — run `python3 scripts/seed_db.py` to fix")
        return 1

    print("\nOK — all hashes verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
