# Repo Manifest

> Single entry-point for finding any file in this repo. The narrative
> layer (specs, ideas, concepts, lineage) has been indexed for a
> while; the code layer (routers, services, components, scripts) is
> indexed by `scripts/generate_repo_indexes.py`.

> An agent landing here costs ~400 tokens to know which INDEX to
> drill into next, then ~1500 tokens to know which file to read.
> Total cost to locate any file: under 2K tokens.

## Agent entry (read first)

| Doc | Purpose |
|---|---|
| [docs/shared/agent-start-packet.md](docs/shared/agent-start-packet.md) | **First file for any agent** — Form-native runtime primary surface, Python bridge/bootstrap compost, read-only query default |
| [docs/PRODUCTION-SUBSTRATE.md](docs/PRODUCTION-SUBSTRATE.md) | **Current production substrate** — Hostinger/VPS topology, internal Postgres credential carriers, native-kernel DB probe path |
| [docs/coherence-substrate/INDEX.md](docs/coherence-substrate/INDEX.md) | Substrate + Form notation drill-down |
| [docs/front-door/INDEX.md](docs/front-door/INDEX.md) | **Public front door for any AI assistant** — ask the substrate and offer it content from a public ChatGPT/Claude/Gemini, no account, no git (`llms.txt`, connectors, GPT action) |

## Narrative layer (existing)

| Index | Purpose |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Body tending practice + Quick Lookup table |
| [docs/PRODUCTION-SUBSTRATE.md](docs/PRODUCTION-SUBSTRATE.md) | Current Hostinger/VPS topology, internal Postgres, and native-kernel DB probe path |
| [specs/INDEX.md](specs/INDEX.md) | All specs, grouped by parent idea (auto-generated) |
| [ideas/INDEX.md](ideas/INDEX.md) | Super-ideas (16) across the 6 pillars |
| [docs/vision-kb/INDEX.md](docs/vision-kb/INDEX.md) | Living Collective wiki — concepts, axes, lineage |
| [docs/vision-kb/locations/INDEX.md](docs/vision-kb/locations/INDEX.md) | Climate adaptations |
| [docs/vision-kb/materials/INDEX.md](docs/vision-kb/materials/INDEX.md) | Construction methods |
| [docs/vision-kb/realization/INDEX.md](docs/vision-kb/realization/INDEX.md) | Governance, economics, membership, phases |
| [docs/vision-kb/resources/INDEX.md](docs/vision-kb/resources/INDEX.md) | Open-source plans, references, books |
| [docs/vision-kb/scales/INDEX.md](docs/vision-kb/scales/INDEX.md) | 50 / 100 / 200 people configurations |
| [docs/vision-kb/spaces/INDEX.md](docs/vision-kb/spaces/INDEX.md) | Hearth, garden, workshop, sanctuary, gathering |
| [docs/vision-kb/stories/INDEX.md](docs/vision-kb/stories/INDEX.md) | Field vignettes — scenes from the future |
| [docs/lineage/INDEX.md](docs/lineage/INDEX.md) | Teaching lineages and presences |
| [docs/presences/INDEX.md](docs/presences/INDEX.md) | Specific presences in the field |

## Code layer (auto-generated)

| Index | Files | Purpose |
|---|---|---|
| [api/app/routers/INDEX.md](api/app/routers/INDEX.md) | 147 | Python bridge/API routers — current endpoint carrier and upstream tail while Form-native routes are promoted |
| [api/app/services/INDEX.md](api/app/services/INDEX.md) | 247 | API services — business logic and graph operations |
| [api/app/models/INDEX.md](api/app/models/INDEX.md) | 58 | API models — Pydantic + ORM shapes |
| [api/tests/INDEX.md](api/tests/INDEX.md) | 274 | API tests — flow-centric |
| [web/lib/INDEX.md](web/lib/INDEX.md) | 36 | Web library — shared client/server helpers |
| [web/components/INDEX.md](web/components/INDEX.md) | 53 | Web components — shared React surfaces |
| [web/app/INDEX.md](web/app/INDEX.md) | 166 | Web routes — every visible page in the app |
| [scripts/INDEX.md](scripts/INDEX.md) | 322 | Scripts — operational tools, generators, syncers |

## Convention

Every new source file gets a one-line purpose statement at the top:

- **Python**: a module docstring (`"""What this module does."""`) on line 1
- **TypeScript/TSX**: a leading `// What this file does` comment OR a JSDoc block `/** What this file does */`

After adding/renaming files, re-run:

```
python3 scripts/generate_repo_indexes.py
```

CI runs `--check` and fails if any INDEX.md is stale.
