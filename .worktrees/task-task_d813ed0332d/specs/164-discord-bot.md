# Spec 164 — Discord Bot Integration

**Idea:** social-platform-bots
**Status:** implementing
**Platform:** Discord (selected for best developer API, free tier, OSS-friendly community)

## Summary

Build a Discord bot that exposes Coherence Network idea portfolio features via
slash commands, reaction voting, idea-channel sync, and pipeline feeds.

## Rationale

Discord offers the richest bot developer experience: slash commands, gateway
intents, webhooks, embeds, reaction events.  Free tier and OSS community make
it the lowest-friction first platform for social-platform-bots.

## Deliverables

### API Additions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ideas/{idea_id}/questions/{idx}/vote` | POST | Cast a vote on an idea question by index |

### Discord Bot Commands

| Command | Description |
|---------|-------------|
| `/cc-idea <id>` | Fetch and display idea details as a rich embed |
| `/cc-status` | Show portfolio summary (total, validated, top ROI) |
| `/cc-stake <id> <amount>` | Stake CC on an idea |

### Discord Bot Features

- **Idea-channel sync**: Post new ideas to a designated channel automatically
- **Pipeline feed**: Forward pipeline events (task completed, idea advanced) to a feed channel
- **Reaction voting**: Users react to idea embeds to vote on open questions

## Models

### VoteCreate (request body)
```python
class VoteCreate(BaseModel):
    voter_id: str          # contributor or Discord user ID
    direction: str = "up"  # "up" or "down"
```

### VoteResult (response)
```python
class VoteResult(BaseModel):
    idea_id: str
    question_index: int
    question: str
    votes_up: int
    votes_down: int
    voter_id: str
```

## Verification

1. `POST /api/ideas/{id}/questions/{idx}/vote` returns 200 with vote tally
2. Vote on nonexistent idea returns 404
3. Vote on out-of-range question index returns 404
4. Discord bot module defines slash command handlers for `/cc-idea`, `/cc-status`, `/cc-stake`
5. Bot formats idea data as Discord embeds with colour-coded status
6. At least 6 API tests pass covering vote endpoint and bot formatting

## Risks and Assumptions

- Discord bot token is provided via `DISCORD_BOT_TOKEN` env var at runtime
- Bot does not run in the API process — it is a standalone service
- Reaction voting maps 👍/👎 to up/down votes via the vote API

## Known Gaps and Follow-up Tasks

- Rate limiting per Discord user not yet implemented
- Channel sync requires webhook URL configuration (future spec)
- Multi-guild support deferred
