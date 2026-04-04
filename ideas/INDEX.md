# Ideas Index

12 ideas aligned to mission: **every idea tracked, funded, built, measured.**

## How to find what you need

1. Find the idea slug below
2. Read `ideas/{slug}.md` for frontmatter (specs list, stage)
3. Query `GET /api/ideas/{slug}` for scores, questions, value data
4. Each linked spec file has a `source:` map pointing to implementing code

## Active Ideas

| Slug | Title | Stage | Specs | Domain |
|------|-------|-------|-------|--------|
| `idea-realization-engine` | Idea Realization Engine | implementing | 7 | Core |
| `value-attribution` | Value Attribution | implementing | 6 | Core |
| `coherence-credit` | Coherence Credit | implementing | 6 | Core |
| `contributor-experience` | Contributor Experience | specced | 3 | Core |
| `agent-pipeline` | Agent Pipeline | implementing | 6 | Pipeline |
| `pipeline-reliability` | Pipeline Reliability | implementing | 8 | Pipeline |
| `pipeline-optimization` | Pipeline Optimization | implementing | 6 | Pipeline |
| `agent-cli` | Agent CLI | implementing | 2 | Pipeline |
| `data-infrastructure` | Data Infrastructure | implementing | 8 | Infra |
| `user-surfaces` | User Surfaces | implementing | 6 | Infra |
| `identity-and-onboarding` | Identity and Onboarding | specced | 2 | Phase 2 |
| `developer-experience` | Developer Experience | implementing | 0 | DevEx |

## Querying

```bash
curl https://api.coherencycoin.com/api/ideas/{slug}       # single idea
curl https://api.coherencycoin.com/api/ideas               # all ideas ranked by score
cc ideas                                                   # CLI list
cc idea {slug}                                             # CLI detail
```

## Retired

~70 ideas retired (lifecycle=retired): test data, micro-tactical details, off-mission features, duplicates.
