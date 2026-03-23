---
name: coherence-daily-brief
description: >
  Your personalized morning brief from the Coherence Network. Scans 100+ news
  articles from 5 sources, matches them to YOUR ideas using resonance scoring,
  and shows what the world is saying that aligns with what you are building.
  Run this each morning to stay connected to your coherence surface.
version: "1.0.0"
author: coherence-network
license: MIT
compatibility: Requires internet access to api.coherencycoin.com
allowed-tools: Bash Read
metadata:
  openclaw:
    category: engagement
    tags: [daily-brief, news, resonance, engagement, morning]
    hub_url: https://coherencycoin.com
    api_url: https://api.coherencycoin.com
  schedule:
    default: "0 8 * * *"
    description: "Runs at 8am daily (configurable)"
---

# Coherence Daily Brief

Your morning resonance surface — what the world is saying that aligns with what you are building.

## How It Works

1. **Fetch** — Pull 100+ articles from 5 RSS sources (Hacker News, TechCrunch, Ars Technica, The Guardian Tech, Reddit r/programming)
2. **Match** — Score each article against your staked ideas using the Concept Resonance Kernel
3. **Rank** — Surface the top matches with scores, keywords, and explanations
4. **Engage** — Show which ideas are most alive in today's news cycle

## Resonance Algorithm

Each article is scored against each of your ideas using 4 factors:

- **Keyword overlap** (Jaccard similarity) — how many meaningful words do the article and idea share?
- **Phrase boost** — if idea keywords appear in the article *title* (not just body), that's editorial emphasis (+0.15 per match)
- **Recency boost** — fresh news is actionable (<1hr: +0.2, <6hr: +0.1, <24hr: +0.05)
- **Confidence weight** — ideas you believe in more get stricter matching, focusing your attention

## What You Know About Me (Contributor Profile)

The system stores contributor knowledge at three levels:

### 1. Identity (who you are)
```
GET /api/contributors/{id}           → name, email, type (human/system)
GET /api/identity/{contributor_id}   → linked identities (GitHub, Ethereum, etc.)
```
Your identity is your contributor record plus any linked external accounts. This is stored in Neo4j (graph) and PostgreSQL (relational).

### 2. Interests (what you care about)
```
GET /api/ideas?contributor_id={id}   → ideas you created
GET /api/ideas/{id}/stake            → ideas you staked CC on
GET /api/ideas/{id}/questions        → questions you asked
GET /api/governance/change-requests  → changes you proposed or voted on
```
Your interests are inferred from your *actions*: which ideas you created, staked on, questioned, voted on. The resonance engine uses these to personalize your brief.

### 3. Activity (what you've done)
```
GET /api/value-lineage/links         → value flows you participated in
GET /api/runtime/events              → API usage patterns
GET /api/inventory/commit-evidence   → git commits attributed to you
```
Your activity feeds back into coherence scoring — more activity in an area increases the resonance weight for related news.

### Privacy
- No personal data is shared with news sources
- Resonance is computed locally against public RSS feeds
- Your contributor profile is visible to other network participants (it's a collaboration network)
- You control what you stake on and what questions you ask — that's your signal

## Running the Brief

### Via API
```bash
# Get your personalized resonance feed
curl https://api.coherencycoin.com/api/news/resonance/{your_contributor_id}

# Get raw feed
curl https://api.coherencycoin.com/api/news/feed

# Get trending keywords
curl https://api.coherencycoin.com/api/news/trending
```

### Via OpenClaw / Claude
```
/coherence-daily-brief
```

### Via Scheduled Task
The brief can be scheduled via OpenClaw to run every morning:
```json
{
  "schedule": "0 8 * * *",
  "skill": "coherence-daily-brief",
  "contributor_id": "your-id"
}
```

## Example Output

```
======================================================================

  COHERENCE NETWORK — MORNING BRIEF
  March 23, 2026 | seeker71

======================================================================

  127 articles scanned from 5 sources
  Matched against your 10 active ideas

  TOP RESONANCE
  --------------------------------------------------
  █████████░░░░░░░░░░░ 45%
  ChatGPT, Claude, and Gemini Render Markdown in the Browser
  ↳ resonates with: AI agent federation and multi-provider orchestration
  ↳ why: Matched keywords: claude, gemini. Title match. Recency boost.

  ██████░░░░░░░░░░░░░░ 32%
  Reverse engineering a viral open source launch
  ↳ resonates with: Open source contribution intelligence
  ↳ why: Matched keywords: open, source. Title match.

  BY IDEA
  --------------------------------------------------
  AI agent federation                    2 articles  (top: 45%)
  Open source contribution               5 articles  (top: 32%)
  Data privacy and AI governance          5 articles  (top: 36%)
  News ingestion and daily briefs         5 articles  (top: 27%)

  ==================================================
  Your coherence surface today: what the world is
  saying that aligns with what you are building.
  ==================================================
```

## How Other Contributors See Different Briefs

Two contributors staking on different ideas get completely different briefs from the same feed:

**Contributor A** (staked on: AI agents, MCP servers)
→ Sees: Claude/Gemini article, Cursor model article, TypeScript 6.0

**Contributor B** (staked on: privacy, regulation, crypto)
→ Sees: FBI hacker article, fake compliance article, blockchain treasury news

Same 127 articles. Different resonance surfaces. Your stakes define your signal.
