# Idea Portfolio (Federated Framework)

This portfolio tracks ideas as first-class system objects across human contributors, AI agents, and external interfaces.

## Goal

Maximize energy flow to the whole (interactions, creation, research, attraction, attention, value) with minimum resistance (time, internal resources, external resources).

## Core Fields Per Idea

- `potential_value`: estimated contribution to whole-system value
- `actual_value`: measured contribution from real outcomes
- `estimated_cost`: expected effort/resource cost
- `actual_cost`: measured cost
- `resistance_risk`: expected friction/risk factor
- `confidence`: estimate confidence (0.0–1.0)
- `manifestation_status`: `none | partial | validated`
- `open_questions`: ordered by `value_to_whole`

## Prioritization Function

`free_energy_score = (potential_value * confidence) / (estimated_cost + resistance_risk)`

Higher score means higher expected value flow per unit friction.

## API

The portfolio is exposed for machine and human interfaces:

- `GET /api/ideas`
- `GET /api/ideas?only_unvalidated=true`
- `GET /api/ideas/{idea_id}`
- `PATCH /api/ideas/{idea_id}`

Data is persisted in `api/logs/idea_portfolio.json` (or `IDEA_PORTFOLIO_PATH`).

## Operating Loop

1. Add/maintain ideas with estimates.
2. Prioritize by `free_energy_score`.
3. Run smallest validating experiment.
4. Replace estimates with measured actuals.
5. Re-rank and repeat.
