# Spec 171: OpenClaw Daily Engagement Skill — Morning Brief + Contribution Opportunities

**Spec ID**: task_3610e59a86ceadce
**Spec Number**: 171
**Status**: Draft
**Author**: product-manager agent
**Date**: 2026-03-28
**Priority**: High

---

## Purpose

OpenClaw sessions today are reactive: an agent picks up a task, does the work, and exits. There is no
*pull* mechanism that brings the human or agent back to the network with useful, personalized context
before they decide what to do.

This spec defines an **OpenClaw daily engagement skill** — a morning brief generator that surfaces:
(1) news articles resonating with the user's ideas, (2) ideas in the network that need the user's
specific skills, (3) tasks whose provider slot matches the user's available executors, (4) contributors
who are geographically or ontologically nearby, and (5) patterns the network is actively discovering.

The skill is the **two-way engagement channel** that transforms passive browsing into active
participation: it calls the user in with relevant context and hands them a single action to take.

Without this, the network grows in the background but never creates the participation habit loop that
compounds contributor value over time.

---

## Summary

### What Exists Today

- `GET /api/ideas` — lists all ideas
- `GET /api/contributors/{id}` — contributor profile
- `GET /api/news` — recent ingested news items
- `cc inbox` — unread messages for this node
- No endpoint that computes a *personalized* digest across all entity families

### What This Spec Adds

1. **`GET /api/brief/daily`** — personalized daily brief API endpoint
2. **`cc brief`** — CLI command that calls the API and formats output for terminal
3. **`/brief`** — Web page showing the brief in a card-based layout
4. **`GET /api/brief/engagement-metrics`** — endpoint proving the skill is working over time
5. **Brief feedback loop**: `POST /api/brief/feedback` — user signals which card led to action

---

## Problem Statement

### The Participation Gap

The network ingests ideas, assigns tasks, and tracks contributions — but there is no daily touchpoint
that brings a contributor back. A contributor who last participated 3 days ago has no way to know:
- That a new idea resonates with their top concept cluster
- That a task waiting for a `claude` provider has been sitting for 12 hours
- That a contributor 2 hops away is working on something adjacent

### The Proof Gap

Even if a daily brief existed, we would have no way to measure whether it works. This spec adds an
engagement metrics endpoint so the effectiveness claim is falsifiable: if `brief → action` conversion
rate is below 10% after 30 days, the brief algorithm needs tuning. If it is above 30%, the skill is
the primary acquisition driver.

---

## Requirements

### R1 — Brief Computation API

**`GET /api/brief/daily`** must return a structured daily brief. Parameters:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `contributor_id` | string | optional | Personalize for this contributor. If omitted, return generic brief. |
| `limit_per_section` | int | optional, default 3 | Max items per section (1–10). |
| `as_of` | ISO 8601 datetime | optional | Compute brief as of this timestamp (for testing/replay). |

Response sections (all optional, omit if no data):

```json
{
  "generated_at": "2026-03-28T07:00:00Z",
  "contributor_id": "contrib_abc",
  "sections": {
    "news_resonance": [
      {
        "news_id": "news_123",
        "title": "Quantum coherence in biological systems",
        "resonance_score": 0.87,
        "matching_idea_id": "idea_456",
        "matching_idea_title": "Resonance as a biological organizing principle",
        "url": "https://example.com/article",
        "published_at": "2026-03-27T14:00:00Z"
      }
    ],
    "ideas_needing_skills": [
      {
        "idea_id": "idea_789",
        "title": "Graph-based coherence scoring",
        "skill_match": ["python", "neo4j"],
        "phase": "spec",
        "open_tasks": 2,
        "coherence_score": 0.74
      }
    ],
    "tasks_for_providers": [
      {
        "task_id": "task_aaa",
        "idea_title": "Edge navigation",
        "task_type": "impl",
        "provider": "claude",
        "waiting_since": "2026-03-28T04:30:00Z",
        "priority": "high"
      }
    ],
    "nearby_contributors": [
      {
        "contributor_id": "contrib_xyz",
        "display_name": "Alice",
        "shared_concepts": ["coherence", "graph-theory"],
        "hop_distance": 2,
        "recent_contribution": "Implemented edge navigation spec"
      }
    ],
    "network_patterns": [
      {
        "pattern_type": "convergence",
        "description": "3 independent contributors are adding graph-traversal related ideas",
        "idea_ids": ["idea_11", "idea_22", "idea_33"],
        "first_seen": "2026-03-26T00:00:00Z",
        "signal_strength": 0.65
      }
    ]
  },
  "cta": {
    "recommended_action": "claim_task",
    "target_id": "task_aaa",
    "reason": "Waiting 3.5h for a claude provider — this matches your executor profile"
  }
}
```

- Response 200 always (even if all sections are empty).
- Response 400 if `contributor_id` is provided but not found.
- Response 422 if `limit_per_section` is out of range (< 1 or > 10).
- `coherence_score` values are always in [0.0, 1.0].
- `resonance_score` values are always in [0.0, 1.0].
- `generated_at` is always UTC ISO 8601.

### R2 — Engagement Metrics API

**`GET /api/brief/engagement-metrics`** returns aggregate statistics proving the brief is working:

```json
{
  "window_days": 30,
  "briefs_generated": 142,
  "unique_contributors": 8,
  "section_click_rates": {
    "news_resonance": 0.31,
    "ideas_needing_skills": 0.24,
    "tasks_for_providers": 0.41,
    "nearby_contributors": 0.12,
    "network_patterns": 0.08
  },
  "cta_conversion_rate": 0.27,
  "actions_attributable_to_brief": 38,
  "trend": "improving"
}
```

Parameters: `window_days` (int, default 30, max 365).

- Returns 200 with zero values if no data exists yet (not 404).
- `trend` is `"improving"` | `"stable"` | `"degrading"` based on comparing latest 7-day window to prior 7-day window.

### R3 — Brief Feedback

**`POST /api/brief/feedback`** records that a brief card led to action:

```json
{
  "brief_id": "brief_abc",
  "section": "tasks_for_providers",
  "item_id": "task_aaa",
  "action": "claimed"
}
```

Valid `action` values: `"claimed"`, `"opened"`, `"dismissed"`, `"shared"`.
Response 201 on success, 404 if `brief_id` not found, 422 if `section` or `action` is invalid.

Each generated brief must have a stable `brief_id` in the response header `X-Brief-ID` and in
the response body as a top-level field.

### R4 — CLI Command

**`cc brief`** must:
- Call `GET /api/brief/daily` with the current node's identity (`cc identity get`).
- Print a formatted terminal brief with sections separated by headers.
- Each item in `tasks_for_providers` that matches the current node's provider type is
  highlighted (bold or colored).
- The CTA is printed last with a call-to-action box.
- `cc brief --json` prints raw JSON without formatting.
- `cc brief --section tasks_for_providers` prints only that section.
- `cc brief --mark-cta-done` sends `POST /api/brief/feedback` with `action: claimed` for the CTA item.

### R5 — Web Page `/brief`

- Accessible at `/brief` in the Next.js app.
- Shows the same sections as the API response in a card-based layout.
- Each card has a primary action button (Claim, View, Open) that POSTs to `/api/brief/feedback`.
- Page auto-refreshes if `generated_at` is older than 4 hours (client-side check).
- If `contributor_id` is set in the user's session/cookie, the brief is personalized.
- Skeleton loading state while API call is in flight.
- Empty state card: "The network is quiet — check back in a few hours." when all sections empty.

### R6 — Algorithm: Scoring Rules

The brief algorithm must use these signals (exact weights are implementation details, but the
signals must be present and contribute to ranking):

| Section | Primary signal | Secondary signal |
|---------|---------------|-----------------|
| `news_resonance` | Cosine similarity between news embedding and contributor's idea embeddings | Recency (decay over 48h) |
| `ideas_needing_skills` | Tag overlap between contributor's skills and idea's required skills | Idea coherence score |
| `tasks_for_providers` | Provider type match (exact) | Wait time (prefer longer-waiting tasks) |
| `nearby_contributors` | Shared concept count | Hop distance in contributor graph |
| `network_patterns` | Idea count in convergence cluster | Time since first seen (prefer recent) |

If no contributor_id is provided, `news_resonance` uses network-wide trending, `ideas_needing_skills`
uses ideas with the highest coherence score, and `tasks_for_providers` lists the longest-waiting tasks.

### R7 — Proof Mechanism

The system must be able to answer "Is the brief working?" via observable metrics. The following
must be true within 30 days of deployment:

- `engagement-metrics.briefs_generated >= 1` (at least one brief was generated)
- `engagement-metrics.cta_conversion_rate` is computable (not null)
- At least one `POST /api/brief/feedback` record exists

If these are not true after 30 days, the skill implementation is considered failing and must trigger
a hotfix task automatically (via the `verify-production` phase gate).

---

## Data Model

```yaml
DailyBrief:
  id: string (uuid)
  contributor_id: string | null
  generated_at: datetime (UTC)
  sections_json: text (JSON blob of sections)
  cta_json: text (JSON blob of CTA)

BriefFeedback:
  id: string (uuid)
  brief_id: string (FK → DailyBrief.id)
  section: string (enum: news_resonance | ideas_needing_skills | tasks_for_providers | nearby_contributors | network_patterns)
  item_id: string
  action: string (enum: claimed | opened | dismissed | shared)
  recorded_at: datetime (UTC)
```

Database: PostgreSQL (existing schema). Migrations add these two tables.

---

## Files to Create/Modify

- `api/app/routers/brief.py` — Create: route handlers for `/api/brief/daily`, `/api/brief/feedback`, `/api/brief/engagement-metrics`
- `api/app/services/brief_service.py` — Create: scoring algorithm, brief assembly logic
- `api/app/models/brief.py` — Create: Pydantic request/response models (DailyBriefResponse, BriefFeedbackRequest, EngagementMetricsResponse)
- `api/alembic/versions/XXXXXXXX_add_brief_tables.py` — Create: PostgreSQL migration adding `daily_briefs` and `brief_feedback` tables
- `api/app/main.py` — Modify: register brief router
- `api/tests/test_brief.py` — Create: pytest tests (minimum 15 test cases covering all acceptance criteria)
- `web/src/app/brief/page.tsx` — Create: Next.js `/brief` page
- `web/src/components/brief/BriefCard.tsx` — Create: card component for each brief item
- `web/src/components/brief/BriefSection.tsx` — Create: section container with header
- `web/src/components/brief/CtaBox.tsx` — Create: CTA call-to-action block
- `cli/lib/commands/brief.mjs` — Create: `cc brief` CLI command implementation
- `cli/lib/commands/index.mjs` — Modify: register `brief` command in CLI router

---

## Acceptance Tests

```
api/tests/test_brief.py::test_get_daily_brief_anonymous_returns_200
api/tests/test_brief.py::test_get_daily_brief_with_valid_contributor_returns_personalized
api/tests/test_brief.py::test_get_daily_brief_with_invalid_contributor_returns_400
api/tests/test_brief.py::test_get_daily_brief_limit_per_section_out_of_range_returns_422
api/tests/test_brief.py::test_sections_respect_limit_per_section
api/tests/test_brief.py::test_response_includes_brief_id_header
api/tests/test_brief.py::test_post_feedback_valid_returns_201
api/tests/test_brief.py::test_post_feedback_invalid_brief_id_returns_404
api/tests/test_brief.py::test_post_feedback_invalid_action_returns_422
api/tests/test_brief.py::test_engagement_metrics_returns_zeros_when_empty
api/tests/test_brief.py::test_engagement_metrics_reflects_generated_briefs
api/tests/test_brief.py::test_engagement_metrics_window_days_respected
api/tests/test_brief.py::test_tasks_for_providers_ordered_by_wait_time
api/tests/test_brief.py::test_news_resonance_scores_in_range
api/tests/test_brief.py::test_coherence_scores_in_range
```

---

## API Contract Summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/brief/daily` | none | Generate daily brief |
| `POST` | `/api/brief/feedback` | none | Record user action on brief item |
| `GET` | `/api/brief/engagement-metrics` | none | Aggregate effectiveness metrics |

---

## Verification Scenarios

### Scenario 1: Anonymous brief generation (baseline)

**Setup**: API is running. At least one idea and one task exist in the database.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/brief/daily | jq '{generated_at, sections_keys: (.sections | keys)}'
```

**Expected result**:
- HTTP 200
- `generated_at` is a valid ISO 8601 UTC timestamp from the last 60 seconds
- `sections` is an object (may have 0–5 keys, all from the defined set)
- Response body includes `brief_id` field (string, non-empty)
- Response header `X-Brief-ID` matches body `brief_id`

**Edge case**: `GET /api/brief/daily?contributor_id=nonexistent` returns HTTP 400 with `{"detail": "Contributor not found: nonexistent"}`.

**Edge case**: `GET /api/brief/daily?limit_per_section=0` returns HTTP 422.

**Edge case**: `GET /api/brief/daily?limit_per_section=11` returns HTTP 422.

---

### Scenario 2: Feedback loop (create-read cycle)

**Setup**: One brief has been generated (Scenario 1 ran first). `brief_id` captured from response.

**Action**:
```bash
BRIEF_ID=$(curl -s 'https://api.coherencycoin.com/api/brief/daily' | jq -r '.brief_id')

curl -s -X POST https://api.coherencycoin.com/api/brief/feedback \
  -H "Content-Type: application/json" \
  -d "{\"brief_id\": \"$BRIEF_ID\", \"section\": \"tasks_for_providers\", \"item_id\": \"task_test\", \"action\": \"opened\"}"
```

**Expected result**:
- HTTP 201
- Response contains `{"id": "<uuid>", "brief_id": "<BRIEF_ID>", "section": "tasks_for_providers", "action": "opened", "recorded_at": "<ISO8601>"}`

**Then**:
```bash
curl -s 'https://api.coherencycoin.com/api/brief/engagement-metrics' | jq '.briefs_generated, .actions_attributable_to_brief'
```
- `briefs_generated` is ≥ 1
- `actions_attributable_to_brief` is ≥ 1

**Edge case**: POST feedback with `brief_id = "nonexistent"` returns HTTP 404.

**Edge case**: POST feedback with `action = "invalid_action"` returns HTTP 422.

---

### Scenario 3: Personalized brief for known contributor

**Setup**: Contributor `contrib_test` exists with skills `["python", "neo4j"]`. At least one idea has tag `neo4j`. At least one task has `provider = "claude"`.

**Action**:
```bash
curl -s 'https://api.coherencycoin.com/api/brief/daily?contributor_id=contrib_test' | jq '.sections.ideas_needing_skills[0].skill_match'
```

**Expected result**:
- HTTP 200
- `sections.ideas_needing_skills` is a non-empty array (since contributor has matching skills)
- Each item in `ideas_needing_skills` has `coherence_score` in [0.0, 1.0]
- `cta` field is present and has `recommended_action`, `target_id`, `reason`

**Edge case**: If contributor has no skills defined, `ideas_needing_skills` may be empty — this is valid (not an error).

---

### Scenario 4: Engagement metrics trend detection

**Setup**: 14 briefs have been generated over the last 14 days. In the first 7 days, 3 feedbacks were recorded. In the last 7 days, 8 feedbacks were recorded.

**Action**:
```bash
curl -s 'https://api.coherencycoin.com/api/brief/engagement-metrics?window_days=14' | jq '{trend, cta_conversion_rate, briefs_generated}'
```

**Expected result**:
- `briefs_generated` = 14
- `cta_conversion_rate` = (total feedbacks with action=claimed) / (total briefs)
- `trend` = `"improving"` (since last-7d has more actions than first-7d)

**Edge case**: `GET /api/brief/engagement-metrics?window_days=400` returns HTTP 422 (`window_days` max is 365).

---

### Scenario 5: CLI brief command

**Setup**: `cc` CLI is installed. API is reachable.

**Action**:
```bash
cc brief --json | jq '.sections | keys'
```

**Expected result**:
- Output is valid JSON
- `keys` is an array, subset of `["news_resonance","ideas_needing_skills","tasks_for_providers","nearby_contributors","network_patterns"]`
- No error output to stderr

**Then**:
```bash
cc brief --section tasks_for_providers
```
- Output contains only the `tasks_for_providers` section formatted as text
- Other sections are not printed

**Edge case**:
```bash
cc brief --section invalid_section
```
- Exits with code 1 and prints `Error: unknown section 'invalid_section'`

---

## Concurrency Behavior

- **Read operations** (`GET /api/brief/daily`, `GET /api/brief/engagement-metrics`): safe for concurrent access; no locking required. Briefs are computed fresh on each request (no caching in Phase 1).
- **Write operations** (`POST /api/brief/feedback`): last-write-wins per `(brief_id, section, item_id)` — duplicate feedback for the same item in the same brief is allowed (both records stored, metrics count distinct actions).

---

## How We Know It Is Working — Proof Signals

The spec was written to answer the open question: "How can we improve this, show whether it is
working, and make that proof clearer over time?"

### Immediate proof (Day 1)

- `GET /api/brief/engagement-metrics` returns `briefs_generated >= 1` within 24h of deployment.
- `cc brief` CLI exits with code 0 and prints at least one section.
- `/brief` page loads without error on the production site.

### Short-term proof (Day 7–14)

- `cta_conversion_rate > 0.0` — at least one brief card led to a claimed task or opened idea.
- `section_click_rates.tasks_for_providers` is the highest-value section (hypothesis: tasks with
  waiting time attract immediate action).

### Long-term proof (Day 30+)

| Metric | Healthy threshold | Degraded threshold | Source |
|--------|------------------|--------------------|--------|
| `briefs_generated` / day | ≥ 1 | < 1 | engagement-metrics |
| `cta_conversion_rate` | ≥ 0.10 | < 0.05 | engagement-metrics |
| `actions_attributable_to_brief` | ≥ 5 / week | < 2 / week | engagement-metrics |
| `trend` | `improving` or `stable` | `degrading` | engagement-metrics |

If any long-term metric falls below "Degraded" for 7 consecutive days, the pipeline should
auto-create a `spec` task to revise the brief algorithm.

### Algorithm iteration loop

Because `POST /api/brief/feedback` records which section drove each action, the algorithm can be
tuned iteratively:
1. Check `section_click_rates` weekly.
2. If a section's click rate drops below 5%, audit its scoring signal.
3. If `news_resonance` is unused, investigate embedding quality.
4. If `tasks_for_providers` converts at > 50%, increase its default position in brief output.

---

## Out of Scope

- Email or push notification delivery of the brief (Phase 2 follow-up)
- AI-generated natural language summaries of the brief (Phase 3 follow-up)
- Brief scheduling/caching layer (Phase 2 — compute fresh in Phase 1)
- Per-contributor preference settings for which sections to show
- Mobile-optimized brief layout
- Brief sharing (URL-based public brief view)

---

## Risks and Assumptions

- **Risk (Medium)**: No embeddings exist for news items → `news_resonance` section always empty. Mitigation: fall back to keyword matching on title/tags; emit a warning in logs if < 10% of news items have embeddings.
- **Risk (High)**: Contributor skills not populated → `ideas_needing_skills` always empty. Mitigation: return generic top-coherence ideas when skills are missing; add onboarding prompt in `/brief` web page.
- **Risk (Medium)**: Brief generation too slow (> 2s). Mitigation: cap each section query to 50ms using `LIMIT 20` with indexed queries; add `X-Brief-Generation-Time-Ms` response header for observability.
- **Risk (Low)**: `cc brief` CLI not installed on agent nodes. Mitigation: document install step in RUNBOOK.md; fall back to `curl /api/brief/daily` in agent skills.
- **Assumption**: Contributor skills can be inferred from their previous task types and idea tags if not explicitly set. If this assumption is false, `ideas_needing_skills` may require a separate skills-onboarding spec before it can be meaningfully populated.

---

## Known Gaps and Follow-up Tasks

- **Gap**: No embedding infrastructure exists yet for news items. The `news_resonance` section requires a vector similarity query. Follow-up: spec for news embedding pipeline (Phase 2).
- **Gap**: `nearby_contributors` section requires the contributor graph to have edges. If < 5 contributors exist, this section will be sparse. Acceptable for MVP.
- **Gap**: `network_patterns` detection requires a background pattern-detection job that does not exist yet. In Phase 1, this section can return static patterns derived from tag co-occurrence counts (no ML required). Follow-up: spec for pattern-detection background job.
- **Gap**: The `cc brief --mark-cta-done` flow requires the node to know its current task assignment. This may not be available in all node types. Acceptable for MVP — agents can manually POST to `/api/brief/feedback`.

---

## Failure/Retry Reflection

- **Failure mode**: Brief generation returns 500 because news embedding service is down.
  **Blind spot**: The brief service treats all section failures as fatal.
  **Next action**: Wrap each section in a try/except; return partial brief with empty section rather than 500.

- **Failure mode**: `cc brief` exits 0 but prints nothing — empty brief in a quiet network.
  **Blind spot**: Empty brief is valid but confusing.
  **Next action**: Print "The network is quiet — no matching items found" as explicit empty state.

- **Failure mode**: `engagement-metrics.cta_conversion_rate` is always 0 because agents never send feedback.
  **Blind spot**: CLI skill must send feedback automatically on CTA action, not rely on manual call.
  **Next action**: `cc brief --mark-cta-done` must be documented in the OpenClaw skill protocol as a required post-action step.

---

## Decision Gates

- **Algorithm weights**: The exact scoring weights for each section are left to the implementer for Phase 1. The product owner should review weights after the first 7 days of data from `engagement-metrics`.
- **Embedding dependency**: If no embedding infrastructure is available at implementation time, `news_resonance` should be implemented as keyword/tag-based scoring with a clear TODO comment and a known-gap log line. This is acceptable for Phase 1.
