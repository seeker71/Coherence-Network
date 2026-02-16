# Spec Quality Gate

Purpose: prevent low-quality specs from reaching implementation, where they create manual follow-up fix requests.

## Core Rule

Before implementation begins, changed feature specs must pass:

```bash
python3 scripts/validate_spec_quality.py --base <base_sha> --head <head_sha>
```

If a spec is being authored directly:

```bash
python3 scripts/validate_spec_quality.py --file specs/<spec-file>.md
```

## What The Gate Enforces

- Required sections exist:
  - `Purpose`
  - `Requirements`
  - `Files to Create/Modify`
  - `Acceptance Tests`
  - `Verification`
  - `Out of Scope`
  - `Risks and Assumptions` (or equivalent)
  - `Known Gaps and Follow-up Tasks` (or equivalent)
- Requirements include at least 3 checklist items.
- Acceptance section references tests or explicit manual validation.
- Verification includes executable commands (`pytest`, `npm run`, `curl`, etc.).
- Gaps section is explicit: either `None` or linked follow-up task/issue references.
- Unresolved template placeholders are rejected.

## Why This Closes The Gap

- Forces unknowns and assumptions into the spec before coding.
- Forces explicit verification commands before merge work starts.
- Forces a written gap/follow-up record so implementation drift does not get lost.

## Integration Points

- CI:
  - `.github/workflows/test.yml`
  - `.github/workflows/thread-gates.yml`
- Local process:
  - `docs/CODEX-THREAD-PROCESS.md`
  - `AGENTS.md`
- Spec authoring source:
  - `specs/TEMPLATE.md`

## Fast Failure Policy

If this gate fails:

1. Update the spec first.
2. Re-run `validate_spec_quality.py`.
3. Then proceed to impl/test/review.
