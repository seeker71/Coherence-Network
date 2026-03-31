#!/usr/bin/env python3
"""Capture local tool guard baseline after warming the idea registry.

Run once before local tool validation. Warm-up (GET /api/ideas) absorbs one-time
ensure logic; then we capture counts and ID-level snapshots for invariant diffing.

Usage:
  python api/scripts/capture_local_tool_baseline.py [--base-url http://127.0.0.1:8000] [--output api/logs/local_tool_guard_baseline.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OUTPUT = "api/logs/local_tool_guard_baseline.json"


def _warm_ideas(client: httpx.Client, base_url: str) -> None:
    """Warm idea registry so ensure logic runs before baseline capture."""
    url = f"{base_url.rstrip('/')}/api/ideas"
    try:
        client.get(url, params={"limit": 500, "include_internal": "true"}, timeout=30)
    except Exception:
        pass


def _fetch_ideas(client: httpx.Client, base_url: str, read_only_guard: bool = False) -> list[dict]:
    """Return all ideas (paginated) for ID snapshot. read_only_guard=True avoids persisting ensure logic."""
    url = f"{base_url.rstrip('/')}/api/ideas"
    out: list[dict] = []
    offset = 0
    limit = 500
    params: dict = {"limit": limit, "include_internal": "true"}
    if read_only_guard:
        params["read_only_guard"] = "true"
    while True:
        r = client.get(
            url,
            params={**params, "offset": offset},
            timeout=30,
        )
        if r.status_code != 200:
            break
        data = r.json()
        ideas = data.get("ideas") if isinstance(data, dict) else []
        if not ideas:
            break
        out.extend(ideas)
        if len(ideas) < limit:
            break
        offset += limit
    return out


def _fetch_specs(client: httpx.Client, base_url: str) -> list[dict]:
    """Return spec registry entries for ID snapshot."""
    url = f"{base_url.rstrip('/')}/api/spec-registry"
    r = client.get(url, params={"limit": 1000, "offset": 0}, timeout=30)
    if r.status_code != 200:
        return []
    data = r.json()
    return data if isinstance(data, list) else []


def _count_pattern(ids: list[str], prefix: str) -> int:
    return sum(1 for i in ids if str(i).startswith(prefix))


def _run_diff(
    client: httpx.Client,
    base_url: str,
    baseline_path: Path,
    allow_idea_id_prefix: str | None = None,
) -> dict:
    """Fetch current ideas/specs and diff against baseline. Returns diff summary."""
    ideas = _fetch_ideas(client, base_url)
    specs = _fetch_specs(client, base_url)
    cur_idea_ids = set(str(i.get("id") or "").strip() for i in ideas if i.get("id"))
    cur_spec_ids = set(str(s.get("spec_id") or "").strip() for s in specs if s.get("spec_id"))

    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)
    base_idea_ids = set(baseline.get("idea_ids") or [])
    base_spec_ids = set(baseline.get("spec_ids") or [])

    added_ideas = sorted(cur_idea_ids - base_idea_ids)
    removed_ideas = sorted(base_idea_ids - cur_idea_ids)
    added_specs = sorted(cur_spec_ids - base_spec_ids)
    removed_specs = sorted(base_spec_ids - cur_spec_ids)

    base_idea_count = len(baseline.get("idea_ids") or [])
    base_spec_count = len(baseline.get("spec_ids") or [])
    no_forbidden = (
        _count_pattern(added_ideas, "endpoint-lineage-") == 0
        and _count_pattern(added_ideas, "spec-origin-") == 0
        and _count_pattern(added_specs, "auto-") == 0
    )
    if allow_idea_id_prefix and added_ideas and not removed_ideas:
        allowed_adds = [i for i in added_ideas if i.startswith(allow_idea_id_prefix)]
        if len(allowed_adds) == len(added_ideas) and len(added_specs) == 0:
            invariant_ok = no_forbidden
        else:
            invariant_ok = False
    else:
        invariant_ok = (
            len(cur_idea_ids) == base_idea_count
            and len(cur_spec_ids) == base_spec_count
            and no_forbidden
        )
    return {
        "ideas_total": len(cur_idea_ids),
        "specs_total": len(cur_spec_ids),
        "idea_ids_added": added_ideas,
        "idea_ids_removed": removed_ideas,
        "spec_ids_added": added_specs,
        "spec_ids_removed": removed_specs,
        "invariant_ok": invariant_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture local tool guard baseline (warm + ID-level snapshot)")
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--diff",
        metavar="BASELINE_JSON",
        help="Diff current ideas/specs against baseline; do not write. Exit 0 if invariant_ok else 1.",
    )
    parser.add_argument(
        "--allow-idea-id-prefix",
        metavar="PREFIX",
        help="When diffing, treat added ideas that all start with PREFIX as allowed (e.g. runtime-idea-cli-flow-).",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    with httpx.Client(timeout=30.0) as client:
        if args.diff:
            diff = _run_diff(
                client,
                base_url,
                Path(args.diff),
                allow_idea_id_prefix=args.allow_idea_id_prefix or None,
            )
            print(json.dumps(diff, indent=2))
            return 0 if diff.get("invariant_ok", False) else 1

        _warm_ideas(client, base_url)
        ideas = _fetch_ideas(client, base_url, read_only_guard=True)
        specs = _fetch_specs(client, base_url)

    idea_ids = sorted({str(i.get("id") or "").strip() for i in ideas if i.get("id")})
    spec_ids = sorted({str(s.get("spec_id") or "").strip() for s in specs if s.get("spec_id")})

    baseline = {
        "ideas_total": len(idea_ids),
        "specs_total": len(spec_ids),
        "idea_ids_endpoint_lineage": _count_pattern(idea_ids, "endpoint-lineage-"),
        "idea_ids_spec_origin": _count_pattern(idea_ids, "spec-origin-"),
        "spec_ids_auto": _count_pattern(spec_ids, "auto-"),
        "idea_ids": idea_ids,
        "spec_ids": spec_ids,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)

    print(json.dumps({"output": str(output_path), "ideas_total": baseline["ideas_total"], "specs_total": baseline["specs_total"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
