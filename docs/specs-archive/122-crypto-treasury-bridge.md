# Spec 122: Crypto Treasury Bridge -- BTC/ETH to Coherence Credit Exchange

**Depends on**: Spec 119 (Coherence Credit), Spec 123 (Transparent Audit Ledger)
**Depended on by**: Spec 121 (OpenClaw Idea Marketplace -- CC payouts)

## Purpose

Coherence Credits (CC) are currently an internal unit of account with no external backing. This spec introduces a crypto treasury that backs CC with real BTC and ETH deposits. Users can deposit BTC or ETH to receive CC, and withdraw CC back to BTC or ETH subject to governance approval. The founder provides initial seed funding to bootstrap the treasury. All treasury operations are recorded on-chain and in the internal audit ledger (spec 123) to ensure full transparency. Without this bridge, CC has no redeemable value and cannot incentivize external contributors to participate in the OpenClaw idea marketplace.

## Coherence-First Design Principles

This spec follows coherence-first economics: transparency and verifiability replace the need for external enforcement.

1. **Continuous coherence verification** — Treasury coherence score (`treasury_balance / (cc_supply × exchange_rate)`) is computed and published on every deposit/withdrawal. If it drops below 1.0, the system halts CC operations and publishes the discrepancy. No quarterly audits by trusted third parties — the math is always visible.

2. **Friction proportional to risk** — Small withdrawals (< 100 CC) are instant. Medium (100–1000 CC) need 24h cooldown + 1 approval. Large (> 1000 CC) need 72h + community quorum. This replaces rigid multisig rules with adaptive, transparent friction.

3. **Deposit capital is always returnable** — Withdrawing your own deposited capital is a right, not a governance vote. The governance process applies only to pool payouts (contribution rewards, bounties, staking returns). This is the foundation of trust.

4. **Transparency as compliance** — CC is a unit of account within the system, not a transmitted currency. BTC/ETH deposits are contributions to a commons. The complete audit trail (spec 123) is the compliance artifact — any regulator can verify any claim via a public URL.

5. **No artificial scarcity or yield** — CC supply is backed 1:1 by deposits. Appreciation comes from proven value creation (ideas that generate real usage), not from tokenomics games. Staking into ideas is a bet on real outcomes, not a yield farm.

## Requirements

- [ ] **R1: Treasury wallet management** -- The system manages at least one BTC wallet and one ETH wallet for receiving deposits. Wallet addresses are publicly visible. Private keys are stored in a hardware security module (HSM) or equivalent secrets manager -- never in application code or config files.
- [ ] **R2: Deposit flow** -- A user initiates a deposit via `POST /api/treasury/deposit` which returns a deposit address, expected amount, and a unique deposit_id. The system monitors the blockchain for the incoming transaction. Once confirmed (6 confirmations for BTC, 12 for ETH), CC is minted to the user's account at the current exchange rate. Deposit status is queryable via `GET /api/treasury/deposit/{deposit_id}`.
- [ ] **R3: Exchange rate computation** -- CC/BTC and CC/ETH exchange rates are derived from: (a) the CC/USD rate from spec 119 ExchangeRate config, and (b) real-time BTC/USD and ETH/USD prices from a configurable price oracle (default: CoinGecko API). Exchange rates are cached for 5 minutes and include a 1% spread to cover volatility during confirmation wait. Rate is locked at deposit initiation time.
- [ ] **R4: CC minting** -- CC is minted (created) only when backed by a confirmed on-chain deposit. The total CC supply equals the sum of all minted CC minus all burned CC. The supply is queryable via `GET /api/treasury/supply`. Minting events are recorded in the audit ledger.
- [ ] **R5: Withdrawal flow** -- A user requests withdrawal via `POST /api/treasury/withdraw`. The system distinguishes two withdrawal types: (a) **Deposit capital returns** — withdrawing CC that originated from the user's own deposits does NOT require governance approval; instead, it uses time-locked escrow with amount-proportional cooldown (< 100 CC: instant, 100–1000 CC: 24h cooldown + 1 approval, > 1000 CC: 72h cooldown + community quorum). (b) **Pool payouts** (contribution rewards, bounties, staking returns) — these create a governance ChangeRequest (type=TREASURY_WITHDRAWAL) requiring minimum 2 approvals (configurable). On completion, CC is burned and the equivalent BTC or ETH is sent from the treasury wallet. Withdrawal fee: 0.5% to cover gas/network fees, minimum 0.0001 BTC or 0.001 ETH.
- [ ] **R6: Balance tracking** -- Each user has a CC balance tracked internally. `GET /api/treasury/balance` returns the user's CC balance, equivalent BTC value, and equivalent ETH value at current rates. Balance cannot go negative.
- [ ] **R7: Founder seed funding** -- The system supports a bootstrap deposit with `founder_seed: true` flag that mints CC to a designated founder account. Seed deposits bypass the standard deposit monitoring flow (founder provides transaction hash directly). Limited to accounts with `role: founder` in the contributor registry.
- [ ] **R8: Multisig treasury control** -- Multisig is used for pool payouts and system operations. Individual deposit returns use time-locked escrow with amount-proportional cooldown. For pool payouts and system operations requiring multisig: 2-of-3 signers for amounts under 1 BTC / 10 ETH equivalent, 3-of-3 for larger amounts. Signer identities are public and listed in the treasury configuration.
- [ ] **R9: Reserve ratio enforcement** -- The system enforces a minimum reserve ratio of 100% (CC supply never exceeds the value of on-chain assets). If price drops cause the reserve ratio to fall below 100%, withdrawals are paused until the ratio recovers or governance votes to adjust.
- [ ] **R10: Deposit limits** -- Minimum deposit: 0.0001 BTC or 0.001 ETH. Maximum single deposit: 10 BTC or 100 ETH (configurable via governance). Deposits below minimum are returned minus network fee.
- [ ] **R11: Treasury dashboard data** -- `GET /api/treasury/summary` returns total BTC held, total ETH held, total CC supply, reserve ratio, current exchange rates, and pending withdrawal count. All data is public.

## Research Inputs (Required)

- `2026-03-18` - Spec 119 Coherence Credit models -- CC/USD exchange rate anchor and epoch system
- `2026-03-20` - Bitcoin confirmation safety analysis -- 6 confirmations provides ~99.97% finality for typical transaction values
- `2026-03-20` - Ethereum finality model (post-merge) -- 12 confirmations (~2.5 minutes) provides strong finality guarantee
- `2026-03-20` - CoinGecko API v3 documentation -- free tier supports 10-30 calls/minute, sufficient for 5-minute cache
- `2026-03-18` - Spec 094 Governance -- ChangeRequest model for withdrawal approvals
- `2026-03-20` - BIP-174 (PSBT) -- Partially Signed Bitcoin Transactions for multisig workflow
- `2026-03-20` - EIP-712 -- Typed structured data signing for Ethereum multisig

## Task Card (Required)

```yaml
goal: Implement crypto treasury bridge with BTC/ETH deposit, CC minting, governance-approved withdrawal, and reserve enforcement
files_allowed:
  - api/app/models/treasury.py
  - api/app/services/treasury_service.py
  - api/app/services/price_oracle_service.py
  - api/app/services/blockchain_monitor_service.py
  - api/app/routers/treasury.py
  - api/app/main.py
  - api/app/models/governance.py
  - data/treasury_config.json
  - api/tests/test_treasury.py
  - api/tests/test_price_oracle.py
  - specs/122-crypto-treasury-bridge.md
done_when:
  - POST /api/treasury/deposit returns deposit address and deposit_id
  - GET /api/treasury/deposit/{deposit_id} returns confirmation status
  - CC is minted only after on-chain confirmation threshold met
  - POST /api/treasury/withdraw creates governance ChangeRequest
  - Approved withdrawal burns CC and queues on-chain transaction
  - GET /api/treasury/balance returns user balance with BTC/ETH equivalents
  - GET /api/treasury/supply shows total CC supply equals minted minus burned
  - Reserve ratio enforced at 100%
  - All tests pass
commands:
  - python3 -m pytest api/tests/test_treasury.py -x -v
  - python3 -m pytest api/tests/test_price_oracle.py -x -v
  - python3 -m pytest api/tests/test_governance_api.py -x -q
constraints:
  - Private keys NEVER appear in code, config, logs, or API responses
  - All treasury operations logged to audit ledger (spec 123)
  - Exchange rate locked at deposit initiation, not confirmation time
  - Governance model extensions must be backward compatible
```

## API Contract

### `POST /api/treasury/deposit`

Initiate a crypto deposit to receive CC.

**Request**
```json
{
  "user_id": "alice",
  "currency": "BTC",
  "expected_amount": 0.05,
  "founder_seed": false
}
```

**Response 201**
```json
{
  "deposit_id": "dep_abc123",
  "user_id": "alice",
  "currency": "BTC",
  "deposit_address": "bc1q...",
  "expected_amount_crypto": 0.05,
  "locked_exchange_rate": {
    "cc_per_btc": 16666.67,
    "btc_usd": 50000.0,
    "cc_per_usd": 333.33,
    "spread_pct": 1.0,
    "locked_at": "2026-03-20T12:00:00Z"
  },
  "expected_cc_amount": 833.33,
  "confirmations_required": 6,
  "status": "awaiting_deposit",
  "expires_at": "2026-03-20T13:00:00Z",
  "created_at": "2026-03-20T12:00:00Z"
}
```

**Response 422**
```json
{
  "detail": "Deposit amount below minimum",
  "errors": [{"field": "expected_amount", "message": "Minimum BTC deposit is 0.0001"}]
}
```

### `GET /api/treasury/deposit/{deposit_id}`

Check deposit confirmation status.

**Response 200**
```json
{
  "deposit_id": "dep_abc123",
  "user_id": "alice",
  "currency": "BTC",
  "expected_amount_crypto": 0.05,
  "received_amount_crypto": 0.05,
  "tx_hash": "abc123def456...",
  "confirmations": 6,
  "confirmations_required": 6,
  "status": "confirmed",
  "cc_minted": 833.33,
  "confirmed_at": "2026-03-20T12:45:00Z"
}
```

**Response 404**
```json
{ "detail": "Deposit not found" }
```

### `GET /api/treasury/balance`

Get user's CC balance and crypto equivalents.

**Request (query params)**
- `user_id`: string (required)

**Response 200**
```json
{
  "user_id": "alice",
  "cc_balance": 833.33,
  "equivalent_btc": 0.04995,
  "equivalent_eth": 0.2498,
  "btc_usd_rate": 50000.0,
  "eth_usd_rate": 3333.33,
  "cc_per_usd": 333.33,
  "as_of": "2026-03-20T14:00:00Z"
}
```

### `POST /api/treasury/withdraw`

Request CC withdrawal to crypto.

**Request**
```json
{
  "user_id": "alice",
  "cc_amount": 500.0,
  "target_currency": "ETH",
  "destination_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f..."
}
```

**Response 201**
```json
{
  "withdrawal_id": "wdr_xyz789",
  "user_id": "alice",
  "cc_amount": 500.0,
  "fee_cc": 2.5,
  "net_cc": 497.5,
  "target_currency": "ETH",
  "estimated_crypto_amount": 0.1493,
  "destination_address": "0x742d35Cc...",
  "governance_request_id": "cr_gov123",
  "status": "pending_governance",
  "required_approvals": 2,
  "created_at": "2026-03-20T15:00:00Z"
}
```

**Response 400**
```json
{ "detail": "Insufficient CC balance" }
```

**Response 422**
```json
{
  "detail": "Invalid destination address",
  "errors": [{"field": "destination_address", "message": "Not a valid ETH address"}]
}
```

### `GET /api/treasury/supply`

Public treasury supply information.

**Response 200**
```json
{
  "total_cc_minted": 50000.0,
  "total_cc_burned": 2000.0,
  "cc_in_circulation": 48000.0,
  "total_btc_held": 1.5,
  "total_eth_held": 10.0,
  "btc_value_usd": 75000.0,
  "eth_value_usd": 33333.0,
  "total_treasury_value_usd": 108333.0,
  "total_cc_value_usd": 144.0,
  "reserve_ratio": 1.0,
  "reserve_status": "healthy",
  "withdrawals_paused": false,
  "as_of": "2026-03-20T14:00:00Z"
}
```

### `GET /api/treasury/summary`

Public treasury dashboard data.

**Response 200**
```json
{
  "btc_held": 1.5,
  "eth_held": 10.0,
  "cc_supply": 48000.0,
  "reserve_ratio": 1.0,
  "current_rates": {
    "cc_per_btc": 16666.67,
    "cc_per_eth": 1111.11,
    "cc_per_usd": 333.33,
    "btc_usd": 50000.0,
    "eth_usd": 3333.33
  },
  "pending_withdrawals": 2,
  "multisig_signers": ["signer-a", "signer-b", "signer-c"],
  "as_of": "2026-03-20T14:00:00Z"
}
```

## Data Model

```yaml
TreasuryConfig:
  properties:
    btc_wallet_address: { type: string }
    eth_wallet_address: { type: string }
    multisig_signers: { type: "list[str]", min_items: 3 }
    multisig_threshold_low: { type: int, default: 2, description: "Signers for < 1 BTC" }
    multisig_threshold_high: { type: int, default: 3, description: "Signers for >= 1 BTC" }
    high_value_threshold_btc: { type: float, default: 1.0 }
    high_value_threshold_eth: { type: float, default: 10.0 }
    min_deposit_btc: { type: float, default: 0.0001 }
    min_deposit_eth: { type: float, default: 0.001 }
    max_deposit_btc: { type: float, default: 10.0 }
    max_deposit_eth: { type: float, default: 100.0 }
    btc_confirmations: { type: int, default: 6 }
    eth_confirmations: { type: int, default: 12 }
    spread_pct: { type: float, default: 1.0 }
    withdrawal_fee_pct: { type: float, default: 0.5 }
    min_reserve_ratio: { type: float, default: 1.0 }
    price_oracle_url: { type: string, default: "https://api.coingecko.com/api/v3" }
    price_cache_ttl_seconds: { type: int, default: 300 }
    deposit_expiry_minutes: { type: int, default: 60 }

Deposit:
  properties:
    deposit_id: { type: string, format: "dep_{uuid}" }
    user_id: { type: string, min_length: 1 }
    currency: { type: string, enum: ["BTC", "ETH"] }
    deposit_address: { type: string }
    expected_amount_crypto: { type: float, gt: 0 }
    received_amount_crypto: { type: "float | null" }
    tx_hash: { type: "string | null" }
    confirmations: { type: int, default: 0 }
    confirmations_required: { type: int }
    locked_exchange_rate: { type: LockedRate }
    expected_cc_amount: { type: float }
    cc_minted: { type: "float | null" }
    status: { type: string, enum: ["awaiting_deposit", "detected", "confirming", "confirmed", "expired", "failed"] }
    founder_seed: { type: bool, default: false }
    expires_at: { type: datetime }
    created_at: { type: datetime }
    confirmed_at: { type: "datetime | null" }

LockedRate:
  properties:
    cc_per_crypto: { type: float, gt: 0 }
    crypto_usd: { type: float, gt: 0 }
    cc_per_usd: { type: float, gt: 0 }
    spread_pct: { type: float }
    locked_at: { type: datetime }

Withdrawal:
  properties:
    withdrawal_id: { type: string, format: "wdr_{uuid}" }
    user_id: { type: string, min_length: 1 }
    cc_amount: { type: float, gt: 0 }
    fee_cc: { type: float, ge: 0 }
    net_cc: { type: float, gt: 0 }
    target_currency: { type: string, enum: ["BTC", "ETH"] }
    estimated_crypto_amount: { type: float }
    destination_address: { type: string, min_length: 1 }
    governance_request_id: { type: string }
    tx_hash: { type: "string | null" }
    status: { type: string, enum: ["pending_governance", "approved", "processing", "completed", "rejected", "failed"] }
    multisig_signatures: { type: "list[str]", default: [] }
    created_at: { type: datetime }
    completed_at: { type: "datetime | null" }

UserBalance:
  properties:
    user_id: { type: string }
    cc_balance: { type: float, ge: 0 }
    total_deposited_cc: { type: float, ge: 0 }
    total_withdrawn_cc: { type: float, ge: 0 }
    total_earned_cc: { type: float, ge: 0, description: "CC from marketplace attribution" }
    last_updated: { type: datetime }

TreasurySupply:
  properties:
    total_cc_minted: { type: float, ge: 0 }
    total_cc_burned: { type: float, ge: 0 }
    cc_in_circulation: { type: float, ge: 0 }
    total_btc_held: { type: float, ge: 0 }
    total_eth_held: { type: float, ge: 0 }
    reserve_ratio: { type: float, ge: 0 }
    reserve_status: { type: string, enum: ["healthy", "warning", "paused"] }
    withdrawals_paused: { type: bool }
```

## Files to Create/Modify

- `api/app/models/treasury.py` -- Pydantic models: TreasuryConfig, Deposit, LockedRate, Withdrawal, UserBalance, TreasurySupply
- `api/app/services/treasury_service.py` -- deposit initiation, CC minting, withdrawal flow, balance tracking, reserve enforcement, supply computation
- `api/app/services/price_oracle_service.py` -- CoinGecko price fetching with TTL cache, rate computation
- `api/app/services/blockchain_monitor_service.py` -- transaction confirmation monitoring (abstracted interface for BTC and ETH)
- `api/app/routers/treasury.py` -- route handlers for all treasury endpoints
- `api/app/main.py` -- wire treasury router
- `api/app/models/governance.py` -- add TREASURY_WITHDRAWAL to ChangeRequestType enum
- `data/treasury_config.json` -- default treasury configuration (wallet addresses empty, to be configured at deploy time)
- `api/tests/test_treasury.py` -- contract tests for all requirements
- `api/tests/test_price_oracle.py` -- unit tests for price oracle with mocked API responses

## Acceptance Tests

- `api/tests/test_treasury.py::test_deposit_initiation_201` -- returns deposit address and locked rate
- `api/tests/test_treasury.py::test_deposit_below_minimum_422` -- rejects too-small deposits
- `api/tests/test_treasury.py::test_deposit_above_maximum_422` -- rejects too-large deposits
- `api/tests/test_treasury.py::test_deposit_confirmation_mints_cc` -- CC minted after confirmation threshold
- `api/tests/test_treasury.py::test_deposit_expiry` -- unconfirmed deposit expires after timeout
- `api/tests/test_treasury.py::test_deposit_rate_locked_at_initiation` -- rate does not change during confirmation
- `api/tests/test_treasury.py::test_founder_seed_deposit` -- founder can seed with tx_hash directly
- `api/tests/test_treasury.py::test_balance_query` -- returns CC with BTC/ETH equivalents
- `api/tests/test_treasury.py::test_balance_never_negative` -- withdrawal beyond balance returns 400
- `api/tests/test_treasury.py::test_withdrawal_creates_governance_request` -- withdrawal creates ChangeRequest with type TREASURY_WITHDRAWAL
- `api/tests/test_treasury.py::test_withdrawal_approval_burns_cc` -- approved withdrawal reduces CC supply
- `api/tests/test_treasury.py::test_withdrawal_rejection_returns_cc` -- rejected withdrawal restores balance
- `api/tests/test_treasury.py::test_withdrawal_fee_deducted` -- 0.5% fee applied correctly
- `api/tests/test_treasury.py::test_supply_equals_minted_minus_burned` -- invariant: supply = minted - burned
- `api/tests/test_treasury.py::test_reserve_ratio_enforcement` -- withdrawals paused when ratio < 100%
- `api/tests/test_treasury.py::test_multisig_threshold_low_value` -- 2-of-3 for small withdrawals
- `api/tests/test_treasury.py::test_multisig_threshold_high_value` -- 3-of-3 for large withdrawals
- `api/tests/test_treasury.py::test_summary_endpoint_shape` -- all required fields present and public
- `api/tests/test_treasury.py::test_invalid_destination_address_422` -- bad address format rejected
- `api/tests/test_price_oracle.py::test_price_cache_ttl` -- cached price used within TTL
- `api/tests/test_price_oracle.py::test_price_oracle_failure_fallback` -- stale cache used on API failure
- `api/tests/test_price_oracle.py::test_spread_applied` -- 1% spread included in exchange rate

## Concurrency Behavior

- **Balance operations**: Must use optimistic locking (version field on UserBalance) to prevent double-spend on concurrent withdrawal requests. This is an exception to the project-wide last-write-wins default because financial correctness requires it.
- **Deposit monitoring**: Single-threaded polling loop; concurrent deposits for different users are safe. Same user concurrent deposits are safe (each has unique deposit_id).
- **Price cache**: Thread-safe; stale reads are acceptable (5-minute TTL).

## Failure and Retry Behavior

- **Price oracle unavailable**: Use last cached price if available (log warning). If no cached price exists, return 503 with "Price data unavailable, try again later."
- **Blockchain monitor unavailable**: Deposit stays in "awaiting_deposit" or "confirming" state. Monitor retries every 30 seconds. No CC minted until confirmation succeeds.
- **Withdrawal transaction failure**: Withdrawal status set to "failed", CC returned to user balance, error logged to audit ledger. Manual intervention required.
- **Governance timeout**: Withdrawal requests without governance action for 7 days are auto-expired and CC returned.
- **Database unavailable**: Return 503; client retries with exponential backoff.
- **Key management failure**: If HSM/secrets manager is unreachable, all withdrawal processing halts. Deposits can still be initiated (no private key needed for receiving).

## Verification

```bash
python3 -m pytest api/tests/test_treasury.py -x -v
python3 -m pytest api/tests/test_price_oracle.py -x -v
python3 -m pytest api/tests/test_governance_api.py -x -q
python3 scripts/validate_spec_quality.py --file specs/122-crypto-treasury-bridge.md
```

Manual verification:
- Initiate a testnet BTC deposit, confirm it, verify CC minted.
- Request withdrawal, approve via governance, verify CC burned and transaction queued.
- Verify `GET /api/treasury/supply` shows correct reserve ratio.
- Verify all operations appear in audit ledger (spec 123).

## Out of Scope

- Stablecoin support (USDC, USDT) -- future spec
- Fiat on/off ramp (bank transfers)
- Automated market maker or liquidity pools
- CC trading between users (peer-to-peer CC transfer is a separate spec)
- Tax reporting or regulatory compliance reporting
- Mobile wallet integration
- Smart contract deployment (multisig handled at application layer for MVP)
- Mainnet deployment (testnet only for Phase 1)

## Risks and Assumptions

- **Risk: Key compromise** -- If treasury private keys are compromised, all funds are at risk. Mitigation: HSM storage, multisig requiring 2-of-3 or 3-of-3, key rotation procedure documented. Emergency: governance can vote to pause all withdrawals.
- **Risk: Price oracle manipulation** -- CoinGecko API could return manipulated prices. Mitigation: 5-minute cache limits exposure window. Future: use multiple oracle sources and take median.
- **Risk: Front-running** -- A user could observe a large price movement and deposit/withdraw to profit from the rate lock window. Mitigation: 1% spread covers most short-term volatility. For large deposits, governance review can delay CC minting.
- **Risk: Regulatory classification** -- CC backed by crypto may be classified as a security or money service in some jurisdictions. Mitigation: seek legal counsel before mainnet launch. Phase 1 is testnet only.
- **Risk: Reorg / double-spend** -- A blockchain reorganization could invalidate a confirmed deposit. Mitigation: 6 confirmations for BTC and 12 for ETH provide strong finality. For deposits over 1 BTC equivalent, require 12 BTC confirmations.
- **Assumption**: CoinGecko free tier API is sufficient for MVP volume. If rate-limited, upgrade to Pro tier or switch to another oracle.
- **Assumption**: Application-layer multisig is acceptable for MVP. On-chain smart contract multisig is future work.
- **Assumption**: 100% reserve ratio is non-negotiable. The system never creates unbacked CC.

## Known Gaps and Follow-up Tasks

- Follow-up task: On-chain smart contract multisig (Gnosis Safe or equivalent)
- Follow-up task: Multiple price oracle sources with median aggregation
- Follow-up task: Large deposit governance review threshold
- Follow-up task: Key rotation procedure and documentation
- Follow-up task: Stablecoin (USDC) deposit support
- Follow-up task: Testnet-to-mainnet migration plan with security audit
- Follow-up task: Rate-limited API tier upgrade for price oracle
- Follow-up task: Emergency pause mechanism (governance fast-track vote)

## Failure/Retry Reflection

- Failure mode: Price oracle returns stale data during high volatility, causing rate lock to be unfavorable
- Blind spot: 5-minute cache could mask a 10% price swing in extreme market conditions
- Next action: Reduce cache TTL to 60 seconds during high-volatility periods (detected by price delta > 3% between successive fetches)

## Decision Gates

- **DG1**: HSM provider selection (AWS KMS, HashiCorp Vault, or hardware HSM) -- needs security review
- **DG2**: Multisig signer identity (who are the 3 signers?) -- needs founder decision
- **DG3**: Testnet vs mainnet for Phase 1 -- recommendation: testnet only, mainnet requires security audit
- **DG4**: Legal review of CC-as-backed-token regulatory implications -- must complete before mainnet
