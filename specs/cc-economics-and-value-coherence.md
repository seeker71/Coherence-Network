---
idea_id: coherence-credit
status: partial
source:
  - file: api/app/models/coherence_credit.py
    symbols: [CostVector, ValueVector, ExchangeRate]
  - file: api/app/services/coherence_credit_service.py
    symbols: [exchange rate loading]
requirements:
  - "R1: CC supply is always backed -- `total_cc_outstanding <= treasury_value_usd / exchange_rate` at all times. CC is minte"
  - "R2: Value appreciation through proven impact -- when an idea funded by CC generates measurable usage (downstream usage e"
  - "R3: Users can stake CC into an idea via `POST /api/cc/stake`. If the idea generates value, the staker's CC attribution g"
  - "R4: Staked CC can be unstaked at any time via `POST /api/cc/unstake` with amount-proportional cooldown: instant for < 10"
  - "R5: 1% spread on CC-to-crypto exchange. Transparent, posted in exchange rate response, auditable in the audit ledger. No"
  - "R6: Demand drivers -- CC is required to: (a) publish ideas to marketplace (quality gate deposit, returned if idea achiev"
  - "R7: CC coherence score is continuously computed and published: `treasury_value / (total_cc * exchange_rate)`. Must be >="
  - "R8: `GET /api/cc/supply` returns total minted, total burned, outstanding, and coherence score."
  - "R9: `GET /api/cc/exchange-rate` returns current rate with 5-minute oracle cache TTL, spread percentage, and cache freshn"
  - "R10: `GET /api/cc/staking/{user_id}` returns all staking positions for a user with per-position idea_id, amount, current"
done_when:
  - "GET /api/cc/supply returns total_minted, total_burned, outstanding, coherence_score"
  - "GET /api/cc/exchange-rate returns rate with spread and cache metadata"
  - "POST /api/cc/stake creates a staking position linked to an idea"
  - "POST /api/cc/unstake initiates cooldown with correct tier (instant/<100, 24h/100-1000, 72h/>1000)"
  - "GET /api/cc/staking/{user_id} returns all positions with attribution values"
  - "Coherence score invariant enforced -- minting pauses when score < 1.0"
  - "1% spread applied and visible in exchange rate response"
  - "All tests pass in test_cc_economics.py"
test: "python3 -m pytest api/tests/test_coherence_credit.py -x -q"
constraints:
  - "No unbacked CC may ever exist -- treasury invariant is a hard constraint"
  - "No guaranteed yield on staking -- returns are purely outcome-based"
  - "Exchange spread must be visible in API response, never hidden"
  - "Cooldown tiers are exact: <100 instant, 100-1000 24h, >1000 72h"
---

> **Parent idea**: [coherence-credit](../ideas/coherence-credit.md)
> **Source**: [`api/app/models/coherence_credit.py`](../api/app/models/coherence_credit.py) | [`api/app/services/coherence_credit_service.py`](../api/app/services/coherence_credit_service.py)

# Spec 124: CC Economics and Value Coherence

**Idea**: `cc-value-physics` (sub-idea of `coherence-credit-system`)
**Depends on**: Spec 119 (CC internal currency), Spec 118 (unified SQLite store), Spec 117 (idea hierarchy)
**Integrates with**:
- `coherence_credit_service` (CC unit of account, conversion functions)
- `idea_registry_service` (idea records for staking targets)
- `value_lineage_service` (downstream usage events for value measurement)
- `commit_evidence_service` (implementation evidence for staked ideas)
- `unified_db` (persistence for staking positions, treasury ledger)

## Status: Draft

## Purpose

Spec 119 introduced CC as an internal unit of account. This spec defines the economic model that makes CC trustworthy: full treasury backing, value appreciation through proven impact rather than scarcity mechanics, and transparent staking into ideas with real-outcome returns. Without these invariants, CC is just another token. With them, CC is a unit that represents measurable value created by the network. The system must never allow unbacked CC to exist, must never hide fees, and must never lock users into positions they cannot exit.

## Requirements

- [ ] R1: CC supply is always backed -- `total_cc_outstanding <= treasury_value_usd / exchange_rate` at all times. CC is minted on deposit, burned on withdrawal. No unbacked CC may exist.
- [ ] R2: Value appreciation through proven impact -- when an idea funded by CC generates measurable usage (downstream usage events, fork count, implementation evidence via value_lineage and commit_evidence), the CC attribution for stakers of that idea grows proportionally to proven impact.
- [ ] R3: Users can stake CC into an idea via `POST /api/cc/stake`. If the idea generates value, the staker's CC attribution grows proportionally. If it does not, the stake stays flat. No guaranteed yield.
- [ ] R4: Staked CC can be unstaked at any time via `POST /api/cc/unstake` with amount-proportional cooldown: instant for < 100 CC, 24h for 100-1000 CC, 72h for > 1000 CC. No lock-ups.
- [ ] R5: 1% spread on CC-to-crypto exchange. Transparent, posted in exchange rate response, auditable in the audit ledger. No hidden fees.
- [ ] R6: Demand drivers -- CC is required to: (a) publish ideas to marketplace (quality gate deposit, returned if idea achieves minimum evidence threshold), (b) stake into ideas for attribution, (c) pay for compute resources on the network.
- [ ] R7: CC coherence score is continuously computed and published: `treasury_value / (total_cc * exchange_rate)`. Must be >= 1.0. System pauses all CC minting and exchange operations if coherence score drops below 1.0.
- [ ] R8: `GET /api/cc/supply` returns total minted, total burned, outstanding, and coherence score.
- [ ] R9: `GET /api/cc/exchange-rate` returns current rate with 5-minute oracle cache TTL, spread percentage, and cache freshness timestamp.
- [ ] R10: `GET /api/cc/staking/{user_id}` returns all staking positions for a user with per-position idea_id, amount, current attribution value, stake timestamp, and cooldown status.

## Research Inputs (Required)

- `2026-03-19` - Spec 119 CC internal currency implementation - establishes CC unit of account, CostVector, ValueVector, and exchange rate config that this spec extends
- `2026-03-18` - Spec 116 grounded idea portfolio metrics - provides the measured value signals (usage events, commit evidence, spec costs) that drive staking returns
- `2026-03-18` - Spec 117/118 unified store and idea hierarchy - provides persistence layer and parent/child idea lineage for stake propagation
- `2026-03-20` - CoinGecko API documentation (https://docs.coingecko.com/v3.0.1/reference/introduction) - oracle integration for crypto exchange rate with caching and circuit breaker

## Task Card (Required)

```yaml
goal: Implement CC economics with treasury backing, idea staking, and exchange endpoints
files_allowed:
  - api/app/routers/cc_economics.py
  - api/app/services/cc_economics_service.py
  - api/app/services/cc_treasury_service.py
  - api/app/services/cc_staking_service.py
  - api/app/services/cc_oracle_service.py
  - api/app/models/cc_economics.py
  - api/app/services/unified_models.py
  - api/tests/test_cc_economics.py
  - specs/cc-economics-and-value-coherence.md
done_when:
  - GET /api/cc/supply returns total_minted, total_burned, outstanding, coherence_score
  - GET /api/cc/exchange-rate returns rate with spread and cache metadata
  - POST /api/cc/stake creates a staking position linked to an idea
  - POST /api/cc/unstake initiates cooldown with correct tier (instant/<100, 24h/100-1000, 72h/>1000)
  - GET /api/cc/staking/{user_id} returns all positions with attribution values
  - Coherence score invariant enforced -- minting pauses when score < 1.0
  - 1% spread applied and visible in exchange rate response
  - All tests pass in test_cc_economics.py
commands:
  - python3 -m pytest api/tests/test_cc_economics.py -x -v
  - python3 -m pytest api/tests/test_coherence_credit.py -x -q
constraints:
  - No unbacked CC may ever exist -- treasury invariant is a hard constraint
  - No guaranteed yield on staking -- returns are purely outcome-based
  - Exchange spread must be visible in API response, never hidden
  - Cooldown tiers are exact: <100 instant, 100-1000 24h, >1000 72h
```

## API Contract

### `GET /api/cc/supply`

**Request**: No parameters.

**Response 200**
```json
{
  "total_minted": 150000.0,
  "total_burned": 12000.0,
  "outstanding": 138000.0,
  "treasury_value_usd": 145000.0,
  "exchange_rate": 1.0,
  "coherence_score": 1.0507,
  "coherence_status": "healthy",
  "as_of": "2026-03-20T12:00:00Z"
}
```

**Response 503** (treasury data unavailable)
```json
{ "detail": "Treasury data temporarily unavailable" }
```

### `GET /api/cc/exchange-rate`

**Request**: No parameters.

**Response 200**
```json
{
  "cc_per_usd": 333.33,
  "spread_pct": 1.0,
  "buy_rate": 330.0,
  "sell_rate": 336.66,
  "oracle_source": "coingecko",
  "cached_at": "2026-03-20T11:57:00Z",
  "cache_ttl_seconds": 300,
  "is_stale": false
}
```

**Response 503** (oracle unavailable and no cached value)
```json
{ "detail": "Exchange rate unavailable" }
```

### `POST /api/cc/stake`

**Request**
```json
{
  "user_id": "string",
  "idea_id": "string",
  "amount_cc": 500.0
}
```

**Response 201**
```json
{
  "stake_id": "string",
  "user_id": "string",
  "idea_id": "string",
  "amount_cc": 500.0,
  "attribution_cc": 500.0,
  "staked_at": "2026-03-20T12:00:00Z",
  "status": "active"
}
```

**Response 400** (insufficient balance or CC operations paused)
```json
{ "detail": "Insufficient CC balance" }
```

**Response 404** (idea not found)
```json
{ "detail": "Idea not found" }
```

### `POST /api/cc/unstake`

**Request**
```json
{
  "stake_id": "string",
  "user_id": "string"
}
```

**Response 200**
```json
{
  "stake_id": "string",
  "amount_cc": 500.0,
  "attribution_cc": 620.0,
  "cooldown_hours": 24,
  "available_at": "2026-03-21T12:00:00Z",
  "status": "cooling_down"
}
```

**Response 400** (already unstaking)
```json
{ "detail": "Stake is already in cooldown" }
```

**Response 404** (stake not found)
```json
{ "detail": "Stake not found" }
```

### `GET /api/cc/staking/{user_id}`

**Request**
- `user_id`: string (path)

**Response 200**
```json
{
  "user_id": "string",
  "positions": [
    {
      "stake_id": "string",
      "idea_id": "string",
      "amount_cc": 500.0,
      "attribution_cc": 620.0,
      "staked_at": "2026-03-20T12:00:00Z",
      "status": "active",
      "cooldown_hours": null,
      "available_at": null
    }
  ],
  "total_staked_cc": 500.0,
  "total_attribution_cc": 620.0
}
```

**Response 404** (user not found)
```json
{ "detail": "User not found" }
```

## Data Model

```yaml
CCSupply:
  properties:
    total_minted: { type: float, ge: 0 }
    total_burned: { type: float, ge: 0 }
    outstanding: { type: float, ge: 0 }
    treasury_value_usd: { type: float, ge: 0 }
    exchange_rate: { type: float, gt: 0 }
    coherence_score: { type: float, ge: 0 }
    coherence_status: { type: string, enum: [healthy, warning, paused] }
    as_of: { type: datetime }

CCExchangeRate:
  properties:
    cc_per_usd: { type: float, gt: 0 }
    spread_pct: { type: float, ge: 0 }
    buy_rate: { type: float, gt: 0 }
    sell_rate: { type: float, gt: 0 }
    oracle_source: { type: string }
    cached_at: { type: datetime }
    cache_ttl_seconds: { type: int, gt: 0, default: 300 }
    is_stale: { type: bool }

StakePosition:
  properties:
    stake_id: { type: string, min_length: 1 }
    user_id: { type: string, min_length: 1 }
    idea_id: { type: string, min_length: 1 }
    amount_cc: { type: float, gt: 0 }
    attribution_cc: { type: float, ge: 0 }
    staked_at: { type: datetime }
    status: { type: string, enum: [active, cooling_down, withdrawn] }
    cooldown_hours: { type: "int | None", default: null }
    available_at: { type: "datetime | None", default: null }

StakeRequest:
  properties:
    user_id: { type: string, min_length: 1 }
    idea_id: { type: string, min_length: 1 }
    amount_cc: { type: float, gt: 0 }

UnstakeRequest:
  properties:
    stake_id: { type: string, min_length: 1 }
    user_id: { type: string, min_length: 1 }

UserStakingSummary:
  properties:
    user_id: { type: string }
    positions: { type: "list[StakePosition]" }
    total_staked_cc: { type: float, ge: 0 }
    total_attribution_cc: { type: float, ge: 0 }

TreasuryLedgerEntry (SQLAlchemy):
  table: cc_treasury_ledger
  columns:
    id: { type: string, primary_key: true }
    action: { type: string, enum: [mint, burn, stake, unstake, fee] }
    amount_cc: { type: float }
    user_id: { type: string }
    idea_id: { type: "string | None" }
    treasury_balance_after: { type: float }
    coherence_score_after: { type: float }
    created_at: { type: datetime }

StakePositionRow (SQLAlchemy):
  table: cc_stake_positions
  columns:
    stake_id: { type: string, primary_key: true }
    user_id: { type: string, index: true }
    idea_id: { type: string, index: true }
    amount_cc: { type: float }
    attribution_cc: { type: float }
    staked_at: { type: datetime }
    status: { type: string }
    cooldown_until: { type: "datetime | None" }
```

## Files to Create/Modify

- `api/app/models/cc_economics.py` - Pydantic models: CCSupply, CCExchangeRate, StakePosition, StakeRequest, UnstakeRequest, UserStakingSummary
- `api/app/services/cc_economics_service.py` - Orchestrator: supply calculation, coherence score check, staking coordination
- `api/app/services/cc_treasury_service.py` - Treasury ledger: mint, burn, balance tracking, coherence score invariant enforcement
- `api/app/services/cc_staking_service.py` - Staking logic: create position, unstake with cooldown tiers, attribution calculation from value_lineage
- `api/app/services/cc_oracle_service.py` - CoinGecko oracle: cached rate fetch, 5-min TTL, stale detection
- `api/app/routers/cc_economics.py` - FastAPI router: GET /api/cc/supply, GET /api/cc/exchange-rate, POST /api/cc/stake, POST /api/cc/unstake, GET /api/cc/staking/{user_id}
- `api/app/services/unified_models.py` - Add TreasuryLedgerEntry and StakePositionRow SQLAlchemy models
- `api/tests/test_cc_economics.py` - Tests covering all requirements

## Acceptance Tests

- `api/tests/test_cc_economics.py::test_supply_coherence_score_above_one`
- `api/tests/test_cc_economics.py::test_mint_on_deposit_burn_on_withdrawal`
- `api/tests/test_cc_economics.py::test_no_mint_when_coherence_below_one`
- `api/tests/test_cc_economics.py::test_stake_into_idea_creates_position`
- `api/tests/test_cc_economics.py::test_stake_insufficient_balance_rejected`
- `api/tests/test_cc_economics.py::test_unstake_cooldown_instant_under_100`
- `api/tests/test_cc_economics.py::test_unstake_cooldown_24h_100_to_1000`
- `api/tests/test_cc_economics.py::test_unstake_cooldown_72h_over_1000`
- `api/tests/test_cc_economics.py::test_unstake_already_cooling_rejected`
- `api/tests/test_cc_economics.py::test_attribution_grows_with_usage_events`
- `api/tests/test_cc_economics.py::test_attribution_flat_without_usage`
- `api/tests/test_cc_economics.py::test_exchange_rate_includes_spread`
- `api/tests/test_cc_economics.py::test_exchange_rate_cached_5min`
- `api/tests/test_cc_economics.py::test_exchange_rate_stale_detection`
- `api/tests/test_cc_economics.py::test_quality_gate_deposit_returned_on_evidence`
- `api/tests/test_cc_economics.py::test_quality_gate_deposit_retained_without_evidence`
- `api/tests/test_cc_economics.py::test_user_staking_summary_aggregation`
- `api/tests/test_cc_economics.py::test_treasury_ledger_audit_trail`

## Concurrency Behavior

- **Read operations** (supply, exchange rate, staking positions): Safe for concurrent access; no locking required.
- **Write operations** (stake, unstake, mint, burn): Serialized per-user via database row-level locking on user balance. Treasury balance updates use optimistic locking with coherence score recheck after write.
- **Coherence score check**: Computed at read time from treasury ledger aggregates. Eventual consistency acceptable within 1-second window.

## Verification

```bash
python3 -m pytest api/tests/test_cc_economics.py -x -v
python3 -m pytest api/tests/test_coherence_credit.py -x -q
python3 scripts/validate_spec_quality.py specs/cc-economics-and-value-coherence.md
```

## Out of Scope

- Crypto wallet integration (handled by separate wallet spec)
- CC governance voting mechanics
- Multi-currency treasury (USD only for Phase 1)
- Automated market maker or liquidity pools
- UI for staking interface (web spec separate)
- Epoch transition governance policy (follow-up from Spec 119)

## Risks and Assumptions

- **Risk**: Oracle downtime could prevent exchange rate updates. Mitigation: 5-minute cache means brief outages are invisible; extended outages freeze rate at last known-good value (see Spec 125 circuit breaker).
- **Risk**: Floating-point precision in treasury accounting. Mitigation: all CC amounts rounded to 6 decimal places; ledger entries are append-only so balance is always recomputable from history.
- **Assumption**: CoinGecko free tier rate limits (10-30 calls/min) are sufficient with 5-minute caching. If rate-limited, the cache handles it gracefully.
- **Assumption**: Value lineage usage events (from Spec 116) provide sufficient signal to compute meaningful attribution growth. If usage data is sparse, attribution will be flat -- which is the correct behavior (no fabricated returns).
- **Risk**: Cooldown tiers could be gamed by splitting large unstakes into sub-100 CC chunks. Mitigation: cooldown applies per-position, not per-transaction. A 500 CC position unstakes with 24h cooldown regardless of partial withdrawal attempts.

## Known Gaps and Follow-up Tasks

- Follow-up task: Spec 125 defines oracle circuit breaker and coherence degradation response (cross-referenced)
- Follow-up task: Multi-currency treasury support (ETH, SOL alongside USD)
- Follow-up task: Attribution calculation formula tuning based on real usage data
- Follow-up task: Rate limiting on stake/unstake endpoints to prevent abuse
- Follow-up task: CC balance snapshot for point-in-time audits

## Failure and Retry Behavior

- **Oracle timeout**: Return cached rate if available (up to 1 hour stale); return 503 if no cached rate exists. Retry with exponential backoff (1s, 2s, 4s, max 30s).
- **Treasury DB unavailable**: Supply endpoint returns 503. Stake/unstake return 503. Client should retry with exponential backoff.
- **Coherence score violation**: Minting and exchange operations pause immediately. Existing stakes and reads continue. System logs violation to audit ledger with full context.
- **Invalid stake amount**: Return 400 with descriptive message. No retry needed.
- **Concurrent balance conflict**: Retry treasury write up to 3 times with coherence recheck. If still conflicting, return 409.

## Decision Gates

- Treasury backing ratio: is 1.0 the correct minimum, or should there be a buffer (e.g., 1.05)? Current spec uses 1.0 exact.
- Attribution growth formula: linear proportional to usage events, or diminishing returns? Current spec uses linear. May need tuning after real data.
- Quality gate deposit amount: not specified in this spec. Needs product decision before implementation.
