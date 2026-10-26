---
name: coherence-daily-brief
description: >
  Explore news through interests and ideas you choose. Read the Coherence
  Network feed, explain returned matches, and follow curiosity, play, learning
  or creation at your pace. Run on request; schedule only when asked.
version: "1.1.0"
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

News to explore through interests you choose. A brief can offer a discovery,
a playful connection or something useful; the encounter sets its direction.

## How It Works

1. Read the requested feed or resonance endpoint. Report its actual article
   and idea counts; availability and freshness come from that response.
2. Use a contributor ID only when the person has supplied or authorized it.
   The general feed and general resonance route are available without one.
3. Explain a few returned matches using their evidence and source links.
   Scores describe keyword matching, not the person's inner state or values.
4. Let a satisfying brief stand. Follow-up, saving and scheduling follow the
   person's request and established authorization.

## Resonance Algorithm

Each article is scored against each of your ideas using 4 factors:

- **Keyword overlap** (Jaccard similarity) — how many meaningful words do the article and idea share?
- **Title match** — one title keyword match adds 0.15; two or more add 0.30
- **Recency boost** — fresh news is actionable (<1hr: +0.2, <6hr: +0.1, <24hr: +0.05)
- **Confidence weight** — the idea record's confidence multiplies the capped combined score

## What the current route uses

`GET /api/news/resonance/{contributor_id}` reads idea IDs from that
contributor's contribution-ledger history (up to 500 records), filters the
current idea portfolio, and scores feed items against those ideas. The
response calls this set `staked_idea_ids`; the implementation currently accepts
any ledger record carrying an idea ID. When that set is empty, it uses the
whole portfolio. Describe that result as general matching.

The request goes to the configured API server, where feed fetching and
matching run. The host assistant also receives the returned material. Inspect
the actual host and service controls before making statements about storage,
visibility, retention or further processing. This skill itself creates no
profile and grants no additional access. Personal interests offered in a
conversation stay within that conversation's established scope; publishing,
identity linking and durable memory need their own authorization.

The implementation is in `api/app/routers/news.py` and
`api/app/services/news_resonance_service.py`. Recheck those boundaries when
making a more specific data-use claim.

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
