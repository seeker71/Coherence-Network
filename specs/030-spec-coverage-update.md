# Spec: Update docs/SPEC-COVERAGE.md for specs 007, 008, and new specs

## Purpose

Keep the spec→implementation→test mapping accurate and complete. This spec defines the one-time (or periodic) documentation task: ensure `docs/SPEC-COVERAGE.md` includes summary rows and, where applicable, detail sections for specs 007, 008, and every other feature spec in `specs/`, so agents and humans have a single source of truth for coverage.

## Requirements

- [ ] **007 and 008** — `docs/SPEC-COVERAGE.md` has a Status Summary row and a detailed section for each:
  - **007** — Per [007-sprint-0-landing.md](007-sprint-0-landing.md): root landing, /docs reachability; requirements mapped to implementation and tests.
  - **008** — Per [sprint0-graph-foundation-indexer-api.md](sprint0-graph-foundation-indexer-api.md): GraphStore, indexer, projects/search API, 5K index; requirements mapped to implementation and tests (including via 019).
- [ ] **New specs** — Every other spec in `specs/` that describes a feature (numbered specs and any additional feature specs) has at least a **Status Summary** row. Specs that have implementation and tests get a **detail section** (Requirement | Implementation | Test) following the existing SPEC-COVERAGE pattern.
- [ ] **Format** — Conventions follow existing SPEC-COVERAGE: Status Summary table (Spec | Present | Spec'd | Tested | Notes), optional detail sections with (Requirement | Implementation | Test), Files and See also as used elsewhere. Use [specs/TEMPLATE.md](TEMPLATE.md) only as structural reference for *this* spec document; SPEC-COVERAGE.md keeps its current doc structure.
- [ ] **Exclusions** — TEMPLATE.md, test/backlog-only files (e.g. test-backlog-cursor.md), and duplicate/alias filenames (e.g. 007-meta-pipeline-backlog vs 007-sprint-0-landing) are handled consistently: one canonical entry per logical spec (e.g. one row for "007 Sprint 0 Landing" from 007-sprint-0-landing.md).

## Files to Create/Modify

- `docs/SPEC-COVERAGE.md` — Add or expand Status Summary rows and detail sections for 007, 008, and any spec missing from the document.

## Acceptance Tests

- **Summary completeness** — Status Summary table includes 007, 008, and every numbered/feature spec present in `specs/` (excluding TEMPLATE and test-backlog-only files).
- **007 detail** — Section "Spec 007: Sprint 0 Landing" lists each requirement from 007-sprint-0-landing.md with corresponding Implementation and Test (or note).
- **008 detail** — Section "Spec 008: Sprint 1 Graph Foundation" lists each requirement from sprint0-graph-foundation-indexer-api.md with corresponding Implementation and Test (or note); may reference 019 where implemented via GraphStore spec.
- **New spec rows** — Any spec in `specs/` that is not yet in the Status Summary gets an additive row (no removal of existing rows to satisfy this spec).

## Out of Scope

- Changing the behavior of `api/scripts/update_spec_coverage.py` (see [027-auto-update-framework.md](027-auto-update-framework.md)).
- Adding or changing implementation or tests for specs 007 or 008; this spec is documentation-only.
- Deciding which specs are "feature" vs "meta" (use existing SPEC-COVERAGE and spec filenames; when in doubt, add a row).

## See also

- [006-overnight-backlog.md](006-overnight-backlog.md) — Item 10: Update docs/SPEC-COVERAGE.md for specs 007, 008, and any new specs
- [027-auto-update-framework.md](027-auto-update-framework.md) — Script that additively updates SPEC-COVERAGE
- [specs/TEMPLATE.md](TEMPLATE.md) — Spec document format (for this spec, not for SPEC-COVERAGE layout)

## Decision Gates

- None. Documentation-only change.
