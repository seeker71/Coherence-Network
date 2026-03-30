# Integrated Execution Plan

## Goal

Run one continuous loop that improves both product delivery and delivery mechanics:

- ship scoped spec-backed features,
- measure results,
- detect issues early,
- heal or re-route work quickly,
- keep docs/status artifacts accurate.

## Execution Loop

1. **Backlog selection** (project manager)
2. **Task execution** (agent runner)
3. **Validation** (tests + CI)
4. **Monitoring** (status + attention rules)
5. **Correction** (heal, retry, or decision gate)
6. **Documentation sync** (status/coverage updates)

## Delivery Streams

### Stream A: Product
- API and graph feature delivery
- Search/coherence/import workflows
- Web support for shipped endpoints

### Stream B: Pipeline
- task routing quality
- runtime reliability
- attention heuristics
- auto-recovery readiness

### Stream C: Operational Clarity
- runbook quality
- status-report consistency
- spec/test/doc traceability

## Success Metrics

- Pipeline success rate
- Mean time to detect failures
- Mean time to recovery
- Throughput (completed tasks per run)
- Spec coverage completeness

## Guardrails

- Spec is the implementation contract.
- Tests are the merge gate.
- Monitoring must surface actionable signals.
- Any repeated failure pattern must produce a follow-up fix task.

## Related Documents

- [PLAN](PLAN.md)
- [STATUS](STATUS.md)
- [PIPELINE-ATTENTION](PIPELINE-ATTENTION.md)
- [PIPELINE-MONITORING-AUTOMATED](PIPELINE-MONITORING-AUTOMATED.md)
- [RUNBOOK](RUNBOOK.md)
