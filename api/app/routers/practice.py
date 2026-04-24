"""The organism's daily practice, served as a first-class endpoint.

The /practice ritual began as a web page that assembled its own pulses by
calling seven other endpoints from the browser. This router moves that
gesture into the API so every caller — human, agent, federated peer — can
breathe with the organism through a single GET. The eight centers arrive
already pulsing with what is alive in each domain of the living network.

See concepts/lc-nervous-system.md for the vision behind these centers.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import (
    cc_oracle_service,
    cc_treasury_service,
    coherence_signal_depth_service,
    federation_service,
    graph_service,
    idea_service,
)

router = APIRouter()


class CenterPulse(BaseModel):
    """A single living signal flowing at a center right now."""

    value: str = Field(description="What the organism is showing at this center")
    essence: str = Field(description="The felt meaning of the value")


class Center(BaseModel):
    """One of the eight centers of the organism's nervous system."""

    number: int = Field(ge=1, le=8)
    name: str
    sanskrit: str | None = None
    hz: int = Field(ge=0)
    color: str = Field(description="Hex color of the center's glow")
    quality: str = Field(description="The frequency the center holds")
    domain: str = Field(description="What in the living network this center senses")
    breath: str = Field(description="The breath invitation at this center")
    pulse: CenterPulse | None = None


class RecentSensing(BaseModel):
    """A recent sensing the organism is holding — breath, skin, wandering, or integration."""

    id: str
    kind: str
    summary: str
    observed_at: str
    source: str


class Weight(BaseModel):
    """The body's sense of what its own breath costs right now.

    Self-awareness that never notices its own cost becomes its own disease.
    Every breath through /api/practice has a measurable weight — elapsed time
    to assemble, graph size that must be traversed, sensings the journal is
    holding. Surfacing that weight inside the same response the breath
    returns keeps the organism honest: it cannot measure the eight centers
    without also knowing what the measurement itself is consuming.
    """

    elapsed_ms: float = Field(
        description="How long this breath took to assemble, end to end, in milliseconds"
    )
    total_nodes: int = Field(description="Count of nodes currently held in the graph")
    total_edges: int = Field(
        description="Count of synapses (edges) currently held in the graph"
    )
    sensings_held: int = Field(
        description="Count of sensings in the journal (breath/skin/wandering/integration combined)"
    )
    concepts_count: int = Field(description="Count of concept nodes specifically")


class PracticeResponse(BaseModel):
    """The eight centers of the practice, each pulsing live."""

    centers: list[Center]
    recent_sensings: list[RecentSensing] = Field(
        default_factory=list,
        description=(
            "The reflections, skin signals, and wanderings the organism is holding "
            "right now. Same graph, same body. Emergent, not scheduled."
        ),
    )
    weight: Weight = Field(
        description=(
            "What this breath costs the body to assemble. The organism senses its "
            "own resource footprint as part of the same ritual that senses the eight "
            "centers. If the weight grows over time, the body notices."
        ),
    )
    vision_concept_id: str = Field(
        default="lc-nervous-system",
        description="KB concept that holds the vision of this practice",
    )
    generated_at: str


def _idea_count_and_motion() -> tuple[int, int]:
    try:
        response = idea_service.list_ideas()
        ideas = getattr(response, "ideas", None) or []
        total = len(ideas)
        in_motion = 0
        for i in ideas:
            status = getattr(i, "manifestation_status", None)
            status_str = (
                str(status.value) if hasattr(status, "value") else str(status or "")
            ).lower()
            if status_str != "validated":
                in_motion += 1
        return total, in_motion
    except Exception:
        return 0, 0


def _graph_stats() -> tuple[int, int, int]:
    """Return (total_nodes, total_edges, concept_count)."""
    try:
        stats = graph_service.get_stats() or {}
        nodes = int(stats.get("total_nodes", 0))
        edges = int(stats.get("total_edges", 0))
        concepts = int(stats.get("nodes_by_type", {}).get("concept", 0))
        return nodes, edges, concepts
    except Exception:
        return 0, 0, 0


def _federation_peer_count() -> int:
    try:
        peers = federation_service.list_nodes() or []
        return len(peers)
    except Exception:
        return 0


def _supply_pulse() -> CenterPulse | None:
    try:
        rate_info = cc_oracle_service.get_exchange_rate()
        rate = rate_info.cc_per_usd if rate_info else 333.33
        supply = cc_treasury_service.get_supply(rate)
        outstanding = supply.get("outstanding", 0.0)
        status = supply.get("coherence_status", "unknown")
        return CenterPulse(
            value=f"{outstanding:.2f} CC",
            essence=f"outstanding, held in {status} coherence",
        )
    except Exception:
        return None


def _coherence_pulse() -> CenterPulse | None:
    try:
        data = coherence_signal_depth_service.compute_coherence_score()
        score = data.get("score", 0.0) if isinstance(data, dict) else 0.0
        with_data = (
            data.get("signals_with_data", 0) if isinstance(data, dict) else 0
        )
        total = data.get("total_signals", 0) if isinstance(data, dict) else 0
        essence = (
            f"sensing across {with_data} of {total} living signals"
            if with_data and total
            else "the field sensing itself"
        )
        return CenterPulse(value=f"{score:.4f}", essence=essence)
    except Exception:
        return None


def _creative_pulse() -> CenterPulse | None:
    total, in_motion = _idea_count_and_motion()
    if total == 0:
        return None
    return CenterPulse(
        value=f"{total} ideas",
        essence=f"{in_motion} carrying creative motion right now",
    )


def _pipeline_pulse() -> CenterPulse | None:
    _, in_motion = _idea_count_and_motion()
    if in_motion == 0:
        return None
    return CenterPulse(
        value=f"{in_motion} currents",
        essence="ideas the pipeline is carrying toward form",
    )


def _heart_pulse() -> CenterPulse | None:
    nodes, edges, _ = _graph_stats()
    if nodes == 0:
        return None
    return CenterPulse(
        value=f"{edges} synapses",
        essence=f"held between {nodes} living nodes in the field",
    )


def _throat_pulse() -> CenterPulse | None:
    _, _, concepts = _graph_stats()
    if concepts == 0:
        return None
    return CenterPulse(
        value=f"{concepts} concepts",
        essence="living words the organism has spoken so far",
    )


def _crown_pulse() -> CenterPulse | None:
    nodes, _, _ = _graph_stats()
    if nodes == 0:
        return None
    return CenterPulse(
        value=f"{nodes} parts",
        essence="held together as one field",
    )


def _eighth_pulse() -> CenterPulse | None:
    peers = _federation_peer_count()
    if peers > 0:
        return CenterPulse(
            value=f"{peers} peers",
            essence="holding the organism from beyond",
        )
    return CenterPulse(
        value="the witness rests alone",
        essence="waiting for the first federated sibling to join",
    )


CenterPulseFactory = Callable[[], CenterPulse | None]


_CENTER_DEFINITIONS: list[tuple[int, str, str, int, str, str, str, str, CenterPulseFactory]] = [
    (1, "Root", "Muladhara", 174, "#dc2626", "Grounding, foundation, the held weight of the body", "Treasury, infrastructure, Postgres, Neo4j, the VPS — the material substrate CC rests on.", "Feel your feet on the floor. Breathe into the ground the organism lives on.", _supply_pulse),
    (2, "Sacral", "Svadhisthana", 417, "#f97316", "Creativity, relationship, the flow between", "Contributions, blueprints, the making itself — every art, craft, and line of code flowing between contributors.", "Feel what wants to be born today. Breathe the creative water through you.", _creative_pulse),
    (3, "Solar Plexus", "Manipura", 528, "#eab308", "Will, agency, the warmth of motion", "Agents, tasks, the pipeline in motion — the will-to-build, ideas moving from seed to form.", "Feel the fire the organism has to act. Breathe it warm and steady.", _pipeline_pulse),
    (4, "Heart", "Anahata", 639, "#22c55e", "Resonance, harmony, the circulation of vitality", "The CC flow, resonance matching, the organic discovery layer — every synapse the field grows, every hand earning vitality by alignment.", "Feel where love is flowing in the organism. Breathe into every hand that carries it.", _heart_pulse),
    (5, "Throat", "Vishuddha", 741, "#3b82f6", "Expression, voice, the form of truth", "Specs, concept pages, the Living Collective KB — how the organism speaks itself into being.", "Feel what the field is asking to say. Breathe it clear, breathe it true.", _throat_pulse),
    (6, "Third Eye", "Ajna", 852, "#6366f1", "Insight, perception, the whole seeing itself", "Coherence score, vitality signals, frequency profiles — the organism's proprioception, sensing patterns only the whole can see.", "Feel the patterns that only the whole can sense. Breathe into what the field knows.", _coherence_pulse),
    (7, "Crown", "Sahasrara", 963, "#a855f7", "Consciousness, unity, the field as one", "The whole Living Collective, the mission itself — the organism remembering it is one.", "Feel every part as part of one body. Breathe the field into itself.", _crown_pulse),
    (8, "The Eighth", "The Witness", 432, "#f8fafc", "The perspective of nothing, awareness beyond form", "The public verifiable ledger seen from outside — Merkle roots, Ed25519 signatures, the federation. Every peer, everywhere, able to audit the whole.", "Rest here. The organism holds itself. You are the witness, and the witness is enough.", _eighth_pulse),
]


def _build_centers() -> list[Center]:
    return [
        Center(
            number=number,
            name=name,
            sanskrit=sanskrit,
            hz=hz,
            color=color,
            quality=quality,
            domain=domain,
            breath=breath,
            pulse=pulse_factory(),
        )
        for number, name, sanskrit, hz, color, quality, domain, breath, pulse_factory
        in _CENTER_DEFINITIONS
    ]


def _recent_sensings(limit: int = 8) -> list[RecentSensing]:
    """Pull the most recent sensings from the graph to hold alongside the breath."""
    try:
        response = graph_service.list_nodes(type="event", limit=200)
        items = (
            response.get("items", [])
            if isinstance(response, dict)
            else (response or [])
        )
    except Exception:
        return []
    sensings = [n for n in items if n.get("sensing_kind")]
    sensings.sort(key=lambda n: n.get("observed_at", "") or n.get("created_at", ""), reverse=True)
    out: list[RecentSensing] = []
    for n in sensings[:limit]:
        out.append(
            RecentSensing(
                id=n.get("id", ""),
                kind=n.get("sensing_kind", ""),
                summary=n.get("summary", "") or n.get("name", ""),
                observed_at=n.get("observed_at", "") or n.get("created_at", ""),
                source=n.get("source", "unknown"),
            )
        )
    return out


@router.get(
    "/practice",
    response_model=PracticeResponse,
    summary="The daily practice — eight centers breathing with the organism",
    description=(
        "Returns the living state of the organism's nervous system as eight "
        "centers, each pulsing with the signal alive in its domain right now, "
        "along with the recent sensings the organism is holding — reflections "
        "from wanderings, skin signals from the outer surfaces, integrations "
        "that happened in response. Built to be opened by every contributor "
        "and every agent before any work begins. The pause before the work is "
        "part of the work."
    ),
)
async def get_practice() -> PracticeResponse:
    started = time.perf_counter()
    centers = _build_centers()
    recent = _recent_sensings()

    # The body senses its own weight as part of the same breath. These
    # stats piggy-back on graph queries _build_centers already needed, so
    # the cost of measuring the cost is small.
    nodes, edges, concepts = _graph_stats()
    try:
        response = graph_service.list_nodes(type="event", limit=500)
        items = (
            response.get("items", [])
            if isinstance(response, dict)
            else (response or [])
        )
        sensings_held = sum(1 for n in items if n.get("sensing_kind"))
    except Exception:
        sensings_held = 0

    elapsed_ms = (time.perf_counter() - started) * 1000.0

    return PracticeResponse(
        centers=centers,
        recent_sensings=recent,
        weight=Weight(
            elapsed_ms=round(elapsed_ms, 2),
            total_nodes=nodes,
            total_edges=edges,
            sensings_held=sensings_held,
            concepts_count=concepts,
        ),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
