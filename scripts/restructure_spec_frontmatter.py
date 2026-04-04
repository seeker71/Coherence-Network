"""Restructure spec frontmatter: absorb requirements, done_when, test command.

Reads each spec .md file, extracts:
  - Requirements (from ## Requirements section)
  - done_when + test command (from ## Task Card yaml block)
Adds them to YAML frontmatter, keeps body as-is for human reference.

Result: agents read 15-25 lines of frontmatter instead of 170 lines of spec.
"""

import re
import sys
from pathlib import Path


def extract_frontmatter_and_body(text: str) -> tuple[str, str]:
    """Split into raw YAML frontmatter and body."""
    if not text.startswith("---"):
        return "", text
    end = text.index("---", 3)
    fm = text[3:end].strip()
    body = text[end + 3:].strip()
    return fm, body


def extract_requirements(body: str) -> list[str]:
    """Extract requirements from ## Requirements section."""
    # Find the Requirements section
    match = re.search(r'^## Requirements\s*\n(.*?)(?=^## |\Z)', body, re.MULTILINE | re.DOTALL)
    if not match:
        return []

    section = match.group(1).strip()
    reqs = []

    for line in section.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Match: - [x] **R1: Title** — description  OR  - [x] requirement text  OR  - [ ] requirement text
        # Also match: - **R1:** text
        m = re.match(r'^-\s*\[[ x]\]\s*\*\*R\d+:?\s*(.*?)\*\*\s*[-—–]?\s*(.*)', line)
        if m:
            title = m.group(1).strip().rstrip(':')
            desc = m.group(2).strip()
            if desc:
                reqs.append(f"{title}: {desc[:120]}")
            else:
                reqs.append(title[:120])
            continue

        m = re.match(r'^-\s*\[[ x]\]\s*\*\*(.*?)\*\*\s*[-—–]?\s*(.*)', line)
        if m:
            title = m.group(1).strip().rstrip(':')
            desc = m.group(2).strip()
            if desc:
                reqs.append(f"{title}: {desc[:120]}")
            else:
                reqs.append(title[:120])
            continue

        m = re.match(r'^-\s*\[[ x]\]\s*(.*)', line)
        if m:
            req_text = m.group(1).strip()
            if req_text and len(req_text) > 5:
                reqs.append(req_text[:120])
            continue

    return reqs


def extract_task_card(body: str) -> tuple[list[str], str, list[str]]:
    """Extract done_when, test command, and constraints from Task Card yaml block.

    Returns (done_when_list, test_command, constraints_list)
    """
    # Find yaml code block in Task Card section
    match = re.search(r'^## Task Card.*?\n.*?```ya?ml\s*\n(.*?)```', body, re.MULTILINE | re.DOTALL)
    if not match:
        return [], "", []

    yaml_text = match.group(1)

    done_when = []
    test_cmd = ""
    constraints = []

    current_key = None
    for line in yaml_text.split('\n'):
        stripped = line.strip()

        if stripped.startswith('done_when:'):
            current_key = 'done_when'
            continue
        elif stripped.startswith('commands:'):
            current_key = 'commands'
            continue
        elif stripped.startswith('constraints:'):
            current_key = 'constraints'
            continue
        elif stripped.startswith('goal:') or stripped.startswith('files_allowed:'):
            current_key = 'other'
            continue
        elif re.match(r'^[a-z_]+:', stripped) and not stripped.startswith('- '):
            current_key = 'other'
            continue

        if current_key == 'done_when' and stripped.startswith('- '):
            item = stripped[2:].strip()
            if item:
                done_when.append(item[:120])
        elif current_key == 'commands' and stripped.startswith('- '):
            cmd = stripped[2:].strip()
            if cmd and ('pytest' in cmd or 'test' in cmd or 'npm' in cmd):
                test_cmd = cmd
        elif current_key == 'constraints' and stripped.startswith('- '):
            item = stripped[2:].strip()
            if item:
                constraints.append(item[:120])

    return done_when, test_cmd, constraints


def extract_acceptance_criteria(body: str) -> list[str]:
    """For specs without task cards, try Acceptance Criteria or Success Criteria sections."""
    for heading in ['Acceptance Criteria', 'Success Criteria', 'Done When']:
        match = re.search(rf'^## {heading}\s*\n(.*?)(?=^## |\Z)', body, re.MULTILINE | re.DOTALL)
        if match:
            items = []
            for line in match.group(1).strip().split('\n'):
                line = line.strip()
                m = re.match(r'^-\s*\[?[ x]?\]?\s*(.*)', line)
                if m and len(m.group(1).strip()) > 5:
                    items.append(m.group(1).strip()[:120])
            if items:
                return items
    return []


def build_new_frontmatter(old_fm: str, requirements: list[str], done_when: list[str],
                           test_cmd: str, constraints: list[str]) -> str:
    """Add extracted fields to existing frontmatter YAML."""
    lines = old_fm.split('\n')

    # Add requirements if we found any (cap at 10 for frontmatter compactness)
    if requirements:
        lines.append("requirements:")
        for req in requirements[:10]:
            # Escape YAML special chars
            safe = req.replace('"', '\\"')
            lines.append(f'  - "{safe}"')
        if len(requirements) > 10:
            lines.append(f'  # ... {len(requirements) - 10} more in Requirements section below')

    # Add done_when
    if done_when:
        lines.append("done_when:")
        for dw in done_when:
            safe = dw.replace('"', '\\"')
            lines.append(f'  - "{safe}"')

    # Add test command
    if test_cmd:
        safe = test_cmd.replace('"', '\\"')
        lines.append(f'test: "{safe}"')

    # Add constraints if meaningful
    if constraints:
        lines.append("constraints:")
        for c in constraints:
            safe = c.replace('"', '\\"')
            lines.append(f'  - "{safe}"')

    return '\n'.join(lines)


def process_spec(path: Path, dry_run: bool = False) -> dict:
    """Process a single spec file. Returns stats."""
    text = path.read_text()
    fm, body = extract_frontmatter_and_body(text)

    if not fm:
        return {"file": path.name, "skipped": "no frontmatter"}

    # Skip if already has requirements/done_when in frontmatter
    if 'done_when:' in fm or 'requirements:' in fm:
        return {"file": path.name, "skipped": "already restructured"}

    requirements = extract_requirements(body)
    done_when, test_cmd, constraints = extract_task_card(body)

    # If no task card, try acceptance criteria
    if not done_when:
        done_when = extract_acceptance_criteria(body)

    if not requirements and not done_when and not test_cmd:
        return {"file": path.name, "skipped": "no extractable data",
                "has_requirements_section": bool(re.search(r'^## Requirements', body, re.MULTILINE)),
                "has_task_card": bool(re.search(r'^## Task Card', body, re.MULTILINE))}

    new_fm = build_new_frontmatter(fm, requirements, done_when, test_cmd, constraints)
    new_text = f"---\n{new_fm}\n---\n\n{body}\n"

    if not dry_run:
        path.write_text(new_text)

    return {
        "file": path.name,
        "updated": True,
        "requirements": len(requirements),
        "done_when": len(done_when),
        "test_cmd": bool(test_cmd),
        "constraints": len(constraints),
    }


def main():
    dry_run = "--dry-run" in sys.argv
    specs_dir = Path(__file__).resolve().parents[1] / "specs"

    results = []
    for path in sorted(specs_dir.glob("*.md")):
        if path.name in ("INDEX.md", "TEMPLATE.md"):
            continue
        result = process_spec(path, dry_run=dry_run)
        results.append(result)

    # Report
    updated = [r for r in results if r.get("updated")]
    skipped = [r for r in results if r.get("skipped")]

    print(f"\n{'DRY RUN — ' if dry_run else ''}Spec Frontmatter Restructure")
    print(f"{'=' * 50}")
    print(f"Total specs: {len(results)}")
    print(f"Updated: {len(updated)}")
    print(f"Skipped: {len(skipped)}")

    if updated:
        print(f"\nUpdated specs:")
        for r in updated:
            parts = []
            if r["requirements"]: parts.append(f"{r['requirements']} reqs")
            if r["done_when"]: parts.append(f"{r['done_when']} done_when")
            if r["test_cmd"]: parts.append("test")
            if r["constraints"]: parts.append(f"{r['constraints']} constraints")
            print(f"  {r['file']}: {', '.join(parts)}")

    if skipped:
        print(f"\nSkipped specs:")
        for r in skipped:
            print(f"  {r['file']}: {r['skipped']}")


if __name__ == "__main__":
    main()
