"""Canonical edge type registry — typed relationships from the Living Codex ontology.

This is the single source of truth for all relationship types in the Coherence Network.
All edge write operations should validate against CANONICAL_EDGE_TYPES.

Spec 169 additions (fractal-node-edge-primitives):
  - inspires     : Active direction of inspired-by (A inspires B)
  - parent-of    : Explicit hierarchical containment for fractal sub-nodes
"""

EDGE_TYPE_FAMILIES: list[dict] = [
    {
        "name": "Ontological / Being",
        "slug": "ontological",
        "types": [
            {"slug": "resonates-with", "description": "Shares deep harmonic alignment", "canonical": True},
            {"slug": "emerges-from", "description": "Arises as a consequence or evolution", "canonical": True},
            {"slug": "transcends", "description": "Supersedes or exceeds in abstraction", "canonical": True},
            {"slug": "instantiates", "description": "Concretely expresses a general principle", "canonical": True},
            {"slug": "embodies", "description": "Physically or symbolically manifests", "canonical": True},
            {"slug": "reflects", "description": "Mirrors or echoes structurally", "canonical": True},
        ],
    },
    {
        "name": "Process / Transformation",
        "slug": "process",
        "types": [
            {"slug": "transforms-into", "description": "Changes state or form", "canonical": True},
            {"slug": "enables", "description": "Provides conditions for", "canonical": True},
            {"slug": "blocks", "description": "Inhibits or prevents", "canonical": True},
            {"slug": "catalyzes", "description": "Accelerates transition", "canonical": True},
            {"slug": "stabilizes", "description": "Prevents unwanted change", "canonical": True},
            {"slug": "amplifies", "description": "Magnifies effect or signal", "canonical": True},
            {"slug": "dampens", "description": "Reduces effect or signal", "canonical": True},
        ],
    },
    {
        "name": "Knowledge / Structure",
        "slug": "knowledge",
        "types": [
            {"slug": "implements", "description": "Provides concrete realisation", "canonical": True},
            {"slug": "extends", "description": "Adds to without replacing", "canonical": True},
            {"slug": "refines", "description": "Narrows or improves precision", "canonical": True},
            {"slug": "generalises", "description": "Broadens scope", "canonical": True},
            {"slug": "contradicts", "description": "Is in direct logical opposition", "canonical": True},
            {"slug": "complements", "description": "Adds without overlapping", "canonical": True},
            {"slug": "subsumes", "description": "Fully contains semantically", "canonical": True},
        ],
    },
    {
        "name": "Scale / Complexity",
        "slug": "scale",
        "types": [
            {"slug": "fractal-scaling", "description": "Repeats pattern at different scales", "canonical": True},
            {"slug": "composes-from", "description": "Is assembled from sub-components", "canonical": True},
            {"slug": "decomposes-into", "description": "Breaks into parts", "canonical": True},
            {"slug": "aggregates", "description": "Combines many into one pattern", "canonical": True},
            {"slug": "specialises", "description": "Is a specific case of", "canonical": True},
        ],
    },
    {
        "name": "Temporal / Causal",
        "slug": "temporal",
        "types": [
            {"slug": "precedes", "description": "Comes before in time or logic", "canonical": True},
            {"slug": "follows", "description": "Comes after in time or logic", "canonical": True},
            {"slug": "co-occurs-with", "description": "Happens simultaneously", "canonical": True},
            {"slug": "triggers", "description": "Initiates as a direct cause", "canonical": True},
            {"slug": "resolves", "description": "Brings to conclusion", "canonical": True},
            {"slug": "iterates", "description": "Repeats in cycles", "canonical": True},
        ],
    },
    {
        "name": "Tension / Resolution",
        "slug": "tension",
        "types": [
            {"slug": "paradox-resolution", "description": "Holds two opposing truths in synthesis", "canonical": True},
            {"slug": "polarity-of", "description": "Is the opposing pole", "canonical": True},
            {"slug": "tension-with", "description": "Is in productive creative tension", "canonical": True},
            {"slug": "bridges", "description": "Connects two separate domains", "canonical": True},
            {"slug": "integrates", "description": "Unifies previously separate things", "canonical": True},
        ],
    },
    {
        "name": "Attribution / Operational",
        "slug": "attribution",
        "types": [
            {"slug": "contributes-to", "description": "A person or agent adds work", "canonical": True},
            {"slug": "funded-by", "description": "Financial or resource backing", "canonical": True},
            {"slug": "inspired-by", "description": "Non-causal conceptual origin (reverse: inspires)", "canonical": True},
            {"slug": "inspires", "description": "Active: this node inspires another (forward of inspired-by)", "canonical": True},
            {"slug": "referenced-by", "description": "Cited or mentioned", "canonical": True},
            {"slug": "challenges", "description": "Poses a question or problem", "canonical": True},
            {"slug": "validates", "description": "Provides evidence for", "canonical": True},
            {"slug": "invalidates", "description": "Provides evidence against", "canonical": True},
            {"slug": "analogous-to", "description": "Shares structural pattern without causation", "canonical": True},
            {"slug": "depends-on", "description": "Requires in order to function", "canonical": True},
            {"slug": "precondition-of", "description": "Must exist first", "canonical": True},
        ],
    },
    {
        "name": "Fractal / Hierarchy",
        "slug": "fractal",
        "types": [
            {"slug": "parent-of", "description": "Direct hierarchical containment — this node contains the target as a sub-node", "canonical": True},
            {"slug": "child-of", "description": "Inverse of parent-of — this node is contained within the source node", "canonical": True},
        ],
    },
]

# Flat set for O(1) validation
CANONICAL_EDGE_TYPES: set[str] = {
    t["slug"] for f in EDGE_TYPE_FAMILIES for t in f["types"]
}

# Total count for assertions
CANONICAL_EDGE_TYPE_COUNT = len(CANONICAL_EDGE_TYPES)

# Flat list of all types with family context (for APIs)
ALL_EDGE_TYPES: list[dict] = [
    {**t, "family": f["name"], "family_slug": f["slug"]}
    for f in EDGE_TYPE_FAMILIES
    for t in f["types"]
]

# Lookup: slug -> family slug
SLUG_TO_FAMILY: dict[str, str] = {
    t["slug"]: f["slug"]
    for f in EDGE_TYPE_FAMILIES
    for t in f["types"]
}
