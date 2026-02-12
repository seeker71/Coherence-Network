---
name: spec-guard
description: Validates implementation against spec. Flags files modified outside the spec's allowed list. Use when verifying work, before merge, or when asked to check spec compliance.
---

# Spec Guard Validation

## Quick Start

1. **Read the spec** — identify "Files to Create/Modify"
2. **List actual changes** — which files were modified or created?
3. **Compare** — any file changed that is NOT in the spec = scope creep
4. **Report** — PASS or FAIL with violations listed

## Validation Checklist

- [ ] Files the spec says to modify
- [ ] Files actually modified/created
- [ ] Flag any file NOT in the spec

## Output Format

**PASS**: All changes are within spec.

**FAIL**: List each violation:
- `path/to/file.py` — not in spec's Files to Create/Modify

Recommend: revert out-of-scope changes or escalate to `needs_decision`.

## Constraints

- Read-only. Do not fix; validate and report.
- Spec template: `specs/TEMPLATE.md` — "Files to Create/Modify" defines the allowed set.
