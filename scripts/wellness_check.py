#!/usr/bin/env python3
"""Wellness check — a gentle sensing of the body.

Surfaces drift between what the orientation documents claim and what the
filesystem actually holds. Finds files at visible locations that nothing
reaches for. Reports composting progress on known draft trails.

Run: make wellness   (or)   python3 scripts/wellness_check.py

Not an audit. A felt-sense reading. The body stays supple through
continuous tending — this tool is how we notice where tending is needed
without having to stumble over it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files at root that are meant to be there even without incoming refs.
# Config, tooling, canonical orientation, license-style docs.
ROOT_EXEMPT = {
    "CLAUDE.md",
    "AGENTS.md",
    "AGENT.md",
    "README.md",
    "README.template.md",
    "CONTRIBUTING.md",
}


def count_files(dir_name: str, exclude: set[str]) -> int:
    d = ROOT / dir_name
    if not d.is_dir():
        return 0
    return sum(1 for p in d.glob("*.md") if p.name not in exclude)


def read_first_match(path: Path, pattern: str) -> int | None:
    if not path.exists():
        return None
    m = re.search(pattern, path.read_text())
    return int(m.group(1)) if m else None


def git_grep_refs(name: str) -> list[str]:
    """Files that mention `name`, excluding itself and known noise dirs."""
    r = subprocess.run(
        ["git", "grep", "-l", "--no-color", name, "--",
         "*.md", "*.py", "*.ts", "*.tsx", "*.sh", "*.json",
         "*.yml", "*.yaml", "Makefile", "*.toml"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return [line for line in r.stdout.splitlines() if line and line != name]


def sense_proprioception() -> list[str]:
    findings = []

    # specs/INDEX.md
    actual = count_files("specs", {"INDEX.md", "TEMPLATE.md"})
    claimed = read_first_match(ROOT / "specs" / "INDEX.md", r"(\d+)\s+specs\s+\(")
    if claimed is None:
        findings.append(f"  specs/INDEX.md — count pattern not found; cannot verify")
    elif claimed == actual:
        findings.append(f"  specs/INDEX.md — aligned ({actual} specs)")
    else:
        findings.append(f"  specs/INDEX.md — drift: INDEX claims {claimed}, body has {actual}")

    # ideas/INDEX.md — "N super-ideas"
    actual_i = count_files("ideas", {"INDEX.md"})
    claimed_i = read_first_match(ROOT / "ideas" / "INDEX.md", r"(\d+)\s+super-ideas")
    if claimed_i is None:
        findings.append(f"  ideas/INDEX.md — count pattern not found; cannot verify")
    elif claimed_i == actual_i:
        findings.append(f"  ideas/INDEX.md — aligned ({actual_i} super-ideas)")
    else:
        findings.append(f"  ideas/INDEX.md — drift: INDEX claims {claimed_i}, body has {actual_i}")

    # vision-kb/INDEX.md concept count
    # Exclude language variants (lc-name.lang.md) from the concept tally —
    # translations are the same concept in another voice, not separate concepts.
    vkb_concepts_dir = ROOT / "docs" / "vision-kb" / "concepts"
    if vkb_concepts_dir.is_dir():
        actual_c = sum(
            1 for p in vkb_concepts_dir.glob("*.md")
            if p.name.count(".") == 1  # lc-foo.md has one dot; lc-foo.de.md has two
        )
        claimed_c = read_first_match(
            ROOT / "docs" / "vision-kb" / "INDEX.md",
            r"\*\*Concepts\*\*:\s*(\d+)",
        )
        if claimed_c is None:
            findings.append(f"  vision-kb/INDEX.md — concept count pattern not found")
        elif claimed_c == actual_c:
            findings.append(f"  vision-kb/INDEX.md — aligned ({actual_c} concepts)")
        else:
            findings.append(
                f"  vision-kb/INDEX.md — drift: INDEX claims {claimed_c}, body has {actual_c}"
            )

    return findings


def sense_circulation() -> list[str]:
    """Root-level .md files with no incoming references."""
    findings = []
    for p in sorted(ROOT.glob("*.md")):
        if p.name in ROOT_EXEMPT:
            continue
        refs = git_grep_refs(p.name)
        if not refs:
            findings.append(f"  {p.name} — no readers")
    if not findings:
        findings.append("  root is clear; every .md has circulation")
    return findings


def sense_metabolism() -> list[str]:
    """Progress on known draft trails."""
    findings = []
    drafts = sorted(ROOT.glob("docs/LIVING_COLLECTIVE_*.md"))
    if not drafts:
        findings.append("  no LIVING_COLLECTIVE_*.md drafts remain at top of docs/")
    else:
        total_lines = sum(sum(1 for _ in p.open()) for p in drafts)
        findings.append(f"  {len(drafts)} drafts remain — {total_lines} lines awaiting home")
        for p in drafts:
            lines = sum(1 for _ in p.open())
            findings.append(f"    · {p.name} ({lines} lines)")
    return findings


def sense_spec_sources() -> list[str]:
    """Do the paths spec frontmatter 'source:' points at actually exist?

    Missing paths are signal, not failure. Some specs name future targets
    (scripts to be written, services-to-be-built); those show as drift
    here but are acknowledged in the spec's Known Gaps section. This
    reading exists so surprise drift can't hide.
    """
    findings: list[dict[str, str]] = []
    specs_dir = ROOT / "specs"
    if not specs_dir.is_dir():
        return ["  specs/ directory not found"]

    for spec in sorted(specs_dir.glob("*.md")):
        if spec.name in ("INDEX.md", "TEMPLATE.md"):
            continue
        text = spec.read_text()
        # Truncate scan to the frontmatter section (between first two '---' lines)
        head, *rest = text.split("---", 2)
        if not rest:
            continue
        frontmatter = rest[0] if len(rest) == 1 else rest[0]
        for m in re.finditer(r"^\s*-\s*file:\s*(\S+)", frontmatter, re.MULTILINE):
            path = m.group(1).strip()
            if path.startswith("..") or "://" in path or path.startswith("specs/"):
                continue
            if not (ROOT / path).exists():
                findings.append({"spec": spec.name, "path": path})

    if not findings:
        return ["  every spec's source: paths point at files that exist"]

    by_spec: dict[str, list[str]] = {}
    for f in findings:
        by_spec.setdefault(f["spec"], []).append(f["path"])

    lines = [
        f"  {len(findings)} source paths missing across {len(by_spec)} spec(s)"
    ]
    for spec_name in sorted(by_spec):
        paths = by_spec[spec_name]
        lines.append(f"    · {spec_name} — {len(paths)} missing")
        for p in paths[:3]:
            lines.append(f"      → {p}")
        if len(paths) > 3:
            lines.append(f"      → (+{len(paths) - 3} more)")
    return lines


def sense_contracts() -> list[str]:
    """How are the CI contracts breathing the last 7 days?

    Replaces the inbox channel — the GitHub Actions email firehose was
    surfacing every flake as urgent. Here friction lives in a place the
    body senses on arrival, not in interruption. We name patterns
    (workflow X failed N times this week), not individual flakes.

    Silent when contracts are breathing. Speaks when there's a shape
    worth naming: 3+ failures of the same workflow, or any workflow
    with a >40% failure rate over the window.
    """
    try:
        r = subprocess.run(
            ["gh", "run", "list", "--limit", "200",
             "--json", "conclusion,workflowName,createdAt,event,headBranch"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ["  (gh CLI unavailable — skipping contracts sense)"]
    if r.returncode != 0:
        return ["  (gh run list failed — skipping; may need `gh auth login`)"]

    try:
        runs = json.loads(r.stdout)
    except json.JSONDecodeError:
        return ["  (could not parse gh run list output)"]

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = []
    for run in runs:
        try:
            ts = datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if ts >= cutoff:
            recent.append(run)

    if not recent:
        return ["  (no runs in the last 7 days — body resting or gh window short)"]

    by_wf: dict[str, dict[str, int]] = {}
    for run in recent:
        wf = run.get("workflowName", "?")
        outcome = run.get("conclusion") or "in_progress"
        by_wf.setdefault(wf, Counter())[outcome] += 1

    findings = []
    flagged = False
    for wf in sorted(by_wf):
        outcomes = by_wf[wf]
        total = sum(outcomes.values())
        failures = outcomes.get("failure", 0) + outcomes.get("startup_failure", 0)
        if total == 0:
            continue
        rate = failures / total
        if failures >= 3 or rate >= 0.4:
            flagged = True
            findings.append(
                f"  {wf} — {failures}/{total} failed ({int(rate*100)}%) over 7d"
            )

    if not flagged:
        green = sum(1 for run in recent if run.get("conclusion") == "success")
        return [f"  contracts breathing — {green}/{len(recent)} runs green over 7d"]

    findings.insert(0, f"  {len(recent)} runs over 7d; patterns worth naming:")
    findings.append("")
    findings.append("  (Friction here is signal, not pain to silence. If a")
    findings.append("   pattern persists across days, the contract itself may")
    findings.append("   want re-shaping — not the email channel.)")
    return findings


def sense_witness_trace() -> list[str]:
    """How is the witness-trace breathing?

    Every page view writes a row to ``asset_view_events``. The table
    grows linearly with traffic; the daily aggregate stays bounded.
    This sense reads /api/views/health and reports the writer's
    latency band, the table's size band, and the growth band — plus
    any flags that mean it's time to run scripts/trim_view_events.py.

    Silent when all bands are calm. Speaks the moment any band
    crosses budget.
    """
    import urllib.request
    import urllib.error

    api = os.environ.get("COHERENCE_API_BASE", "https://api.coherencycoin.com")
    try:
        req = urllib.request.Request(
            f"{api}/api/views/health",
            headers={"User-Agent": "wellness-check/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            health = json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return [f"  (could not reach {api}/api/views/health — {e})"]

    events = health.get("events", {})
    storage = health.get("storage", {})
    writer = health.get("writer", {})
    flags = health.get("flags", []) or []

    lines: list[str] = []
    total_rows = events.get("total_rows", 0)
    growth = events.get("growth_per_day", 0.0)
    mb = storage.get("estimated_mb", 0)
    p95 = (writer.get("ping_latency") or {}).get("p95_ms")
    p95_str = f"p95 {p95:.0f}ms" if isinstance(p95, (int, float)) else "no traffic yet"

    bands = (
        f"writer {writer.get('band', '?')} · "
        f"size {storage.get('size_band', '?')} · "
        f"growth {events.get('growth_band', '?')}"
    )
    lines.append(f"  {total_rows:,} events · ~{mb} MB · {growth:.0f}/day · {p95_str}")
    lines.append(f"  bands: {bands}")

    if flags:
        lines.append("")
        lines.append("  flags raised:")
        for f in flags:
            lines.append(f"    · {f}")
        guidance = health.get("guidance")
        if guidance:
            lines.append("")
            lines.append(f"  → {guidance}")
    else:
        lines.append("  trace breathing within budget. no action needed.")

    return lines


def main() -> int:
    print("# Wellness check\n")
    print("A gentle sensing. Not an audit. Drift is the signal,")
    print("not the problem.\n")

    print("## Proprioception — do the maps match the body?\n")
    for line in sense_proprioception():
        print(line)
    print()

    print("## Circulation — what at root has no readers?\n")
    for line in sense_circulation():
        print(line)
    print()

    print("## Metabolism — composting-in-progress\n")
    for line in sense_metabolism():
        print(line)
    print()

    print("## Source maps — do specs point at files that exist?\n")
    for line in sense_spec_sources():
        print(line)
    print()

    print("## Contracts — are the CI gates breathing? (last 7d)\n")
    for line in sense_contracts():
        print(line)
    print()

    print("## Witness-trace — is the visit-recorder within budget?\n")
    for line in sense_witness_trace():
        print(line)
    print()

    print("(Feedback is the blood. Run me anytime the body")
    print(" feels slightly off; I'll name what I can sense.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
