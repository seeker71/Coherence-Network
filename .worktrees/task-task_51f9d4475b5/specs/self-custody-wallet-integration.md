---
idea_id: self-custody-wallet-integration
status: draft
source:
  - file: api/app/services/wallet_service.py
    symbols: [WalletRecord, connect_wallet, verify_wallet, get_wallets, get_contributor_by_wallet]
  - file: api/app/routers/wallets.py
    symbols: [connect_wallet, verify_wallet, lookup_by_address, list_wallets, disconnect_wallet]
  - file: api/app/models/contributor.py
    symbols: [ContributorBase]
  - file: api/app/adapters/postgres_models.py
    symbols: [ContributorModel]
  - file: api/app/routers/contributors.py
    symbols: [_PROVIDERS, GraduateIn]
  - file: api/app/services/ip_registration_service.py
    symbols: [is_ready, register_ip_asset]
  - file: api/app/services/settlement_service.py
    symbols: [run_daily_settlement]
  - file: web/lib/wallet-config.ts
    symbols: [walletConfig, chains]
  - file: web/components/WalletConnect.tsx
    symbols: [WalletConnect]  # new
  - file: web/app/join/_components/ContributorSetup.tsx
    symbols: [ContributorSetup]
  - file: web/app/identity/page.tsx
    symbols: [IdentityPage]
requirements:
  - "WalletRecord gains wallet_provider field (injected | walletconnect | manual) stored on connect"
  - "WalletRecord gains is_primary boolean; POST /api/wallets/{wallet_id}/primary atomically sets one primary per contributor"
  - "POST /api/wallets/challenge generates SIWE (EIP-4361) message with 10-min nonce; stored in _SIWE_NONCES dict"
  - "POST /api/wallets/verify validates SIWE nonce replay, recovers address via eth_account, sets verified=true"
  - "ip_registration_service.resolve_signer_address(contributor_id) returns primary verified wallet address"
  - "settlement_service reads verified wallet address for USDC payout routing when wallet present"
  - "web/components/WalletConnect.tsx connects via RainbowKit ConnectButton, calls /api/wallets/connect + /api/wallets/challenge + /api/wallets/verify on signature"
  - "web/app/join/_components/ContributorSetup.tsx shows WalletConnect as optional identity step"
  - "all existing wallet tests pass"
done_when:
  - "POST /api/wallets/challenge returns {message, nonce} with SIWE-formatted message"
  - "POST /api/wallets/verify returns {verified: true, wallet_id, address} on valid signature; 409 on replayed nonce"
  - "POST /api/wallets/{wallet_id}/primary returns {is_primary: true} for verified wallet; 422 for unverified"
  - "GET /api/wallets/{contributor_id} returns wallets with wallet_provider and is_primary fields"
  - "ip_registration_service.resolve_signer_address('test-contributor') returns the primary verified address"
  - "all tests pass: cd api && python -m pytest tests/ -q"
test: "cd api && python -m pytest tests/ -q"
constraints:
  - "Never store private keys — address + signature only"
  - "Only verified wallets (verified=true) may be set as primary"
  - "SIWE nonce must be consumed on first use; second use returns HTTP 409"
  - "WalletConnect v2 (AppKit) only — v1 EOL"
  - "wallet-config.ts already has mainnet/base/polygon; do not change chain list"
  - "eth_account must be in api/requirements.txt; verify before impl"
---

# Spec: Self-Custodial Wallet Integration

## Purpose

Contributors bring their own EVM wallet (MetaMask, Rainbow, WalletConnect, or manual entry) as their on-chain identity. The platform already has `wallet_service.py` with connect/verify/list/lookup and `web/lib/wallet-config.ts` with RainbowKit configured. What's missing: SIWE-compliant challenge/nonce for replay protection, a `wallet_provider` field to track connection method, `is_primary` designation, Story Protocol signer resolution via the contributor's own verified wallet, and a React component that wires RainbowKit into the API flow.

## Requirements

- [ ] **R1 — wallet_provider field**: Add `wallet_provider: Optional[str]` to `WalletRecord` ORM and pass it through `connect_wallet(...)`. Accepted values: `injected` (MetaMask, Rabby, Brave), `walletconnect`, `manual`. `WalletConnectRequest` in `wallets.py` gains `wallet_provider: Optional[str]` field.

- [ ] **R2 — is_primary field**: Add `is_primary: bool = False` to `WalletRecord` ORM. New endpoint `POST /api/wallets/{wallet_id}/primary` atomically clears `is_primary` for all other wallets of that contributor, then sets `is_primary=True` on the target. Rejects (422) if the wallet is not verified. `wallet_service.set_primary_wallet(wallet_id) -> dict` implements this.

- [ ] **R3 — SIWE challenge endpoint**: New `POST /api/wallets/challenge` takes `{address, contributor_id}` and returns `{message, nonce}`. The message follows EIP-4361 format: domain `coherencycoin.com`, URI `https://coherencycoin.com`, chain ID 1, statement `"Sign in to Coherence Network"`, 10-char alphanumeric nonce, `issued-at` as ISO 8601 UTC. Nonce stored in module-level `_SIWE_NONCES: dict[str, datetime]` in `wallet_service.py`, expires after 10 minutes.

- [ ] **R4 — SIWE nonce verification in verify_wallet**: Upgrade `wallet_service.verify_wallet(...)` to parse the SIWE nonce from the message, check it exists in `_SIWE_NONCES` and has not expired, recover the signer via `eth_account`, and delete the nonce on success. Expired/missing nonce → `ValueError("nonce expired or not found")`. Replayed nonce → `ValueError("nonce already used")`. HTTP layer maps ValueError → 400, but the router adds 409 for the replay case specifically.

- [ ] **R5 — Story Protocol signer resolution**: Add `resolve_signer_address(contributor_id: str) -> str` to `ip_registration_service.py`. Queries `wallet_service.get_wallets(contributor_id)`, returns the address of the first wallet where `is_primary=True` and `verified=True`. If none, returns the first verified wallet. If none verified, raises `IpRegistrationPending("No verified wallet for contributor {contributor_id}")`. This answers the open question in the file's docstring: signer = contributor's own wallet, not a platform hot wallet.

- [ ] **R6 — Settlement payout routing**: In `settlement_service.run_daily_settlement()`, when computing payout for a contributor, call `wallet_service.get_wallets(contributor_id)` and use the primary verified wallet address as `usdc_destination`. If no verified wallet, mark payout as `pending_wallet` and skip rather than failing the whole settlement run.

- [ ] **R7 — WalletConnect React component**: New `web/components/WalletConnect.tsx` (client component). Uses RainbowKit's `ConnectButton` from `@rainbow-me/rainbowkit` (already in `wallet-config.ts`). On wallet connected: (1) calls `POST /api/wallets/challenge` with the connected address and contributor_id from localStorage; (2) requests personal_sign on the message via wagmi's `useSignMessage`; (3) calls `POST /api/wallets/connect` then `POST /api/wallets/verify` with the signature. Shows address (first 6 + last 4 chars) and disconnect button on success.

- [ ] **R8 — Join flow integration**: `web/app/join/_components/ContributorSetup.tsx` adds `WalletConnect` as an optional step after name entry. Shown with label "Connect wallet (optional) — for on-chain CC tracking and payouts."

- [ ] **R9 — Identity page wallet section**: `web/app/identity/page.tsx` adds a "Wallet" card showing all connected wallets (address truncated, chain, verified badge, is_primary badge), "Connect wallet" button via `WalletConnect`, and "Set as primary" button on verified wallets.

## Research Inputs

- `2026-04-25` — `api/app/services/wallet_service.py` — existing EIP-191 verify; nonce/SIWE layer missing
- `2026-04-25` — `web/lib/wallet-config.ts` — RainbowKit + wagmi already configured; WalletConnect project ID via env
- `2026-04-25` — `api/app/services/ip_registration_service.py` — open question "platform hot wallet or contributor wallet" → R5 answers this
- `2026-04-25` — EIP-4361 (Sign-In with Ethereum) — SIWE message format + nonce replay protection

## API Contract

### `POST /api/wallets/challenge` (new)

**Request**
```json
{
  "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "contributor_id": "wallet-abc123"
}
```

**Response 200**
```json
{
  "nonce": "xK7mQ3pZ9w",
  "message": "coherencycoin.com wants you to sign in with your Ethereum account:\n0xd8da6bf26964af9d7eed9e03e53415d37aa96045\n\nSign in to Coherence Network\n\nURI: https://coherencycoin.com\nVersion: 1\nChain ID: 1\nNonce: xK7mQ3pZ9w\nIssued At: 2026-04-25T12:00:00.000Z"
}
```

---

### `POST /api/wallets/verify` (extended — nonce validation added)

**Request** (unchanged shape; message now must be a SIWE message)
```json
{
  "contributor_id": "wallet-abc123",
  "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "message": "<SIWE message from /challenge>",
  "signature": "0x..."
}
```

**Response 200**
```json
{
  "id": "uuid",
  "contributor_id": "wallet-abc123",
  "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "chain": "ethereum",
  "verified": true,
  "verified_at": "2026-04-25T12:00:05.000Z",
  "is_primary": false,
  "wallet_provider": "injected",
  "label": null,
  "created_at": "2026-04-25T12:00:00.000Z"
}
```

**Response 400** — bad signature
**Response 409** — nonce already used or expired

---

### `POST /api/wallets/{wallet_id}/primary` (new)

**Response 200**
```json
{
  "id": "uuid",
  "contributor_id": "wallet-abc123",
  "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "is_primary": true,
  "verified": true
}
```

**Response 422** — wallet not verified

---

### `POST /api/wallets/connect` (extended — wallet_provider added)

**Request** (wallet_provider field added)
```json
{
  "contributor_id": "wallet-abc123",
  "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "chain": "ethereum",
  "wallet_provider": "injected",
  "label": "Main wallet"
}
```

Response shape gains `wallet_provider` and `is_primary` fields.

---

### `GET /api/wallets/{contributor_id}` (extended)

Response items gain `wallet_provider` and `is_primary` fields.

## Data Model

```yaml
WalletRecord (api/app/services/wallet_service.py):
  id: String(64)
  contributor_id: String(128)  # indexed
  address: String(128)         # unique, indexed
  chain: String(32)            # default "ethereum"
  verified: Boolean            # default False
  verified_at: DateTime        # nullable
  label: String(128)           # nullable
  wallet_provider: String(32)  # NEW — injected | walletconnect | manual
  is_primary: Boolean          # NEW — default False
  created_at: DateTime

_SIWE_NONCES: dict[str, datetime]  # module-level in wallet_service.py
# key=nonce (10-char alphanum), value=expiry UTC
# Entries deleted on use or expiry. In-process only — acceptable for
# single-container deploy. If horizontally scaled, move to Redis or
# wallets table column.
```

## Files

### New files
- `web/components/WalletConnect.tsx` — RainbowKit ConnectButton + API wiring (challenge → sign → connect → verify)

### Modified files
- `api/app/services/wallet_service.py` — add `wallet_provider` + `is_primary` to `WalletRecord`; add `_SIWE_NONCES`; add `generate_siwe_challenge(address, contributor_id) -> dict`; upgrade `verify_wallet` to check SIWE nonce; add `set_primary_wallet(wallet_id) -> dict`
- `api/app/routers/wallets.py` — add `wallet_provider` to `WalletConnectRequest`; add `POST /api/wallets/challenge` handler; add `POST /api/wallets/{wallet_id}/primary` handler; map replay ValueError to 409
- `api/app/services/ip_registration_service.py` — add `resolve_signer_address(contributor_id) -> str`
- `api/app/services/settlement_service.py` — read primary verified wallet address for USDC payout routing; mark as `pending_wallet` when missing
- `web/app/join/_components/ContributorSetup.tsx` — add `WalletConnect` optional step
- `web/app/identity/page.tsx` — add wallet card with list, connect, set-primary actions

## Verification Scenarios

### Scenario 1 — Full connect + SIWE verify flow

```bash
# Connect wallet (unverified)
curl -s -X POST https://api.coherencycoin.com/api/wallets/connect \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"wallet-abc123","address":"0xd8da6bf26964af9d7eed9e03e53415d37aa96045","chain":"ethereum","wallet_provider":"injected"}' \
  | jq '{id, verified, wallet_provider}'
# Expected: { "id": "<uuid>", "verified": false, "wallet_provider": "injected" }

# Get SIWE challenge
curl -s -X POST https://api.coherencycoin.com/api/wallets/challenge \
  -H "Content-Type: application/json" \
  -d '{"address":"0xd8da6bf26964af9d7eed9e03e53415d37aa96045","contributor_id":"wallet-abc123"}' \
  | jq '{nonce, message}'
# Expected: { "nonce": "<10-char>", "message": "coherencycoin.com wants you to sign in..." }
```

### Scenario 2 — Replay attack rejected

```bash
# After a successful verify, submitting the same signature again returns 409
FIRST=$(curl -s -X POST https://api.coherencycoin.com/api/wallets/verify \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"wallet-abc123","address":"0xd8...","message":"<siwe msg>","signature":"0x..."}')
echo $FIRST | jq .verified
# Expected: true

SECOND=$(curl -s -o /dev/null -w "%{http_code}" -X POST https://api.coherencycoin.com/api/wallets/verify \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"wallet-abc123","address":"0xd8...","message":"<same siwe msg>","signature":"0x..."}')
echo $SECOND
# Expected: 409
```

### Scenario 3 — Set primary wallet

```bash
WALLET_ID=$(curl -s "https://api.coherencycoin.com/api/wallets/wallet-abc123" | jq -r '.[0].id')

curl -s -X POST "https://api.coherencycoin.com/api/wallets/${WALLET_ID}/primary" \
  | jq '{is_primary, verified}'
# Expected: { "is_primary": true, "verified": true }

# Confirm list reflects new primary
curl -s "https://api.coherencycoin.com/api/wallets/wallet-abc123" \
  | jq '[.[] | {address, is_primary}]'
# Expected: exactly one entry has is_primary=true
```

### Scenario 4 — Story Protocol signer resolution

```python
# In api/ python REPL or test
from app.services import ip_registration_service, wallet_service

# Precondition: contributor has a verified primary wallet
wallet_service.set_primary_wallet("<verified-wallet-id>")
addr = ip_registration_service.resolve_signer_address("wallet-abc123")
assert addr == "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
```

### Scenario 5 — Manual address entry, unverified

```bash
curl -s -X POST https://api.coherencycoin.com/api/wallets/connect \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"wallet-abc123","address":"0xmanual...","wallet_provider":"manual"}' \
  | jq '{verified, wallet_provider}'
# Expected: { "verified": false, "wallet_provider": "manual" }

# Attempting to set manual unverified as primary returns 422
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "https://api.coherencycoin.com/api/wallets/<manual-wallet-id>/primary"
# Expected: 422
```

## Out of Scope

- Multi-chain smart contract wallets (Safe, Argent) — EIP-1271 signature verification deferred
- Hardware wallets (Ledger, Trezor) — treated as injected by browser; no special handling needed
- On-chain CC token contract — CC remains in graph DB; wallet address is payout destination only
- USDC conversion rate logic — address routing only; conversion math in separate spec
- Story Protocol on-chain calls — `register_ip_asset` implementation deferred; `resolve_signer_address` is the handoff point

## Risks and Assumptions

- **eth_account availability**: `wallet_service.py` already imports `eth_account` with `ImportError` guard. Verify `eth-account` is in `api/requirements.txt` before impl; add if missing.
- **In-memory nonce store**: `_SIWE_NONCES` dict is process-local. Acceptable for single-container deploy. If API runs multiple workers, nonces won't share state — move to a `wallet_nonces` PostgreSQL table then.
- **WalletConnect project ID**: `wallet-config.ts` reads `NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID` from env. Must be set in `.env` or config; without it, WalletConnect QR fallback is broken (injected wallets still work). Document in README.
- **SIWE domain binding**: The challenge message hardcodes domain `coherencycoin.com`. In local dev this will differ. Impl agent should read domain from config (e.g. `config.get("domain", "coherencycoin.com")`) so local testing works.
- **Alembic migration**: Adding `wallet_provider` and `is_primary` columns to `wallets` table requires an Alembic migration for PostgreSQL. Both columns nullable/have defaults — safe to add online. SQLite dev path uses `ensure_schema()` which will pick them up automatically.
