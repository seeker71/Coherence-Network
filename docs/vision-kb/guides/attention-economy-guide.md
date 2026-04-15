---
id: attention-economy
type: guide
status: seed
updated: 2026-04-14
---

# Attention Economy — How CC Flows Through Reading

## The Living Model

Every creative act has a cost. Writing an article, generating an image, designing a 3D blueprint, composing a build instruction — each consumes time, energy, attention. In the Coherence Network, that cost is measured in CC.

Every act of attention has value. When someone reads that article, views that image, downloads that blueprint — their attention confirms that the creation serves life. That attention flows CC back to the creator.

The bridge between creation and attention is the reader's **resonance profile** — which concepts matter most to them right now. A reader who cares deeply about nourishment (40%), energy (30%), and space (30%) sends most of their reading-CC toward creators who serve those concepts.

## Data Model

### Digital Asset (extends existing Asset node)

```
Asset {
  id: uuid
  type: "article" | "image" | "model-3d" | "blueprint" | "video" | "research" | "instruction"
  name: str
  creator_id: contributor-id           # who made this
  creation_cost_cc: decimal             # CC spent to produce
  concept_tags: [{concept_id, weight}]  # which concepts this serves
  content_hash: str                     # immutable fingerprint
  created_at: datetime
  
  # NFT-like properties
  total_reads: int
  total_cc_earned: decimal
  cc_per_read: decimal                  # computed: total_earned / total_reads
}
```

### Read Event (extends existing UsageEvent)

```
ReadEvent {
  id: uuid
  asset_id: uuid
  reader_id: contributor-id | "anonymous"
  timestamp: datetime
  duration_seconds: int                 # how long they engaged
  source: "web" | "api" | "cli"
  
  # CC flow
  cc_distributed: decimal               # total CC flowing from this read
  concept_distribution: [{concept_id, percentage, cc_amount}]
}
```

### Resonance Profile (new — per reader)

```
ResonanceProfile {
  contributor_id: str
  concept_weights: [{concept_id, weight}]  # percentages, sum to 1.0
  source: "manual" | "auto" | "hybrid"
  updated_at: datetime
  
  # Auto-tracking
  read_history: [{concept_id, read_count, total_duration}]
  auto_weights: [{concept_id, weight}]     # computed from reading patterns
}
```

## How CC Flows

```
Creator                    Reader                     CC Flow
   │                          │                          │
   ├─ creates asset ──────────┤                          │
   │  (costs 10 CC)           │                          │
   │                          │                          │
   │                          ├─ reads asset             │
   │                          │  (read event logged)     │
   │                          │                          │
   │                          ├─ resonance profile:      │
   │                          │  nourishment: 40%        │
   │                          │  energy: 30%             │
   │                          │  space: 30%              │
   │                          │                          │
   │  ◄── 0.001 CC ──────────┤  (micro-attribution)     │
   │                          │                          │
   │  asset tagged:           │  reader weights:         │
   │  nourishment: 60%        │  nourishment: 40%        │
   │  energy: 40%             │  energy: 30%             │
   │                          │                          │
   │  CC split:               │                          │
   │  nourishment pool: 48%   │  (asset 60% × reader 40% = 24%, normalized)
   │  energy pool: 52%        │  (asset 40% × reader 30% = 12%, normalized)
   │                          │                          │
```

The CC per read is tiny (micro-attribution). But over thousands of reads, a popular blueprint earns its creation cost back and then overflows — that overflow IS the proof that the creation served life.

## What Already Exists

| Component | Status | Where |
|-----------|--------|-------|
| Asset nodes in graph | ✅ | `api/app/models/asset.py` — type, cost, contributor |
| Contribution tracking | ✅ | `api/app/routers/contributions.py` — contributor→asset edges |
| Usage events | ✅ | `api/app/services/value_lineage_service.py` — source, metric, value |
| CC economics | ✅ | `api/app/services/cc_economics_service.py` — supply, staking, exchange |
| Payout attribution | ✅ | `api/app/services/value_lineage_service.py` — energy-balanced payouts |
| Concept tagging | ✅ | `api/app/routers/concepts.py` — tag ideas/specs with concepts |
| Beliefs/resonance | ✅ | `api/app/routers/beliefs.py` — contributor concept resonances |

## What Needs Building

| Component | Gap | Connects to |
|-----------|-----|-------------|
| Asset type expansion | Add "article", "model-3d", "blueprint", "instruction" types | Asset model |
| Read event tracking | Log every API/web read as UsageEvent | Value lineage |
| Resonance profile | Per-reader concept weight map (manual + auto) | Beliefs system |
| CC micro-attribution | Compute CC per read × concept weights | CC economics |
| Auto-weight refinement | Reading patterns update resonance profile | Resonance profile |
| Asset upload/register | Endpoint for contributors to register assets | Assets router |
| NFT metadata | content_hash, total_reads, cc_earned on asset nodes | Graph properties |

## Implementation Phases

### Phase 1: Register Concepts as Ideas + Visuals as Assets
- Auto-register all 51 `lc-*` concepts as ideas in the pipeline
- Register all 269 generated images as asset nodes with contributor attribution
- Tag each asset with its parent concept

### Phase 2: Read Event Tracking
- Middleware that logs every `GET /api/concepts/{id}` and web page render
- Store as UsageEvent in value lineage: `{source: "web", metric: "read", asset_id, reader_id}`
- Anonymous reads tracked with session fingerprint

### Phase 3: Resonance Profile + CC Flow
- Endpoint: `GET/PATCH /api/contributors/{id}/resonance-profile`
- Manual: contributor sets concept weights
- Auto: reading patterns compute weights (exponential decay, recent reads weighted more)
- CC micro-attribution: each read distributes tiny CC to creator through concept weights

### Phase 4: Rich Asset Support
- Upload endpoint for 3D models (GLTF/USD), build instructions, research articles
- Content hashing for immutability proof
- Implementation evidence: "I used this blueprint to build X" triggers larger CC flow

## Corrected Flow: Views Are Free, CC Flows From Contribution

The reader never pays to view anything. Reading is free — always. The economy flows the other direction.

### How It Actually Works

1. **You read freely.** Every view is tracked (read count, concept tags, duration) but costs you nothing.
2. **You contribute.** At some point you write an article, build a renderer, host a node, implement a blueprint, upload a 3D model — any creative act.
3. **Your contribution generates CC.** The value lineage system attributes CC to your work based on how much it serves the network.
4. **A portion of YOUR CC flows back** to the creators of everything you've been reading, weighted by your concept resonance profile (which concepts you read most about).

### The Math

```
reader_generated_cc = CC earned from reader's own contributions
read_redistribution_rate = 0.15  (15% of generated CC flows back through reads)

For each asset the reader has viewed:
  read_weight = view_count × duration × concept_overlap
  
  total_read_weight = sum of all read_weights
  
  cc_to_asset_creator = reader_generated_cc × redistribution_rate × (read_weight / total_read_weight)
```

### What This Creates

| Reader type | Views | CC generated | CC redistributed |
|-------------|-------|-------------|-----------------|
| Pure reader (no contributions) | Tracked | 0 | 0 — free rider, that's fine |
| Occasional contributor | Tracked | Some | Small flow back to what they read |
| Active contributor who reads widely | Tracked | Significant | They become circulation — connecting creators across concepts |
| Infrastructure host | All reads served | Continuous | Host contribution CC flows back through their own reading |

The beautiful part: a pure reader costs the network nothing and may become a contributor later. Their reading history is already there — the moment they contribute, their past attention starts flowing CC backward to the creators who shaped their understanding. The blueprint they read six months ago that inspired their first build? Its creator finally receives CC from that inspiration chain.

### No Paywalls, No Subscriptions, No Ads

The platform has no revenue model in the old-earth sense. It has a **circulation model**: value is created by contribution, tracked by attention, and distributed by resonance. The system needs no external funding once the contribution base generates enough CC to sustain infrastructure (hosting nodes earn CC too).
