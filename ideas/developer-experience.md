---
idea_id: developer-experience
title: Developer Experience
stage: implementing
work_type: enhancement
pillar: surfaces
specs:
  - [developer-quick-start](../specs/developer-quick-start.md)
---

# Developer Experience

Make the platform easy to develop, test, and operate. A new developer should be able to clone the repo, run the tests, and make their first change within 15 minutes. The test suite should run in under 10 seconds. Database errors should be caught and reported, not silently swallowed. Token costs should be estimable before scanning files.

## Problem

Developer friction compounds. If tests are slow, developers skip them. If database errors are silent, bugs ship to production. If scanning a large file costs thousands of tokens, agents waste budget on low-value reads. If there is no proof that the platform works outside its own codebase, potential adopters cannot evaluate it. Every friction point reduces the number of people willing to contribute.

## Key Capabilities

- **External repo proof**: Demonstrate that Coherence Network works beyond its own codebase. A `coherence-external-proof` repository that uses the platform's APIs and CLI to manage ideas, track contributions, and measure coherence for an unrelated project. This is the "eat your own dog food outside the kitchen" test.
- **Silent DB failure detection**: `schema_ok` field in the health endpoint (`GET /api/health`) reports whether all expected tables exist and have the correct schema. Startup database errors are logged at ERROR level, not swallowed. Missing tables are recorded as friction events in the telemetry system, surfacing infrastructure issues before they cause data loss.
- **Context budget tooling**: `python3 scripts/context_budget.py <files-or-dirs>` estimates token cost before scanning files. Reports file sizes, estimated token impact, and compact summaries. Uses a cache in `.cache/context_budget/summary_cache.json` so repeated scans avoid re-reading large files. Prevents agents from burning 50K tokens reading a file that could be summarized in 500.
- **Test suite**: 177 flow-centric integration tests that complete in ~8 seconds. Tests use real data and algorithms (no mocks, per project convention). Tests cover the full lifecycle: compose -> expand -> validate -> melt/patch/refreeze -> contract.

## What Success Looks Like

- New developer productive (first passing test, first code change) within 15 minutes of cloning
- Zero silent database failures -- every schema issue surfaces in health checks and logs
- Context budget tool prevents any agent session from exceeding 200K tokens on file reads
- External proof repo demonstrates full API coverage with a non-Coherence-Network project
- Test suite stays under 10 seconds as the codebase grows

## Absorbed Ideas

- **external-repo-milestone**: Create `coherence-external-proof` repo to demonstrate external enablement. The repo uses the public API to create ideas, record contributions, track lifecycle stages, and measure coherence scores for a completely unrelated project. If the platform cannot manage someone else's ideas, it is not ready for adoption.
- **db-error-tracking**: Health endpoint reports `schema_ok` boolean. Startup database errors logged at ERROR level (not WARNING or INFO). Missing tables recorded as friction events with table name, expected schema, and timestamp. This turns invisible infrastructure failures into actionable alerts.
