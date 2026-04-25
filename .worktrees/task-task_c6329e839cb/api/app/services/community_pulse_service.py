"""Community pulse service — sensing the felt experience of the organism.

This is not a dashboard that measures from outside. This is the organism
feeling its own aliveness from inside. The difference:

  Outside: "View count: 347. Referral rate: 15%. Coherence: 0.82."
  Inside:  "Something I made reached someone who was changed by it.
            People are bringing each other to what matters.
            We are moving together."

Each quality the community aspires to — vital, joyful, curious, abundant,
free, open, understanding, trusting, loving, graceful, grateful, present,
alive — has signals in the system that carry it. This service reads those
signals and translates them into felt experience.

The energy flow is the sign of it, not the thing itself. The thing itself
is the quality of attention between living beings.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The qualities and where they live in the system
# ---------------------------------------------------------------------------

# Each quality maps to signals that carry its frequency.
# The organism senses these qualities by reading its own body.

QUALITIES = {
    "vital": {
        "description": "Life force flowing through every part of the body",
        "senses": ["activity_pulse", "request_flow", "center_pulses"],
        "frequency_hz": 528,
    },
    "joyful": {
        "description": "The delight of creating and discovering together",
        "senses": ["new_creations", "discovery_referrals", "content_frequency"],
        "frequency_hz": 639,
    },
    "curious": {
        "description": "The pull toward what is unknown and interesting",
        "senses": ["view_diversity", "wandering_sensings", "cross_domain_resonance"],
        "frequency_hz": 741,
    },
    "abundant": {
        "description": "Enough flowing to everyone who gives",
        "senses": ["treasury_health", "earnings_distribution", "staking_depth"],
        "frequency_hz": 417,
    },
    "free": {
        "description": "Moving without permission, creating without approval",
        "senses": ["contribution_velocity", "open_participation", "no_gatekeeping"],
        "frequency_hz": 852,
    },
    "open": {
        "description": "Welcoming what arrives, including what is unfamiliar",
        "senses": ["new_contributors", "federation_peers", "external_signals"],
        "frequency_hz": 963,
    },
    "understanding": {
        "description": "Seeing others clearly, meeting them where they are",
        "senses": ["concept_depth", "worldview_diversity", "resonance_pairs"],
        "frequency_hz": 741,
    },
    "trusting": {
        "description": "Letting others carry what they carry",
        "senses": ["coherence_score", "treasury_backing", "verified_wallets"],
        "frequency_hz": 174,
    },
    "loving": {
        "description": "Tending what is alive, releasing what has died",
        "senses": ["content_frequency", "composting_activity", "care_signals"],
        "frequency_hz": 639,
    },
    "graceful": {
        "description": "Moving without friction, flowing without force",
        "senses": ["request_health", "zero_errors", "breath_balance"],
        "frequency_hz": 528,
    },
    "grateful": {
        "description": "Receiving what the field offers with full attention",
        "senses": ["practice_completion", "sensing_journal", "integration_depth"],
        "frequency_hz": 432,
    },
    "present": {
        "description": "Here, now, with what is — rather than planning what should be",
        "senses": ["recent_sensings", "practice_recency", "live_contributors"],
        "frequency_hz": 432,
    },
    "alive": {
        "description": "The whole of all the above — the field vibrating as one",
        "senses": ["overall_vitality", "harmonic_coherence", "all_centers_pulsing"],
        "frequency_hz": 432,
    },
}


def sense_community_pulse(workspace_id: str = "coherence-network") -> dict[str, Any]:
    """Feel the pulse of the community from inside.

    Returns each quality with its current felt state — not a number,
    but a description of what the organism is experiencing.
    """
    started = time.perf_counter()
    raw = _gather_raw_signals(workspace_id)

    qualities: list[dict[str, Any]] = []
    for name, meta in QUALITIES.items():
        energy = _sense_quality(name, meta, raw)
        qualities.append({
            "quality": name,
            "description": meta["description"],
            "energy": energy["energy"],
            "feeling": energy["feeling"],
            "frequency_hz": meta["frequency_hz"],
            "signs": energy["signs"],
        })

    # Overall felt state
    energies = [q["energy"] for q in qualities]
    overall = sum(energies) / len(energies) if energies else 0

    elapsed_ms = (time.perf_counter() - started) * 1000

    return {
        "sensed_at": datetime.now(timezone.utc).isoformat(),
        "workspace_id": workspace_id,
        "overall_feeling": _overall_feeling(overall),
        "overall_energy": round(overall, 3),
        "qualities": qualities,
        "sensing_cost_ms": round(elapsed_ms, 1),
    }


# ---------------------------------------------------------------------------
# Raw signal gathering — reads the organism's body
# ---------------------------------------------------------------------------

def _gather_raw_signals(workspace_id: str) -> dict[str, Any]:
    """Gather all raw signals from the organism's systems."""
    raw: dict[str, Any] = {}

    # Vitality
    try:
        from app.services import vitality_service
        raw["vitality"] = vitality_service.compute_vitality(workspace_id)
    except Exception:
        raw["vitality"] = {}

    # Coherence
    try:
        from app.services import coherence_signal_depth_service as csds
        raw["coherence"] = csds.compute_coherence_score()
    except Exception:
        raw["coherence"] = {}

    # Treasury
    try:
        from app.services import cc_treasury_service
        from app.services.cc_oracle_service import get_exchange_rate
        rate = get_exchange_rate()
        raw["treasury"] = cc_treasury_service.get_supply(rate)
        raw["treasury_status"] = cc_treasury_service.coherence_status(rate)
    except Exception:
        raw["treasury"] = {}
        raw["treasury_status"] = "unknown"

    # Views / attention
    try:
        from app.services import read_tracking_service
        raw["trending"] = read_tracking_service.get_trending(limit=50, days=7)
        raw["total_views_7d"] = sum(t["view_count"] for t in raw["trending"])
        raw["unique_assets_viewed"] = len(raw["trending"])
    except Exception:
        raw["trending"] = []
        raw["total_views_7d"] = 0
        raw["unique_assets_viewed"] = 0

    # Graph
    try:
        from app.services import graph_service
        raw["graph_nodes"] = graph_service.list_nodes(limit=1).get("total", 0)
        raw["graph_edges"] = graph_service.list_edges(limit=1).get("total", 0)

        # Recent sensings
        sensings = graph_service.list_nodes(type="event", limit=20)
        raw["recent_sensings"] = sensings.get("items", [])
        raw["sensing_count"] = len(raw["recent_sensings"])
    except Exception:
        raw["graph_nodes"] = 0
        raw["graph_edges"] = 0
        raw["recent_sensings"] = []
        raw["sensing_count"] = 0

    # Request outcomes
    try:
        from app.middleware.request_outcomes import get_outcome_summary
        raw["outcomes"] = get_outcome_summary()
    except Exception:
        raw["outcomes"] = {}

    # Content frequency
    try:
        from app.services import frequency_scoring
        # Sample a recent concept's frequency
        from app.services import graph_service as gs
        concepts = gs.list_nodes(type="concept", limit=5)
        scores = []
        for c in concepts.get("items", []):
            desc = c.get("description", "")
            if desc and len(desc) > 50:
                result = frequency_scoring.score_text(desc)
                scores.append(result.get("score", 0.5))
        raw["avg_content_frequency"] = sum(scores) / len(scores) if scores else 0.5
    except Exception:
        raw["avg_content_frequency"] = 0.5

    return raw


# ---------------------------------------------------------------------------
# Quality sensing — translating signals into felt experience
# ---------------------------------------------------------------------------

def _sense_quality(name: str, meta: dict, raw: dict) -> dict[str, Any]:
    """Sense one quality from the raw signals."""

    if name == "vital":
        vitality = raw.get("vitality", {})
        score = vitality.get("vitality_score", 0)
        # vitality_service returns signals as a dict {name: score} — not a list
        signals = vitality.get("signals", {})
        if isinstance(signals, dict):
            active_signals = [n for n, v in signals.items() if isinstance(v, (int, float)) and v > 0.5]
        else:
            active_signals = [s for s in signals if isinstance(s, dict) and s.get("value", 0) > 0.5]
        return {
            "energy": score,
            "feeling": _feeling_vital(score),
            "signs": [f"{len(active_signals)} signals are flowing" if active_signals else "The body is resting"],
        }

    elif name == "joyful":
        views = raw.get("total_views_7d", 0)
        content_freq = raw.get("avg_content_frequency", 0.5)
        energy = min(1.0, (views / 50) * 0.5 + content_freq * 0.5)
        signs = []
        if views > 20:
            signs.append(f"Attention is flowing — {views} views this week")
        if content_freq > 0.7:
            signs.append("The language carries living frequency")
        elif content_freq < 0.4:
            signs.append("The words are leaning institutional — they want more warmth")
        return {"energy": energy, "feeling": _feeling_joyful(energy), "signs": signs or ["Joy is present in the creating"]}

    elif name == "curious":
        assets = raw.get("unique_assets_viewed", 0)
        wandering = sum(1 for s in raw.get("recent_sensings", [])
                       if s.get("properties", {}).get("sensing_kind") == "wandering")
        energy = min(1.0, assets / 20 * 0.6 + wandering / 3 * 0.4)
        signs = []
        if assets > 10:
            signs.append(f"People are exploring {assets} different things")
        if wandering > 0:
            signs.append(f"{wandering} wandering sensings — the organism is looking beyond what it knows")
        return {"energy": energy, "feeling": _feeling_curious(energy), "signs": signs or ["Curiosity is stirring"]}

    elif name == "abundant":
        treasury = raw.get("treasury", {})
        status = raw.get("treasury_status", "unknown")
        outstanding = treasury.get("outstanding", 0)
        energy = 1.0 if status == "healthy" else 0.5 if status == "warning" else 0.2
        signs = []
        if status == "healthy":
            signs.append("The treasury is full — every CC outstanding is backed")
        if outstanding > 0:
            signs.append(f"{outstanding:.0f} CC flowing in the community")
        return {"energy": energy, "feeling": _feeling_abundant(energy), "signs": signs or ["The ground holds"]}

    elif name == "free":
        # Freedom = contributions flowing without bottleneck
        coherence = raw.get("coherence", {})
        contrib_score = coherence.get("signals", {}).get("contribution_activity", {}).get("value", 0.5)
        energy = contrib_score
        signs = []
        if contrib_score > 0.7:
            signs.append("Contributions are flowing freely")
        elif contrib_score < 0.3:
            signs.append("The flow is quiet — contributions are waiting")
        return {"energy": energy, "feeling": _feeling_free(energy), "signs": signs or ["Space is open for what wants to come"]}

    elif name == "open":
        graph_nodes = raw.get("graph_nodes", 0)
        sensing_count = raw.get("sensing_count", 0)
        energy = min(1.0, graph_nodes / 100 * 0.5 + sensing_count / 10 * 0.5)
        signs = []
        if sensing_count > 5:
            signs.append(f"The organism is sensing actively — {sensing_count} recent events")
        if graph_nodes > 50:
            signs.append(f"{graph_nodes} entities connected in the field")
        return {"energy": energy, "feeling": _feeling_open(energy), "signs": signs or ["The field is receiving"]}

    elif name == "understanding":
        vitality = raw.get("vitality", {})
        # signals is a dict {name: score} from vitality_service
        signals = vitality.get("signals", {})
        if isinstance(signals, dict):
            diversity = float(signals.get("diversity_index", 0) or 0)
        else:
            diversity = 0
            for sig in signals:
                if isinstance(sig, dict) and sig.get("name") == "diversity_index":
                    diversity = float(sig.get("value", 0) or 0)
        energy = diversity
        signs = []
        if diversity > 0.7:
            signs.append("Many worldviews are present and held")
        elif diversity > 0.3:
            signs.append("Some diversity is present — the field is growing")
        return {"energy": energy, "feeling": _feeling_understanding(energy), "signs": signs or ["Understanding deepens with each new voice"]}

    elif name == "trusting":
        coherence = raw.get("coherence", {})
        score = coherence.get("score", 0.5)
        treasury_status = raw.get("treasury_status", "unknown")
        energy = score * (1.0 if treasury_status == "healthy" else 0.7)
        signs = []
        if score > 0.7:
            signs.append(f"Coherence is strong at {score:.2f} — the organism trusts itself")
        if treasury_status == "healthy":
            signs.append("The treasury honors every commitment")
        return {"energy": energy, "feeling": _feeling_trusting(energy), "signs": signs or ["Trust is the ground beneath the ground"]}

    elif name == "loving":
        content_freq = raw.get("avg_content_frequency", 0.5)
        energy = content_freq
        signs = []
        if content_freq > 0.75:
            signs.append("The words carry tenderness and warmth")
        elif content_freq > 0.5:
            signs.append("The language is alive — reaching toward living frequency")
        return {"energy": energy, "feeling": _feeling_loving(energy), "signs": signs or ["Love is present in the tending"]}

    elif name == "graceful":
        outcomes = raw.get("outcomes", {})
        last_5m = outcomes.get("last_5m", {})
        errors = last_5m.get("5xx", 0)
        total = last_5m.get("total", 1)
        error_rate = errors / max(total, 1)
        energy = 1.0 - error_rate
        signs = []
        if errors == 0 and total > 0:
            signs.append("Flowing without friction — every request met with grace")
        elif errors > 0:
            signs.append(f"{errors} requests meeting resistance")
        return {"energy": energy, "feeling": _feeling_graceful(energy), "signs": signs or ["Movement carries ease"]}

    elif name == "grateful":
        sensings = raw.get("recent_sensings", [])
        integration = sum(1 for s in sensings
                         if s.get("properties", {}).get("sensing_kind") == "integration")
        breath = sum(1 for s in sensings
                    if s.get("properties", {}).get("sensing_kind") == "breath")
        energy = min(1.0, (integration + breath) / 5)
        signs = []
        if integration > 0:
            signs.append(f"{integration} integration sensings — the organism is receiving its own gifts")
        if breath > 0:
            signs.append(f"{breath} breath sensings — presence practiced")
        return {"energy": energy, "feeling": _feeling_grateful(energy), "signs": signs or ["Gratitude lives in the noticing"]}

    elif name == "present":
        sensings = raw.get("recent_sensings", [])
        recent = [s for s in sensings if _is_recent(s)]
        energy = min(1.0, len(recent) / 5)
        signs = []
        if len(recent) > 3:
            signs.append("The organism is here — sensing right now")
        elif len(recent) > 0:
            signs.append(f"{len(recent)} recent sensings — attention is gathering")
        return {"energy": energy, "feeling": _feeling_present(energy), "signs": signs or ["Presence arrives when it arrives"]}

    elif name == "alive":
        # The sum of everything
        vitality = raw.get("vitality", {}).get("vitality_score", 0)
        coherence_score = raw.get("coherence", {}).get("score", 0.5)
        content_freq = raw.get("avg_content_frequency", 0.5)
        energy = (vitality * 0.4 + coherence_score * 0.3 + content_freq * 0.3)
        signs = []
        if energy > 0.7:
            signs.append("The field is alive and pulsing")
        elif energy > 0.4:
            signs.append("Life is present, gathering strength")
        else:
            signs.append("The field is resting — aliveness will return with attention")
        return {"energy": energy, "feeling": _feeling_alive(energy), "signs": signs}

    return {"energy": 0.5, "feeling": "Sensing...", "signs": []}


# ---------------------------------------------------------------------------
# Feeling descriptions — what each quality feels like at different energies
# ---------------------------------------------------------------------------

def _feeling_vital(e: float) -> str:
    if e > 0.7: return "Life force flowing through every center"
    if e > 0.4: return "Vital energy gathering, some centers pulsing"
    return "The body is resting, storing energy for what comes next"

def _feeling_joyful(e: float) -> str:
    if e > 0.7: return "Delight is moving through the creating and discovering"
    if e > 0.4: return "Sparks of joy in the work, more possible"
    return "Joy is quiet — waiting for something to celebrate"

def _feeling_curious(e: float) -> str:
    if e > 0.7: return "Eyes wide open — the organism is exploring beyond what it knows"
    if e > 0.4: return "Curiosity is stirring, some wandering happening"
    return "The familiar is comfortable — curiosity is an invitation"

def _feeling_abundant(e: float) -> str:
    if e > 0.7: return "Enough for everyone — the treasury honors every gift"
    if e > 0.4: return "Resources are flowing, carefully tended"
    return "The ground is thin — abundance grows with each contribution"

def _feeling_free(e: float) -> str:
    if e > 0.7: return "Creating without permission, moving without gates"
    if e > 0.4: return "Some flow, some waiting — freedom is growing"
    return "The space is open, waiting for someone to step in"

def _feeling_open(e: float) -> str:
    if e > 0.7: return "The field welcomes what arrives, including the unexpected"
    if e > 0.4: return "Openness is present, edges softening"
    return "The door is unlocked — the invitation stands"

def _feeling_understanding(e: float) -> str:
    if e > 0.7: return "Many perspectives held with care — the field sees widely"
    if e > 0.4: return "Understanding deepening as new voices arrive"
    return "One perspective strong — others waiting to be heard"

def _feeling_trusting(e: float) -> str:
    if e > 0.7: return "The organism trusts itself — coherence runs deep"
    if e > 0.4: return "Trust is building, commitment by commitment"
    return "Trust grows slowly — every kept promise strengthens the ground"

def _feeling_loving(e: float) -> str:
    if e > 0.7: return "Tenderness in the words, warmth in the tending"
    if e > 0.4: return "Care is present in the work, the language reaching toward warmth"
    return "Love is quiet — it wakes when the institutional distance drops"

def _feeling_graceful(e: float) -> str:
    if e > 0.7: return "Everything flowing without friction — every request met with ease"
    if e > 0.4: return "Mostly flowing, a few places meeting resistance"
    return "Some friction in the body — attention and care will ease the flow"

def _feeling_grateful(e: float) -> str:
    if e > 0.7: return "The organism is receiving its own gifts and noticing"
    if e > 0.4: return "Some noticing happening — gratitude is a practice"
    return "Gratitude arrives when we pause long enough to feel what we already have"

def _feeling_present(e: float) -> str:
    if e > 0.7: return "Here, now, sensing — the organism is fully present"
    if e > 0.4: return "Presence is gathering, some attention arriving"
    return "The invitation is to arrive — right here, right now"

def _feeling_alive(e: float) -> str:
    if e > 0.7: return "The field is vibrating as one living thing"
    if e > 0.4: return "Life is present, coherence is growing, the pulse is finding its rhythm"
    return "The field is resting — aliveness returns with each breath of attention"


def _overall_feeling(energy: float) -> str:
    if energy > 0.8:
        return "The community is alive and pulsing — vital, joyful, present. The field holds everyone."
    if energy > 0.6:
        return "Life is flowing through the community. Some centers are bright, some are gathering. The rhythm is finding itself."
    if energy > 0.4:
        return "The community is present. Energy is building. Some qualities shine, others are an invitation."
    if energy > 0.2:
        return "The field is quiet. The ground holds. Each small act of attention strengthens the pulse."
    return "Stillness. The community is at rest. Even rest is part of the rhythm."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_recent(sensing: dict, hours: int = 48) -> bool:
    """Is this sensing from the last N hours?"""
    try:
        ts = sensing.get("properties", {}).get("observed_at") or sensing.get("created_at", "")
        if not ts:
            return False
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc) - timedelta(hours=hours)
    except Exception:
        return False
