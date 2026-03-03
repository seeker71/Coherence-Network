#!/usr/bin/env python3
"""Audit external tooling usage and detect untracked additions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _load_registry(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _discover_workflow_actions(workflows_dir: Path) -> set[str]:
    actions: set[str] = set()
    uses_re = re.compile(r"^\s*uses:\s*([^\s]+)\s*$")
    for wf in sorted(workflows_dir.glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        for line in text.splitlines():
            m = uses_re.match(line)
            if not m:
                continue
            action = m.group(1).strip()
            if action.startswith("./"):
                continue
            actions.add(action)
    return actions


def _extract_command(line: str) -> str | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None

    if s.startswith("- "):
        s = s[2:].strip()
    if not s:
        return None

    # Ignore shell function definitions like:
    #   run_validate() { ... }
    #   c() { ... }
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*\(\)\s*\{?\s*$", s):
        return None

    # Handle command substitution assignments like:
    #   VAR=$(git log -1 ...)
    #   VAR="$(git rev-parse HEAD)"
    assignment_cmd = re.match(
        r"^(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=(?:\"|')?\$\((.+)\)(?:\"|')?\s*$",
        s,
    )
    if assignment_cmd:
        inner = assignment_cmd.group(1).strip()
        # Likely a local function call: exit_code=$(run_validate)
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", inner):
            return None
        s = inner
    else:
        # Ignore pure assignment lines (including GitHub expression assignments).
        # These commonly contain spaces and are not "env prefix + command" patterns.
        if re.match(r"^(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=", s):
            return None

        # Strip simple env-var prefixes that precede a command, e.g.:
        #   FOO=bar BAR=baz git status
        # Only applies when values are whitespace-free.
        while True:
            m = re.match(r"^(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=[^\s\"']+\s+(.+)$", s)
            if not m:
                break
            s = m.group(1).strip()

    if not s:
        return None

    token = re.split(r"[ \t|;&()]+", s, maxsplit=1)[0].strip()
    if not token:
        return None

    if token.startswith(("\"", "'", "-", "${", "steps.", "}")):
        return None

    shell_keywords = {
        "if",
        "then",
        "else",
        "elif",
        "fi",
        "for",
        "do",
        "done",
        "while",
        "case",
        "esac",
        "in",
        "function",
        "{",
        "}",
        "set",
        "exit",
        "break",
        "continue",
        "local",
    }
    if token in shell_keywords:
        return None

    # Ignore local script paths; this audit is about external tooling.
    if "/" in token:
        return None

    # Normalize common variants.
    if token == "python3":
        token = "python"

    return token


def _discover_workflow_cli_tools(workflows_dir: Path) -> set[str]:
    tools: set[str] = set()
    run_re = re.compile(r"^(\s*)run:\s*\|\s*$")

    for wf in sorted(workflows_dir.glob("*.yml")):
        lines = wf.read_text(encoding="utf-8").splitlines()
        i = 0
        in_continuation = False
        heredoc_end: str | None = None
        in_single_quote_literal = False

        while i < len(lines):
            m = run_re.match(lines[i])
            if not m:
                i += 1
                continue

            indent = len(m.group(1))
            i += 1
            in_continuation = False
            heredoc_end = None
            in_single_quote_literal = False

            while i < len(lines):
                raw = lines[i]
                if raw.strip() == "":
                    i += 1
                    continue
                current_indent = len(raw) - len(raw.lstrip(" "))
                if current_indent <= indent:
                    break

                stripped = raw.strip()

                # Skip heredoc bodies; they are data, not executed commands.
                if heredoc_end is not None:
                    if stripped == heredoc_end:
                        heredoc_end = None
                    i += 1
                    continue

                # Skip single-quoted multi-line literals (for example awk programs or JSON passed to curl).
                if in_single_quote_literal:
                    if stripped.count("'") % 2 == 1:
                        in_single_quote_literal = False
                    i += 1
                    continue

                if in_continuation:
                    in_continuation = stripped.endswith("\\")
                    i += 1
                    continue

                heredoc_start = re.search(r"<<-?\s*(?:'|\")?([A-Za-z_][A-Za-z0-9_]*)(?:'|\")?", stripped)
                if heredoc_start:
                    heredoc_end = heredoc_start.group(1)

                cmd = _extract_command(stripped)
                if cmd:
                    tools.add(cmd)

                if stripped.count("'") % 2 == 1:
                    in_single_quote_literal = True

                in_continuation = stripped.endswith("\\")
                i += 1

    return tools


def _discover_dependency_ecosystems(repo_root: Path) -> set[str]:
    ecosystems: set[str] = set()
    if (repo_root / ".github" / "workflows").exists():
        ecosystems.add("github-actions")
    if (repo_root / "api" / "requirements.txt").exists() or (repo_root / "api" / "pyproject.toml").exists():
        ecosystems.add("pip")
    if (repo_root / "web" / "package.json").exists():
        ecosystems.add("npm")
    return ecosystems


def build_report(registry: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    workflows_dir = repo_root / ".github" / "workflows"
    discovered_actions = sorted(_discover_workflow_actions(workflows_dir))
    discovered_tools = sorted(_discover_workflow_cli_tools(workflows_dir))
    discovered_ecosystems = sorted(_discover_dependency_ecosystems(repo_root))

    tracked_actions = set(registry.get("github_actions", []))
    tracked_tools = set(registry.get("workflow_cli_tools", []))
    tracked_ecosystems = set(registry.get("dependency_ecosystems", []))

    untracked_actions = sorted(set(discovered_actions) - tracked_actions)
    untracked_tools = sorted(set(discovered_tools) - tracked_tools)
    untracked_ecosystems = sorted(set(discovered_ecosystems) - tracked_ecosystems)

    report = {
        "policy": registry.get("policy", {}),
        "discovered": {
            "github_actions": discovered_actions,
            "workflow_cli_tools": discovered_tools,
            "dependency_ecosystems": discovered_ecosystems,
        },
        "tracked": {
            "github_actions": sorted(tracked_actions),
            "workflow_cli_tools": sorted(tracked_tools),
            "dependency_ecosystems": sorted(tracked_ecosystems),
        },
        "untracked": {
            "github_actions": untracked_actions,
            "workflow_cli_tools": untracked_tools,
            "dependency_ecosystems": untracked_ecosystems,
        },
        "ok": not (untracked_actions or untracked_tools or untracked_ecosystems),
    }
    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--registry",
        default="docs/system_audit/external_tools_registry.json",
        help="Path to external tools registry JSON",
    )
    p.add_argument("--json", action="store_true", help="Output JSON report")
    p.add_argument("--fail-on-untracked", action="store_true", help="Exit non-zero when untracked tools are found")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    registry = _load_registry(repo_root / args.registry)
    report = build_report(registry, repo_root)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Audit OK: {report['ok']}")
        print(f"Untracked github actions: {report['untracked']['github_actions']}")
        print(f"Untracked workflow CLI tools: {report['untracked']['workflow_cli_tools']}")
        print(f"Untracked dependency ecosystems: {report['untracked']['dependency_ecosystems']}")

    if args.fail_on_untracked and not report["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
