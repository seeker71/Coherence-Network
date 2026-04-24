#!/usr/bin/env python3
"""External proof demo — exercises the Coherence Network public API from outside the repo.

Runs the full idea lifecycle against a live deployment using only
`COHERENCE_API_URL` and `COHERENCE_API_KEY` env vars. No internal
imports. Safe to copy into any other repo and run.

Usage:
    # Happy path against a live API
    export COHERENCE_API_URL=https://api.coherencycoin.com
    export COHERENCE_API_KEY=<real-key>
    python3 scripts/external_proof_demo.py

    # Dry run — prints intended API calls, makes no HTTP requests
    python3 scripts/external_proof_demo.py --dry-run

    # Override API URL at CLI (useful for local testing)
    python3 scripts/external_proof_demo.py --api-url http://localhost:8000

Exit codes:
    0  — all checkpoints passed
    1  — any API call failed or env vars missing

Dependencies: requests (or any HTTP client). Stdlib-only if possible
by keeping requests usage minimal.

See specs/external-repo-milestone.md (R1–R7) for the full contract.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from typing import Any, Dict, Optional


def _idea_create_payload() -> Dict[str, Any]:
    return {
        "name": "External Proof Test Idea [auto-cleanup]",
        "description": "Created by external_proof_demo.py - will be archived.",
        "potential_value": 1.0,
        "estimated_cost": 0.1,
        "confidence": 0.8,
        "workspace_id": "coherence-network",
        "tags": ["external-proof", "auto-cleanup"],
    }


def _import_requests():
    try:
        import requests  # type: ignore[import-not-found]

        return requests
    except ImportError:
        print(
            "Error: requests not installed. Run: pip install requests",
            file=sys.stderr,
        )
        sys.exit(1)


class ProofRunner:
    """Walks the idea lifecycle via public API. In dry-run mode it
    prints intended calls without executing them."""

    def __init__(self, api_url: str, api_key: str, dry_run: bool = False):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.dry_run = dry_run
        self.requests = None if dry_run else _import_requests()
        self.endpoints_exercised: list[str] = []
        self.idea_id: Optional[str] = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _log(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> None:
        summary = f"{method} {self.api_url}{path}"
        if body:
            compact = json.dumps(body, separators=(",", ":"))
            if len(compact) > 80:
                compact = compact[:77] + "..."
            summary += f"  {compact}"
        prefix = "[DRY-RUN]" if self.dry_run else "[CALL]   "
        print(f"{prefix} {summary}")

    def _call(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.endpoints_exercised.append(f"{method} {path}")
        self._log(method, path, body)
        if self.dry_run:
            return {"_dry_run": True}
        url = f"{self.api_url}{path}"
        response = self.requests.request(
            method, url, headers=self._headers(), json=body, timeout=30
        )
        if not response.ok:
            print(
                f"[FAIL] HTTP {response.status_code} — {response.text[:500]}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def pass_(self, message: str) -> None:
        print(f"[PASS] {message}")

    # ---- Lifecycle steps ----

    def create_idea(self) -> None:
        result = self._call(
            "POST",
            "/api/ideas",
            _idea_create_payload(),
        )
        if not self.dry_run:
            if "id" not in result:
                print(
                    f"[FAIL] POST /api/ideas response missing 'id': {result}",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            self.idea_id = result["id"]
        else:
            self.idea_id = "dry-run-idea-id"
        self.pass_(f"idea created (id={self.idea_id})")

    def advance_stage(self) -> None:
        self._call(
            "POST",
            f"/api/ideas/{self.idea_id}/advance",
        )
        self.pass_("stage advanced")

    def record_contribution(self) -> None:
        result = self._call(
            "POST",
            "/api/contributions",
            {
                "idea_id": self.idea_id,
                "contributor_id": "external-proof-bot",
                "type": "code",
                "description": "Proof contribution",
                "cc_amount": 1,
            },
        )
        if not self.dry_run and "id" not in result:
            print(
                f"[FAIL] POST /api/contributions response missing 'id': {result}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        self.pass_("contribution recorded")

    def check_coherence_score(self) -> None:
        result = self._call("GET", f"/api/coherence/{self.idea_id}")
        if not self.dry_run:
            score = result.get("score")
            if not isinstance(score, (int, float)) or not (0.0 <= score <= 1.0):
                print(
                    f"[FAIL] coherence score not a float in [0,1]: {result}",
                    file=sys.stderr,
                )
                raise SystemExit(1)
        self.pass_("coherence score read")

    def archive_idea(self) -> None:
        if self.idea_id is None:
            return
        # "archived" is an IdeaLifecycle value, not an IdeaStage — the
        # stage endpoint would reject it. Lifecycle lives on the idea
        # object itself and is mutated via PATCH.
        self._call(
            "PATCH",
            f"/api/ideas/{self.idea_id}",
            {"lifecycle": "archived"},
        )
        self.pass_("idea archived")

    def run(self) -> None:
        try:
            self.create_idea()
            self.advance_stage()
            self.record_contribution()
            self.check_coherence_score()
        finally:
            try:
                self.archive_idea()
            except SystemExit:
                # Archival failure shouldn't mask the primary failure
                print("[WARN] archive step failed — test idea may remain", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default=os.environ.get("COHERENCE_API_URL", "https://api.coherencycoin.com"),
        help="API base URL (default: COHERENCE_API_URL env or coherencycoin.com)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended API calls without executing them",
    )
    args = parser.parse_args()

    api_key = os.environ.get("COHERENCE_API_KEY", "")
    if not args.dry_run and not api_key:
        print(
            "Error: COHERENCE_API_KEY environment variable not set",
            file=sys.stderr,
        )
        return 1

    runner = ProofRunner(args.api_url, api_key, dry_run=args.dry_run)
    runner.run()

    if args.dry_run:
        print(f"\n[DRY-RUN] {len(runner.endpoints_exercised)} endpoints would be exercised:")
        for e in runner.endpoints_exercised:
            print(f"  {e}")
    else:
        print(f"\nAll checkpoints passed. {len(runner.endpoints_exercised)} endpoints exercised.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
