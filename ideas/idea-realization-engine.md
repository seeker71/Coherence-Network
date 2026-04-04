---
idea_id: idea-realization-engine
title: Idea Realization Engine
stage: implementing
work_type: feature
specs:
  - [053-ideas-prioritization](../specs/053-ideas-prioritization.md)
  - [138-idea-lifecycle-management](../specs/138-idea-lifecycle-management.md)
  - [176-idea-lifecycle-closure](../specs/176-idea-lifecycle-closure.md)
  - [117-idea-hierarchy-super-child](../specs/117-idea-hierarchy-super-child.md)
  - [120-super-idea-rollup-criteria](../specs/120-super-idea-rollup-criteria.md)
  - [158-idea-right-sizing](../specs/158-idea-right-sizing.md)
  - [181-idea-dual-identity](../specs/181-idea-dual-identity.md)
---

# Idea Realization Engine

The core product. Every idea in Coherence Network has a measurable lifecycle from inception to impact. The realization engine is the system that tracks that lifecycle, scores ideas by expected ROI, decomposes large ideas into actionable sub-ideas, and ensures nothing falls through the cracks. If it is not tracked here, it does not exist.

## Problem

Ideas discussed in conversations, Slack threads, and GitHub issues evaporate. There is no way to know which ideas are worth pursuing, which are duplicates, which are blocked, or which have already been completed. Teams end up re-debating the same ideas because there is no canonical record of what was decided and why.

## Key Capabilities

- **Free-energy scoring**: `(potential_value x confidence) / (estimated_cost + resistance_risk)` ranks every idea by ROI. The highest-scoring ideas surface automatically for execution. Scores update as real cost and value data flows in from the pipeline.
- **Lifecycle stages**: `none` -> `specced` -> `implementing` -> `testing` -> `reviewing` -> `complete`. Each transition requires specific criteria (spec exists, tests pass, review approved). Ideas cannot skip stages.
- **Super/child hierarchy**: Big ideas decompose into smaller ones. A "data infrastructure" super-idea contains child ideas for PostgreSQL migration, node-edge layer, coherence algorithm. Rollup criteria determine when a super-idea is done (e.g., all children complete, or N of M children complete).
- **Right-sizing**: Ideas with 12+ open questions get flagged for splitting into sub-ideas. Near-duplicate ideas get merge suggestions via TF-IDF overlap detection. The system actively prevents both idea bloat and idea fragmentation.
- **Dual identity**: Every idea has both a human-readable slug (`idea-realization-engine`) and an API-queryable UUID. Either can be used in URLs, CLI commands, and API calls.
- **Standing questions**: Every idea always has at least one open improvement or measurement question. This prevents ideas from going stale -- there is always a next step to consider.

## What Success Looks Like

- Every idea discussed in any session is recorded with `POST /api/ideas` before the session ends
- Ideas are ranked by free-energy score and the top-ranked ideas are the ones actually being worked on
- No idea has more than 12 open questions without being split
- Super-ideas accurately reflect the completion state of their children
- Any contributor can find any idea by slug or UUID in under 5 seconds

## Absorbed Ideas

- **fractal-idea-right-sizing**: Ideas too big get decomposed into sub-ideas. Ideas too small get merged. System suggests splits when 12+ open questions exist. Merge suggestions triggered by TF-IDF overlap detection between idea descriptions.
- **proof-based-validation**: Validation must be trustless -- endpoint exists, response matches schema, known-input round-trip works, edge cases return correct errors, data persists across restart. No "trust me it works" -- the system proves it.
- **self-balancing-graph**: System monitors its own shape. Too many children on one node triggers a split signal. Orphan clusters trigger a merge signal. When 80% of energy concentrates on 3 ideas, the system surfaces neglected ones.

## Open Questions

- How do we prevent concept collapse where everything reduces to a few super-categories? (e.g., "platform" becomes a super-idea that absorbs everything)
- How does the graph self-balance as it grows beyond 500+ ideas? What are the computational limits of TF-IDF overlap detection at scale?
- Should lifecycle stage transitions be automatic (based on criteria) or require explicit human/agent action?
