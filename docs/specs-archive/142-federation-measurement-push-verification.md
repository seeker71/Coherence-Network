# Spec 142: Federation Measurement Push — Verification & Production Readiness

## Purpose

Verify that Spec 131 (federation measurement push) is fully implemented, all tests pass, the migration is production-ready, and close the `flow_unblock` friction signal. This is a verification-only spec — no new code is written.

## Requirements

- [x] All 12 Spec 131 acceptance tests pass.
- [x] All 16 Spec 131 requirement checkboxes are marked `[x]`.
- [x] Migration SQL is idempotent (uses `IF NOT EXISTS`).
- [x] Smoke test for `compute_summaries()` with empty dir returns `[]`.
- [x] Spec 131 passes `validate_spec_quality.py`.
- [x] No regressions in federation test suite (excluding pre-existing spec-134 full-flow failure).

## Files to Create/Modify

- `specs/131-federation-measurement-push.md` — mark requirement checkboxes as complete
- `specs/142-federation-measurement-push-verification.md` — this verification plan (new)

## PLAN

### Intent

Optimize for **trust** and **operational reliability**: confirm that Spec 131 (federation measurement push) is fully implemented, all tests pass, the migration is production-ready, and the spec requirements checklist can be marked complete. This closes the `flow_unblock` signal for `federation-measurement-push` and reduces the `failed-tasks` friction category by ensuring no repeated CI failures from this feature.

### System-Level Behavior Change

After this plan executes:
- The `POST /api/federation/nodes/{node_id}/measurements` and `GET /api/federation/nodes/{node_id}/measurements` endpoints are verified functional against all 16 spec requirements.
- The `node_measurement_summaries` PostgreSQL migration is confirmed idempotent (`IF NOT EXISTS`).
- The client-side push service (`federation_push_service.py`) is verified to correctly aggregate, push, and track state.
- Spec 131 requirements checkboxes are marked `[x]` to signal completion.
- Downstream specs (133 aggregated visibility, 134 strategy propagation) have a verified data source.

### Approach Options

| # | Approach | Tradeoff |
|---|----------|----------|
| A | **Verify-and-close** — run tests, confirm migration, mark spec done | Lowest risk; no code changes; closes friction immediately |
| B | Add integration smoke test hitting a real DB | Higher confidence but requires DB fixture setup; deferred to follow-up |
| C | Add retention policy and push scheduling | Scope creep; explicitly out-of-scope in spec 131 |

**Selected: A** — Verify-and-close. The implementation is complete, tests pass, and the spec is well-defined. Adding more scope would introduce new failure modes without closing the current friction signal.

### Failure Anticipation (2-week degradation)

- **Risk**: Tests could become flaky if `datetime.now(timezone.utc)` drifts across test boundaries. *Guardrail*: Tests use relative timestamps with 1-hour margins; no sub-second sensitivity.
- **Risk**: Migration not applied on VPS after merge. *Guardrail*: Step 4 below includes explicit VPS migration verification command.
- **Risk**: Spec marked done but downstream spec 133 (`aggregated-visibility`) assumes data that never arrives because no node runs the push client. *Guardrail*: Spec 131 Known Gaps already documents this; push scheduling is a tracked follow-up.

### Proof of Meaning

For **operators**: fleet-wide telemetry becomes available via a verified, tested push path. Operators can see which providers perform well across nodes without manual data collection.
For **developers**: the spec-to-implementation loop for federation measurement push is closed with all checkboxes checked, preventing the idea from re-surfacing as a friction signal.

---

## PATCH

### Files Modified

1. `specs/131-federation-measurement-push.md` — Mark all 16 requirement checkboxes as `[x]` (done).

### No Code Changes

All implementation files already satisfy the spec:
- `api/app/routers/federation.py` — POST/GET endpoints implemented (lines 100-150)
- `api/app/services/federation_service.py` — `store_measurement_summaries()`, `list_measurement_summaries()` implemented
- `api/app/services/federation_push_service.py` — `compute_summaries()`, `push_to_hub()`, `load_last_push()`, `save_last_push()` implemented
- `api/app/models/federation.py` — All Pydantic models defined (lines 80-118)
- `api/app/db/migrations/add_node_measurement_summaries.sql` — Idempotent DDL with indexes
- `api/tests/test_federation_measurement_push.py` — 12 tests covering all acceptance criteria

---

## RUN

### Step 1: Run Spec 131 Tests

**Command:**
```bash
cd api && pytest -q tests/test_federation_measurement_push.py
```

**Proof:** Output contains `12 passed` and no failures/errors.

**Unblock (test failure):**
```bash
cd api && pytest -v tests/test_federation_measurement_push.py --tb=short 2>&1 | head -60
```
Fix the failing test's root cause (do NOT modify tests to force pass — per CLAUDE.md guardrails). Re-run until proof is present.

### Step 2: Run Full Federation Test Suite

**Command:**
```bash
cd api && pytest -q tests/test_federation*.py
```

**Proof:** All federation tests pass (no regressions from related specs 132, 133, 134).

**Unblock (import error / missing dependency):**
```bash
cd api && pip install -e ".[dev]" 2>&1 | tail -5
```
Then re-run.

### Step 3: Verify Migration Idempotency

**Command:**
```bash
grep -c "IF NOT EXISTS" api/app/db/migrations/add_node_measurement_summaries.sql
```

**Proof:** Output is `3` (one `CREATE TABLE IF NOT EXISTS`, two `CREATE INDEX IF NOT EXISTS`).

### Step 4: Verify Smoke Test — compute_summaries with Empty Dir

**Command:**
```bash
cd api && python -c "
from app.services.federation_push_service import compute_summaries
from pathlib import Path
import tempfile, os
d = Path(tempfile.mkdtemp())
assert compute_summaries(d, None) == [], 'Expected empty list for empty dir'
os.rmdir(d)
print('smoke OK')
"
```

**Proof:** Output is `smoke OK`.

### Step 5: Mark Spec Requirements Complete

**Action:** Edit `specs/131-federation-measurement-push.md` — change all `- [ ]` to `- [x]`.

**Proof:** `grep -c '\- \[x\]' specs/131-federation-measurement-push.md` outputs `16`.

### Step 6: Validate Spec Quality

**Command:**
```bash
python3 scripts/validate_spec_quality.py specs/131-federation-measurement-push.md
```

**Proof:** No errors reported (warnings acceptable).

**Unblock (script not found):**
```bash
ls scripts/validate_spec_quality.py || echo "SKIP: validator not present"
```

### Step 7 (Post-Merge, VPS): Apply Migration

**Command (on VPS):**
```bash
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network && docker compose exec postgres psql -U coherence -d coherence -f /app/api/app/db/migrations/add_node_measurement_summaries.sql'
```

**Proof:** Output contains `CREATE TABLE` or `already exists` (idempotent).

**Unblock (connection refused):**
```bash
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 'docker compose ps postgres'
```
If postgres is down: `docker compose up -d postgres`, wait 5s, retry.

---

## RESULT

### Acceptance Criteria

| # | Criterion | Proof |
|---|-----------|-------|
| 1 | All 12 spec tests pass | `pytest` output: `12 passed` |
| 2 | No federation test regressions | `pytest tests/test_federation*.py` all green |
| 3 | Migration is idempotent | 3x `IF NOT EXISTS` in SQL file |
| 4 | Smoke test passes | `smoke OK` output |
| 5 | All 16 spec requirements marked `[x]` | `grep` count = 16 |
| 6 | Spec quality validated | No errors from validator |

### Common Blocker Reference

| Blocker | Unblock Command | Proof |
|---------|----------------|-------|
| Lint failure | `cd api && ruff check --fix .` | Exit code 0 |
| Missing env var | `export OPENROUTER_API_KEY=test` | Tests don't need real key |
| Stale branch | `git fetch origin && git rebase origin/main` | Clean rebase, no conflicts |
| Flaky CI / network | Re-run; tests are fully offline (mocked httpx) | Same pass count |
| Missing tool dep | `cd api && pip install -e ".[dev]"` | Import succeeds |

### Maintainability Guidance

- **Hotspot**: `federation_push_service.py` — any change to SlotSelector JSON format (fields, nesting) breaks `compute_summaries()`. Guard: spec 131 Risks section documents this; add a schema version field if format evolves.
- **Drift risk**: New decision points added without push coverage. Guard: `compute_summaries()` auto-discovers all `*.json` files in store dir — no manual registration needed.
- **Recommendation**: When adding retention policies (Known Gap #3), add a `pushed_at < cutoff` DELETE with `RETURNING id` to verify row count, not a blind `TRUNCATE`.

### Friction Signal Resolution

- `flow_unblock` for `federation-measurement-push`: **CLOSED** — spec complete, implementation verified, requirements checked off.
- `failed-tasks` (severity=high): **REDUCED** — verified test suite passes; no CI-heavy rework needed for this feature.
- `friction` (severity=high): **ADDRESSED** — documented resolution with proof artifacts.

## Verification

```bash
cd api && pytest -q tests/test_federation_measurement_push.py
grep -c '\- \[x\]' specs/131-federation-measurement-push.md  # expect 16
python3 scripts/validate_spec_quality.py --file specs/131-federation-measurement-push.md
```

## Out of Scope

- New feature code or endpoint changes.
- Retention policies for measurement summaries.
- Push scheduling automation (cron/systemd).
- Fixing pre-existing spec-134 `advisory_only` field test failure in `test_federation_full_flow.py`.

## Risks and Assumptions

- **Risk**: VPS migration not applied after merge. *Mitigation*: Step 7 provides explicit SSH command with idempotent SQL.
- **Assumption**: Pre-existing `test_federation_full_flow.py` failure is a spec-134 issue (missing `advisory_only` in strategy compute response), not a spec-131 regression.

## Known Gaps and Follow-up Tasks

- Follow-up: Fix `advisory_only` field in strategy compute endpoint (spec 134 scope).
- Follow-up: Add automated push scheduling (cron or systemd timer) for `federation_push_service`.
- Follow-up: Retention policy for `node_measurement_summaries` table (prune old rows).
