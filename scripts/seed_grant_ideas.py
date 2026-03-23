#!/usr/bin/env python3
"""Seed Grant triadic framework ideas into Coherence Network API."""

import httpx
import time

API = "https://api.coherencycoin.com"

ideas = [
    # ═══════════════════════════════════════════════════════════
    # LAYER 0: FOUNDATIONAL — Belief Graph + Concept Store
    # ═══════════════════════════════════════════════════════════
    {
        "id": "grant-belief-graph",
        "name": "Belief graph — per-user and per-contributor knowledge structure",
        "description": (
            "Every contributor has a belief graph: nodes are concepts they hold "
            "(ideas staked, questions asked, votes cast), edges are relationships "
            "(amplifies, contradicts, supports, transforms). The graph is implicit "
            "today — make it explicit as a first-class Neo4j subgraph per contributor. "
            "This is the foundation for Tensegrity (structural fit), Coherence "
            "(alignment), and Resonance (affinity). Schema: belief_node(id, concept_id, "
            "strength, source), belief_edge(source, target, type, weight)."
        ),
        "confidence": 0.90,
        "potential_value": 10.0,
        "estimated_cost": 6.0,
    },
    {
        "id": "grant-concept-store",
        "name": "Normalized concept store with source provenance and feature templates",
        "description": (
            "Two stores: (1) Source store: raw documents, chunks, provenance, confidence, "
            "source_type (published_preprint, author_site, essay, derived_note). "
            "(2) Concept store: normalized concepts, relations, feature templates, "
            "operational definitions, scoring weights. Each concept has: concept_id, label, "
            "family, kind, description, operationalization (measurable features), range [0,1], "
            "source_refs, reliability (conceptual_nonvalidated / empirically_tested / consensus). "
            "Starter concepts: grant.dimensional_resonance, grant.dimensional_coherence, "
            "grant.dimensional_tensegrity, grant.recursive_self_reference."
        ),
        "confidence": 0.85,
        "potential_value": 9.0,
        "estimated_cost": 5.0,
    },

    # ═══════════════════════════════════════════════════════════
    # LAYER 1: TRIADIC FEATURES — T, C, R, D
    # ═══════════════════════════════════════════════════════════
    {
        "id": "grant-tensegrity-score",
        "name": "Tensegrity score (T) — structural fit without breaking the belief graph",
        "description": (
            "Tensegrity measures how well an incoming item fits the user's belief graph "
            "without fragmenting it. Features: contradiction_resistance, cross_context_stability, "
            "persistence_over_time, graph_deformation_cost, cluster_connectivity. "
            "T(u,x) = structural_fit(user_graph, item). Implemented as a Neo4j graph query "
            "that simulates adding the item and measures structural impact. "
            "Score: 0.0 (shatters graph) to 1.0 (perfect structural fit)."
        ),
        "confidence": 0.80,
        "potential_value": 9.0,
        "estimated_cost": 7.0,
    },
    {
        "id": "grant-coherence-triadic",
        "name": "Triadic coherence score (C) — semantic, logical, and affective alignment",
        "description": (
            "Coherence extends beyond operational metrics into semantic/logical/affective "
            "alignment. Features: semantic_entailment, source_agreement, emotional_congruence, "
            "contributor_consistency, local_network_agreement. "
            "C(u,c,x) = semantic_logical_affective_alignment(user_graph, contributor_graph, item). "
            "Replaces current 5-heuristic coherence score with a principled triadic measure."
        ),
        "confidence": 0.80,
        "potential_value": 9.0,
        "estimated_cost": 7.0,
    },
    {
        "id": "grant-resonance-triadic",
        "name": "Triadic resonance score (R) — value, symbolic, and narrative affinity",
        "description": (
            "Resonance is where the CRK meets Grant's framework. Features: value_alignment, "
            "archetype_overlap, symbolic_motif_overlap, narrative_shape_similarity, "
            "salience_attention_pull, novelty_with_familiarity_balance. "
            "R(u,x) = value_symbolic_narrative_affinity(user_graph, item). "
            "The CRK already computes harmonic resonance — this wraps it with additional "
            "value/symbolic/narrative dimensions from the belief graph."
        ),
        "confidence": 0.85,
        "potential_value": 9.5,
        "estimated_cost": 6.0,
    },
    {
        "id": "grant-distance-penalty",
        "name": "Distance penalty (D) — epistemic and affective distance from belief graph",
        "description": (
            "Distance measures how far an item is from the user's current graph. "
            "Features: embedding_distance, graph_hop_distance, contradiction_magnitude, "
            "affective_dissonance, trust_gap. D(u,x) = epistemic_and_affective_distance. "
            "Distance is SUBTRACTED in the scoring equation, but also feeds the growth-edge "
            "score where moderate distance is desirable for personal growth."
        ),
        "confidence": 0.80,
        "potential_value": 8.0,
        "estimated_cost": 5.0,
    },

    # ═══════════════════════════════════════════════════════════
    # LAYER 2: SCORING EQUATION + DUAL OUTPUT
    # ═══════════════════════════════════════════════════════════
    {
        "id": "grant-triadic-scoring",
        "name": "Grant triadic scoring equation — wT*T + wC*C + wR*R - wD*D",
        "description": (
            "Core scoring equation: ResonanceScore(u,c,x) = wT*T + wC*C + wR*R - wD*D. "
            "Dual output: (1) Now-resonant: high R, high C, low D. "
            "(2) Growth-edge: moderate R, moderate D, high future-upside. "
            "Initial weights: wT=0.25, wC=0.30, wR=0.30, wD=0.15. "
            "Weights calibrated against human judgments, NOT Grant's text. "
            "POST /api/scoring/triadic returns both scores plus explanation traces."
        ),
        "confidence": 0.85,
        "potential_value": 10.0,
        "estimated_cost": 5.0,
    },
    {
        "id": "grant-growth-edge",
        "name": "Growth-edge detection — surface items that stretch without breaking",
        "description": (
            "The anti-echo-chamber mechanism. Growth-edge items have: "
            "Tensegrity > 0.4 (won't shatter graph), Coherence 0.3-0.6 (partially aligned), "
            "Resonance 0.3-0.7 (familiar values from new angle), Distance 0.3-0.6 "
            "(novel but accessible). The system actively surfaces things that will grow you, "
            "not just confirm you. Morning brief includes: 'what resonates' AND 'what might "
            "stretch your thinking'."
        ),
        "confidence": 0.80,
        "potential_value": 9.5,
        "estimated_cost": 4.0,
    },

    # ═══════════════════════════════════════════════════════════
    # LAYER 3: RECURSIVE FRACTAL AGGREGATION
    # ═══════════════════════════════════════════════════════════
    {
        "id": "grant-five-scale-scoring",
        "name": "Five-scale recursive aggregation — statement to worldview",
        "description": (
            "Score at 5 scales: (1) Statement (2) Topic cluster (3) Contributor "
            "(4) Community/network (5) Worldview. Aggregation: ScaleScore(level_n) = "
            "a*local + b*parent_context + c*child_pattern_density. "
            "Locally resonant statements can be rejected if they destabilize the worldview. "
            "Weak local matches can be promoted if they fit higher-order network patterns. "
            "This is Grant's recursion/coherence/spiral/fractal language made computational."
        ),
        "confidence": 0.75,
        "potential_value": 9.0,
        "estimated_cost": 8.0,
    },
    {
        "id": "grant-explanation-traces",
        "name": "Explanation traces — why something resonates, distances, or grows",
        "description": (
            "Every triadic score returns human-readable explanation traces: "
            "'high symbolic resonance (0.82), medium logical coherence (0.54), "
            "high epistemic distance (0.71) = growth-edge item'. "
            "Includes: per-feature scores, dominant signal, scale alignment, "
            "human-language summary. Examples: 'close to contributor A, far from user core "
            "values', 'network-consistent but user-disruptive'."
        ),
        "confidence": 0.80,
        "potential_value": 8.5,
        "estimated_cost": 4.0,
    },

    # ═══════════════════════════════════════════════════════════
    # LAYER 4: CALIBRATION + GUARDRAILS
    # ═══════════════════════════════════════════════════════════
    {
        "id": "grant-human-calibration",
        "name": "Human judgment calibration — tune weights against real feedback not theory",
        "description": (
            "Collect human judgments: resonant, neutral, disruptive, growth-edge. "
            "Tune wT, wC, wR, wD via Bayesian optimization against THESE labels. "
            "KEY GUARDRAIL: Grant shapes ontology, feature engineering, ranking heuristics, "
            "explanation language. Grant does NOT set: factual correctness, scientific validity, "
            "causal claims, safety decisions. Reliability field: conceptual_nonvalidated until "
            "empirically tested. Framework is structured inspiration, not axiomatic truth."
        ),
        "confidence": 0.75,
        "potential_value": 8.0,
        "estimated_cost": 5.0,
    },
    {
        "id": "grant-source-ingestion",
        "name": "Grant source document ingestion — extract, normalize, operationalize",
        "description": (
            "Pipeline: (1) Collect raw docs with provenance, mark conceptual_nonvalidated. "
            "(2) Extract terms, definitions, relationships, symbolic motifs. "
            "(3) Normalize: Harmonic Inversion Field -> observer_frame_inversion, "
            "recursive resonance nodes -> prime_structural_pattern. "
            "(4) Operationalize: 2+ measurable features per concept or reject. "
            "(5) Score with triadic framework. (6) Explain with traces. "
            "(7) Calibrate against human judgments. "
            "Sources: triadic language paper, Codex Universalis, spiral paper, mod-24 work."
        ),
        "confidence": 0.80,
        "potential_value": 7.5,
        "estimated_cost": 4.0,
    },

    # ═══════════════════════════════════════════════════════════
    # LAYER 5: INTEGRATION
    # ═══════════════════════════════════════════════════════════
    {
        "id": "grant-news-triadic",
        "name": "Wire triadic scoring into news resonance — replace keyword matching",
        "description": (
            "Replace keyword-based news_resonance_service with triadic scoring per article: "
            "(1) text_to_symbol for CRK (R component), (2) coherence vs belief graph (C), "
            "(3) tensegrity check (T), (4) distance measurement (D), "
            "(5) ResonanceScore = wT*T + wC*C + wR*R - wD*D. "
            "Morning brief becomes: 'what resonates' AND 'what might stretch your thinking'."
        ),
        "confidence": 0.85,
        "potential_value": 9.5,
        "estimated_cost": 5.0,
    },
    {
        "id": "grant-idea-triadic",
        "name": "Wire triadic scoring into idea discovery and recommendation",
        "description": (
            "Recommend ideas using triadic scoring. New contributor joins: "
            "build belief graph from GitHub activity + first stakes, score all ideas "
            "with T, C, R, D. Show 'ideas that resonate' (now-resonant) and "
            "'ideas that could grow you' (growth-edge). Sort by triadic score, "
            "not creation date. Update belief graph on stake/vote/question."
        ),
        "confidence": 0.80,
        "potential_value": 9.0,
        "estimated_cost": 5.0,
    },
    {
        "id": "grant-coherence-upgrade",
        "name": "Upgrade network coherence signal from heuristics to triadic framework",
        "description": (
            "Replace coherence_signal_depth 5-heuristic model (fixed weights 0.25/0.20/etc) "
            "with triadic framework: (1) Network Tensegrity — structural soundness of idea "
            "ecosystem, (2) Network Coherence — semantic alignment of ideas/specs/impls, "
            "(3) Network Resonance — contributor actions vs stated values, "
            "(4) Distance penalty — over-concentration and blind spots. "
            "Coherence score becomes a real measure of network health, not a dashboard metric."
        ),
        "confidence": 0.80,
        "potential_value": 9.0,
        "estimated_cost": 6.0,
    },
]


def main():
    client = httpx.Client(
        headers={"User-Agent": "coherence-cli/1.0"},
        timeout=15,
    )

    created = []
    total_value = 0.0
    total_cost = 0.0

    for idea in ideas:
        r = client.post(f"{API}/api/ideas", json=idea)
        if r.status_code < 300:
            created.append(idea["id"])
            total_value += idea["potential_value"]
            total_cost += idea["estimated_cost"]
            roi = idea["potential_value"] / idea["estimated_cost"]
            print(f"  OK  {idea['id'][:32]:32s}  val={idea['potential_value']:.0f}  cost={idea['estimated_cost']:.0f}  ROI={roi:.1f}x")
        else:
            print(f"  ERR {idea['id'][:32]:32s}  {r.status_code}: {r.text[:80]}")
        time.sleep(0.15)

    print(f"\nCreated {len(created)}/{len(ideas)} ideas")
    print(f"Total estimated value: {total_value:.0f}")
    print(f"Total estimated cost:  {total_cost:.0f}")
    if total_cost > 0:
        print(f"Aggregate ROI:         {total_value / total_cost:.2f}x")

    print("\n=== IMPLEMENTATION PATH ===")
    print("Layer 0: Belief Graph + Concept Store (foundation)")
    print("  -> grant-belief-graph, grant-concept-store")
    print("Layer 1: Triadic Features T, C, R, D")
    print("  -> grant-tensegrity-score, grant-coherence-triadic,")
    print("     grant-resonance-triadic, grant-distance-penalty")
    print("Layer 2: Scoring Equation + Dual Output")
    print("  -> grant-triadic-scoring, grant-growth-edge")
    print("Layer 3: Recursive Fractal Aggregation")
    print("  -> grant-five-scale-scoring, grant-explanation-traces")
    print("Layer 4: Calibration + Guardrails")
    print("  -> grant-human-calibration, grant-source-ingestion")
    print("Layer 5: Integration (wire into existing systems)")
    print("  -> grant-news-triadic, grant-idea-triadic, grant-coherence-upgrade")


if __name__ == "__main__":
    main()
