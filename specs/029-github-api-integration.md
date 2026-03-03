# Spec: GitHub API Integration

## Purpose

Populate Contributor and Organization nodes in the graph from GitHub. Required for real coherence scores: contributor_diversity, activity_cadence, community_responsiveness, security_posture. Without GitHub data, coherence components remain stubs. P0 for product value.

## Requirements

- [ ] GraphStore: add `Contributor` and `Organization` node types; edges `CONTRIBUTES_TO`, `MAINTAINS`, `MEMBER_OF`
- [ ] GitHub API client: repos, contributors, PRs, issues; rate-limit aware; ETag/conditional requests
- [ ] Indexer: given Project (npm/pypi), resolve GitHub repo URL; fetch contributors, recent activity
- [ ] Store: persist Contributor (login, name, avatar_url, contributions_count); Organization (login, type)
- [ ] Coherence API: wire contributor_diversity, activity_cadence from real GitHub data when available
- [ ] Env: `GITHUB_TOKEN` optional; unauthenticated 60 req/h; token 5000 req/h

## API Contract (if applicable)

No new public API endpoints. Extends existing:
- `GET /api/projects/{eco}/{name}/coherence` — components_with_data increases when GitHub data present

## Data Model

```yaml
Contributor:
  id: string  # github:login or npm:username
  source: github | npm
  login: string
  name: string | null
  avatar_url: string | null
  contributions_count: int

Organization:
  id: string
  login: string
  type: string  # Organization, User

 edges:
  CONTRIBUTES_TO: (Contributor)-[:CONTRIBUTES_TO]->(Project)
  MAINTAINS: (Contributor)-[:MAINTAINS]->(Project)
  MEMBER_OF: (Contributor)-[:MEMBER_OF]->(Organization)
```

## Files to Create/Modify

- `api/app/services/github_client.py` — GitHub API wrapper; rate limit, ETag
- `api/app/services/graph_store.py` — add Contributor, Organization, edges
- `api/scripts/index_github.py` — fetch contributors for indexed projects
- `api/app/routers/coherence.py` or services — wire real contributor_diversity, activity_cadence
- `specs/029-github-api-integration.md` — this spec

## Acceptance Tests

- GitHub client: mock or VCR; fetch contributors for known repo
- GraphStore: upsert Contributor; query CONTRIBUTES_TO
- Coherence: project with GitHub data returns components_with_data >= 3

## Out of Scope

- OAuth for user GitHub login
- Private repo access
- Full GitHub GraphQL (REST first)

## Decision Gates

- Schema change (new node types) — human approve
- GITHUB_TOKEN in CI — use Actions token; no secrets in code
