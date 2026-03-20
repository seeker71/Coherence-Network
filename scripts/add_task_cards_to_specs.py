#!/usr/bin/env python3
"""Add Task Card and Research Inputs sections to spec files that don't have them.

Reads each .md file in specs/, and for specs missing:
- "## Task Card" — inserts one after Requirements (or Purpose)
- "## Research Inputs" — inserts one before Task Card
- "### Input Validation" — appends to API Contract section if present

Skips specs 112-119 (gold standard) and non-numbered files.
"""

import os
import re
import sys
from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parent.parent / "specs"

# Spec numbers to skip (gold standard)
SKIP_RANGE = range(112, 120)


def extract_spec_number(filename: str) -> int | None:
    """Extract the leading spec number from a filename like '001-health-check.md'."""
    m = re.match(r"^(\d+)-", filename)
    if m:
        return int(m.group(1))
    return None


def find_section(lines: list[str], heading: str) -> int | None:
    """Find the line index of a ## heading. Returns None if not found."""
    pattern = re.compile(r"^##\s+" + re.escape(heading.lstrip("# ").strip()), re.IGNORECASE)
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            return i
    return None


def find_section_end(lines: list[str], start: int) -> int:
    """Find where a section ends (next ## heading or EOF)."""
    for i in range(start + 1, len(lines)):
        if re.match(r"^##\s+", lines[i].strip()):
            return i
    return len(lines)


def extract_purpose_first_sentence(lines: list[str]) -> str:
    """Extract the first sentence from the Purpose section."""
    idx = find_section(lines, "Purpose")
    if idx is None:
        return "Implement the functionality described in this spec"
    text_lines = []
    for i in range(idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("## "):
            break
        if stripped:
            text_lines.append(stripped)
    text = " ".join(text_lines)
    # First sentence
    m = re.match(r"([^.!?]+[.!?])", text)
    if m:
        return m.group(1).strip()
    return text[:200].strip() if text else "Implement the functionality described in this spec"


def extract_files_allowed(lines: list[str]) -> list[str]:
    """Extract file paths from 'Files to Create/Modify' section."""
    idx = find_section(lines, "Files to Create/Modify")
    if idx is None:
        return ["# TBD — determine from implementation"]
    files = []
    for i in range(idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("## "):
            break
        # Match lines like "- `api/app/routers/health.py` — description"
        m = re.match(r"^[-*]\s+`([^`]+)`", stripped)
        if m:
            files.append(m.group(1))
    return files if files else ["# TBD — determine from implementation"]


def extract_done_when(lines: list[str]) -> list[str]:
    """Extract done_when items from Requirements checkboxes."""
    idx = find_section(lines, "Requirements")
    if idx is None:
        idx = find_section(lines, "Acceptance Criteria")
    if idx is None:
        return ["All requirements implemented and tests pass"]
    items = []
    for i in range(idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("## "):
            break
        # Match checkbox lines: - [x] or - [ ] or numbered items
        m = re.match(r"^[-*]\s+\[[ x]\]\s+(.+)", stripped)
        if m:
            text = m.group(1).strip()
            # Clean up markdown bold
            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
            # Truncate long items
            if len(text) > 120:
                text = text[:117] + "..."
            items.append(text)
        elif re.match(r"^\d+\.\s+", stripped):
            text = re.sub(r"^\d+\.\s+", "", stripped).strip()
            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
            if len(text) > 120:
                text = text[:117] + "..."
            items.append(text)
    # Limit to 5
    return items[:5] if items else ["All requirements implemented and tests pass"]


def extract_test_command(lines: list[str], filename: str) -> str:
    """Infer the test command from the spec."""
    # Look for existing verification commands
    idx = find_section(lines, "Verification")
    if idx is not None:
        for i in range(idx + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped.startswith("## "):
                break
            if "pytest" in stripped or "npm" in stripped:
                return stripped
    # Infer from files
    files = extract_files_allowed(lines)
    for f in files:
        if "tests/" in f:
            return f"cd api && python -m pytest {f} -q"
    # Default
    return "cd api && python -m pytest tests/ -q"


def extract_referenced_specs(lines: list[str]) -> list[str]:
    """Find spec numbers referenced in the file."""
    text = "\n".join(lines)
    refs = set()
    # Match patterns like [009-api-error-handling.md], spec 009, etc.
    for m in re.finditer(r"\b(\d{3})-\w+", text):
        refs.add(m.group(1))
    return sorted(refs)


def has_section(lines: list[str], heading: str) -> bool:
    """Check if a section heading exists."""
    return find_section(lines, heading) is not None


def has_subsection(lines: list[str], parent_heading: str, sub_heading: str) -> bool:
    """Check if a subsection exists within a parent section."""
    parent_idx = find_section(lines, parent_heading)
    if parent_idx is None:
        return False
    parent_end = find_section_end(lines, parent_idx)
    pattern = re.compile(r"^###\s+" + re.escape(sub_heading.lstrip("# ").strip()), re.IGNORECASE)
    for i in range(parent_idx + 1, parent_end):
        if pattern.match(lines[i].strip()):
            return True
    return False


def build_task_card(lines: list[str], filename: str) -> str:
    """Build the Task Card section content."""
    goal = extract_purpose_first_sentence(lines)
    files = extract_files_allowed(lines)
    done_when = extract_done_when(lines)
    test_cmd = extract_test_command(lines, filename)

    files_yaml = "\n".join(f"  - {f}" for f in files)
    done_yaml = "\n".join(f"  - {item}" for item in done_when)

    return f"""## Task Card

```yaml
goal: {goal}
files_allowed:
{files_yaml}
done_when:
{done_yaml}
commands:
  - {test_cmd}
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```
"""


def build_research_inputs(lines: list[str], filename: str) -> str:
    """Build the Research Inputs section content."""
    refs = extract_referenced_specs(lines)
    # Remove self-reference
    spec_num = extract_spec_number(filename)
    if spec_num is not None:
        own_prefix = f"{spec_num:03d}"
        refs = [r for r in refs if r != own_prefix]

    related = ", ".join(refs) if refs else "none"
    return f"""## Research Inputs

- Codebase analysis of existing implementation
- Related specs: {related}
"""


INPUT_VALIDATION_BLOCK = """### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)
"""


def process_spec(filepath: Path) -> dict:
    """Process a single spec file. Returns a summary dict."""
    filename = filepath.name
    spec_num = extract_spec_number(filename)

    result = {"file": filename, "changes": [], "skipped": False}

    if spec_num is None:
        result["skipped"] = True
        result["reason"] = "no spec number"
        return result

    if spec_num in SKIP_RANGE:
        result["skipped"] = True
        result["reason"] = "gold standard (112-119)"
        return result

    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    needs_task_card = not has_section(lines, "Task Card")
    needs_research = not has_section(lines, "Research Inputs")
    needs_input_validation = (
        has_section(lines, "API Contract")
        and not has_subsection(lines, "API Contract", "Input Validation")
    )

    if not needs_task_card and not needs_research and not needs_input_validation:
        result["changes"].append("already complete")
        return result

    # Build new content by inserting sections
    new_lines = list(lines)

    # 1. Add Input Validation to API Contract section
    if needs_input_validation:
        api_idx = find_section(new_lines, "API Contract")
        if api_idx is not None:
            api_end = find_section_end(new_lines, api_idx)
            # Insert before the end of the API Contract section
            insert_block = "\n" + INPUT_VALIDATION_BLOCK
            new_lines.insert(api_end, insert_block)
            result["changes"].append("added Input Validation")

    # 2. Determine insertion point for Research Inputs and Task Card
    # Insert after Requirements (or Purpose if no Requirements)
    insert_after = find_section(new_lines, "Requirements")
    if insert_after is None:
        insert_after = find_section(new_lines, "Acceptance Criteria")
    if insert_after is None:
        insert_after = find_section(new_lines, "Purpose")
    if insert_after is None:
        # Fallback: after first heading
        for i, line in enumerate(new_lines):
            if line.strip().startswith("# "):
                insert_after = i
                break
    if insert_after is None:
        insert_after = 0

    insert_point = find_section_end(new_lines, insert_after)

    blocks_to_insert = []

    if needs_research:
        blocks_to_insert.append(build_research_inputs(lines, filename))
        result["changes"].append("added Research Inputs")

    if needs_task_card:
        blocks_to_insert.append(build_task_card(lines, filename))
        result["changes"].append("added Task Card")

    if blocks_to_insert:
        insert_text = "\n" + "\n".join(blocks_to_insert)
        new_lines.insert(insert_point, insert_text)

    new_content = "\n".join(new_lines)
    # Clean up excessive blank lines (3+ -> 2)
    new_content = re.sub(r"\n{4,}", "\n\n\n", new_content)

    filepath.write_text(new_content, encoding="utf-8")
    return result


def main():
    specs = sorted(SPECS_DIR.glob("*.md"))
    print(f"Found {len(specs)} spec files in {SPECS_DIR}\n")

    results = []
    modified = 0
    skipped = 0

    for spec in specs:
        if spec.name == "TEMPLATE.md":
            continue
        r = process_spec(spec)
        results.append(r)
        if r["skipped"]:
            skipped += 1
        elif r["changes"] and r["changes"] != ["already complete"]:
            modified += 1

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total specs processed: {len(results)}")
    print(f"Modified:              {modified}")
    print(f"Skipped (gold std):    {skipped}")
    print(f"Already complete:      {len(results) - modified - skipped}")
    print()

    for r in results:
        if r["skipped"]:
            continue
        changes = r["changes"]
        if changes and changes != ["already complete"]:
            print(f"  {r['file']}: {', '.join(changes)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
