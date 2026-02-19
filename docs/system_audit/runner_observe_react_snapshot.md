# Runner Observe/React Snapshot

Generated at: 2026-02-19T08:12:01.795696+00:00

## Highest-signal recent evidence (agent pipeline idea)
1. `docs/system_audit/commit_evidence_2026-02-17_postgres-tracking-metrics-migration.json` refs=7 intent=runtime_feature :: Migrate file-based tracking domains (commit evidence, telemetry, ideas/specs, and graph entities for assets/contributors/contributions) to PostgreSQL-backed per
2. `docs/system_audit/commit_evidence_2026-02-17_agent-and-environment-contract.json` refs=5 intent=process_only :: Align AGENTS.md and .codex environment configuration with mandatory worktree/start/pre-commit/CI+deploy follow-through contract.
3. `docs/system_audit/commit_evidence_2026-02-17_openclaw-executor-config.json` refs=4 intent=runtime_fix :: Treat openclaw as an executor label, not a standalone provider: attribute usage to the underlying provider/model (e.g. openrouter), stop requiring OPENCLAW_API_
4. `docs/system_audit/commit_evidence_2026-02-17_openclaw-paid-usage-validation.json` refs=4 intent=runtime_fix :: Refactor agent routing into a dedicated service with explicit executor/model/provider decisions, add route diagnostics, and enforce free-vs-paid provider classi
5. `docs/system_audit/commit_evidence_2026-02-17_automation-endpoint-spec-traceability.json` refs=4 intent=process_only :: Link automation usage/readiness endpoints to a tracked spec and enforce endpoint->spec traceability via canonical route metadata and inventory checks.
6. `docs/system_audit/commit_evidence_2026-02-17_mandatory-delivery-contract-agents.json` refs=4 intent=process_only :: Add mandatory delivery contract to AGENTS.md so all threads consistently use worktree-only execution, required start/pre-commit gates, PR/CI follow-through, and
7. `docs/system_audit/commit_evidence_2026-02-17_public-deploy-health-proxy-unknown-warning.json` refs=3 intent=runtime_fix :: Treat unknown web health-proxy SHA as a warning so public deploy contract can pass when API health and main-head SHA checks are already green.
8. `docs/system_audit/commit_evidence_2026-02-17_provider-usage-tracking.json` refs=3 intent=runtime_fix :: Harden provider usage/readiness probes: parse RFC9233 rate-limit headers (e.g. ratelimit-limit: 1000;w=3600), broaden recognized rate-limit header keys for Open
9. `docs/system_audit/commit_evidence_2026-02-17_tasks-ui-runtime-backfill.json` refs=3 intent=runtime_fix :: Fix Tasks UI emptiness across deploy restarts by backfilling agent tasks from persisted runtime completion events; adjust CI evidence enforcement to run on PRs 
10. `docs/system_audit/commit_evidence_2026-02-17_pr-check-failure-triage-automation.json` refs=3 intent=process_only :: Document and automate PR check failure detection with remediation mapping and scheduled triage workflow that retries flaky failed actions checks.
11. `docs/system_audit/commit_evidence_2026-02-19_agent-manifest-provenance.json` refs=3 intent=process_only :: Add runner-managed AGENT.md manifestation provenance so generated code blocks are linked to line ranges, idea links, and source document references.
12. `docs/system_audit/commit_evidence_2026-02-16_task-claim-tracking-roi-dedupe.json` refs=2 intent=runtime_feature :: track task claim ownership and prevent ROI auto-pick duplicate work across parallel contributors

## Observe -> React policy hints
- Observe: track repeated failures and long hold patterns before increasing retry cadence.
- React: request one targeted diagnostic on repeated failure class instead of blind retries.
- Escalate: when hold pattern persists, switch to needs_decision with context snapshot.
