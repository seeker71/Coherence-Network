#!/usr/bin/env python3
"""Publish the weekly verification snapshot — public-verification-framework R2 CLI.

Wraps the already-implemented verification service:
  compute_weekly_snapshot(week)  — Merkle root + Ed25519 signature
  publish_to_archive_org(...)    — permanent publication

Run this weekly (cron, GitHub Actions schedule, or manually) so the
signed proof-of-reserves / read-count snapshot is published where
any external party can verify it. Prints the snapshot identifier and
archive URL on success.

Usage:
    # Publish last week's snapshot (default)
    python3 scripts/publish_snapshot.py

    # Publish a specific ISO week
    python3 scripts/publish_snapshot.py --week 2026-W16

    # Compute without publishing (diagnostic)
    python3 scripts/publish_snapshot.py --dry-run

Exit codes:
    0  — snapshot computed (and published when not dry-run)
    1  — service unavailable or publication failed

No partner keys required here — the API's existing Ed25519 keypair
in the platform keystore is used by the verification service.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta


def _default_week() -> str:
    """Previous full ISO week, matching verification_service's default."""
    today = date.today()
    prev_week = today - timedelta(days=7)
    return prev_week.strftime("%G-W%V")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--week",
        default=None,
        help="ISO week to publish (e.g. 2026-W16). Defaults to last week.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the snapshot but skip the archive.org publish step.",
    )
    args = parser.parse_args()

    try:
        from app.services import verification_service
    except Exception as exc:  # pragma: no cover — import-time guard
        print(f"Error: verification_service unavailable: {exc}", file=sys.stderr)
        return 1

    week = args.week or _default_week()
    print(f"[COMPUTE] snapshot for week {week}...")
    try:
        snapshot = verification_service.compute_weekly_snapshot(week=week)
    except Exception as exc:
        print(f"[FAIL] compute_weekly_snapshot: {exc}", file=sys.stderr)
        return 1

    merkle_root = snapshot.get("merkle_root")
    signature = snapshot.get("signature")
    print(f"  week:        {snapshot.get('week', week)}")
    print(f"  merkle_root: {merkle_root[:16] if merkle_root else '(none)'}...")
    print(f"  signature:   {signature[:16] if signature else '(none)'}...")
    if "assets_count" in snapshot:
        print(f"  assets:      {snapshot['assets_count']}")

    if args.dry_run:
        print("[DRY-RUN] skipping archive.org publish")
        return 0

    payload_json = json.dumps(snapshot, sort_keys=True, default=str)
    print(f"[PUBLISH] archive.org (payload {len(payload_json)} bytes)...")
    try:
        archive_url = verification_service.publish_to_archive_org(
            week=week, payload_json=payload_json
        )
    except Exception as exc:
        print(f"[FAIL] publish_to_archive_org: {exc}", file=sys.stderr)
        return 1

    if archive_url is None:
        print("[WARN] publish returned None — snapshot stored locally, not archived")
        return 0

    print(f"[PASS] archived at {archive_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
