# Progress — ux-new-contributor-orientation

## Completed phases
- **impl** (task_089875ccdff5519b): Added new contributor orientation to homepage
  - 2-sentence explanation above the fold
  - "What is this?" expandable section (3 paragraphs: what it is, value graph, CC credits)
  - Pulse stats show "validated" count using existing API field

## Current task
Complete

## Key decisions
- Reused existing `validated_ideas` from `/api/ideas` summary — no new API endpoint
- Replaced "value created" stat with "validated" for clearer newcomer signal
- Simple client component with useState toggle, no dependencies

## Blockers
(none)
