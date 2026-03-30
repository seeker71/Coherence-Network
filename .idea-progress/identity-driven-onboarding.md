# Idea progress — identity-driven-onboarding

## Current task

- **task_4040db58596a0978**: Complete. Implemented TOFU→verified upgrade path (Spec 184).

## Completed phases

- Spec 168 documents **trust-on-first-use for MVP**, OAuth deferred.
- `GET /api/onboarding/roi` and `register.roi_signals` expose funnel metrics.
- Tests: `api/tests/test_onboarding.py`, `api/tests/test_onboarding_identity_extended.py`.
- Web `/onboarding` shows MVP trust line from live ROI JSON.
- **Spec 184**: OAuth upgrade path replaces 501 stub. `POST /api/onboarding/upgrade` now accepts `Bearer session_token` + provider credentials, links identity, and upgrades `trust_level` to `verified`.
- Enhanced ROI: `tofu_to_verified_conversions`, `conversion_rate`, `funnel` (registered/linked/verified step counts).
- Tests: `api/tests/test_onboarding_upgrade.py` (7 tests). All 17 onboarding tests pass.

## Key decisions

- **MVP**: No verification at first registration; `trust_level: tofu` until upgrade.
- **Upgrade**: Self-asserted identity link upgrades to `verified`. Cryptographic proof (gist/wallet signature) uses existing `/api/auth/verify/*` endpoints separately.
- **Idempotent**: Re-upgrading already-verified session returns current state.
- **No token rotation** on upgrade — same session token, upgraded trust level.
- **Bearer auth on upgrade** — session token passed via Authorization header, not request body.
- **Provider validation** — upgrade rejects unsupported providers with 422.
- **Evidence**: `specs/168-identity-driven-onboarding-tofu.md`, `specs/184-onboarding-oauth-upgrade.md`.

## Blockers

- None.
