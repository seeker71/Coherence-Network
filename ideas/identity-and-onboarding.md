---
idea_id: identity-and-onboarding
title: Identity and Onboarding
stage: specced
work_type: feature
phase: 2
specs:
  - 168-identity-driven-onboarding-tofu
  - 157-investment-ux-stake-cc-on-ideas
---

# Identity and Onboarding (Phase 2)

Multi-user identity and investment UX for the platform.

## What It Does

- Trust-on-first-use (TOFU): claim handle, get session token, no password or OAuth needed
- Investment UX: stake CC on ideas with clear returns, portfolio view, history
- Foundation for multi-user attribution and governance

## API

- `POST /api/identity/claim` — claim handle
- `POST /api/ideas/{id}/stake` — stake CC

## Why It Matters

Phase 2 dependency. Can't have multi-user attribution without identity. Can't have investment without identity.
