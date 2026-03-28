# Spec 168: Identity-Driven Onboarding — Trust-on-First-Use (TOFU) MVP

## Goal

Enable zero-friction contributor onboarding for the MVP using trust-on-first-use (TOFU), with a
clear upgrade path to OAuth verification.

## Problem

- Requiring OAuth before first contribution blocks low-friction onboarding.
- Many contributors just want to claim a handle and start contributing.
- OAuth adds infrastructure complexity not warranted for the MVP stage.
- A verified identity is a good-to-have; a claimed identity that can be verified later is enough.

## Solution

**Phase 1 — TOFU (MVP, this spec):** A new visitor claims a handle and optionally supplies a
GitHub username or wallet hint. The system immediately issues a personal session token.
No password, no OAuth redirect, no email confirmation. Identity recorded with `trust_level: "tofu"`.

**Phase 2 — OAuth (post-MVP, Spec 169):** The contributor can later verify via GitHub or
Ethereum signature, upgrading to `"verified"`. TOFU sessions remain valid and are upgraded in-place.

## Acceptance Criteria

1. `POST /api/onboarding/register` accepts `{handle, email?, hint_github?, hint_wallet?}` and
   returns `{contributor_id, session_token, trust_level: "tofu", roi_signals}`.
2. If `handle` is already taken, returns 409 with `detail: "handle_taken"`.
3. `GET /api/onboarding/session` with `Authorization: Bearer <token>` returns the contributor
   profile or 401.
4. `POST /api/onboarding/upgrade` accepts `{contributor_id, provider, provider_id}` and returns
   501 stub (OAuth planned for Spec 169).
5. `GET /api/onboarding/roi` returns `{handle_registrations, verified_count, verified_ratio,
   avg_time_to_verify_days, spec_ref}`.
6. Handle validation: 3-40 chars, `[a-z0-9_-]` only.
7. Session tokens are 64-char random hex strings stored in SQLite.

## Verification

```bash
cd api && python -m pytest tests/test_onboarding.py -v
```

## Risks and Assumptions

- TOFU handles are self-claimed — no uniqueness enforced by any external authority.
- Session tokens have no TTL in MVP (add expiry in follow-up).
- OAuth upgrade is a 501 stub until Spec 169.

## Known Gaps and Follow-up Tasks

- Spec 169: Full OAuth upgrade path (GitHub, Ethereum).
- Session token expiry / rotation.
- Rate-limiting on `/register` to prevent name squatting.
- Key revocation endpoint.
