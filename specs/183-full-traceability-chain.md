---
idea_id: full-traceability-chain
spec_id: 183-full-traceability-chain
status: approved
---

# Spec 183: Full Traceability Chain

**idea_id**: `full-traceability-chain`
**Status**: Approved
**Phase**: Implementation

## Summary

Every source file and public function in the Coherence Network codebase must be
traceable back to a spec, and every spec must be traceable back to an idea.
Current coverage is ~17% — this spec drives it to >80% through a two-phase approach:
automated backfill (Phase 1) and enforced conventions (Phase 2).

## Motivation

Traceability is the backbone of value attribution. If we cannot answer "what idea
spawned this function?", we cannot credit contributors, measure idea ROI, or audit
system changes. Without the full chain, the Coherence Network's value-lineage story
is broken at the code level.

## Goals

1. Every spec file has `idea_id` in its frontmatter.
2. Every router/service Python file has a `# spec: <id>` comment in the first 5 lines.
3. Every public function in routers/services is decorated with `@spec_traced`.
4. DB `specs` table rows have `idea_id` populated.
5. A `/api/traceability/report` endpoint shows coverage metrics and gaps.
6. CI rejects new files missing spec comments.

## Phase 1 — Automated Backfill

### 1.1 Spec file backfill (`scripts/backfill_spec_idea_links.py`)
- Scan `specs/*.md` for existing `idea_id:` references in body text.
- If found and frontmatter is missing `idea_id`, inject it.
- Write a CSV report to `data/spec_idea_backfill.csv`.
- Dry-run by default; `--apply` to write changes.

### 1.2 DB spec backfill
- For each row in `specs` where `idea_id IS NULL`, look up the spec file on disk.
- Extract `idea_id` from frontmatter.
- Write back to DB using `UPDATE specs SET idea_id = ? WHERE id = ?`.
- Endpoint: `POST /api/traceability/backfill` triggers the job asynchronously.

### 1.3 Code file spec reference scan (`scripts/check_spec_references.py`)
- Walk `api/app/routers/` and `api/app/services/` for `*.py`.
- Check first 5 lines for `# spec: <id>` pattern.
- Report files missing the comment.
- CI mode: exit 1 if violations found on changed files.

### 1.4 Links table
- In-memory (for now): `{source_file, spec_id, idea_id, function, line}` tuples.
- Exposed at `GET /api/traceability` and `GET /api/traceability/report`.

## Phase 2 — Convention Enforcement

### 2.1 New spec convention
Every new spec MUST include `idea_id` in frontmatter:
```yaml
---
idea_id: <slug>
spec_id: <number>-<slug>
---
```

### 2.2 New file convention
Every new `api/app/routers/*.py` and `api/app/services/*.py` MUST start with:
```python
# spec: <spec-id>
# idea: <idea-slug>
```

### 2.3 CI check
`python3 scripts/check_spec_references.py --changed-only` in CI pipeline.
Exit 1 blocks merge if newly-added files miss the spec comment.

### 2.4 New function convention
Every new public endpoint or service function MUST use `@spec_traced`:
```python
from app.core.tracing import spec_traced

@spec_traced("183-full-traceability-chain", idea_id="full-traceability-chain")
async def my_endpoint(...):
    ...
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/traceability` | All runtime-traced functions |
| GET | `/api/traceability/coverage` | Legacy coverage summary |
| GET | `/api/traceability/report` | Full multi-dimension coverage report |
| GET | `/api/traceability/functions` | Filtered @spec_traced registry |
| GET | `/api/traceability/spec/{spec_id}` | Forward trace: spec → files/functions |
| GET | `/api/traceability/idea/{idea_id}` | Reverse trace: idea → functions |
| GET | `/api/traceability/lineage/{idea_id}` | Full lineage chain |
| POST | `/api/traceability/backfill` | Trigger async backfill job |
| GET | `/api/traceability/backfill/status` | Check backfill job status |

## Data Models

```python
class TraceabilitySummary(BaseModel):
    spec_files_total: int
    spec_files_with_idea_id: int
    spec_files_coverage_pct: float
    db_specs_total: int
    db_specs_with_idea_id: int
    db_specs_coverage_pct: float
    source_files_total: int
    source_files_with_spec_ref: int
    source_files_coverage_pct: float
    functions_traced: int
    functions_total: int
    function_coverage_pct: float
    overall_traceability_pct: float

class TraceabilityGap(BaseModel):
    type: str  # "spec_no_idea" | "file_no_spec" | "function_not_traced"
    spec_file: str | None
    spec_id: str | None
    severity: str  # "high" | "medium" | "low"

class TraceabilityReport(BaseModel):
    summary: TraceabilitySummary
    gaps: list[TraceabilityGap]
    links: list[dict]

class TracedFunction(BaseModel):
    module: str
    function: str
    spec_id: str | None
    idea_id: str | None
    file: str | None
    line: int | None
    description: str | None

class BackfillRequest(BaseModel):
    dry_run: bool = True

class BackfillResponse(BaseModel):
    job_id: str
    status: str
    dry_run: bool
    queued_at: datetime
```

## Verification

- `GET /api/traceability/report` returns `overall_traceability_pct > 30` after Phase 1.
- `python3 scripts/check_spec_references.py` exits 0 after new files have comments.
- `python3 scripts/backfill_spec_idea_links.py --apply` processes > 50 spec files.
- `GET /api/traceability/functions` returns > 50 traced functions.

## Risks and Assumptions

- **Risk**: DB spec table may not have `idea_id` column. Assumed it does; service
  falls back gracefully to `(0, 0)` if the query fails.
- **Risk**: Spec body text idea references may not be machine-readable. The backfill
  extracts the best candidate; manual review needed for low-confidence cases.
- **Assumption**: `app.db.get_db_session` is available; traceability degrades but
  does not error if DB is offline.

## Known Gaps and Follow-up Tasks

- Function-level `@spec_traced` coverage for legacy code (pre-181) — separate PR.
- Web components (`web/app/**/*.tsx`) not yet covered by spec comment convention.
- PR-to-spec linkage (GitHub API) — Phase 3, not in this spec.
