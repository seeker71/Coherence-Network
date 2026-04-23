# Spec Index

> 74 specs (69 done, 5 draft). Grouped by parent idea. Read frontmatter (`limit=30`) for source files, requirements, done_when.

## By Idea (18 ideas → 74 specs)

### idea-realization-engine (8 specs)
- [idea-dual-identity](idea-dual-identity.md) — curated + raw dual identity
- [idea-hierarchy-super-child](idea-hierarchy-super-child.md) — parent/child absorption
- [idea-lifecycle-closure](idea-lifecycle-closure.md) — close/archive/absorb lifecycle
- [idea-lifecycle-management](idea-lifecycle-management.md) — stage transitions + history
- [idea-right-sizing](idea-right-sizing.md) — complexity scoring + split/merge
- [ideas-prioritization](ideas-prioritization.md) — free-energy scoring + ranking
- [standing-questions-roi-and-next-task-generation](standing-questions-roi-and-next-task-generation.md) — ROI questions → task generation
- [super-idea-rollup-criteria](super-idea-rollup-criteria.md) — rollup rules for super-ideas

### agent-pipeline (6 specs)
- [agent-orchestration-api](agent-orchestration-api.md) — task dispatch + agent coordination
- [attention-heuristics-pipeline-status](attention-heuristics-pipeline-status.md) — pipeline attention scoring
- [coherence-network-agent-pipeline](coherence-network-agent-pipeline.md) — end-to-end pipeline flow
- [pipeline-observability-and-auto-review](pipeline-observability-and-auto-review.md) — observability + auto-review
- [project-manager-pipeline](project-manager-pipeline.md) — PM cycle orchestration
- [split-review-deploy-verify-phases](split-review-deploy-verify-phases.md) — review/deploy/verify phases

### pipeline-reliability (8 specs)
- [auto-heal-from-diagnostics](auto-heal-from-diagnostics.md) — auto-heal from failure diagnostics
- [data-driven-timeout-resume](data-driven-timeout-resume.md) — adaptive timeouts + resume
- [failed-task-diagnostics-contract](failed-task-diagnostics-contract.md) — structured failure diagnostics
- [heal-completion-issue-resolution](heal-completion-issue-resolution.md) — heal + issue resolution
- [incident-response-and-self-healing](incident-response-and-self-healing.md) — incident response automation
- [smart-reap](smart-reap.md) — intelligent task reaping
- [stale-task-reaper](stale-task-reaper.md) — stale task cleanup
- [task-deduplication](task-deduplication.md) — duplicate task detection

### pipeline-optimization (6 specs)
- [cross-task-outcome-correlation](cross-task-outcome-correlation.md) — outcome correlation across tasks
- [prompt-ab-roi-measurement](prompt-ab-roi-measurement.md) — prompt A/B testing + ROI
- [provider-health-alerting](provider-health-alerting.md) — LLM provider health monitoring
- [provider-usage-coalescing-timeout-resilience](provider-usage-coalescing-timeout-resilience.md) — usage coalescing + resilience
- [runner-auto-contribution](runner-auto-contribution.md) — runner auto-contribution tracking
- [tool-failure-awareness](tool-failure-awareness.md) — tool failure detection + routing

### data-infrastructure (8 specs)
- [api-request-logging-middleware](api-request-logging-middleware.md) — request logging middleware
- [canonical-route-registry-and-runtime-mapping](canonical-route-registry-and-runtime-mapping.md) — route registry + runtime mapping
- [coherence-algorithm-spec](coherence-algorithm-spec.md) — CRK coherence scoring algorithm
- [postgresql-migration](postgresql-migration.md) — SQLite → PostgreSQL migration
- [release-gates](release-gates.md) — release gate checks
- [runtime-telemetry-db-precedence](runtime-telemetry-db-precedence.md) — telemetry DB precedence rules
- [unified-sqlite-store](unified-sqlite-store.md) — unified SQLite store (legacy)
- [universal-node-edge-layer](universal-node-edge-layer.md) — graph DB node + edge CRUD

### coherence-credit (7 specs)
- [cc-economics-and-value-coherence](cc-economics-and-value-coherence.md) — CC economic model
- [cc-new-earth-exchange-bridge](cc-new-earth-exchange-bridge.md) — CC ↔ external exchange adapters + swap flow
- [coherence-credit-internal-currency](coherence-credit-internal-currency.md) — CC as internal currency
- [grounded-cost-value-measurement](grounded-cost-value-measurement.md) — grounded cost/value measurement
- [grounded-idea-portfolio-metrics](grounded-idea-portfolio-metrics.md) — portfolio-level metrics
- [mvp-cost-and-acceptance-proof](mvp-cost-and-acceptance-proof.md) — MVP cost + acceptance proof
- [portfolio-governance-effectiveness](portfolio-governance-effectiveness.md) — governance effectiveness scoring

### value-attribution (9 specs)
- [asset-renderer-plugin](asset-renderer-plugin.md) — pluggable renderers per MIME type
- [assets-api](assets-api.md) — asset CRUD + lineage
- [contributions-api](contributions-api.md) — contribution tracking API
- [contributor-onboarding-and-governed-change-flow](contributor-onboarding-and-governed-change-flow.md) — governed change flow
- [distribution-engine](distribution-engine.md) — value distribution engine
- [normalize-github-commit-cost-estimation](normalize-github-commit-cost-estimation.md) — GitHub commit cost estimation
- [task-claim-tracking-and-roi-dedupe](task-claim-tracking-and-roi-dedupe.md) — task claim tracking + ROI dedup
- [value-lineage-and-payout-attribution](value-lineage-and-payout-attribution.md) — value lineage chain
- [story-protocol-integration](story-protocol-integration.md) — Story Protocol IP + x402 micropayments + Arweave storage

### user-surfaces (6 specs)
- [coherence-cli-comprehensive](coherence-cli-comprehensive.md) — CLI 35+ commands
- [mcp-skill-registry-submission](mcp-skill-registry-submission.md) — MCP skill registry
- [meta-self-discovery](meta-self-discovery.md) — system self-discovery endpoints
- [node-task-visibility](node-task-visibility.md) — node task visibility dashboard
- [ux-homepage-readability](ux-homepage-readability.md) — homepage readability UX
- [web-ideas-specs-usage-pages](web-ideas-specs-usage-pages.md) — web ideas/specs/usage pages

### portfolio-governance (1 spec)
- [portfolio-governance-health](portfolio-governance-health.md) — governance health scoring

### agent-cli (2 specs)
- [agent-execution-lifecycle-hooks](agent-execution-lifecycle-hooks.md) — execution lifecycle hooks
- [unified-agent-cli-flow-patch-on-fail](unified-agent-cli-flow-patch-on-fail.md) — CLI flow + patch-on-fail

### knowledge-and-resonance (4 specs)
- [agent-memory-system](agent-memory-system.md) — write/manage/read memory loop: moments of aliveness, consolidation at rest, retrieval as composition (draft)
- [knowledge-resonance-engine](knowledge-resonance-engine.md) — concept layer, belief resonance, discovery feed
- [living-signal-layer](living-signal-layer.md) — sense signals as a changing field, not fixed categories
- [source-artifact-sensing-graph-integration](source-artifact-sensing-graph-integration.md) — source artifacts as first-class graph nodes with provenance

### identity-and-onboarding (2 specs)
- [identity-driven-onboarding-tofu](identity-driven-onboarding-tofu.md) — TOFU identity + 37 providers
- [investment-ux-stake-cc-on-ideas](investment-ux-stake-cc-on-ideas.md) — stake CC on ideas UX

### contributor-experience (1 spec)
- [contributor-journey](contributor-journey.md) — contributor orientation + journey

### developer-experience (1 spec)
- [developer-quick-start](developer-quick-start.md) — developer quick start guide

### federation-and-nodes (1 spec)
- [federation-network-layer](federation-network-layer.md) — multi-node federation protocol

### external-presence (2 specs)
- [external-presence-bots-and-news](external-presence-bots-and-news.md) — social bots + news ingestion
- [multilingual-web](multilingual-web.md) — multilingual UI + content, machine and community translations

### public-verification-framework (1 spec)
- [public-verification-framework](public-verification-framework.md) — Merkle hash chains, Arweave snapshots, public audit API

### financial-integration-fiat-bridge (1 spec)
- [financial-integration](financial-integration.md) — CC fiat bridge, USDC exchange, KYC, tax reporting

## Lookup

```bash
# Find spec by keyword
grep -l "resonance" specs/*.md

# Read spec frontmatter only (source, requirements, done_when)
head -30 specs/{slug}.md

# API: all specs for an idea
curl https://api.coherencycoin.com/api/ideas/{idea_id}/specs
```
