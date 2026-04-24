---
idea_id: agent-cli
status: active
source:
  - file: cli/package.json
    symbols: [bin]
  - file: cli/bin/cc.mjs
    symbols: [file rename → coh.mjs]
  - file: cli/README.md
    symbols: [installation instructions, usage examples]
  - file: CLAUDE.md
    symbols: [Quick Lookup table, Key Conventions, Agent Guardrails]
requirements:
  - "R1: Remove `cc` from cli/package.json bin map; keep `coh` and `coherence` as registered binaries"
  - "R2: Rename cli/bin/cc.mjs → cli/bin/coh.mjs; update bin map path accordingly"
  - "R3: Update CLAUDE.md — replace every `cc <command>` example with `coh <command>`"
  - "R4: Update cli/README.md — coh as primary command, npx coherence-cli as zero-install path, cc deprecation note"
  - "R5: Add macOS conflict-detection block in cli/bin/coh.mjs — warn once if /usr/bin/cc resolves to Apple clang in PATH before coh"
  - "R6: Document npx coherence-cli as the canonical zero-conflict invocation path in README and CLAUDE.md"
done_when:
  - "`npm exec --package=coherence-cli coh ideas` exits 0 (or returns JSON/table output)"
  - "`cc --version` on a clean macOS shell still invokes Apple clang, not coherence-cli"
  - "`coh --help` prints coherence-cli help text"
  - "`npx coherence-cli ideas` exits 0"
  - "CLAUDE.md contains no bare `cc <command>` references (grep shows 0 matches for `cc ` as CLI invocation)"
  - "cli/bin/cc.mjs no longer exists in the repo"
test: "cd cli && node bin/coh.mjs --help"
constraints:
  - "Do NOT break `coherence` alias — it is a backward-compatible entry point for scripts"
  - "Conflict-detection warning is advisory only — must not block execution"
  - "No changes to the npm package name (`coherence-cli`) or registry entry"
  - "No API changes — this is purely a CLI surface change"
---

# Spec: CLI Binary Name Conflict — Rename `cc` → `coh`

## Purpose

`npm install -g coherence-cli` registers `cc` as a global binary, which shadows `/usr/bin/cc` (Apple clang) on macOS. Any developer or agent that types `cc` expecting the Coherence CLI silently invokes the C compiler instead — or vice versa. The fix promotes `coh` (already present as an alias in v0.12.1) to the sole primary binary, removes `cc` from the bin map, and updates all documentation to reflect the new canonical command.

This is primarily a cleanup and promotion, not a new feature. The `coh` binary already works today; this spec formalizes its primacy, retires the conflicting name, and makes the zero-install path (`npx coherence-cli`) a first-class recommendation.

## Requirements

- [ ] **R1 — Remove `cc` from bin map**: Delete the `"cc": "bin/cc.mjs"` entry from `cli/package.json`. After this change, only `coh` and `coherence` are registered as bin executables. This prevents the npm global install from shadowing `/usr/bin/cc` on macOS.

- [ ] **R2 — Rename entry point file**: Rename `cli/bin/cc.mjs` to `cli/bin/coh.mjs`. Update the `bin` map in `cli/package.json` so both `coh` and `coherence` point to `bin/coh.mjs`. The file rename makes it clear which binary is primary when browsing the repo.

- [ ] **R3 — Update CLAUDE.md**: Replace every bare `cc <command>` invocation reference with `coh <command>`. The Quick Lookup table, Key Conventions, Agent Guardrails, and any workflow examples must use `coh`. The goal: `grep -n "^| cc\|= cc\b" CLAUDE.md` returns zero matches.

- [ ] **R4 — Update cli/README.md**: Change installation section to show `coh` as the primary command after global install. Add a callout at the top recommending `npx coherence-cli` for first-time or one-off use. Add a short deprecation note: "The `cc` binary was removed in v0.13.0 to avoid shadowing Apple's C compiler on macOS. Use `coh` instead."

- [ ] **R5 — macOS conflict-detection warning**: In `cli/bin/coh.mjs`, at startup, check whether `process.platform === 'darwin'`. If yes, and the first `cc`-like binary in PATH is NOT coherence-cli, print a one-time advisory to stderr: `[coherence-cli] Tip: the old 'cc' binary has been retired. Use 'coh' or 'npx coherence-cli'.` Write a marker file (`~/.coherence-network/.cc-conflict-warned`) so the warning fires at most once per machine.

- [ ] **R6 — npx as canonical zero-install path**: In both `cli/README.md` and `CLAUDE.md`, add `npx coherence-cli <command>` as the first usage example before the global-install examples. This surfaces the zero-conflict path prominently for agents and new users.

## Research Inputs

- `2026-04-24` — cli/package.json v0.12.1 — confirms `coh` already present as alias; `cc` still registered alongside it
- `2026-04-24` — ideas/agent-cli.md — "cc shadows Apple clang" listed as a known friction point in the Problem section

## API Contract

No API changes. This spec is entirely CLI surface.

## Data Model

No data model changes.

## Files to Create/Modify

- `cli/package.json` — remove `"cc"` entry from `bin`; update `coh` and `coherence` paths to `bin/coh.mjs`
- `cli/bin/cc.mjs` → `cli/bin/coh.mjs` — rename file (git mv); add macOS conflict-detection warning block at startup
- `cli/README.md` — update installation section, add npx callout, add cc deprecation note
- `CLAUDE.md` — replace all bare `cc <command>` CLI examples with `coh <command>`; add `npx coherence-cli` as primary invocation in Quick Lookup

## Acceptance Tests

No automated test file is needed for this spec — the done_when criteria are verified by shell commands (see Verification below). If a test file exists for CLI smoke tests, extend it with a `coh --help` exit-0 assertion.

## Verification Scenarios

### Scenario 1 — `coh` works as primary command

```bash
# After global install of the updated package:
coh --help
# Expected: prints coherence-cli help text, exits 0
# NOT expected: "command not found" or Apple clang output
```

### Scenario 2 — `cc` no longer routes to coherence-cli on macOS

```bash
# On macOS with Xcode CLT installed:
which cc
# Expected: /usr/bin/cc  (Apple clang)
cc --version
# Expected: "Apple clang version X.Y.Z ..."
# NOT expected: coherence-cli help or error about unknown flag
```

### Scenario 3 — `npx coherence-cli` zero-install path

```bash
# Without global install:
npx coherence-cli ideas
# Expected: table or JSON of ideas, exits 0
# Proves that zero-install invocation works without binary conflict
```

### Scenario 4 — `coherence` alias preserved

```bash
# After global install:
coherence --help
# Expected: identical to `coh --help` output, exits 0
# Ensures backward-compatible alias is unbroken
```

### Scenario 5 — CLAUDE.md contains no bare `cc` CLI invocations

```bash
grep -n " cc " CLAUDE.md | grep -v "Apple\|clang\|/usr/bin\|#\|coherence-cli\|binary"
# Expected: zero matches
# All CLI usage examples in CLAUDE.md use `coh` or `npx coherence-cli`
```

## Out of Scope

- Changing the npm package name (`coherence-cli`) — the package name is separate from the binary name and is already conflict-free
- Updating MCP server tooling — MCP tools are invoked by name inside agents, not via shell binary
- Changing the API base URL or any backend behavior
- Adding automated CI checks for binary conflict — advisory warning is sufficient

## Risks and Assumptions

- **Risk — scripts hard-coded to `cc`**: Any agent or developer script using `cc <command>` will break silently after upgrading. Mitigation: the conflict-detection warning in R5 fires once on first `coh` run to remind users; the README deprecation note is explicit.
- **Risk — Homebrew or other package managers**: If coherence-cli is installed via a non-npm path that still registers `cc`, this spec does not address that path. Assumption: npm global install is the only supported installation method.
- **Assumption — `coh` is memorable enough**: `coh` is short and distinct. If user research shows confusion, `cn` remains an option but is out of scope here.
- **Assumption — macOS is the only affected platform**: Linux and Windows do not ship `/usr/bin/cc` as Apple clang. The conflict-detection warning is macOS-only (guarded by `process.platform`).
