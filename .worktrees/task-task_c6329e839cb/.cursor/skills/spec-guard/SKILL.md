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

**FAIL**: List each violation and provide patch-ready guidance so a follow-up impl/heal can fix without starting from scratch. Use this structure:

- **VERIFICATION_RESULT**: `FAIL`
- **FILES_TO_CHANGE**: list of paths that need changes (from spec's Files to Create/Modify or violations)
- **PATCH_GUIDANCE**: actionable instructions or minimal diff (file, location, suggested change) for targeted edits
- Optional: **SPEC_VERIFICATION_IMPROVEMENT**: if the spec's Verification section is wrong or ambiguous, suggest concrete improvement (exact command or steps)

Example FAIL block:
```
VERIFICATION_RESULT: FAIL
FILES_TO_CHANGE: api/app/routers/foo.py, api/app/services/foo_service.py
PATCH_GUIDANCE: In foo.py line 42, return 404 when id not found. In foo_service.py, add null check before calling bar().
```

Recommend: revert out-of-scope changes. Escalate to `needs_decision` only when human judgment required.

## Constraints

- Read-only. Do not fix; validate and report.
- Spec template: `specs/TEMPLATE.md` — "Files to Create/Modify" defines the allowed set.
