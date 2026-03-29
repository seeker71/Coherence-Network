# Spec: Full traceability — idea → spec → code → function

**Idea ID (spec slug):** `idea-full-traceability`  
**Related task:** `task_9ffe2571792992ea`  
**Status:** Draft (spec-only; implementation follows separate task cards per phase)

## Summary

Coherence Network currently has weak end-to-end traceability: most spec files do not link to ideas, persisted spec records lack `idea_id`, code does not systematically reference specs, and there is no function-level attribution. This spec defines a **three-phase program** to reach a target state where **any file and (where feasible) any function** can be traced backward to a **spec** and an **idea**, and forward to **evidence** (PRs, commits, external inspiration). Phase 1 is **automated backfill and link construction**. Phase 2 is **repository and process conventions** enforced by CI and templates. Phase 3 is **runtime lineage**: optional dynamic resolution, PR/spec auto-linking from commit messages, and automatic value-lineage chain materialization from the link graph.

Baseline called out in discovery: ~17% traceability; 126/152 spec files without idea link; 0/54 DB specs with `idea_id`; no implementation-to-spec links; no function-level attribution. Success is measured by **coverage metrics** (specs with `idea_id`, files with spec headers, API link rows) and by **verification scenarios** below runnable against production after implementation.

## Purpose

Without traceability, attribution, audit, and onboarding suffer: contributors cannot see *why* code exists, PM cannot prove which idea funded a change, and value lineage (idea → spec → implementation → external source) stays implicit. This spec makes those relationships **first-class, queryable, and incrementally enforceable**, starting with high-yield automation and ending with optional deep (function-level) resolution where cost/benefit allows.

## Open questions (resolved in this spec)

### Q1: How do we backfill traceability for many existing specs without manual work?

**Answer:** **Tiered automation, not 100% manual.**

1. **Parse spec frontmatter and body** for machine-detectable signals:
   - YAML/JSON frontmatter fields: `idea_id`, `idea`, `related_idea`, `task_id`, `Idea ID`, etc.
   - Inline patterns: `POST /api/ideas`, links to idea slugs, `See idea:`, `task_` prefixes, numbered spec cross-references that map to ideas via the graph API.
2. **Infer from filename**: `specs/task_<id>.md` → correlate `<id>` with agent tasks that store `idea_id` when available.
3. **Fuzzy match** spec titles/summaries to idea titles (above threshold) → queue as **suggested** links requiring one-click confirm in a review UI, not auto-write to production without governance (configurable: `TRACEABILITY_AUTOLINK_CONFIDENCE_MIN`).
4. **Default for unlinked specs**: create or attach a **synthetic umbrella idea** (e.g. `legacy-spec-backlog`) grouped by quarter/domain, so *every* spec has *some* idea anchor; then split/refine in Phase 2 as humans curate.

Manual work is limited to **low-confidence buckets** and **policy exceptions**, not all 126 files.

### Q2: What is the minimal spec-to-code annotation format that is not burdensome?

**Answer:** **One mandatory file header line** plus **optional** function anchors.

**File-level (required for new/changed files in Phase 2):**

```text
# traceability: spec=specs/123-feature.md idea=idea-slug-or-uuid
```

or for languages that prefer block comments:

```text
/* traceability: spec=specs/123-feature.md idea=idea-slug-or-uuid */
```

Rules:

- `spec=` path is **repo-relative** from repository root.
- `idea=` is **idea id/slug** as stored in `/api/ideas` (canonical string form documented in API).
- Order of keys fixed (`spec` then `idea`) for grep simplicity; CI regex is stable.
- **Omit `idea=`** only if spec frontmatter already declares `idea_id` and CI validates spec file contains it (single source of truth in spec file).

**Function-level (optional Phase 3, minimal):**

```text
# traceability-fn: spec=specs/123-feature.md#R7
```

where `#R7` refers to requirement id in the spec body, **or** a stable spec anchor slug. Implementations MAY use decorators (`@traceability(spec=..., req=...)`) if the team standardizes on Python/TS — but the **comment form remains the portable contract** for polyglot repos.

### Q3: Static (comments) vs dynamic (runtime introspection) for function-level traceability?

**Answer:** **Primary source of truth is static** (comments or codegen metadata file); **runtime is a derived index**.

- **Static**: survives debugging, works in any language, indexable by CI and IDEs.
- **Dynamic**: optional `GET /api/traceability/resolve?file=&line=` that reads a **precomputed map** (JSON generated at build/CI) from parser output — not `inspect.getsource` in production for correctness at scale.

Phase 3 delivers **static annotations + build artifact** (`traceability-map.json`); runtime API serves the map, not live AST parsing on each request.

## Requirements

### Phase 1 — Automated backfill and links

- [ ] **P1-R1:** Batch scanner walks `specs/**/*.md`, extracts `idea_id` (or equivalent) where present; persists to DB spec records.
- [ ] **P1-R2:** Backfill job sets `idea_id` on all spec rows that can be inferred with confidence ≥ configured threshold; others flagged `idea_id_suggested` + `confidence` for review.
- [ ] **P1-R3:** Scanner walks `api/`, `web/`, `scripts/` (configurable roots) for `traceability:` header or legacy patterns (`specs/\d+`, `Spec \d+`, `specs/idea-`).
- [ ] **P1-R4:** New **links table** (or graph edges) stores: `(source_type, source_id, target_type, target_id, relationship, created_at, evidence)` where `relationship ∈ {implements, references, tests, documents}`.
- [ ] **P1-R5:** Idempotent job: re-run does not duplicate links; uses stable hash of (source, target, relationship).
- [ ] **P1-R6:** Report endpoint or CLI: `traceability coverage %`, counts of specs without idea, files without spec header.

### Phase 2 — Conventions and gates

- [ ] **P2-R1:** Spec template (`specs/TEMPLATE.md`) includes mandatory `idea_id` (or `idea_id: required` in frontmatter schema).
- [ ] **P2-R2:** `validate_spec_quality.py` (or sibling) fails if changed spec under `specs/` lacks resolvable `idea_id` when merged to main (allow list for archival paths optional).
- [ ] **P2-R3:** CI job fails new/changed `*.py`, `*.ts`, `*.tsx` files missing `traceability:` first comment block (with defined exceptions: generated files, `__init__.py` empty re-exports list maintained in config).
- [ ] **P2-R4:** PR template requires `Spec: specs/....md` line; optional GitHub Action comments with missing spec link.
- [ ] **P2-R5:** Document in `CLAUDE.md` / `AGENTS.md`: every session records ideas via API; spec must cite idea.

### Phase 3 — Runtime lineage

- [ ] **P3-R1:** Commit message convention `spec(specs/foo.md): summary` parsed to auto-create `implements` edges from PR merge commit to spec.
- [ ] **P3-R2:** `GET /api/traceability/chain?file=` returns JSON: `{ file, spec, idea, inspirations[] }` walking links; 404 if unknown.
- [ ] **P3-R3:** Value lineage: when idea links include external URLs (Nature article, etc.), chain includes those nodes as `inspires` / `references` edges.
- [ ] **P3-R4:** Optional web drill-down: click symbol → show spec + idea + sources (uses static map + API).

## API changes

New or extended endpoints (exact paths can be adjusted in implementation spec; semantics fixed here):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/traceability/scan` | Admin/cron: trigger spec+code scan (body: `{ "roots": [...], "dry_run": bool }`) |
| `GET` | `/api/traceability/coverage` | Metrics: `% specs with idea_id`, `files with spec header`, `open gaps` |
| `GET` | `/api/traceability/links` | Paginated query: `?source_type=&target_type=&id=` |
| `GET` | `/api/traceability/chain` | Query: `?file=`, optional `line=` — returns merged chain spec→idea→inspirations |
| `GET` | `/api/specs/{spec_id}/trace` | Spec-centric view: linked files, ideas, PRs |

**Auth:** Scan and bulk write = operator/admin; read endpoints public or authenticated per existing API policy.

**Responses:** Pydantic models; dates ISO 8601 UTC; error bodies consistent with existing `{ "detail": "..." }`.

## Data model

```yaml
TraceLink:
  properties:
    id: { type: string, format: uuid }
    source_type: { type: string, enum: [spec_file, code_file, function_symbol, idea, pr, commit, external_ref] }
    source_id: { type: string, description: "stable id: path, commit sha, idea id, URL" }
    target_type: { type: string, enum: [spec_file, code_file, function_symbol, idea, pr, commit, external_ref] }
    target_id: { type: string }
    relationship: { type: string, enum: [implements, references, tests, documents, inspires, derived_from] }
    confidence: { type: number, minimum: 0, maximum: 1, nullable: true }
    evidence: { type: object, description: "parser version, matched line, rule name" }
    created_at: { type: string, format: date-time }

SpecRecord:  # extend existing persisted spec model
  properties:
    idea_id: { type: string, nullable: true }
    idea_id_status: { type: string, enum: [confirmed, inferred, suggested, missing] }
    last_scan_at: { type: string, format: date-time, nullable: true }
```

Storage may be PostgreSQL tables or Neo4j edges **as long as** the API contract and idempotency hold; implementation chooses per existing platform norms.

## Files to Create/Modify (implementation scope — not all in one PR)

- `api/app/models/traceability.py` — Pydantic models
- `api/app/services/traceability_scanner_service.py` — scan + infer + upsert links
- `api/app/services/traceability_report_service.py` — coverage metrics
- `api/app/routers/traceability.py` — HTTP surface
- `api/app/main.py` — register router
- `scripts/traceability_scan.py` — CLI for local/CI
- `specs/TEMPLATE.md` — mandatory `idea_id`
- `scripts/validate_spec_quality.py` — spec idea gate
- `.github/workflows/` — CI traceability check (new workflow or job)
- `docs/RUNBOOK.md` — operator notes for scan cron
- `api/tests/test_traceability_scan.py`, `api/tests/test_traceability_api.py`

Exact file list MUST be frozen in a downstream implementation task card per repo rules.

## Acceptance criteria (product)

1. **Coverage:** ≥ 95% of specs in `specs/` have a non-null `idea_id` (confirmed or inferred ≥ threshold) within 30 days of Phase 1 deploy; remaining documented in `Known Gaps`.
2. **Code files:** ≥ 90% of application code files (`api/app/`, `web/app/` or agreed roots) carry a valid `traceability:` header within 90 days (grandfathered list shrinks monthly).
3. **API:** `GET /api/traceability/coverage` returns JSON matching schema and is used in STATUS reporting.
4. **Chain:** For any file with header + registered spec + idea with external link, `GET /api/traceability/chain?file=...` returns a path including spec id, idea id, and external URL.
5. **CI:** Merging a PR that adds a spec without `idea_id` fails the quality gate; adding a new code file without header fails unless exempt.

## Verification Scenarios

Scenarios below are **contracts for production verification** after implementation. Adjust URLs to deployment base (`https://api.coherencycoin.com` or worktree local).

### Scenario 1 — Coverage report reflects backfill

- **Setup:** Phase 1 deployed; database contains mix of specs with and without `idea_id` before scan; at least one spec file includes frontmatter `idea_id: test-idea-trace`.
- **Action:** `curl -sS "$API/api/traceability/coverage" | jq .`
- **Expected:** HTTP 200; body includes numeric fields e.g. `specs_total`, `specs_with_idea`, `spec_coverage_ratio` in `0..1`; `specs_with_idea` increases after scan vs pre-scan snapshot (prove monotonic improvement when run twice with same inputs).
- **Edge:** Unauthenticated call behavior matches policy (401 vs 200 public read); if 401, repeat with valid admin token and expect 200.
- **Edge:** Malformed `Authorization` header returns 401, not 500.

### Scenario 2 — Scan job is idempotent

- **Setup:** Clean worktree; seed one spec with `idea_id` and one code file with `# traceability: spec=specs/177-demo.md idea=test-idea-trace`.
- **Action:** `curl -sS -X POST "$API/api/traceability/scan" -H "Content-Type: application/json" -d '{"dry_run":false}'` (with admin auth); note `links_created`; run identical POST again.
- **Expected:** Second run `links_created == 0` or `links_unchanged` count matches; no duplicate rows for same `(source_type, source_id, target_type, target_id, relationship)` per API contract.
- **Edge:** `dry_run: true` returns proposed diff without DB writes; second identical dry_run matches first.
- **Edge:** Invalid body `{}` missing required fields returns 422 with Pydantic detail array.

### Scenario 3 — File chain resolves end-to-end

- **Setup:** Idea `fractal-ontology-core` exists via `POST /api/ideas` with `metadata.inspirations: ["https://www.nature.com/articles/..."]` (or dedicated field per existing idea schema); spec `specs/177-demo.md` has `idea_id: fractal-ontology-core`; code file path registered with header pointing to that spec.
- **Action:** `curl -sS "$API/api/traceability/chain?file=api/app/demo_traceability.py" | jq .`
- **Expected:** HTTP 200; JSON contains `spec.path == "specs/177-demo.md"`, `idea.id == "fractal-ontology-core"`, and `inspirations` or equivalent includes the Nature URL.
- **Edge:** Unknown file: `GET .../chain?file=nonexistent.py` returns 404 with `detail` string, not empty 200.
- **Edge:** File exists but no header: 404 or `partial: true` with explicit `gaps[]` — behavior fixed in implementation doc and tested.

### Scenario 4 — Spec quality gate blocks missing idea

- **Setup:** Branch adds new file `specs/999-missing-idea.md` without `idea_id` frontmatter; run `python3 scripts/validate_spec_quality.py --base origin/main --head HEAD` in CI container.
- **Expected:** Non-zero exit code; stderr or stdout names file and rule `spec_missing_idea_id`.
- **Edge:** Spec in `allowlist_path` (if configured) passes.
- **Edge:** Draft spec under `specs/_drafts/` excluded by config — document exclusion list.

### Scenario 5 — PR commit parses spec reference

- **Setup:** Merge (or simulate webhook) commit with message `spec(specs/177-demo.md): add traceability scanner`.
- **Action:** Invoke PR ingestion job (or `POST` hook handler) once.
- **Expected:** New `TraceLink` with `source_type=commit`, `relationship=implements`, `target_type=spec_file`, `target_id=specs/177-demo.md`.
- **Edge:** Duplicate merge event does not duplicate link.
- **Edge:** Message without `spec(...)` creates no link; parser does not throw 500.

## Verification (developer commands — post-implementation)

```bash
cd api && pytest -q api/tests/test_traceability_api.py api/tests/test_traceability_scan.py
python3 scripts/traceability_scan.py --dry-run
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
```

## Evidence that the idea is realized (independently verifiable)

| Evidence type | What to collect |
|---------------|-----------------|
| **Live API** | Public or authenticated `GET /api/traceability/coverage` on production returns stable JSON schema documented in OpenAPI. |
| **OpenAPI** | `/openapi.json` contains `/api/traceability/*` paths after deploy. |
| **Repository** | Tagged release contains `scripts/traceability_scan.py` and sample `traceability-map.json` artifact in CI logs. |
| **Attestation** | Commit SHA on `main` implementing Phase 1+2; PR link showing CI green for traceability job. |
| **Screenshot (optional)** | Web UI showing chain (Phase 3) with idea + external article — filename and path in PR description. |

Any third party can verify without insider access: curl production + read OpenAPI + inspect git history.

## Risks and Assumptions

- **Risk:** Autolink false positives attach wrong idea to spec — **Mitigation:** confidence threshold + `suggested` status + human review queue; never auto-set `confirmed` above threshold without rule match on explicit id.
- **Risk:** Comment headers drift from moved files — **Mitigation:** scan detects stale spec paths; CI fails if spec path invalid.
- **Assumption:** Ideas API and spec persistence remain the system of record; traceability is an overlay, not a second CMS.
- **Assumption:** Polyglot repo tolerates one-line comment convention; generated code exempt via config.

## Known Gaps and Follow-up Tasks

- Function-level coverage for minified bundles and third-party vendored code — default **exempt** with explicit `traceability-ignore` reason in config file.
- IDE LSP integration — follow-up after static map stable.
- Cross-repo forks (federation) — traceability chain may stop at instance boundary unless federated idea ids standardized (tie to federation specs).

## Out of scope

- Rewriting all historical commits to add `spec(...)` messages.
- Legal discovery-grade provenance (court admissibility) — separate compliance spec.
- Automatic scraping of Nature full text; only URLs/metadata stored.

## Failure/Retry Reflection

- **Failure mode:** Scan OOM on huge monorepo — **Next action:** incremental scan by git diff since last `last_scan_at`.
- **Failure mode:** Neo4j write contention — **Next action:** batch upsert with backoff; PostgreSQL fallback table.

## Task Card (implementation seed)

```yaml
goal: Phase 1 — automated traceability scan, backfill idea_id on specs, links table, coverage API
files_allowed:
  - api/app/models/traceability.py
  - api/app/services/traceability_scanner_service.py
  - api/app/services/traceability_report_service.py
  - api/app/routers/traceability.py
  - api/app/main.py
  - scripts/traceability_scan.py
  - api/tests/test_traceability_api.py
  - api/tests/test_traceability_scan.py
  - specs/idea-full-traceability.md
done_when:
  - POST /api/traceability/scan persists links idempotently
  - GET /api/traceability/coverage returns required metrics
  - pytest tests for scan + API pass
commands:
  - cd api && pytest -q tests/test_traceability_api.py tests/test_traceability_scan.py
constraints:
  - Do not weaken validate_spec_quality for unrelated specs until Phase 2 task explicitly enables the new gate
```

## See also

- `specs/123-transparent-audit-ledger.md` — audit and evidence patterns
- `specs/138-idea-lifecycle-management.md` — idea as lifecycle anchor
- `docs/RUNBOOK.md` — idea tracking protocol
- `CLAUDE.md` — spec-first and file scope rules
