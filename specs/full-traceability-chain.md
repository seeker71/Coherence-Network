# Full traceability chain

**idea_id**: `full-traceability-chain`

## Purpose

Raise coverage so every implementation file and (where practical) public surface traces to a spec and an idea: markdown specs carry idea metadata, the relational `spec_registry_entries` row carries `idea_id`, and static parser-discovered edges live in `traceability_implementation_links` for reporting and audits.

## Phase 1 (automated)

- Scan `specs/*.md` for idea references; optional frontmatter injection via `POST /api/traceability/backfill`.
- Backfill `idea_id` on `spec_registry_entries` when `content_path` resolves to a spec file containing extractable idea metadata.
- Scan `api/app`, `web/app`, and `cli` sources for `# spec:` / `// spec:` comments; persist edges with `traceability_links_service.replace_all_links`.
- Inspect aggregate coverage with `GET /api/traceability/report` (`persisted_implementation_links` counts stored rows).

## See also

- `specs/181-full-code-traceability.md` — decorator-based function traceability and API details.
