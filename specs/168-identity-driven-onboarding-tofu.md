# Spec 168 -- Identity-Driven Onboarding: Trust-on-First-Use (TOFU) MVP

## Goal

Enable zero-friction contributor onboarding for the MVP using trust-on-first-use (TOFU),
with a clear upgrade path to OAuth verification (Spec 169).

## Problem

- Requiring OAuth before first contribution blocks low-friction onboarding.
- Many contributors want to claim a handle and start contributing -- no email/password needed.
- OAuth adds infrastructure complexity not warranted for MVP stage.
- A claimed identity that can be verified later is sufficient for attribution and CC earning.

## Solution

**Phase 1 -- TOFU (this spec):** A visitor claims a handle. The system issues a personal
session token immediately. No password, OAuth, or email confirmation needed. Identity is
recorded with trust_level: tofu.

**Phase 2 -- OAuth (Spec 169):** The contributor can later verify via GitHub or Ethereum
signature, upgrading trust level to verified. Additive -- TOFU sessions remain valid.

## Acceptance Criteria

1. POST /api/onboarding/register accepts { handle, email?, hint_github?, hint_wallet? } and
   returns { contributor_id, session_token, trust_level: tofu, handle, created, roi_signals }.
2. Handle must match [a-z0-9_-]{3,40} -- invalid handles 422.
3. Duplicate handle -- 409 { detail: handle_taken }.
4. GET /api/onboarding/session with Authorization: Bearer <token> returns contributor profile
   or 401.
5. POST /api/onboarding/upgrade returns 501 stub until Spec 169 is implemented.
6. GET /api/onboarding/roi returns { handle_registrations, verified_count, verified_ratio,
   avg_time_to_verify_days, spec_ref: spec-168 }.
7. All 9 integration tests in api/tests/test_onboarding.py pass.

## Verification

- pytest api/tests/test_onboarding.py -v -- 9/9 pass.
- GET /api/onboarding/session with fresh token returns trust_level: tofu.
- GET /api/onboarding/roi returns valid ROI shape with spec_ref: spec-168.

## Risks and Assumptions

- TOFU handles are self-claimed -- uniqueness enforced only within this system.
- Session tokens are opaque 64-char hex strings. No expiry in MVP.
- OAuth upgrade is a 501 stub -- full flow in Spec 169.

## Known Gaps and Follow-up Tasks

- Session token TTL / rotation (follow-up).
- Rate-limiting on registration endpoint (follow-up).
- Full OAuth redirect flow: Spec 169.
- Email magic-link verification: future spec.
