# Spec 168 — Identity-Driven Onboarding: Trust-on-First-Use (TOFU) MVP

## Goal

Enable zero-friction contributor onboarding for the MVP using trust-on-first-use (TOFU), with a
clear upgrade path to OAuth verification.

## Problem

- Requiring OAuth before first contribution blocks low-friction onboarding.
- Many contributors just want to claim a handle and start contributing — no email/password flow.
- OAuth adds infrastructure complexity that is not warranted for the MVP stage.
- A verified identity is a good-to-have; a claimed identity that can be verified later is enough
  to associate attribution, track contributions, and earn coherence credits.

## Solution

**Phase 1 — TOFU (MVP):** A new visitor claims a handle and optionally supplies an email or
social hint (GitHub username, wallet address). The system immediately issues a personal
session token. No password, no OAuth redirect, no email confirmation. The identity is recorded
with `trust_level: "tofu"`.

**Phase 2 — OAuth (post-MVP):** The contributor can later verify their identity via GitHub or
Ethereum signature, upgrading the trust level to `"verified"`. This is additive; TOFU sessions
remain valid and are upgraded in-place.

## Acceptance Criteria

1. `POST /api/onboarding/register` accepts `{ handle, email?, hint_github?, hint_wallet? }` and
   returns `{ contributor_id, session_token, trust_level: "tofu" }`.
2. If `handle` is already taken, returns a 409 with `{ detail: "handle_taken" }`.
3. `GET /api/onboarding/session` with `Authorization: Bearer <token>` returns the contributor
   profile or 401.
4. `POST /api/onboarding/upgrade` accepts `{ contributor_id, provider, provider_id, verified_by
   }` and upgrades `trust_level` to `"verified"` (delegates to identity_service).
5. Session tokens are opaque random strings (32 bytes hex) stored in the contributor identity
   table alongside trust metadata.
6. All responses include `roi_signals` with fields `handle_registrations`, `verified_ratio`,
   `avg_time_to_verify_days` computed from the current store snapshot.
7. API integration tests cover: register → session → upgrade happy path, duplicate handle 409,
   invalid token 401.

## Verification

- `pytest api/tests/test_onboarding.py -v` passes all 7 test cases.
- `GET /api/onboarding/session` with fresh token returns `trust_level: "tofu"`.
- `POST /api/onboarding/upgrade` followed by `GET /api/onboarding/session` returns
  `trust_level: "verified"`.

## Risks and Assumptions

- TOFU handles are self-claimed — no uniqueness enforced by any external authority. This is
  intentional for MVP; uniqueness is enforced only within this system.
- Session tokens are not JWTs — they're random blobs. No expiry in MVP (add TTL in a follow-up).
- OAuth upgrade is a stub that delegates to `contributor_identity_service` — full OAuth flow
  already exists in `contributor_identity.py`.

## Known Gaps and Follow-up Tasks

- Session token expiry / rotation not implemented (follow-up: add TTL field).
- No rate-limiting on registration endpoint (follow-up: add IP-based throttling).
- OAuth state parameter does not include `session_token` yet — linking the OAuth flow back to a
  TOFU session requires a follow-up spec.
- Email verification (magic link) not implemented.
