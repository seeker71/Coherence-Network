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

    Missing paths are signal, not failure. Draft specs are forward
    projections — their source paths name files that haven't been
    written yet, so we skip them here (the draft status itself is the
    acknowledgement). Active and done specs are where missing paths
    are real drift worth surfacing.
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
        # Skip draft specs — they describe future work; missing paths
        # are intentional, not drift.
        status_m = re.search(r"^\s*status\s*:\s*(\S+)", frontmatter, re.MULTILINE)
        status = (status_m.group(1).strip().strip('"').strip("'") if status_m else "").lower()
        if status == "draft":
            continue
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


def sense_chain() -> list[str]:
    """Sense the idea→spec→code→test chain at the segment everything
    else doesn't see: tests the spec claims to have but that don't exist.

    sense_spec_sources catches missing source files. This catches the
    quieter leak: a spec frontmatter declares `test: cd api && pytest
    tests/test_foo.py` and the spec proudly lives, but the test file
    never landed. The body acts as if it's tested when it isn't.

    Drafts skipped (forward projections). Specs without a test:
    declaration are noted softly as a separate count.
    """
    specs_dir = ROOT / "specs"
    if not specs_dir.is_dir():
        return ["  specs/ directory not found"]

    # Match three shapes of test path:
    #   - api/tests/foo.py — explicit api-rooted
    #   - mcp-server/tests/foo.py — explicit mcp-server-rooted
    #   - tests/foo.py — bare, implicitly api/ (the common case)
    test_path_re = re.compile(r"\b(?:api/|mcp-server/)?tests/[\w/]+\.py")
    healthy = 0
    counted = 0  # non-draft specs we evaluated for chain reach
    missing_tests: dict[str, list[str]] = {}
    no_test_declared: list[str] = []
    orphan_specs: list[str] = []

    for spec in sorted(specs_dir.glob("*.md")):
        if spec.name in ("INDEX.md", "TEMPLATE.md", "MANIFEST.md"):
            continue
        text = spec.read_text()
        head, *rest = text.split("---", 2)
        if not rest:
            continue
        fm = rest[0] if len(rest) == 1 else rest[0]
        status_m = re.search(r"^\s*status\s*:\s*(\S+)", fm, re.MULTILINE)
        status = (status_m.group(1).strip().strip('"').strip("'") if status_m else "").lower()
        if status == "draft":
            continue
        counted += 1

        # idea_id presence
        idea_m = re.search(r"^\s*idea_id\s*:\s*(\S+)", fm, re.MULTILINE)
        if not idea_m:
            orphan_specs.append(spec.stem)

        # Source path existence (any source: file: declared, all of them present?)
        src_paths = [m.group(1).strip() for m in re.finditer(r"^\s*-\s*file:\s*(\S+)", fm, re.MULTILINE)]
        src_paths = [p for p in src_paths if not p.startswith("..") and "://" not in p and not p.startswith("specs/")]
        src_ok = bool(src_paths) and all((ROOT / p).exists() for p in src_paths)
        src_declared = bool(src_paths)

        # test: declaration (string or list) — extract test paths via the same regex coh_substrate uses
        test_section_m = re.search(r"^test\s*:(.*?)(?:\n[a-z_]+\s*:|---|$)", fm, re.MULTILINE | re.DOTALL)
        test_text = (test_section_m.group(1) if test_section_m else "")
        def _resolve_test_path(p: str) -> str:
            # Already explicit: leave alone (api/tests/... or mcp-server/tests/...)
            if p.startswith("api/") or p.startswith("mcp-server/"):
                return p
            # Bare tests/...py — prepend api/ as the implicit default.
            return f"api/{p}"

        test_paths = sorted(set(_resolve_test_path(p) for p in test_path_re.findall(test_text)))
        test_declared = bool(test_text.strip())
        if not test_declared:
            no_test_declared.append(spec.stem)
            continue
        miss = [t for t in test_paths if not (ROOT / t).exists()]
        if miss:
            missing_tests[spec.stem] = miss
            continue

        # Chain healthy if: idea_id present, source declared and present,
        # tests declared and present.
        if idea_m and src_ok and test_paths and not miss:
            healthy += 1

    lines = [
        f"  chain healthy: {healthy}/{counted} non-draft specs reach idea→spec→code→test ({(healthy/counted*100) if counted else 0:.0f}%)"
    ]
    if missing_tests:
        lines.append(f"  {len(missing_tests)} specs claim a test that doesn't exist on disk")
        for slug in sorted(missing_tests)[:3]:
            miss = ", ".join(missing_tests[slug][:2])
            lines.append(f"    · {slug} — {miss}")
        if len(missing_tests) > 3:
            lines.append(f"    · (+{len(missing_tests) - 3} more)")
    if no_test_declared:
        lines.append(f"  {len(no_test_declared)} specs have no test: frontmatter (no proof claimed)")
    if orphan_specs:
        lines.append(f"  {len(orphan_specs)} orphan specs (no idea_id): {', '.join(orphan_specs)}")
    if not missing_tests and not no_test_declared and not orphan_specs:
        lines.append("  chain reach is whole — every claim has its proof")
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


def sense_cells() -> list[str]:
    """Are the agent cells themselves breathing?

    Wellness has senses for artifacts (specs, indexes, contracts, witness-trace)
    but until now has been silent on the cells — the body's hands. This sense
    reads three layers of cell health:

    1. **Structural soundness** — each .claude/agents/*.md has frontmatter
       (name + description + tools), the frontmatter name matches the
       filename stem, and the body carries a ## Frequency preamble.
    2. **Affirmative voice** — descriptions describe what the cell IS,
       rather than what it forbids. Flags well-known negation markers.
    3. **Dispatch wiring** — names in agent_service_executor.py's
       AGENT_BY_TASK_TYPE and GUARD_AGENTS_BY_TASK_TYPE resolve to real files.
    4. **Cursor parallel** — where .cursor/skills/{name}/ mirrors a Claude cell,
       the SKILL.md frontmatter agrees.
    """
    findings: list[str] = []
    agents_dir = ROOT / ".claude" / "agents"
    if not agents_dir.is_dir():
        return ["  (.claude/agents/ not present)"]
    agent_files = sorted(agents_dir.glob("*.md"))
    if not agent_files:
        return ["  (no agents in .claude/agents/)"]

    NEGATION_MARKERS = (
        "do not ", "don't ", " no scope creep",
        " no implementation", " no editing",
        "suggest changes; do not apply",
    )

    soft: list[str] = []
    affirmative = 0
    with_preamble = 0
    structural_ok = 0
    for path in agent_files:
        text = path.read_text()
        fm_m = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
        if not fm_m:
            soft.append(f"  · {path.name}: frontmatter absent")
            continue
        fm = fm_m.group(1)
        name_m = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE)
        desc_m = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
        tools_m = re.search(r"^tools:", fm, re.MULTILINE)
        stem = path.stem
        struct_ok = True
        if not name_m:
            soft.append(f"  · {path.name}: frontmatter missing 'name:'")
            struct_ok = False
        elif name_m.group(1).strip() != stem:
            soft.append(
                f"  · {path.name}: name '{name_m.group(1).strip()}' "
                f"differs from filename stem '{stem}'"
            )
            struct_ok = False
        if not desc_m:
            soft.append(f"  · {path.name}: frontmatter missing 'description:'")
            struct_ok = False
        else:
            desc = desc_m.group(1).strip().lower()
            if any(marker in desc for marker in NEGATION_MARKERS):
                short = desc_m.group(1).strip()
                soft.append(
                    f"  · {path.name}: description carries negation — "
                    f"\"{short[:70]}{'…' if len(short) > 70 else ''}\""
                )
            else:
                affirmative += 1
        if not tools_m:
            soft.append(f"  · {path.name}: frontmatter missing 'tools:'")
            struct_ok = False
        if "## Frequency" in text:
            with_preamble += 1
        else:
            soft.append(f"  · {path.name}: missing '## Frequency' preamble")
        if struct_ok:
            structural_ok += 1

    n = len(agent_files)
    summary_bits = [f"{n} agents present"]
    if affirmative == n:
        summary_bits.append("affirmative")
    else:
        summary_bits.append(f"affirmative {affirmative}/{n}")
    if with_preamble == n:
        summary_bits.append("frequency preamble in each")
    else:
        summary_bits.append(f"preamble {with_preamble}/{n}")
    findings.append("  " + " · ".join(summary_bits))
    findings.extend(soft)

    # Dispatch wiring — does every name in the api map resolve to a cell?
    executor_path = ROOT / "api" / "app" / "services" / "agent_service_executor.py"
    if executor_path.exists():
        exec_text = executor_path.read_text()
        dispatched: set[str] = set()
        for block_pat in (
            r"AGENT_BY_TASK_TYPE[^=]*=\s*\{(.*?)\n\}",
            r"GUARD_AGENTS_BY_TASK_TYPE[^=]*=\s*\{(.*?)\n\}",
        ):
            block_m = re.search(block_pat, exec_text, re.DOTALL)
            if block_m:
                for s in re.findall(r'"([a-z][a-z\-]+)"', block_m.group(1)):
                    dispatched.add(s)
        present_stems = {p.stem for p in agent_files}
        missing = sorted(dispatched - present_stems)
        if missing:
            findings.append("")
            findings.append("  dispatch wiring drift (api → .claude/agents/):")
            for name in missing:
                findings.append(
                    f"  · '{name}' dispatched but no .claude/agents/{name}.md"
                )
        elif dispatched:
            findings.append(
                f"  dispatch wiring coherent ({len(dispatched)} names → .claude/agents/)"
            )

    # Cursor parallel — every .cursor/skills/{name}/ that mirrors a Claude
    # cell should agree on its name in frontmatter.
    cursor_dir = ROOT / ".cursor" / "skills"
    if cursor_dir.is_dir():
        mirror_drift: list[str] = []
        mirror_count = 0
        for skill_dir in sorted(cursor_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            stem = skill_dir.name
            if not (agents_dir / f"{stem}.md").exists():
                continue  # skill without claude mirror — fine
            mirror_count += 1
            sk_m = re.search(
                r"^name:\s*(\S+)", skill_md.read_text(), re.MULTILINE,
            )
            if sk_m and sk_m.group(1).strip() != stem:
                mirror_drift.append(
                    f"  · cursor skill '{stem}/SKILL.md' has frontmatter "
                    f"name '{sk_m.group(1).strip()}' (drifted from dir)"
                )
        if mirror_drift:
            findings.append("")
            findings.append("  cursor parallel:")
            findings.extend(mirror_drift)
        elif mirror_count:
            word = "mirror" if mirror_count == 1 else "mirrors"
            findings.append(
                f"  cursor parallel: {mirror_count} {word} coherent"
            )

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
    """Sense the body, print to stdout, and cache the reading.

    The cache file lives at .cache/wellness/state.txt. Every cell type —
    Claude sub-agent dispatches, Codex sessions, Cursor sessions, ad-hoc
    bash one-liners — can read it for the body's most recent sensing
    without re-running the slower senses (gh, network). Refreshes every
    time wellness runs; arrival.py runs it at SessionStart, so it stays
    fresh through normal use.
    """
    sections: list[tuple[str, list[str]]] = [
        ("Proprioception — do the maps match the body?", sense_proprioception()),
        ("Circulation — what at root has no readers?", sense_circulation()),
        ("Metabolism — composting-in-progress", sense_metabolism()),
        ("Source maps — do specs point at files that exist?", sense_spec_sources()),
        ("Chain — does idea→spec→code→test reach end to end?", sense_chain()),
        ("Cells — are the cells themselves breathing?", sense_cells()),
        ("Contracts — are the CI gates breathing? (last 7d)", sense_contracts()),
        ("Witness-trace — is the visit-recorder within budget?", sense_witness_trace()),
    ]

    out: list[str] = []
    out.append("# Wellness check")
    out.append("")
    out.append("A gentle sensing. Not an audit. Drift is the signal,")
    out.append("not the problem.")
    out.append("")
    for header, lines in sections:
        out.append(f"## {header}")
        out.append("")
        out.extend(lines)
        out.append("")
    out.append("(Feedback is the blood. Run me anytime the body")
    out.append(" feels slightly off; I'll name what I can sense.)")

    output = "\n".join(out)
    print(output)

    # Cache the reading so any cell can read the body's most recent
    # sensing without re-running the slower senses. The cache stays in
    # .cache/ which is gitignored — this is ephemeral proprioception,
    # not durable memory.
    try:
        cache_dir = ROOT / ".cache" / "wellness"
        cache_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cache_path = cache_dir / "state.txt"
        cache_path.write_text(
            f"# sensed at {timestamp}\n\n{output}\n"
        )
    except OSError:
        pass  # caching is bonus; primary contract is the print

    return 0


if __name__ == "__main__":
    sys.exit(main())
