# MVP Investment Allocation Policy

Last updated: 2026-03-28
Owner: `seeker71`
Status: **FINALIZED**

## Purpose

Define the financial discipline and allocation strategy for funds within the MVP Marketplace phase.

## Target Allocation Ranges

| Category | Target Range | Description |
|---|---|---|
| **Runway (Liquidity)** | 40% - 60% | Liquid cash/stables for monthly operating expenses. Minimum 6 months runway goal. |
| **Yield Sleeve (Income)** | 30% - 50% | Conservative yield-bearing assets (e.g., staked ETH, stables yield). |
| **Growth / Operating Spend** | 10% - 20% | Discretionary spend for pilot onboarding, bounty payouts, or infrastructure. |

## Allocation Strategy

1. **Safety First**: Prioritize liquid runway above all. If runway drops below 6 months, yield sleeve and growth spend must be paused.
2. **Conservative Yield**: Income-sleeve assets should be low-risk (no leverage, no de-pegged assets).
3. **Rebalance Cadence**: Review and rebalance allocations monthly based on actual burn rate and income.

## Decision Criteria

All allocation actions (moving funds between categories) must meet the following:
- Does this maintain at least 6 months of liquid runway?
- Is the destination asset compliant with the conservative yield strategy?
- Is the rationale recorded in the monthly review?

## Compliance Monitoring

- Track `allocated_capital_total_usd` and `yield_sleeve_allocated_usd` in the weekly dashboard.
- Any action outside target ranges or 6-month runway floor is logged as a `policy_variance`.
