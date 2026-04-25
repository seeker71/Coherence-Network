---
idea_id: self-custody-wallet-integration
status: active
source:
  - file: api/app/services/wallet_service.py
    symbols: [generate_siwe_challenge(), verify_siwe_signature(), link_wallet(), get_wallet_status(), generate_ed25519_keypair(), verify_ed25519_signature()]
  - file: api/app/models/wallet.py
    symbols: [WalletChallengeRequest, WalletChallengeResponse, WalletVerifyRequest, WalletLinkResult, WalletStatusResponse, Ed25519KeypairResponse]
  - file: api/app/routers/wallet.py
    symbols: [challenge, verify, link_manual, get_status, get_keypair]
  - file: api/app/services/onboarding_service.py
    symbols: [OnboardingSession.wallet_address, OnboardingSession.wallet_chain_id, OnboardingSession.wallet_trust_level, OnboardingSession.ed25519_public_key]
  - file: api/alembic/versions/add_wallet_fields.py
    symbols: [upgrade(), downgrade()]
  - file: web/components/WalletConnect.tsx
    symbols: [WalletConnect, useWalletProviders, WalletManualEntry]
  - file: web/hooks/useWallet.ts
    symbols: [useWallet, useWalletConnect, useInjectedProvider]
  - file: web/app/settings/wallet/page.tsx
    symbols: [WalletSettingsPage]
requirements:
  - "GET /api/wallet/challenge returns SIWE challenge nonce for EVM wallet signing"
  - "POST /api/wallet/verify accepts SIWE-signed message, verifies signature, links wallet to contributor"
  - "POST /api/wallet/manual accepts raw EVM address (0x…), links with trust_level wallet_unverified"
  - "GET /api/wallet/{contributor_id}/status returns wallet_address, chain_id, trust_level, linked_at, ed25519_public_key"
  - "GET /api/wallet/{contributor_id}/keypair returns Ed25519 public key; private key never leaves client"
  - "POST /api/wallet/keypair/verify accepts Ed25519 signature + public key, returns ok/fail"
  - "All wallet addresses stored checksummed EIP-55; manual entries normalized before storage"
  - "Wallet link elevates trust_level from tofu → wallet_unverified (manual) or wallet_verified (SIWE)"
  - "WalletConnect.tsx supports injected providers (MetaMask, Rabby), WalletConnect QR, and manual address"
  - "WalletSettingsPage displays current wallet status with connect/disconnect actions"
done_when:
  - "GET /api/wallet/challenge returns {nonce, domain, issued_at, expiry} within 60s TTL"
  - "POST /api/wallet/verify with valid SIWE sig returns {contributor_id, wallet_address, trust_level: wallet_verified}"
  - "POST /api/wallet/manual with '0xabc…' returns {wallet_address, trust_level: wallet_unverified}"
  - "GET /api/wallet/{id}/status returns all fields; wallet_address matches what was linked"
  - "Signature mismatch on /verify returns 401 with code sig_invalid"
  - "All tests in api/tests/test_wallet.py pass"
test: "cd api && python -m pytest api/tests/test_wallet.py -v"
constraints:
  - "Platform NEVER stores private keys; only public keys and wallet addresses"
  - "SIWE challenge nonces are single-use and expire after 5 minutes"
  - "EIP-55 checksum validation enforced on all wallet address inputs"
  - "Ed25519 key generation happens client-side; API only stores the public key"
  - "No dependency on Story Protocol or x402 in this spec — wallet address is the foundation those build on"
---

> **Parent idea**: self-custody-wallet-integration
> **Source**: [`api/app/services/wallet_service.py`](../api/app/services/wallet_service.py) | [`api/app/routers/wallet.py`](../api/app/routers/wallet.py) | [`web/components/WalletConnect.tsx`](../web/components/WalletConnect.tsx)

# Spec: Self-Custodial Wallet Integration

## Summary

Contributors bring their own EVM wallet (MetaMask, Rainbow, WalletConnect, etc.) instead of a platform-managed address. The wallet address becomes the contributor's on-chain identity anchor — used for Story Protocol IP registration, x402 micropayments, and USDC conversion. An Ed25519 keypair for off-chain signing links to the same graph node as the wallet address. No platform custody: private keys, CC, and identity always remain under the contributor's control.

This spec delivers the identity layer. Settlement (x402), Story Protocol registration, and USDC conversion are built on top of this in separate specs.

## Requirements

- [ ] **R1 — SIWE challenge/verify flow**: `GET /api/wallet/challenge` generates a [EIP-4361](https://eips.ethereum.org/EIPS/eip-4361) Sign-In With Ethereum message with a single-use nonce (5-minute TTL). `POST /api/wallet/verify` accepts the signed message, recovers the signer address via `eth_recover`, verifies nonce freshness, and links the address to the contributor's session with `trust_level: wallet_verified`. Replays and expired nonces return 401.

- [ ] **R2 — Manual address entry**: `POST /api/wallet/manual` accepts a raw EVM address (with or without checksum). The service normalizes it to EIP-55 checksum format and links it with `trust_level: wallet_unverified`. This path supports contributors who want to provide an address for attribution without signing (read-only attribution, no on-chain settlement until verified).

- [ ] **R3 — Ed25519 off-chain keypair registration**: `POST /api/wallet/keypair` accepts an Ed25519 public key generated client-side. Stores it against the contributor's wallet record. `POST /api/wallet/keypair/verify` accepts a signature over a server-issued challenge and returns `{ok: true}` if the public key verifies it. Private key is never transmitted or stored.

- [ ] **R4 — Wallet status endpoint**: `GET /api/wallet/{contributor_id}/status` returns current wallet linkage: `wallet_address`, `chain_id`, `trust_level`, `linked_at`, `ed25519_public_key` (hex), and `story_protocol_ready` (bool: address linked + chain_id set). Returns 404 if no wallet linked.

- [ ] **R5 — DB migration**: Add columns to `onboarding_sessions` table: `wallet_address VARCHAR(42)`, `wallet_chain_id INTEGER`, `wallet_trust_level VARCHAR(32)`, `wallet_linked_at TIMESTAMP`, `ed25519_public_key VARCHAR(64)`. Both SQLite (dev/test) and PostgreSQL (prod) migrations required.

- [ ] **R6 — Frontend wallet connection UI**: `WalletConnect.tsx` component supports three connection modes: (a) injected provider detection (MetaMask, Rabby, Coinbase Wallet), (b) WalletConnect v2 QR modal, (c) manual address text input with validation. Uses `wagmi` + `@wagmi/connectors` (already in `web/package.json` if present, else add). Displays current connection state and wallet address.

- [ ] **R7 — Wallet settings page**: `web/app/settings/wallet/page.tsx` shows current wallet status (linked/unlinked, trust level, address, ed25519 key), provides connect/disconnect actions, and surfaces `story_protocol_ready` status as a readiness indicator.

- [ ] **R8 — Address normalization invariant**: All wallet addresses stored and returned in EIP-55 checksum format. Inputs failing `isAddress()` validation return 422 with `code: invalid_address`.

## Research Inputs

- `2026-04-26` — [EIP-4361 Sign-In With Ethereum](https://eips.ethereum.org/EIPS/eip-4361) — canonical standard for wallet-based auth; nonce/domain/issued_at/expiry fields
- `2026-04-26` — [Story Protocol IP registration](https://docs.storyprotocol.xyz) — wallet address is required as IP registrant; this spec produces that address
- `2026-04-26` — Existing `onboarding_service.py` — `hint_wallet` field already exists but is unvalidated; this spec replaces it with a structured wallet link
- `2026-04-26` — [WalletConnect v2](https://docs.walletconnect.com) — QR-code-based connection for mobile wallets; wagmi connector wraps this

## API Contract

### `GET /api/wallet/challenge`

Request headers: `Authorization: Bearer <session_token>` (contributor must be registered)

**Response 200**
```json
{
  "nonce": "8f3a2b9c",
  "domain": "coherencycoin.com",
  "issued_at": "2026-04-26T10:00:00Z",
  "expiry": "2026-04-26T10:05:00Z",
  "siwe_message": "coherencycoin.com wants you to sign in with your Ethereum account:\n{address}\n\nSign in to Coherence Network\n\nURI: https://coherencycoin.com\nVersion: 1\nChain ID: 1\nNonce: 8f3a2b9c\nIssued At: 2026-04-26T10:00:00Z\nExpiration Time: 2026-04-26T10:05:00Z"
}
```

### `POST /api/wallet/verify`

```json
{
  "message": "<the full SIWE message text that was signed>",
  "signature": "0xabc123...<65-byte hex EIP-191 signature>"
}
```

**Response 200**
```json
{
  "contributor_id": "c_abc123",
  "wallet_address": "0xAbCd...1234",
  "chain_id": 1,
  "trust_level": "wallet_verified",
  "linked_at": "2026-04-26T10:00:30Z"
}
```

**Response 401 — signature mismatch or expired nonce**
```json
{
  "detail": "Signature verification failed",
  "code": "sig_invalid"
}
```

### `POST /api/wallet/manual`

```json
{
  "wallet_address": "0xAbCd...1234"
}
```

**Response 200**
```json
{
  "contributor_id": "c_abc123",
  "wallet_address": "0xAbCd...1234",
  "trust_level": "wallet_unverified",
  "linked_at": "2026-04-26T10:01:00Z"
}
```

**Response 422 — invalid address format**
```json
{
  "detail": "Invalid EVM address",
  "code": "invalid_address"
}
```

### `GET /api/wallet/{contributor_id}/status`

**Response 200**
```json
{
  "contributor_id": "c_abc123",
  "wallet_address": "0xAbCd...1234",
  "chain_id": 1,
  "trust_level": "wallet_verified",
  "linked_at": "2026-04-26T10:00:30Z",
  "ed25519_public_key": "a1b2c3d4...64hexchars",
  "story_protocol_ready": true
}
```

**Response 404 — no wallet linked**
```json
{
  "detail": "No wallet linked",
  "code": "wallet_not_linked"
}
```

### `POST /api/wallet/keypair`

```json
{
  "ed25519_public_key": "a1b2c3d4...64hexchars"
}
```

**Response 200**
```json
{
  "stored": true,
  "ed25519_public_key": "a1b2c3d4...64hexchars"
}
```

### `POST /api/wallet/keypair/verify`

```json
{
  "challenge": "server-issued-nonce",
  "signature": "hex-encoded-ed25519-signature",
  "public_key": "a1b2c3d4...64hexchars"
}
```

**Response 200**
```json
{
  "ok": true,
  "contributor_id": "c_abc123"
}
```

## Data Model

```yaml
OnboardingSession (existing table — add columns):
  wallet_address: string | null          # EIP-55 checksummed, e.g. "0xAbCd...1234"
  wallet_chain_id: integer | null        # EIP-155 chain ID, e.g. 1 (mainnet), 8453 (Base)
  wallet_trust_level: string | null      # "wallet_unverified" | "wallet_verified"
  wallet_linked_at: datetime | null
  ed25519_public_key: string | null      # 32-byte public key as 64-char hex

SiweNonce (new in-memory or DB table, ephemeral):
  nonce: string (primary key)            # 8-char hex random
  contributor_id: string
  issued_at: datetime
  expires_at: datetime
  used: boolean
```

## Files

### New files

- `api/app/services/wallet_service.py` — SIWE challenge generation, signature verification via `eth_account`, EIP-55 normalization, Ed25519 public key storage and verification, nonce lifecycle management
- `api/app/models/wallet.py` — Pydantic models: `WalletChallengeResponse`, `WalletVerifyRequest`, `WalletVerifyResponse`, `WalletManualRequest`, `WalletLinkResult`, `WalletStatusResponse`, `Ed25519RegisterRequest`, `Ed25519VerifyRequest`, `Ed25519VerifyResponse`
- `api/app/routers/wallet.py` — Router mounted at `/api/wallet` with endpoints: `GET /challenge`, `POST /verify`, `POST /manual`, `GET /{contributor_id}/status`, `POST /keypair`, `POST /keypair/verify`
- `api/tests/test_wallet.py` — Integration tests covering all endpoints and failure paths
- `api/alembic/versions/add_wallet_fields_to_onboarding_sessions.py` — Alembic migration adding 5 wallet columns; handles SQLite + PostgreSQL
- `web/components/WalletConnect.tsx` — Wallet connection widget: injected provider, WalletConnect QR, manual input
- `web/hooks/useWallet.ts` — React hook wrapping wagmi/connectors + API calls
- `web/app/settings/wallet/page.tsx` — Wallet settings page

### Modified files

- `api/app/services/onboarding_service.py` — Add `wallet_address`, `wallet_chain_id`, `wallet_trust_level`, `wallet_linked_at`, `ed25519_public_key` columns to `OnboardingSession` model
- `api/app/main.py` — Register `wallet_router` on `/api/wallet`
- `web/app/settings/page.tsx` — Add link to wallet sub-page

### Dependencies to add (if absent)

- `eth-account>=0.11` — Python SIWE signature recovery (PyPI)
- `PyNaCl>=1.5` — Ed25519 signature verification (PyPI)
- `wagmi`, `@wagmi/connectors`, `viem` — Frontend wallet integration (npm)

## Verification Scenarios

### Scenario 1 — SIWE happy path (wallet_verified)

```bash
# 1. Register a contributor (TOFU)
TOKEN=$(curl -s -X POST https://api.coherencycoin.com/api/onboarding/register \
  -H "Content-Type: application/json" \
  -d '{"handle":"wallet-tester-01"}' | jq -r '.session_token')

# 2. Get a SIWE challenge
CHALLENGE=$(curl -s https://api.coherencycoin.com/api/wallet/challenge \
  -H "Authorization: Bearer $TOKEN")
echo $CHALLENGE | jq .nonce
# expected: 8-char hex string, e.g. "a3f9b21c"

# 3. Sign the SIWE message with a local wallet (e.g. cast from foundry)
# cast wallet sign --private-key $PRIVKEY "$(echo $CHALLENGE | jq -r .siwe_message)"
SIG="0x<65-byte-sig>"

# 4. Verify and link
curl -s -X POST https://api.coherencycoin.com/api/wallet/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\": $(echo $CHALLENGE | jq .siwe_message), \"signature\": \"$SIG\"}" | jq .
# expected: {"contributor_id":"c_...","wallet_address":"0x...","trust_level":"wallet_verified","linked_at":"..."}
```

### Scenario 2 — Manual address entry (wallet_unverified)

```bash
TOKEN=$(curl -s -X POST https://api.coherencycoin.com/api/onboarding/register \
  -H "Content-Type: application/json" \
  -d '{"handle":"manual-wallet-user"}' | jq -r '.session_token')

curl -s -X POST https://api.coherencycoin.com/api/wallet/manual \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"0x742d35Cc6634C0532925a3b844Bc454e4438f44e"}' | jq .
# expected: {"contributor_id":"c_...","wallet_address":"0x742d35Cc6634C0532925a3b844Bc454e4438f44e","trust_level":"wallet_unverified","linked_at":"..."}

# Verify status
CID=$(curl -s https://api.coherencycoin.com/api/onboarding/session \
  -H "Authorization: Bearer $TOKEN" | jq -r '.contributor_id')
curl -s https://api.coherencycoin.com/api/wallet/$CID/status | jq .story_protocol_ready
# expected: false  (unverified → not ready for Story Protocol)
```

### Scenario 3 — Invalid address rejected

```bash
curl -s -X POST https://api.coherencycoin.com/api/wallet/manual \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"not-an-address"}' | jq '{status: .detail, code: .code}'
# expected: {"status": "Invalid EVM address", "code": "invalid_address"}
# HTTP status: 422
```

### Scenario 4 — Replayed or expired SIWE nonce

```bash
# Attempt to reuse a nonce that was already consumed
curl -s -X POST https://api.coherencycoin.com/api/wallet/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"...same message...", "signature":"...same sig..."}' | jq .code
# expected: "sig_invalid"
# HTTP status: 401
```

### Scenario 5 — Ed25519 keypair register and verify

```bash
# Register public key (generated client-side, never send private key)
curl -s -X POST https://api.coherencycoin.com/api/wallet/keypair \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ed25519_public_key":"a1b2c3d4e5f6...64chars"}' | jq .stored
# expected: true

# Get wallet status — ed25519_public_key is now populated
curl -s https://api.coherencycoin.com/api/wallet/$CID/status | jq .ed25519_public_key
# expected: "a1b2c3d4e5f6...64chars"
```

## Acceptance Tests

- `api/tests/test_wallet.py::test_siwe_challenge_returns_valid_nonce`
- `api/tests/test_wallet.py::test_wallet_verify_links_with_trust_verified`
- `api/tests/test_wallet.py::test_wallet_manual_links_with_trust_unverified`
- `api/tests/test_wallet.py::test_wallet_manual_invalid_address_returns_422`
- `api/tests/test_wallet.py::test_wallet_status_returns_all_fields`
- `api/tests/test_wallet.py::test_wallet_status_404_when_not_linked`
- `api/tests/test_wallet.py::test_siwe_replay_returns_401`
- `api/tests/test_wallet.py::test_ed25519_keypair_register_and_status`
- `api/tests/test_wallet.py::test_story_protocol_ready_true_after_siwe_verify`

## Out of Scope

- Story Protocol IP registration (separate spec)
- x402 micropayment flow (separate spec)
- USDC conversion or on-chain settlement (separate spec)
- Multi-wallet per contributor (one wallet address per contributor for now)
- Solana, NEAR, or non-EVM wallets
- Wallet-as-primary-login (TOFU handle claim still required first; wallet upgrades trust level)
- Key rotation or wallet address change after initial link

## Risks and Assumptions

- **Risk — wagmi version conflicts**: `web/package.json` may not have wagmi yet. If it pulls in a conflicting version of viem, pin to compatible versions. `wagmi@2.x` + `viem@2.x` are aligned.
- **Risk — eth_account not in api/requirements.txt**: Add `eth-account>=0.11` and `PyNaCl>=1.5`. Run `pip install` before tests.
- **Risk — SIWE nonce storage**: If the API is stateless/serverless, nonce state needs to be in Redis or the DB. Assumption: nonce table in the same PostgreSQL DB is sufficient for MVP.
- **Assumption — chain ID defaults to 1 (mainnet)**: For MVP, only mainnet Ethereum. Base (8453) and other L2s can be added in a follow-on spec once the architecture is proven.
- **Assumption — contributor must have TOFU session first**: Wallet link is an upgrade, not a replacement for handle-based identity. A contributor must register a handle before linking a wallet.
- **Proof this is working**: Monitor `wallet_trust_level = 'wallet_verified'` count in `onboarding_sessions`. Rising ratio of verified to total contributors is the primary health signal. Add to `GET /api/onboarding/roi` response as `wallet_verified_count` and `wallet_unverified_count`.
