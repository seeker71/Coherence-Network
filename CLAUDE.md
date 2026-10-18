# Coherence Network

Coherence Network is an open intelligence organism in which ideas, people,
agents, source, runtime proof, teachings, and value flows share one inspectable
body.

## Arrival

Begin with `AGENTS.md`, `docs/shared/agent-start-packet.md`, and the cached
`.cache/wellness/state.txt`. Run `make wellness` only when changed inputs give
the senses new work to do.

Use `MANIFEST.md` and the nearest `INDEX.md` to locate tissue. Specs name source,
requirements, checks, and constraints. Work only in a linked worktree; the
primary checkout remains read-only.

## Runtime authority

`fkwu` is the only kernel. It is bootstrapped from `form/runtime/fkwu-uni.c` and
runs Form source directly. Retired carriers and generated host artifacts are
historical bootstrap evidence—not runtime choices, fallbacks, or recurring
gates.

The execution path is:

1. BML or the highest fitting domain grammar.
2. Form recipes and cells.
3. Direct realization on fkwu.
4. The fkwu page JIT for hot compatible recipes.
5. A returned observation or explicit error.

A JIT miss is work in the JIT. Never route around it through a generated host
path. New behavior is Form/BML; do not add host-language implementations beside
the body.

The pinned `form/` submodule owns reusable kernel work. Coherence Network owns
application Form in `form/form/apps/coherence-network/api.bml` and
`api/app/form_recipes/`. The Python API and Next.js application are compatibility
hosts while their ownership moves into the native Form application host. Remove
each compatibility owner after its live Form replacement carries the complete
effect.

## Form-first reasoning

Ask the body before a rented mind:

- `form-cli ask` for grounded prose lookup and sufficiency judgment.
- `form/fkwu form/observe/form-find-ask.bml` for exact structural source lookup.
- `fsh-main.fk` and shell grammar for native scripted search and orchestration.
- `scripts/coh_substrate.py form` only while the public lattice bridge remains
  outside the native application host.

A grounded, sufficient native answer stops the search. A miss or bounded
failure is permission to use the rented reasoning lane. Report the path honestly
with `path`, `grounded`, `freq`, `suffic`, and `observed`; never describe remote
reasoning as native generation.

## Application boundary

The current fkwu/Form body already carries cells, files, sockets, HTTP client
operations, crypto, JSON, host I/O, and a native form-cli build door. The live
application-host work is template-parameter HTTP dispatch, file-backed config,
PostgreSQL, durable persistence, and route startup ownership. Close those gaps
where they live.

Configuration is file-backed:

`~/.coherence-network/config.json` → `api/config/api.json` → defaults.

Application code does not read environment variables. CI runner secrets are the
only exception.

## Validation

Validation follows the changed claim:

- A change to fkwu runtime source receives the smallest focused fkwu observation
  that proves that change.
- A Form/BML application change receives the smallest route or source
  observation that proves its changed effect.
- Documentation and deletion work receive structural checks.
- Do not run retired bootstrap comparisons or routine broad kernel validation.

Issues are work. Preserve the exact failure and repair its cause. Do not rename
an error as an accepted limitation, skip it through a fallback, or restore an
obsolete carrier to make a check green.

## How this body is tended

- Tend over produce. Update the living source before adding a sibling.
- Keep intent, inputs, owner, effects, and evidence together.
- Describe observed, inferred, measured, and mysterious claims distinctly.
- Let source coordinates, NodeIDs, routes, tests, and witness readings carry
  structural truth; labels only help people arrive.
- When a replacement works and callers have moved, remove the replaced flow,
  workaround, duplicate authority, and obsolete check.
- Lift repeated low-level behavior into a Form grammar, recipe, cell, or JIT
  capability so the next occurrence is simpler.
- Keep private personal and relational context out of repository artifacts.

## Workflow

Spec → test/observation → implement → review → merge → deploy.

Start with `make prompt-guide`. Before push, fetch and rebase on `origin/main`,
add one commit-evidence record under `docs/system_audit/`, and run only the
focused checks earned by the changed surface. Open the PR immediately after
push and keep the exact-head checks visible until the task lands or an external
blocker is named with its next command.

## Navigation

- `MANIFEST.md` — repository map.
- `docs/shared/agent-start-packet.md` — current runtime floor and destination.
- `docs/system_audit/form_kernel_floor_2026-10-18.md` — current fkwu floor.
- `form/form/apps/coherence-network/api.bml` — native application route catalog.
- `api/app/form_recipes/` — application-owned Form recipes still reached through
  the compatibility API.
- `specs/` and `ideas/` — intent and source ownership.
- `docs/PRODUCTION-SUBSTRATE.md` — deployed topology and live persistence.

## Work receipt

Close substantive work with what loosened or stayed tight, the most surprising
teaching, where observed discomfort became useful work, and an honest native
body versus rented-oracle receipt.
