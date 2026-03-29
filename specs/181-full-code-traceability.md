# Spec 181: Full Code Traceability — Every File and Function Traces to a Spec and Idea

**idea_id**: `full-code-traceability`
**Status**: Draft
**Created**: 2026-03-28
**Author**: product-manager agent (task_857245cf53038aed)

---

## Purpose

Today, 83% of the codebase is untraceable: you cannot click a function and know *why* it was written, which idea spawned it, or which spec governs it. Traceability is the connective tissue of intentional engineering — without it, dead code silently accumulates, duplicate work goes undetected, and value attribution is impossible. This spec defines a three-phase system to bring traceability from 17% to ≥ 90% across specs, code files, functions, and database entities, without burdening future contributors with manual overhead.

The goal: given any function, file, or spec in the codebase, an agent or human can answer in one query:
- Which idea originated this?
- Which spec governs it?
- Which implementation file delivers it?
- What value was created and who gets attribution?

---

## Background & Current State

| Dimension | Current | Target |
|-----------|---------|--------|
| Spec files with `idea_id` | 26 of 152 (17%) | ≥ 145 of 152 (95%) |
| DB spec rows with `idea_id` set | 0 of 54 (0%) | ≥ 50 of 54 (93%) |
| Source files with spec reference comment | ~0% | ≥ 80% of changed files |
| Function-level annotation | 0% | ≥ 60% of public API functions |
| Spec→implementation links table | Does not exist | Fully built |
| Value lineage chain | Broken | End-to-end: idea→spec→file→function |

Related specs:
- Spec 048: Value Lineage and Payout Attribution
- Spec 049: System Lineage Inventory and Runtime Telemetry
- Spec 054: Commit Provenance Contract Gate
- Spec 056: Commit-Derived Traceability Report
- Spec 089: Endpoint Traceability Coverage

---

## Requirements

### Phase 1 — Automated Backfill (no human effort required)

- [ ] **P1.1** — Write `scripts/backfill_spec_idea_links.py` that:
  - Scans all `specs/*.md` files for any string matching `idea_id:`, `idea:`, `/api/ideas/`, or known idea slugs
  - Extracts the idea reference and writes it into the spec frontmatter as `idea_id`
  - Outputs a CSV report: `spec_file, idea_id_found, confidence (high/low/none), action_taken`
  - Handles the case where no idea reference exists by flagging as `needs_review`

- [ ] **P1.2** — Write `scripts/backfill_db_spec_idea_ids.py` that:
  - Queries all specs rows in PostgreSQL where `idea_id IS NULL`
  - Cross-references spec title/content against idea names and slugs via fuzzy match
  - Updates `idea_id` on matched rows (confidence ≥ 0.85)
  - Outputs audit log: `spec_id, spec_title, matched_idea_id, match_score, action`

- [ ] **P1.3** — Write `scripts/scan_code_spec_references.py` that:
  - Scans all `.py`, `.ts`, `.tsx` files under `api/` and `web/` for any comment or docstring matching `spec:`, `spec_id:`, `# spec NNN`, or `SPEC-NNN`
  - Builds a `spec_links` table in the DB: `(source_file, line_number, spec_id, function_name, confidence)`
  - Reports coverage per module and overall

- [ ] **P1.4** — Add `POST /api/traceability/backfill` endpoint that triggers all three scripts as a background job and returns a job_id

- [ ] **P1.5** — Add `GET /api/traceability/report` endpoint that returns:
  ```json
  {
    "summary": {
      "spec_files_total": 152,
      "spec_files_with_idea_id": 0,
      "spec_files_coverage_pct": 0.0,
      "db_specs_total": 54,
      "db_specs_with_idea_id": 0,
      "db_specs_coverage_pct": 0.0,
      "source_files_total": 0,
      "source_files_with_spec_ref": 0,
      "source_files_coverage_pct": 0.0,
      "functions_traced": 0,
      "functions_total": 0,
      "function_coverage_pct": 0.0,
      "overall_traceability_pct": 0.0
    },
    "gaps": [
      {
        "type": "spec_no_idea",
        "spec_file": "specs/055-foo.md",
        "severity": "high"
      }
    ],
    "links": [...]
  }
  ```

### Phase 2 — Convention Enforcement (new work must comply)

- [ ] **P2.1** — Every new spec file MUST include `idea_id` in its frontmatter. `scripts/validate_spec_quality.py` MUST fail if `idea_id` is absent.

- [ ] **P2.2** — Every new source file MUST include a spec reference comment in the first 5 lines:
  ```python
  # spec: 181-full-code-traceability
  # idea: full-code-traceability
  ```
  or for TypeScript:
  ```typescript
  // spec: 181-full-code-traceability
  // idea: full-code-traceability
  ```

- [ ] **P2.3** — CI check `scripts/check_spec_references.py` validates new/modified files have spec references. Fails the PR if a new `.py` or `.ts/.tsx` file under `api/` or `web/app/` lacks a spec comment.

- [ ] **P2.4** — PR description template updated to require: "Implements spec: NNN" as a mandatory field. The commit provenance contract gate (Spec 054) adds `spec_id` as a required evidence key.

- [ ] **P2.5** — `scripts/validate_spec_quality.py` updated to enforce:
  - `idea_id` field present and non-empty
  - `Verification Scenarios` section present
  - `Risks and Assumptions` section present
  - `Known Gaps and Follow-up Tasks` section present

### Phase 3 — Runtime Traceability (function-level attribution)

- [ ] **P3.1** — Define a lightweight Python decorator `@spec_traced(spec_id, idea_id)` in `api/app/core/tracing.py`:
  ```python
  def spec_traced(spec_id: str, idea_id: str | None = None):
      """Decorator that attaches traceability metadata to a function."""
      def decorator(fn):
          fn._spec_id = spec_id
          fn._idea_id = idea_id
          fn._traced = True
          return fn
      return decorator
  ```

- [ ] **P3.2** — `GET /api/traceability/functions` scans all loaded modules for functions with `_traced = True` and returns:
  ```json
  {
    "functions": [
      {
        "module": "api.app.routers.ideas",
        "function": "create_idea",
        "spec_id": "181-full-code-traceability",
        "idea_id": "full-code-traceability",
        "file": "api/app/routers/ideas.py",
        "line": 42
      }
    ],
    "coverage": {
      "traced": 18,
      "total_public": 87,
      "pct": 20.7
    }
  }
  ```

- [ ] **P3.3** — `GET /api/traceability/lineage/{idea_id}` returns the full value lineage chain:
  ```json
  {
    "idea_id": "fractal-ontology-core",
    "idea_title": "Fractal Ontology Core",
    "specs": [
      {
        "spec_id": "145",
        "spec_title": "Fractal Ontology Node Schema",
        "files": [
          {
            "path": "api/app/services/ontology_service.py",
            "functions": ["get_node", "expand_node"]
          }
        ]
      }
    ],
    "inspiration": null
  }
  ```

- [ ] **P3.4** — Auto-link PRs to specs: `scripts/parse_pr_spec_links.py` parses PR description and commit messages for `spec: NNN` or `Implements spec NNN` patterns and creates `spec_links` DB entries.

- [ ] **P3.5** — `GET /api/traceability/spec/{spec_id}` returns the full forward trace: which files implement it, which functions carry the decorator, which PRs merged it.

---

## Data Model

### New table: `spec_links`
```yaml
spec_links:
  properties:
    id: { type: uuid, pk: true }
    spec_id: { type: string, indexed: true }
    idea_id: { type: string, nullable: true }
    source_file: { type: string }
    function_name: { type: string, nullable: true }
    line_number: { type: integer, nullable: true }
    link_type: { type: string, enum: [static_comment, decorator, pr_reference, manual] }
    confidence: { type: float, min: 0.0, max: 1.0 }
    pr_number: { type: integer, nullable: true }
    created_at: { type: datetime }
```

### Spec frontmatter extension (Markdown)
All spec files gain a YAML-compatible frontmatter block at the top:
```markdown
---
idea_id: <slug>
spec_id: NNN
status: draft | approved | implemented | deprecated
created: YYYY-MM-DD
---
```

### `specs` DB table additions
```sql
ALTER TABLE specs ADD COLUMN idea_id VARCHAR(255);
ALTER TABLE specs ADD COLUMN spec_file VARCHAR(500);
ALTER TABLE specs ADD COLUMN traceability_score FLOAT DEFAULT 0.0;
```

---

## API Contract

### `POST /api/traceability/backfill`
Trigger background backfill of all three Phase 1 scripts.

**Request**: Empty body or `{ "dry_run": true }` to preview without writing.

**Response 202**:
```json
{ "job_id": "backfill-20260328", "status": "queued", "dry_run": false }
```

**Response 409**: If a backfill job is already running.

---

### `GET /api/traceability/report`
Returns current traceability state across all dimensions.

**Response 200**: See requirements P1.5 above.

---

### `GET /api/traceability/lineage/{idea_id}`
Returns complete lineage chain from idea → specs → files → functions.

**Response 200**: See requirements P3.3 above.

**Response 404**: `{ "detail": "Idea not found" }`

---

### `GET /api/traceability/spec/{spec_id}`
Returns all code that implements a given spec.

**Response 200**:
```json
{
  "spec_id": "145",
  "spec_title": "Fractal Ontology Node Schema",
  "idea_id": "fractal-ontology-core",
  "files": ["api/app/services/ontology_service.py"],
  "functions": [
    { "file": "api/app/services/ontology_service.py", "function": "get_node", "line": 55 }
  ],
  "prs": [749, 767]
}
```

**Response 404**: `{ "detail": "Spec not found" }`

---

### `GET /api/traceability/functions`
Returns all functions with `@spec_traced` decorator.

**Response 200**: See requirements P3.2 above.

---

## Files to Create/Modify

**New files:**
- `scripts/backfill_spec_idea_links.py` — Phase 1.1 backfill script
- `scripts/backfill_db_spec_idea_ids.py` — Phase 1.2 DB backfill
- `scripts/scan_code_spec_references.py` — Phase 1.3 code scanner
- `scripts/check_spec_references.py` — Phase 2.3 CI check
- `api/app/core/tracing.py` — `@spec_traced` decorator (Phase 3.1)
- `api/app/routers/traceability.py` — New router for traceability endpoints
- `api/app/services/traceability_service.py` — Business logic
- `api/app/models/traceability.py` — Pydantic models
- `api/tests/test_traceability.py` — Tests for all endpoints and scripts

**Modified files:**
- `scripts/validate_spec_quality.py` — Add `idea_id` and section enforcement (Phase 2.5)
- `api/app/main.py` — Register traceability router
- `api/alembic/versions/` — Migration for `spec_links` table and `specs` column additions

---

## Acceptance Tests

- `api/tests/test_traceability.py::test_backfill_triggers_job`
- `api/tests/test_traceability.py::test_report_returns_summary_counts`
- `api/tests/test_traceability.py::test_lineage_chain_idea_to_functions`
- `api/tests/test_traceability.py::test_spec_forward_trace`
- `api/tests/test_traceability.py::test_function_list_filtered_by_spec`
- `api/tests/test_traceability.py::test_backfill_dry_run_no_writes`
- `api/tests/test_traceability.py::test_409_on_duplicate_backfill_job`

---

## Verification Scenarios

### Scenario 1: Backfill detects and links spec files with idea references
**Setup**: The `specs/` directory contains 152 spec files. At least 26 already have `idea_id` in frontmatter. Some others mention idea slugs in their body text.

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/traceability/backfill \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
# → Should return 202 with job_id
# Wait a few seconds, then:
curl -s https://api.coherencycoin.com/api/traceability/report
```

**Expected result**: Response contains `spec_files_with_idea_id` ≥ 80 (up from 26), `spec_files_coverage_pct` ≥ 52.0. Job status field shows `"completed"`.

**Edge case**: Running `POST /api/traceability/backfill` a second time while the first job is still running returns HTTP 409 `{"detail": "Backfill job already running"}`, not a 500.

---

### Scenario 2: DB specs backfill updates idea_id on matched rows
**Setup**: 54 `specs` rows in PostgreSQL have `idea_id = NULL`. Ideas table has entries with slugs like `fractal-ontology-core`, `automation-garden-map`, etc.

**Action**:
```bash
# Run DB backfill script
python3 scripts/backfill_db_spec_idea_ids.py --min-confidence 0.85
# Then check report:
curl -s https://api.coherencycoin.com/api/traceability/report | python3 -c \
  "import json,sys; r=json.load(sys.stdin); print(r['summary']['db_specs_with_idea_id'])"
```

**Expected result**: `db_specs_with_idea_id` ≥ 40 (up from 0). Audit log file written to `data/backfill_db_audit.csv` listing each spec, matched idea, and confidence score. No row updated if confidence < 0.85.

**Edge case**: Spec title `"Spec 099: Placeholder"` has no good match. Script leaves `idea_id = NULL` and writes `needs_review` to audit log, does not error out.

---

### Scenario 3: Lineage chain traversal from idea to functions
**Setup**: Idea `fractal-ontology-core` exists in the DB. Spec 145 has `idea_id = fractal-ontology-core`. File `api/app/services/ontology_service.py` has `@spec_traced("145", "fractal-ontology-core")` on `get_node` and `expand_node`.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/traceability/lineage/fractal-ontology-core | python3 -m json.tool
```

**Expected result**: Response contains `idea_id: "fractal-ontology-core"`, `specs` list containing an entry with `spec_id: "145"`, and `files` list including `api/app/services/ontology_service.py` with `functions: ["get_node", "expand_node"]`.

**Edge case**: `GET /api/traceability/lineage/nonexistent-idea` returns HTTP 404 `{"detail": "Idea not found"}`, not 500. Partial lineage (idea exists but no specs) returns the idea with an empty `specs` array.

---

### Scenario 4: CI check fails if new file lacks spec reference comment
**Setup**: Developer creates `api/app/routers/new_feature.py` with no spec comment at top.

**Action**:
```bash
python3 scripts/check_spec_references.py --files api/app/routers/new_feature.py
```

**Expected result**: Exit code 1. Stderr contains: `FAIL api/app/routers/new_feature.py: missing spec reference comment (expected "# spec: NNN" in first 5 lines)`. When the developer adds `# spec: 181-full-code-traceability` to line 1, the script exits 0.

**Edge case**: Files in `api/tests/` and `scripts/` are exempt from the check (test and script files do not require spec comments). Running the check on a test file exits 0 even without a spec comment.

---

### Scenario 5: `@spec_traced` decorator appears in function registry
**Setup**: `api/app/routers/ideas.py` has `@spec_traced("022-idea-lifecycle", "idea-lifecycle")` on the `create_idea` function.

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/traceability/functions?spec_id=022-idea-lifecycle"
```

**Expected result**: Response contains `functions` array with at least one entry: `{"module": "api.app.routers.ideas", "function": "create_idea", "spec_id": "022-idea-lifecycle", "idea_id": "idea-lifecycle"}`. `coverage.traced` ≥ 1.

**Edge case**: `GET /api/traceability/functions?spec_id=nonexistent-spec-999` returns HTTP 200 with `{"functions": [], "coverage": {"traced": 0, "total_public": N, "pct": 0.0}}` — not a 404, since the query is a filter, not a lookup.

---

## Open Questions — Resolved

| Question | Resolution |
|----------|-----------|
| How do we backfill 126 existing specs without manual work? | Automated: regex scan of spec body for idea references + fuzzy match of spec title to idea name. Confidence threshold 0.85 for auto-update; below threshold → `needs_review` flag. Estimated coverage: 70–80% automated, remainder flagged for human review. |
| Minimal spec-to-code annotation format? | Single comment line in first 5 lines: `# spec: NNN`. No XML, no JSON, no special markers. Easiest possible format for humans, parseable by grep. |
| Static (comments) vs dynamic (runtime) function traceability? | Both, in layers. Static comments satisfy CI checks and grep-based tooling. Dynamic decorator `@spec_traced` enables `/api/traceability/functions` endpoint and value lineage chains. Decorator is opt-in, not required for all functions — start with public API route handlers. |

---

## Risks and Assumptions

- **Risk**: Fuzzy matching in Phase 1.2 may produce false-positive idea links on generic-sounding spec titles (e.g., "Spec 015: Placeholder"). **Mitigation**: Minimum confidence threshold 0.85; anything below is flagged `needs_review` rather than written.
- **Risk**: The `@spec_traced` decorator adds a negligible function-call overhead. **Mitigation**: Decorator stores metadata on the function object at decoration time (import time), not at call time — zero runtime cost.
- **Risk**: Developers may skip the spec comment convention. **Mitigation**: CI check `scripts/check_spec_references.py` blocks PR merge for new files under `api/app/` and `web/app/` that lack the comment.
- **Assumption**: The `specs` DB table exists and has a `title` column usable for fuzzy matching against idea names. Confirmed via existing Spec 089 usage.
- **Assumption**: All spec files use consistent Markdown format with a `# Spec NNN:` H1 header. Confirmed by inspection of `specs/*.md`.

---

## Known Gaps and Follow-up Tasks

- TypeScript/TSX function-level tracing: The `@spec_traced` decorator is Python-only in Phase 3. A JSDoc `@spec` tag convention for TypeScript is deferred to a follow-up spec.
- Historical commit mining: Parsing all prior commit messages for spec references to backfill old PRs is out of scope here. See Spec 056 for commit-derived traceability.
- UI overlay: A web UI showing the lineage chain visually (idea → specs → files → functions as a DAG) is out of scope for this spec. Follow-up task: `task_traceability_ui_dag`.
- Spec deprecation: No mechanism yet to mark a spec as deprecated and unlink its code. Follow-up task: `task_spec_deprecation`.

---

## Failure/Retry Reflection

- **Failure mode**: Backfill script times out on a large repo.
  - **Blind spot**: Underestimated number of files × regex operations.
  - **Next action**: Run with `--batch-size 20` argument; process in chunks.

- **Failure mode**: DB migration for `spec_links` fails because `spec_id` column already exists under a different name.
  - **Blind spot**: Existing partial traceability schema from Spec 089.
  - **Next action**: Run `\d spec_links` in psql before migration; check for column conflicts.

- **Failure mode**: CI check blocks all PRs because many existing files lack spec comments.
  - **Blind spot**: Check applies to all files, not just new ones.
  - **Next action**: Scope CI check to `git diff --name-only origin/main` — only new/modified files in the current PR, not all historical files.

---

## Out of Scope

- Traceability for infrastructure files (`docker-compose.yml`, `nginx.conf`, Dockerfiles)
- Traceability for test files (tests reference the code they test, not the spec directly)
- Automatic spec generation from code (reverse direction)
- Attribution payouts or economic value calculation (covered in Spec 048)

---

## Task Card

```yaml
goal: Implement multi-phase traceability system linking every spec to an idea, every file to a spec, and every function to both.
files_allowed:
  - scripts/backfill_spec_idea_links.py
  - scripts/backfill_db_spec_idea_ids.py
  - scripts/scan_code_spec_references.py
  - scripts/check_spec_references.py
  - scripts/validate_spec_quality.py
  - api/app/core/tracing.py
  - api/app/routers/traceability.py
  - api/app/services/traceability_service.py
  - api/app/models/traceability.py
  - api/app/main.py
  - api/tests/test_traceability.py
  - api/alembic/versions/NNN_add_spec_links_table.py
done_when:
  - GET /api/traceability/report returns overall_traceability_pct >= 50
  - POST /api/traceability/backfill triggers job and returns 202
  - GET /api/traceability/lineage/{idea_id} returns spec + file + function chain
  - GET /api/traceability/spec/{spec_id} returns forward trace to files and functions
  - scripts/check_spec_references.py exits 1 for new files lacking spec comment
  - @spec_traced decorator decorates >= 5 API route handlers
  - All tests in api/tests/test_traceability.py pass
commands:
  - python3 -m pytest api/tests/test_traceability.py -x -v
  - python3 scripts/check_spec_references.py --files api/app/routers/traceability.py
  - python3 scripts/backfill_spec_idea_links.py --dry-run
constraints:
  - No schema migrations without explicit approval
  - CI check must be scoped to new/modified files only (not historical)
  - Fuzzy match confidence threshold must be configurable, default 0.85
  - Decorator must have zero call-time overhead
  - Backfill scripts must be idempotent (safe to run multiple times)
```

---

## Evidence of Realization

The following can be independently verified once implemented:

1. `curl https://api.coherencycoin.com/api/traceability/report` — returns `overall_traceability_pct` ≥ 50, `spec_files_with_idea_id` ≥ 80
2. `curl https://api.coherencycoin.com/api/traceability/lineage/fractal-ontology-core` — returns full idea → spec → file → function chain
3. `git log --all --grep="spec:" --oneline | wc -l` — shows ≥ 10 commits referencing spec IDs in messages
4. Contributor attestation: any engineer can inspect `api/app/routers/traceability.py` and confirm `@spec_traced` decorators are present on route handlers
5. `python3 scripts/check_spec_references.py --files api/app/routers/ideas.py` — exits 0, confirming the file has a valid spec reference comment
