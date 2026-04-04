---
idea_id: contributor-experience
title: Contributor Experience
stage: specced
work_type: feature
specs:
  - 094-contributor-onboarding-and-governed-change-flow
  - 168-identity-driven-onboarding-tofu
  - 157-investment-ux-stake-cc-on-ideas
---

# Contributor Experience

Make it easy for anyone to contribute to ideas and get credited.

## What It Does

- Contributors register, propose updates, get attribution, pass review flow
- Trust-on-first-use (TOFU) identity: claim handle, get session token, no password needed
- Investment UX: stake CC on ideas you believe in, track returns
- Governed change flow ensures quality without blocking contributors

## API

- `POST /api/contributors` — register contributor
- `POST /api/ideas/{id}/stake` — invest CC
- `GET /api/ideas/{id}/progress` — see contributor list and CC flow

## Why It Matters

The platform only works if people can contribute. This is the front door.
