---
idea_id: agent-cli
title: Agent CLI
stage: implementing
work_type: feature
specs:
  - 108-unified-agent-cli-flow-patch-on-fail
  - 111-agent-execution-lifecycle-hooks
---

# Agent CLI

Local execution with lifecycle hooks and patch-on-fail recovery.

## What It Does

- All task types (spec/impl/test/review/heal) executable locally and remotely
- Patch-on-fail: when verification fails, generate a targeted fix
- Hook-first execution pattern for task lifecycle transitions
- Unified CLI flow: same commands work for all providers

## API

- CLI: `cc run`, `cc task`, `cc heal`
- Hooks: pre-execute, post-execute, on-fail

## Why It Matters

Agents need reliable local execution. Patch-on-fail reduces the retry → fail → retry loop.
