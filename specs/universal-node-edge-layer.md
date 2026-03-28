# Spec: Universal Node + Edge Data Layer

**Idea ID**: `universal-node-edge-layer`  
**Status**: Draft (spec-first unblock for flow `spec` stage)

## Purpose

Define a single, explicit **node + edge** persistence and API contract so every entity (ideas, tasks, specs, runtime events, friction records) can be addressed uniformly: one identity scheme, one relationship model, and deterministic projections to HTTP and SQL views. This spec does **not** implement the layer; it constrains a small, verifiable follow-up implementation that reduces **failed-tasks** and **friction** churn by eliminating ambiguous dual paths (ad-hoc JSON versus table versus in-memory) before more CI-heavy iterations. Operators gain **trust** (traceable ids), **clarity** (one vocabulary), and **reuse** (adapters over new stores).

**Intent (what we optimize for)**:

- **Trust**: Operators can trace any API response to a stable node id and edge set with proof artifacts.
- **Clarity**: One vocabulary (`node`, `edge`, `kind`, `payload`) across services and docs.
- **Reuse**: New features add node kinds and adapters, not parallel stores.

**System-level behavior change (when implemented)**:

- The running API will serve reads and writes through a documented contract: create or upsert nodes, attach typed edges, list by kind and filters, and project subgraphs for UI and automation.
- Observability: friction and task events can correlate to the same node ids as domain entities, shrinking “investigate failed output” loops.

---

## Requirements

- [ ] **Canonical identity**: Every persisted record exposed as an API resource MUST be representable as `node_id` (UUID or repo-standard string) with `kind`, `created_at`, `updated_at`, and `payload` (JSON object) metadata.
- [ ] **Edges first-class**: Relationships MUST be `edge_id`, `from_node_id`, `to_node_id`, `rel_type`, optional `weight` or `metadata`, with indexes suitable for “neighbors of kind X” queries.
- [ ] **Adapter boundary**: SQLAlchemy (or unified store per spec 118) remains the physical store; the **logical** model is node and edge. No new parallel JSON file stores for entities covered by this spec.
- [ ] **Backward compatibility**: Existing tables MAY map via views or repository mappers; migration is phased with feature flags or read-only dual-read where required.
- [ ] **Friction alignment**: Task and friction APIs SHOULD accept or emit `node_id` references where today only opaque strings exist, without breaking existing clients (additive fields).

## Out of scope

- Full migration of all legacy domains in one PR (phased implementation only).
- GraphQL or arbitrary recursive graph analytics in the first slice (cap depth and surface area first).
- Authorization and tenancy model beyond additive `node_id` references (follow-up spec).

---

## API changes (target contract)

### `POST /api/nodes`

**Request** (conceptual)

```json
{
  "kind": "idea",
  "payload": { "title": "Universal layer", "status": "draft" }
}
```

**Response 201**

```json
{
  "node_id": "uuid",
  "kind": "idea",
  "payload": {},
  "created_at": "2026-03-28T00:00:00Z",
  "updated_at": "2026-03-28T00:00:00Z"
}
```

### `POST /api/edges`

**Request**

```json
{
  "from_node_id": "uuid",
  "to_node_id": "uuid",
  "rel_type": "implements_spec"
}
```

**Response 201** — edge record with `edge_id`.

### `GET /api/nodes/{node_id}`

**Response 200** — full node; **404** if missing.

### `GET /api/nodes`

Query params: `kind`, `limit`, `cursor` (pagination contract TBD in implementation spec).

*Note: Exact paths may be prefixed under `/api/graph/` or merged with existing resources; this spec fixes the **shape**, not final URL naming.*

---

## Data model

```yaml
Node:
  node_id: string (UUID)
  kind: string   # e.g. idea, spec, task, friction_event
  payload: object
  created_at: datetime (UTC)
  updated_at: datetime (UTC)

Edge:
  edge_id: string (UUID)
  from_node_id: string
  to_node_id: string
  rel_type: string
  metadata: object
  created_at: datetime (UTC)
```

Physical mapping: tables `graph_nodes`, `graph_edges` (names illustrative) with FK integrity and indexes on `(kind)`, `(from_node_id, rel_type)`, `(to_node_id, rel_type)`.

---

## Files to Create/Modify

- `specs/universal-node-edge-layer.md` — normative contract and execution plan (this file).
- `api/app/routers/graph_nodes.py` — FastAPI routes for nodes and edges (implementation phase).
- `api/app/services/graph_service.py` — persistence and mapping to SQLAlchemy (implementation phase).
- `api/tests/test_graph_nodes.py` — contract tests for CRUD and idempotency (implementation phase).

## Acceptance Tests

- `api/tests/test_graph_nodes.py::test_create_node_returns_node_id` — POST node returns stable `node_id` and timestamps.
- `api/tests/test_graph_nodes.py::test_create_edge_links_nodes` — POST edge ties two existing nodes with `rel_type`.
- Manual validation: `curl -sS http://localhost:8000/api/health` then exercise new routes when implemented (document JSON fields in PR).

---

## Verification

```bash
# Spec quality gate for changed specs (run from repo root after staging or committing)
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD

# After implementation exists: lint and tests
cd api && .venv/bin/ruff check .
cd api && .venv/bin/pytest -v tests/test_graph_nodes.py
```

| Criterion | Proof artifact |
|-----------|------------------|
| Contract documented | This file plus OpenAPI snippet in implementation PR |
| Idempotent tests | pytest output shows passed tests for `test_graph_nodes.py` |
| No duplicate source of truth | Code search shows no new JSON entity stores for covered kinds |
| API smoke | `curl` to health plus new endpoints returns 2xx with JSON body containing `node_id` |

---

## Risks and Assumptions

- **Migration complexity**: Mapping legacy rows to nodes may be lossy if payloads differ. Mitigation: start read-only projection and dual-write behind flag.
- **Performance**: Deep graph queries can be expensive. Mitigation: cap depth, paginate, add indexes early.
- **Scope creep**: Refactoring all domains at once. Mitigation: phase 1 covers ideas and specs only; phase 2 covers tasks and friction.
- **Assumption**: Unified SQLite or Postgres strategy from spec 118 remains authoritative for durability.
- **Assumption**: Cheap executor runs must have explicit file lists and commands; ambiguous specs increase failed-tasks volume.

---

## Known Gaps and Follow-up Tasks

- [ ] Final URL namespace (`/api/nodes` versus nested under existing routers) — issue or task link when scheduled.
- [ ] Alembic migrations versus `ensure_schema` for graph tables — follow-up task.
- [ ] Authorization: which roles can create edges between which kinds — follow-up spec.

---

## Execution plan (verification-first)

**Rule**: No step advances without **concrete proof** (file path, command stdout/stderr excerpt, or API JSON fields). If proof is missing, **retry once** with the same command; then document a **blocker** in `.task-checkpoint.md` with exact error text.

### PLAN

**Options (2–3 approaches)**:

| Approach | Long-term tradeoff |
|----------|-------------------|
| A. New `graph_*` tables + dedicated router | Clear separation; extra migration; best for reuse. |
| B. Materialized views over existing tables only | Lowest migration risk; weaker uniform `payload` story. |
| C. JSON column in one “blob” table | Fast MVP; worst query/index story — **not chosen**. |

**Choice**: **A** — dedicated tables + thin services — best alignment with “single source of truth” and indexing for operators.

**Optimization intent**: Reduce **failed-tasks** (3130 events) by making contracts explicit before implementation; improve **friction** closure by linking outputs to `node_id`.

**Steps (each needs proof before next)**:

1. **Spec quality**: Run `python3 scripts/validate_spec_quality.py --base origin/main --head HEAD` — proof: exit code 0 + last 20 lines saved or pasted.
2. **Scope lock**: List `files_allowed` in a task card (separate commit or issue) — proof: file path + line range.
3. **Implement** (future): Migrations + routes + tests per task card — proof: `pytest` output, `ruff check` clean.

### PATCH

- **Lint failure**: Unblock: `cd api && .venv/bin/ruff check .` → fix implementation; **proof**: ruff stdout `All checks passed`.
- **Test failure**: Unblock: `cd api && .venv/bin/pytest -v --tb=short <listed tests>` — **proof**: `N passed` line; if flaky, rerun once, then open issue with seed + test name.
- **Missing env**: Unblock: copy `api/.env.example` → `api/.env`; set `DATABASE_URL` or in-memory — **proof**: `curl -s localhost:8000/api/health` returns `"status":"ok"` (or documented equivalent).
- **Stale branch / rebase**: Unblock: `git fetch origin main && git rebase origin/main` — **proof**: `git status` clean, `git log -1 --oneline`.
- **Flaky CI / network**: Unblock: re-run failed job once; if still fails, capture run URL + log excerpt — **proof**: pasted in checkpoint.
- **Missing tool**: Unblock: `cd api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` — **proof**: `which .venv/bin/python`.

### RUN

Commands for **this** spec-only deliverable (executor on agent machine):

```bash
# Append ignore rules (if not already present — idempotent check first)
grep -q '^\.task-\*$' .gitignore || printf '%s\n' '*.pyc' '__pycache__/' '.task-*' 'data/coherence.db' >> .gitignore

git add -A
git diff --cached --stat
git commit -m "spec(universal-node-edge-layer): node+edge layer spec and gitignore hygiene"
```

**Proof**: `git show --stat HEAD` shows commit with spec file and `.gitignore`.

### RESULT

**Done when**:

1. `specs/universal-node-edge-layer.md` exists, ≥500 characters of substantive spec content, sections Purpose / Requirements / API / Data model / Verification / Risks present.
2. Git commit contains spec + `.gitignore` update; `git diff --cached --stat` was used before commit.
3. Checkpoint file `.task-checkpoint.md` updated with completion note.

**Failure anticipation (two weeks out)**:

- **Degradation**: Implementers might bypass the layer and add quick SQL again → **guardrails**: `rg` / CI check for forbidden new JSON stores; friction metric “open investigations” trending up.
- **Degradation**: API shape drift vs this doc → **guardrails**: OpenAPI diff in PR, spec quality script.

**Proof of meaning for humans/operators**: Fewer opaque failures; task output links to stable ids; less time in “what failed and where” loops (maps to wasted minutes in friction analytics).

**Maintainability (quality-awareness)**:

- Before implementation, run hotspot tooling if available (`scripts/context_budget.py` on `api/app/services/`) to pick adapter insertion points; prefer one service module over scattered edits.

**Friction-category prioritization**:

1. **failed-tasks** (high ROI): Spec-first reduces wrong implementations → fewer CI burn cycles.
2. **friction**: Documented resolution paths per PATCH section.
3. **flow_unblock (spec stage)**: This file unblocks `universal-node-edge-layer` for implementation task cards.

---

## Task card (for implementation follow-up)

```yaml
goal: Introduce graph_nodes/graph_edges persistence and minimal CRUD API matching specs/universal-node-edge-layer.md
files_allowed: []  # to be filled when implementation is scheduled
done_when:
  - pytest passes for listed tests
  - ruff check passes
commands:
  - cd api && .venv/bin/pytest -v tests/test_graph_nodes.py
  - cd api && .venv/bin/ruff check .
constraints:
  - modify only files_allowed
  - no new JSON entity stores for kinds covered by this spec
```
