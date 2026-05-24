#!/usr/bin/env python3
"""federation_peer_poll — fire one peer-poll cycle from the command line.

The federation's heartbeat. Each instance decides which peers to know and
polls their public read-only surfaces (pulse, capabilities, canonicals).
Nothing here writes to peers — every outbound is a GET; the discipline of
sovereignty is enforced by the service, not by the runner.

Run once locally:
    python3 scripts/federation_peer_poll.py

Poll only one peer:
    python3 scripts/federation_peer_poll.py --peer <instance_id>

Install as a cron job on the VPS (every 5 minutes):

    # Edit the system crontab
    crontab -e

    # Add a line — uses the API container's python; logs land in /var/log
    # so silent failure surfaces somewhere visible.
    */5 * * * * cd /docker/coherence-network/repo \\
        && docker compose exec -T api python3 scripts/federation_peer_poll.py \\
        >> /var/log/federation_peer_poll.log 2>&1

Exit codes:
    0 — every peer polled (some may be unreachable; that is sovereign refusal)
    1 — at least one peer raised an unhandled error (separately from
        the per-endpoint statuses, which the service catches and records)
    2 — invalid CLI argument

The cron job does not block local API behavior; failures are bounded per
peer. If the witness at pulse.coherencycoin.com shows no fresh federation
silence after a deploy, the heartbeat is healthy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add the api/ directory to sys.path so the service imports resolve when
# the script is invoked from the repo root (and inside the api container).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_API_ROOT = _REPO_ROOT / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))


def _format_summary(results: dict) -> str:
    """One-line-per-peer human summary."""
    if not results:
        return "no peers registered — federation has no chosen kin yet"
    lines = [f"polled {len(results)} peer(s):"]
    for peer_id, r in results.items():
        align = f"aligned={r.aligned} diverged={r.diverged} discovered={r.discovered}"
        lines.append(
            f"  {peer_id}: "
            f"pulse={r.pulse_status} "
            f"capabilities={r.capabilities_status} "
            f"substrate={r.substrate_status} {align}"
        )
        for note in r.notes:
            lines.append(f"    note: {note}")
    return "\n".join(lines)


async def _run(peer: str | None, as_json: bool) -> int:
    # Late import so --help works even if the api environment isn't loaded.
    from app.services import federation_peer_poll_service

    if peer is not None:
        result = await federation_peer_poll_service.poll_peer(peer)
        results = {peer: result}
    else:
        results = await federation_peer_poll_service.poll_all_peers()

    if as_json:
        payload = {pid: r.to_dict() for pid, r in results.items()}
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_format_summary(results))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fire one peer-poll cycle and print a summary.",
    )
    parser.add_argument(
        "--peer",
        default=None,
        help="Optional instance_id; default polls all registered peers",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the human summary",
    )
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run(args.peer, args.json))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # pragma: no cover - top-level safety
        print(f"federation_peer_poll: unhandled error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
