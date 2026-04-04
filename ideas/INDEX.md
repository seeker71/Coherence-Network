# Ideas Index

12 ideas aligned to mission: **every idea tracked, funded, built, measured.**

## How to find what you need

1. Click the idea link below to see full description, capabilities, and absorbed ideas
2. Each idea file has clickable spec links (`../specs/{slug}.md`)
3. Query `GET /api/ideas/{slug}` for scores, questions, value data

## Core — What we're building for users

| Idea | Stage | Specs | Description |
|------|-------|-------|-------------|
| [Idea Realization Engine](idea-realization-engine.md) | implementing | 7 | Track every idea from inception to impact. Free-energy scoring, lifecycle stages, right-sizing. |
| [Value Attribution](value-attribution.md) | implementing | 7 | Track who contributed what, calculate fair payouts via value lineage chain. |
| [Coherence Credit](coherence-credit.md) | implementing | 6 | CC as unit of account. Every action has a cost, every outcome has a value. |
| [Contributor Experience](contributor-experience.md) | specced | 3 | Onboarding, identity (37 providers), governed change flow, investment UX. |

## Pipeline — How ideas become working software

| Idea | Stage | Specs | Description |
|------|-------|-------|-------------|
| [Agent Pipeline](agent-pipeline.md) | implementing | 6 | Task orchestration, project manager cycles, split review/deploy/verify phases. |
| [Pipeline Reliability](pipeline-reliability.md) | implementing | 8 | Self-healing: diagnostics, auto-heal, smart reap, data-driven timeouts, dedup. |
| [Pipeline Optimization](pipeline-optimization.md) | implementing | 6 | Prompt A/B testing, provider health, cross-task correlation, cost tracking. |
| [Agent CLI](agent-cli.md) | implementing | 2 | MCP server (20 tools), coherence-cli (35+ commands), lifecycle hooks. |

## Infrastructure — What everything runs on

| Idea | Stage | Specs | Description |
|------|-------|-------|-------------|
| [Data Infrastructure](data-infrastructure.md) | implementing | 8 | Universal node+edge layer, PostgreSQL, coherence algorithm, route registry. |
| [User Surfaces](user-surfaces.md) | implementing | 6 | Web pages, CLI, homepage readability, MCP skill registry, self-discovery. |

## Phase 2 — After core is proven

| Idea | Stage | Specs | Description |
|------|-------|-------|-------------|
| [Identity and Onboarding](identity-and-onboarding.md) | specced | 2 | TOFU identity, 37 providers, investment UX (stake CC on ideas). |
| [Developer Experience](developer-experience.md) | implementing | 0 | External repo proof, DB error tracking, context budget tooling. |

## Querying

```bash
curl https://api.coherencycoin.com/api/ideas/{slug}       # single idea
curl https://api.coherencycoin.com/api/ideas               # all ideas ranked by score
```
