---
id: cc-economy-explainer
type: guide
status: seed
updated: 2026-04-15
---

# The Coherence Credit Economy — How This Is Different

## What Every Other Platform Does

On every existing platform, you create and someone else captures:

- **YouTube**: You make the video. Google keeps 45% of ad revenue and owns the algorithm that decides who sees it.
- **Substack**: You write the article. Substack takes 10% and Stripe takes 3%. Your readers are their users.
- **Etsy/Gumroad**: You make the thing. They take 6-15% plus payment processing. You compete with everyone else on their marketplace.
- **Patreon**: Your community pays you. Patreon takes 5-12%. If Patreon changes terms, you lose your income.
- **Open source**: You contribute for free. Corporations use your code to make billions. You get a GitHub star.

The pattern: **you create value, the platform extracts rent, an algorithm you can't see decides your fate.**

## What This Platform Does

No one extracts rent. There is no algorithm deciding who wins. Every contribution — from writing an article to running a server to promoting the platform to viewing a page — is tracked, attributed, and rewarded through CC (Coherence Credits) that flow based on actual community resonance.

### Everyone in the chain is a contributor

| Who | What they contribute | How they earn CC |
|-----|---------------------|-----------------|
| **Content creator** | Article, blueprint, 3D model, research, recipe, song | CC flows when people read/use their work |
| **Image/visual creator** | Photos, renders, diagrams, maps | CC flows on every view |
| **Renderer builder** | Code that displays a format (3D viewer, music player) | CC flows every time their renderer displays any asset |
| **Infrastructure host** | Server, bandwidth, storage, compute | CC flows for every API call served |
| **Promoter** | Blog post, tweet, talk, referral link | CC flows when people they brought in later contribute |
| **Community member** | Presence, feedback, ceremony, tending | CC flows through participation in the living field |
| **Reader/viewer** | Attention, engagement, resonance | Free — but their reading pattern shapes CC flow when they contribute |

### How CC actually flows

```
1. You contribute something (any creative act)
   ↓
2. The system tracks its cost (your time, energy, resources)
   ↓
3. Other people read/use/view your contribution (free, always)
   ↓
4. When those readers ALSO contribute, they generate CC
   ↓
5. A portion of THEIR generated CC flows back through their
   reading history to the creators they learned from
   ↓
6. The flow is weighted by their concept resonance profile
   (which concepts they care about most)
   ↓
7. You receive CC proportional to how much your work served
   what those contributors needed
```

No paywall. No subscription. No ads. No algorithm picking winners. Just resonance — your work earns based on how much it actually nourishes the people who encounter it.

## The Community Chooses the Algorithm

This is the critical difference: **each community chooses and updates its own distribution algorithm.**

There is no platform-wide algorithm imposed from above. Each community (a group of contributors who share a node) decides:

- **What counts as contribution**: Maybe one community values ceremony and physical building equally. Another values research and documentation more heavily. They set the weights.
- **How CC splits flow**: The default is 80% asset creator / 15% renderer / 5% host. But a community can change this to 60/25/15 if they believe infrastructure deserves more.
- **What the redistribution rate is**: How much of your earned CC flows back through your reading history. Default 15%. A community focused on knowledge sharing might set this to 25%.
- **How concept resonance is weighted**: Equal weight across all concepts? Or heavier weight toward the concepts the community is actively building?
- **The evidence multiplier**: How much extra CC flows when someone proves they used a blueprint to actually build something. Default 5x. A community that values implementation might set this to 10x.

These parameters are stored on-chain (Story Protocol) and can be updated by community consensus. The algorithm itself is open source — anyone can read the code, verify the math, and propose changes.

### Algorithm governance

The algorithm isn't voted on in the old-earth sense (majority rules, minorities lose). It's sensed:

1. Any community member can propose a parameter change
2. The proposal lives for a sensing period (typically 2 weeks)
3. Members signal resonance (not approval — resonance)
4. If the field aligns, the parameter updates
5. If it doesn't align, the proposal composts — it might return later in different form

This is harmonic rebalancing applied to economics. The algorithm evolves as the community evolves.

## Infrastructure as Contribution

Running the platform IS contributing. Every resource consumed to serve the community is tracked:

| Resource | How it's measured | CC attribution |
|----------|------------------|---------------|
| **Compute** | CPU-seconds serving API requests | Per-request micro-attribution |
| **Storage** | Bytes stored on node's disk | Monthly storage contribution |
| **Bandwidth** | Bytes transferred to readers | Per-transfer micro-attribution |
| **Availability** | Uptime percentage | Bonus CC for reliability |
| **Arweave fees** | Cost of permanent storage | Reimbursed from treasury + margin |

A community member who runs a node on a Raspberry Pi in their home earns CC for every page served, every API call answered, every image delivered. They're contributing infrastructure the same way a writer contributes articles.

When multiple nodes serve the same content (federation), each node earns proportional to what it served. This naturally incentivizes geographic distribution — a node in New Zealand serves Kiwi readers faster than a node in Portugal, so it earns more CC from that region.

## Why This Is Fair

Traditional platforms decide fairness for you. Here, fairness is:

1. **Transparent**: Every CC flow is publicly verifiable on-chain (Story Protocol + Merkle chains)
2. **Community-defined**: Each community sets its own parameters — not a corporation
3. **Proportional**: Earn based on actual resonance, not follower count or algorithm favor
4. **Retroactive**: Past contributions earn CC when future readers benefit from them
5. **Composable**: A blueprint that inspires a derivative that inspires an implementation — the whole chain is attributed
6. **Inclusive**: Every type of contribution counts — not just content creation but hosting, rendering, promoting, tending

## What CC Can Become

CC starts as an internal unit of account — tracking who contributed what. As the network grows:

1. **Internal exchange**: Trade CC for goods/services within the community
2. **Inter-community exchange**: CC flows between communities in a federated network
3. **USDC bridge**: Convert CC to stablecoins via Base L2 (when treasury backs it)
4. **Fiat off-ramp**: Eventually convert to traditional currency where needed
5. **Sovereign currency**: At sufficient scale, CC IS the currency — no conversion needed

The treasury backing ensures CC has real value: every CC in circulation is backed by the real assets, infrastructure, and creative work of the network. The exchange rate is computed from treasury reserves divided by outstanding supply — no speculation, no manipulation, just math that anyone can verify.
