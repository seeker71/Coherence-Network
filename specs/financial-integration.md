---
id: financial-integration
idea_id: financial-integration-fiat-bridge
status: draft
priority: high
source:
  - file: api/app/services/cc_economics_service.py
    symbols: [treasury_status, exchange_rate]
  - file: api/app/services/cc_exchange_adapter.py
    symbols: [swap, settlement]
  - file: api/app/routers/cc_exchange.py
    symbols: [swap_cc, get_rate, withdrawal]
requirements:
  - "CC <> USDC exchange via Base L2 (using x402 facilitator infrastructure)"
  - "Treasury backing: every CC in circulation backed by real value (Arweave-stored proof)"
  - "Exchange rate computed from treasury reserves / outstanding CC supply"
  - "Fiat on-ramp via USDC (Coinbase, MoonPay, or similar)"
  - "Fiat off-ramp via USDC to bank transfer"
  - "KYC for fiat conversion above threshold (regulatory compliance)"
  - "Tax reporting API for contributors (annual CC earnings summary)"
  - "Treasury audit trail on-chain (all mint/burn events verifiable)"
done_when:
  - "Contributor can convert CC to USDC and withdraw to bank"
  - "Treasury reserves verifiable on-chain"
  - "Exchange rate publicly queryable and matches treasury math"
  - "KYC integration functional for fiat conversion"
test: "python3 -m pytest api/tests/test_financial_integration.py -x -v"
constraints:
  - "No money transmitter license required for initial launch (CC as utility token, not security)"
  - "All treasury operations append-only and verifiable"
  - "Exchange rate cannot be manually overridden — computed from formula only"
---

> **Parent idea**: [financial-integration-fiat-bridge](../ideas/financial-integration-fiat-bridge.md)
> **Source**: [`api/app/services/cc_economics_service.py`](../api/app/services/cc_economics_service.py) | [`api/app/services/cc_exchange_adapter.py`](../api/app/services/cc_exchange_adapter.py) | [`api/app/routers/cc_exchange.py`](../api/app/routers/cc_exchange.py)

# Spec: Financial Integration -- CC Fiat Bridge

## Purpose

Contributors earn CC by creating digital assets that others read. Today, CC has no exit to the real economy -- a contributor cannot pay rent with CC. This spec builds the bridge: CC converts to USDC on Base L2, USDC converts to fiat via an off-ramp partner, and fiat lands in a bank account. The reverse path (fiat to USDC to CC) lets new contributors buy into the ecosystem. Without this bridge, CC is play money. With it, CC is income.

The bridge must be trustworthy: every CC is backed by treasury reserves, the exchange rate is a formula (not a knob), treasury operations are on-chain and auditable, and fiat conversion above thresholds requires KYC for regulatory compliance. Contributors must also be able to generate tax documents for their CC earnings.

## Requirements

- [ ] **R1**: CC to USDC exchange via Base L2. Contributors submit a swap request (`POST /api/cc/exchange/swap`). The system burns the specified CC amount, computes the USDC equivalent at the current exchange rate minus spread, and initiates a USDC transfer on Base L2 to the contributor's wallet address. The x402 facilitator infrastructure handles the on-chain settlement.
- [ ] **R2**: Treasury backing with Arweave proof. The treasury maintains a reserve of USDC on Base L2. The total USDC reserve must always be >= total CC outstanding * exchange rate. A proof-of-reserves snapshot is published to Arweave weekly (coordinated with the verification framework spec). The snapshot includes: reserve USDC balance, total CC outstanding, exchange rate, and the Base L2 contract address for independent verification.
- [ ] **R3**: Exchange rate computed from formula only. `rate = treasury_reserves_usdc / total_cc_outstanding`. No manual override. Rate recomputed every 5 minutes from on-chain treasury balance and CC supply ledger. Published at `GET /api/cc/exchange/rate`. The formula, inputs, and output are all visible in the response.
- [ ] **R4**: Fiat on-ramp. New contributors purchase USDC via an on-ramp partner (Coinbase Onramp, MoonPay, or Transak). The USDC arrives at the platform's Base L2 treasury address. The system mints CC at the current exchange rate and credits the contributor's balance. The on-ramp flow is initiated via `POST /api/cc/exchange/onramp` which returns a redirect URL to the partner's hosted checkout.
- [ ] **R5**: Fiat off-ramp. Contributors convert CC to USDC (R1), then request fiat withdrawal via `POST /api/cc/exchange/withdraw`. The system initiates a USDC-to-fiat transfer through the off-ramp partner. Withdrawal to bank account via ACH (US), SEPA (EU), or wire (international). Minimum withdrawal: $10 equivalent. Processing time: 1-3 business days.
- [ ] **R6**: KYC for fiat conversion above threshold. Any fiat conversion (on-ramp or off-ramp) above $2,000 cumulative per rolling 30-day period requires KYC verification. KYC is handled by an external provider (Jumio, Onfido, or Persona). The contributor completes KYC once; the verification status is stored and reused. Below-threshold CC-to-USDC swaps (crypto-to-crypto) do not require KYC.
- [ ] **R7**: Tax reporting API. `GET /api/cc/exchange/tax-report/{contributor_id}?year=2026` returns an annual earnings summary: total CC earned, total CC converted, total fiat received, dates of each conversion, and applicable exchange rates. The response is downloadable as CSV. The platform does not provide tax advice -- it provides data.
- [ ] **R8**: Treasury audit trail on-chain. Every mint (CC creation from USDC deposit) and burn (CC destruction from USDC withdrawal) is recorded as a transaction on Base L2. The transaction includes: CC amount, USDC amount, exchange rate at time of transaction, contributor wallet address (hashed for privacy), and timestamp. The audit trail is queryable via `GET /api/cc/exchange/audit-trail`.

## Research Inputs

- `2026-04-14` - Base L2 documentation (https://docs.base.org) -- EVM-compatible L2 by Coinbase, low fees (~$0.01/tx), USDC native support.
- `2026-04-14` - x402 micropayment protocol (https://www.x402.org) -- HTTP-native payments, facilitator model for settlement. Already integrated in Story Protocol spec.
- `2026-04-14` - Coinbase Onramp SDK (https://docs.cdp.coinbase.com/onramp) -- hosted checkout for fiat-to-crypto, supports ACH and card.
- `2026-04-14` - Existing CC economics spec (`specs/cc-economics-and-value-coherence.md`) -- treasury model, supply tracking, coherence score that this spec extends with real USDC backing.
- `2026-04-14` - Persona KYC API (https://docs.withpersona.com) -- identity verification with global coverage, API-first integration.

## Treasury Model

```
                    TREASURY RESERVE (Base L2)
                    ==========================

  Contributor deposits          Platform
  fiat via on-ramp              treasury wallet
       |                        (USDC on Base L2)
       v                             |
  On-ramp partner        +-----------+-----------+
  (Coinbase/MoonPay)     |                       |
       |                 |   USDC Reserve Pool    |
       v                 |                       |
  USDC arrives at        |   Backing invariant:  |
  treasury wallet        |   reserve >= CC * rate |
       |                 |                       |
       v                 +-----------+-----------+
  Mint CC at rate              |
  Credit contributor           |   Weekly Arweave
       |                       |   proof-of-reserves
       v                       v
  CC in circulation      Arweave snapshot:
                         {reserve, outstanding, rate}


  Contributor withdraws
  CC to fiat
       |
       v
  Burn CC at rate
  Compute USDC amount
       |
       v
  Transfer USDC from
  treasury to contributor
  wallet on Base L2
       |
       v
  Off-ramp partner
  converts USDC to fiat
       |
       v
  Bank deposit
  (ACH/SEPA/wire)
```

The treasury is a single USDC wallet on Base L2. All CC in circulation is backed by the USDC in this wallet. The exchange rate is always `reserve / outstanding`. If reserve grows faster than CC supply (e.g., from platform revenue), the exchange rate increases -- CC holders benefit. If CC supply grows without matching reserve growth (which should never happen due to the minting constraint), the rate would decrease -- but the system prevents this by only minting CC when USDC is deposited.

## Exchange Mechanism

### CC to USDC Flow

```
Contributor                  Platform API                  Base L2
===========                  ============                  =======

POST /api/cc/exchange/swap
  { cc_amount: 100,
    wallet: "0xABC..." }
         |
         v
    Validate balance -------> Check CC balance >= 100
    Compute USDC -----------> usdc = 100 * rate * (1 - spread)
    Burn CC ----------------> Deduct 100 CC from balance
    Initiate transfer ------> USDC.transfer(0xABC, usdc) -----> on-chain tx
    Record audit -----------> mint/burn event on-chain
         |
         v
    Return swap receipt
    { tx_hash, usdc_amount,
      rate_used, spread }
```

### USDC to CC Flow (On-ramp)

```
Contributor                  Platform API              On-ramp Partner
===========                  ============              ===============

POST /api/cc/exchange/onramp
  { fiat_amount: 50,
    currency: "USD" }
         |
         v
    Check KYC status ------> If cumulative > $2000,
                              require KYC completion
         |
         v
    Generate checkout URL --> Partner hosted page -------> Contributor
         |                                                 completes
         v                                                 payment
    Webhook callback <------- Partner confirms USDC ------/
         |                    deposited to treasury
         v
    Verify USDC received ---> Check treasury balance
    Compute CC amount ------> cc = usdc_received * rate
    Mint CC ----------------> Credit contributor balance
    Record audit -----------> mint event on-chain
         |
         v
    Notify contributor
    { cc_credited, rate_used }
```

## Rate Computation

**Formula**: `rate_cc_per_usdc = total_cc_outstanding / treasury_reserves_usdc`

Inverted for display: `rate_usdc_per_cc = treasury_reserves_usdc / total_cc_outstanding`

**Update frequency**: Recomputed every 5 minutes from:
- `treasury_reserves_usdc`: queried from Base L2 treasury wallet balance
- `total_cc_outstanding`: computed from CC supply ledger (minted - burned)

**Spread**: 1% on swaps (buy and sell). Spread CC is burned (deflationary), not retained by platform.

**Staleness**: If the rate has not been updated in 15 minutes, API response includes `"is_stale": true`. Swaps are blocked if rate is stale for > 30 minutes.

## API Contract

### `GET /api/cc/exchange/rate`

Returns current exchange rate with full transparency on computation.

**Response 200**
```json
{
  "rate_usdc_per_cc": 0.0033,
  "rate_cc_per_usdc": 303.03,
  "spread_pct": 1.0,
  "buy_rate_cc_per_usdc": 300.0,
  "sell_rate_usdc_per_cc": 0.003267,
  "treasury_reserves_usdc": 50000.00,
  "total_cc_outstanding": 15000000.0,
  "formula": "treasury_reserves_usdc / total_cc_outstanding",
  "computed_at": "2026-04-14T12:00:00Z",
  "is_stale": false
}
```

### `POST /api/cc/exchange/swap`

Swap CC for USDC.

**Request**
```json
{
  "contributor_id": "string",
  "cc_amount": 1000.0,
  "destination_wallet": "0xABC123..."
}
```

**Response 201**
```json
{
  "swap_id": "string",
  "contributor_id": "string",
  "cc_burned": 1000.0,
  "usdc_amount": 3.267,
  "rate_used": 0.003267,
  "spread_applied": 1.0,
  "destination_wallet": "0xABC123...",
  "base_l2_tx_hash": "0xDEF456...",
  "status": "pending",
  "created_at": "2026-04-14T12:01:00Z"
}
```

**Response 400** (insufficient balance)
```json
{ "detail": "Insufficient CC balance. Available: 500.0, requested: 1000.0" }
```

**Response 503** (rate stale or treasury unavailable)
```json
{ "detail": "Exchange rate stale. Swaps temporarily suspended." }
```

### `POST /api/cc/exchange/onramp`

Initiate fiat-to-CC purchase via on-ramp partner.

**Request**
```json
{
  "contributor_id": "string",
  "fiat_amount": 50.00,
  "fiat_currency": "USD"
}
```

**Response 200**
```json
{
  "session_id": "string",
  "checkout_url": "https://pay.coinbase.com/...",
  "fiat_amount": 50.00,
  "fiat_currency": "USD",
  "estimated_cc": 15151.5,
  "rate_used": 303.03,
  "kyc_required": false,
  "expires_at": "2026-04-14T13:00:00Z"
}
```

**Response 403** (KYC required)
```json
{
  "detail": "KYC verification required for cumulative fiat conversion above $2000",
  "kyc_url": "https://api.coherencycoin.com/api/cc/exchange/kyc/start",
  "cumulative_30d": 2150.00,
  "threshold": 2000.00
}
```

### `POST /api/cc/exchange/withdraw`

Convert USDC to fiat and withdraw to bank.

**Request**
```json
{
  "contributor_id": "string",
  "usdc_amount": 50.00,
  "bank_details": {
    "method": "ach",
    "account_last4": "1234",
    "routing_number_last4": "5678"
  }
}
```

**Response 201**
```json
{
  "withdrawal_id": "string",
  "contributor_id": "string",
  "usdc_amount": 50.00,
  "estimated_fiat": 49.50,
  "fiat_currency": "USD",
  "method": "ach",
  "status": "processing",
  "estimated_arrival": "2026-04-17",
  "created_at": "2026-04-14T12:05:00Z"
}
```

**Response 400** (below minimum)
```json
{ "detail": "Minimum withdrawal is $10.00. Requested: $5.00" }
```

**Response 403** (KYC required)
```json
{ "detail": "KYC verification required for fiat withdrawal" }
```

### `GET /api/cc/exchange/tax-report/{contributor_id}`

Annual earnings summary for tax purposes.

**Query parameters**:
- `year` (required): integer, e.g., 2026
- `format` (optional): `json` (default) or `csv`

**Response 200**
```json
{
  "contributor_id": "string",
  "tax_year": 2026,
  "summary": {
    "total_cc_earned": 45000.0,
    "total_cc_converted": 12000.0,
    "total_usdc_received": 39.60,
    "total_fiat_withdrawn": 38.50,
    "conversion_count": 8
  },
  "conversions": [
    {
      "date": "2026-03-15",
      "cc_amount": 1500.0,
      "usdc_amount": 4.95,
      "rate_used": 0.0033,
      "type": "cc_to_usdc"
    }
  ],
  "disclaimer": "This is a data export, not tax advice. Consult a tax professional.",
  "generated_at": "2026-04-14T12:10:00Z"
}
```

### `GET /api/cc/exchange/audit-trail`

On-chain treasury audit trail.

**Query parameters**:
- `from_date` (optional): ISO 8601 date
- `to_date` (optional): ISO 8601 date
- `event_type` (optional): `mint`, `burn`, or `all` (default)
- `limit` (optional): integer, default 100, max 1000

**Response 200**
```json
{
  "events": [
    {
      "event_id": "string",
      "type": "burn",
      "cc_amount": 1000.0,
      "usdc_amount": 3.267,
      "rate_at_time": 0.003267,
      "base_l2_tx_hash": "0xDEF456...",
      "contributor_hash": "sha256-of-contributor-id",
      "timestamp": "2026-04-14T12:01:00Z"
    }
  ],
  "total_events": 342,
  "total_minted_cc": 15000000.0,
  "total_burned_cc": 3000000.0,
  "net_outstanding_cc": 12000000.0
}
```

## KYC Integration

```
Contributor                  Platform API              KYC Provider
===========                  ============              ============

Attempts fiat conversion
above $2000/30d threshold
         |
         v
POST /api/cc/exchange/kyc/start
  { contributor_id }
         |
         v
    Create inquiry ---------> POST /api/v1/inquiries ------> Provider
         |                                                    creates
         v                                                    session
    Return session URL <------ Session URL <-----------------/
         |
         v
    Contributor completes ---> ID scan + selfie + liveness -> Provider
    verification on                                           verifies
    provider hosted page                                      identity
         |                                                       |
         v                                                       v
    Webhook callback <-------- POST /webhooks/kyc <---------- Provider
         |                     { status: approved,              sends
         v                       contributor_id }               result
    Store KYC status -------> kyc_verifications table
    Unlock fiat conversion     { contributor_id,
                                 status: approved,
                                 verified_at,
                                 provider_ref,
                                 expires_at }
```

**Thresholds**:
- Below $2,000 cumulative 30-day fiat conversion: no KYC required
- $2,000 - $10,000: Basic KYC (government ID + selfie)
- Above $10,000: Enhanced KYC (government ID + selfie + proof of address)

**Data handling**:
- The platform stores only: contributor_id, KYC status (approved/denied/pending), verification date, expiry date, and provider reference ID
- The platform does NOT store: ID images, personal details, address -- these remain with the KYC provider
- KYC verification expires after 12 months; re-verification required

## Data Model

```yaml
SwapTransaction:
  table: cc_swap_transactions
  columns:
    swap_id: { type: string, primary_key: true }
    contributor_id: { type: string, index: true }
    direction: { type: string, enum: [cc_to_usdc, usdc_to_cc] }
    cc_amount: { type: float, gt: 0 }
    usdc_amount: { type: float, gt: 0 }
    rate_used: { type: float, gt: 0 }
    spread_pct: { type: float, ge: 0 }
    destination_wallet: { type: "string | None" }
    base_l2_tx_hash: { type: "string | None" }
    status: { type: string, enum: [pending, confirmed, failed] }
    created_at: { type: datetime }
    confirmed_at: { type: "datetime | None" }

FiatWithdrawal:
  table: cc_fiat_withdrawals
  columns:
    withdrawal_id: { type: string, primary_key: true }
    contributor_id: { type: string, index: true }
    usdc_amount: { type: float, gt: 0 }
    fiat_amount: { type: float, gt: 0 }
    fiat_currency: { type: string, default: "USD" }
    method: { type: string, enum: [ach, sepa, wire] }
    status: { type: string, enum: [processing, completed, failed] }
    partner_ref: { type: "string | None" }
    created_at: { type: datetime }
    completed_at: { type: "datetime | None" }

OnrampSession:
  table: cc_onramp_sessions
  columns:
    session_id: { type: string, primary_key: true }
    contributor_id: { type: string, index: true }
    fiat_amount: { type: float, gt: 0 }
    fiat_currency: { type: string }
    estimated_cc: { type: float, gt: 0 }
    rate_used: { type: float, gt: 0 }
    checkout_url: { type: string }
    status: { type: string, enum: [pending, completed, expired, failed] }
    partner_ref: { type: "string | None" }
    created_at: { type: datetime }
    completed_at: { type: "datetime | None" }
    expires_at: { type: datetime }

KYCVerification:
  table: cc_kyc_verifications
  columns:
    id: { type: string, primary_key: true }
    contributor_id: { type: string, unique: true, index: true }
    status: { type: string, enum: [pending, approved, denied, expired] }
    tier: { type: string, enum: [basic, enhanced] }
    provider_ref: { type: string }
    verified_at: { type: "datetime | None" }
    expires_at: { type: "datetime | None" }
    created_at: { type: datetime }

TreasuryAuditEvent:
  table: cc_treasury_audit
  columns:
    event_id: { type: string, primary_key: true }
    type: { type: string, enum: [mint, burn] }
    cc_amount: { type: float }
    usdc_amount: { type: float }
    rate_at_time: { type: float }
    base_l2_tx_hash: { type: string }
    contributor_hash: { type: string }
    treasury_balance_after: { type: float }
    cc_outstanding_after: { type: float }
    timestamp: { type: datetime }
  constraints:
    - append_only: true
```

## Regulatory Considerations

- **Token classification**: CC is a utility token -- it grants access to platform features (publishing, staking, compute). It is not marketed as an investment, does not promise returns, and has no fixed supply cap designed to create scarcity. The exchange rate is derived from real treasury backing, not market speculation.
- **Money transmission**: The platform facilitates CC-to-USDC swaps using the contributor's own wallet. USDC-to-fiat conversion is handled by a licensed off-ramp partner. The platform does not hold fiat, does not transmit fiat, and does not custody USDC on behalf of users (treasury USDC is platform-owned backing for CC).
- **KYC/AML**: Fiat conversion above thresholds triggers KYC via a licensed provider. The platform enforces thresholds but delegates identity verification to the provider.
- **Jurisdictional differences**: Some jurisdictions may classify CC differently. The platform should geo-restrict fiat features in jurisdictions where utility token exchange is prohibited. The initial launch targets US and EU markets with clear regulatory frameworks.
- **Tax obligations**: The platform provides data (tax report endpoint) but does not advise on or calculate tax liability. Contributors are responsible for their own tax reporting.

## Files to Create/Modify

- `api/app/services/cc_exchange_adapter.py` -- Core exchange logic: swap execution, rate computation from on-chain data, USDC transfer initiation via Base L2
- `api/app/services/cc_economics_service.py` -- Extend existing service: add treasury_status() for real-time reserve query, update exchange_rate() to use on-chain data
- `api/app/services/cc_kyc_service.py` -- KYC integration: session creation, webhook handling, status checking, threshold enforcement
- `api/app/services/cc_tax_service.py` -- Tax report generation: annual aggregation, CSV export
- `api/app/routers/cc_exchange.py` -- FastAPI router: swap, onramp, withdraw, rate, tax-report, audit-trail, kyc endpoints
- `api/app/models/cc_exchange.py` -- Pydantic models: SwapRequest, SwapResponse, OnrampRequest, WithdrawRequest, TaxReport, AuditEvent
- `api/tests/test_financial_integration.py` -- Test suite for all requirements

## Acceptance Tests

- `api/tests/test_financial_integration.py::test_swap_cc_to_usdc_burns_cc` -- CC balance decremented, USDC transfer initiated
- `api/tests/test_financial_integration.py::test_swap_insufficient_balance_rejected` -- 400 when CC balance too low
- `api/tests/test_financial_integration.py::test_swap_stale_rate_blocked` -- 503 when rate older than 30 minutes
- `api/tests/test_financial_integration.py::test_rate_matches_treasury_formula` -- rate = reserves / outstanding, verified
- `api/tests/test_financial_integration.py::test_rate_no_manual_override` -- no API or config path to set rate manually
- `api/tests/test_financial_integration.py::test_spread_applied_correctly` -- 1% spread deducted from swap amount
- `api/tests/test_financial_integration.py::test_onramp_returns_checkout_url` -- valid partner URL returned
- `api/tests/test_financial_integration.py::test_onramp_mints_cc_on_callback` -- CC credited after webhook confirmation
- `api/tests/test_financial_integration.py::test_withdrawal_minimum_enforced` -- 400 when below $10
- `api/tests/test_financial_integration.py::test_withdrawal_kyc_required_above_threshold` -- 403 when cumulative > $2000 without KYC
- `api/tests/test_financial_integration.py::test_kyc_below_threshold_not_required` -- swap proceeds without KYC under $2000
- `api/tests/test_financial_integration.py::test_kyc_status_stored_not_pii` -- only status and provider ref stored, no PII
- `api/tests/test_financial_integration.py::test_tax_report_annual_summary` -- correct totals for a year of conversions
- `api/tests/test_financial_integration.py::test_tax_report_csv_format` -- CSV download matches JSON data
- `api/tests/test_financial_integration.py::test_audit_trail_append_only` -- events cannot be modified or deleted
- `api/tests/test_financial_integration.py::test_audit_trail_matches_swap_history` -- every swap has corresponding audit event
- `api/tests/test_financial_integration.py::test_treasury_backing_invariant` -- reserve >= outstanding * rate after every operation

## Verification

```bash
python3 -m pytest api/tests/test_financial_integration.py -x -v
python3 scripts/validate_spec_quality.py specs/financial-integration.md
```

## Phased Implementation

**Phase 1 -- CC to USDC exchange (weeks 1-2)**:
- Implement `cc_exchange_adapter.py` with swap logic
- Implement rate computation from treasury formula
- Create `POST /api/cc/exchange/swap` and `GET /api/cc/exchange/rate`
- Create swap_transactions and treasury_audit tables
- Acceptance: contributor can swap CC to USDC, rate matches formula, audit trail recorded

**Phase 2 -- Treasury verification (week 3)**:
- Extend treasury_status() to query Base L2 wallet balance
- Implement proof-of-reserves snapshot (coordinate with public-verification-framework spec)
- Implement `GET /api/cc/exchange/audit-trail`
- Acceptance: treasury reserves queryable on-chain, audit trail complete

**Phase 3 -- Fiat bridge (weeks 4-5)**:
- Integrate on-ramp partner SDK (Coinbase Onramp or MoonPay)
- Implement `POST /api/cc/exchange/onramp` with checkout URL generation
- Implement webhook handler for on-ramp completion
- Integrate off-ramp partner for USDC-to-fiat
- Implement `POST /api/cc/exchange/withdraw`
- Acceptance: end-to-end flow from fiat to CC and CC to fiat bank deposit

**Phase 4 -- KYC integration (week 6)**:
- Integrate KYC provider (Persona or Jumio)
- Implement threshold checking (cumulative 30-day tracking)
- Implement `POST /api/cc/exchange/kyc/start` and webhook handler
- Create kyc_verifications table
- Acceptance: KYC enforced above $2000, verification status persisted

**Phase 5 -- Tax reporting (week 7)**:
- Implement `cc_tax_service.py` with annual aggregation
- Implement `GET /api/cc/exchange/tax-report/{contributor_id}` with JSON and CSV
- Acceptance: accurate annual summary, CSV downloadable

## Concurrency Behavior

- **Rate computation**: Cached for 5 minutes. Concurrent reads serve cached value. Single writer updates cache on expiry.
- **Swap execution**: Serialized per-contributor via database row-level lock on CC balance. Two concurrent swaps from the same contributor are processed sequentially. Swaps from different contributors are fully parallel.
- **Treasury balance updates**: Optimistic locking with retry. After CC burn/mint, the treasury audit event records the balance-after. If a concurrent operation changed the balance, retry with fresh balance.
- **KYC threshold check**: Read cumulative 30-day total at swap time. Race condition (two swaps simultaneously crossing threshold) is acceptable -- worst case, one extra sub-threshold swap goes through before KYC kicks in.

## Failure and Retry Behavior

- **Base L2 transaction failure**: Swap remains in `pending` status. Background job retries up to 3 times with exponential backoff. If all retries fail, CC is re-credited to contributor balance and swap marked `failed`.
- **On-ramp webhook missed**: Polling job checks on-ramp partner for session completion every 15 minutes. If USDC detected at treasury address with matching session reference, CC is minted.
- **Off-ramp partner unavailable**: Withdrawal remains in `processing` status. Alert logged. Manual intervention required after 48 hours of no progress.
- **KYC provider timeout**: Return 503 to contributor. KYC session remains in `pending` status. Contributor can retry.
- **Rate computation failure**: Serve last known rate with `is_stale: true`. Block swaps after 30 minutes of staleness.

## Out of Scope

- Multi-currency treasury (USDC only for Phase 1; ETH, SOL support is a follow-up)
- Automated market maker or liquidity pools (rate is formula-based, not market-based)
- Contributor wallet custody (contributors manage their own wallets)
- Credit card direct purchase of CC (must go through USDC intermediary)
- Recurring/scheduled swaps or withdrawals
- Tax withholding or 1099 generation (data export only)
- CC-to-CC transfers between contributors (out of scope for financial bridge)

## Risks and Assumptions

- **Risk**: Off-ramp partner changes terms or discontinues service. Mitigation: adapter pattern in `cc_exchange_adapter.py` allows swapping the off-ramp provider without changing the API contract.
- **Risk**: Regulatory classification of CC changes. Mitigation: utility token positioning with no yield promises, no supply manipulation, and transparent treasury. Legal review required before launch.
- **Risk**: Treasury USDC on Base L2 is a single point of failure. Mitigation: multi-sig wallet controlled by multiple keyholders. Key rotation on a quarterly schedule.
- **Assumption**: Base L2 transaction fees remain below $0.05 per swap, making small CC-to-USDC conversions economically viable.
- **Assumption**: On-ramp partner supports at least USD and EUR fiat currencies at launch.
- **Risk**: Exchange rate volatility if treasury reserves fluctuate. Mitigation: rate is recomputed frequently (5 min) and the formula ensures CC is always fully backed. Rate changes are gradual because treasury changes are gradual.

## Decision Gates

- **On-ramp partner selection**: Coinbase Onramp vs MoonPay vs Transak. Decision needed before Phase 3 starts. Evaluation criteria: supported currencies, fees, geographic coverage, API quality.
- **KYC provider selection**: Persona vs Jumio vs Onfido. Decision needed before Phase 4. Evaluation criteria: price per verification, global ID coverage, API integration complexity, data retention policies.
- **KYC threshold**: $2,000/30-day is the initial proposal. May need adjustment based on legal counsel for specific jurisdictions.
- **Spread destination**: Current spec burns spread CC (deflationary). Alternative: route spread to platform operations fund. Decision impacts tokenomics.

## Known Gaps and Follow-up Tasks

- None yet — follow-up gaps will be recorded here as implementation proceeds.
