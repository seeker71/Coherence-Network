# Reference Repositories

Coherence-Network was created by synthesizing plans and ideas from two existing repos. They are linked via symlinks in `references/` for Cursor and human reference.

## Structure

```
Coherence-Network/
├── references/
│   ├── crypo-coin/     → ../../Crypo-Coin-Coherency-Network
│   └── living-codex/   → ../../Living-Codex-CSharp
└── ...
```

## What to Use From Each

### Crypo-Coin-Coherency-Network (`references/crypo-coin/`)

**Purpose:** Planning, spec-driven workflow, agent architecture, first use case.

| File/Dir | Use For |
|----------|---------|
| `AGENT-AUTONOMY.md` | Agent Council, human-on-the-loop, decision routing |
| `MODEL-ROUTING.md` | Model tiers, cost optimization (adapt to our subscriptions) |
| `SPEC-DRIVEN-PLAN.md` | Spec format, test-first, guardrails |
| `FRAMEWORK-architecture-spec.md` | States of matter, concept-as-everything, C# vision |
| `FIRST-USE-CASE-analysis.md` | OSS Contribution Intelligence rationale |
| `EXECUTION-PLAN.md` | Tech stack, project structure |
| `REVIEW-vision-and-direction.md` | Strategic direction, revenue models |
| `concepts/` | CC001–CC008, coherence rewards, governance |

### Living-Codex-CSharp (`references/living-codex/`)

**Purpose:** Proven implementation patterns, node architecture, operational lessons.

| File/Dir | Use For |
|----------|---------|
| `LIVING_CODEX_SPECIFICATION.md` | Implementation status, API catalog, architecture |
| `specs/LIVING_UI_SPEC.md` | UI patterns, lenses, data flow |
| `.cursor/rules/stay-generic.mdc` | Principles: everything is a node, adapters, tiny deltas |
| `src/CodexBootstrap/` | Module loading, API routing, node registry patterns |
| `living-codex-ui/` | Next.js structure, components, API client |

## Important: Project Boundaries

- **Current project:** Coherence-Network. All new code, specs, and edits go here.
- **Reference repos:** Read-only context. Use for patterns and ideas; do not modify as part of Coherence-Network work.
- If a pattern from a reference repo should be adopted, implement it in Coherence-Network (possibly adapted).

## Symlink Setup

The symlinks use relative paths (`../../Crypo-Coin-Coherency-Network`). They assume:

- Coherence-Network is at `.../source/Coherence-Network`
- Crypo-Coin-Coherency-Network is at `.../source/Crypo-Coin-Coherency-Network`
- Living-Codex-CSharp is at `.../source/Living-Codex-CSharp`

If you clone Coherence-Network elsewhere, create the symlinks manually:

```bash
cd /path/to/Coherence-Network/references
ln -sf /path/to/Crypo-Coin-Coherency-Network crypo-coin
ln -sf /path/to/Living-Codex-CSharp living-codex
```

Or clone the reference repos as siblings under the same parent directory.
