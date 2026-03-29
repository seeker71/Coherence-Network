# Progress — idea-fecc6d087c4e

## Completed phases

- **Tests (task_091e05a4a2ae7242)**: New file `api/tests/test_idea_fecc6d087c4e_invest_ts_parity.py` — acceptance checks for Invest page TS/Python parity (`computeRoi`, `roiBarWidth`, source anchors, ROI sort). Complements existing `test_fecc6d087c4e_invest_garden_metaphor.py` without editing it.

## Current task

Done for this task; pending local runner: pytest + DIF + git commit.

## Key decisions

- Kept scope to **new test file only** per task rules; no edits to prior garden-metaphor test module.
- Parity tests mirror `web/app/invest/page.tsx` exactly so future garden UI can rely on stable math.

## Blockers

- Local/sandbox: run pytest and DIF verify before merge.
