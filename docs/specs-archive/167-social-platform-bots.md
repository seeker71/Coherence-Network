# Spec 167: Social Platform Bots — Platform Selection and ROI Framework

**Spec ID**: 167-social-platform-bots
**Task ID**: task_eccad35e9bee91d1
**Status**: approved
**Priority**: high
**Author**: dev-engineer agent
**Date**: 2026-03-28
**Depends on**: Spec 164 (Discord Bot — Channels Per Idea)
**Depended on by**: Future X/Twitter bot (Phase 2)

---

## Decision: Discord First, X Second

**Winner: Discord**

Both X (formerly Twitter) and Discord have strong bot APIs, but Discord is the right first
platform for Coherence Network based on the following evidence:

| Criterion | Discord | X (Twitter) |
|-----------|---------|-------------|
| Bot API quality | ✅ Discord.js v14, gateway, slash commands, threads | ⚠️ v2 API, complex OAuth, tweet-only |
| Free tier | ✅ Unlimited for self-hosted bots | ❌ Basic tier is $100/month for write access |
| Community fit | ✅ OSS communities live in Discord | ⚠️ Public-facing only; no private channels |
| Interactive UX | ✅ Slash commands, buttons, threads, reactions | ❌ Replies only; no interactive components |
| Persistent state | ✅ Channels, threads, pinned messages | ❌ Ephemeral feed; no persistence |
| Real-time | ✅ WebSocket gateway | ⚠️ Polling only (paid streaming) |
| Rate limits | ✅ Per-route, recoverable | ❌ Strict tweet caps even on paid tiers |

**Conclusion**: Discord's architecture maps 1:1 to Coherence Network's pipeline model
(channels per idea, threads per question, reaction voting). X/Twitter is a broadcast
medium, not a collaboration medium — better suited for announcements in Phase 2.

---

## Summary

This spec records the platform selection decision and defines the ROI measurement
framework for Coherence Network's bot presence. Spec 164 covers the Discord bot
implementation. This spec covers:

1. Platform selection rationale (recorded above).
2. ROI signals and success metrics for the Discord bot.
3. Phase 2 X/Twitter announcement bot spec stub.
4. `/cc-link` slash command (Discord user → contributor ID mapping), required for
   attribution on `/cc-idea` and `/cc-stake`.

---

## Goals

1. Record the platform decision with evidence (above).
2. Define measurable ROI signals for the Discord bot (R1–R5 below).
3. Implement `/cc-link` (the missing command from spec-164 Phase 1 scope).
4. Stub the X bot spec for Phase 2.

---

## ROI Signals

### R1 — Idea Submission Rate via Discord

**Signal**: `POST /api/ideas` calls with `source=discord` / total submissions.

**Target**: ≥ 10% of new ideas submitted via Discord within 30 days of bot launch.

**How to measure**: Ideas created by `/cc-idea` carry `interfaces: ["discord"]`.
Query: `GET /api/ideas?interface=discord&created_after=<launch_date>`.

**Evidence link**: `GET https://api.coherencycoin.com/api/ideas?interface=discord`

---

### R2 — Reaction Vote Volume

**Signal**: `question_votes` table row count per day.

**Target**: ≥ 50 votes/day within 14 days of bot launch.

**How to measure**: `SELECT DATE(created_at), COUNT(*) FROM question_votes GROUP BY 1 ORDER BY 1 DESC LIMIT 14`.

**Evidence link**: Vote endpoint: `POST /api/ideas/{id}/questions/{idx}/vote`

---

### R3 — Pipeline Feed Engagement

**Signal**: Users who react to pipeline feed messages / total pipeline messages posted.

**Target**: ≥ 15% reaction rate on pipeline feed messages.

**How to measure**: Discord API `GET /channels/{id}/messages` — count messages with ≥ 1 reaction.

---

### R4 — `/cc-stake` Investment Volume

**Signal**: CC invested via Discord `/cc-stake` / total CC invested.

**Target**: ≥ 20% of investment volume via Discord within 60 days.

**How to measure**: `GET /api/investments?source=discord` when `source` field is added.

---

### R5 — Bot Uptime

**Signal**: Docker container restarts per week.

**Target**: < 1 unplanned restart per week.

**How to measure**: `docker inspect coherence-network-discord-bot-1 --format '{{.RestartCount}}'`

---

## `/cc-link` Slash Command (Phase 1 Completion)

This command was referenced in spec-164 as needed for contributor attribution but
deferred. It is implemented in this spec.

```
/cc-link contributor_id:<string>
```

**Flow**:
1. User calls `/cc-link contributor_id:alice`.
2. Bot stores `{discord_user_id: interaction.user.id, contributor_id: "alice"}` in `data/contributors.db`.
3. Bot replies (ephemeral): "✅ Linked! Your Discord account is now mapped to contributor `alice`."
4. Subsequent `/cc-idea` and `/cc-stake` calls resolve `contributor_id` from this mapping.

**File**: `discord-bot/src/commands/cc-link.js`

---

## Phase 2 — X/Twitter Announcement Bot (Stub)

When to build: after Discord bot has been live for 30 days and ROI signals R1–R3 are green.

**Scope**: Read-only announcements only (no interactive commands).

**Trigger events**:
- New idea reaches `specced` stage → tweet with idea name + URL.
- Task completes with `cc_earned > 50` → tweet celebrating contributor.
- Weekly pipeline summary (top 3 ideas by coherence score).

**API needed**: X v2 OAuth2 app-only token (free tier: 1500 tweets/month write limit).
At 3 tweets/day this fits the free tier.

**Implementation**: Separate `x-bot/` directory, Python, `tweepy` library.
Triggered by the existing pipeline event system — not a separate polling loop.

---

## File Paths

| Path | Purpose |
|------|---------|
| `discord-bot/src/commands/cc-link.js` | `/cc-link` command — links Discord user to contributor ID |
| `discord-bot/src/register-commands.js` | Must add cc-link to registration list |
| `specs/167-social-platform-bots.md` | This spec |

---

## Verification

| Proof | How to check |
|-------|-------------|
| `/cc-link` works | Run `/cc-link contributor_id:test-user` → ephemeral "Linked!" reply |
| Attribution works | Run `/cc-idea` after linking → idea has correct `contributor_id` |
| ROI R2 is tracked | `GET /api/ideas/{id}` shows `open_questions[0].votes` populated after reaction |
| Discord bot is live | `/cc-status` shows green embed with uptime |

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| X API pricing changes | X bot is Phase 2 and budget-gated; platform costs reviewed before starting |
| Contributors don't link accounts | `/cc-idea` prompts to `/cc-link` if no mapping found |
| Discord bot policy changes | Standard Discord bot ToS compliance; no DM spam, rate limits respected |

---

## Known Gaps and Follow-up Tasks

- X bot Phase 2 spec needs full implementation detail when budget is confirmed.
- `/cc-link` should validate that `contributor_id` exists in `GET /api/contributors` before linking.
- ROI dashboard in the web UI (spec-165 follow-up) to visualize R1–R5 signals.
- `source` field on investment and idea models to track Discord-originated activity.
