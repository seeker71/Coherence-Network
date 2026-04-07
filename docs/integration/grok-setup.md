# Use Coherence Network from Grok

Grok can interact with the Coherence Network REST API to create ideas, track contributions, measure impact, and navigate the full idea-to-realization lifecycle.

## How It Works

The Coherence Network API is public at `https://api.coherencycoin.com`. Grok can call it via HTTP. No special plugin required — just describe what you want and ask Grok to make the API call.

## Quick Start Prompts

### Create an Idea

> Tell Grok: "Call the Coherence Network API at https://api.coherencycoin.com/api/ideas to create an idea. POST with header X-API-Key: dev-key and JSON body: name is 'Street Art Map', description is 'Crowdsourced map of street art in our city — anyone can add a mural, tag who made it, and rate it. Goal: map 200 murals by summer.' Set potential_value to 40 and estimated_cost to 5."

### Add Questions

> "Now POST to https://api.coherencycoin.com/api/ideas/street-art-map/questions with the same API key header. Question: 'How do we verify that submitted murals actually exist?' Value_to_whole: 25, estimated_cost: 3."

### Create a Spec

> "POST to https://api.coherencycoin.com/api/spec-registry with API key. Title: 'Street Art Submission Process', summary: 'Contributors submit photo + location + artist name. Verified by second contributor visiting the same spot. Unverified submissions visible but marked as unconfirmed.' Set idea_id to 'street-art-map'."

### Record Work

> "POST to https://api.coherencycoin.com/api/contributions/record with API key. Contributor_display_name: 'Alex', contribution_type: 'community', description: 'Photographed and mapped 15 murals in the Mission District', idea_id: 'street-art-map', amount_cc: 8."

### Update Measurements

> "PATCH https://api.coherencycoin.com/api/ideas/street-art-map with API key. Set actual_value to 30, actual_cost to 4, manifestation_status to 'validated'."

### Check the Full Picture

> "GET https://api.coherencycoin.com/api/ideas/street-art-map and show me all the details."

## The Complete Flow

```
Step 1: Create idea       → POST /api/ideas
Step 2: Ask questions      → POST /api/ideas/{id}/questions
Step 3: Write spec         → POST /api/spec-registry
Step 4: Record work        → POST /api/contributions/record
Step 5: Update stage       → PATCH /api/ideas/{id}
Step 6: Measure impact     → PATCH /api/ideas/{id} (actual_value, actual_cost)
Step 7: Check progress     → GET /api/ideas/{id}
Step 8: See all specs      → GET /api/spec-registry/cards
Step 9: Vote on changes    → POST /api/governance/change-requests
Step 10: Check CC balance  → GET /api/cc/supply
```

## API Reference

**Base URL**: `https://api.coherencycoin.com`
**Auth**: `X-API-Key: dev-key` header (for write operations)
**Docs**: `https://api.coherencycoin.com/docs` (interactive Swagger UI with all 386 endpoints)

### Key Endpoints

| Action | Method | Path |
|--------|--------|------|
| List ideas | GET | `/api/ideas?limit=20` |
| Create idea | POST | `/api/ideas` |
| Get idea detail | GET | `/api/ideas/{id}` |
| Update idea | PATCH | `/api/ideas/{id}` |
| Add question | POST | `/api/ideas/{id}/questions` |
| Create spec | POST | `/api/spec-registry` |
| List specs | GET | `/api/spec-registry/cards` |
| Record contribution | POST | `/api/contributions/record` |
| Contributor ledger | GET | `/api/contributions/ledger/{contributor_id}` |
| Propose change | POST | `/api/governance/change-requests` |
| Vote | POST | `/api/governance/change-requests/{id}/votes` |
| CC supply | GET | `/api/cc/supply` |
| Stake CC | POST | `/api/cc/stake` |
| Health | GET | `/api/health` |
| Idea lifecycle | GET | `/api/ideas/{id}/lifecycle` |
| Idea rollup | GET | `/api/ideas/{id}/rollup` |
| Right-sizing | GET | `/api/ideas/right-sizing` |
| Task chains | GET | `/api/agent/task-chains/stats` |

## MCP Server (If Grok Supports MCP in the Future)

The Coherence Network also publishes an MCP server with 60 typed tools. If/when Grok adds MCP support, configure it:

```json
{
  "mcpServers": {
    "coherence-network": {
      "command": "npx",
      "args": ["coherence-mcp-server"],
      "env": {
        "COHERENCE_API_URL": "https://api.coherencycoin.com"
      }
    }
  }
}
```

This gives Grok structured tool access to all 60 operations without raw HTTP calls.

## Example: Full Idea Lifecycle in One Conversation

```
You: I want to organize free coding workshops for kids in my neighborhood.

Grok: Let me create that idea in Coherence Network.
      [POST /api/ideas → created "neighborhood-coding-workshops"]

      Created! ID: neighborhood-coding-workshops
      Potential value: 60.0 | Estimated cost: 12.0 | Confidence: 0.6

      Three questions to consider:
      1. Where will you hold the workshops? (value: 30)
      2. Who will teach? (value: 25)
      3. What age range? (value: 15)

      Want me to add these questions?

You: Yes, add them. For location, the library has a free meeting room Saturdays.

Grok: [POST 3 questions, answers question #1]
      Questions added! Library meeting room answers the location question.

      That's your highest-value question resolved. Confidence update?

You: Yes, bump it to 0.8. My friend Sarah is a software engineer and wants to teach.

Grok: [PATCH confidence, POST contribution for Sarah]
      Updated confidence to 0.8. Recorded Sarah's commitment as a contribution.

      Ready to write a plan? I can create a spec covering:
      - Schedule (Saturdays 10am-12pm)
      - Curriculum (Scratch → Python → web basics)
      - Materials needed (laptops — does the library have them?)

You: The library has 10 Chromebooks we can use. Write that spec.

Grok: [POST /api/spec-registry]
      Spec created: "Kids Coding Workshop Operations"
      Your idea is now at stage: specced.

      Next step: start teaching and record what happens!

You: We did our first workshop! 8 kids showed up. Sarah taught Scratch.

Grok: [POST contributions for Sarah and you, PATCH stage to implementing]
      Recorded! Two contributions logged.
      Stage updated to: implementing.

      After a few more sessions, we'll have enough data to measure impact.

You: After 6 weeks: 12 regular attendees, 3 built their own games,
     one parent asked about a Python class for adults.

Grok: [PATCH actual_value=45, actual_cost=8, manifestation_status=validated]
      Impact measured:
      - 12 regular attendees (from 0)
      - 3 student projects completed
      - Adult demand emerging (potential fork: adult coding workshop)
      - ROI: 5.6x on effort invested
      - Status: VALIDATED

      Want me to create a child idea for the adult Python class?
```

Every step is an API call. Every data point is stored. The idea went from a thought to a validated program with measured impact — all tracked in one conversation.
