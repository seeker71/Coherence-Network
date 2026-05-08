#!/usr/bin/env python3
"""Honour a contributor's opt-out across the network's body of evidence.

The Coherence Network's posture is public-by-default — contributions,
attribution, view events, postgres dumps live in the open as the
substrate for sovereign-transparent attribution. Most contributors
arrive knowing this and want their participation visible.

This script is the lever for the case where a contributor genuinely
needs their data redacted from the body of evidence — a privacy
concern that emerged after joining, a dispute, a right-to-be-
forgotten request, anything we couldn't anticipate at arrival.

What it touches, in order:

  1. **Hot tier (asset_view_events)** — UPDATE rows tied to the
     contributor: contributor_id → NULL, session_fingerprint → NULL,
     source_page → NULL, referrer_contributor_id → NULL. The events
     stay (the network preserves the *shape* of attention) but the
     *who* is removed.

  2. **Contribution ledger (contribution_ledger)** — UPDATE rows
     tied to the contributor: contributor_id → "contributor:redacted".
     The ledger keeps WHAT happened; WHO is anonymised. (NULL isn't
     valid for the ledger's contributor_id column; the sentinel
     preserves shape without pretending no one was there.)

  3. **Cold tier (per-day archives)** — for each archived day that
     contains the contributor, download the gzipped JSONL, apply the
     same anonymisation transform to each event, re-gzip, recompute
     SHA-256, re-upload (same tag + filename so the deterministic URL
     stays valid), and update the tombstone in lockstep.

  4. **Audit log** — append a JSONL record to
     /var/lib/coherence-network/opt-outs.log capturing what was done,
     when, and what content the redacted contributor data had at the
     moment of redaction (kept for compliance review only — never
     shipped to the public archive).

Honest properties of this opt-out:

  · **Past third-party mirrors** can't be unwound. Anyone who
    downloaded a cold-tier archive before the rewrite has the old
    SHA on their disk. The opt-out is forward-looking from here.
  · **Past postgres dumps** in the public archive aren't rewritten
    by this script — those are monolithic snapshots and rewriting
    them retroactively would invalidate every prior verification.
    Going forward, every new nightly dump reflects the redacted DB.
  · **Sentinel contributor:redacted** preserves the ledger's
    aggregate-counter behaviour (the network can still see "N
    contributions came from redacted cells") without exposing who.

Usage:

    # Dry-run — see what would change without touching anything
    python3 scripts/opt_out_contributor.py \\
        --contributor-id contributor:abc123 --dry-run

    # Apply — perform the redaction across hot + cold + ledger + audit
    python3 scripts/opt_out_contributor.py \\
        --contributor-id contributor:abc123 --apply

    # On VPS, inside the api container (which has gh + auth):
    docker compose exec -T api python3 /tmp/opt_out_contributor.py \\
        --contributor-id contributor:abc123 --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_ROOT = os.path.join(REPO_ROOT, "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from sqlalchemy import or_  # noqa: E402

log = logging.getLogger("opt_out_contributor")
logging.basicConfig(level=logging.INFO, format="%(message)s")

REDACTED_SENTINEL = "contributor:redacted"
AUDIT_LOG_PATH = Path(
    os.environ.get(
        "COHERENCE_OPTOUT_AUDIT_LOG",
        "/var/lib/coherence-network/opt-outs.log",
    )
)


def _human(n: int) -> str:
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}k"
    return f"{n / 1_000_000:.2f}M"


# ---------------------------------------------------------------------------
# Hot tier — asset_view_events
# ---------------------------------------------------------------------------

def count_hot_events(contributor_id: str) -> dict:
    from app.services.unified_db import session, ensure_schema
    from app.services.read_tracking_service import AssetViewEvent
    ensure_schema()
    with session() as s:
        as_contributor = (
            s.query(AssetViewEvent)
            .filter(AssetViewEvent.contributor_id == contributor_id)
            .count()
        )
        as_referrer = (
            s.query(AssetViewEvent)
            .filter(AssetViewEvent.referrer_contributor_id == contributor_id)
            .count()
        )
    return {"as_contributor": as_contributor, "as_referrer": as_referrer}


def anonymize_hot_events(contributor_id: str, *, apply: bool) -> int:
    from app.services.unified_db import session, ensure_schema
    from app.services.read_tracking_service import AssetViewEvent
    ensure_schema()
    if not apply:
        return 0
    with session() as s:
        n_c = (
            s.query(AssetViewEvent)
            .filter(AssetViewEvent.contributor_id == contributor_id)
            .update(
                {
                    AssetViewEvent.contributor_id: None,
                    AssetViewEvent.session_fingerprint: None,
                    AssetViewEvent.source_page: None,
                },
                synchronize_session=False,
            )
        )
        n_r = (
            s.query(AssetViewEvent)
            .filter(AssetViewEvent.referrer_contributor_id == contributor_id)
            .update(
                {AssetViewEvent.referrer_contributor_id: None},
                synchronize_session=False,
            )
        )
        s.commit()
    return (n_c or 0) + (n_r or 0)


# ---------------------------------------------------------------------------
# Ledger — contribution_ledger (sentinel-redact, NULL not allowed)
# ---------------------------------------------------------------------------

def count_ledger_rows(contributor_id: str) -> int:
    from app.services.unified_db import session, ensure_schema
    from app.services.contribution_ledger_service import ContributionLedgerRecord
    ensure_schema()
    with session() as s:
        return (
            s.query(ContributionLedgerRecord)
            .filter(ContributionLedgerRecord.contributor_id == contributor_id)
            .count()
        )


def redact_ledger_rows(contributor_id: str, *, apply: bool) -> int:
    from app.services.unified_db import session, ensure_schema
    from app.services.contribution_ledger_service import ContributionLedgerRecord
    ensure_schema()
    if not apply:
        return 0
    with session() as s:
        n = (
            s.query(ContributionLedgerRecord)
            .filter(ContributionLedgerRecord.contributor_id == contributor_id)
            .update(
                {ContributionLedgerRecord.contributor_id: REDACTED_SENTINEL},
                synchronize_session=False,
            )
        )
        s.commit()
    return n or 0


# ---------------------------------------------------------------------------
# Cold tier — rewrite per-day archives
# ---------------------------------------------------------------------------

def _make_event_transform(contributor_id: str):
    """Return a closure that anonymises events tied to the contributor.
    Returns the redacted event (not None) so the row count stays
    stable — the network preserves that *something* happened that
    day, just not who."""
    def transform(ev: dict) -> dict:
        touched = False
        if ev.get("contributor_id") == contributor_id:
            ev = {**ev,
                  "contributor_id": None,
                  "session_fingerprint": None,
                  "source_page": None}
            touched = True
        if ev.get("referrer_contributor_id") == contributor_id:
            ev = {**ev, "referrer_contributor_id": None}
            touched = True
        return ev if not touched else ev  # event is rewritten in place above
    return transform


def find_archived_days_with_contributor(contributor_id: str) -> list:
    """Walk every tombstone, fetch its archive, return the days that
    contain the contributor. Cached locally so re-walks are cheap."""
    from app.services import view_events_archive_service as vea
    days = vea.list_archived_days()
    affected = []
    for d in days:
        result = vea.retrieve_day(d)
        if not result.get("fetched"):
            log.warning("  could not inspect archive for %s: %s", d, result.get("error"))
            continue
        events = result.get("events", [])
        hit = any(
            ev.get("contributor_id") == contributor_id
            or ev.get("referrer_contributor_id") == contributor_id
            for ev in events
        )
        if hit:
            affected.append(d)
    return affected


def rewrite_cold_tier(contributor_id: str, *, apply: bool, repo: str) -> list:
    from app.services import view_events_archive_service as vea
    affected = find_archived_days_with_contributor(contributor_id)
    log.info("  cold-tier days touched: %s", len(affected))
    if not apply:
        for d in affected:
            log.info("    (dry-run) would rewrite %s", d)
        return [{"day": str(d), "rewritten": False, "reason": "dry-run"} for d in affected]

    transform = _make_event_transform(contributor_id)
    summaries = []
    for d in affected:
        summary = vea.rewrite_archived_day(
            d,
            transform=transform,
            repo=repo,
            notes=(
                f"Opt-out redaction at {datetime.now(timezone.utc).isoformat()} — "
                f"events tied to a contributor were anonymised. The day's row "
                f"count is preserved; identifying fields are NULL on those rows."
            ),
        )
        log.info("    rewrote %s: %s", d, summary)
        summaries.append(summary)
    return summaries


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def record_audit(contributor_id: str, summary: dict) -> None:
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "at": datetime.now(timezone.utc).isoformat(),
            "contributor_id": contributor_id,
            "summary": summary,
        }
        with AUDIT_LOG_PATH.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        log.info("  audit logged → %s", AUDIT_LOG_PATH)
    except OSError as e:
        log.warning("  audit log write failed: %s", e)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(contributor_id: str, *, apply: bool, repo: str) -> dict:
    log.info("=== opt-out · contributor=%s · mode=%s ===",
             contributor_id, "APPLY" if apply else "DRY-RUN")

    log.info("\n[1/3] hot tier · asset_view_events")
    counts = count_hot_events(contributor_id)
    log.info("  rows where contributor_id matches:        %s", counts["as_contributor"])
    log.info("  rows where referrer_contributor_id match: %s", counts["as_referrer"])
    hot_anonymized = anonymize_hot_events(contributor_id, apply=apply)
    if apply:
        log.info("  ✓ %s rows anonymised in hot tier", hot_anonymized)

    log.info("\n[2/3] contribution_ledger")
    ledger_count = count_ledger_rows(contributor_id)
    log.info("  ledger rows tied to contributor: %s", ledger_count)
    ledger_redacted = redact_ledger_rows(contributor_id, apply=apply)
    if apply:
        log.info("  ✓ %s ledger rows redacted (contributor_id → %s)",
                 ledger_redacted, REDACTED_SENTINEL)

    log.info("\n[3/3] cold-tier archives")
    cold_summaries = rewrite_cold_tier(contributor_id, apply=apply, repo=repo)

    summary = {
        "contributor_id": contributor_id,
        "applied": apply,
        "hot_tier": counts,
        "hot_tier_anonymized": hot_anonymized,
        "ledger_count": ledger_count,
        "ledger_redacted": ledger_redacted,
        "cold_tier": cold_summaries,
    }

    if apply:
        record_audit(contributor_id, summary)

    log.info("\n=== summary ===")
    log.info("  hot-tier rows touched:    %s",
             counts["as_contributor"] + counts["as_referrer"])
    log.info("  ledger rows touched:      %s", ledger_count)
    log.info("  cold-tier days affected:  %s", len(cold_summaries))
    if not apply:
        log.info("\n(dry-run) re-run with --apply to commit. body waits.")
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--contributor-id", required=True,
                   help="The contributor id to opt out (e.g. contributor:abc123).")
    p.add_argument("--apply", action="store_true",
                   help="Commit redactions. Without this, run is read-only.")
    p.add_argument("--dry-run", action="store_true",
                   help="Report only — explicit alias for the default behaviour.")
    p.add_argument("--repo", default=os.environ.get(
        "COHERENCE_ARCHIVE_REPO", "seeker71/Coherence-Network"),
                   help="GitHub repo where cold-tier archives live.")
    args = p.parse_args(argv)

    apply = args.apply and not args.dry_run

    if apply and not args.contributor_id.startswith("contributor:"):
        log.error("Refusing to apply: contributor-id must start with 'contributor:'")
        return 2

    run(args.contributor_id, apply=apply, repo=args.repo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
