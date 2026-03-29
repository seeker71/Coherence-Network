# Review: Spec 180 — Submit to 5+ MCP and Skill Registries for Discovery

**Task:** task_8d9f2114e2f980f5
**Spec:** 180-mcp-skill-registry-submission
**Reviewer:** claude (reviewer agent)
**Date:** 2026-03-28
**Verdict:** REVIEW_FAILED

---

## Executive Summary

Spec 180 has a prior implementation attempt (`0fbfebb`) that is substantively
correct but is an **orphaned git commit** — not on any branch, never merged
to `main`, and not deployed to production. The current worktree (`worker-main`)
contains an older version of the registry service with wrong registry IDs.
Production fails all five verification scenarios from the spec.

---

## Verification Scenario Results

All scenarios were run against `https://api.coherencycoin.com` (deployed SHA
`46b10d8cb6dd71caf416d7badff1ebfe9614fba8`).

### Scenario 1 — All six registry IDs appear in submission inventory

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-submissions
```

**Expected:** HTTP 200, JSON with six items including `smithery`, `glama`,
`pulsemcp`, `mcp-so`, `skills-sh`, `askill-sh`.

**Actual:** `{"detail":"Not Found"}` — HTTP 404.

**Result: FAIL** — endpoint not registered in production.

---

### Scenario 2 — `core_requirement_met = true`

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-submissions | \
  <extract summary.core_requirement_met>
```

**Actual:** 404 (endpoint missing).

**Result: FAIL** — cannot evaluate.

---

### Scenario 3 — Stats endpoint source labels

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-stats
```

**Actual:** HTTP 404 — endpoint not present.

**Result: FAIL** — endpoint not implemented in deployed API.

---

### Scenario 4 — Cache refresh behaviour

**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats?refresh=true"
```

**Actual:** HTTP 404.

**Result: FAIL** — endpoint not present.

---

### Scenario 5 — Dashboard merges submission + stats

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-dashboard
```

**Actual:** HTTP 404.

**Result: FAIL** — endpoint not present.

---

## Root Cause Analysis

### 1. Implementation commit is orphaned (BLOCKER)

Commit `0fbfebb` was created with all spec-180 changes but was never pushed to
a named branch and no PR was opened:

```
git branch -a --contains 0fbfebb
# → remotes/origin/worker/impl/idea-4deb5bd7c800/task_b1e   (wrong branch)
# The commit appears in --all log but has no usable branch reference
```

`origin/main` is at `39b25f0`. Commit `0fbfebb` is not reachable from `main`.

### 2. Worker-main has old registry targets (BLOCKER)

Current `api/app/services/registry_discovery_service.py` in `worker-main`
contains these registry IDs:
- `modelcontextprotocol-registry` ← not in spec-180
- `npm` ← not in spec-180
- `smithery` ← correct
- `mcp-so` ← correct
- `clawhub` ← not in spec-180
- `agentskills` ← not in spec-180

Spec-180 requires: `smithery`, `glama`, `pulsemcp`, `mcp-so`, `skills-sh`, `askill-sh`.

Missing: `glama`, `pulsemcp`, `skills-sh`, `askill-sh`.

### 3. `registry_stats_service.py` missing from worktree (BLOCKER)

The file `api/app/services/registry_stats_service.py` does not exist in the
current worktree. Only a `.pyc` bytecode file is present from a previous test
run on a different checkout. The new endpoints (`/registry-stats`,
`/registry-dashboard`) depend on this service.

### 4. Router only exposes one endpoint (BLOCKER)

Current `api/app/routers/registry_discovery.py` only registers:
```
GET /discovery/registry-submissions
```

It does not register `/registry-stats` or `/registry-dashboard`.
Both are required by AC3, AC4, AC5, AC6.

---

## What IS Correct (Positive Findings)

These items are properly implemented in the current worktree:

| Item | Status |
|------|--------|
| `mcp-server/server.json` | Present, valid MCP manifest with `$schema`, npm package |
| `mcp-server/glama.json` | Present with correct fields (`name`, `description`, `url`, `homepage`, `license`, `tags`, `install`) |
| `mcp-server/package.json` | Present with `name: coherence-mcp-server`, `bin` entry |
| `mcp-server/README.md` | Present |
| `skills/coherence-network/SKILL.md` | Present with `name: coherence-network`, `metadata:`, `cc inbox` reference |
| Spec 180 itself | Well-formed, complete, has all required sections |
| Orphaned impl commit `0fbfebb` | Code quality is good — correct models, service, router, 793-line test file |

The orphaned implementation would likely pass all tests if extracted onto a branch.

---

## Required Fixes Before Re-Review

### Fix 1 — Extract orphaned commit and create a PR

The orphaned commit chain (`022dc32` → `1ca65e7` → `0fbfebb`) contains the
full implementation. It must be cherry-picked or rebased onto a branch and a
PR opened.

```bash
# Example recovery:
git checkout -b fix/spec-180-registry worker-main
git cherry-pick 022dc32  # spec
git cherry-pick 1ca65e7  # tests
git cherry-pick 0fbfebb  # impl
# Resolve any conflicts from rebase onto current worker-main
# Then push and open PR
```

### Fix 2 — Verify registry IDs match spec-180

After applying the cherry-picks, confirm `_TARGETS` contains exactly:
`smithery`, `glama`, `pulsemcp`, `mcp-so`, `skills-sh`, `askill-sh`.

### Fix 3 — Verify `registry_stats_service.py` is present

The service must exist as a Python source file (not just `.pyc`).

### Fix 4 — Verify router registers all three endpoints

```python
# Expected in registry_discovery.py after fix:
GET /discovery/registry-submissions
GET /discovery/registry-stats
GET /discovery/registry-dashboard
```

### Fix 5 — Deploy and re-run verification scenarios

After merging to `main`, deploy to VPS and re-run all five verification
scenarios from the spec. Only then can this review pass.

---

## Registry Asset Readiness (Current State)

These assets exist and would satisfy submission requirements:

| Registry | Required Assets | Status |
|----------|----------------|--------|
| Smithery | `server.json`, `package.json`, `README.md` | Ready |
| Glama | `glama.json`, `server.json`, `package.json` | Ready |
| PulseMCP | `server.json`, `package.json`, `README.md` | Ready |
| MCP.so | `server.json`, `package.json`, `README.md` | Ready |
| skills.sh | `skills/coherence-network/SKILL.md`, `README.md` | Ready (pending `README.md` skill section) |
| askill.sh | `skills/coherence-network/SKILL.md`, `README.md` | Ready (pending `README.md` skill section) |

Note: the README.md's `## Skills` section referencing `clawhub install coherence-network`
may not be present — this must be verified.

---

## Open Questions Addressed

**Q: How can we improve this idea, show whether it is working yet, and make
that proof clearer over time?**

1. **Immediate**: The API-based proof is the right approach. Once deployed,
   `GET /api/discovery/registry-submissions` with `core_requirement_met = true`
   is a concrete, machine-verifiable proof that assets are in place.

2. **Short-term**: Integrate a weekly cron calling `/registry-stats?refresh=true`
   and log counts to PostgreSQL. A monotonically increasing `total_installs`
   is the clearest possible external validation signal.

3. **Medium-term**: Build the `/discovery` dashboard page (Spec 181) so the
   human-visible proof matches the machine-verifiable proof — color-coded
   badges, status per registry, sparkline for counts.

4. **For PR submissions**: Add a `notes` field to each registry record tracking
   the PR URL once submitted. This closes the loop between "assets ready" and
   "submission made".

5. **Discovery gap**: There is currently no tracking of *actual PR submission*
   to Glama's `awesome-mcp-servers`, PulseMCP catalog, `skills.sh`, or
   `askill.sh`. The asset-readiness check proves the repo is ready; it does
   not prove the PR was sent or accepted.

---

## Acceptance Criteria Check

| # | Criterion | Status |
|---|-----------|--------|
| AC1 | `registry-submissions` returns six spec-180 registry IDs | FAIL — 404 in prod |
| AC2 | `core_requirement_met = true` when assets present | FAIL — 404 |
| AC3 | `registry-stats` returns items with valid `source` labels | FAIL — 404 |
| AC4 | `?refresh=true` forces live fetch | FAIL — 404 |
| AC5 | Upstream failure → HTTP 200, `source: unavailable` | FAIL — 404 |
| AC6 | `registry-dashboard` → HTTP 200 even if stats fail | FAIL — 404 |
| AC7 | `mcp-server/glama.json` exists and is valid | PASS — file present, valid JSON |
| AC8 | Six registry validators in `registry_discovery_service.py` | FAIL — current has 4 wrong IDs |
| AC9 | Tests cover happy-path + failure modes | PARTIAL — tests exist in orphaned commit but not in worktree |

**Pass: 1/9 | Fail: 7/9 | Partial: 1/9**

---

## REVIEW_FAILED

The implementation work was done correctly in commit `0fbfebb` but it was
never landed on a reachable branch, never merged to main, and was never
deployed. All five production verification scenarios fail with 404. The single
passing acceptance criterion (AC7 — glama.json exists) is insufficient.

**Rework required:**
1. Recover the orphaned commit chain onto a branch
2. Open and merge a PR
3. Deploy to production
4. Re-run all verification scenarios
5. Request re-review

