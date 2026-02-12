# Meta-Pipeline Backlog

Work that improves the pipeline itself. Runs through the same spec→impl→test→review flow. See [docs/EXECUTION-PLAN.md](../docs/EXECUTION-PLAN.md).

**Full automation priority (Feb 2026):** Items 1–5 close meta-level gaps; items 6+ are general pipeline improvement.

## Items

### Full Automation (Prioritized)

1. **Progress toward PLAN metric:** Add to GET /api/agent/effectiveness: `plan_progress` with Phase 6/7 completion (from PM state or backlog) so we measure progress toward PLAN.md goals → spec [045-effectiveness-plan-progress-phase-6-7.md](045-effectiveness-plan-progress-phase-6-7.md)
2. **Heal completion → issue resolution:** When a heal task completes and its related monitor condition clears on next check, ensure monitor records resolution; optionally auto-resolve the issue in monitor_issues.json → spec [047-heal-completion-issue-resolution.md](047-heal-completion-issue-resolution.md)
3. **Meta-questions periodic check:** Add script or monitor extension that runs META-QUESTIONS checklist periodically; log answers to api/logs/meta_questions.json; surface "unanswered" or "failed" in status-report
4. **Backlog alignment check:** Add monitor rule or effectiveness field: verify backlog items (from 006) map to PLAN phases; flag if Phase 6/7 items not being worked
5. **Heal task effectiveness tracking:** Record which heal task addressed which issue; when condition clears, attribute to heal; add to metrics "heal_resolved_count"

### Pipeline Improvement (General)

6. Write spec 027-auto-update-framework: script to update SPEC-COVERAGE and STATUS when tests pass; CI integration
7. Implement spec 027: update_spec_coverage.py; wire in CI
8. Implement spec 026 Phase 1: persist task metrics; GET /api/agent/metrics
9. Add attention heuristics to pipeline-status (stuck, repeated failures)
10. Add hierarchical view to check_pipeline (goal → PM → tasks → artifacts)
11. Set up GitHub Discussions as public forum; add "Join the conversation" to README
12. Add meta-pipeline items to overnight backlog rotation (20% capacity)
