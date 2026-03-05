# Minimal Execution Packet (Review Template)

## Objective

Summarize the packet in one sentence for the next maintainer: what changed, why, and how it was validated.

## Scoped Change

- Files changed: ``
- Constraints observed: no extra files, minimal diff, explicit command/output proof only

## Validation Commands

1. `make start-gate` (or project equivalent gate command)
2. `rg -n "^(## )?(Objective|Scoped Change|Validation Commands|Validation Results|Claim-to-PLAN\.md Mapping)" <packet file>`
3. `rg -n "graph/API correctness|pipeline throughput and recovery|operational clarity for maintainers" <packet file> docs/PLAN.md`

## Validation Results

- Command 1: ``
- Command 2: ``
- Command 3: ``

## Claim-to-PLAN.md Mapping

| Claim | PLAN.md goal | Evidence command/result |
|---|---|---|
| Packet enforces correctness-first review | `graph/API correctness` | `rg` check #2 confirms required section headers and mapping keys |
| Packet requires command/result proof for throughput learning | `pipeline throughput and recovery` | `rg` check #2 confirms validation/result headers and evidence row |
| Packet standardizes reviewer visibility | `operational clarity for maintainers` | `rg` check #2 confirms explicit claim-to-goal mapping row |
