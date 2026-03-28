---
name: coherence-daily-engagement
description: >
  Two-way engagement for the Coherence Network: one call returns your morning
  brief (news matched to your ideas), ideas that need skills like yours, agent
  tasks waiting for providers, contributors to collaborate with, and patterns
  the network is discovering. Use daily to turn browsing into participation.
version: "1.0.0"
author: coherence-network
license: MIT
compatibility: Requires api.coherencycoin.com (or self-hosted API with engagement routes)
allowed-tools: Bash Read
metadata:
  openclaw:
    category: engagement
    tags: [daily-brief, engagement, tasks, contributors, patterns, morning]
    hub_url: https://coherencycoin.com
    api_url: https://api.coherencycoin.com
  schedule:
    default: "30 7 * * *"
    description: "Daily engagement after markets open (adjust TZ in runner)"
---

# Coherence Daily Engagement

Personalized bundle for **participation**, not just consumption.

## Primary API

Replace `{contributor_id}` with your contributor name or id (e.g. `seeker71`):

```bash
curl -sS "https://api.coherencycoin.com/api/engagement/daily/seeker71?refresh=false"
```

Optional query parameters:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `refresh` | false | Force RSS refresh before scoring |
| `news_limit` | 100 | Cap articles scanned |
| `top_news_matches` | 10 | Max news items in `morning_brief` |
| `task_limit` | 12 | Max pending agent tasks listed |
| `peer_limit` | 12 | Max other contributors |

## Response sections

- **morning_brief** — `top_matches` with resonance scores, titles, URLs, linked ideas.
- **ideas_needing_skills** — Ideas with unanswered questions overlapping your staked-idea keywords.
- **tasks_for_providers** — Queue items with `status=pending` for runners to claim.
- **contributors_nearby** — Recent contributor nodes (graph) excluding you.
- **network_patterns** — Trending keywords from news + hot ideas from `get_resonance_feed`.

## OpenClaw invocation

```
/coherence-daily-engagement seeker71
```

Have the agent call the GET endpoint above and summarize each section in plain language with 1–3 concrete next actions (stake, pick up task, message contributor).

## Relation to coherence-daily-brief

`coherence-daily-brief` focuses on **news resonance** only. This skill adds **tasks, peers, and network signals** in one response for full-loop engagement.
