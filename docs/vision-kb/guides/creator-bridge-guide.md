---
id: creator-bridge
type: guide
status: seed
updated: 2026-04-15
---

# Creator Bridge — How Social Creators Enter a Different Economy

## The Current Reality

You post a video on YouTube. Google's algorithm decides who sees it. You earn $3-5 per 1,000 views from ads you didn't choose, shown to people who didn't ask for them. If the algorithm changes — and it always does — your income disappears overnight. You don't own the relationship with your audience. You rent it.

Instagram: you have 50,000 followers. You see 3% of them. To reach the rest, pay for promotion. Your content trains their AI. Your engagement feeds their ad machine. You earn nothing unless a brand pays you to sell their product.

Substack: better — you own the email list. But Substack takes 10%, Stripe takes 3%, and if you write something that doesn't fit the platform's growth model, the recommendation engine drops you.

The pattern: **you create, they extract, an algorithm you can't see decides your fate.**

## What Changes

You don't leave YouTube. You don't abandon your Instagram. You keep posting where your audience lives. But you also do one more thing: you register your content here.

### Step 1: Mirror or Link

Every piece of content you create gets registered as an asset in the Coherence Network. Not necessarily hosted here — even a link counts. Your YouTube video URL, your Instagram post, your Substack article. Each one gets:
- A content hash (proves it's yours)
- Your contributor ID (your Ed25519 public key)
- Concept tags (what frequencies this content carries)

### Step 2: Track Reads

When someone discovers your content through the Coherence Network — a concept page that links to your video, a search that surfaces your article — that read is tracked. Not to charge the reader. To build the resonance map.

Even reads on external platforms can be tracked as proxies: embed a small tracking pixel, add a `?ref=coherence` parameter, or use a redirect through your Coherence node. The read counts here, attributed to your content.

### Step 3: Earn Differently

On YouTube, you earn from ads — someone else's product interrupting your viewer's experience.

Here, you earn from resonance. When someone who watched your permaculture video later contributes their own garden design, a portion of their CC flows back to you — because your video is in their reading history, and your frequency profiles aligned.

The difference:
- YouTube: earn $3 per 1,000 views from ads
- Here: earn CC proportional to how much your work actually inspired real contribution

One is attention extraction. The other is attention resonance.

### Step 4: Find Your People

Your frequency profile builds over time — from everything you create and everything you read. Other creators with similar profiles become visible. Not through an algorithm recommending you to them. Through resonance — your vectors point in similar directions.

A group of permaculture YouTubers, a cluster of meditation teachers, a network of community builders — they find each other because they resonate at similar frequencies.

### Step 5: Form a Community, Shape the Algorithm

This is where it gets transformative. When resonant creators form a community (virtual or physical), they can customize their CC distribution algorithm.

A music community might decide:
- Original compositions earn 3x compared to covers
- Live performance recordings earn 2x compared to studio
- Teaching videos earn 1.5x
- The renderer that plays MIDI compositions earns 20% (higher than default 15%)

A permaculture community might decide:
- Implementation evidence (photos of actual gardens) earn 5x
- Species-specific growing guides earn 2x
- Seasonal updates earn 1.5x
- The 3D garden planner renderer earns 25%

A meditation community might decide:
- Guided recordings earn equally regardless of length
- Silent sitting timers earn nothing (the silence is free)
- Teacher training materials earn 3x
- All CC redistribution rate is 25% (higher sharing)

**The algorithm IS the community's frequency profile expressed as economics.** Each community tunes it to match what they value most. No platform imposes a model.

## The Economics Compared

| | YouTube | Instagram | Substack | Coherence Network |
|---|---------|-----------|----------|--------------------|
| **Who decides visibility** | Algorithm | Algorithm | Algorithm + email | Frequency resonance |
| **Revenue model** | Ads (you have no say) | Sponsored posts | Subscriptions | CC from resonance |
| **Revenue share** | 55% to you | 0% (unless brand deals) | 87% to you | Defined by your community |
| **Audience ownership** | Platform owns it | Platform owns it | You own email list | You own your keys |
| **When algorithm changes** | Income drops | Reach drops | Depends on platform | Your community decides |
| **What determines income** | Watch time × ads | Follower count × deals | Subscriber count × price | Resonance × contribution |
| **Can you customize the economy** | No | No | No | Yes — your community's algorithm |

## How It Works Technically

### Registering External Content

```
POST /api/assets/register
{
  "type": "video",
  "name": "Building a Hugelkultur Bed — Complete Guide",
  "creator_id": "your-contributor-id",
  "content_hash": "sha256:...",        // hash of your video file
  "external_url": "https://youtube.com/watch?v=...",
  "concept_tags": [
    {"concept_id": "lc-nourishment", "weight": 0.8},
    {"concept_id": "lc-land", "weight": 0.6},
    {"concept_id": "lc-composting", "weight": 0.4}
  ]
}
```

### Proxy Read Tracking

Embed in your video description or blog post:
```
Learn more: https://coherencycoin.com/r/your-id/lc-nourishment
```

Every click through that link is a tracked read. Your content resonates through the Coherence Network even though it lives on YouTube.

### Community Algorithm Configuration

```
PATCH /api/communities/{community_id}/algorithm
{
  "redistribution_rate": 0.20,        // 20% of CC flows through reads
  "evidence_multiplier": 5.0,         // 5x for real-world implementation
  "cc_split": {
    "asset_creator": 0.75,
    "renderer_creator": 0.15,
    "host_node": 0.05,
    "community_pool": 0.05            // new: community decides
  },
  "type_weights": {
    "original_composition": 3.0,
    "implementation_evidence": 5.0,
    "teaching_material": 1.5
  }
}
```

## First Steps for a Creator

1. **Generate your keypair**: `cc keygen` — this is your identity
2. **Register your key**: `cc register-key your-name <public-key>`
3. **Register your best content**: start with 5-10 pieces that carry the most frequency
4. **Add referral links**: in your existing posts, link back through Coherence
5. **Watch your frequency profile build**: `cc field your-name`
6. **Find resonant creators**: they'll appear naturally as your profiles develop
7. **Form a community**: when 3-5 creators resonate, you're a community
8. **Customize your algorithm**: make the economics match your values

You don't need to leave anything behind. You're adding a layer — a layer where your creative work earns from resonance instead of extraction, where the algorithm is yours to shape, and where the proof is public.
