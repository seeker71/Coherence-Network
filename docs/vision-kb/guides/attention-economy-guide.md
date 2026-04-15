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
