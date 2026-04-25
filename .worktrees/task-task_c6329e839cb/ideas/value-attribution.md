---
idea_id: value-attribution
title: Value Attribution
stage: implementing
work_type: feature
pillar: economics
specs:
  - [contributions-api](../specs/contributions-api.md)
  - [value-lineage-and-payout-attribution](../specs/value-lineage-and-payout-attribution.md)
  - [distribution-engine](../specs/distribution-engine.md)
  - [assets-api](../specs/assets-api.md)
  - [task-claim-tracking-and-roi-dedupe](../specs/task-claim-tracking-and-roi-dedupe.md)
  - [normalize-github-commit-cost-estimation](../specs/normalize-github-commit-cost-estimation.md)
  - [contributor-onboarding-and-governed-change-flow](../specs/contributor-onboarding-and-governed-change-flow.md)
  - [story-protocol-integration](../specs/story-protocol-integration.md)
---

# Value Attribution

Track who contributed what, calculate fair payouts based on measurable value. Every line of code, every spec written, every review completed has an owner and a value. The attribution system creates an unbroken chain from idea inception through implementation to real-world usage and CC payout.

## Problem

Open-source contributions are invisible. Someone writes a critical spec, another person implements it, a third reviews it, and none of them can prove what they did or receive proportional credit. When payouts happen, they are either equal (unfair to high contributors) or subjective (unfair to everyone). Without a verifiable record, trust breaks down.

## Key Capabilities

- **Contributions API**: Record time, effort, code, and cost for every contributor on every task. Each contribution is timestamped, linked to a specific idea and task, and assigned a coherence score reflecting its alignment with the idea's goals.
- **Value lineage**: Full traceability from idea -> spec -> implementation -> usage -> payout. If a feature generates value, the system traces back through every contribution that made it possible and allocates credit proportionally.
- **Distribution engine**: Fair CC payouts based on coherence scores and contribution weight. Contributors who do higher-coherence work (more aligned with the idea, higher quality) receive proportionally more CC.
- **Assets API**: Track code, models, content, and data artifacts linked to ideas. Assets are the tangible outputs of contributions -- a deployed API endpoint, a trained model, a documentation page.
- **Task claim tracking**: Prevent double-counting when multiple agents work on the same idea. Claims are exclusive per task -- once claimed, other agents see it as taken and move to the next available task.
- **GitHub commit cost normalization**: Derive cost estimates from commit diffs. Lines changed, file complexity, test coverage delta, and review rounds are normalized into CC cost estimates so human and agent contributions are comparable.

## What Success Looks Like

- Every completed task has at least one contribution record with a non-zero coherence score
- Value lineage chains are complete: no orphaned contributions without an idea, no ideas without attribution
- CC payouts match contribution weight within 5% of the distribution engine's calculation
- Zero duplicate task claims across concurrent agents

## Absorbed Ideas

- **cross-linked-presences**: All 6 presences (GitHub, npm CLI, npm MCP, OpenClaw, API docs, Web) link to each other. Ecosystem table on every surface. Contributors can discover the platform from any entry point and trace their contributions across all surfaces.
- **agent-session-summary**: Before session ends, auto-summarize: ideas created, contributions made, tasks completed. POST as contribution record. Ensures no agent work is lost -- every session produces a permanent record.
- **dif-instrumentation-feedback**: Track DIF (Diff Impact Factor) true/false positives per file, feed back to improve code quality scoring. Over time, the system learns which diffs actually produce value and which are noise.
