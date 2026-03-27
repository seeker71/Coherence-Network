# Spec 157 — Investment UX (CC + time)

## Purpose

Improve staking/investment UX: CLI confirmation with projected ROI, web invest actions, portfolio and history with flow visualization, and time-based commitments.

## Requirements

1. **Preview** — Given `idea_id` and `amount_cc`, return projected return using live idea `roi_cc`.
2. **Portfolio** — Per contributor, list idea positions with staked CC and estimated current value.
3. **Flow** — Graph nodes/edges + timeline from ledger for visualization.
4. **Time investment** — Record `time_commitment` contributions with hours and role (`review` | `implement`).
5. **CLI** — `cc invest <idea> <amount>` with confirmation; `portfolio` / `history` / `time` subcommands.
6. **Web** — Invest button with ROI preview on `/invest`; `/invest/portfolio` and `/invest/history` pages.

## API Contract

- `GET /api/investments/preview?idea_id=&amount_cc=` → preview payload
- `GET /api/investments/portfolio?contributor_id=` → positions + totals
- `GET /api/investments/flow?contributor_id=` → nodes, edges, timeline
- `POST /api/investments/time/{idea_id}` → record time commitment

## Files to Create/Modify

- `api/app/services/investment_service.py` (new)
- `api/app/routers/investments.py` (new)
- `api/app/main.py`
- `api/app/services/contribution_ledger_service.py` (suggested type)
- `cli/lib/commands/invest.mjs` (new)
- `cli/bin/cc.mjs`
- `web/app/invest/page.tsx`
- `web/app/invest/portfolio/page.tsx` (new)
- `web/app/invest/history/page.tsx` (new)
- `web/components/invest_idea_button.tsx` (new)
- `web/components/time_commitment_form.tsx` (new)
- `web/app/ideas/[idea_id]/page.tsx` (time commitment section)
- `web/app/invest/InvestBalanceSection.tsx` (balance field fix)

## Verification

- `GET /api/investments/preview` returns 404 for unknown idea
- Portfolio and flow return 200 with JSON for a contributor id
- Time commitment creates ledger record with metadata

## Risks and Assumptions

- Current value uses `staked_cc * (1 + min(roi_cc, 50))` as a display estimate; not financial advice.

## Known Gaps and Follow-up Tasks

- Deeper integration with treasury payouts when available.
