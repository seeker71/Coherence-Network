---
idea_id: portfolio-governance
status: done
source:
  - file: api/app/services/governance_service.py
    symbols: [create_change_request, vote_on_change_request, apply_approved]
  - file: api/app/services/grounded_idea_metrics_service.py
    symbols: [compute_idea_metrics, compute_portfolio_health]
  - file: api/app/services/coherence_service.py
    symbols: [compute_coherence_score]
  - file: api/app/services/right_sizing_service.py
    symbols: [build_report, compute_granularity_signal, apply_suggestion]
  - file: api/app/services/vitality_service.py
    symbols: [compute_vitality]
  - file: api/app/services/cc_economics_service.py
    symbols: [get_supply, stake, unstake]
  - file: api/app/services/distribution_engine.py
    symbols: [compute_distribution]
requirements:
  - Governance change requests with voting and auto-apply
  - Grounded idea metrics (actual_value vs potential_value)
  - Coherence score from 9+ signals
  - Right-sizing detection (too_large, too_small, overlap via TF-IDF)
  - Workspace vitality (6 living-system health signals)
  - CC economics (treasury, staking, exchange rate, coherence invariant)
  - Distribution engine for CC payouts
  - Super-idea rollup criteria with auto-status update
done_when:
  - GET /api/coherence returns score with signal breakdown
  - GET /api/ideas/right-sizing returns health counts and suggestions
  - GET /api/workspaces/{id}/vitality returns 6 health signals
  - GET /api/cc/supply returns coherence score
  - POST /api/cc/stake creates staking position
  - All tests pass
test: "python3 -m pytest api/tests/test_cc_economics.py api/tests/test_right_sizing.py api/tests/test_flow_vitality.py -q"
---

> **Parent idea**: [portfolio-governance](../ideas/portfolio-governance.md)
> **Source**: [`api/app/services/governance_service.py`](../api/app/services/governance_service.py) | [`api/app/services/grounded_idea_metrics_service.py`](../api/app/services/grounded_idea_metrics_service.py) | [`api/app/services/coherence_service.py`](../api/app/services/coherence_service.py) | [`api/app/services/right_sizing_service.py`](../api/app/services/right_sizing_service.py) | [`api/app/services/vitality_service.py`](../api/app/services/vitality_service.py) | [`api/app/services/cc_economics_service.py`](../api/app/services/cc_economics_service.py) | [`api/app/services/distribution_engine.py`](../api/app/services/distribution_engine.py)

# Portfolio Governance Health -- Coherence Score, Right-Sizing, and Living Metrics

## Goal

Provide the measurement and governance layer that lets the network reason about its idea portfolio as one coherent system -- with grounded metrics that replace guesswork, coherence scoring from 9+ signals, automatic right-sizing detection, workspace vitality tracking, CC economics with treasury invariants, and a distribution engine that pays contributors based on proven impact.

## What's Built

The portfolio governance layer spans seven service files implementing six interlocking capabilities.

**Governance**: `governance_service.py` implements the propose-review-approve pipeline with `create_change_request`, `vote_on_change_request`, and `apply_approved`. Every change to ideas and specs flows through this pipeline with full proposer and voter attribution. Approved requests auto-apply by default.

**Grounded metrics**: `grounded_idea_metrics_service.py` computes `actual_value` vs `potential_value` for every idea via `compute_idea_metrics`. `compute_portfolio_health` aggregates these into a portfolio-wide health snapshot showing which ideas are pulling their weight and which are noise.

**Coherence scoring**: `coherence_service.py` implements `compute_coherence_score` which synthesizes 9+ signals (semantic alignment, structural fit, contribution velocity, resonance depth, and more) into a single 0.0-1.0 score with full signal breakdown. Every score comes with a "why" -- no black-box rankings.

**Right-sizing**: `right_sizing_service.py` detects granularity drift with `compute_granularity_signal` which flags ideas as `too_large`, `too_small`, or `overlap` using TF-IDF similarity. `build_report` generates portfolio health counts and actionable suggestions. `apply_suggestion` executes split or merge operations with dry-run support.

**Workspace vitality**: `vitality_service.py` implements `compute_vitality` which measures 6 living-system health signals for each workspace -- contribution frequency, idea velocity, question resolution rate, member engagement, coherence trend, and decay risk. Workspaces that are dying get surfaced before they become structural debt.

**CC economics and distribution**: `cc_economics_service.py` manages the treasury with `get_supply` (total minted, burned, outstanding, coherence score), `stake` (CC into ideas), and `unstake` (with tiered cooldown). The coherence invariant -- `treasury_value / (total_cc * exchange_rate) >= 1.0` -- is enforced at all times. `distribution_engine.py` implements `compute_distribution` for CC payouts proportional to proven impact.

## Requirements

1. Governance change requests with voting and auto-apply
2. Grounded idea metrics (actual_value vs potential_value)
3. Coherence score from 9+ signals
4. Right-sizing detection (too_large, too_small, overlap via TF-IDF)
5. Workspace vitality (6 living-system health signals)
6. CC economics (treasury, staking, exchange rate, coherence invariant)
7. Distribution engine for CC payouts
8. Super-idea rollup criteria with auto-status update

## Acceptance Tests

```bash
python3 -m pytest api/tests/test_cc_economics.py api/tests/test_right_sizing.py api/tests/test_flow_vitality.py -q
```
