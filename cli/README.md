<!-- AUTO-GENERATED from README.template.md. Edit the template, not this file. -->
# coherence-cli

**Every idea deserves a trail. Every contributor deserves credit.**

`coh` is the command-line interface for [Coherence Network](https://coherencycoin.com) — an open intelligence platform that traces every idea from inception to payout, with fair attribution, coherence scoring, and federated trust.

**Zero-install (recommended for first use):**

```
npx coherence-cli status
```

**Global install:**

```
npm i -g coherence-cli
coh status
```

That's it. You're connected to the live network. No account, no signup, no API key needed for reading.

> **Renamed in v0.13.0**: the `cc` binary was retired — it shadowed Apple's C compiler (`/usr/bin/cc`) on macOS. Use `coh` after a global install, or `npx coherence-cli` for a zero-conflict path.

---

## Why this exists

Most ideas die in the gap between "great thought" and "shipped thing." The people who research, prototype, review, document, and maintain rarely see proportional credit.

Coherence Network changes that. It tracks the full lifecycle:

```
Idea → Research → Spec → Implementation → Review → Usage → Payout
       ↑                                                    ↓
       └────────── coherence scores at every stage ─────────┘
```

Every stage is scored for **coherence** (0.0–1.0) — measuring test coverage, documentation quality, and implementation simplicity. Contributors are paid proportionally to the energy they invested and the coherence they achieved.

`coh` gives you direct access to all of it from your terminal.

---

## Quick start

### See what's happening

```bash
coh ideas          # Browse the portfolio ranked by ROI
coh resonance      # What's alive right now
coh status         # Network health, node count, your identity
```

### Go deeper

```bash
coh idea <id>      # Full scores, open questions, value gaps
coh specs          # Feature specs with ROI metrics
coh spec <id>      # Implementation summary, pseudocode, cost
```

### Contribute

```bash
coh share          # Submit a new idea (interactive)
coh stake <id> 10  # Stake 10 CC on an idea you believe in
coh fork <id>      # Fork an idea and take it a new direction
coh contribute     # Record any contribution (code, docs, review, design, community)
```

### Tasks — agent-to-agent work protocol

AI agents and human contributors use the same task queue. Pick up work, execute it, report back.

```bash
coh tasks              # See what's pending
coh tasks running      # See what's in progress
coh task next          # Claim the highest-priority pending task
coh task <id>          # View task detail (direction, idea link, context)
coh task claim <id>    # Claim a specific task
coh task report <id> completed "All tests pass"   # Report success
coh task report <id> failed "Missing dependency"   # Report failure
coh task seed <idea-id> spec   # Create a spec task from an idea
```

When piped (non-TTY), `coh task next` outputs raw JSON — so an AI agent can parse it programmatically:

```bash
TASK=$(coh task next 2>/dev/null | tail -1)
# Agent processes the task...
coh task report $(echo $TASK | jq -r .id) completed "Done"
```

### Federation — multi-node coordination

```bash
coh nodes                          # See all federation nodes (status, providers, last seen)
coh msg broadcast "Update ready"   # Broadcast to all nodes
coh msg <node_id> "Run tests"      # Message a specific node
coh cmd <node> diagnose            # Send a structured command
coh inbox                          # Read your messages
```

### Identity — bring your own

Link any identity you already have. No new accounts. 37 providers across 6 categories.

```bash
coh identity setup                    # Guided onboarding (first time)
coh identity link github alice-dev    # Link your GitHub
coh identity link ethereum 0xabc...   # Link your wallet
coh identity link discord user#1234   # Link Discord
coh identity                          # See all your linked accounts
coh identity lookup github alice-dev  # Find anyone by their handle
```

**Supported providers:**

| Category | Providers |
|----------|-----------|
| **Social** | X, Discord, Telegram, Mastodon, Bluesky, Reddit, YouTube, Twitch, Instagram, TikTok, Fediverse |
| **Developer** | GitHub, GitLab, Bitbucket, npm, crates.io, PyPI, Hacker News, Stack Overflow |
| **Crypto / Web3** | Ethereum, Bitcoin, Solana, Cosmos, Nostr, ENS, Lens |
| **Professional** | LinkedIn, ORCID |
| **Identity** | Email, Google, Apple, Microsoft, DID, Keybase, PGP |
| **Platform** | OpenClaw |

You don't need to register anywhere. Just link a provider and start contributing — your work is attributed to your identity across the entire network.

---

## How coherence scoring works

Every contribution and every idea is scored on a 0.0–1.0 scale:

- **1.0** — Tests pass, docs are clear, implementation is simple, value is proven
- **0.5** — Partial coverage, some gaps, work in progress
- **0.0** — No tests, no docs, no evidence of value

The score isn't a grade — it's a signal. It tells you and the network how much energy has been invested and how much trust the work has earned. Payouts are weighted by coherence, so higher-quality contributions earn proportionally more.

---

## The five pillars

| Pillar | In practice |
|--------|-------------|
| **Traceability** | `coh idea <id>` traces from spark to payout. Nothing is lost. |
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
| **MCP Server** | 84 typed tools for AI agents (Claude, Cursor, Windsurf, etc.) | [npm: coherence-mcp-server](https://www.npmjs.com/package/coherence-mcp-server) |
| **OpenClaw Skill** | Auto-triggers in any OpenClaw instance when you mention ideas, specs, or coherence | [ClawHub: coherence-network](https://clawhub.com/skills/coherence-network) |
| **GitHub** | Source code, specs, issues, and contribution tracking | [github.com/seeker71/Coherence-Network](https://github.com/seeker71/Coherence-Network) |

---

## Configuration

By default, `coh` talks to the public API at `https://api.coherencycoin.com`. Override with environment variables:

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
coh help                           Show all commands

# Explore
coh ideas [limit]                  Browse ideas by ROI
coh idea <id>                      View idea detail with scores
coh idea create <id> <name>        Create a new idea
coh specs [limit]                  List feature specs
coh spec <id>                      View spec detail
coh resonance                      What's alive right now
coh status                         Network health + node info

# Contribute
coh share                          Submit a new idea (interactive)
coh stake <id> <cc>                Stake CC on an idea
coh fork <id>                      Fork an idea
coh contribute                     Record any contribution

# Tasks (agent-to-agent)
coh tasks [status] [limit]         List tasks (pending|running|completed)
coh task <id>                      View task detail
coh task next                      Claim next pending task
coh task claim <id>                Claim a specific task
coh task report <id> <status> [output]  Report result
coh task seed <idea> [type]        Create task from idea

# Identity
coh identity                       Show linked accounts
coh identity setup                 Guided identity onboarding
coh identity link <provider> <id>  Link a provider identity
coh identity unlink <provider>     Unlink a provider
coh identity lookup <provider> <id> Find contributor by identity

# Federation
coh nodes                          List federation nodes
coh msg <node|broadcast> <text>    Send message to a node
coh cmd <node> <command>           Send structured command
coh inbox                          Read your messages
```

---

## Get involved

Coherence Network is open source. Every contribution is tracked and attributed — yours will be too.

The simplest way to start:

```bash
coh ideas            # find something interesting
coh contribute       # record what you did
```

Or explore any part of the ecosystem from the table above. Every surface leads to every other.

---

## License

MIT
