# Unshipped Specs — thematic consolidation

Sensed from `docs/lineage/unshipped-work-archive-2026-04-26.md` (1,062 task branches → 386 unique spec attempts).

This document is a navigable map of what was attempted but never landed. It distills the 62k-line raw archive into themes so the body can walk its unshipped intent without reading every fragment.

## Counts

- **390 unique unshipped spec slugs** in the archive
- **10** UUID-named placeholders (auto-generated noise; safe to release)
- **8** with **same name as a spec already on main** (the attempt didn't land but the canonical did via different commit)
- **57** with a **numeric-prefix variant of an on-main slug** (old convention; canonical lives on main without the prefix)
- **315** **truly unshipped** — no on-main equivalent yet

## Already on main under same name (8)

These attempts targeted specs that landed via a different commit. The work is on `main`; the unshipped attempt is duplicate effort.

- `specs/cli-binary-name-conflict.md` ↔ on main
- `specs/financial-integration.md` ↔ on main
- `specs/meta-self-discovery.md` ↔ on main
- `specs/runner-auto-contribution.md` ↔ on main
- `specs/stale-task-reaper.md` ↔ on main
- `specs/task-deduplication.md` ↔ on main
- `specs/universal-node-edge-layer.md` ↔ on main
- `specs/ux-homepage-readability.md` ↔ on main

## Numeric-prefix variants of on-main specs (57)

Old naming convention from the early body. Canonical lives on main without the number.

- `specs/002-agent-orchestration-api.md` → canonical `specs/agent-orchestration-api.md` on main
- `specs/005-project-manager-pipeline.md` → canonical `specs/project-manager-pipeline.md` on main
- `specs/018-coherence-algorithm-spec.md` → canonical `specs/coherence-algorithm-spec.md` on main
- `specs/026-pipeline-observability-and-auto-review.md` → canonical `specs/pipeline-observability-and-auto-review.md` on main
- `specs/032-attention-heuristics-pipeline-status.md` → canonical `specs/attention-heuristics-pipeline-status.md` on main
- `specs/047-heal-completion-issue-resolution.md` → canonical `specs/heal-completion-issue-resolution.md` on main
- `specs/048-contributions-api.md` → canonical `specs/contributions-api.md` on main
- `specs/048-value-lineage-and-payout-attribution.md` → canonical `specs/value-lineage-and-payout-attribution.md` on main
- `specs/049-distribution-engine.md` → canonical `specs/distribution-engine.md` on main
- `specs/050-canonical-route-registry-and-runtime-mapping.md` → canonical `specs/canonical-route-registry-and-runtime-mapping.md` on main
- `specs/051-release-gates.md` → canonical `specs/release-gates.md` on main
- `specs/052-assets-api.md` → canonical `specs/assets-api.md` on main
- `specs/053-ideas-prioritization.md` → canonical `specs/ideas-prioritization.md` on main
- `specs/053-standing-questions-roi-and-next-task-generation.md` → canonical `specs/standing-questions-roi-and-next-task-generation.md` on main
- `specs/054-postgresql-migration.md` → canonical `specs/postgresql-migration.md` on main
- `specs/074-tool-failure-awareness.md` → canonical `specs/tool-failure-awareness.md` on main
- `specs/075-web-ideas-specs-usage-pages.md` → canonical `specs/web-ideas-specs-usage-pages.md` on main
- `specs/083-task-claim-tracking-and-roi-dedupe.md` → canonical `specs/task-claim-tracking-and-roi-dedupe.md` on main
- `specs/086-normalize-github-commit-cost-estimation.md` → canonical `specs/normalize-github-commit-cost-estimation.md` on main
- `specs/094-contributor-onboarding-and-governed-change-flow.md` → canonical `specs/contributor-onboarding-and-governed-change-flow.md` on main
- `specs/107-runtime-telemetry-db-precedence.md` → canonical `specs/runtime-telemetry-db-precedence.md` on main
- `specs/108-unified-agent-cli-flow-patch-on-fail.md` → canonical `specs/unified-agent-cli-flow-patch-on-fail.md` on main
- `specs/111-agent-execution-lifecycle-hooks.md` → canonical `specs/agent-execution-lifecycle-hooks.md` on main
- `specs/112-prompt-ab-roi-measurement.md` → canonical `specs/prompt-ab-roi-measurement.md` on main
- `specs/113-failed-task-diagnostics-contract.md` → canonical `specs/failed-task-diagnostics-contract.md` on main
- `specs/113-provider-usage-coalescing-timeout-resilience.md` → canonical `specs/provider-usage-coalescing-timeout-resilience.md` on main
- `specs/114-auto-heal-from-diagnostics.md` → canonical `specs/auto-heal-from-diagnostics.md` on main
- `specs/114-mvp-cost-and-acceptance-proof.md` → canonical `specs/mvp-cost-and-acceptance-proof.md` on main
- `specs/115-grounded-cost-value-measurement.md` → canonical `specs/grounded-cost-value-measurement.md` on main
- `specs/116-grounded-idea-portfolio-metrics.md` → canonical `specs/grounded-idea-portfolio-metrics.md` on main
- `specs/117-idea-hierarchy-super-child.md` → canonical `specs/idea-hierarchy-super-child.md` on main
- `specs/118-unified-sqlite-store.md` → canonical `specs/unified-sqlite-store.md` on main
- `specs/119-coherence-credit-internal-currency.md` → canonical `specs/coherence-credit-internal-currency.md` on main
- `specs/120-super-idea-rollup-criteria.md` → canonical `specs/super-idea-rollup-criteria.md` on main
- `specs/124-cc-economics-and-value-coherence.md` → canonical `specs/cc-economics-and-value-coherence.md` on main
- `specs/125-incident-response-and-self-healing.md` → canonical `specs/incident-response-and-self-healing.md` on main
- `specs/126-portfolio-governance-effectiveness.md` → canonical `specs/portfolio-governance-effectiveness.md` on main
- `specs/127-cross-task-outcome-correlation.md` → canonical `specs/cross-task-outcome-correlation.md` on main
- `specs/130-api-request-logging-middleware.md` → canonical `specs/api-request-logging-middleware.md` on main
- `specs/133-federation-aggregated-visibility.md` → canonical `specs/federation-aggregated-visibility.md` on main
- `specs/135-provider-health-alerting.md` → canonical `specs/provider-health-alerting.md` on main
- `specs/138-idea-lifecycle-management.md` → canonical `specs/idea-lifecycle-management.md` on main
- `specs/139-coherence-network-agent-pipeline.md` → canonical `specs/coherence-network-agent-pipeline.md` on main
- `specs/148-coherence-cli-comprehensive.md` → canonical `specs/coherence-cli-comprehensive.md` on main
- `specs/157-investment-ux-stake-cc-on-ideas.md` → canonical `specs/investment-ux-stake-cc-on-ideas.md` on main
- `specs/158-idea-right-sizing.md` → canonical `specs/idea-right-sizing.md` on main
- `specs/159-split-review-deploy-verify-phases.md` → canonical `specs/split-review-deploy-verify-phases.md` on main
- `specs/161-node-task-visibility.md` → canonical `specs/node-task-visibility.md` on main
- `specs/162-meta-self-discovery.md` → canonical `specs/meta-self-discovery.md` on main
- `specs/165-ux-homepage-readability.md` → canonical `specs/ux-homepage-readability.md` on main
- `specs/166-universal-node-edge-layer.md` → canonical `specs/universal-node-edge-layer.md` on main
- `specs/168-identity-driven-onboarding-tofu.md` → canonical `specs/identity-driven-onboarding-tofu.md` on main
- `specs/169-smart-reap.md` → canonical `specs/smart-reap.md` on main
- `specs/176-idea-lifecycle-closure.md` → canonical `specs/idea-lifecycle-closure.md` on main
- `specs/180-mcp-skill-registry-submission.md` → canonical `specs/mcp-skill-registry-submission.md` on main
- `specs/181-idea-dual-identity.md` → canonical `specs/idea-dual-identity.md` on main
- `specs/200-identity-driven-onboarding-tofu.md` → canonical `specs/identity-driven-onboarding-tofu.md` on main

## UUID-named placeholders (10)

Auto-generated when the task pipeline didn't have a real idea slug.

- `specs/09a5901f-27f9-4489-ab13-915e7394709e.md`
- `specs/2dfdccc7-c976-4f3d-9747-ae8a71ce4b8e.md`
- `specs/315c11db-e5df-42c8-90d4-6aafc1a94845.md`
- `specs/6d1cd360-4e08-48a1-bd80-4a891c010e65.md`
- `specs/74211aab-286b-499a-8425-ccc50c161ac2.md`
- `specs/84df8ee2-6323-4319-99b9-bdc648be655d.md`
- `specs/ba4a45bc-931e-42dc-ad36-cb89b327cd71.md`
- `specs/bc2466c4-7893-444f-a0f0-c02fd03ed65a.md`
- `specs/dfdcb9fe-72ee-4e59-87cc-38a69caaf9e8.md`
- `specs/e7f32e03-2327-4cae-a8d8-facd8281a604.md`

## Truly unshipped, by theme (315 specs across 284 themes)

Each theme groups specs that share a first 1-2 word prefix. Themes that match an existing idea slug are marked.

### `idea` — 4 specs

- `specs/idea-4deb5bd7c800.md`
- `specs/idea-5136127f7007.md`
- `specs/idea-a6fce8cc9f8f.md`
- `specs/idea-fecc6d087c4e.md`

### `project-manager` — 4 specs

- `specs/005-project-manager-orchestrator.md`
- `specs/040-project-manager-load-backlog-malformed-test.md`
- `specs/041-project-manager-state-file-flag-test.md`
- `specs/042-project-manager-reset-clears-state-test.md`

### `contribution-recognition` — 3 specs

- `specs/171-contribution-recognition-growth.md`
- `specs/177-contribution-recognition-growth-tracking.md`
- `specs/178-contribution-recognition-growth.md`

### `federation-measurement` — 3 specs

- `specs/131-federation-measurement-push.md`
- `specs/142-federation-measurement-push-verification.md`
- `specs/federation-measurement-push.md`

### `fractal-node` — 3 specs

- `specs/168-fractal-node-edge-primitives.md`
- `specs/169-fractal-node-edge-primitives.md`
- `specs/fractal-node-edge-primitives.md`

### `web` — 3 specs

- `specs/012-web-skeleton.md`
- `specs/017-web-ci.md`
- `specs/web-skeleton.md`

### `### 1.1 Spec file backfill (`scripts/backfill_spec_idea_links.py`)` — 1 spec

- `specs/### 1.1 Spec file backfill (`scripts/backfill_spec_idea_links.py`).md`

### `agent-service` — 2 specs

- `specs/043-agent-service-spec-task-type-local-model-test.md`
- `specs/044-agent-service-test-task-type-local-model-test.md`

### `ci` — 2 specs

- `specs/004-ci-pipeline.md`
- `specs/ci-pipeline.md`

### `community-project` — 2 specs

- `specs/141-community-project-funder-match-showcase-page.md`
- `specs/community-project-funder-match.md`

### `configurable-news` — 2 specs

- `specs/151-configurable-news-sources.md`
- `specs/configurable-news-sources.md`

### `contributor` — 2 specs

- `specs/contributor-discovery.md`
- `specs/contributor-messaging.md`

### `data-hygiene` — 2 specs

- `specs/177-data-hygiene-monitor.md`
- `specs/data-hygiene-db-monitoring.md`

### `discord-bot` — 2 specs

- `specs/163-discord-bot-channels-per-idea.md`
- `specs/164-discord-bot-channels-per-idea.md`

### `federation-strategy` — 2 specs

- `specs/134-federation-strategy-propagation.md`
- `specs/federation-strategy-propagation.md`

### `fractal-self` — 2 specs

- `specs/172-fractal-self-balance.md`
- `specs/fractal-self-balance.md`

### `full-traceability` — 2 specs

- `specs/183-full-traceability-chain.md`
- `specs/184-full-traceability-chain.md`

### `invest-garden` — 2 specs

- `specs/181-invest-garden-metaphor.md`
- `specs/182-invest-garden-metaphor.md`

### `logging` — 2 specs

- `specs/013-logging-audit.md`
- `specs/logging-audit.md`

### `pagination` — 2 specs

- `specs/011-pagination.md`
- `specs/pagination.md`

### `post-tasks` — 2 specs

- `specs/037-post-tasks-invalid-task-type-422.md`
- `specs/038-post-tasks-empty-direction-422.md`

### `resonance` — 2 specs

- `specs/163-resonance-navigation.md`
- `specs/resonance-navigation.md`

### `self-balancing` — 2 specs

- `specs/172-self-balancing-graph.md`
- `specs/180-self-balancing-graph.md`

### `**Spec file**: `validation-requires` — 1 spec

- `specs/**Spec file**: `validation-requires-production` (same stem as `idea_id` for registry).md`

### `accessible` — 1 spec

- `specs/185-accessible-ontology.md`

### `adaptive-tracking` — 1 spec

- `specs/adaptive-tracking-tiers.md`

### `agent-debugging` — 1 spec

- `specs/046-agent-debugging-pipeline-stuck-task-hangs.md`

### `agent-session` — 1 spec

- `specs/agent-session-summary.md`

### `agent-sse` — 1 spec

- `specs/agent-sse-control-channel.md`

### `agent-telegram` — 1 spec

- `specs/003-agent-telegram-decision-loop.md`

### `ai-agent` — 1 spec

- `specs/113-ai-agent-biweekly-intelligence-feedback-loop.md`

### `alive-empty` — 1 spec

- `specs/170-alive-empty-state.md`

### `api-bulk` — 1 spec

- `specs/api-bulk-operations.md`

### `api-error` — 1 spec

- `specs/009-api-error-handling.md`

### `attention-economy` — 1 spec

- `specs/attention-economy-cc-flow.md`

### `auto-update` — 1 spec

- `specs/027-auto-update-framework.md`

### `automation-capacity` — 1 spec

- `specs/181-automation-capacity-garden-map.md`

### `automation-garden` — 1 spec

- `specs/181-automation-garden-map.md`

### `automation-provider` — 1 spec

- `specs/100-automation-provider-usage-readiness-api.md`

### `backlog` — 1 spec

- `specs/005-backlog.md`

### `belief` — 1 spec

- `specs/169-belief-system.md`

### `belief-systems` — 1 spec

- `specs/181-belief-systems-translation.md`

### `bot` — 1 spec

- `specs/bot-telegram.md`

### `breath-cycle` — 1 spec

- `specs/breath-cycle-phases.md`

### `cc-flow` — 1 spec

- `specs/cc-flow-on-asset-use.md`

### `check-pipeline` — 1 spec

- `specs/036-check-pipeline-hierarchical-view.md`

### `ci-noise` — 1 spec

- `specs/ci-noise-reduction.md`

### `cli-mcp` — 1 spec

- `specs/cli-mcp-surface.md`

### `cli-noninteractive` — 1 spec

- `specs/cli-noninteractive-identity.md`

### `coherence-algorithm` — 1 spec

- `specs/coherence-algorithm-engine.md`

### `coherence-cli` — 1 spec

- `specs/coherence-cli-npm.md`

### `collective-coherence` — 1 spec

- `specs/114-collective-coherence-resonance-flow-friction-health.md`

### `commit-derived` — 1 spec

- `specs/056-commit-derived-traceability-report.md`

### `commit-provenance` — 1 spec

- `specs/054-commit-provenance-contract-gate.md`

### `concept-as` — 1 spec

- `specs/concept-as-idea-registration.md`

### `concept-layer` — 1 spec

- `specs/182-concept-layer-crud.md`

### `concept-resonance` — 1 spec

- `specs/173-concept-resonance-kernel.md`

### `concept-translation` — 1 spec

- `specs/181-concept-translation-worldview-lenses.md`

### `consolidate-nav` — 1 spec

- `specs/183-consolidate-nav-pages.md`

### `consolidate-overlapping` — 1 spec

- `specs/consolidate-overlapping-pages.md`

### `contributor-leaderboard` — 1 spec

- `specs/128-contributor-leaderboard-api.md`

### `creator-economy` — 1 spec

- `specs/creator-economy-bridge.md`

### `cross-domain` — 1 spec

- `specs/179-cross-domain-concept-resonance.md`

### `cross-linked` — 1 spec

- `specs/cross-linked-presences.md`

### `crypto-treasury` — 1 spec

- `specs/122-crypto-treasury-bridge.md`

### `data-driven` — 1 spec

- `specs/136-data-driven-timeout-dashboard.md`

### `data-retention` — 1 spec

- `specs/data-retention-summarization.md`

### `db-error` — 1 spec

- `specs/db-error-tracking.md`

### `deploy` — 1 spec

- `specs/014-deploy-readiness.md`

### `deploy-latest` — 1 spec

- `specs/156-deploy-latest-to-vps.md`

### `disable-vercel` — 1 spec

- `specs/105-disable-vercel-pr-deployments.md`

### `documentation-developer` — 1 spec (idea: [developer-experience](../../ideas/developer-experience.md))

- `specs/documentation-developer-experience.md`

### `e165294430dc487b` — 1 spec

- `specs/e165294430dc487b.md`

### `effectiveness-plan` — 1 spec

- `specs/045-effectiveness-plan-progress-phase-6-7.md`

### `endpoint-traceability` — 1 spec

- `specs/089-endpoint-traceability-coverage.md`

### `external-tools` — 1 spec

- `specs/106-external-tools-audit-stability.md`

### `federated-instance` — 1 spec

- `specs/143-federated-instance-aggregation.md`

### `federation-aggregated` — 1 spec

- `specs/federation-aggregated-visibility-followup-how-can-we-improve-this-idea-show-whet.md`

### `federation-node` — 1 spec

- `specs/132-federation-node-identity.md`

### `financial-integration` — 1 spec

- `specs/financial-integration-fiat-bridge.md`

### `friction` — 1 spec

- `specs/050-friction-analysis.md`

### `full-code` — 1 spec

- `specs/181-full-code-traceability.md`

### `fully-automated` — 1 spec

- `specs/027-fully-automated-pipeline.md`

### `geo` — 1 spec

- `specs/170-geo-location.md`

### `geolocation-awareness` — 1 spec

- `specs/geolocation-awareness-geocoding.md`

### `github-api` — 1 spec

- `specs/029-github-api-integration.md`

### `glossary` — 1 spec

- `specs/035-glossary.md`

### `graph-store` — 1 spec

- `specs/019-graph-store-abstraction.md`

### `greenfield-autonomous` — 1 spec

- `specs/111-greenfield-autonomous-intelligence-system.md`

### `health` — 1 spec

- `specs/001-health-check.md`

### `holdout` — 1 spec

- `specs/016-holdout-tests.md`

### `homepage-readability` — 1 spec

- `specs/150-homepage-readability-contrast.md`

### `host-contribution` — 1 spec

- `specs/host-contribution-tracking.md`

### `idea-c3731991380b` — 1 spec

- `specs/idea-c3731991380b-automation-garden-map.md`

### `idea-fecc6d087c4e` — 1 spec

- `specs/idea-fecc6d087c4e-mcp-npm-pypi-publish.md`

### `idea-full` — 1 spec

- `specs/idea-full-traceability.md`

### `idea-tagging` — 1 spec

- `specs/129-idea-tagging-system.md`

### `ideas-page` — 1 spec

- `specs/159-ideas-page-lead-with-ideas.md`

### `identity-37` — 1 spec

- `specs/identity-37-providers.md`

### `implementation-request` — 1 spec

- `specs/081-implementation-request-question-task-sync.md`

### `improvement-as` — 1 spec

- `specs/improvement-as-contribution.md`

### `invest-page` — 1 spec

- `specs/181-invest-page-garden-metaphor.md`

### `landing-page` — 1 spec

- `specs/082-landing-page-contributor-onboarding.md`

### `langgraph-stateschema` — 1 spec

- `specs/110-langgraph-stateschema-adoption.md`

### `legacy-commit` — 1 spec

- `specs/087-legacy-commit-cost-ui-normalization.md`

### `live-gate` — 1 spec

- `specs/084-live-gate-tests-without-mocks.md`

### `maintainability-architecture` — 1 spec

- `specs/090-maintainability-architecture-and-placeholder-gate.md`

### `mcp-npm` — 1 spec

- `specs/186-mcp-npm-pypi-publish.md`

### `mcp-registry` — 1 spec

- `specs/178-mcp-registry-submission.md`

### `merge-runners` — 1 spec

- `specs/merge-runners-single-file.md`

### `meta-pipeline` — 1 spec

- `specs/007-meta-pipeline-backlog.md`

### `metadata-self` — 1 spec

- `specs/metadata-self-discovery.md`

### `minimum-federation` — 1 spec

- `specs/120-minimum-federation-layer.md`

### `my-portfolio` — 1 spec

- `specs/186-my-portfolio-personal-view.md`

### `n8n-security` — 1 spec

- `specs/108-n8n-security-and-hitl-hardening.md`

### `node-capability` — 1 spec

- `specs/137-node-capability-discovery.md`

### `node-message` — 1 spec

- `specs/node-message-bus.md`

### `nonblocking-monitoring` — 1 spec

- `specs/104-nonblocking-monitoring-workflows.md`

### `open-responses` — 1 spec

- `specs/109-open-responses-interoperability-layer.md`

### `openclaw-bidirectional` — 1 spec

- `specs/156-openclaw-bidirectional-messaging.md`

### `openclaw-idea` — 1 spec

- `specs/121-openclaw-idea-marketplace.md`

### `openclaw-inbox` — 1 spec

- `specs/149-openclaw-inbox-session-protocol.md`

### `openclaw-node` — 1 spec

- `specs/openclaw-node-bridge.md`

### `opencode-canary` — 1 spec

- `specs/opencode-canary-validation.md`

### `ops` — 1 spec

- `specs/034-ops-runbook.md`

### `orchestration-guidance` — 1 spec

- `specs/112-orchestration-guidance-awareness.md`

### `organic-discovery` — 1 spec

- `specs/organic-discovery-replaces-marketing.md`

### `oss-interface` — 1 spec

- `specs/140-oss-interface-alignment.md`

### `overnight` — 1 spec

- `specs/006-overnight-backlog.md`

### `parallel-by` — 1 spec

- `specs/028-parallel-by-phase-pipeline.md`

### `persistent-store` — 1 spec

- `specs/080-persistent-store-test-contributor-guard.md`

### `phase-1` — 1 spec

- `specs/026-phase-1-task-metrics.md`

### `pipeline-data` — 1 spec

- `specs/pipeline-data-flow-fixes.md`

### `pipeline-deploy` — 1 spec

- `specs/pipeline-deploy-phase.md`

### `pipeline-full` — 1 spec

- `specs/030-pipeline-full-automation.md`

### `pipeline-status` — 1 spec

- `specs/039-pipeline-status-empty-state-200.md`

### `placeholder` — 1 spec

- `specs/015-placeholder.md`

### `portfolio-cockpit` — 1 spec

- `specs/052-portfolio-cockpit-ui.md`

### `proof-based` — 1 spec

- `specs/proof-based-validation.md`

### `provider-model` — 1 spec

- `specs/provider-model-registry.md`

### `provider-readiness` — 1 spec

- `specs/096-provider-readiness-contract-automation.md`

### `public-e2e` — 1 spec

- `specs/095-public-e2e-flow-gate-automation.md`

### `public-validation` — 1 spec

- `specs/113-public-validation-gates-api.md`

### `public-walkable` — 1 spec

- `specs/072-public-walkable-flow-parity.md`

### `pypi` — 1 spec

- `specs/024-pypi-indexing.md`

### `question-answering` — 1 spec

- `specs/051-question-answering-and-minimum-e2e-flow.md`

### `rate-limited` — 1 spec

- `specs/rate-limited-preview-steers-tracking.md`

### `readme-quick` — 1 spec

- `specs/033-readme-quick-start-qualify.md`

### `referral-as` — 1 spec

- `specs/referral-as-contribution.md`

### `request` — 1 spec

- `specs/010-request-validation.md`

### `requirements-txt` — 1 spec

- `specs/025-requirements-txt-import.md`

### `resonance-alive` — 1 spec

- `specs/169-resonance-alive-empty-state.md`

### `resonant-tracking` — 1 spec

- `specs/resonant-tracking-incentives.md`

### `runner-pipeline` — 1 spec

- `specs/runner-pipeline-health.md`

### `runner-self` — 1 spec

- `specs/runner-self-update.md`

### `runtime-intent` — 1 spec

- `specs/055-runtime-intent-and-public-e2e-contract-gate.md`

### `self-aware` — 1 spec

- `specs/self-aware-sensing-organism.md`

### `setup-troubleshooting` — 1 spec

- `specs/031-setup-troubleshooting-venv.md`

### `shared-asset` — 1 spec

- `specs/shared-asset-tracking.md`

### `silent-failure` — 1 spec

- `specs/silent-failure-detection.md`

### `smart-reap` — 1 spec

- `specs/smart-reap-diagnose-resume.md`

### `social-platform` — 1 spec

- `specs/167-social-platform-bots.md`

### `source-to` — 1 spec

- `specs/source-to-idea-lineage.md`

### `spec-coverage` — 1 spec

- `specs/030-spec-coverage-update.md`

### `spec-process` — 1 spec

- `specs/088-spec-process-implementation-validation-flow.md`

### `spec-verification` — 1 spec

- `specs/spec-verification-upgrade.md`

### `split-review` — 1 spec

- `specs/split-review-into-phases.md`

### `sprint-0` — 1 spec

- `specs/007-sprint-0-landing.md`

### `sprint-1` — 1 spec

- `specs/008-sprint-1-graph-foundation.md`

### `sprint-2` — 1 spec

- `specs/020-sprint-2-coherence-api.md`

### `sprint0-graph` — 1 spec

- `specs/sprint0-graph-foundation-indexer-api.md`

### `sse-agent` — 1 spec

- `specs/sse-agent-control-channel.md`

### `sse-native` — 1 spec

- `specs/sse-native-agent-control-channel.md`

### `start-gate` — 1 spec

- `specs/115-start-gate-continuation-and-hosted-worker-proof.md`

### `system-lineage` — 1 spec

- `specs/049-system-lineage-inventory-and-runtime-telemetry.md`

### `system-self` — 1 spec

- `specs/system-self-discovery.md`

### `task_0145d2767bd35a0d` — 1 spec

- `specs/task_0145d2767bd35a0d.md`

### `task_0218b79e7b63ee6b` — 1 spec

- `specs/task_0218b79e7b63ee6b.md`

### `task_0ac213ec7b80d275` — 1 spec

- `specs/task_0ac213ec7b80d275.md`

### `task_0c91997f1ad03156` — 1 spec

- `specs/task_0c91997f1ad03156.md`

### `task_0f6beb214878ad87` — 1 spec

- `specs/task_0f6beb214878ad87.md`

### `task_1584e336bc395a81` — 1 spec

- `specs/task_1584e336bc395a81.md`

### `task_2bfd59d1e7156ad1` — 1 spec

- `specs/task_2bfd59d1e7156ad1.md`

### `task_301592eda8fb3e03` — 1 spec

- `specs/task_301592eda8fb3e03.md`

### `task_3111bb8447ba6cfb` — 1 spec

- `specs/task_3111bb8447ba6cfb.md`

### `task_3610e59a86ceadce` — 1 spec

- `specs/task_3610e59a86ceadce.md`

### `task_3c58d78ff98f9abd` — 1 spec

- `specs/task_3c58d78ff98f9abd.md`

### `task_3cb2649ca953cf2b` — 1 spec

- `specs/task_3cb2649ca953cf2b.md`

### `task_3d0ac3e0921ec81a` — 1 spec

- `specs/task_3d0ac3e0921ec81a.md`

### `task_43f1117b83ad0eb2` — 1 spec

- `specs/task_43f1117b83ad0eb2.md`

### `task_44ce8329e73eb5b0` — 1 spec

- `specs/task_44ce8329e73eb5b0.md`

### `task_47b6f48b350aabc5` — 1 spec

- `specs/task_47b6f48b350aabc5.md`

### `task_5005632aa6b487b7` — 1 spec

- `specs/task_5005632aa6b487b7.md`

### `task_50a6e725680b18e3` — 1 spec

- `specs/task_50a6e725680b18e3.md`

### `task_568bd9ca41fd0dcf` — 1 spec

- `specs/task_568bd9ca41fd0dcf.md`

### `task_588507d48375713f` — 1 spec

- `specs/task_588507d48375713f.md`

### `task_5cb9d9ff27681827` — 1 spec

- `specs/task_5cb9d9ff27681827.md`

### `task_6313cc742c4d9739` — 1 spec

- `specs/task_6313cc742c4d9739.md`

### `task_6346e0df6428e09b` — 1 spec

- `specs/task_6346e0df6428e09b.md`

### `task_66c7373e2e4892ca` — 1 spec

- `specs/task_66c7373e2e4892ca.md`

### `task_73353535960bdea2` — 1 spec

- `specs/task_73353535960bdea2.md`

### `task_73e6498051df944f` — 1 spec

- `specs/task_73e6498051df944f.md`

### `task_74074f3dc4c3b246` — 1 spec

- `specs/task_74074f3dc4c3b246.md`

### `task_7c82e1901f83aafe` — 1 spec

- `specs/task_7c82e1901f83aafe.md`

### `task_7de286c308d78f97` — 1 spec

- `specs/task_7de286c308d78f97.md`

### `task_831eba0fc342aeb9` — 1 spec

- `specs/task_831eba0fc342aeb9.md`

### `task_85e4058296dee117` — 1 spec

- `specs/task_85e4058296dee117.md`

### `task_8fb002e966d45f76` — 1 spec

- `specs/task_8fb002e966d45f76.md`

### `task_9460b68fbf0e81f5` — 1 spec

- `specs/task_9460b68fbf0e81f5.md`

### `task_948aa5fed3ed69f0` — 1 spec

- `specs/task_948aa5fed3ed69f0.md`

### `task_957a8a7e00501874` — 1 spec

- `specs/task_957a8a7e00501874.md`

### `task_99ebbbbf852dfff6` — 1 spec

- `specs/task_99ebbbbf852dfff6.md`

### `task_9cdf923eb7a29457` — 1 spec

- `specs/task_9cdf923eb7a29457.md`

### `task_9d0bc336699bda69` — 1 spec

- `specs/task_9d0bc336699bda69.md`

### `task_a3b9ebf271f19b5d` — 1 spec

- `specs/task_a3b9ebf271f19b5d.md`

### `task_a48f6e7eaf85e811` — 1 spec

- `specs/task_a48f6e7eaf85e811.md`

### `task_a50fa999fdddd444` — 1 spec

- `specs/task_a50fa999fdddd444.md`

### `task_a53eff65d08fad5f` — 1 spec

- `specs/task_a53eff65d08fad5f.md`

### `task_a58cac25401b5d34` — 1 spec

- `specs/task_a58cac25401b5d34.md`

### `task_a65c34cb403c35a6` — 1 spec

- `specs/task_a65c34cb403c35a6.md`

### `task_ac3a01c45e385457` — 1 spec

- `specs/task_ac3a01c45e385457.md`

### `task_ad1705c62ca9c76d` — 1 spec

- `specs/task_ad1705c62ca9c76d.md`

### `task_ad7874ff3e085e36` — 1 spec

- `specs/task_ad7874ff3e085e36.md`

### `task_b1dc9bcb70271052` — 1 spec

- `specs/task_b1dc9bcb70271052.md`

### `task_b3a301192ba99cc3` — 1 spec

- `specs/task_b3a301192ba99cc3.md`

### `task_b605232289da6daf` — 1 spec

- `specs/task_b605232289da6daf.md`

### `task_bd7d2e9bf6638f27` — 1 spec

- `specs/task_bd7d2e9bf6638f27.md`

### `task_bd9d4e78050da0c2` — 1 spec

- `specs/task_bd9d4e78050da0c2.md`

### `task_c41bb1c360c06d9c` — 1 spec

- `specs/task_c41bb1c360c06d9c.md`

### `task_c50d4bbc1df581dc` — 1 spec

- `specs/task_c50d4bbc1df581dc.md`

### `task_c7eb6f1390fdaec9` — 1 spec

- `specs/task_c7eb6f1390fdaec9.md`

### `task_cc39be1e81c4f663` — 1 spec

- `specs/task_cc39be1e81c4f663.md`

### `task_ce06deb4e7944a33` — 1 spec

- `specs/task_ce06deb4e7944a33.md`

### `task_ce07a558035576f9` — 1 spec

- `specs/task_ce07a558035576f9.md`

### `task_d04f93663743f5e8` — 1 spec

- `specs/task_d04f93663743f5e8.md`

### `task_d23c632f30ac3501` — 1 spec

- `specs/task_d23c632f30ac3501.md`

### `task_d488be6308527250` — 1 spec

- `specs/task_d488be6308527250.md`

### `task_db6bddf6664e5db0` — 1 spec

- `specs/task_db6bddf6664e5db0.md`

### `task_db97e8e02d420314` — 1 spec

- `specs/task_db97e8e02d420314.md`

### `task_e02a05d8d4599b1d` — 1 spec

- `specs/task_e02a05d8d4599b1d.md`

### `task_e4946662cb9deb3a` — 1 spec

- `specs/task_e4946662cb9deb3a.md`

### `task_e647f5766a54f6f1` — 1 spec

- `specs/task_e647f5766a54f6f1.md`

### `task_edfa105d1d6ae46c` — 1 spec

- `specs/task_edfa105d1d6ae46c.md`

### `task_efcbfe10cbf5b359` — 1 spec

- `specs/task_efcbfe10cbf5b359.md`

### `task_f0b27e390a5aa4ee` — 1 spec

- `specs/task_f0b27e390a5aa4ee.md`

### `task_f4a9da594102d8e0` — 1 spec

- `specs/task_f4a9da594102d8e0.md`

### `task_f576c873b5af86d3` — 1 spec

- `specs/task_f576c873b5af86d3.md`

### `task_fb1085907b2f5f51` — 1 spec

- `specs/task_fb1085907b2f5f51.md`

### `task_fbceb79ee5d481d5` — 1 spec

- `specs/task_fbceb79ee5d481d5.md`

### `task_fc3bb95cb540f270` — 1 spec

- `specs/task_fc3bb95cb540f270.md`

### `tasks-page` — 1 spec

- `specs/155-tasks-page-fetch-error.md`

### `test` — 1 spec

- `specs/test-idea.md`

### `test-backlog` — 1 spec

- `specs/test-backlog-cursor.md`

### `third-party` — 1 spec

- `specs/third-party-audit-certification.md`

### `tool-result` — 1 spec

- `specs/tool-result-as-asset.md`

### `tracked-count` — 1 spec

- `specs/085-tracked-count-parity-and-source-discovery.md`

### `transparent-audit` — 1 spec

- `specs/123-transparent-audit-ledger.md`

### `ucore-daily` — 1 spec

- `specs/ucore-daily-engagement-skill.md`

### `ucore-event` — 1 spec

- `specs/ucore-event-streaming.md`

### `ui-alignment` — 1 spec

- `specs/076-ui-alignment-overhaul.md`

### `unknown` — 1 spec

- `specs/unknown.md`

### `ux-contributor` — 1 spec (idea: [contributor-experience](../../ideas/contributor-experience.md))

- `specs/ux-contributor-experience.md`

### `ux-my` — 1 spec

- `specs/ux-my-portfolio.md`

### `ux-new` — 1 spec

- `specs/ux-new-contributor-orientation.md`

### `ux-resonance` — 1 spec

- `specs/ux-resonance-empty-state.md`

### `ux-tasks` — 1 spec

- `specs/156-ux-tasks-page-broken.md`

### `ux-value` — 1 spec

- `specs/ux-value-lineage-visualization.md`

### `ux-web` — 1 spec

- `specs/156-ux-web-ecosystem-links.md`

### `validation` — 1 spec

- `specs/validation-categories.md`

### `validation-quality` — 1 spec

- `specs/validation-quality-gates.md`

### `validation-requires` — 1 spec

- `specs/validation-requires-production.md`

### `vision-asset` — 1 spec

- `specs/vision-asset-economy.md`

### `visual-asset` — 1 spec

- `specs/visual-asset-nft-tracking.md`

### `walkable-flow` — 1 spec

- `specs/073-walkable-flow-runtime-mismatch-fixes.md`

### `web-audit` — 1 spec

- `specs/156-web-audit-findings-2026-03-24.md`

### `web-import` — 1 spec

- `specs/023-web-import-stack-ui.md`

### `web-live` — 1 spec

- `specs/091-web-live-refresh-and-link-parity.md`

### `web-news` — 1 spec

- `specs/web-news-resonance-page.md`

### `web-project` — 1 spec

- `specs/021-web-project-search-ui.md`

### `web-refresh` — 1 spec

- `specs/092-web-refresh-reliability-and-route-completeness.md`

### `web-theme` — 1 spec

- `specs/093-web-theme-auto-detection.md`

### `worldview` — 1 spec

- `specs/182-worldview-translation.md`

### `worldview-translation` — 1 spec

- `specs/183-worldview-translation-engine.md`

