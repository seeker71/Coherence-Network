---
idea_id: self-custody-wallet-integration
status: active
source:
  - file: api/app/routers/wallets.py
    symbols: [WalletConnectRequest, WalletVerifyRequest, connect_wallet, verify_wallet, lookup_by_address, list_wallets, disconnect_wallet]
  - file: api/app/services/wallet_service.py
    symbols: [WalletRecord, connect_wallet, verify_wallet, get_wallets, get_contributor_by_wallet, disconnect_wallet]
  - file: api/app/services/onboarding_service.py
    symbols: [OnboardingSession.hint_wallet]
  - file: api/app/adapters/postgres_models.py
    symbols: [ContributorModel.wallet_address]
  - file: api/tests/test_views_and_wallets.py
    symbols: [wallet test suite]
  - file: web/app/settings/wallet/page.tsx
    symbols: [WalletSettingsPage, ConnectedWallets]
  - file: web/components/wallet/WalletConnect.tsx
    symbols: [WalletConnect, registerWallet, verifyWallet]
  - file: web/components/wallet/WalletProvider.tsx
    symbols: [WalletProvider]
  - file: web/lib/wallet-config.ts
    symbols: [chains, walletConfig]
  - file: docs/how-to-use-wallets.md
    symbols: []
requirements:
  - "POST /api/wallets/connect accepts contributor_id + address + chain (+ optional label) and links the address as an unverified WalletRecord. Returns 201 with the record."
  - "POST /api/wallets/verify accepts contributor_id + address + message + signature; recovers signer via EIP-191 (eth_account); marks the WalletRecord verified=true with verified_at set."
  - "GET /api/wallets/{contributor_id} lists all wallets for a contributor."
  - "GET /api/wallets/lookup/{address} returns the contributor that owns a wallet address (404 if none)."
  - "DELETE /api/wallets/{wallet_id} disconnects a wallet; rolls ContributorModel.wallet_address forward to the next remaining wallet or clears it."
  - "Address normalization: stored lowercase. Duplicate-address-different-contributor returns 409 Conflict."
  - "Web /settings/wallet renders a RainbowKit ConnectButton, surfaces register and verify actions, lists linked wallets with verified status."
  - "WalletProvider wraps wagmi + RainbowKit + react-query for any subtree using wallet hooks; renders nothing until mounted (SSR-safe)."
  - "Supported chains: Ethereum mainnet (1), Base (8453), Polygon (137)."
  - "Self-custody invariant: the platform never stores private keys, never custodies funds, never intermediates transactions. Send and receive happen in the visitor's own wallet."
done_when:
  - "POST /api/wallets/connect with a fresh address returns 201 with verified=false, address normalized to lowercase."
  - "POST /api/wallets/verify with a valid EIP-191 signature for the connected address returns 200 with verified=true and verified_at set."
  - "POST /api/wallets/verify with a mismatched signature returns 400 with a clear error message."
  - "GET /api/wallets/{contributor_id} returns the array of WalletRecord dicts."
  - "GET /api/wallets/lookup/{address} returns 200 with {contributor_id, wallet} for a linked address, 404 otherwise."
  - "Visiting /settings/wallet without a contributor_id in localStorage shows the 'Set up your contributor first' prompt linking to /join."
  - "Visiting /settings/wallet with a contributor_id renders the Connect Wallet button and Linked wallets section."
  - "All tests in api/tests/test_views_and_wallets.py covering wallet flows pass."
test: "cd api && python3 -m pytest tests/test_views_and_wallets.py -q -k wallet"
constraints:
  - "Platform NEVER stores private keys; only wallet addresses (and optional ed25519 public keys in a future spec)."
  - "Address inputs normalized to lowercase before storage; duplicate-address conflict returns 409."
  - "WalletProvider renders null until mounted to avoid Wagmi hooks firing without WagmiProvider in the tree."
  - "Send/receive flows belong to the visitor's wallet UI (MetaMask, Rainbow, etc.); the platform does not intermediate."
  - "Chain validation is currently a free string; tighten to an enum only when send/receive flows land that depend on it."
---

> **Parent idea**: self-custody-wallet-integration
> **Source**: [`api/app/routers/wallets.py`](../api/app/routers/wallets.py) | [`api/app/services/wallet_service.py`](../api/app/services/wallet_service.py) | [`web/components/wallet/WalletConnect.tsx`](../web/components/wallet/WalletConnect.tsx) | [`web/app/settings/wallet/page.tsx`](../web/app/settings/wallet/page.tsx)
> **How-to**: [`docs/how-to-use-wallets.md`](../docs/how-to-use-wallets.md)

# Spec: Self-Custodial Wallet Integration

## Summary

Contributors bring their own EVM wallet (MetaMask, Rainbow, WalletConnect, etc.) instead of a platform-managed address. The wallet address becomes the contributor's on-chain identity anchor. The platform stores only the address (and a verified flag); private keys never leave the visitor's wallet, and the platform never intermediates transactions. Send and receive happen in the visitor's own wallet UI.

This spec delivers the **identity layer**. Settlement (x402, USDC), Story Protocol IP registration, and any platform-mediated payment flows are built on top of this in separate specs.

## Requirements

- [x] **R1 — Connect a wallet to a contributor.** `POST /api/wallets/connect` accepts `{contributor_id, address, chain, label?}` and creates a `WalletRecord` with `verified=false`. Address normalized to lowercase. Returns 201 with the record. Duplicate-address-on-different-contributor returns 409.

- [x] **R2 — Verify wallet ownership via EIP-191 signature.** `POST /api/wallets/verify` accepts `{contributor_id, address, message, signature}`. Service uses `eth_account.recover_message` to recover the signer; if it matches the address, the record is marked `verified=true` with `verified_at` timestamp.

- [x] **R3 — List a contributor's wallets.** `GET /api/wallets/{contributor_id}` returns an array of WalletRecord dicts ordered by `created_at`.

- [x] **R4 — Reverse lookup contributor by address.** `GET /api/wallets/lookup/{address}` returns the contributor that owns the address (404 if none).

- [x] **R5 — Disconnect a wallet.** `DELETE /api/wallets/{wallet_id}` removes the record. If it was the contributor's primary `wallet_address`, that field rolls forward to the next remaining wallet or clears.

- [x] **R6 — Web flow at `/settings/wallet`.** Renders a RainbowKit ConnectButton, lets the visitor register the connected address against their contributor identity, and verify ownership via signed message. Lists linked wallets with verified state.

- [x] **R7 — WalletProvider SSR-safe.** Wraps wagmi + RainbowKit + react-query around any subtree that uses wallet hooks. Renders `null` until mounted so wagmi hooks never fire without WagmiProvider in the tree.

- [x] **R8 — Supported chains.** Ethereum mainnet (1), Base (8453), Polygon (137) configured in `web/lib/wallet-config.ts`.

## API Contract

### `POST /api/wallets/connect`

```json
{
  "contributor_id": "c_abc123",
  "address": "0xAbCd1234...",
  "chain": "ethereum",
  "label": "Main wallet"
}
```

**Response 201**:
```json
{
  "id": "uuid-...",
  "contributor_id": "c_abc123",
  "address": "0xabcd1234...",
  "chain": "ethereum",
  "verified": false,
  "verified_at": null,
  "label": "Main wallet",
  "created_at": "2026-05-09T12:00:00+00:00"
}
```

**Response 409** — address linked to a different contributor.

### `POST /api/wallets/verify`

```json
{
  "contributor_id": "c_abc123",
  "address": "0xabcd1234...",
  "message": "Verify wallet ownership for Coherence Network.\nAddress: 0xAbCd1234...\nTimestamp: 2026-05-09T12:00:00Z",
  "signature": "0x<65-byte-hex-signature>"
}
```

**Response 200** — same shape as connect, with `verified=true`, `verified_at` set.

**Response 400** — signature mismatch, or no record to verify.

**Response 501** — `eth-account` not installed in API runtime.

### `GET /api/wallets/{contributor_id}`

**Response 200** — array of WalletRecord dicts.

### `GET /api/wallets/lookup/{address}`

**Response 200**:
```json
{
  "contributor_id": "c_abc123",
  "wallet": { "id": "...", "address": "0x...", "verified": true, ... }
}
```

**Response 404** — no contributor owns that address.

### `DELETE /api/wallets/{wallet_id}`

**Response 200**:
```json
{ "deleted": true, "wallet_id": "uuid-..." }
```

**Response 404** — wallet not found.

## Data Model

```yaml
WalletRecord (table: wallets):
  id: string (primary key, uuid)
  contributor_id: string (indexed)
  address: string (unique, indexed, normalized lowercase)
  chain: string (default "ethereum")
  verified: boolean (default false)
  verified_at: datetime | null
  label: string | null
  created_at: datetime

ContributorModel.wallet_address: string | null
  # Mirror of the contributor's primary wallet (first connected, or rolled
  # forward on disconnect). Used for fast-path attribution.
```

## Web flow — what a visitor experiences

1. Visit `/join`, set up a contributor handle (stored as `coherence_contributor_id` in localStorage).
2. Visit `/settings/wallet`. The page detects the contributor_id and wraps the wallet UI in `WalletProvider` (Wagmi + RainbowKit).
3. Click **Connect Wallet** — RainbowKit modal opens with injected providers + WalletConnect QR.
4. Approve in your wallet. Address now in page state.
5. Click **Register Wallet** — calls `POST /api/wallets/connect`, creates an unverified record.
6. Click **Verify Wallet** (optional) — page generates a short message with address + timestamp; wallet signs; calls `POST /api/wallets/verify`; record marked verified.
7. **Linked wallets** list shows the records with verified status (green dot for verified, grey for unverified).

See [`docs/how-to-use-wallets.md`](../docs/how-to-use-wallets.md) for the full visitor flow, API examples, and send/receive guidance.

## Self-custody invariant

The platform never:
- Stores private keys.
- Custodies funds.
- Intermediates transactions.
- Asks the visitor to sign anything beyond simple ownership-proof messages.

The platform only knows the visitor's address (and a verified flag). All sending and receiving happens in the visitor's own wallet UI on the chain they choose.

## Acceptance Tests

- `api/tests/test_views_and_wallets.py::test_wallets_connect_creates_unverified_record`
- `api/tests/test_views_and_wallets.py::test_wallets_verify_marks_record_verified`
- `api/tests/test_views_and_wallets.py::test_wallets_verify_rejects_mismatched_signature`
- `api/tests/test_views_and_wallets.py::test_wallets_list_returns_contributor_wallets`
- `api/tests/test_views_and_wallets.py::test_wallets_lookup_returns_owner_or_404`
- `api/tests/test_views_and_wallets.py::test_wallets_disconnect_rolls_forward_primary`

## Out of Scope (separate specs when designed)

- **x402 micropayment flow** — HTTP 402 wallet-to-wallet settlement for inference, content, generation. Self-custody invariant preserved: the platform never holds funds in the path.
- **Story Protocol IP registration** — register ideas as IP using a verified wallet; royalties flow on-chain to the verified address.
- **USDC conversion / fiat off-ramp** — partner integrations (Coinbase, Stripe Crypto) routed through the contributor's own accounts.
- **Ed25519 off-chain keypair** — was originally in this spec; deferred to whichever signing-flow spec needs it. Not currently implemented.
- **EIP-4361 (SIWE) full flow** — current verification uses a free-form ownership-proof message + EIP-191 recovery. SIWE adds nonce/domain/expiry guarantees needed for stronger session-binding; can be a future hardening once a session model needs it.
- **Multi-wallet roles** — the model supports multiple wallets per contributor, but the UI doesn't yet differentiate primary / treasury / hot / cold roles.
- **Solana, NEAR, or non-EVM wallets.**

## Risks and Assumptions

- **Risk — `eth-account` not installed in API runtime.** The verify endpoint returns 501 if the package is missing. Add `eth-account>=0.11` to `api/requirements.txt`.
- **Risk — `@react-native-async-storage/async-storage` and `pino-pretty` warnings during web build.** These are optional peer dependencies of `@metamask/sdk` and `pino` respectively; they're not used in browser builds and can be safely ignored. To silence, add them to `web/package.json` or configure webpack to mark them external.
- **Assumption — contributor_id from localStorage is enough to authenticate the connect/verify flow for now.** When the platform adds session tokens, the wallet endpoints should require them. Today the fast-path is open by design (TOFU model).
- **Assumption — chain is a free string.** Validation tightens when send/receive flows that depend on the specific chain (gas, decimals, contract addresses) land.

## Known Gaps from Original Design

The first draft of this spec described a SIWE + Ed25519 + manual-entry + alembic-migration architecture. The implementation that shipped is simpler:

| Original design | Reality |
|---|---|
| `api/app/models/wallet.py` Pydantic models | Models live inline in `api/app/routers/wallets.py` |
| `api/app/routers/wallet.py` (singular) | `api/app/routers/wallets.py` (plural) |
| `api/alembic/versions/add_wallet_fields.py` migration | No alembic — `wallets` table created via `unified_db.ensure_schema()` |
| `OnboardingSession.wallet_address/wallet_chain_id/wallet_trust_level/ed25519_public_key` | Separate `wallets` table; `ContributorModel.wallet_address` mirrors the primary |
| `GET /api/wallet/challenge` (SIWE nonce) + `POST /api/wallet/verify` (SIWE signed) | `POST /api/wallets/verify` with free-form EIP-191 message |
| `POST /api/wallet/manual` (separate manual-entry path) | Single `POST /api/wallets/connect` creates the record; verify is optional |
| `GET /api/wallet/{id}/keypair` (Ed25519 public key) | Not implemented |
| `web/hooks/useWallet.ts` | Hooks come from wagmi directly inside `WalletConnect.tsx` |
| `web/components/WalletConnect.tsx` (flat) | `web/components/wallet/WalletConnect.tsx` (subdirectory) |

This spec now describes what shipped. The pieces that didn't ship (SIWE, Ed25519, manual-as-separate-endpoint, alembic) are listed in *Out of Scope* with notes on what would re-introduce them.
