---
idea_id: idea-realization-engine
status: active
source: []  # not yet implemented
---

# Spec 120: Super-Idea Rollup Criteria

## Purpose

Define explicit validation criteria for super-ideas so they can self-assess completion. A super-idea is "validated" when ALL child ideas are validated AND the rollup condition is met.

## Rollup Definitions

| Super Idea | Rollup Condition |
|---|---|
| `oss-interface-alignment` | All OSS interface specs pass parity tests AND web pages render without API errors |
| `portfolio-governance` | All governance endpoints have auth + identity verification AND approval flow tested end-to-end |
| `community-project-funder-match` | Funder proof page renders live data AND matching algorithm produces valid results |
| `coherence-network-agent-pipeline` | All child ideas validated AND pipeline can execute a task end-to-end without manual intervention |

## Requirements

- [ ] R1: Each super-idea has a `rollup_condition` field in the DB
- [ ] R2: `validate_super_idea(idea_id)` checks all children validated + rollup condition
- [ ] R3: Super-idea manifestation_status auto-updates when rollup criteria met
- [ ] R4: Dashboard shows rollup progress (children validated / total children)


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Define explicit validation criteria for super-ideas so they can self-assess completion.
files_allowed:
  - # TBD — determine from implementation
done_when:
  - R1: Each super-idea has a `rollup_condition` field in the DB
  - R2: `validate_super_idea(idea_id)` checks all children validated + rollup condition
  - R3: Super-idea manifestation_status auto-updates when rollup criteria met
  - R4: Dashboard shows rollup progress (children validated / total children)
commands:
  - python3 -m pytest api/tests/test_idea_hierarchy.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Failure and Retry Behavior

- If a child idea regresses (validated → partial), parent auto-downgrades
- Rollup check is idempotent and safe to retry

## Risks and Known Gaps

- Rollup conditions are currently descriptive, not machine-checkable
- Follow-up: Convert rollup conditions to executable assertions

## Verification

```bash
python3 -m pytest api/tests/test_idea_hierarchy.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
