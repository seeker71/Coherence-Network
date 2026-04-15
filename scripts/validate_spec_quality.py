#!/usr/bin/env python3
"""Validate spec quality so implementation does not need manual follow-up gap fixes."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Iterable


PLACEHOLDER_PATTERNS = [
    r"\[Feature Name\]",
    r"\[1.?2 sentences",
    r"\[What this does NOT include\]",
]

SECTION_ALIASES = {
    "purpose": {"purpose"},
    "requirements": {"requirements", "requirements checklist"},
    "files": {"files to create/modify", "files to create or modify", "files to modify"},
    "acceptance": {"acceptance tests", "acceptance criteria"},
    "verification": {"verification", "verification steps", "validation", "validation steps"},
    "out_of_scope": {"out of scope", "non-goals", "not in scope"},
    "risks": {
        "risks and assumptions",
        "assumptions and risks",
        "risks / assumptions",
        "risks",
        "assumptions",
        "risks and known gaps",
    },
    "gaps": {
        "known gaps and follow-up tasks",
        "known gaps",
        "gap follow-ups",
        "risks and known gaps",
    },
}


def _normalize_heading(title: str) -> str:
    # Remove everything in parentheses to handle "Verification (CI complete)" etc.
    title = re.sub(r"\(.*?\)", "", title)
    cleaned = re.sub(r"[^a-z0-9\s/_-]", "", title.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _parse_sections(markdown: str) -> list[tuple[str, str]]:
    lines = markdown.splitlines()
    headers: list[tuple[int, str, int]] = []
    for idx, line in enumerate(lines):
        m = re.match(r"^(#{2,6})\s+(.+?)\s*$", line)
        if not m:
            continue
        headers.append((len(m.group(1)), m.group(2).strip(), idx))

    sections: list[tuple[str, str]] = []
    for index, (_level, title, start_idx) in enumerate(headers):
        end_idx = headers[index + 1][2] if index + 1 < len(headers) else len(lines)
        body = "\n".join(lines[start_idx + 1 : end_idx]).strip()
        sections.append((_normalize_heading(title), body))
    return sections


def _find_section(sections: list[tuple[str, str]], aliases: set[str]) -> str | None:
    normalized_aliases = {_normalize_heading(alias) for alias in aliases}
    for title, body in sections:
        if title in normalized_aliases:
            return body
        # Allow partial match if title starts with an alias (e.g. "Verification CI complete")
        for alias in normalized_aliases:
            if title.startswith(alias + " ") or title.endswith(" " + alias):
                return body
    return None


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _checklist_items(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"(?im)^\s*-\s*\[[ xX]\]\s+(.+)$", text)]


def _bullet_items(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"(?im)^\s*-\s+(.+)$", text)]


def _contains_command(text: str) -> bool:
    command_tokens = ("pytest", "npm run", "curl ", "make ", "uvicorn", "python ", "python3 ")
    lowered = text.lower()
    if any(token in lowered for token in command_tokens):
        return True
    if re.search(r"```(?:bash|sh|zsh)\b", lowered):
        return True
    return False


def _looks_like_path(text: str) -> bool:
    return bool(re.search(r"[/\\]|\.py\b|\.ts\b|\.tsx\b|\.md\b|\.json\b", text))


def _looks_like_test_reference(text: str) -> bool:
    lowered = text.lower()
    if "manual validation" in lowered:
        return True
    # If it contains a test command like pytest, it's a test reference
    if _contains_command(text):
        return True
    return bool(re.search(r"tests?/|test_[a-z0-9_]+\.py|\.spec\.", lowered))


def validate_spec(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        markdown = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"failed to read file: {exc}"]

    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, markdown, flags=re.IGNORECASE):
            errors.append(f"contains unresolved template placeholder matching /{pattern}/")

    sections = _parse_sections(markdown)
    if not sections:
        errors.append("no markdown sections found")
        return errors

    bodies: dict[str, str] = {}
    for key, aliases in SECTION_ALIASES.items():
        body = _find_section(sections, aliases)
        if body is None:
            errors.append(f"missing required section: {key}")
        else:
            bodies[key] = body

    purpose = bodies.get("purpose", "")
    if purpose and _word_count(purpose) < 12:
        errors.append("purpose section must contain at least 12 words")

    requirements = bodies.get("requirements", "")
    if requirements:
        items = _checklist_items(requirements)
        if len(items) < 3:
            errors.append("requirements section must include at least 3 checklist items")
        placeholders = [item for item in items if re.search(r"requirement\s+\d", item, flags=re.IGNORECASE)]
        if placeholders:
            errors.append("requirements section contains placeholder checklist items")

    files = bodies.get("files", "")
    if files:
        file_items = _bullet_items(files)
        if not file_items:
            errors.append("files section must include at least one bullet entry")
        elif not any(_looks_like_path(item) for item in file_items):
            errors.append("files section must reference at least one concrete file path")

    acceptance = bodies.get("acceptance", "")
    if acceptance and not _looks_like_test_reference(acceptance):
        errors.append("acceptance section must reference tests/ or explicit manual validation")

    verification = bodies.get("verification", "")
    if verification and not _contains_command(verification):
        errors.append("verification section must include executable verification commands")

    out_of_scope = bodies.get("out_of_scope", "")
    if out_of_scope and len(_bullet_items(out_of_scope)) < 1:
        errors.append("out_of_scope section must include at least one bullet item")

    risks = bodies.get("risks", "")
    if risks and len(_bullet_items(risks)) < 1:
        errors.append("risks section must include at least one bullet item")

    gaps = bodies.get("gaps", "")
    if gaps:
        gap_items = _bullet_items(gaps)
        if not gap_items:
            errors.append("gaps section must include bullets or explicit 'None'")
        else:
            if not any(re.search(r"\bnone\b", item, flags=re.IGNORECASE) for item in gap_items):
                if not any(re.search(r"\b(task|issue|todo|follow-?up)\b", item, flags=re.IGNORECASE) for item in gap_items):
                    errors.append("gaps section must include follow-up task/issue references or explicit 'None'")

    return errors


def _specs_dir_for_workspace(repo_root: Path, workspace_id: str) -> Path:
    """Resolve the specs directory for a workspace.

    Default workspace ('coherence-network') uses the legacy repo-root
    ``specs/`` directory. All other workspaces live at
    ``workspaces/{slug}/specs/``.
    """
    if workspace_id == "coherence-network":
        return repo_root / "specs"
    return repo_root / "workspaces" / workspace_id / "specs"


def _rel_prefix_for_workspace(workspace_id: str) -> str:
    """Return the repo-relative path prefix for this workspace's specs."""
    if workspace_id == "coherence-network":
        return "specs/"
    return f"workspaces/{workspace_id}/specs/"


def _changed_spec_files(repo_root: Path, base: str, head: str, workspace_id: str = "coherence-network") -> list[Path]:
    cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", base, head]
    output = subprocess.check_output(cmd, cwd=str(repo_root), text=True)
    rows = [line.strip() for line in output.splitlines() if line.strip()]
    prefix = _rel_prefix_for_workspace(workspace_id)
    spec_paths = []
    for rel in rows:
        if not rel.startswith(prefix) or not rel.endswith(".md"):
            continue
        name = Path(rel).name.lower()
        if name == "template.md":
            continue
        if "backlog" in name:
            continue
        spec_paths.append(repo_root / rel)
    return sorted(spec_paths)


def _validate_many(paths: Iterable[Path]) -> int:
    had_error = False
    for path in paths:
        if not path.is_file():
            print(f"ERROR: spec file does not exist: {path}")
            had_error = True
            continue
        errors = validate_spec(path)
        if errors:
            print(f"ERROR: spec quality validation failed for {path}")
            for error in errors:
                print(f"- {error}")
            had_error = True
            continue
        print(f"OK: spec quality validation passed for {path}")
    return 1 if had_error else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate spec quality contract for changed/new specs.")
    parser.add_argument("--file", action="append", default=[], help="Specific spec file to validate (repeatable).")
    parser.add_argument("--base", default="", help="Base git ref for changed spec detection.")
    parser.add_argument("--head", default="HEAD", help="Head git ref for changed spec detection.")
    parser.add_argument(
        "--require-changed-spec",
        action="store_true",
        help="Fail when no changed specs are detected in the git range.",
    )
    parser.add_argument(
        "--workspace",
        default="coherence-network",
        help=(
            "Workspace to validate specs for. Default 'coherence-network' uses "
            "the legacy repo-root specs/ directory. Any other workspace looks at "
            "workspaces/{slug}/specs/."
        ),
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    workspace_id = args.workspace or "coherence-network"
    targets: list[Path] = []

    if args.file:
        targets = [Path(p).resolve() for p in args.file]
    elif args.base:
        try:
            targets = _changed_spec_files(
                repo_root=repo_root, base=args.base, head=args.head, workspace_id=workspace_id,
            )
        except subprocess.CalledProcessError as exc:
            print(f"ERROR: failed to compute changed specs for range {args.base}..{args.head}: {exc}")
            return 1
        if not targets:
            if args.require_changed_spec:
                print("ERROR: no changed spec files found in git range")
                return 1
            print(f"OK: no changed feature spec files detected in git range (workspace={workspace_id})")
            return 0
    else:
        specs_dir = _specs_dir_for_workspace(repo_root, workspace_id)
        if not specs_dir.is_dir():
            print(f"ERROR: specs dir does not exist for workspace '{workspace_id}': {specs_dir}")
            return 1
        default_specs = specs_dir.glob("*.md")
        targets = [
            path
            for path in sorted(default_specs)
            if path.name.lower() != "template.md" and "backlog" not in path.name.lower()
        ]

    return _validate_many(targets)


if __name__ == "__main__":
    raise SystemExit(main())
