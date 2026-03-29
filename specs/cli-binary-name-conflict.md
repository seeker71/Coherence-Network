# Spec: CLI Binary Name Conflict — Rename `cc` to `coh` (or add alias)

## Purpose

`npm i -g coherence-cli` installs a binary named `cc`, which shadows `/usr/bin/cc` (Apple's
clang compiler wrapper) on macOS. Every developer or agent that runs `cc` in a shell that
has the npm global bin directory first in `PATH` gets the Coherence CLI instead of the
compiler. This is the first friction point encountered during onboarding and blocks macOS
contributors from using both tools.

The fix: rename the primary binary to `coh` (short, memorable, no system conflicts) while
keeping `cc` as a deprecated alias for backward compatibility during the transition period.

---

## Current State

`cli/package.json`:
```json
"bin": {
  "cc": "./bin/cc.mjs"
}
```

`cli/bin/cc.mjs` — entry point shebang: `#!/usr/bin/env node`

The binary `cc` conflicts with:
- `/usr/bin/cc` — Apple clang on macOS
- `cc` — C compiler wrapper on Linux (gcc symlink)
- Any shell alias `cc` that contributors may have set

---

## Required Changes

### 1. `cli/package.json`
```json
"bin": {
  "coh": "./bin/cc.mjs",
  "cc":  "./bin/cc.mjs"
}
```

Add both entries so existing `cc` usage keeps working. Deprecate `cc` in a future major version.

### 2. `cli/bin/cc.mjs` — deprecation warning for `cc` invocation
```js
const invokedAs = path.basename(process.argv[1]);
if (invokedAs === 'cc') {
  process.stderr.write(
    '\x1b[33m[coherence-cli] Warning: `cc` shadows the system C compiler.\n' +
    'Run `npm i -g coherence-cli` again after this release to get `coh`.\n\x1b[0m'
  );
}
```

### 3. Documentation updates
- `README.md`: Replace all `cc <command>` examples with `coh <command>`
- `CLAUDE.md`: Add note about `coh` as primary binary
- `cli/bin/cc.mjs` help text: update header from `cc — Coherence Network CLI` to `coh — Coherence Network CLI`

### 4. npm publish
After the `package.json` change, bump version to next minor (`x.y+1.0`) and publish:
```
cd cli && npm version minor && npm publish
```

---

## Files to Modify

| File | Change |
|---|---|
| `cli/package.json` | Add `"coh"` bin entry alongside `"cc"` |
| `cli/bin/cc.mjs` | Add deprecation warning when invoked as `cc`; update help header |
| `README.md` | Replace `cc` examples with `coh` |
| `CLAUDE.md` | Note `coh` as primary binary name |

---

## Verification Scenarios

### Scenario 1: `coh` resolves after install
- **Setup**: `npm i -g coherence-cli` (new version)
- **Action**: Run `coh help`
- **Expected**: CLI help output, no error
- **Edge**: `which coh` returns npm global bin path

### Scenario 2: `cc` still works (backward compat)
- **Setup**: Same install
- **Action**: Run `cc help`
- **Expected**: CLI help output + deprecation warning on stderr
- **Edge**: `cc ideas` continues to work for existing scripts

### Scenario 3: No conflict with system compiler
- **Setup**: macOS with Xcode command line tools; npm global bin in PATH
- **Action**: Run `cc --version`
- **Expected**: Coherence CLI deprecation warning + help (not clang)
- **But**: `$(which cc) --version` resolves to `/usr/bin/cc` = clang (PATH order independent)
- **Fix validated**: `coh --version` is unambiguous

### Scenario 4: CLAUDE.md reflects new name
- **Action**: `grep -i 'coh\|cc ' CLAUDE.md | head -5`
- **Expected**: Documentation references `coh` as the primary CLI binary

### Scenario 5: npm package version bumped
- **Action**: `npm show coherence-cli version`
- **Expected**: Version number higher than previous; both `cc` and `coh` listed in `bin`

---

## Risks and Assumptions

- **Existing scripts**: Any CI or runner script that calls `cc` will continue working due to the
  alias — no breaking change.
- **npm publish access**: Requires npm token with publish rights to the `coherence-cli` package.
- **PATH order**: The deprecation warning only fires when the npm bin directory is before
  `/usr/bin` in PATH — which is the problematic configuration to warn about.
- **Future breaking change**: Removing `cc` from `bin` is a breaking change; defer to a major
  version bump.

---

## Known Gaps and Follow-up Tasks

- **Shell completion**: If `cc` was registered for tab completion, `coh` needs its own
  registration (`coh completion >> ~/.zshrc`).
- **Docker images**: Agent containers that install `coherence-cli` globally may need updating
  once `cc` is removed.
- **`cc` alias removal**: Track in a follow-up idea; remove in next major version after 3-month
  deprecation window.
- **Binary verification test**: Add a CI step that asserts `which coh` succeeds after
  `npm install`.
