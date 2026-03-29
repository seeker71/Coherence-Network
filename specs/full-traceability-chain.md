# Spec: Full Traceability Chain (`full-traceability-chain`)

**idea_id**: `full-traceability-chain`  
**parent_idea**: `fractal-ontology-core`  
**Status**: Draft  
**Created**: 2026-03-29  
**Related technical spec**: [`specs/181-full-code-traceability.md`](181-full-code-traceability.md) (implementation detail, scripts, endpoints, DB)

---

## Summary

Coherence Network is spec-driven, but traceability from **code → spec → idea → external inspiration** is weak: roughly 17% of spec files link to an idea, registry rows in PostgreSQL often lack `idea_id`, and there is no durable graph of which functions implement which specs. This specification defines the **full traceability chain** outcome: from any symbol in the repo, a user or agent can walk backward to the governing spec, originating idea, and (where recorded) inspiration sources such as articles. Delivery is intentionally **multi-phase**: automated backfill and link construction first, conventions and CI second, runtime and lineage projection third. This document is the **product charter** for idea `full-traceability-chain`; detailed file lists and API shapes align with spec 181 unless explicitly overridden below.

---

## Purpose

Establish end-to-end traceability so that engineering intent is never orphaned: every meaningful artifact (spec file, registry row, implementation file, and progressively every public API function) can be tied to an **idea** and, where applicable, to **value lineage** records. This prevents duplicate work, enables attribution, and supports the Fractal Ontology Core narrative—structure that knows its own origin. Without this chain, the graph is “flat data”; with it, the system can answer *why* something exists and *which hypothesis* it tests.

---

## Background & Metrics (from inventory)

| Dimension | Approximate current | Target (Phase 1–2) | Target (Phase 3) |
|-----------|---------------------|--------------------|------------------|
| Spec markdown files with resolvable `idea_id` | ~17% | ≥ 85% | ≥ 95% |
| `spec_registry_entries.idea_id` populated | low / many null | ≥ 90% of rows | ≥ 95% |
| Source files with machine-detectable spec reference | ~0% (new/changed files enforced) | new files 100% via CI | stable + decorators |
| Function-level links | none | optional decorator on key routes | ≥ 60% public API |
| End-to-end lineage API | missing | report + partial lineage | idea → spec → file → function |

---

## Requirements

### Product requirements (acceptance)

- [ ] **R1 — Idea link on every spec (markdown)**: Every spec under `specs/` either has a machine-readable `idea_id` (YAML frontmatter or established header pattern per 181) or is explicitly flagged `needs_review` by the backfill job with a reason code (no silent gaps in the report).
- [ ] **R2 — Registry alignment**: PostgreSQL `spec_registry_entries` rows are backfilled or matched so that `idea_id` is set where confidence ≥ agreed threshold (default 0.85 per 181); lower-confidence matches are listed for human review, not written blindly.
- [ ] **R3 — Code → spec links**: A persistent `spec_links` (or equivalent) store captures static references from source (comments, optional decorators, PR/commit metadata) with `link_type`, `confidence`, and pointers to file/line/function where applicable.
- [ ] **R4 — Report API**: `GET /api/traceability/report` (or successor) returns aggregate coverage metrics comparable to 181 P1.5 so operators can track progress independently of ad-hoc SQL.
- [ ] **R5 — Lineage read API**: `GET /api/traceability/lineage/{idea_id}` returns a forward trace from idea through specs to files and (where available) decorated functions, consistent with 181 P3.3.
- [ ] **R6 — Conventions**: New specs must include `idea_id`; new/modified implementation files under `api/app/` and `web/app/` must carry a minimal top-of-file spec reference; CI scopes checks to changed paths so legacy code is not blocked en masse.
- [ ] **R7 — Evidence**: Independently verifiable proof of realization is published (public API responses and/or repository scripts with documented commands) — see **Evidence of realization** below.

### Engineering requirements (must align with 181)

- [ ] **R8 — Idempotent backfill**: All backfill scripts are safe to re-run; they log actions and do not duplicate rows in link tables.
- [ ] **R9 — Tests**: Contract tests exist for traceability endpoints and critical scripts (see Acceptance Tests).

---

## Open questions — decisions

| Question | Decision |
|----------|----------|
| How do we backfill ~126 existing specs without manual work? | **Automated extraction first**: scan markdown for `idea_id`, `idea:`, `/api/ideas/{slug}`, known slugs from the ideas registry, and “See also” cross-links. **Second pass**: fuzzy title/summary match to ideas. **No auto-write** below confidence threshold; emit CSV/JSON for review. Optional LLM-assisted classification is out of scope unless approved (cost + nondeterminism). |
| What is the minimal spec-to-code annotation format? | **One line in the first five lines**: `# spec: <id-or-slug>` (Python) or `// spec: <id-or-slug>` (TS/TSX). Optional second line `# idea: <slug>`. No XML, no structured blocks required for MVP. |
| Static vs dynamic function traceability? | **Both, layered**: Static comments satisfy CI and grep tooling. **Optional** `@spec_traced` (or equivalent) on Python handlers provides introspection for `/api/traceability/functions`. TypeScript uses JSDoc `@spec` in a follow-up; do not block Phase 1–2 on TS decorators. |

---

## API changes

See `specs/181-full-code-traceability.md` for full JSON schemas. This charter **requires** the following surface area to exist for idea `full-traceability-chain` to be considered “implemented”:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/traceability/backfill` | Queue or run Phase 1 backfill (supports `dry_run`) |
| `GET` | `/api/traceability/report` | Coverage summary and gap list |
| `GET` | `/api/traceability/lineage/{idea_id}` | Idea → specs → files → functions |
| `GET` | `/api/traceability/spec/{spec_id}` | Forward trace of implementations |
| `GET` | `/api/traceability/functions` | List of decorator-tagged functions (optional filter) |

**N/A** — No breaking changes to existing ideas CRUD; traceability is additive.

---

## Data model

Aligned with spec 181:

- **Table `spec_links`** (or equivalent name): links `spec_id`, optional `idea_id`, `source_file`, optional `function_name`, `line_number`, `link_type` (`static_comment`, `decorator`, `pr_reference`, `manual`), `confidence`, optional `pr_number`, timestamps.
- **`spec_registry_entries`**: continue using existing `idea_id` column; backfill and index for lineage queries.
- **Spec markdown**: frontmatter fields `idea_id`, `spec_id` (or numeric id), `status`, `created` as in 181.

---

## Files to Create/Modify

Implementation follows **181**; this list is the authoritative set for impl agents (create if missing, modify as needed):

**New files**

- `scripts/backfill_spec_idea_links.py` — Phase 1: scan `specs/*.md`, emit reports, optional frontmatter patch
- `scripts/backfill_db_spec_idea_ids.py` — Phase 1: match registry rows to ideas
- `scripts/scan_code_spec_references.py` — Phase 1: scan `api/`, `web/` for spec comments and build `spec_links`
- `scripts/check_spec_references.py` — Phase 2: CI for changed files only
- `scripts/parse_pr_spec_links.py` — Phase 3: PR/commit message → spec links (optional)
- `api/app/core/tracing.py` — `@spec_traced` decorator (Python)
- `api/app/routers/traceability.py` — HTTP routes
- `api/app/services/traceability_service.py` — Business logic
- `api/app/models/traceability.py` — Pydantic models
- `api/tests/test_traceability.py` — Contract tests
- `api/alembic/versions/<revision>_add_spec_links_and_traceability.py` — Migration for `spec_links` and indexes

**Modified files**

- `scripts/validate_spec_quality.py` — Enforce `idea_id` and required sections for new/changed specs (Phase 2)
- `api/app/main.py` — Register traceability router
- `api/app/services/spec_registry_service.py` — Helpers for bulk updates and safe writes during backfill
- `.github/workflows/*.yml` — Wire `check_spec_references.py` into CI for PRs (exact workflow file TBD by impl)
- `docs/RUNBOOK.md` — Document operator commands for backfill and reporting (short section)

---

## Acceptance Tests

- `api/tests/test_traceability.py::test_report_returns_summary_counts`
- `api/tests/test_traceability.py::test_lineage_chain_includes_idea_specs_and_files`
- `api/tests/test_traceability.py::test_backfill_respects_dry_run`
- `api/tests/test_traceability.py::test_spec_forward_trace_lists_files`
- `python3 scripts/validate_spec_quality.py --file specs/full-traceability-chain.md` (spec quality gate)

---

## Verification Scenarios

### Scenario 1: Report shows improved spec coverage after backfill

**Setup**: API deployed with traceability routes enabled; `specs/` contains a mix of files with and without `idea_id` in frontmatter.  
**Action**:

```bash
curl -sS https://api.coherencycoin.com/api/traceability/report | python3 -m json.tool
```

**Expected result**: HTTP 200; JSON includes `summary.spec_files_total` ≥ 152, `summary.spec_files_with_idea_id` strictly greater than pre-backfill baseline (e.g. > 26), and `gaps` is an array listing remaining `spec_no_idea` entries with `spec_file` paths.  
**Edge**: If `POST /api/traceability/backfill` is called with `{"dry_run": true}`, report counts for `spec_files_with_idea_id` are unchanged from baseline; job log records “dry_run”.

---

### Scenario 2: Registry backfill sets `idea_id` only above threshold

**Setup**: Staging DB with `spec_registry_entries` rows where `idea_id` IS NULL; ideas table contains known slugs.  
**Action**:

```bash
python3 scripts/backfill_db_spec_idea_ids.py --min-confidence 0.85
curl -sS "$API_URL/api/traceability/report" | python3 -c "import json,sys; print(json.load(sys.stdin)['summary'].get('db_specs_with_idea_id'))"
```

**Expected result**: `db_specs_with_idea_id` increases; audit artifact lists each updated `spec_id` and `matched_idea_id`.  
**Edge**: A spec titled `"Untitled"` with no textual overlap with any idea returns **no** row update and appears in audit as `needs_review`, not error.

---

### Scenario 3: Lineage endpoint walks idea → spec → file

**Setup**: Idea `fractal-ontology-core` exists; at least one spec linked to it; at least one source file with `spec:` comment or decorator referencing that spec.  
**Action**:

```bash
curl -sS https://api.coherencycoin.com/api/traceability/lineage/fractal-ontology-core | python3 -m json.tool
```

**Expected result**: HTTP 200; JSON includes `idea_id` equal to `fractal-ontology-core`, non-empty `specs` array, and at least one file path under `specs[].files[]`.  
**Edge**: `GET /api/traceability/lineage/does-not-exist-idea` returns HTTP 404 with `{"detail": "Not found"}` or documented equivalent — not 500.

---

### Scenario 4: CI rejects new file without spec comment

**Setup**: New file `api/app/routers/ephemeral_feature.py` with no `# spec:` in first five lines.  
**Action**:

```bash
python3 scripts/check_spec_references.py --files api/app/routers/ephemeral_feature.py
echo $?
```

**Expected result**: Exit code 1; stderr contains `missing spec reference` or `spec:` substring. After adding `# spec: full-traceability-chain` as line 1, exit code 0.  
**Edge**: `api/tests/test_foo.py` is exempt (no failure) when listed in exempt paths.

---

### Scenario 5: Decorator-registered function appears in function inventory

**Setup**: One route handler decorated with `@spec_traced("full-traceability-chain", "full-traceability-chain")` (or spec id from 181).  
**Action**:

```bash
curl -sS "https://api.coherencycoin.com/api/traceability/functions" | python3 -m json.tool
```

**Expected result**: HTTP 200; `functions` array contains an object with matching `spec_id` and `module`/`function` fields.  
**Edge**: Query with unknown filter returns empty `functions` array with 200, not 500.

---

## Verification

```bash
# Contract tests
cd api && .venv/bin/pytest -q api/tests/test_traceability.py -v

# Spec quality (this file)
python3 scripts/validate_spec_quality.py --file specs/full-traceability-chain.md

# Local backfill dry run (when implemented)
python3 scripts/backfill_spec_idea_links.py --dry-run
```

---

## Out of Scope

- Rewriting all historical commits to add spec tags (use forward-looking PR/commit parsing only).
- Full IDE “click symbol → navigate to lineage” (editor plugins); APIs must exist first.
- Economic payout calculation (handled under value-lineage / treasury specs).
- Mandatory TypeScript runtime decorators in Phase 1–2.

---

## Risks and Assumptions

- **Risk**: Fuzzy matching links the wrong idea to a spec. **Mitigation**: Confidence thresholds, audit logs, human review queue for low confidence.  
- **Risk**: CI noise if checks apply to all files. **Mitigation**: Scope to `git diff` against `main` for PRs.  
- **Risk**: Duplicate or conflicting entries in `spec_links`. **Mitigation**: Unique constraints on `(source_file, spec_id, link_type)` or idempotent upsert; document merge rules.  
- **Assumption**: The ideas registry exposes stable string ids usable as `idea_id` foreign references.  
- **Assumption**: Spec 181 remains the technical source of truth for table/column names unless superseded by a migration with review.

---

## Known Gaps and Follow-up Tasks

- TypeScript/JSDoc `@spec` convention for `web/` components — follow-up task aligned with spec 181 gaps.  
- Visual DAG UI for lineage — **not** in this charter; depends on report + lineage APIs.  
- **None** for blocking MVP: if all Phase 1 endpoints and scripts are delivered, this idea can be marked realized per Evidence section.

---

## Evidence of realization

Any party can verify without private access:

1. **Public API**: `GET https://api.coherencycoin.com/api/traceability/report` returns JSON with `overall_traceability_pct` ≥ 50 after Phase 1 completion (or documented interim threshold in `summary`).  
2. **Lineage**: `GET https://api.coherencycoin.com/api/traceability/lineage/full-traceability-chain` returns a structured chain when this idea exists in the registry.  
3. **Repository**: `git grep -n "spec: full-traceability-chain" -- api web` shows at least one implementation file referencing this spec.  
4. **Attestation**: Merge commit or PR description explicitly states `Implements spec: full-traceability-chain` with link to `specs/full-traceability-chain.md`.

---

## Failure/Retry Reflection

- **Failure mode**: Backfill OOM on large trees. **Next action**: Batch by directory or glob chunking.  
- **Failure mode**: Migration conflicts with existing traceability tables. **Next action**: Inspect live schema before `alembic upgrade`; align with spec 089 if overlap exists.

---

## Task Card

```yaml
goal: Deliver full traceability chain (idea→spec→code→function) for idea full-traceability-chain per spec 181 and this charter.
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
  - api/app/services/spec_registry_service.py
  - api/tests/test_traceability.py
done_when:
  - GET /api/traceability/report returns measurable coverage fields
  - GET /api/traceability/lineage/{idea_id} returns 200 for a known idea
  - pytest api/tests/test_traceability.py passes
  - validate_spec_quality passes for this spec file
commands:
  - cd api && .venv/bin/pytest -q api/tests/test_traceability.py
  - python3 scripts/validate_spec_quality.py --file specs/full-traceability-chain.md
constraints:
  - Do not weaken tests to pass; fix implementation
  - Backfill idempotent; CI scoped to changed files only
```
