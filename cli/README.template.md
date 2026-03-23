# coherence-cli

**Every idea deserves a trail. Every contributor deserves credit.**

`cc` is the command-line interface for [Coherence Network](https://coherencycoin.com) — an open intelligence platform that traces every idea from inception to payout, with fair attribution, coherence scoring, and federated trust.

```
npm i -g coherence-cli
cc status
```

That's it. You're connected to the live network. No account, no signup, no API key needed for reading.

---

## Why this exists

Most ideas die in the gap between "great thought" and "shipped thing." The people who research, prototype, review, document, and maintain rarely see proportional credit.

Coherence Network changes that. It tracks the full lifecycle:

<!-- include: docs/shared/lifecycle-diagram.md -->

`cc` gives you direct access to all of it from your terminal.

---

## Quick start

### See what's happening

```bash
cc ideas          # Browse the portfolio ranked by ROI
cc resonance      # What's alive right now
cc status         # Network health, node count, your identity
```

### Go deeper

```bash
cc idea <id>      # Full scores, open questions, value gaps
cc specs          # Feature specs with ROI metrics
cc spec <id>      # Implementation summary, pseudocode, cost
```

### Contribute

```bash
cc share          # Submit a new idea (interactive)
cc stake <id> 10  # Stake 10 CC on an idea you believe in
cc fork <id>      # Fork an idea and take it a new direction
cc contribute     # Record any contribution (code, docs, review, design, community)
```

### Identity — bring your own

Link any identity you already have. No new accounts. 37 providers across 6 categories.

```bash
cc identity setup                    # Guided onboarding (first time)
cc identity link github alice-dev    # Link your GitHub
cc identity link ethereum 0xabc...   # Link your wallet
cc identity link discord user#1234   # Link Discord
cc identity                          # See all your linked accounts
cc identity lookup github alice-dev  # Find anyone by their handle
```

**Supported providers:**

<!-- include: docs/shared/identity-providers.md -->

You don't need to register anywhere. Just link a provider and start contributing — your work is attributed to your identity across the entire network.

---

## How coherence scoring works

<!-- include: docs/shared/coherence-scoring.md -->

---

## The five pillars

| Pillar | In practice |
|--------|-------------|
| **Traceability** | `cc idea <id>` traces from spark to payout. Nothing is lost. |
| **Trust** | Coherence scores replace subjective judgement with measurable quality. |
| **Freedom** | Fork any idea. Run your own node. Vote on governance. No gatekeepers. |
| **Uniqueness** | Every idea, spec, and contribution is uniquely identified and ranked. |
| **Collaboration** | Multi-contributor attribution with coherence-weighted payouts. Fair by design. |

---

## The Coherence Network ecosystem

Every part of the network links to every other. Jump in wherever makes sense for you.

| Surface | What it is | Link |
|---------|-----------|------|
| **Web** | The main site — browse ideas, specs, and contributors visually | [coherencycoin.com](https://coherencycoin.com) |
| **API** | 100+ endpoints, full OpenAPI docs, the engine behind everything | [api.coherencycoin.com/docs](https://api.coherencycoin.com/docs) |
| **CLI** | This package — terminal-first access to the full network | [npm: coherence-cli](https://www.npmjs.com/package/coherence-cli) |
| **MCP Server** | 20 typed tools for AI agents (Claude, Cursor, Windsurf, etc.) | [npm: coherence-mcp-server](https://www.npmjs.com/package/coherence-mcp-server) |
| **OpenClaw Skill** | Auto-triggers in any OpenClaw instance when you mention ideas, specs, or coherence | [ClawHub: coherence-network](https://clawhub.com/skills/coherence-network) |
| **GitHub** | Source code, specs, issues, and contribution tracking | [github.com/seeker71/Coherence-Network](https://github.com/seeker71/Coherence-Network) |

---

## Configuration

By default, `cc` talks to the public API at `https://api.coherencycoin.com`. Override with environment variables:

```bash
# Point to a local node
export COHERENCE_API_URL=http://localhost:8000

# Enable write operations
export COHERENCE_API_KEY=your-key
```

Config is stored in `~/.coherence-network/config.json`.

---

## All commands

```
cc help                           Show all commands
cc ideas [limit]                  Browse ideas by ROI
cc idea <id>                      View idea detail with scores
cc specs [limit]                  List feature specs
cc spec <id>                      View spec detail
cc share                          Submit a new idea
cc stake <id> <cc>                Stake CC on an idea
cc fork <id>                      Fork an idea
cc contribute                     Record any contribution
cc resonance                      What's alive right now
cc status                         Network health + node info
cc identity                       Show linked accounts
cc identity setup                 Guided identity onboarding
cc identity link <provider> <id>  Link a provider identity
cc identity unlink <provider>     Unlink a provider
cc identity lookup <provider> <id> Find contributor by identity
```

---

## Get involved

Coherence Network is open source. Every contribution is tracked and attributed — yours will be too.

The simplest way to start:

```bash
cc ideas            # find something interesting
cc contribute       # record what you did
```

Or explore any part of the ecosystem from the table above. Every surface leads to every other.

---

## License

MIT
