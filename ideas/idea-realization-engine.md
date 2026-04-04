---
idea_id: idea-realization-engine
title: Idea Realization Engine
stage: implementing
work_type: feature
specs:
  - 053-ideas-prioritization
  - 138-idea-lifecycle-management
  - 176-idea-lifecycle-closure
  - 117-idea-hierarchy-super-child
  - 120-super-idea-rollup-criteria
  - 158-idea-right-sizing
  - 181-idea-dual-identity
---

# Idea Realization Engine

The core product: track every idea from inception to measurable impact.

## What It Does

- Ideas are tracked with lifecycle stages (none → specced → implementing → testing → reviewing → complete)
- Ideas decompose into super/child hierarchies with rollup criteria
- Right-sizing detects bloated or nano ideas and suggests splits/merges
- Dual identity (UUID + human slug) makes ideas queryable by machines and humans
- Free energy scoring prioritizes highest-ROI ideas for execution

## API

- `GET /api/ideas` — list all ideas ranked by score
- `GET /api/ideas/{id}` — get idea by UUID or slug
- `GET /api/ideas/progress` — per-stage counts and completion %
- `POST /api/ideas` — create new idea
- `POST /api/ideas/{id}/advance` — advance to next stage

## Why It Matters

Without this, ideas are just conversations. With it, every idea has a measurable lifecycle with attribution.
