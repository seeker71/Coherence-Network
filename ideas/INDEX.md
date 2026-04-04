# Ideas Index

12 consolidated ideas aligned with the mission: **every idea gets tracked, funded, built, and measured.**

| Idea | Slug | Stage | Specs | Domain |
|------|------|-------|-------|--------|
| [Idea Realization Engine](idea-realization-engine.md) | `idea-realization-engine` | implementing | 053, 138, 176, 117, 120, 158, 181 | Core |
| [Value Attribution](value-attribution.md) | `value-attribution` | implementing | 048, 049, 052, 083, 086, 094 | Core |
| [Coherence Credit](coherence-credit.md) | `coherence-credit` | implementing | 119, 124, 114, 115, 116, 126 | Core |
| [Contributor Experience](contributor-experience.md) | `contributor-experience` | specced | 094, 168, 157 | Core |
| [Agent Pipeline](agent-pipeline.md) | `agent-pipeline` | implementing | 002, 005, 139, 026, 032, 159 | Pipeline |
| [Pipeline Reliability](pipeline-reliability.md) | `pipeline-reliability` | implementing | 113, 114, 125, 169, 186, 047 | Pipeline |
| [Pipeline Optimization](pipeline-optimization.md) | `pipeline-optimization` | implementing | 074, 112, 113, 127, 135 | Pipeline |
| [Agent CLI](agent-cli.md) | `agent-cli` | implementing | 108, 111 | Pipeline |
| [Data Infrastructure](data-infrastructure.md) | `data-infrastructure` | implementing | 018, 054, 118, 166, 050, 107, 130, 051 | Infra |
| [User Surfaces](user-surfaces.md) | `user-surfaces` | implementing | 148, 075, 161, 162, 165, 180 | Infra |
| [Identity and Onboarding](identity-and-onboarding.md) | `identity-and-onboarding` | specced | 168, 157 | Phase 2 |
| [Developer Experience](developer-experience.md) | `developer-experience` | implementing | — | DevEx |

## Retired Ideas

~70 ideas retired from the database (lifecycle=retired). These were:
- Test/placeholder data (idea_id_1, roi-progress-idea-*, x1, fork-x1-*)
- Micro-tactical implementation details (absorbed into consolidated ideas above)
- Off-mission features (demo-community-climate-marketplace, federated-instance-aggregation)
- Duplicate timestamps (demo-community-climate-marketplace-20260311060252)

## Querying Ideas

```bash
# By slug
curl https://api.coherencycoin.com/api/ideas/agent-pipeline

# By ID
curl https://api.coherencycoin.com/api/ideas/agent-pipeline

# List all
cc ideas

# CLI detail
cc idea agent-pipeline
```
