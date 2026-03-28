"""Canonical node type registry — Universal Node primitives for the Coherence Network.

Every entity in the system is a node. This registry defines the closed-but-extensible
vocabulary of node types, their allowed lifecycle phases, and semantic metadata.

Node lifecycle (Ice/Water/Gas model from Living Codex breath/water states):
  - gas   : speculative, volatile, pre-form. Ideas bubbling up. Not yet committed.
  - water : active, flowing, being worked on. Implementation in progress.
  - ice   : stable, archived, reference. Frozen potential — specification or completed work.

Phase transitions that are valid:
  gas   → water  (commit to active work)
  gas   → ice    (archive without developing — e.g. rejected ideas)
  water → ice    (complete / freeze)
  water → gas    (dissolve back — scope reduced, de-prioritised)
  ice   → water  (thaw — reopen for iteration)
  ice   → gas    (fully dissolve — rare, means discarding even the frozen form)
"""

from __future__ import annotations

# ── Node Type Families ────────────────────────────────────────────────


NODE_TYPE_FAMILIES: list[dict] = [
    {
        "name": "Knowledge",
        "slug": "knowledge",
        "description": "Epistemic artifacts — ideas, concepts, specs, and implementations",
        "types": [
            {
                "slug": "idea",
                "label": "Idea",
                "description": "An atomic unit of intent or insight. The primary entry point for new work.",
                "default_phase": "water",
                "allowed_phases": ["gas", "water", "ice"],
                "fractal": True,   # can contain sub-nodes of same type
                "icon": "lightbulb",
            },
            {
                "slug": "concept",
                "label": "Concept",
                "description": "A named abstraction or mental model that underpins multiple ideas.",
                "default_phase": "water",
                "allowed_phases": ["gas", "water", "ice"],
                "fractal": True,
                "icon": "brain",
            },
            {
                "slug": "spec",
                "label": "Spec",
                "description": "A formal specification defining behaviour, contracts, or requirements.",
                "default_phase": "ice",
                "allowed_phases": ["gas", "water", "ice"],
                "fractal": True,
                "icon": "document",
            },
            {
                "slug": "implementation",
                "label": "Implementation",
                "description": "Concrete code, configuration, or artefact that realises a spec.",
                "default_phase": "water",
                "allowed_phases": ["gas", "water", "ice"],
                "fractal": False,
                "icon": "code",
            },
        ],
    },
    {
        "name": "Agents",
        "slug": "agents",
        "description": "Human and software agents that act in the network",
        "types": [
            {
                "slug": "contributor",
                "label": "Contributor",
                "description": "A human or AI agent who contributes to the network.",
                "default_phase": "water",
                "allowed_phases": ["water", "ice"],
                "fractal": False,
                "icon": "person",
            },
            {
                "slug": "service",
                "label": "Service",
                "description": "A running software service or API that the network depends on.",
                "default_phase": "water",
                "allowed_phases": ["gas", "water", "ice"],
                "fractal": True,
                "icon": "server",
            },
        ],
    },
    {
        "name": "Infrastructure",
        "slug": "infrastructure",
        "description": "Operational and structural nodes that support the network",
        "types": [
            {
                "slug": "domain",
                "label": "Domain",
                "description": "A bounded context or subject area that groups related nodes.",
                "default_phase": "water",
                "allowed_phases": ["water", "ice"],
                "fractal": True,
                "icon": "folder",
            },
            {
                "slug": "task",
                "label": "Task",
                "description": "An executable work unit assigned to an agent.",
                "default_phase": "water",
                "allowed_phases": ["gas", "water", "ice"],
                "fractal": False,
                "icon": "check",
            },
            {
                "slug": "asset",
                "label": "Asset",
                "description": "A digital artefact — file, image, dataset, credential.",
                "default_phase": "water",
                "allowed_phases": ["gas", "water", "ice"],
                "fractal": False,
                "icon": "file",
            },
        ],
    },
    {
        "name": "Signals",
        "slug": "signals",
        "description": "External signals and measurements ingested into the graph",
        "types": [
            {
                "slug": "news_item",
                "label": "News Item",
                "description": "An external news article or event ingested into the network.",
                "default_phase": "water",
                "allowed_phases": ["water", "ice"],
                "fractal": False,
                "icon": "newspaper",
            },
            {
                "slug": "measurement",
                "label": "Measurement",
                "description": "A quantitative signal or metric observation.",
                "default_phase": "ice",
                "allowed_phases": ["water", "ice"],
                "fractal": False,
                "icon": "chart",
            },
        ],
    },
    {
        "name": "Topology",
        "slug": "topology",
        "description": "Graph-structural and network-topology nodes",
        "types": [
            {
                "slug": "federation_node",
                "label": "Federation Node",
                "description": "A peer Coherence Network instance in the federation.",
                "default_phase": "water",
                "allowed_phases": ["water", "ice"],
                "fractal": False,
                "icon": "globe",
            },
            {
                "slug": "axis",
                "label": "Axis",
                "description": "A navigational dimension or resonance axis.",
                "default_phase": "ice",
                "allowed_phases": ["water", "ice"],
                "fractal": True,
                "icon": "arrows",
            },
            {
                "slug": "frequency",
                "label": "Frequency",
                "description": "A periodic signal or harmonic dimension.",
                "default_phase": "water",
                "allowed_phases": ["water", "ice"],
                "fractal": False,
                "icon": "wave",
            },
            {
                "slug": "message",
                "label": "Message",
                "description": "A communication event between agents or systems.",
                "default_phase": "ice",
                "allowed_phases": ["water", "ice"],
                "fractal": False,
                "icon": "envelope",
            },
        ],
    },
]


# ── Valid phase transitions ───────────────────────────────────────────

VALID_PHASE_TRANSITIONS: dict[str, list[str]] = {
    "gas":   ["water", "ice"],
    "water": ["ice", "gas"],
    "ice":   ["water", "gas"],
}


# ── Derived lookups ───────────────────────────────────────────────────

# Flat set of all canonical node type slugs
CANONICAL_NODE_TYPES: set[str] = {
    t["slug"]
    for f in NODE_TYPE_FAMILIES
    for t in f["types"]
}

# Slug -> type metadata
NODE_TYPE_REGISTRY: dict[str, dict] = {
    t["slug"]: {**t, "family": f["name"], "family_slug": f["slug"]}
    for f in NODE_TYPE_FAMILIES
    for t in f["types"]
}

# Flat list with family context (for APIs)
ALL_NODE_TYPES: list[dict] = [
    {**t, "family": f["name"], "family_slug": f["slug"]}
    for f in NODE_TYPE_FAMILIES
    for t in f["types"]
]

CANONICAL_NODE_TYPE_COUNT = len(CANONICAL_NODE_TYPES)


def is_valid_phase_transition(from_phase: str, to_phase: str) -> bool:
    """Return True if the from_phase → to_phase transition is allowed."""
    if from_phase == to_phase:
        return False  # no-op is not a transition
    return to_phase in VALID_PHASE_TRANSITIONS.get(from_phase, [])


def is_phase_allowed_for_type(node_type: str, phase: str) -> bool:
    """Return True if the given phase is allowed for the given node type."""
    meta = NODE_TYPE_REGISTRY.get(node_type)
    if not meta:
        return True  # unknown types are permissive
    return phase in meta.get("allowed_phases", ["gas", "water", "ice"])
