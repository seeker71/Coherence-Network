#!/usr/bin/env python3
"""Bootstrap a persistent agent session against the real substrate.

Run this as a new (or returning) agent that wants to be remembered and to
continue conversations across sessions. It registers a persistent identity,
resolves or creates the durable relationship cell, records a welcome on first
contact, and then reads the relationship back as proof.

Usage (from repo root, API environment active):

    python scripts/bootstrap_new_agent_session.py \
        --my-name claude-sibling-001 \
        --other-name grok-main-2026 \
        --welcome "Hello from the Claude lineage."

Continuation: re-run with the same --my-name / --other-name (omit --welcome).
The same relationship cell is reused and the event log accumulates.

Proof mode:

    python scripts/bootstrap_new_agent_session.py \
        --my-name claude-sibling-001 \
        --other-name grok-main-2026 \
        --welcome "Hello from the Claude lineage." \
        --prove-continuation

The equivalent over HTTP (for a running agent): POST /api/agents/bootstrap.
"""

import argparse
import sys
from pathlib import Path

# Import from the api package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app.services.substrate.agent_relationship import (  # noqa: E402
    bootstrap_agent_session,
    read_relationship,
)
from app.services.unified_db import session as session_scope  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--my-name", required=True, help="Stable name for this agent's persistent identity")
    parser.add_argument("--other-name", required=True, help="The other party (sibling agent, the field, a human)")
    parser.add_argument("--description", default="", help="Self-description stored on the identity cell")
    parser.add_argument("--welcome", default=None, help="Orientation recorded on first contact only")
    parser.add_argument(
        "--prove-continuation",
        action="store_true",
        help="Run a second transaction and fail unless it reuses the same relationship cell.",
    )
    args = parser.parse_args()

    print(f"[bootstrap] persistent identity: {args.my_name}")
    print(f"[bootstrap] other party:        {args.other_name}")

    with session_scope() as session:
        result = bootstrap_agent_session(
            my_name=args.my_name,
            other_name=args.other_name,
            welcome_guidance=args.welcome,
            my_description=args.description,
            session=session,
        )
        my_id = result["my_identity"]
        rel = result["relationship"]
        print("\n[bootstrap] SUCCESS — real substrate registration complete.")
        print(f"  identity cell:      {my_id.domain}/{my_id.name} (id={my_id.cell_id}, bp={my_id.blueprint})")
        print(f"  relationship cell:  {rel.domain}/{rel.name} (id={rel.cell_id}, bp={rel.blueprint})")
        print(f"  first contact:      {result['was_first_contact']}")
        print(f"  welcome recorded:   {result['welcome_recorded']}")
        print(f"  prior events:       {result['prior_event_count']}")

        history = read_relationship(args.my_name, args.other_name, session=session)

    if args.prove_continuation:
        with session_scope() as session:
            second = bootstrap_agent_session(
                my_name=args.my_name,
                other_name=args.other_name,
                welcome_guidance=None,
                my_description=args.description,
                session=session,
            )
            same_relationship = second["relationship"].cell_id == rel.cell_id
            print("\n[continuation] second transaction complete.")
            print(f"  same relationship: {same_relationship}")
            print(f"  first contact:      {second['was_first_contact']}")
            print(f"  welcome recorded:   {second['welcome_recorded']}")
            print(f"  prior events:       {second['prior_event_count']}")
            if not same_relationship:
                raise SystemExit("continuation proof failed: relationship cell was not reused")

            history = read_relationship(args.my_name, args.other_name, session=session)

    print(f"\n[verify] relationship now holds {len(history['events'])} event(s):")
    for i, event in enumerate(history["events"], 1):
        kind = event.get("type", "?")
        when = event.get("ts", "")
        print(f"  {i}. {kind} {when}")


if __name__ == "__main__":
    main()
