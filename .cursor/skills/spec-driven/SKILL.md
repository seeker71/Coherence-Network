---
name: spec-driven
description: Implements features strictly from specs. Reads specs first, modifies only listed files, no scope creep. Use when implementing a feature, working with specs/, or when the user references a spec number.
---

# Spec-Driven Implementation

## Quick Start

1. **Read the spec** — `specs/NNN-feature-name.md` or the spec referenced in the task
2. **Implement only what it says** — no extra features, no adjacent refactors
3. **Modify only listed files** — see "Files to Create/Modify" in the spec
4. **Do not change tests** — fix implementation, not tests

## Constraints

- Only modify files listed in the spec's "Files to Create/Modify" section
- Do not add docs, READMEs, or refactors unless the spec requires them
- If unsure whether a change is in scope, escalate with `needs_decision`
- Follow API Contract and Data Model from the spec exactly

## Spec Format Reference

Specs follow `specs/TEMPLATE.md`:
- Purpose, Requirements, API Contract, Data Model
- Files to Create/Modify (the allowed set)
- Acceptance Tests, Out of Scope, Decision Gates

## When Tests Fail

Fix the implementation. Do NOT modify tests to make them pass.
