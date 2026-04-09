---
idea_id: knowledge-and-resonance
status: done
source:
  - file: api/app/services/concept_service.py
    symbols: [list_concepts, get_concept, search_concepts]
  - file: api/app/services/concept_resonance_kernel.py
    symbols: [compute_crk, text_to_symbol, ot_phi_distance]
  - file: api/app/services/belief_service.py
    symbols: [get_belief_profile, compute_resonance, find_resonant_peers]
  - file: api/app/services/idea_resonance_service.py
    symbols: [get_cross_domain_pairs, get_resonance_for_idea]
  - file: api/app/services/accessible_ontology_service.py
    symbols: [suggest_concept, approve_suggestion, endorse_concept]
  - file: api/app/services/discovery_service.py
    symbols: [build_discovery_feed]
  - file: api/app/routers/resonance.py
    symbols: [cross_domain, idea_resonance, resonance_proof]
  - file: api/app/routers/beliefs.py
    symbols: [get_profile, update_profile, compute_resonance]
requirements:
  - 184 universal concepts with 46 typed relationships and 53 axes
  - Concept Resonance Kernel (CRK) -- harmonic spectral matching
  - Optimal Transport distance (OT-phi) for coherence scoring
  - Contributor belief profiles with 6 worldview axes
  - Cross-domain resonance discovery between ideas from different domains
  - Accessible ontology -- non-technical contributors can suggest/endorse concepts
  - Serendipity discovery feed combining 5 resonance sources
  - Resonance proof endpoint showing network health
done_when:
  - GET /api/concepts returns 184+ concepts
  - GET /api/resonance/cross-domain returns pairs with coherence scores
  - POST /api/beliefs/{id}/resonance/{idea_id} returns breakdown
  - GET /api/resonance/proof shows discovery health
  - GET /api/discover/{contributor_id} returns personalized feed
  - All tests pass
test: "python3 -m pytest api/tests/test_flow_discovery.py -q"
---

> **Parent idea**: [knowledge-and-resonance](../ideas/knowledge-and-resonance.md)
> **Source**: [`api/app/services/concept_service.py`](../api/app/services/concept_service.py) | [`api/app/services/concept_resonance_kernel.py`](../api/app/services/concept_resonance_kernel.py) | [`api/app/services/belief_service.py`](../api/app/services/belief_service.py) | [`api/app/services/idea_resonance_service.py`](../api/app/services/idea_resonance_service.py) | [`api/app/services/accessible_ontology_service.py`](../api/app/services/accessible_ontology_service.py) | [`api/app/services/discovery_service.py`](../api/app/services/discovery_service.py) | [`api/app/routers/resonance.py`](../api/app/routers/resonance.py) | [`api/app/routers/beliefs.py`](../api/app/routers/beliefs.py)

# Knowledge and Resonance Engine -- 184 Concepts, Harmonic Matching, Belief Translation

## Goal

Provide the semantic substrate that makes coherence scoring meaningful -- a living ontology of 184 universal concepts with typed relationships, a harmonic resonance kernel for cross-domain idea matching, contributor belief profiles for personalized discovery, and an accessible ontology that non-technical contributors can extend naturally.

## What's Built

The knowledge and resonance engine spans eight source files implementing four layers: concepts, resonance, beliefs, and discovery.

**Concept layer**: `concept_service.py` manages 184 universal concepts with 46 typed relationships and 53 axes from the Living Codex ontology. `list_concepts` returns the full vocabulary, `get_concept` retrieves a single concept with its relationships, and `search_concepts` enables semantic lookup. Concepts are nodes; relationships are edges. This provides the vocabulary for all coherence and resonance scoring.

**Resonance kernel**: `concept_resonance_kernel.py` implements the Concept Resonance Kernel (CRK) -- harmonic spectral matching that finds resonance between ideas that share underlying concepts even when surface words differ. `compute_crk` performs the core harmonic similarity computation. `text_to_symbol` converts natural language into the concept vocabulary. `ot_phi_distance` computes Optimal Transport distance for coherence scoring -- the mathematical backbone of cross-domain discovery.

**Belief system**: `belief_service.py` implements per-contributor worldview profiles with 6 axes. `get_belief_profile` returns a contributor's current belief state. `compute_resonance` scores how strongly an idea resonates with a specific belief system. `find_resonant_peers` discovers contributors with similar worldviews for collaboration. `beliefs.py` exposes these as API endpoints for profile management and resonance computation.

**Cross-domain discovery**: `idea_resonance_service.py` provides `get_cross_domain_pairs` which finds semantically related ideas across different domains -- a climate idea resonating with a supply-chain idea because they share underlying concepts. `get_resonance_for_idea` returns the full resonance profile for a single idea. `accessible_ontology_service.py` lets non-technical contributors participate by suggesting, approving, and endorsing concepts naturally. `discovery_service.py` combines 5 resonance sources into a personalized serendipity feed via `build_discovery_feed`.

**Resonance proof**: `resonance.py` exposes `resonance_proof` which shows network-wide discovery health -- how many cross-domain connections exist, the distribution of resonance scores, and whether the concept layer is generating genuine insight.

## Requirements

1. 184 universal concepts with 46 typed relationships and 53 axes
2. Concept Resonance Kernel (CRK) -- harmonic spectral matching
3. Optimal Transport distance (OT-phi) for coherence scoring
4. Contributor belief profiles with 6 worldview axes
5. Cross-domain resonance discovery between ideas from different domains
6. Accessible ontology -- non-technical contributors can suggest/endorse concepts
7. Serendipity discovery feed combining 5 resonance sources
8. Resonance proof endpoint showing network health

## Acceptance Tests

```bash
python3 -m pytest api/tests/test_flow_discovery.py -q
```
