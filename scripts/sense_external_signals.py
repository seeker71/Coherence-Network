#!/usr/bin/env python3
"""Sense the outer skin of the organism and record what is found.

The internal breath lives at /api/practice — eight centers moving with
the known. Wandering lives at POST /api/sensings with kind="wandering"
and catches the unknown. This script is the skin form: it reaches into
the GitHub field (workflow runs, external PRs, upstream repos) via the
`gh` CLI, notices what asks for attention, and records each finding as
a first-class sensing in the same living graph as everything else.

One body, one source of truth. The skin signals are not in a parallel
file or a log somewhere — they live in the same /api/sensings feed the
breath and the wandering live in, and the /practice page surfaces all
three forms together.

Retrieval of what was noticed is emergent: GET /api/sensings?kind=skin
returns the most recent skin sensings the organism is holding.

Usage:
    python3 scripts/sense_external_signals.py
    python3 scripts/sense_external_signals.py --user seeker71
    python3 scripts/sense_external_signals.py --repo seeker71/Coherence-Network
    python3 scripts/sense_external_signals.py --api http://localhost:8000
    python3 scripts/sense_external_signals.py --dry-run  # print findings without posting

Requires `gh` CLI authenticated to GitHub.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


DEFAULT_USER = "seeker71"
DEFAULT_REPO = "seeker71/Coherence-Network"
DEFAULT_API = "http://localhost:8000"
STALE_PR_DAYS = 7
RECENT_CI_RUNS = 5


@dataclass
class Signal:
    kind: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    urgency: str = "notice"  # notice | attention | urgent


def gh(args: list[str]) -> str:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def days_since(iso: str) -> float:
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return 0.0
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0


def sense_external_prs(user: str) -> list[Signal]:
    """Open PRs authored by `user` in any repo. Flag stale and dirty ones."""
    raw = gh(
        [
            "search",
            "prs",
            "--author",
            user,
            "--state",
            "open",
            "--json",
            "repository,title,url,createdAt,updatedAt,number",
            "--limit",
            "30",
        ]
    )
    if not raw.strip():
        return []
    try:
        prs = json.loads(raw)
    except json.JSONDecodeError:
        return []

    signals: list[Signal] = []
    for pr in prs:
        repo = pr.get("repository", {}).get("nameWithOwner", "")
        number = pr.get("number", 0)
        title = pr.get("title", "")
        url = pr.get("url", "")
        updated = pr.get("updatedAt", "")
        created = pr.get("createdAt", "")
        age_days = days_since(created)
        stale_days = days_since(updated)

        detail = gh(
            [
                "pr",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "mergeable,mergeStateStatus,state",
            ]
        )
        mergeable = ""
        merge_state = ""
        if detail.strip():
            try:
                d = json.loads(detail)
                mergeable = d.get("mergeable", "")
                merge_state = d.get("mergeStateStatus", "")
            except json.JSONDecodeError:
                pass

        urgency = "notice"
        reasons: list[str] = []
        if mergeable == "CONFLICTING" or merge_state == "DIRTY":
            urgency = "urgent"
            reasons.append("merge conflicts")
        if stale_days >= STALE_PR_DAYS:
            urgency = "attention" if urgency == "notice" else urgency
            reasons.append(f"stale {stale_days:.0f}d since last activity")

        if reasons:
            signals.append(
                Signal(
                    kind="external_pr",
                    summary=f"{repo}#{number} — {title}",
                    details={
                        "url": url,
                        "age_days": round(age_days, 1),
                        "stale_days": round(stale_days, 1),
                        "mergeable": mergeable,
                        "merge_state": merge_state,
                        "reasons": reasons,
                    },
                    urgency=urgency,
                )
            )
    return signals


def sense_workflow_runs(repo: str) -> list[Signal]:
    """Recent workflow runs on main. Flag failures in the last N runs."""
    raw = gh(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--branch",
            "main",
            "--limit",
            str(RECENT_CI_RUNS),
            "--json",
            "status,conclusion,workflowName,displayTitle,createdAt,url",
        ]
    )
    if not raw.strip():
        return []
    try:
        runs = json.loads(raw)
    except json.JSONDecodeError:
        return []

    latest_by_workflow: dict[str, dict[str, Any]] = {}
    for run in runs:
        name = run.get("workflowName", "")
        if name not in latest_by_workflow:
            latest_by_workflow[name] = run

    signals: list[Signal] = []
    for name, run in latest_by_workflow.items():
        if run.get("conclusion") == "failure":
            signals.append(
                Signal(
                    kind="workflow_failure",
                    summary=f"{name} failing on main",
                    details={
                        "repo": repo,
                        "last_title": run.get("displayTitle", ""),
                        "url": run.get("url", ""),
                        "last_seen_days": round(
                            days_since(run.get("createdAt", "")), 1
                        ),
                    },
                    urgency="urgent",
                )
            )
    return signals


def post_sensing(api: str, signals: list[Signal], source: str) -> dict | None:
    """POST a single skin sensing summarizing what was noticed."""
    if not signals:
        return None

    urgent = [s for s in signals if s.urgency == "urgent"]
    attention = [s for s in signals if s.urgency == "attention"]

    if urgent:
        summary = (
            f"{len(urgent)} urgent skin signal(s): "
            + "; ".join(s.summary for s in urgent[:3])
        )
    elif attention:
        summary = (
            f"{len(attention)} skin signal(s) drifting: "
            + "; ".join(s.summary for s in attention[:3])
        )
    else:
        summary = f"{len(signals)} skin signal(s) worth holding"
    summary = summary[:480]

    content_parts: list[str] = []
    for label, bucket in [
        ("Urgent — asking for attention now", urgent),
        ("Attention — drifting, still in reach", attention),
        (
            "Notice — quieter signals worth holding",
            [s for s in signals if s.urgency == "notice"],
        ),
    ]:
        if not bucket:
            continue
        content_parts.append(f"\n{label}:\n")
        for s in bucket:
            content_parts.append(f"- [{s.kind}] {s.summary}")
            for k, v in s.details.items():
                if v:
                    content_parts.append(f"    {k}: {v}")
    content = "\n".join(content_parts).strip() or summary

    related_to = [
        s.details.get("url", "").rsplit("/", 1)[-1]
        for s in signals
        if s.details.get("url")
    ]

    payload = {
        "kind": "skin",
        "summary": summary,
        "content": content,
        "source": source,
        "metadata": {
            "urgent_count": len(urgent),
            "attention_count": len(attention),
            "total_count": len(signals),
            "signals": [
                {
                    "kind": s.kind,
                    "summary": s.summary,
                    "urgency": s.urgency,
                    "details": s.details,
                }
                for s in signals
            ],
        },
    }

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{api}/api/sensings",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.stderr.write(
            f"skin sensing: POST /api/sensings failed {e.code}: "
            f"{e.read().decode(errors='ignore')[:400]}\n"
        )
        return None
    except Exception as e:
        sys.stderr.write(f"skin sensing: POST /api/sensings failed: {e}\n")
        return None


def render_report(signals: list[Signal]) -> str:
    if not signals:
        return "The outer skin is clear. All external signals are in harmony.\n"

    urgent = [s for s in signals if s.urgency == "urgent"]
    attention = [s for s in signals if s.urgency == "attention"]
    notice = [s for s in signals if s.urgency == "notice"]

    lines: list[str] = []
    lines.append(f"Outer-skin sensing — {len(signals)} signal(s) from the field:\n")

    def section(label: str, items: list[Signal]) -> None:
        if not items:
            return
        lines.append(f"  {label}")
        for s in items:
            lines.append(f"    • [{s.kind}] {s.summary}")
            for k, v in s.details.items():
                if v:
                    lines.append(f"        {k}: {v}")
        lines.append("")

    section("Urgent — asking for attention now:", urgent)
    section("Attention — drifting, still in reach:", attention)
    section("Notice — quieter signals worth holding:", notice)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default=DEFAULT_USER, help="GitHub user to sense PRs for")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Repo to sense CI for")
    parser.add_argument("--api", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print findings without posting to the graph",
    )
    args = parser.parse_args()

    signals: list[Signal] = []
    signals.extend(sense_external_prs(args.user))
    signals.extend(sense_workflow_runs(args.repo))

    sys.stdout.write(render_report(signals))

    if args.dry_run or not signals:
        return 0 if not any(s.urgency == "urgent" for s in signals) else 2

    source = f"sense_external_signals.py user={args.user} repo={args.repo}"
    result = post_sensing(args.api, signals, source)
    if result:
        sys.stdout.write(
            f"\nstored as sensing {result['id']} in the living graph\n"
        )
    return 0 if not any(s.urgency == "urgent" for s in signals) else 2


if __name__ == "__main__":
    sys.exit(main())
