# Spec 200 — Identity-Driven Onboarding: Trust-on-First-Use (TOFU) MVP

**Status**: approved
**Idea**: identity-driven-onboarding
**Owner**: dev-engineer
**Created**: 2026-03-28

---

## Summary

Enable contributors to self-onboard instantly with zero friction for the MVP. A
contributor registers with a handle (or email) and receives a personal API key
immediately — no email verification, no OAuth dance. OAuth identity linking is
supported *optionally* after the fact, upgrading the account to **verified**
status without changing the key.

This is the classic **Trust-on-First-Use** model: we issue a key on first contact
and rely on the contributor to keep it secret. Verification is a later enrichment,
not a gate.

---

## Goals

| Goal | Metric |
|------|--------|
| Zero-friction onboarding | ≤ 1 API call to get a working key |
| No external deps at sign-up | Works offline / no OAuth service required |
| Upgradeable to verified | OAuth link available at any time post-signup |
| Auditable | Every key issuance recorded with source IP + timestamp |
| Reversible | Keys can be rotated or revoked by the holder |

---

## Acceptance Criteria

### AC-1 — Self-registration via handle

`POST /api/onboard` with `{ "handle": "<username>" }` returns:
- HTTP 201
- `{ "contributor_id": "...", "api_key": "ccn_...", "verified": false, "onboarding_source": "tofu" }`
- The API key is valid immediately for authenticated endpoints
- Calling again with the same handle rotates and returns a new key

### AC-2 — Optional email onboarding

`POST /api/onboard` with `{ "handle": "...", "email": "user@example.com" }`:
- Email stored but **not verified** at this stage
- `verified: false` in response
- Duplicate email detection returns HTTP 409 with `detail: "email already registered"`

### AC-3 — Upgrade to verified (OAuth)

`POST /api/onboard/verify` with `{ "contributor_id": "...", "provider": "github", "provider_id": "..." }`:
- Links an OAuth identity to the existing contributor
- Sets `verified: true` on the contributor identity record
- Returns `{ "contributor_id": "...", "verified": true, "provider": "github" }`

### AC-4 — Key rotation

`POST /api/onboard/rotate` with `X-API-Key: <existing key>` header:
- Invalidates the old key
- Issues a new `ccn_...` key
- Returns `{ "api_key": "<new>", "rotated_at": "<iso>" }`
- Old key returns HTTP 401 after rotation

### AC-5 — TOFU source tracking

All keys issued through `/api/onboard` carry `onboarding_source: "tofu"` in
the key store, distinguishing them from future OAuth-issued or admin-issued keys.

---

## Implementation Plan

### Phase 1 — MVP (this spec)

- `POST /api/onboard` — TOFU registration, returns API key
- `POST /api/onboard/rotate` — rotate existing key
- `POST /api/onboard/verify` — link OAuth identity to upgrade

### Phase 2 — OAuth (future spec)

- OAuth redirect flow (GitHub / Google / Discord)
- Automatic `verified: true` on OAuth callback
- Scoped tokens with expiry

---

## Verification

- `pytest api/tests/test_onboarding.py -v` passes all AC tests
- `GET /api/contributors/{handle}` returns the contributor created via `/api/onboard`
- `GET /api/identity/me` with the issued key returns `{ "contributor_id": "..." }`
- Key rotation: old key → 401, new key → 200

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| Handle squatting | Rate-limit `/api/onboard` to 5 req/min per IP |
| Key leakage | TOFU keys are single-use display — store securely |
| No email = uncontactable | Email optional but encouraged; show UI nudge |
| DB in-memory for MVP | `_KEY_STORE` in `auth_keys.py` is in-memory; Phase 2 migrates to PostgreSQL |

---

## Known Gaps and Follow-up Tasks

- [ ] Persist keys to PostgreSQL (currently in-memory dict)
- [ ] Email verification flow (send token, confirm endpoint)
- [ ] OAuth callback handler for GitHub/Google/Discord (Phase 2)
- [ ] Rate limiting per IP on `/api/onboard`
- [ ] Admin key revocation endpoint
- [ ] `/api/onboard/me` — describe own registration status
