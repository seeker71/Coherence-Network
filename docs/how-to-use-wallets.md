# How to Use Wallets — Coherence Network

A self-custody wallet integration. The platform knows your address; the keys stay yours. Linkage enables identity and attribution. Sending and receiving happen in your own wallet, not through the platform.

## What's possible today

| Action | Where it happens |
|---|---|
| Connect a wallet to your contributor identity | `/settings/wallet` (web) or `POST /api/wallets/connect` (API) |
| Verify ownership of an address (via signed message) | `/settings/wallet` → "Verify Wallet" or `POST /api/wallets/verify` |
| List wallets linked to a contributor | `GET /api/wallets/{contributor_id}` |
| Reverse lookup — find contributor by wallet address | `GET /api/wallets/lookup/{address}` |
| Disconnect a wallet | `DELETE /api/wallets/{wallet_id}` |
| Send or receive crypto | **Your own wallet UI** (MetaMask, Rainbow, Coinbase Wallet, etc.) — the platform does not intermediate transactions |

## Web flow — what a visitor sees

1. **Set up a contributor identity first.** Visit `/join` and pick a handle. The browser stores `coherence_contributor_id` in localStorage.
2. **Open `/settings/wallet`.** Click `Settings` from the menu, then `Wallet`.
3. **Click "Connect Wallet".** A RainbowKit modal opens with three connection paths:
   - **Injected providers** — MetaMask, Rabby, Coinbase Wallet, Brave Wallet (auto-detected from the browser).
   - **WalletConnect QR** — scan with a mobile wallet (Rainbow, Trust, Argent, etc.).
   - **Other wallets** — RainbowKit's full provider list.
4. **Approve in your wallet.** Your address is now in the page state but not yet linked on the platform.
5. **Click "Register Wallet".** This calls `POST /api/wallets/connect` and creates an unverified `WalletRecord` linked to your contributor.
6. **Click "Verify Wallet" (optional).** A short message is generated:
   ```
   Verify wallet ownership for Coherence Network.
   Address: 0xAbCd...1234
   Timestamp: 2026-05-09T12:00:00Z
   ```
   Your wallet asks you to sign it. The platform recovers the signer via EIP-191 and marks the record `verified: true`.
7. **Linked wallets** appear below in the list, with a green dot for verified, grey for unverified.

## API flow — for tools, scripts, and other apps

### 1. Connect a wallet

```bash
curl -X POST https://api.coherencycoin.com/api/wallets/connect \
  -H "Content-Type: application/json" \
  -d '{
    "contributor_id": "your-contributor-id",
    "address": "0xAbCd1234...",
    "chain": "ethereum",
    "label": "Main wallet"
  }'
```

**Response 201**:
```json
{
  "id": "uuid-...",
  "contributor_id": "your-contributor-id",
  "address": "0xabcd1234...",
  "chain": "ethereum",
  "verified": false,
  "verified_at": null,
  "label": "Main wallet",
  "created_at": "2026-05-09T12:00:00+00:00"
}
```

The address is normalized to lowercase. If the address is already linked to another contributor, the call returns `409 Conflict`.

### 2. Verify ownership (EIP-191 signed message)

The flow is: client crafts a message → wallet signs it → API recovers the signer.

```javascript
// Client side (browser, with wagmi/ethers/viem)
const message = `Verify wallet ownership for Coherence Network.\nAddress: ${address}\nTimestamp: ${new Date().toISOString()}`;
const signature = await signMessage({ message }); // user approves in wallet

await fetch("https://api.coherencycoin.com/api/wallets/verify", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    contributor_id: "your-contributor-id",
    address,
    message,
    signature,
  }),
});
```

The API uses `eth_account.recover_message` to recover the signer. If it matches the address, the record is marked verified.

**Response 200** — same shape as connect, with `verified: true` and `verified_at` set.

**Errors**:
- `400` if the signature doesn't match the address.
- `400` if no `WalletRecord` exists for that contributor + address (call `connect` first).
- `501` if `eth-account` isn't installed in the API runtime.

### 3. List your wallets

```bash
curl https://api.coherencycoin.com/api/wallets/your-contributor-id
```

**Response 200** — array of wallet records.

### 4. Reverse lookup — find a contributor by address

```bash
curl https://api.coherencycoin.com/api/wallets/lookup/0xabcd1234...
```

**Response 200**:
```json
{
  "contributor_id": "owner-id",
  "wallet": { "id": "...", "address": "0x...", "verified": true, ... }
}
```

Returns `404` if no contributor owns that address.

### 5. Disconnect

```bash
curl -X DELETE https://api.coherencycoin.com/api/wallets/{wallet_id}
```

The record is removed. If it was the contributor's primary `wallet_address`, that field rolls forward to the next remaining wallet, or clears if none.

## How a visitor sends or receives crypto

**Through the platform: not possible today.** This is intentional, not a gap. Self-custody means the platform never holds your keys and never moves your money.

**Through your wallet directly:**

- **Sending** — open your own wallet UI (MetaMask, Rainbow, etc.), enter the recipient's address, sign the transaction. Pay gas in the chain's native asset.
- **Receiving** — share your wallet address. Anyone can send to it on supported chains (Ethereum, Base, Polygon are wired up in `web/lib/wallet-config.ts`). The Network's reverse lookup lets the sender find your contributor profile from the address.
- **Finding someone's address from their profile** — visit `/people/{slug}` (when wallet linkage is surfaced on profiles) or query `GET /api/wallets/{contributor_id}`.

### Why the platform doesn't intermediate transactions

Three reasons, each load-bearing:

1. **Self-custody is the foundation.** The contributor holds the keys. The platform never has the authority to move funds.
2. **Chain-native is simpler than custodial.** Sending USDC on Base from your MetaMask is one signature. Routing it through a platform-managed escrow is many surfaces, much more risk, and a different trust model.
3. **The platform's job is identity and attribution.** When someone pays your wallet, attribution is automatic via the reverse-lookup edge — the sender or a third party can confirm whose contribution they're rewarding.

### What's coming next (separate specs)

- **x402 micropayment flow** — HTTP 402 protocol payments for inference, content, generation. Settles directly wallet-to-wallet via the platform's payment-required headers, but the platform never custodies funds in the path.
- **Story Protocol IP registration** — register ideas as IP using your verified wallet. Royalties flow on-chain to the verified address.
- **USDC conversion / fiat off-ramp** — partner integrations (Coinbase, Stripe Crypto) for moving between USDC and local currency. Routed through the contributor's own accounts, not the platform's.

Each of these is a separate spec written when the design is ready. Self-custody-wallet-integration is the foundation they all rest on.

## Supported chains

Configured in [`web/lib/wallet-config.ts`](../web/lib/wallet-config.ts):

- **Ethereum mainnet** (chain ID 1) — for ETH, USDC, mainnet stablecoins
- **Base** (chain ID 8453) — Coinbase L2; cheapest gas for everyday flows
- **Polygon** (chain ID 137) — POS chain; common for art and NFTs

To add a chain: add it to `chains` in `wallet-config.ts` and to the API's expected `chain` enum if validation is enforced (currently it's a free string, defaulting to `ethereum`).

## Source map

| Layer | File | Role |
|---|---|---|
| API router | [`api/app/routers/wallets.py`](../api/app/routers/wallets.py) | HTTP endpoints |
| API service | [`api/app/services/wallet_service.py`](../api/app/services/wallet_service.py) | `WalletRecord` ORM, signature verification, contributor linkage |
| Web page | [`web/app/settings/wallet/page.tsx`](../web/app/settings/wallet/page.tsx) | The visitor-facing flow |
| Wallet connect UI | [`web/components/wallet/WalletConnect.tsx`](../web/components/wallet/WalletConnect.tsx) | RainbowKit ConnectButton + register/verify actions |
| Provider tree | [`web/components/wallet/WalletProvider.tsx`](../web/components/wallet/WalletProvider.tsx) | WagmiProvider + RainbowKitProvider wrapper |
| Chain config | [`web/lib/wallet-config.ts`](../web/lib/wallet-config.ts) | Supported chains, WalletConnect project ID |
| Spec | [`specs/self-custody-wallet-integration.md`](../specs/self-custody-wallet-integration.md) | Source-of-truth design + done_when |

## When you have a question

If something doesn't behave as documented, the wellness check (`make wellness`) is the first place to look — it names spec-to-source drift gently. The Pulse (`https://pulse.coherencycoin.com/pulse/now`) names whether the API is breathing.
