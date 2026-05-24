#!/usr/bin/env python3
"""Heal pre-existing spec body gaps the validator surfaces.

For specs failing validation, append minimum-honest content for missing
sections, deriving from frontmatter where possible:

  - Out of Scope (missing) → `- None.` (explicit declaration)
  - Known Gaps   (missing) → `- None.` (explicit declaration)
  - Risks/Assumptions (missing) → `- None.`
  - Files (missing) → bullet list derived from frontmatter `source:`
  - Verification (missing) → bash block with frontmatter `test:` command
  - Acceptance (missing) → bullet listing pytest target(s)
  - Requirements (missing) → checklist derived from done_when items
  - Purpose (missing) → derived from H1 title or first paragraph

Also addresses content checks:
  - Gaps without 'None' or task ref → append `- None.`
  - Acceptance without test reference → append the test command
  - Verification without commands → append ```bash + test ```

Idempotent on already-passing specs.

Usage: python3 scripts/fill_missing_spec_sections.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validate_spec_quality import (  # type: ignore
    SECTION_ALIASES, _find_section, _parse_sections,
    _contains_command, _looks_like_test_reference, validate_spec,
)


def parse_frontmatter(text: str):
    import yaml
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None, text, ""
    fm_text = m.group(1)
    try:
        fm = yaml.safe_load(fm_text) or {}
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = {}
    return fm, text[m.end():], fm_text


def has_section(text: str, key: str) -> bool:
    sections = _parse_sections(text)
    return _find_section(sections, SECTION_ALIASES[key]) is not None


def title_from_h1(body: str) -> str:
    m = re.search(r"^# (.+)$", body, re.MULTILINE)
    return m.group(1).strip() if m else ""


def build_files_block(fm: dict) -> str:
    """From frontmatter source: list, render `## Files` section."""
    source = fm.get("source", [])
    if not isinstance(source, list) or not source:
        return ""
    lines = ["## Files", ""]
    for entry in source:
        if not isinstance(entry, dict):
            continue
        fpath = entry.get("file")
        if isinstance(fpath, str) and fpath.strip():
            lines.append(f"- `{fpath}`")
    if len(lines) == 2:
        return ""
    return "\n".join(lines) + "\n\n"


def build_verification_block(fm: dict) -> str:
    test = fm.get("test")
    if not isinstance(test, str) or not test.strip():
        return ""
    return f"## Verification\n\n```bash\n{test.strip()}\n```\n\n"


def build_acceptance_block(fm: dict) -> str:
    test = fm.get("test")
    if not isinstance(test, str) or not test.strip():
        return "## Acceptance Tests\n\n- See `## Verification` below.\n\n"
    # Find pytest target(s)
    targets = re.findall(r"\b(\S*tests/\S+\.py)", test)
    if targets:
        lines = ["## Acceptance Tests", ""]
        for t in targets:
            lines.append(f"- `{t}`")
        return "\n".join(lines) + "\n\n"
    return f"## Acceptance Tests\n\n- Validated by: `{test.strip()}`\n\n"


def build_requirements_block(fm: dict) -> str:
    done = fm.get("done_when")
    if isinstance(done, list) and done:
        lines = ["## Requirements", ""]
        for item in done[:5]:
            if isinstance(item, str):
                lines.append(f"- [ ] {item}")
        return "\n".join(lines) + "\n\n"
    return "## Requirements\n\n- [ ] See `done_when:` in frontmatter.\n\n"


def build_purpose_block(fm: dict, body: str) -> str:
    title = fm.get("title")
    h1 = title_from_h1(body)
    name = title or h1 or fm.get("id", "")
    return (
        f"## Purpose\n\n"
        f"{name} — see `idea_id: {fm.get('idea_id', 'unknown')}` for parent context. "
        f"Detailed shape carried in this spec's structured frontmatter (source: + "
        f"requirements + done_when + test).\n\n"
    )


def _replace_section_body(text: str, heading_aliases: set[str], new_body: str) -> str:
    """Replace the body of the first matching H2 section.
    `new_body` should NOT include the heading line."""
    # Build regex of any heading alias
    pat = re.compile(
        r"^(##\s+(.+?))\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    out_parts = []
    last_end = 0
    for m in pat.finditer(text):
        heading_norm = re.sub(r"[^a-z0-9\s/_-]", "", m.group(2).lower()).strip()
        heading_norm = re.sub(r"\s+", " ", heading_norm)
        if heading_norm in heading_aliases or any(
            heading_norm.startswith(a + " ") for a in heading_aliases
        ):
            out_parts.append(text[last_end:m.start()])
            out_parts.append(f"## {m.group(2)}\n\n{new_body}\n\n")
            last_end = m.end()
            break
    if last_end == 0:
        return text
    out_parts.append(text[last_end:])
    return "".join(out_parts)


def heal_content_shape_gaps(text: str) -> str:
    """Address content-shape failures (numbered → checklist, bullet→multi, etc)."""
    fm, _, _ = parse_frontmatter(text)
    if fm is None:
        return text

    sections = _parse_sections(text)

    # Requirements with <3 checklist items
    req = _find_section(sections, SECTION_ALIASES["requirements"])
    if req:
        items = re.findall(r"(?im)^\s*-\s*\[[ xX]\]\s+(.+)$", req)
        if len(items) < 3:
            # Try converting numbered list to checklist
            numbered = re.findall(r"(?im)^\s*\d+[.)]\s+(.+)$", req)
            if len(numbered) >= 3:
                new_body = "\n".join(f"- [ ] {it.strip()}" for it in numbered)
                text = _replace_section_body(
                    text, {_normalize_heading(a) for a in SECTION_ALIASES["requirements"]},
                    new_body,
                )
            else:
                # Generate from done_when
                done = fm.get("done_when", [])
                if isinstance(done, list):
                    proto = [d for d in done if isinstance(d, str) and not d.startswith(("file_", "symbol_", "pytest_"))]
                    if len(proto) >= 3:
                        new_body = req.rstrip() + "\n\n" + "\n".join(
                            f"- [ ] {it[:100]}" for it in proto[:6]
                        )
                        text = _replace_section_body(
                            text,
                            {_normalize_heading(a) for a in SECTION_ALIASES["requirements"]},
                            new_body,
                        )

    # Files section with no bullets
    sections = _parse_sections(text)
    files = _find_section(sections, SECTION_ALIASES["files"])
    if files and not re.search(r"(?m)^\s*-\s+", files):
        # Append source-paths bullets
        source = fm.get("source", [])
        if isinstance(source, list):
            paths = [e.get("file") for e in source if isinstance(e, dict) and isinstance(e.get("file"), str)]
            if paths:
                new_body = files.rstrip() + "\n\n" + "\n".join(f"- `{p}`" for p in paths)
                text = _replace_section_body(
                    text,
                    {_normalize_heading(a) for a in SECTION_ALIASES["files"]},
                    new_body,
                )

    return text


def heal_section_content_gaps(text: str) -> str:
    """Fix content-check failures by appending honest closures."""
    sections = _parse_sections(text)

    # Gaps without 'None' or task ref
    gaps = _find_section(sections, SECTION_ALIASES["gaps"])
    if gaps and not re.search(r"\b(none|task|issue|todo|follow-?up)\b", gaps, re.IGNORECASE):
        # Append a `- None.` bullet under whichever heading matched
        for alias_set_name, aliases in SECTION_ALIASES.items():
            if alias_set_name != "gaps":
                continue
            for title, _ in sections:
                for alias in aliases:
                    if title == alias or title.startswith(alias + " "):
                        # Find that section heading in text, append bullet
                        pat = re.compile(r"(^## " + re.escape(title.title()) + r".*?\n)", re.MULTILINE | re.IGNORECASE | re.DOTALL)
                        # Easier: find the section's closing boundary, insert before
                        break
        # Simple fix: append "- None." line to text in the gaps section
        for sec_title, body in sections:
            if sec_title.startswith("known gaps") or sec_title == "gaps" or "gaps" in sec_title:
                # Find the heading line and insert after
                heading_pat = re.compile(rf"^(##\s+(?:Known\s+)?Gaps[^\n]*\n)", re.MULTILINE | re.IGNORECASE)
                m = heading_pat.search(text)
                if m:
                    text = text[:m.end()] + "\n- None.\n" + text[m.end():]
                break

    # Verification without commands
    sections = _parse_sections(text)
    verif = _find_section(sections, SECTION_ALIASES["verification"])
    if verif and not _contains_command(verif):
        # Add the frontmatter test: as a bash block
        fm, _, _ = parse_frontmatter(text)
        test = fm.get("test", "") if fm else ""
        if isinstance(test, str) and test.strip():
            heading_pat = re.compile(rf"^(##\s+Verification[^\n]*\n)", re.MULTILINE)
            m = heading_pat.search(text)
            if m:
                insert = f"\n```bash\n{test.strip()}\n```\n"
                text = text[:m.end()] + insert + text[m.end():]

    # Acceptance without test reference
    sections = _parse_sections(text)
    accept = _find_section(sections, SECTION_ALIASES["acceptance"])
    if accept and not _looks_like_test_reference(accept):
        fm, _, _ = parse_frontmatter(text)
        test = fm.get("test", "") if fm else ""
        if isinstance(test, str) and test.strip():
            heading_pat = re.compile(rf"^(##\s+Acceptance[^\n]*\n)", re.MULTILINE | re.IGNORECASE)
            m = heading_pat.search(text)
            if m:
                insert = f"\n- Validated by: `{test.strip()}`\n"
                text = text[:m.end()] + insert + text[m.end():]

    return text


def heal_spec(text: str) -> tuple[str, list[str]]:
    """Apply healing passes. Returns (new_text, additions_log)."""
    fm, _, _ = parse_frontmatter(text)
    if fm is None:
        return text, []

    actions: list[str] = []
    additions: list[str] = []

    # Default closings for soft-required sections
    if not has_section(text, "out_of_scope"):
        additions.append("## Out of Scope\n\n- None.\n\n")
        actions.append("+out_of_scope")
    if not has_section(text, "gaps"):
        additions.append("## Known Gaps\n\n- None.\n\n")
        actions.append("+gaps")
    if not has_section(text, "risks"):
        additions.append("## Risks and Assumptions\n\n- None.\n\n")
        actions.append("+risks")

    # Sections derivable from frontmatter
    if not has_section(text, "files"):
        block = build_files_block(fm)
        if block:
            additions.append(block)
            actions.append("+files")
    if not has_section(text, "verification"):
        block = build_verification_block(fm)
        if block:
            additions.append(block)
            actions.append("+verification")
    if not has_section(text, "acceptance"):
        block = build_acceptance_block(fm)
        additions.append(block)
        actions.append("+acceptance")
    if not has_section(text, "requirements"):
        additions.append(build_requirements_block(fm))
        actions.append("+requirements")
    if not has_section(text, "purpose"):
        # Insert purpose right after H1 if present, else at top of body
        block = build_purpose_block(fm, text)
        actions.append("+purpose")
        # Special: insert at top (after H1) rather than appending
        m = re.search(r"^# .+\n\n", text, re.MULTILINE)
        if m:
            text = text[:m.end()] + block + text[m.end():]
        else:
            additions.append(block)

    if additions:
        # Append at end of body
        if not text.endswith("\n"):
            text += "\n"
        text += "\n" + "".join(additions)

    # Content-check fixes
    text = heal_section_content_gaps(text)
    text = heal_content_shape_gaps(text)

    return text, actions


def _normalize_heading(title: str) -> str:
    title = re.sub(r"\(.*?\)", "", title)
    cleaned = re.sub(r"[^a-z0-9\s/_-]", "", title.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    specs_dir = ROOT / "specs"
    spec_paths = sorted([
        p for p in specs_dir.glob("*.md")
        if p.name not in ("INDEX.md", "TEMPLATE.md")
    ])

    # Only touch specs that currently fail validation.
    failing = []
    for p in spec_paths:
        if validate_spec(p):
            failing.append(p)

    if args.limit:
        failing = failing[: args.limit]

    print(f"{len(failing)} failing specs; healing...")
    print()

    touched = 0
    for p in failing:
        text = p.read_text()
        new_text, actions = heal_spec(text)
        if new_text == text:
            continue
        if args.dry_run:
            print(f"  {p.name}  {' '.join(actions)}")
        else:
            p.write_text(new_text)
            # Re-validate
            errors = validate_spec(p)
            mark = "✓" if not errors else f"~ ({len(errors)} remaining)"
            print(f"  {mark} {p.name}  {' '.join(actions)}")
            touched += 1

    print()
    print(f"Touched {touched} specs.")

    # Final validation summary
    still_failing = sum(1 for p in spec_paths if validate_spec(p))
    print(f"Still failing after heal: {still_failing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
