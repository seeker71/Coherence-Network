---
idea_id: developer-experience
status: done
source:
  - file: api/app/routers/health.py
    symbols: [health_check]
  - file: api/tests/conftest.py
    symbols: [_reset_service_caches_between_tests]
  - file: scripts/agent_status.py
    symbols: [get_worktrees, detect_conflicts]
  - file: .claude/launch.json
    symbols: []
requirements:
  - Health endpoint returns status, version, uptime, schema_ok
  - Test suite runs 353+ tests in under 10 seconds
  - Multi-agent worktree coordination with conflict detection
  - Launch config for local dev server (API + web)
  - No mocks in flow tests -- real API integration
done_when:
  - GET /api/health returns status ok with schema_ok true
  - pytest runs all flow tests in under 10 seconds
  - scripts/agent_status.py --diff reports file-level conflicts
  - All tests pass
test: "python3 -m pytest api/tests/test_flow_core_api.py -q"
---

> **Parent idea**: [developer-experience](../ideas/developer-experience.md)
> **Source**: [`api/app/routers/health.py`](../api/app/routers/health.py) | [`api/tests/conftest.py`](../api/tests/conftest.py) | [`scripts/agent_status.py`](../scripts/agent_status.py) | [`.claude/launch.json`](../.claude/launch.json)

# Developer Quick Start -- Clone, Test, Ship in 15 Minutes

## Goal

Ensure the platform is easy to develop, test, and operate so that a new developer can clone the repo, run the test suite, and make their first change within 15 minutes -- with confidence that the health check catches infrastructure problems and the multi-agent coordination prevents file conflicts.

## What's Built

The developer experience rests on four pillars that are already deployed and operational.

**Health endpoint**: `health.py` exposes `GET /api/health` which returns status, version, uptime, and a `schema_ok` boolean that verifies all expected database tables exist with correct schema. Silent database failures are impossible -- every schema issue surfaces immediately in the health response and startup logs.

**Test infrastructure**: `conftest.py` provides `_reset_service_caches_between_tests` which ensures test isolation without mocks. The suite runs 353+ flow-centric integration tests using real data and algorithms in under 10 seconds. Tests cover the full lifecycle: compose, expand, validate, melt/patch/refreeze, contract.

**Multi-agent coordination**: `agent_status.py` implements `get_worktrees` and `detect_conflicts` for file-level conflict detection across parallel agent sessions (Claude Code, Codex, Cursor). Running `--diff` reports which worktrees touch overlapping files so agents coordinate before proceeding.

**Launch config**: `.claude/launch.json` provides local dev server configuration for both API and web, enabling one-command startup for development.

## Requirements

1. Health endpoint returns status, version, uptime, schema_ok
2. Test suite runs 353+ tests in under 10 seconds
3. Multi-agent worktree coordination with conflict detection
4. Launch config for local dev server (API + web)
5. No mocks in flow tests -- real API integration

## Acceptance Tests

```bash
python3 -m pytest api/tests/test_flow_core_api.py -q
```
