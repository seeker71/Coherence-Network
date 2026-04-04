---
idea_id: agent-cli
title: Agent CLI
stage: implementing
work_type: feature
specs:
  - [108-unified-agent-cli-flow-patch-on-fail](../specs/108-unified-agent-cli-flow-patch-on-fail.md)
  - [111-agent-execution-lifecycle-hooks](../specs/111-agent-execution-lifecycle-hooks.md)
---

# Agent CLI

Terminal and AI-agent interfaces for Coherence Network. The CLI (`coherence-cli` on npm) provides 35+ commands for humans and scripts. The MCP server provides 20 typed tools for AI agents (Claude, Cursor, Windsurf). Both interfaces share the same API backend and produce structured output suitable for automation.

## Problem

Agents and developers interact with Coherence Network through raw API calls, which is error-prone and verbose. There is no standard way to run a task locally, handle failures gracefully, or record contributions automatically. AI agents using MCP need typed tools with schema validation, not raw HTTP endpoints. The CLI binary name `cc` shadows Apple clang on macOS, causing confusion.

## Key Capabilities

- **coherence-cli (npm)**: 35+ commands covering identity, ideas, staking, forking, contributions, ops, and diagnostics. Zero external dependencies beyond Node.js. Works against the public API at `api.coherencycoin.com` or a local dev server. Commands include `cc ideas`, `cc tasks`, `cc stake`, `cc fork`, `cc ops`, `cc nodes`, `cc diagnostics`.
- **MCP server**: 20 typed tools for Claude, Cursor, Windsurf, and other MCP-compatible agents. Tools cover ideas (list, create, advance), specs (read, validate), lineage (trace value chain), identity (claim, verify), and contributions (record, query). Each tool has a JSON schema for inputs and outputs.
- **Unified agent CLI flow**: When a task fails verification, the CLI generates a targeted PATCH (not a full retry) based on the failure diagnostics. `PATCH on fail` means: read the error, generate the minimal fix, apply it, re-verify. This breaks the retry -> fail -> retry loop.
- **Agent execution lifecycle hooks**: Pre-execute hooks validate preconditions (branch is clean, spec exists, dependencies installed). Post-execute hooks record contributions, update task status, and clean up. On-fail hooks capture diagnostics and trigger auto-heal. Hooks are composable and task-type-aware.

## What Success Looks Like

- Any developer can run `npx coherence-cli ideas` and see all platform ideas within 10 seconds of first use
- AI agents using MCP can discover and call all 20 tools without manual configuration
- Failed tasks produce a targeted PATCH 80%+ of the time instead of a full retry
- Lifecycle hooks fire reliably on every task execution -- zero missed contributions

## Absorbed Ideas

- **coherence-mcp-server**: MCP server exposing ideas, specs, lineage, identity, contributions as typed tools for AI agents. Published on Smithery, Glama, PulseMCP for discovery. Agents can browse ideas, read specs, trace value lineage, and record contributions without leaving their IDE.
- **coherence-cli-npm**: Node.js CLI with identity-first onboarding, idea browsing, staking, forking. Zero dependencies, works against public API. Published on npm as `coherence-cli` with global install support.
- **cli-binary-name-conflict**: `cc` shadows Apple clang (`/usr/bin/cc`) on macOS. Developers who type `cc` expecting the Coherence CLI instead invoke the C compiler. Needs alias or rename to `coh` or `cn` to avoid the conflict.
