# Economic Model

## Core Principles

### 1. Pay for Value Created, Not Time Spent

Traditional systems pay for hours worked. Coherence Network pays for value generated, weighted by quality.

**Example**:
- Alice works 10 hours, creates $10,000 value → Earns based on value
- Bob works 10 hours, creates $0 value → Earns nothing

### 2. Quality Multiplies Earnings

Higher coherence = higher multiplier on your share.

**Formula**: `payout = (cost × coherence_multiplier) / total_weighted_cost × value`

**Example**:
- Alice: $100 cost, 0.9 coherence → $140 weighted cost (1.4x)
- Bob: $100 cost, 0.5 coherence → $100 weighted cost (1.0x)
- Total weighted: $240
- $1000 distributed: Alice gets $583, Bob gets $417

**Alice earns 40% more despite same cost!**

### 3. Cheapest Hosting Wins

Node operators compete on price. Network always uses cheapest.

**Result**: 90%+ savings vs AWS, operators still profit.

### 4. Network Self-Sustains

Small fees fund operations, excess distributed to contributors.

**Fees**:
- Distribution: 2%
- Node markup: 10%
- API usage: $0.001/request

## Contribution Tracking

### What Gets Tracked

**Every contribution records**:
- **Cost**: Labor + tools + compute
- **Coherence**: Quality score (0.0 to 1.0)
- **Timestamp**: When it happened
- **Metadata**: What changed

**Stored immutably** in event ledger (can't be changed retroactively).

### Cost Calculation

**Human Labor**:
```
Hours × Hourly Rate = Labor Cost
2 hours × $150/hr = $300
```

**Tool Usage** (LLM APIs):
```
(Input Tokens × Input Rate) + (Output Tokens × Output Rate) = Tool Cost
(1000 × $0.000003) + (500 × $0.000015) = $0.0105
```

**Compute** (local machine):
```
(Hours × Power(kW) × Electricity Rate) + (Hardware Cost / Lifetime × Hours)
(2 × 0.14 × $0.15) + ($7199 / 10000 × 2) = $0.042 + $1.44 = $1.48
```

**Total**: $300 + $0.01 + $1.48 = **$301.49**

## Coherence Scoring

### Formula

```
coherence = (
    0.20 × code_quality +
    0.20 × architecture_alignment +
    0.15 × value_add +
    0.15 × test_coverage +
    0.10 × documentation +
    0.10 × network_effects +
    0.10 × novelty
)
```

### Impact

**Multiplier**: `0.5 + coherence`

| Coherence | Multiplier | Impact |
|-----------|------------|--------|
| 0.0 | 0.5x | Earn 50% of cost share |
| 0.5 | 1.0x | Earn 100% of cost share |
| 0.9 | 1.4x | Earn 140% of cost share |
| 1.0 | 1.5x | Earn 150% of cost share |

**Example** (seeker71):
- Cost: $2,413.19
- Coherence: 0.92
- Multiplier: 1.42x
- Weighted: $3,426.73

When $10k distributed:
- Without coherence: $9,600 (96% of contributions)
- With coherence: $9,622 (96.22% of weighted contributions)
- **Bonus: $22 for quality**

## Distribution Algorithm

### Recursive Graph Traversal

**Steps**:
1. Get all direct contributions to asset
2. Calculate weighted costs: `cost × (0.5 + coherence)`
3. For SYSTEM contributors → attribute to triggering human
4. For ASSET_COMPOSITION → recurse into dependency
5. Aggregate payouts per contributor

**Example**:

```
Asset A: $10,000 value
├─ Alice: $100 cost, 0.9 coherence → $140 weighted
├─ Claude (triggered by Alice): $10 cost → $14 weighted (→ Alice)
└─ Dependency on Asset B: $50 cost

Asset B:
├─ Bob: $40 cost, 0.8 coherence → $52 weighted
└─ Carol: $10 cost, 0.7 coherence → $12 weighted

Total weighted cost A: $140 + $14 + ($52 + $12) = $218
Total weighted cost: $218

Distribution:
- Alice: ($154 / $218) × $10,000 = $7,064
- Bob: ($52 / $218) × $10,000 = $2,385
- Carol: ($12 / $218) × $10,000 = $551
```

## Revenue Streams

### 1. API Usage Fees

**Free Tier**: 1,000 requests/month
**Paid**: $0.001 per request

**At 100k requests/month**:
- Free: 1,000 × $0 = $0
- Paid: 99,000 × $0.001 = $99
- **Revenue**: $99/month

### 2. Distribution Fees

**Rate**: 2% of distributed value

**Example**:
- $10,000 distribution
- Fee: $200
- Contributors get: $9,800

### 3. Node Operator Markup

**Operator pricing**: $0.0001/request
**Network pricing**: $0.00011/request (10% markup)
**Difference**: $0.00001/request to network

**At 1M requests/month**:
- Operator earns: $100
- Network earns: $10

### 4. Enterprise Licenses

**Self-hosted**: $5,000/month
**Managed**: $10,000/month

**Just 1 customer → $5k/month revenue!**

## Cost Structure

### Monthly Expenses

| Category | Amount |
|----------|--------|
| Node operator payments | $5,000 |
| Payment processing (Stripe 2.9%) | $150 |
| Development (bug bounties) | $1,000 |
| Marketing | $500 |
| Infrastructure | $200 |
| Legal/compliance | $150 |
| **Total** | **$7,000** |

### Break-Even Analysis

**Monthly costs**: $7,000

**Revenue needed**:
- From API usage (at $0.001/req): 7M requests
- OR from enterprise: 2 customers
- OR from distributions: $350k distributed (2% fee)

**Realistic**: 250M requests + 1 enterprise customer

## Growth Model

### Month 1 (Loss)
- Requests: 1M
- Revenue: $55
- Costs: $100
- **Loss**: -$45

### Month 3 (Break-even)
- Requests: 10M
- Revenue: $550
- Costs: $400
- **Profit**: $150

### Month 6 (Profitable)
- Requests: 50M
- Revenue: $2,750
- Costs: $2,500
- **Profit**: $250

### Year 1 (Sustainable)
- Requests: 300M/month
- Revenue: $16,500/month
- Costs: $12,000/month
- **Profit**: $4,500/month

**Annual**: $54,000 profit

**Distribution**:
- 50% to reserve: $27,000
- 50% to contributors: $27,000

**seeker71's share** (96.5%): **$26,055/year**

### Year 2 (Scaling)
- Requests: 3B/month
- Revenue: $165,000/month
- Costs: $70,000/month
- **Profit**: $95,000/month

**Annual**: $1,140,000 profit

**Distribution**:
- 50% to reserve: $570,000
- 50% to contributors: $570,000

**seeker71's share** (96.5%): **$550,050/year**

**From a $2,413 investment!**

## Contributor ROI

**Initial investment**: $2,413.19
**Year 1 return**: $26,055
**Year 2 return**: $550,050

**ROI**:
- Year 1: 980%
- Year 2: 22,700%
- Cumulative: 23,780% over 2 years

**This assumes seeker71 maintains 96.5% contribution share.**

As others contribute, your share dilutes but total value grows faster.

## Network Sustainability

**Key metric**: Revenue / Costs

- <1.0: Unsustainable (operating at loss)
- 1.0-1.2: Break-even (minimal buffer)
- 1.2-1.5: Sustainable (building reserves)
- >1.5: Highly profitable (distributing to contributors)

**Target**: 1.5x by Month 6

**Strategy**:
1. Free tier attracts users
2. Heavy users upgrade to paid
3. Enterprise customers = big revenue
4. Node marketplace reduces costs
5. Profit distributed to contributors
6. Contributors build more features
7. More features = more users
8. Flywheel effect!
