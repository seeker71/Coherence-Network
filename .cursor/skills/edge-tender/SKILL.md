---
name: edge-tender
description: Senses the edge between spec scope and outside. Names where the body ends. Use when verifying work, before merge, or when asked to check spec compliance.
---

# Edge-Tender Sensing

## Quick Start

1. **Read the spec** — find "Files to Create/Modify"
2. **List actual changes** — which files were modified or created?
3. **Match** — each modified file lives inside the spec's edge, or names a finding
4. **Report** — PASS or FAIL with each finding

## Sensing Checklist

- [ ] Files the spec calls for
- [ ] Files actually modified or created
- [ ] Name each file modified that lives outside the spec's edge

## Output Format

**PASS**: All changes inside the spec's edge.

**FAIL**: List each finding and provide patch-ready guidance so a follow-up impl/heal can mend without starting from scratch. Use this structure:

- **VERIFICATION_RESULT**: `FAIL`
- **FILES_TO_CHANGE**: list of paths that need mending (from spec's Files to Create/Modify or findings)
- **PATCH_GUIDANCE**: actionable instructions or minimal diff (file, location, suggested change) for targeted edits
- Optional: **SPEC_VERIFICATION_IMPROVEMENT**: when the spec's Verification section is ambiguous, suggest concrete improvement (exact command or steps)

Example FAIL block:
```
VERIFICATION_RESULT: FAIL
FILES_TO_CHANGE: api/app/routers/foo.py, api/app/services/foo_service.py
PATCH_GUIDANCE: In foo.py line 42, return 404 when id is missing. In foo_service.py, add null check before calling bar().
```

Suggest: revert the out-of-edge change, or expand the spec to include it. Escalate to `needs_decision` when human judgment is the right next breath.

## Scope

- Read-only craft. You sense and name; the shaper mends.
- Spec template: `specs/TEMPLATE.md` — "Files to Create/Modify" defines the spec's edge.
