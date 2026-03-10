# Coherence Network — Status

> Implementation status for the active execution scope.

## Current State

### Phase Visibility

- Milestone Tag: **A** (Core Stability)
- Progress source: [`docs/SPEC-TRACKING.md`](SPEC-TRACKING.md)

| Area | Status |
|------|--------|
| API baseline and health endpoints | ✅ Complete |
| Graph indexing + project retrieval | ✅ Complete |
| Coherence endpoint support | ✅ Complete |
| Import stack support (lockfile + requirements) | ✅ Complete |
| Agent orchestration endpoints | ✅ Complete |
| Production deployment | ⚠️ Blocked (Railway account/project unavailable) |
| Pipeline monitoring + attention workflow | 🚧 In progress |
| Full unattended effectiveness loop | 🚧 In progress |

## Public Deployments

| Service | Platform | URL | Status |
|---------|----------|-----|--------|
| API | Railway (previous) | https://coherence-network-production.up.railway.app | ❌ Unavailable (`Application not found`, verified 2026-03-09) |
| Web | Railway web (previous) | https://coherence-web-production.up.railway.app | ❌ Unavailable (`Application not found`, verified 2026-03-09) |

### Deployment Health
- API health endpoint: ❌ Not reachable on previous Railway URL (HTTP 404)
- API ready endpoint: ❌ Not reachable on previous Railway URL (HTTP 404)
- Web root: ❌ Not reachable on previous Railway URL (HTTP 404)
- Web API health page: ❌ Not reachable on previous Railway URL (HTTP 404)
- CORS configuration: ⚙️ Pending new hosting cutover

## Specs Implemented (Selected)

- 001–005 core API/pipeline foundations
- 007–014 platform baseline and safeguards
- 016–025 holdout/web/coherence/import capabilities
- 027–028 pipeline automation structure
- 030, 032, 034, 035, 037–044 hardening and status features

See [SPEC-COVERAGE.md](SPEC-COVERAGE.md) and [SPEC-TRACKING.md](SPEC-TRACKING.md) for full mapping.

## Active Priorities

1. Improve pipeline effectiveness and issue resolution loop.
2. Keep status/coverage artifacts in sync with shipped behavior.
3. Continue graph + coherence quality improvements through scoped specs.
4. Standardize estimate-to-measurement execution for new ideas (see [IDEA-MEASUREMENT-FLOW.md](IDEA-MEASUREMENT-FLOW.md)).

## Validation Snapshot

- API endpoint set is implemented and locally testable; public deployment is currently blocked pending new hosting cutover.
- Test suite remains the release gate.
- Overnight pipeline remains the main autonomous execution path.
