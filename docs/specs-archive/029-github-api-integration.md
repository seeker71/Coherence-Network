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


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Populate Contributor and Organization nodes in the graph from GitHub.
files_allowed:
  - api/app/services/github_client.py
  - api/app/services/graph_store.py
  - api/scripts/index_github.py
  - api/app/routers/coherence.py
  - specs/029-github-api-integration.md
done_when:
  - GraphStore: add `Contributor` and `Organization` node types; edges `CONTRIBUTES_TO`, `MAINTAINS`, `MEMBER_OF`
  - GitHub API client: repos, contributors, PRs, issues; rate-limit aware; ETag/conditional requests
  - Indexer: given Project (npm/pypi), resolve GitHub repo URL; fetch contributors, recent activity
  - Store: persist Contributor (login, name, avatar_url, contributions_count); Organization (login, type)
  - Coherence API: wire contributor_diversity, activity_cadence from real GitHub data when available
commands:
  - python3 -m pytest api/tests/test_github_client.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

No new public API endpoints. Extends existing:
- `GET /api/projects/{eco}/{name}/coherence` — components_with_data increases when GitHub data present


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

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

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add integration tests for error edge cases.


## Verification

```bash
python3 -m pytest api/tests/test_github_client.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
