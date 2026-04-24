# External Enablement Tracking Sheet

What needs work, what's done, what's next.

## External Proof — Public API Lifecycle

`scripts/external_proof_demo.py` exercises the full idea lifecycle from outside the monorepo using only `requests`, `COHERENCE_API_URL`, and `COHERENCE_API_KEY`. The script is the living proof; this section is the human-readable audit trail. Update after each manual run or via CI.

| Field | Value |
|-------|-------|
| Last passing run | 2026-04-24 — initial landing, dry-run verified |
| API base URL | https://api.coherencycoin.com |
| CI workflow | [`.github/workflows/external-proof.yml`](../.github/workflows/external-proof.yml) |
| Script | [`scripts/external_proof_demo.py`](../scripts/external_proof_demo.py) |

Endpoints exercised per run:

- `POST /api/ideas` — create the test idea, expect `id` + `stage`
- `PATCH /api/ideas/{id}/stage` — advance to `spec`
- `POST /api/contributions` — record a minimal contribution
- `GET /api/coherence/{id}` — read score, assert float in `[0, 1]`
- `PATCH /api/ideas/{id}/stage` — archive the test idea (cleanup)

### Running locally

```bash
# Dry run (no HTTP, safe default)
python3 scripts/external_proof_demo.py --dry-run

# Real run against prod
export COHERENCE_API_URL=https://api.coherencycoin.com
export COHERENCE_API_KEY=<real-key>
python3 scripts/external_proof_demo.py

# Against local dev
COHERENCE_API_URL=http://localhost:8000 COHERENCE_API_KEY=dev-key python3 scripts/external_proof_demo.py
```

### Key rotation procedure

1. Generate new key via the deployment's key provisioning path
2. Update `COHERENCE_API_KEY` in **GitHub → Settings → Secrets and variables → Actions**
3. Revoke the old key
4. Manually trigger the `External proof` workflow to verify the new key works

## Open Work

### Credential Routing (enables multi-contributor task execution)

| Step | Task | Status | Files |
|------|------|--------|-------|
| 1 | `--repo` flag in local_runner.py — skip tasks if node lacks credentials for target repo | **done** | `api/scripts/local_runner.py` |
| 2 | Auto-filter: skip tasks for repos without credentials in `keys.json` (no flag needed) | **done** | `api/scripts/local_runner.py` |
| 3 | Write credential routing tests | **done** | `api/tests/test_flow_enforcement.py` |

**Context**: DB schema + CRUD endpoints + CLI `coh credentials` already exist. Runner now filters tasks by repo credentials (both explicit `--repo` flag and automatic credential check).

### Planned Features (priority order)

| # | Feature | Description | Effort |
|---|---------|-------------|--------|
| 1 | **Mission control surface** | `/mission-control` consolidating pipeline, diagnostics, gates, usage, tasks into one view. | Large |
| 2 | **Goal-to-execution model** | Wire ideas/specs as operational goals with task groups, owners, budget envelopes. | Large |
| 3 | **Approvals & budget board** | Single board for governance requests, deploy gates, needs_decision tasks, spend pressure. | Medium |
| 4 | **Adapters catalog** | First-class surface for providers, federation nodes, Discord/Telegram, deploy gates. | Medium |
| 5 | **Guided onboarding** | Beginner-friendly setup flow with deployment presets (local/private/public). | Medium |
| 6 | **CLI mission control parity** | `coh mission-control`, `coh approvals`, `coh budgets`, `coh adapters`. | Medium |
| 7 | **Anomaly self-heal policies** | Orphaned tasks, stale runners, deploy drift → automatic recovery policies. | Large |

### Coverage Gaps

**Web pages missing:**

| Page | Spec | Priority |
|------|------|----------|
| /federation | 120 | Medium |
| /marketplace | 121 | High |
| /graphs | 166 | Medium |
| /measurements | 131 | Low |
| /strategies | 134 | Low |

**CLI commands missing:**

| Command | Spec | Priority |
|---------|------|----------|
| coh marketplace | 121 | High |
| coh graph | 166 | Medium |
| coh onboarding | 168 | Medium |
| coh invest | 157 | Low |
| coh measurements | 131 | Low |
| coh strategies | 134 | Low |

## Completed

### Infrastructure (all specs implemented & deployed)

| Spec | Title | Status |
|------|-------|--------|
| 119 | Coherence Credit (CC) | done |
| 120 | Minimum Federation Layer (6 routes) | done |
| 121 | OpenClaw Idea Marketplace (5 routes) | done |
| 131 | Federation Measurement Push | done |
| 132 | Federation Node Identity | done |
| 133 | Federation Aggregated Visibility | done |
| 134 | Federation Strategy Propagation | done |
| 137 | Node Capability Discovery | done |
| 148 | Coherence CLI (35+ commands) | done |
| 149 | OpenClaw Inbox Session Protocol | done |
| 166 | Universal Node+Edge Layer (19 routes) | done |
| 167 | Social Platform Bots (Discord) | done |
| 168 | Identity-Driven Onboarding TOFU | done |
| 048 | Value Lineage | done |

### Operational Features (all shipped)

| Feature | Description | Status |
|---------|-------------|--------|
| Context budget instrumentation | Tasks annotated with 0-100 hygiene score | done |
| Lean task-card enforcement | Soft gates (file scope, task card, direction) + hard limit (40 files) | done |
| Compact summaries | Summarize large outputs; fetch raw on drilldown | done |
| Tool overhead controls | Auto-prune guard_agents for simple tasks | done |
| Blueprint royalties | Contributors earn CC on blueprint use | done |
| Guide discovery | `coh guides` surfaces top creators | done |
| Skill synthesis | Completed tasks → procedural Skill nodes | done |
| Procedural memory API | Query previous successes before starting work | done |
| Diagnostics console | `/diagnostics` with config editor, workbench, context budget | done |
| CLI ops surface | `coh ops`, `coh config`, task-log drilldown, runner control | done |
| JSON-backed settings | Replaced env-driven config with shared JSON config | done |
| Auto-deploy | GitHub Actions → Hostinger VPS deployment | done |
| Test suite overhaul | 3,244 → 163 flow-centric tests (7s runtime) | done |
| Credential CRUD | DB schema, API endpoints, `coh credentials` CLI | done |

### Per-Contributor Credential Model

| Field | Type | Description |
|-------|------|-------------|
| `contributor_id` | FK | Who owns the credential |
| `repo_url` | string | Which repo (e.g., `github.com/seeker71/Coherence-Network`) |
| `credential_type` | enum | `github_token`, `ssh_key`, `pat` |
| `credential_hash` | string | SHA-256 hash (raw never stored in DB) |
| `scopes` | JSON | `["push", "pull", "pr_create", "pr_merge"]` |
| `status` | enum | `active`, `expired`, `revoked` |

Raw tokens live in `~/.coherence-network/keys.json` under `repo_tokens`. DB stores metadata only.

## Dependency Graph

```
119 (CC) ─── 120 (Federation) ─── 132 (Node Identity) ─── 137 (Capability Discovery)
              │                    ├── 131 (Measurement Push) ─── 133 (Aggregated Visibility)
              │                    │                              └── 134 (Strategy Propagation)
              └── 121 (Marketplace)

148 (CLI) ─── 149 (Inbox Protocol)
              ├── 167 (Social Bots)
              └── 168 (Identity TOFU)

166 (Universal Node+Edge) ─── foundation for all above
```

## Quick Commands

```bash
# Run tests
cd api && pytest tests/ -v --ignore=tests/holdout

# Build web
cd web && npm run build

# Deploy to VPS
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network/repo && git pull origin main && \
   cd /docker/coherence-network && docker compose build --no-cache api web && \
   docker compose up -d api web'

# Verify
curl -sS https://api.coherencycoin.com/api/health | python3 -m json.tool
```
