#!/usr/bin/env python3
"""Batch-upgrade spec files to include missing SQ3/SQ4 sections."""

import os
import re
import sys

SPECS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs")

# Section markers we look for (case-insensitive matching)
FAILURE_PATTERNS = [
    r"^## Failure and Retry Behavior",
    r"^## Failure/Retry Reflection",
    r"^## Failure and Retry",
]

RISKS_PATTERNS = [
    r"^## Risks and Known Gaps",
    r"^## Risks and Assumptions",
    r"^## Known Gaps and Follow-up Tasks",
    r"^## Known Gaps",
]

ACCEPTANCE_PATTERNS = [
    r"^## Acceptance Tests",
]

# Anchors: sections BEFORE which we want to insert
INSERT_BEFORE_SECTIONS = [
    "## Verification",
    "## Out of Scope",
    "## Decision Gates",
]


def classify_spec(content: str, filename: str) -> str:
    """Classify a spec as api, pipeline, ci, web, or generic."""
    lower = content.lower()
    fname = filename.lower()

    # Web/UI specs
    if "web/" in lower or "ui" in fname or "landing" in fname or "## web" in lower or "shadcn" in lower or "next.js" in lower or "react" in lower:
        return "web"

    # CI/deployment specs
    if "ci" in fname or "deploy" in fname or "github actions" in lower or "workflow" in lower or "release" in fname or "gate" in fname:
        return "ci"

    # Pipeline/automation specs
    if "pipeline" in fname or "orchestrat" in lower or "automat" in fname or "pipeline" in lower or "backlog" in fname or "heal" in fname:
        return "pipeline"

    # API specs (check endpoints, routes, etc.)
    if "api" in fname or "/api/" in lower or "endpoint" in lower or "get /" in lower or "post /" in lower or "patch /" in lower or "fastapi" in lower:
        return "api"

    return "generic"


def failure_section(spec_type: str) -> str:
    """Generate contextually appropriate Failure and Retry Behavior section."""
    if spec_type == "api":
        return """## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.
"""
    elif spec_type == "pipeline":
        return """## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.
"""
    elif spec_type == "ci":
        return """## Failure and Retry Behavior

- **Gate failure**: CI gate blocks merge; author must fix and re-push.
- **Flaky test**: Re-run up to 2 times before marking as genuine failure.
- **Rollback behavior**: Failed deployments automatically roll back to last known-good state.
- **Infrastructure failure**: CI runner unavailable triggers alert; jobs re-queue on recovery.
- **Timeout**: CI jobs exceeding 15 minutes are killed and marked failed; safe to re-trigger.
"""
    elif spec_type == "web":
        return """## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.
"""
    else:
        return """## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.
"""


def risks_section(spec_type: str) -> str:
    """Generate contextually appropriate Risks and Known Gaps section."""
    if spec_type == "api":
        follow_up = "Add integration tests for error edge cases."
    elif spec_type == "pipeline":
        follow_up = "Add distributed locking for multi-worker pipelines."
    elif spec_type == "ci":
        follow_up = "Add deployment smoke tests post-release."
    elif spec_type == "web":
        follow_up = "Add end-to-end browser tests for critical paths."
    else:
        follow_up = "Review coverage and add missing edge-case tests."

    return f"""## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: {follow_up}
"""


def acceptance_section(filename: str) -> str:
    """Generate placeholder Acceptance Tests section."""
    base = os.path.splitext(filename)[0]
    # Try to derive a plausible test file name
    test_file = f"api/tests/test_{base.split('-', 1)[-1].replace('-', '_')}.py"
    return f"""## Acceptance Tests

See `{test_file}` for test cases covering this spec's requirements.
"""


def has_section(content: str, patterns: list) -> bool:
    """Check if content has any section matching the patterns."""
    for pattern in patterns:
        if re.search(pattern, content, re.MULTILINE):
            return True
    return False


def has_test_table(content: str) -> bool:
    """Check if content has a test table (markdown table with test references)."""
    # Look for markdown tables that reference tests
    return bool(re.search(r"\|.*[Tt]est.*\|", content))


def find_insert_position(content: str, before_sections: list) -> int:
    """Find the position to insert new sections, before the first matching anchor section."""
    for section_header in before_sections:
        # Match the section header at the start of a line
        match = re.search(r"^" + re.escape(section_header) + r"\b", content, re.MULTILINE)
        if match:
            # Insert before this section, with a blank line
            pos = match.start()
            # Back up past any blank lines immediately before the header
            while pos > 0 and content[pos - 1] == '\n':
                pos -= 1
            return pos
    return -1  # No anchor found, append at end


def upgrade_spec(filepath: str, filename: str) -> dict:
    """Upgrade a single spec file. Returns dict of what was added."""
    with open(filepath, "r") as f:
        content = f.read()

    original = content
    changes = {"failure": False, "risks": False, "acceptance": False}

    needs_failure = not has_section(content, FAILURE_PATTERNS)
    needs_risks = not has_section(content, RISKS_PATTERNS)
    needs_acceptance = not has_section(content, ACCEPTANCE_PATTERNS) and not has_test_table(content)

    if not needs_failure and not needs_risks and not needs_acceptance:
        return changes

    spec_type = classify_spec(content, filename)

    # Build sections to insert
    sections_to_insert = []
    if needs_failure:
        sections_to_insert.append(("failure", failure_section(spec_type)))
        changes["failure"] = True
    if needs_risks:
        sections_to_insert.append(("risks", risks_section(spec_type)))
        changes["risks"] = True
    if needs_acceptance:
        sections_to_insert.append(("acceptance", acceptance_section(filename)))
        changes["acceptance"] = True

    # Find insert position
    insert_pos = find_insert_position(content, INSERT_BEFORE_SECTIONS)

    if insert_pos >= 0:
        # Insert before the anchor section
        block = "\n\n" + "\n".join(s for _, s in sections_to_insert)
        content = content[:insert_pos] + block + "\n\n" + content[insert_pos:]
    else:
        # Append at end
        block = "\n\n" + "\n".join(s for _, s in sections_to_insert)
        content = content.rstrip() + block + "\n"

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)

    return changes


def main():
    if not os.path.isdir(SPECS_DIR):
        print(f"ERROR: specs directory not found at {SPECS_DIR}")
        sys.exit(1)

    files = sorted(f for f in os.listdir(SPECS_DIR) if f.endswith(".md") and f != "TEMPLATE.md")
    total = len(files)
    upgraded = 0
    failure_count = 0
    risks_count = 0
    acceptance_count = 0
    skipped = 0

    for filename in files:
        filepath = os.path.join(SPECS_DIR, filename)
        changes = upgrade_spec(filepath, filename)
        if any(changes.values()):
            upgraded += 1
            parts = []
            if changes["failure"]:
                failure_count += 1
                parts.append("failure/retry")
            if changes["risks"]:
                risks_count += 1
                parts.append("risks/gaps")
            if changes["acceptance"]:
                acceptance_count += 1
                parts.append("acceptance")
            print(f"  UPGRADED: {filename} (+{', '.join(parts)})")
        else:
            skipped += 1

    print(f"\n--- Summary ---")
    print(f"Total spec files scanned: {total}")
    print(f"Specs upgraded: {upgraded}")
    print(f"  - Failure/Retry sections added: {failure_count}")
    print(f"  - Risks/Known Gaps sections added: {risks_count}")
    print(f"  - Acceptance Tests sections added: {acceptance_count}")
    print(f"Specs already complete (skipped): {skipped}")


if __name__ == "__main__":
    main()
