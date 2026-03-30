# Spec 164: Discord Bot — Channels Per Idea, Slash Commands, Live Pipeline Feed

**Spec ID**: 164-discord-bot-channels-per-idea
**Task ID**: task_54c58715153ef78e
**Status**: approved
**Priority**: high
**Author**: product-manager agent
**Date**: 2026-03-28
**Depends on**: Spec 119 (Coherence Credit), Spec 157 (Investment UX), API `/api/ideas`, `/api/pipeline`, `/api/contributors`
**Depended on by**: future Discord-native contribution flows

---

## Summary

A Discord bot (`coherence-bot`) lives in a Discord server and provides:

1. **Channels per active idea** — each idea in `specced`/`implementing`/`testing` stage gets a dedicated `#idea-<slug>` channel with a pinned rich embed showing the idea card.
2. **`/cc-idea`** — slash command to submit a new idea directly from Discord; creates a concept in the API and posts the card to `#idea-submissions`.
3. **`/cc-status`** — slash command to display pipeline health (queue depth, node status, recent task completions).
4. **`/cc-stake`** — slash command to invest CC in any idea by ID; calls `POST /api/investments`.
5. **Live pipeline feed** — the `#pipeline-feed` channel receives a new message whenever a task completes or fails, in real time (polling every 60 s or via webhook).
6. **Reaction-based voting** — idea cards use 👍/👎/🔥 reactions to cast votes; reaction totals sync to the API `open_questions` answer field.
7. **Thread per open question** — every `open_questions` entry on an idea auto-creates a Discord thread inside `#idea-<slug>`.

The bot is implemented in **Node.js** using **Discord.js v14** and calls the existing Coherence Network REST API. No new database tables are required at launch; all persistent state lives in the API.

---

## Motivation

The network currently requires contributors to use the CLI or web UI to participate. Discord is where many OSS contributors already spend time. Bringing the pipeline into Discord:

- Removes friction: submit an idea, stake CC, and vote without leaving Discord.
- Makes the pipeline visible to people who have never opened the web UI.
- Creates a social surface for open questions — threads with real conversation that feed back into the idea graph.

**Working proof** must be visible: every channel pinned embed shows the idea's `manifestation_status` badge and the live `free_energy_score`. The `#pipeline-feed` shows real completions, not stubs. Anyone can `/cc-status` and see the same numbers as `curl api.coherencycoin.com/api/health`.

---

## Goals

1. Deploy `coherence-bot` to the VPS alongside the existing Docker Compose stack.
2. Sync active idea channels on startup and on a 5-minute polling loop.
3. Implement `/cc-idea`, `/cc-status`, `/cc-stake` slash commands.
4. Post pipeline events to `#pipeline-feed` in real time.
5. Reaction-based voting wired to the API.
6. Auto-create threads for every `open_questions` entry.

---

## Non-Goals

- Full bidirectional graph editing via Discord (Phase 2).
- Mobile push notifications (separate spec).
- Per-user CC wallet balances displayed in Discord (deferred to Spec 157 web rollout).
- Moderation / permission enforcement beyond Discord role checks.

---

## Architecture

### Components

```
Discord Server
├── Category: Active Ideas
│   ├── #idea-graphql-cache      ← auto-created per active idea
│   ├── #idea-discord-bot        ← this spec's own channel
│   └── ...
├── #idea-submissions            ← /cc-idea output + voting
├── #pipeline-feed               ← task completions, failures, deploys
└── #bot-commands                ← /cc-status, /cc-stake output

coherence-bot (Node.js / Discord.js v14)
├── src/
│   ├── index.js                 ← Discord client, event loop
│   ├── commands/
│   │   ├── cc-idea.js           ← /cc-idea slash command
│   │   ├── cc-status.js         ← /cc-status slash command
│   │   └── cc-stake.js          ← /cc-stake slash command
│   ├── sync/
│   │   ├── idea-channel-sync.js ← create/update/archive channels
│   │   └── pipeline-feed.js     ← poll pipeline events
│   └── lib/
│       ├── api.js               ← thin REST client for coherence API
│       ├── embeds.js            ← rich embed builders
│       └── reactions.js         ← reaction vote handler
├── package.json
├── Dockerfile
└── .env.example
```

### Data Flow

```
Coherence API (REST)
      ↑ POST ideas, investments, votes
      ↓ GET ideas, pipeline events

coherence-bot
      ↕ Discord.js
Discord Gateway
      ↕ interactions
Discord Users
```

No Neo4j or Postgres access directly — all reads/writes go through the REST API.

---

## File Paths

| Path | Purpose |
|------|---------|
| `discord-bot/` | New top-level directory; sibling of `api/` and `web/` |
| `discord-bot/src/index.js` | Entry point, Discord client init, event wiring |
| `discord-bot/src/commands/cc-idea.js` | `/cc-idea` command handler |
| `discord-bot/src/commands/cc-status.js` | `/cc-status` command handler |
| `discord-bot/src/commands/cc-stake.js` | `/cc-stake` command handler |
| `discord-bot/src/sync/idea-channel-sync.js` | Active idea channel sync loop |
| `discord-bot/src/sync/pipeline-feed.js` | Pipeline event feed loop |
| `discord-bot/src/lib/api.js` | REST API client |
| `discord-bot/src/lib/embeds.js` | Discord embed builders |
| `discord-bot/src/lib/reactions.js` | Reaction vote sync |
| `discord-bot/package.json` | Node.js project manifest |
| `discord-bot/Dockerfile` | Container image for VPS deployment |
| `discord-bot/.env.example` | Required env var documentation |
| `/docker/coherence-network/docker-compose.yml` | Add `discord-bot` service |

---

## Requirements

### R1 — Channels per Active Idea

- On startup and every 5 minutes, the bot queries `GET /api/ideas?stage=specced,implementing,testing&limit=100`.
- For each idea not yet having a channel, it creates `#idea-<slug>` under the `Active Ideas` category.
- On creation, the channel description is set to the idea's first 200 chars.
- A pinned embed is posted immediately (see Embed Format below).
- When an idea's stage leaves the active set (enters `validated` or `archived`), the channel is moved to an `Archived Ideas` category and set read-only.
- **Idempotent**: running sync twice does not create duplicate channels. The bot stores `discord_channel_id` in a local SQLite file (`data/channels.db`); on each sync it checks this map before calling Discord.

### R2 — Idea Card Embed Format

Each idea card is a Discord embed with:

| Field | Value |
|-------|-------|
| Title | Idea name (linked to `https://coherencycoin.com/ideas/<id>`) |
| Description | First 300 chars of `description` |
| Color | Green (`#00C851`) if `manifestation_status=validated`; Yellow (`#ffbb33`) if `specced`; Blue (`#33b5e5`) if `implementing`; Orange (`#FF8800`) if `testing` |
| Fields | Stage · Coherence Score · Free Energy Score · Potential Value (CC) · Actual Value (CC) |
| Footer | `idea-id: <id> · Last updated: <ISO timestamp>` |
| Thumbnail | Coherence Network logo |

Reactions added automatically to the pinned card: 👍 (agree), 👎 (disagree), 🔥 (excited).

### R3 — `/cc-idea` Slash Command

```
/cc-idea name:<string> description:<string> [potential_value:<number>]
```

- Calls `POST /api/ideas` with the provided fields.
- On success: posts the idea card embed to `#idea-submissions`.
- On failure (validation error): ephemeral error message to the invoking user.
- The `contributor_id` is derived from a Discord-user-to-contributor mapping stored in `data/contributors.db`. If the Discord user has no mapping, they are prompted to link with `/cc-link <contributor_id>`.
- Rate limit: 1 submission per user per 10 minutes (enforced in bot memory, not API).

**Interaction flow:**
```
User: /cc-idea name:"GraphQL cache" description:"LRU cache for graph queries" potential_value:120
Bot: [posts idea card to #idea-submissions]
Bot: [creates #idea-graphql-cache in Active Ideas category]
Bot: [DMs user] "Idea submitted! id: graphql-cache · +5 CC for submission"
```

### R4 — `/cc-status` Slash Command

```
/cc-status [verbose:<true|false>]
```

Calls `GET /api/health` and renders a status embed:

| Field | Value |
|-------|-------|
| Title | Pipeline Health |
| Color | Green if `status=ok`, Red if not |
| Fields | Version · Uptime · Schema OK · Integrity |
| Footer | `Checked at <timestamp>` |

With `verbose:true`, also queries `GET /api/tasks?limit=10&sort=updated_desc` and appends a field with the 10 most recent task completions.

### R5 — `/cc-stake` Slash Command

```
/cc-stake idea_id:<string> amount:<number> [rationale:<string>]
```

- Calls `POST /api/investments` with `{idea_id, amount_cc, rationale, contributor_id}`.
- On success: posts a confirmation embed to `#bot-commands` with projected ROI pulled from the idea's `value_vector` and `cost_vector`.
- On failure (idea not found, insufficient CC): ephemeral error to invoking user.
- Confirmation screen before executing: bot replies with an ephemeral "Confirm: stake 50 CC in graphql-cache?" with Yes/No buttons. Timeout 30 s.

### R6 — Live Pipeline Feed

- Background loop polls `GET /api/tasks?status=completed,failed&updated_after=<last_seen_ts>&limit=20` every 60 s.
- For each new task event: posts a compact embed to `#pipeline-feed`.

| Event type | Embed color | Icon |
|-----------|-------------|------|
| `completed` | Green | ✅ |
| `failed` | Red | ❌ |
| `in_progress` (new task started) | Blue | 🔄 |

Pipeline embed fields: task ID, type, idea name, node, duration, CC earned.

### R7 — Reaction-Based Voting

- When a user reacts to a pinned idea card embed with 👍/👎/🔥:
  - Bot calls `POST /api/ideas/<id>/questions/<qid>/vote` (see API Changes below) with `{polarity: "positive"|"negative"|"excited", discord_user_id}`.
  - Duplicate votes from the same user are rejected by the API (idempotent, 409 ignored silently).
- Every 15 minutes, the bot syncs reaction counts back to the embed (edit the pinned message) to keep counts accurate after bot restarts.

### R8 — Threads per Open Question

- When an idea channel is created (or updated), for each entry in `idea.open_questions`:
  - If no thread titled `❓ <question[:80]>` already exists in the channel, create one.
  - The thread starter message includes the question text and `estimated_cost` and `value_to_whole` from the API.
- When an `open_questions` entry gains an `answer` (polled every 5 min), the thread is archived with a final message: "✅ Answered: <answer>".

---

## API Changes

### New endpoint: `POST /api/ideas/{idea_id}/questions/{question_index}/vote`

Required to support reaction voting.

**Request body**:
```json
{
  "polarity": "positive" | "negative" | "excited",
  "discord_user_id": "string"
}
```

**Response 200**:
```json
{
  "question_index": 0,
  "votes": { "positive": 14, "negative": 2, "excited": 7 },
  "your_vote": "positive"
}
```

**Response 409**: User already voted this polarity (idempotent — bot ignores this).

**Response 404**: Idea or question index not found.

This endpoint stores votes in a new `question_votes` table in Postgres:

```sql
CREATE TABLE question_votes (
  id          SERIAL PRIMARY KEY,
  idea_id     VARCHAR NOT NULL,
  question_idx INT NOT NULL,
  discord_user_id VARCHAR NOT NULL,
  polarity    VARCHAR(10) NOT NULL CHECK (polarity IN ('positive','negative','excited')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (idea_id, question_idx, discord_user_id)
);
```

### Modified endpoint: `GET /api/ideas/{idea_id}` — add `question_votes` field

Each element in `open_questions` gains a `votes` sub-object:
```json
"votes": { "positive": 14, "negative": 2, "excited": 7 }
```

---

## Environment Variables

```env
# discord-bot/.env.example
DISCORD_TOKEN=          # Discord bot token (bot permissions: channels, messages, reactions, threads)
DISCORD_GUILD_ID=       # Target server ID
DISCORD_ACTIVE_CATEGORY=Active Ideas      # Category name for active idea channels
DISCORD_ARCHIVE_CATEGORY=Archived Ideas   # Category for archived channels
DISCORD_SUBMISSIONS_CHANNEL=idea-submissions
DISCORD_PIPELINE_CHANNEL=pipeline-feed
DISCORD_COMMANDS_CHANNEL=bot-commands
COHERENCE_API_BASE=https://api.coherencycoin.com
POLL_INTERVAL_SEC=60    # Pipeline feed poll interval
SYNC_INTERVAL_MIN=5     # Idea channel sync interval
LOG_LEVEL=info
```

---

## Docker Compose Addition

```yaml
# Add to /docker/coherence-network/docker-compose.yml
discord-bot:
  build:
    context: ./repo/discord-bot
    dockerfile: Dockerfile
  restart: unless-stopped
  env_file: .env.discord
  volumes:
    - discord-bot-data:/app/data
  depends_on:
    - api
  networks:
    - coherence-net

volumes:
  discord-bot-data:
```

---

## Working Proof / Evidence Checklist

The following are observable, independent proofs that the feature is working:

| Proof point | How to verify |
|-------------|---------------|
| Bot is online | `/cc-status` in `#bot-commands` returns green embed |
| Idea channels exist | Discord server has `#idea-<slug>` channels for all specced/implementing/testing ideas |
| Pipeline feed is live | `#pipeline-feed` has a message within the last 70 s of any task completion |
| Vote count visible | Pinned idea card shows reaction counts matching `GET /api/ideas/<id>` |
| Thread per question | Each `#idea-<slug>` channel has one thread per `open_questions` entry |
| `/cc-idea` submits | After command, `GET /api/ideas/<new-id>` returns the created idea |
| `/cc-stake` invests | After command, `GET /api/investments?contributor_id=X` shows new investment |

---

## Verification Scenarios

### Scenario 1 — Pipeline Feed Live

**Setup**: At least one pipeline task has completed within the last 5 minutes. Check `GET /api/tasks?status=completed&limit=1`.

**Action**: Open `#pipeline-feed` in the Discord server.

**Expected result**: The most recent message was posted within 70 seconds of the task's `completed_at` timestamp. Message contains the task ID, type, and a green ✅ embed. Duration field shows seconds elapsed.

**Edge case**: If the API returns `status=failed` for a task, the message uses red ❌ and includes the error field. If `GET /api/tasks` returns an empty list, no message is posted and the feed channel shows "No recent tasks."

---

### Scenario 2 — `/cc-idea` Creates Idea and Channel

**Setup**: No idea with id `discord-test-idea-001` exists (`GET /api/ideas/discord-test-idea-001` → 404).

**Action**: In `#bot-commands`, type:
```
/cc-idea name:"Discord test idea 001" description:"Spec verification test idea" potential_value:10
```

**Expected result**:
1. Bot replies with a public embed in `#idea-submissions` showing the idea card with title "Discord test idea 001".
2. Within 5 minutes, a new channel `#idea-discord-test-idea-001` appears in the `Active Ideas` category.
3. `GET /api/ideas/discord-test-idea-001` → HTTP 200 with `name: "Discord test idea 001"`.

**Edge case**: Running the same command again within 10 minutes → ephemeral "Rate limit: wait N minutes." No duplicate API call made.

---

### Scenario 3 — `/cc-status` Shows Live Health

**Setup**: API is running (`GET https://api.coherencycoin.com/api/health` returns `status: ok`).

**Action**: In `#bot-commands`, type `/cc-status`.

**Expected result**: Bot replies with a green embed containing:
- Title: "Pipeline Health"
- Field `Status`: ok
- Field `Uptime`: matches `uptime_human` from the API within 5 seconds
- Footer timestamp within 5 seconds of the current time

**Edge case**: API is unreachable → bot replies with red embed: "API unreachable. Last known status: ok (2 min ago)." Does not crash or timeout Discord interaction.

---

### Scenario 4 — Reaction Vote Syncs to API

**Setup**: Idea `stale-task-reaper` exists with `open_questions[0]`. The `#idea-stale-task-reaper` channel has its pinned idea card.

**Action**: Add 👍 reaction to the pinned idea card.

**Expected result**:
1. Within 2 seconds, bot calls `POST /api/ideas/stale-task-reaper/questions/0/vote` with `polarity: "positive"`.
2. Within 15 minutes (next sync), the pinned embed updates to show 👍 count incremented by 1.
3. `GET /api/ideas/stale-task-reaper` response includes `open_questions[0].votes.positive` incremented by 1.

**Edge case**: Same user adds 👍 again → API returns 409 → bot silently ignores → count unchanged.

---

### Scenario 5 — Open Question Thread Auto-Created

**Setup**: Idea `runner-auto-contribution` has `open_questions[0].question = "How can we improve this idea..."`.

**Action**: Bot performs its 5-minute sync cycle (or restart the bot).

**Expected result**: Channel `#idea-runner-auto-contribution` contains a thread titled `❓ How can we improve this idea, show whether it is working yet, and ma…` (truncated at 80 chars). Thread starter message shows `value_to_whole: 20.0` and `estimated_cost: 3.0`.

**Edge case**: If `open_questions[0].answer` is set on the next sync, the thread is archived and its last message is "✅ Answered: <answer text>". The thread is not re-created on the next sync.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| Discord rate limits (channel creation, message posting) | Use `discord.js` built-in rate limit queuing; spread sync over 5-min window using 1s delays between channel creates |
| API downtime breaks bot | All API calls wrapped in try/catch; bot posts "API unreachable" message rather than crashing |
| Many active ideas → many channels | Cap active channels at 50; oldest-updated ideas are archived when limit is exceeded |
| Discord token rotation | Token stored in `.env.discord` on VPS (mode 600); not in git |
| Duplicate channel creation | `data/channels.db` SQLite map is the source of truth; checked before any `guild.channels.create` call |
| Vote manipulation | API enforces unique constraint on `(idea_id, question_idx, discord_user_id)`; bot does not enforce independently |
| Thread spam for ideas with many open questions | Hard cap of 20 threads per channel; excess questions logged but not threaded |

---

## Known Gaps and Follow-up Tasks

- **`/cc-link` command** (Discord user → contributor ID mapping) is referenced but not fully spec'd here; Phase 2.
- **WebSocket events from API** instead of polling would reduce latency; deferred pending API streaming spec.
- **`/cc-contribute`** — record a contribution from Discord — deferred to Phase 2.
- **Per-channel notification roles** (ping `@idea-<slug>` when status changes) — deferred.
- **Investment display in idea card** (how much CC is staked) — deferred pending Spec 157 implementation.
- **`question_votes` migration** must be run before deploying the bot; add to `alembic` migration chain.
- **DIF verification** of bot source files should be performed before merging any implementation PR.

---

## Implementation Order

1. `discord-bot/` scaffold: `package.json`, `Dockerfile`, `.env.example`
2. `discord-bot/src/lib/api.js` — REST client wrapping all required endpoints
3. `discord-bot/src/lib/embeds.js` — all embed builders
4. `discord-bot/src/sync/idea-channel-sync.js` — channel sync loop
5. `discord-bot/src/sync/pipeline-feed.js` — pipeline event loop
6. `discord-bot/src/commands/cc-idea.js` — `/cc-idea`
7. `discord-bot/src/commands/cc-status.js` — `/cc-status`
8. `discord-bot/src/commands/cc-stake.js` — `/cc-stake`
9. `discord-bot/src/lib/reactions.js` — reaction vote handler
10. `discord-bot/src/index.js` — wire everything together
11. API: `question_votes` table migration + vote endpoint
12. Docker Compose update + VPS deploy
13. Integration test against staging server

---

## Acceptance Criteria

- [ ] `/cc-status` returns a correct health embed within 3 s of invocation.
- [ ] `/cc-idea` creates an idea via the API and posts the card to `#idea-submissions`.
- [ ] `/cc-stake` posts a confirmation prompt and calls `POST /api/investments` on confirm.
- [ ] `#pipeline-feed` receives a message within 70 s of any task completion visible in the API.
- [ ] Active idea channels exist for all ideas in `specced`/`implementing`/`testing` stage.
- [ ] Archived ideas have their channels moved to `Archived Ideas` and set read-only.
- [ ] Each `open_questions` entry has a corresponding Discord thread.
- [ ] Reaction votes sync to `POST /api/ideas/{id}/questions/{idx}/vote`.
- [ ] Bot stays online under continuous operation; crashes trigger Docker restart.
- [ ] All 5 Verification Scenarios pass against production.
