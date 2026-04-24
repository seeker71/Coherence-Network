# Ideas Index

> 17 super-ideas across 6 pillars. 338 raw ideas in DB absorbed as children. Drill into any idea file for problem, capabilities, specs, absorbed children.

## All Ideas (17)

| Idea | Pillar | Stage | Specs | Key capability |
|------|--------|-------|-------|----------------|
| [Idea Realization Engine](idea-realization-engine.md) | realization | impl | 8 | Lifecycle, scoring, hierarchy, closure |
| [Portfolio Governance](portfolio-governance.md) | realization | impl | 1 | Triadic scoring, governance snapshots |
| [Agent Pipeline](agent-pipeline.md) | pipeline | impl | 6 | Task dispatch, PM cycles, review/deploy/verify |
| [Pipeline Reliability](pipeline-reliability.md) | pipeline | impl | 8 | Auto-heal, smart reap, timeouts, dedup |
| [Pipeline Optimization](pipeline-optimization.md) | pipeline | impl | 6 | Prompt A/B, provider health, cost tracking |
| [Agent CLI](agent-cli.md) | pipeline | impl | 2 | MCP server (20 tools), CLI (35+ commands) |
| [Coherence Credit](coherence-credit.md) | economics | impl | 6 | CC as unit of account, cost/value measurement |
| [Value Attribution](value-attribution.md) | economics | impl | 7 | Contribution tracking, fair payout lineage |
| [User Surfaces](user-surfaces.md) | surfaces | impl | 6 | Web pages, dashboard, homepage, navigation |
| [Developer Experience](developer-experience.md) | surfaces | impl | 1 | Quick start, self-discovery, spec reflection |
| [Federation and Nodes](federation-and-nodes.md) | network | impl | 1 | Multi-node sync, identity, OpenClaw bridge |
| [Identity and Onboarding](identity-and-onboarding.md) | network | spec | 2 | TOFU identity, 37 providers, investment UX |
| [Contributor Experience](contributor-experience.md) | network | spec | 1 | Orientation, profiles, messaging, recognition |
| [Data Infrastructure](data-infrastructure.md) | foundation | impl | 8 | Graph DB, PostgreSQL, route registry, telemetry |
| [Knowledge and Resonance](knowledge-and-resonance.md) | foundation | impl | 1 | Concept ontology, belief systems, resonance, discovery |
| [External Presence](external-presence.md) | foundation | impl | 1 | Social bots, news ingestion, translation |

**Totals**: 14 implementing, 2 specced. 65 specs across all ideas.

## By Pillar

- **Realization** (2): idea-realization-engine, portfolio-governance
- **Pipeline** (4): agent-pipeline, pipeline-reliability, pipeline-optimization, agent-cli
- **Economics** (2): coherence-credit, value-attribution
- **Surfaces** (2): user-surfaces, developer-experience
- **Network** (3): federation-and-nodes, identity-and-onboarding, contributor-experience
- **Foundation** (3): data-infrastructure, knowledge-and-resonance, external-presence

## Cross-references

- Ideas → Specs: each idea file lists its specs under `specs:` frontmatter
- Ideas → Concepts: `knowledge-and-resonance` → [KB concepts](../docs/vision-kb/INDEX.md)
- Specs → Ideas: each spec frontmatter has `idea_id:` field
- All specs: [specs/INDEX.md](../specs/INDEX.md) (grouped by idea)

## Lookup

```bash
# 16 super-ideas from API
curl https://api.coherencycoin.com/api/ideas?curated_only=true

# Children (absorbed raw ideas) of a super-idea
curl https://api.coherencycoin.com/api/ideas/{idea_id}/children

# Specs for a super-idea
curl https://api.coherencycoin.com/api/ideas/{idea_id}/specs
```
