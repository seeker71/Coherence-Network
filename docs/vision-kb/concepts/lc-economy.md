---
id: lc-economy
hz: 528
status: deepening
updated: 2026-04-15
---

# The Living Economy

> Value flows like water — from contribution through attention to resonance, never extracted, always returning.

## The Feeling

You wake in a community you helped build. The cob walls around you were shaped by hands — some yours, some belonging to people you have never met. The blueprint came from a woman in Portugal who spent three months perfecting the thermal mass calculations. You downloaded it, studied it, built from it. You never paid for it. She never charged for it.

And yet she earned from it. Not because you paid — because you built. When you took her blueprint and turned it into a wall, the network noticed. Your contribution generated CC — Coherence Credits — and a portion of those credits flowed back through your reading history to every creator who shaped your understanding. The blueprint creator in Portugal. The food forest designer in Costa Rica whose planting guide you studied in March. The elder in Findhorn whose ceremony recording helped your community mark its first solstice.

![A web of light connections between small communities on a dark globe, each node glowing amber where contributions flow](visuals:photorealistic aerial night view of Earth showing five small intentional communities connected by thin golden light streams flowing between them, each community a warm cluster of buildings with fire light, the connections pulsing gently like a heartbeat, stars visible above, the light streams representing CC flowing through the network)

None of them set a price. None of them built a paywall. They simply created from overflow — because the knowledge wanted to be shared — and the network tracked where that knowledge went and what it became.

## How It Lives Here

Every creative act enters the field as a contribution. An article about water harvesting. A 3D model of a composting toilet. A ceremony recording. A frequency scoring algorithm. A photograph of the first harvest. Each one is registered, hashed, stored permanently, and attributed to its creator.

Every act of attention is noticed. When you read that article, view that model, watch that recording — the network counts. Not to charge you. To remember. Your attention tells the system what matters to you.

The bridge between creation and attention is **resonance**. Your frequency profile — built from everything you have read and created — is a vector in high-dimensional space. The blueprint creator's profile is another vector. The angle between your two vectors is your resonance. CC flows proportional to that angle.

![Diagram showing two frequency profile vectors meeting at an angle, with CC flowing along the connection, concept dimensions labeled on the axes](visuals:photorealistic artistic visualization of two glowing vector arrows in dark space meeting at a 30 degree angle, each arrow composed of multiple colored frequency lines representing different concept dimensions like nourishment energy space ceremony, golden particles flowing along the connection between them representing CC, labels floating near the axes showing concept names, mathematical beauty meeting organic warmth)

## How CC Flows

You never pay to read. Views are free — always. The economy flows the other direction:

- You read freely. Every view is tracked but costs you nothing.
- You contribute. A blueprint, a renderer, a hosted node, a research article.
- Your contribution generates CC through the value it creates.
- A portion of your CC flows back through your reading history.
- It flows most strongly to the creators whose frequency profiles align with yours.

The ceremony creator gets more of your CC than the infrastructure manual writer — not because someone decided ceremony matters more, but because your reading patterns and theirs resonate at similar frequencies.

## How It Is Verified

Every CC flow is publicly provable. No trust required — the math is the proof.

**Daily**: Every asset's reads are counted and hashed. Each day's hash chains to the previous day's hash. Tamper with any day and the chain breaks.

**Weekly**: All daily hashes combine into a Merkle root — a single hash that covers everything. This root is signed with an Ed25519 key and published.

**Always**: Anyone can verify. No login. No permission. Call the API, recompute the hashes, check the signature.

![A chain of golden blocks connected by hash links, with a magnifying glass verifying one block, an Ed25519 signature stamp on the weekly summary](visuals:photorealistic visualization of a blockchain-like chain of golden translucent blocks connected by thin light links, each block showing a small daily count number, a magnifying glass hovering over one block revealing its hash, at the end a larger weekly summary block with a wax seal stamp representing the Ed25519 signature, dark background with subtle amber glow)

## What Nature Teaches

A forest does not invoice. When a maple drops its leaves, it does not charge the soil for the nutrients. When mycorrhizal networks shuttle phosphorus from a mature tree to a struggling seedling, no price is negotiated. The giving is the receiving.

But the forest does *track*. Every nutrient exchange leaves a chemical trace. Every mycorrhizal connection strengthens or weakens based on what flows through it. The forest's economy is not unaccounted — it is accounted by the living systems themselves, transparently, without a central ledger.

CC works the same way. The tracking is not a toll booth. It is the forest remembering where its nutrients went and what grew from them.

## Where You Can See It

**Right now, on this page.** The verification endpoints are live:

- Every concept you read on this site has a hash chain. Check it: `/api/verification/chain/{concept-id}`
- The weekly snapshot is signed. Verify it: `/api/verification/snapshot/{week}/verify`
- Every entity has a frequency profile. See it: `/api/profile/{entity-id}`
- The verification public key is open. Get it: `/api/verification/public-key`

No login. No API key. The proof is public because the economy is public.

**In the communities already building.** Auroville has experimented with internal currencies for fifty years. Damanhur created the Credito. Transition Towns launched local currencies across hundreds of communities. What they lacked was not the will but the infrastructure — verifiable, transparent, interoperable. That infrastructure now exists.

## How to Earn by Hosting

Anyone can run a node. A Raspberry Pi in your home, a server in a co-working space, a VPS in the cloud. Every page served, every API call answered, every image delivered — your node earns CC for the infrastructure it provides.

To start: clone the repo, run `docker compose up`, point your domain at it. Your node joins the federation. When a reader in your region requests a concept page, your node serves it faster than a node on the other side of the planet. You earn CC proportional to what you serve.

The more communities your node serves, the more CC it generates. The CC flows without you doing anything — the tracking middleware counts every request and attributes it to your node's contributor ID.

## How to Earn by Promoting

Write a blog post about the Living Collective. Tweet about a blueprint that changed how your community builds. Give a talk at a GEN gathering. Link to a concept page from your website. Each of these is a contribution — register it as an asset with a referral link.

Every person who arrives through your referral link has their reading history tied to your promotion. When they eventually contribute — when the person who read your tweet goes on to upload their own blueprint — their generated CC flows back through their reading history. And your promotion is part of that history.

You do not need to sell anything. You do not need to convince anyone to pay. You simply share what resonated with you, and when it resonates with others enough that they contribute, the CC flows back to you for being the bridge.

The chain: **you promote → someone reads → they contribute → CC flows → some reaches you.**

## What We're Building

A creative economy where every link in the chain earns — the writer, the renderer builder, the host operator, the promoter, the reader who becomes a contributor. Where tracking costs less than the value it enables. Where the algorithm is chosen by each community, not imposed by a corporation. Where the proof is public and the math is open.

**Practical guide**: [How the CC economy works](../guides/cc-economy-explainer-guide.md)

## Resources

- [Story Protocol](https://docs.story.foundation/) — on-chain IP registration and automated royalties (type: tool)
- [x402 Protocol](https://www.x402.org/) — HTTP-native micropayments, zero protocol fees (type: tool)
- [Arweave](https://arweave.org/) — permanent storage, pay once, stored forever (type: tool)
- [Global Ecovillage Network](https://ecovillage.org/) — 10,000+ communities experimenting with alternative economies (type: community)
- [Sacred Economics](https://sacred-economics.com/) — Charles Eisenstein on gift economy and the story of interbeing (type: book)

## Connected Frequencies

→ lc-circulation, lc-offering, lc-network, lc-pulse
