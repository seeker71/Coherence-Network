---
idea_id: idea-realization-engine
status: done
source:
  - file: api/app/services/idea_hierarchy.py
    symbols: [set_parent_idea]
  - file: api/app/models/idea.py
    symbols: [IdeaType, Idea]
requirements:
  - Idea model includes idea_type, parent_idea_id, child_idea_ids fields
  - IdeaType enum has super, child, standalone values
  - Super-ideas excluded from task pickup in ROI and unblock queries
  - Child-ideas inherit parent context for display
  - Existing ideas default to standalone for backward compatibility
  - GET /api/ideas returns idea_type; super-ideas show child_idea_ids
done_when:
  - Super-ideas excluded from pickup, child-ideas ranked normally
  - pytest api/tests/test_idea_hierarchy_super_child.py passes
test: "cd api && python -m pytest -q tests/test_super_idea_rollup.py"
---

> **Parent idea**: [idea-realization-engine](../ideas/idea-realization-engine.md)
> **Source**: [`api/app/services/idea_service.py`](../api/app/services/idea_service.py) | [`api/app/models/idea.py`](../api/app/models/idea.py)

# Idea Hierarchy — Super-Ideas and Child-Ideas

**Idea**: `idea-hierarchy-model` (sub-idea of `portfolio-governance`)
**Depends on**: Spec 116 (grounded idea metrics), Spec 053 (free energy scoring)

## Status: In Progress

## Problem

Ideas like `portfolio-governance` (score 7.14, rank #1) are too vague to act on directly.
They represent strategic goals, not actionable work. When the task pickup logic ranks by
free_energy_score, it may surface a super-idea that no agent or contributor can execute
without first decomposing it into smaller pieces.

Currently all ideas are flat — no hierarchy. The `idea_lineage.json` config tracks
parent relationships externally, but the Idea model and task pickup logic don't know
about them.

## Design

### New fields on the Idea model

```python
class IdeaType(str, Enum):
    SUPER = "super"       # Strategic goal; never picked up directly
    CHILD = "child"       # Actionable work item; can be picked up
    STANDALONE = "standalone"  # No parent; acts like a child (backward compat)

class Idea(BaseModel):
    # ... existing fields ...
    idea_type: IdeaType = IdeaType.STANDALONE
    parent_idea_id: str | None = None
    child_idea_ids: list[str] = []
```

### Rules

1. **Super-ideas are excluded from task pickup.** `next_highest_roi_task_from_answered_questions()`
   and `next_unblock_task_from_flow()` filter out `idea_type == "super"`.

2. **Child-ideas inherit parent context.** When a child-idea is displayed, its parent
   is shown for strategic context.

3. **Super-idea metrics auto-compute from children.** The grounded metrics endpoint
   (spec 116) can aggregate child metrics into the parent.

4. **Backward compatible.** Existing ideas default to `standalone` which behaves
   identically to the current model. No breaking changes.

### Idea decomposition

| Current Idea | Type | Children |
|---|---|---|
| `portfolio-governance` | **super** | `coherence-signal-depth`, `idea-hierarchy-model` |
| `oss-interface-alignment` | **super** | `interface-trust-surface`, `minimum-e2e-path` |
| `community-project-funder-match` | **super** | `funder-proof-page`, (future children) |
| `coherence-signal-depth` | **child** (of portfolio-governance) | — |
| `federated-instance-aggregation` | **standalone** | — (no children yet) |
| `coherence-network-agent-pipeline` | **super** (derived) | agent-prompt-ab-roi, agent-failed-task-diagnostics, agent-auto-heal, agent-grounded-measurement |

### Task pickup filter

```python
# In next_highest_roi_task_from_answered_questions():
ranked = [row for row in answered
          if row.get("idea_type") != "super"]
```

## Acceptance Criteria

Verified by `api/tests/test_idea_hierarchy_super_child.py`.

1. Idea model includes `idea_type`, `parent_idea_id`, `child_idea_ids` fields
2. DEFAULT_IDEAS updated: `portfolio-governance` and `oss-interface-alignment` marked as super
3. New child-ideas created for actionable sub-work
4. Task pickup excludes super-ideas
5. `GET /api/ideas` returns idea_type field; super-ideas show child_idea_ids
6. Tests verify: super-ideas excluded from pickup, child-ideas ranked normally,
   standalone backward compat

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Acceptance Tests

See `api/tests/test_idea_hierarchy_super_child.py` for test cases covering this spec's requirements.




## Verification

```bash
cd api && pytest -q tests/test_idea_hierarchy_super_child.py
```

- Unit tests for model validation
- Task pickup filter tests (super excluded, child/standalone included)
- API response includes new fields

## Risks and Assumptions

- **Risk**: Changing the Idea model may break serialization of persisted ideas.
  Mitigation: defaults ensure backward compat (standalone, no parent, no children).
- **Risk**: Over-decomposition — too many tiny child-ideas dilute focus.
  Mitigation: only split when there's an actionable work item with its own spec.

## Known Gaps and Follow-up Tasks

- [ ] **Auto-compute follow-up**: Auto-compute super-idea metrics by aggregating children in grounded_idea_metrics_service.
- [ ] **IdeaUpdate follow-up**: Add `idea_type` to IdeaUpdate so ideas can be promoted/demoted via API.
- [ ] **Web UI follow-up**: Visual hierarchy in web UI (/ideas page tree view).

## Purpose

This spec realizes part of the `idea-realization-engine` idea. The full purpose, problem statement, and design rationale live below in the body and in the frontmatter `requirements:` / `done_when:` blocks. This section exists to satisfy the structural contract so the spec validator can confirm the spec carries its weight.

## Requirements

- [ ] **R1**: Idea model includes idea_type, parent_idea_id, child_idea_ids fields
- [ ] **R2**: IdeaType enum has super, child, standalone values
- [ ] **R3**: Super-ideas excluded from task pickup in ROI and unblock queries
- [ ] **R4**: Child-ideas inherit parent context for display
- [ ] **R5**: Existing ideas default to standalone for backward compatibility
- [ ] **R6**: GET /api/ideas returns idea_type; super-ideas show child_idea_ids

## Files to Create/Modify

- `api/app/services/idea_hierarchy.py`
- `api/app/models/idea.py`

## Out of Scope

- Anything outside the files named in this spec's source map.
- Concerns owned by sibling specs in the same idea cluster.

