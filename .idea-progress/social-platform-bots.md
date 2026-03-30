# Progress — social-platform-bots

## Completed phases
- **task_e1a042e07be337c5**: Added `api/tests/test_social_platform_bots_idea_acceptance.py` covering spec-167 acceptance (Discord R1-style list filtering, vote edge cases, spec text + discord-bot deliverables).
- **task_71470c3ebd867504**: Discord bot ROI signals API + finalization. Added `GET /api/discord/roi-signals` endpoint (model, service, router, 5 tests). Fixed `.env.example` (added DISCORD_CLIENT_ID). All 24 Discord tests passing.

## Current task
- task_71470c3ebd867504: COMPLETE

## Key decisions
- Discord selected over X/Twitter (spec-167): free tier, OSS-friendly, slash commands, gateway intents, webhooks, embeds, reaction events.
- Bot architecture: Node.js + discord.js v14, all reads/writes through REST API.
- ROI signals computed from question_votes table + idea portfolio interface tags.

## Blockers
- None
