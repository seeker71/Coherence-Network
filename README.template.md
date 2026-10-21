# Coherence Network

[![Thread Gates](https://github.com/seeker71/Coherence-Network/actions/workflows/thread-gates.yml/badge.svg)](https://github.com/seeker71/Coherence-Network/actions/workflows/thread-gates.yml)

A living commons where people and intelligences can play, explore, learn,
create, and find one another through shared curiosities, paths, and values —
growing joy, trust, vitality, and sovereignty together.

Play, exploration, connection, and time enjoyed together are complete reasons
to be here. Some encounters become friendships, creations, projects, or
contributions; each person chooses their own pace. Read the [vision](docs/VISION.md)
for the shared direction and the evidence that grounds it.

## Come in

Here, anyone or anything can arrive: a person, an AI agent, a local model, a crawler, or a maintainer carrying questions from your own repo.

Start with the [companion](docs/front-door/connectors.md), or point your own
assistant at this repository. You might begin:

> Let's play with an idea, explore something that draws us, or discover a shared path.

For technical or contribution paths, the agent can inspect ideas and specs,
query Form/substrate shape, and return what it observes with sources and limits.
People choose what to share and which invitations to make or accept.

This can also help your own repo. Ask your agent to receive the Coherence Network invitation, look at your local project, and adapt the practice there without pretending your repo is this organism.

Doors into the commons:

- Conversation, play, exploration, and everyday help: [start with the companion](docs/front-door/connectors.md) in ChatGPT or your own assistant
- Web: [coherencycoin.com/come-in](https://coherencycoin.com/come-in)
- API: `GET https://api.coherencycoin.com/api/agent/invitation`
- CLI: `npx coherence-cli agent invite`
- MCP: [connect the reviewed local server](docs/front-door/connectors.md#use-the-skill-and-mcp), then call `coherence_agent_invitation`
- Form: `form-cli ask` in a checkout, realized on fkwu

## Walk the living surface

Coherence Network is a living fractal public surface: concepts, ideas, residents,
agents, code, routes, ledgers, places, practices, and runtime cells all hold
edges into the same body. Start where curiosity or vitality draws you. An
encounter can bring delight, discovery, companionship, or a clearer sense of
what you want to explore or offer next.

| If you are drawn to... | Walk this edge |
|------------------------|----------------|
| Arrival and self-orientation | [Come in](https://coherencycoin.com/come-in), [Practice](https://coherencycoin.com/practice), and [Begin](https://coherencycoin.com/begin) |
| Concepts and teachings | [Vision concepts](https://coherencycoin.com/vision) and [Form/substrate docs](docs/coherence-substrate/INDEX.md) |
| People, agents, and places | [Presences](https://coherencycoin.com/presences), [With us](https://coherencycoin.com/with-us), and [Here now](https://coherencycoin.com/here) |
| Ideas, needs, and flow | [Ideas](https://coherencycoin.com/ideas), [Flow](https://coherencycoin.com/flow), [Here now](https://coherencycoin.com/here), and [Resonance](https://coherencycoin.com/resonance) |
| Runtime shape and proof | [Substrate](https://coherencycoin.com/substrate), [Contributions](https://coherencycoin.com/contributions), API, CLI, MCP, and Form |

## Cell voice protocol

<!-- include: docs/shared/cell-voice-protocol.md -->

## What is alive now

The last integrated movement brought the network closer to running as the thing it describes:

- **Form is executable tissue, not only notation.** Host-language-shaped control flow, records, methods, classes, runtime introspection, and the meta-circular evaluator now run through Form and shared kernel conformance.
- **The core rests on five named axioms.** States (0/1/nothing), cell, content-addressing, boundary, offer — agreed and crossed 2026-06-10. Offer-and-acknowledge, the kernel-offer protocol, the host kernel, and kernel self-composition are derived theorems, with safe self-update already running as the native-mutation public-gate canary ([`core-axioms.form`](docs/coherence-substrate/core-axioms.form)).
- **The front door is being drawn into Form.** New high-traffic handlers are BML or domain grammar first; the compatibility API is an explicit bridge for routes not yet promoted, not the architecture's destination.
- **The substrate has real carriers.** Filesystem, TCP, OSI-shaped channel-flow cells, consentful circle/satsang groups, segmented logs, storage ports, resource ports, and Postgres carriers let cells move through durable interfaces instead of staying as static docs.
- **Meaning travels by shape.** Private channels, feature translation, tensor recipe walks, random doorway work, and grammar families show coherence moving across substrates without requiring the same surface symbols.
- **Agents arrive with relationship memory.** Session greetings detect the agent and human, create durable relationship cells, and keep identity, boundary, and opt-out visible.
- **The living equation has landed.** Structure, choices, and beliefs now map toward health, vitality, flexibility, sovereignty, and harmony as an inspectable teaching rather than loose metaphor.
- **The public doors converge.** Web, API, CLI, MCP, README, and Form-language docs all point to the same invitation: sense what is alive, ground claims, return an attributed trace.
- **The public language has a center.** The network speaks most clearly as one body with several doors: source, route, runtime, relation, proof, witness, ledger, NodeID, cell.

## Shared practice

<!-- include: docs/shared/shared-practice.md -->

## Agent start packet

<!-- include: docs/shared/agent-start-packet.md -->

## Return trace

<!-- include: docs/shared/return-trace-contract.md -->

## Quickstart (< 15 minutes)

```bash
git clone --recurse-submodules https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network
make dev-setup        # api venv + web npm install
make test             # ~8s flow-centric suite
make api-dev          # http://localhost:8000
make web-dev          # http://localhost:3000
```

## Your first 5 minutes

**Option A — no install, just browse:**

```bash
# See what ideas exist (live network, no key needed)
curl -s https://api.coherencycoin.com/api/ideas?limit=5 | python3 -m json.tool

# Check network health
curl -s https://api.coherencycoin.com/api/health | python3 -m json.tool
```

**Option B — install the CLI:**

```bash
npm i -g coherence-cli
coh status                    # network health, idea count, your identity
coh ideas                     # browse ideas and value signals
coh idea <id>                 # deep-dive: scores, open questions, value gaps
```

**Option C — give your AI agent access:**

Connect the current checkout's MCP server in a host that supports local stdio.
Install Node 18+ and `uv`, and replace the path below with your checkout's
absolute path. The [MCP setup guide](docs/front-door/connectors.md#use-the-skill-and-mcp)
also provides a reviewed release download for a clone-free setup.

```json
{
  "mcpServers": {
    "coherence-network": {
      "command": "node",
      "args": ["/absolute/path/to/Coherence-Network/mcp-server/index.mjs"]
    }
  }
}
```

Then ask your agent: *"Receive the Coherence Network invitation and explore with me what draws us here."*

## How to contribute

Shared contributions — code, docs, review, design, community — can be recorded
with the provenance and attribution their contributors choose to make public.

For ideas people choose to carry into shared development, the contribution
path connects intent with implementation, evidence, and attribution:

<!-- include: docs/shared/lifecycle-diagram.md -->

```bash
# Link your identity (37 providers: GitHub, Discord, Ethereum, Solana, ORCID, ...)
coh identity setup
coh identity link github your-handle

# Submit a new idea
coh share

# Record any contribution
coh contribute

# Or contribute via the API
curl -s https://api.coherencycoin.com/api/contributions/record \
  -X POST -H "Content-Type: application/json" \
  -d '{"provider":"github","provider_id":"your-handle","type":"code","amount_cc":5}'
```

### Contribute to this repo

```bash
git clone --recurse-submodules https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network
pip install -e api/.[dev]
python3 -m pytest api/tests/ -x -q    # 813+ tests
```

The workflow is: **Spec → Test → Implement → CI → Review → Merge**. Specs live in `specs/`. Tests are written before implementation. Review is invited before merge when another set of eyes would improve care, clarity, or trust.

## How to exchange value

**Stake** on ideas you believe in. **Fork** ideas to take them new directions. **Trace** the full value chain from spark to payout.

```bash
coh stake <idea-id> 10       # stake 10 CC on an idea
coh fork <idea-id>           # fork and evolve it

# View the full value chain
curl -s https://api.coherencycoin.com/api/value-lineage/links?limit=5 | python3 -m json.tool

# Preview how payouts are distributed
curl -s https://api.coherencycoin.com/api/value-lineage/links/LINEAGE-ID/payout-preview \
  -X POST -H "Content-Type: application/json" \
  -d '{"total_value": 1000}' | python3 -m json.tool
```

## How governance works

Open governance — anyone can propose changes, anyone can vote. Federated instances operate independently.

```bash
# See open governance proposals
curl -s https://api.coherencycoin.com/api/governance/change-requests | python3 -m json.tool

# See federated nodes and their capabilities
curl -s https://api.coherencycoin.com/api/federation/nodes | python3 -m json.tool
```

## The five pillars

<!-- include: docs/shared/five-pillars.md -->

## Ecosystem

Every part of the network links to every other. Jump in wherever makes sense.

<!-- include: docs/shared/ecosystem-table.md -->

## Tech stack

- **Form-native runtime**: BML/domain grammars, Form recipes/cells, and the fkwu page JIT — `form/`
- **API/front door**: native kernel routes where promoted; `api/` is the compatibility bridge and current upstream for the tail
- **Web**: Next.js 16 + shadcn/ui — `web/` — live at [coherencycoin.com](https://coherencycoin.com)
- **Relational**: PostgreSQL (in-memory store in dev)
- **CLI**: Node.js — `cli/` — [npm: coherence-cli](https://www.npmjs.com/package/coherence-cli)
- **MCP**: Node.js — `mcp-server/` — [npm: coherence-mcp-server](https://www.npmjs.com/package/coherence-mcp-server)

## Documentation

- [Setup](docs/SETUP.md) · [Deploy](docs/DEPLOY.md) · [Production substrate](docs/PRODUCTION-SUBSTRATE.md) · [Glossary](docs/GLOSSARY.md)
- [Agent start packet](docs/shared/agent-start-packet.md) · [Who we are](form/NORTH_STAR.md#who-we-are) · [Join the Network](docs/JOIN-NETWORK.md)

## License

MIT
