# Ideas Index

16 super-ideas across 6 pillars. Every one of the 338 ideas in the DB is absorbed as a child. Nothing hidden, nothing lost — drill into any super-idea to see the full richness beneath it.

## How to find what you need

1. Click the idea link below to see problem, capabilities, specs, and absorbed children
2. Each idea file has clickable spec links (`../specs/{slug}.md`)
3. Query `GET /api/ideas?curated_only=true` for the 16 super-ideas
4. Query `GET /api/ideas/{idea_id}/children` to see everything absorbed under a super-idea
5. Query `GET /api/ideas/{idea_id}/specs` for the specs that realize it

---

## Pillar 1: Realization — Track every idea from inception to impact

| Idea | Stage | Description |
|------|-------|-------------|
| [Idea Realization Engine](idea-realization-engine.md) | implementing | Track every idea from inception to impact. Free-energy scoring, lifecycle stages, right-sizing, hierarchy, closure. |
| [Portfolio Governance and Measurement](portfolio-governance.md) | active | Triadic scoring, explanation traces, governance snapshots. Signal layer for the whole portfolio. |

## Pillar 2: Pipeline — Turn ideas into working software

| Idea | Stage | Description |
|------|-------|-------------|
| [Agent Pipeline](agent-pipeline.md) | implementing | Task orchestration, project manager cycles, split review/deploy/verify phases. |
| [Pipeline Reliability](pipeline-reliability.md) | implementing | Self-healing: diagnostics, auto-heal, smart reap, data-driven timeouts, dedup. |
| [Pipeline Optimization](pipeline-optimization.md) | implementing | Prompt A/B testing, provider health, cross-task correlation, cost tracking. |
| [Agent CLI and Interfaces](agent-cli.md) | implementing | MCP server (20 tools), coherence-cli (35+ commands), node control, lifecycle hooks. |

## Pillar 3: Economics — CC as unit of account, value flows fairly

| Idea | Stage | Description |
|------|-------|-------------|
| [Coherence Credit](coherence-credit.md) | implementing | CC as unit of account. Every action has a cost, every outcome has a value. |
| [Value Attribution](value-attribution.md) | implementing | Track who contributed what, calculate fair payouts via value lineage chain. |

## Pillar 4: Surfaces — Where users meet the system

| Idea | Stage | Description |
|------|-------|-------------|
| [User Surfaces](user-surfaces.md) | implementing | Web pages, homepage readability, live pipeline dashboard, navigation. |
| [Developer Experience](developer-experience.md) | implementing | External repo proof, DB error tracking, self-discovery, spec reflection. |

## Pillar 5: Network — How the platform federates and welcomes people

| Idea | Stage | Description |
|------|-------|-------------|
| [Federation and Nodes](federation-and-nodes.md) | active | Multi-node identity, sync, aggregated visibility, OpenClaw bridge. Essential for ecosystem. |
| [Identity and Onboarding](identity-and-onboarding.md) | specced | TOFU identity, 37 providers, investment UX (stake CC on ideas). |
| [Contributor Experience](contributor-experience.md) | specced | Orientation, profiles, messaging, feedback loops, recognition. |

## Pillar 6: Foundation — Substrate everything rests on

| Idea | Stage | Description |
|------|-------|-------------|
| [Data Infrastructure](data-infrastructure.md) | implementing | Universal node+edge layer, PostgreSQL, route registry, health, release gates. |
| [Knowledge and Resonance](knowledge-and-resonance.md) | active | Concept layer, belief systems, triadic resonance, fractal zoom, ontology. |
| [External Presence and Ecosystem](external-presence.md) | active | Social bots, news ingestion, content parsing, geolocation, translation. |

---

## Querying

```bash
# 16 super-ideas
curl https://api.coherencycoin.com/api/ideas?curated_only=true

# Specs for a super-idea
curl https://api.coherencycoin.com/api/ideas/agent-pipeline/specs

# Children (absorbed ideas) of a super-idea
curl https://api.coherencycoin.com/api/ideas/knowledge-and-resonance/children

# Full 338 ideas (includes every child + spec-leaks)
curl https://api.coherencycoin.com/api/ideas
```
