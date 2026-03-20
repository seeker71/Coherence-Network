# Coherence Network — Engineering Workbook

> Last updated: 2026-03-20T07:15Z
> Status: **Portfolio 100% validated — hardening + spec quality upgrade phase**

---

## 1. System Status

| Metric | Value |
|---|---|
| Ideas | 19/19 validated (1,170/1,172 CC) |
| Specs on disk | 119 |
| Specs in DB | 119/119 linked to ideas (100%) |
| Evidence records | 306 (302 linked to ideas, 99%) |
| Standing questions | 8/8 answered (100%) |
| Content hashes | 401 verified, 0 mismatched |
| Test files | 85 (~930 tests) |
| API services | 77 |
| API routers | 32 |
| Web pages | 26 |
| CI workflows | 14 |

---

## 2. Architecture Review — Improvement Backlog

### Legend
- `[ ]` not started | `[~]` in progress | `[x]` done
- Effort: **S** (<2hr) | **M** (2-8hr) | **L** (1-3 days)

### 2.1 CRITICAL — Blocks production use

| # | Issue | Effort | Status |
|---|---|---|---|
| C1 | **No auth on mutating endpoints** — governance, federation, ideas all unprotected. Voter identity self-asserted. | M | [ ] |
| C2 | **Federation trust model is hollow** — `public_key`/`signature` defined but never verified. `trust_level` stored but never checked. | L | [ ] |
| C3 | **SQLite DB committed to git** — binary can't merge, concurrent branches lose data, bloats history. | S | [ ] |
| C4 | **DELETE-ALL + INSERT-ALL on every save** — `idea_registry_service.py:204-206` races under concurrent requests. | M | [ ] |

### 2.2 HIGH — Significant reliability

| # | Issue | Effort | Status |
|---|---|---|---|
| H1 | **SQL injection pattern** — `f"ALTER TABLE ... ADD COLUMN {name} {ddl}"` in `spec_registry_service.py:122`. | S | [ ] |
| H2 | **JSON file stores with no locking** — value_lineage and federation use read-modify-write on JSON. | M | [ ] |
| H3 | **`datetime.utcnow()` in 36 places** — deprecated, timezone-naive. | S | [ ] |
| H4 | **Monster service files** — `automation_usage_service.py` (6,684 lines), `inventory_service.py` (5,972 lines). | L | [ ] |
| H5 | **83 silent `except Exception:` handlers** — DB failures return empty lists, masking real errors. | M | [ ] |
| H6 | **Engine created per call** in `_contribution_metadata_idea_ids()` — bypasses unified_db. | S | [ ] |

### 2.3 MEDIUM — Engineering practice

| # | Issue | Effort | Status |
|---|---|---|---|
| M1 | No rate limiting on any endpoint. | S | [ ] |
| M2 | Health check doesn't verify DB connectivity. | S | [ ] |
| M3 | Governance auto-approves on 1 self-asserted vote. | M | [ ] |
| M4 | `_read_ideas()` has write side effects on GET requests. | M | [ ] |
| M5 | Module-level caches with no thread safety. | S | [ ] |
| M6 | 6 leftover SQLite DBs despite "unified DB" claim. | M | [ ] |
| M7 | No API versioning strategy. | S | [ ] |
| M8 | README missing setup steps. | S | [ ] |

### 2.4 LOW — Polish

| # | Issue | Effort | Status |
|---|---|---|---|
| L1 | CORS defaults to `localhost:3000`. | S | [ ] |
| L2 | `@app.on_event("startup")` deprecated. | S | [ ] |
| L3 | `DEFAULT_STAGE_WEIGHTS` sum to 1.35, not 1.0. | S | [ ] |
| L4 | Duplicate HealthResponse/ReadyResponse models. | S | [ ] |
| L5 | No tests for concurrent access patterns. | M | [ ] |

---

## 3. Spec & Idea Quality Audit

> **Goal**: Ideas generate specs with high accuracy. Specs generate tests that validate ALL functionality (golden path, fallbacks, retries). No workarounds, no placeholders.

### 3.0 Key Findings

| Metric | Current | Target |
|---|---|---|
| Ideas with `contributing_specs: []` | **8 of 19 (42%)** | 0 |
| Specs under mega-catchall `api-runtime` | **100 of 119 (84%)** | <20 |
| Specs with error/retry/fallback behavior | **25 of 119 (21%)** | 119 |
| Specs with Risks/Known Gaps section | **35 of 119 (29%)** | 119 |
| Specs with named acceptance tests | **87 of 119 (73%)** | 119 |
| Specs with API Contract section | **82 of 119 (69%)** | 119 |
| Specs with Verification commands | **48 of 119 (40%)** | 119 |
| Referenced test files that don't exist | **14** | 0 |
| Spec quality level matching 112-119 gold standard | **8 of 119 (7%)** | 119 |

**The child-idea specs (112-119) are the gold standard.** They have Research Inputs, Task Cards, named acceptance tests, API contracts, data models, and Failure/Retry Reflection. Elevating the other 111 specs to that level is the single highest-leverage improvement.

### 3.1 Idea → Spec Generation Readiness

| idea_id | type | specs linked | can generate specs? | what's missing |
|---|---|---|---|---|
| `oss-interface-alignment` | super | 0 | ❌ | contributing_specs=[], no rollup acceptance criteria |
| `portfolio-governance` | super | 0 | ❌ | contributing_specs=[], children have specs but parent doesn't reference them |
| `community-project-funder-match` | super | 0 | ❌ | contributing_specs=[], no API endpoint list, no data flow |
| `coherence-network-agent-pipeline` | super | 0 (children have 11) | ⚠️ | Good child coverage, but super description doesn't enumerate capabilities |
| `coherence-network-api-runtime` | standalone | **100** (mega-catchall) | ❌ | 84% of all specs dumped here. Needs decomposition into 6-8 sub-ideas |
| `coherence-network-value-attribution` | standalone | 2 | ⚠️ | Governance integration untested, payout approval path missing |
| `coherence-network-web-interface` | standalone | 1 | ❌ | Only 1 spec (093). Other web specs (075,076,091,092) misrouted to api-runtime |
| `coherence-signal-depth` | child | 0 | ❌ | Spec 115/116 reference it but linked to other ideas |
| `federated-instance-aggregation` | child | 0 | ❌ | Spec 120 linked to api-runtime, not this idea. Misclassification |
| `deployment-gate-reliability` | standalone | 0 | ❌ | No specs linked despite 14 CI workflows |
| `interface-trust-surface` | child | 0 | ⚠️ | Has 12 tests but no specs linked |
| `minimum-e2e-path` | child | 2 | ✅ | Good: 2 specs, 7 tests, well-scoped |
| `funder-proof-page` | child | 1 | ✅ | Good: 37 tests |
| `idea-hierarchy-model` | child | 1 | ✅ | Good: 24 tests |
| `unified-sqlite-store` | child | 1 | ✅ | Reasonable coverage |
| `agent-prompt-ab-roi` | child | 2 | ✅ | 9 tests, good spec quality |
| `agent-failed-task-diagnostics` | child | 4 | ✅ | 8 tests, good variety |
| `agent-auto-heal` | child | 3 | ✅ | 7 tests |
| `agent-grounded-measurement` | child | 2 | ✅ | **Best**: 40 tests, excellent spec quality |

**Summary**: 8/19 ideas can generate specs (all are child-ideas with explicit contributing_specs). The 4 super-ideas and 7 standalone/unlinked ideas cannot.

### 3.2 Spec → Test Generation Readiness

**Gold standard (can generate complete tests from spec alone):**

| Spec | Why it works |
|---|---|
| 112-prompt-ab-roi | API contract, data model, named tests, error handling, retry reflection |
| 113-failed-task-diagnostics | Named tests, API contract, data model, error categories |
| 114-auto-heal | Strategy map, API contract, named tests, retry guard |
| 115-grounded-cost-value | Detailed formulas, edge cases, raw signal storage |
| 116-grounded-idea-metrics | Formulas, grounding sources, acceptance criteria |
| 117-idea-hierarchy | Rules, decomposition table, acceptance criteria |
| 119-coherence-credit | Task card, named tests, data models |

**Cannot generate tests (missing too much):**

| Count | What's missing |
|---|---|
| 94 specs (79%) | No error/retry/fallback behavior specified |
| 84 specs (71%) | No Risks and Known Gaps section |
| 71 specs (60%) | No Verification section with pytest commands |
| 37 specs (31%) | No API Contract section |
| 32 specs (27%) | No acceptance tests section at all |

### 3.3 Placeholder / Workaround Inventory

| Pattern | Files | Count | Risk |
|---|---|---|---|
| `return []` / `return {}` / `return None` fallbacks | `automation_usage_service.py`, `release_gate_service.py`, `inventory_service.py` | 96 total | Masks real errors as empty data |
| Bare `pass` in except blocks | `grounded_idea_metrics_service.py`, `automation_usage_service.py` | 12 | Silent error swallowing |
| Referenced test files that don't exist | 14 files across 12 specs | 14 | Specs claim coverage that isn't there |

**Missing test files** (referenced in specs but don't exist):
`test_agent.py`, `test_api_error_handling.py`, `test_cursor_e2e.py`, `test_dual_write_mode.py`, `test_gates_api.py`, `test_placeholder.py`, `test_postgres_agent_task_store.py`, `test_postgres_graph_store.py`, `test_project_manager_pipeline.py`, `test_projects.py`, `test_read_switchover.py`, `test_resource.py`, `test_rollback.py`, `test_update_spec_coverage.py`

### 3.4 Untested Public Functions

| Service | Public funcs | Tested | Untested | Gap |
|---|---|---|---|---|
| `governance_service.py` | 5 | 2 | `list_change_requests`, `get_change_request`, `create_change_request` | **Worst coverage** |
| `idea_service.py` | 11 | 9 | `select_idea`, `list_tracked_idea_ids` | Minor gaps |
| `value_lineage_service.py` | 9 | 8 | `checkpoint` | Minor |
| `federation_service.py` | 6 | 6 | — | ✅ Full |
| `auto_heal_service.py` | 2 | 2 | — | ✅ Full |
| `coherence_credit_service.py` | 7 | 7 | — | ✅ Full |

### 3.5 What Must Change for Self-Generating Ideas → Specs → Tests

**The upgrade path (in priority order):**

| # | What | Why | Effort |
|---|---|---|---|
| SQ1 | **Decompose `coherence-network-api-runtime`** into 6-8 sub-ideas (API foundation, pipeline automation, web UI, deployment/CI, monitoring, infrastructure) | 100 specs under one idea makes classification useless | M |
| SQ2 | **Fix spec-to-idea linkage** for 8 unlinked ideas — populate `contributing_specs`, fix spec 120 misclassification | Ideas can't generate specs they don't know about | S |
| SQ3 | **Add error/retry/fallback to 94 specs** — follow the 112-119 Failure/Retry Reflection pattern | Without this, generated tests only cover golden path | L |
| SQ4 | **Add Risks/Known Gaps to 84 specs** | Required by CLAUDE.md guardrails, needed for risk-aware generation | M |
| SQ5 | **Add Verification sections to 71 specs** | Generator needs `pytest` commands to wire CI | S |
| SQ6 | **Create 14 missing test files** referenced by specs | Specs claim coverage that isn't real | M |
| SQ7 | **Standardize all specs to 112-119 template** — add Research Inputs, Task Card, API Contract, Failure/Retry Reflection | The 112-119 pattern is proven machine-readable | L |
| SQ8 | **Add input validation rules to all API specs** — min/max lengths, allowed values, required fields | Without constraints, generated tests can't validate inputs | M |
| SQ9 | **Add concurrent access behavior to 115 specs** | Only 4 specs (3%) mention concurrency | M |
| SQ10 | **Add super-idea rollup criteria** — each super-idea needs: "validated when all children validated AND [rollup condition]" | Super-ideas can't self-assess completion | S |

---

## 4. Execution Plan

### Phase 1: Stop the bleeding (Week 1)
1. [ ] Auth middleware on all mutating endpoints (C1)
2. [ ] Remove `coherence.db` from git tracking (C3)
3. [ ] Replace `datetime.utcnow()` globally (H3)
4. [ ] Add exception logging to silent catches (H5)

### Phase 2: Data integrity (Week 2)
5. [ ] Fix delete-all/insert-all save pattern (C4)
6. [ ] Migrate JSON stores to unified DB (H2)
7. [ ] Add rate limiting (M1)
8. [ ] DB connectivity in health check (M2)

### Phase 3: Spec quality upgrade (Week 2-3)
9. [ ] Decompose `api-runtime` into 6-8 sub-ideas (SQ1)
10. [ ] Fix spec-to-idea linkage for 8 ideas (SQ2)
11. [ ] Add error/retry/fallback to 94 specs (SQ3)
12. [ ] Add Risks/Known Gaps to 84 specs (SQ4)
13. [ ] Add Verification sections to 71 specs (SQ5)
14. [ ] Create 14 missing test files (SQ6)

### Phase 4: Hardening (Week 3)
15. [ ] Federation crypto/trust gates (C2)
16. [ ] Governance identity verification (M3)
17. [ ] Thread-safe caches (M5)
18. [ ] Separate read/write in idea_service (M4)

### Phase 5: Maintainability (Week 4+)
19. [ ] Standardize all specs to 112-119 template (SQ7)
20. [ ] Decompose monster files (H4)
21. [ ] Clean up leftover DBs (M6)
22. [ ] Complete README (M8)
23. [ ] Add input validation rules to specs (SQ8)
24. [ ] Add concurrent access behavior to specs (SQ9)

---

## 5. Session Log

### 2026-03-20 — Session 1

**PRs merged (8):**

| PR | What |
|---|---|
| #463 | CC currency + DB source of truth + grounded ROI |
| #464 | A/B selection methods (free_energy vs marginal_cc) |
| #465 | Stochastic selection (softmax + temperature) |
| #466 | Full-fidelity seeding + CC scoring + zero fixes |
| #467 | Close top 10 ideas + eliminate seed_ideas.json |
| #468 | Close 6 more ideas + honest progress on 2 |
| #469 | Federation layer + interface parity — portfolio 100% |
| #470 | Close all data gaps: 119 specs + 302 evidence linked |

**Key decisions:**
- DB committed to git as single source of truth (with content hashes)
- Coherence Credit (CC) as internal unit of account (1 CC = 1K tokens)
- Softmax-weighted stochastic idea selection with temperature control
- Federation goes through governance (no trust-free data injection)
- All ideas re-grounded from real codebase evidence

**Reviews completed:**
1. Architecture review: 23 issues (4 critical, 6 high, 8 medium, 5 low)
2. Spec/idea quality audit: 10 improvements needed for self-generating specs
3. Workbook created with full backlog and execution plan

---

## 6. What's Next

**Immediate (next prompt):**
- Start Phase 1 execution: auth middleware (C1) is the #1 priority
- Or start spec quality upgrade (SQ1-SQ2) if the goal is self-generating specs first

**The key strategic question:**
> Do we harden the runtime first (Phase 1-2: auth, save pattern, JSON→DB) or upgrade spec quality first (Phase 3: decompose api-runtime, fix linkage, add error/retry to 94 specs)?

Hardening makes the system safe to run. Spec quality makes the system rebuildable from ideas alone. Both are needed — the question is which unblocks more value first.

**Recommendation:** Start with SQ1-SQ2 (decompose api-runtime + fix linkage) because they're small effort and immediately make the idea→spec→test pipeline functional for 11 more ideas. Then do C1 (auth) because it's the #1 production blocker.
