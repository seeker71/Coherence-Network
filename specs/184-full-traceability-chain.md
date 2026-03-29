---
idea_id: full-traceability-chain
spec_id: 184-full-traceability-chain
status: approved
---

# Spec 184: Full Traceability Chain

**idea_id**: `full-traceability-chain`
**Status**: Approved

## Summary

Every source file and public function in the Coherence Network codebase must trace
back to a spec, and every spec must trace back to an idea. Current coverage ~17%.
This spec drives it to >80% via automated backfill (Phase 1) and convention
enforcement (Phase 2).

## Goals

1. Every spec file has `idea_id` in its frontmatter.
2. Every router/service Python file has `# spec: <id>` in its first 5 lines.
3. Every public endpoint is decorated with `@spec_traced`.
4. DB `specs` table rows have `idea_id` populated.
5. `/api/traceability/report` shows coverage metrics and gaps.
6. CI check blocks new files without spec comments.

## Phase 1 — Automated Backfill

### 1.1 Spec file backfill (`scripts/backfill_spec_idea_links.py`)
- Scan `specs/*.md` for existing `idea_id:` references.
- If found in body but missing from frontmatter, inject into frontmatter.
- Dry-run default; `--apply` writes changes.

### 1.2 DB spec backfill (via `POST /api/traceability/backfill`)
- For DB rows where `idea_id IS NULL`, look up spec file on disk.
- Extract `idea_id` from frontmatter and update DB.

### 1.3 Code file scan (`scripts/check_spec_references.py`)
- Walk `api/app/routers/` and `api/app/services/` for `*.py`.
- Report files missing `# spec: <id>` in first 5 lines.
- CI mode: exit 1 on violations in changed files.

### 1.4 Links table
- In-memory: `{source_file, spec_id, idea_id, function, line}` tuples.
- Exposed at `GET /api/traceability` and `GET /api/traceability/report`.

## Phase 2 — Convention Enforcement

### 2.1 New spec must have `idea_id` in frontmatter:
```yaml
---
idea_id: <slug>
spec_id: <number>-<slug>
---
```

### 2.2 New router/service file must start with:
```python
# spec: <spec-id>
# idea: <idea-slug>
```

### 2.3 CI check: `python3 scripts/check_spec_references.py --changed-only`

### 2.4 New public functions must use `@spec_traced`:
```python
from app.core.tracing import spec_traced

@spec_traced("184-full-traceability-chain", idea_id="full-traceability-chain")
async def my_endpoint(...):
    ...
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/traceability` | All runtime-traced functions |
| GET | `/api/traceability/coverage` | Coverage summary |
| GET | `/api/traceability/report` | Full multi-dimension report |
| GET | `/api/traceability/functions` | Filtered @spec_traced registry |
| GET | `/api/traceability/spec/{spec_id}` | Forward trace: spec → files/functions |
| GET | `/api/traceability/idea/{idea_id}` | Reverse trace: idea → functions |
| GET | `/api/traceability/lineage/{idea_id}` | Full lineage chain |
| POST | `/api/traceability/backfill` | Trigger async backfill |
| GET | `/api/traceability/backfill/status` | Backfill job status |

## Verification

- `GET /api/traceability/report` returns `overall_traceability_pct > 30` post Phase 1.
- `python3 scripts/check_spec_references.py` exits 0 after applying spec comments.
- `python3 scripts/backfill_spec_idea_links.py --apply` processes > 50 spec files.
- `GET /api/traceability/functions` returns > 50 traced functions.

## Risks and Assumptions

- DB `specs` table assumed to have `idea_id` column; service degrades gracefully if missing.
- Spec body idea references may be ambiguous; manual review for low-confidence cases.
- `app.db.get_db_session` assumed available; traceability degrades but does not error if DB offline.

## Known Gaps and Follow-up Tasks

- Function-level `@spec_traced` coverage for pre-184 legacy code — separate PR.
- Web components (`web/app/**/*.tsx`) not yet covered by spec comment convention.
- PR-to-spec linkage (GitHub API) — Phase 3.
