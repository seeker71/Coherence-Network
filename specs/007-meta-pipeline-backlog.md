# Meta-Pipeline Backlog

Work that improves the pipeline itself. Runs through the same spec→impl→test→review flow. See [docs/EXECUTION-PLAN.md](../docs/EXECUTION-PLAN.md).

## Items

1. Write spec 027-auto-update-framework: script to update SPEC-COVERAGE and STATUS when tests pass; CI integration
2. Implement spec 027: update_spec_coverage.py; wire in CI
3. Implement spec 026 Phase 1: persist task metrics; GET /api/agent/metrics
4. Add attention heuristics to pipeline-status (stuck, repeated failures)
5. Add hierarchical view to check_pipeline (goal → PM → tasks → artifacts)
6. Set up GitHub Discussions as public forum; add "Join the conversation" to README
7. Add meta-pipeline items to overnight backlog rotation (20% capacity)
