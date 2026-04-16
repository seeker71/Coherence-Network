"""Energy sensing — the organism sees itself as frequencies and harmonies.

Every signal the system can sense carries a frequency. This router
aggregates all sensing into a unified energy map:
  - Internal: health, coherence, practice centers, request flow
  - Community: contributions, views, referrals, staking, vitality
  - External: federation peers, CI/CD, deployment health
  - Frequency: content resonance, concept harmony, contributor coherence

The dashboard doesn't just show numbers — it shows harmonies and
dissonances. When two signals resonate (both thriving or both struggling),
that's a harmony. When they diverge, that's a dissonance worth attention.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)

router = APIRouter()


# ── Data structures ──────────────────────────────────────────────

FREQUENCY_MAP = {
    # Center frequencies from the practice (Hz)
    "root": 174,
    "sacral": 417,
    "solar_plexus": 528,
    "heart": 639,
    "throat": 741,
    "third_eye": 852,
    "crown": 963,
    "eighth": 432,
}


# ── Endpoints ────────────────────────────────────────────────────

@router.get(
    "/energy/sense",
    summary="Full energy sensing — all signals, all scales",
    description=(
        "The organism senses itself across three scales: "
        "internal body, community body, and the world. "
        "Each signal carries a frequency and vitality state."
    ),
)
async def sense_all(
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Assemble the complete energy map."""
    started = time.perf_counter()

    internal = await _sense_internal()
    community = await _sense_community(workspace_id)
    external = await _sense_external()
    harmonies = _compute_harmonies(internal, community, external)

    elapsed_ms = (time.perf_counter() - started) * 1000

    return {
        "sensed_at": datetime.now(timezone.utc).isoformat(),
        "workspace_id": workspace_id,
        "internal": internal,
        "community": community,
        "external": external,
        "harmonies": harmonies,
        "sensing_cost_ms": round(elapsed_ms, 1),
    }


@router.get(
    "/energy/harmonies",
    summary="Frequency harmonies and dissonances",
    description="Where signals resonate and where they diverge.",
)
async def harmonies_only(
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Just the harmonies — the relationships between signals."""
    internal = await _sense_internal()
    community = await _sense_community(workspace_id)
    external = await _sense_external()
    return _compute_harmonies(internal, community, external)


# ── Internal body sensing ────────────────────────────────────────

async def _sense_internal() -> dict[str, Any]:
    """Sense the internal body: health, practice centers, request flow."""
    signals: list[dict[str, Any]] = []

    # Coherence score
    try:
        from app.services import coherence_signal_depth_service as csds
        coherence = csds.compute_coherence_score()
        signals.append({
            "id": "coherence_score",
            "label": "Coherence",
            "value": coherence.get("score", 0.5),
            "max": 1.0,
            "frequency_hz": 852,
            "vitality": _vitality_label(coherence.get("score", 0.5)),
            "detail": f"{coherence.get('signals_with_data', 0)} signals with data",
        })
    except Exception:
        signals.append(_dormant_signal("coherence_score", "Coherence", 852))

    # Treasury
    try:
        from app.services import cc_treasury_service
        from app.services.cc_oracle_service import get_exchange_rate
        rate = get_exchange_rate()
        status = cc_treasury_service.coherence_status(rate)
        supply = cc_treasury_service.get_supply(rate)
        signals.append({
            "id": "treasury",
            "label": "Treasury",
            "value": 1.0 if status == "healthy" else 0.5 if status == "warning" else 0.2,
            "max": 1.0,
            "frequency_hz": 174,
            "vitality": status,
            "detail": f"{supply.get('outstanding', 0):.0f} CC outstanding",
        })
    except Exception:
        signals.append(_dormant_signal("treasury", "Treasury", 174))

    # Request flow (recent outcomes)
    try:
        from app.middleware.request_outcomes import get_outcome_summary
        outcomes = get_outcome_summary()
        last_5m = outcomes.get("last_5m", {})
        total = last_5m.get("total", 0)
        errors = last_5m.get("5xx", 0)
        health = 1.0 if total > 0 and errors == 0 else 0.7 if errors < 3 else 0.3
        signals.append({
            "id": "request_flow",
            "label": "Request Flow",
            "value": health,
            "max": 1.0,
            "frequency_hz": 528,
            "vitality": _vitality_label(health),
            "detail": f"{total} requests, {errors} errors (5m)",
        })
    except Exception:
        signals.append(_dormant_signal("request_flow", "Request Flow", 528))

    # Practice centers
    try:
        from app.routers.practice import _build_centers
        centers = _build_centers()
        for center in centers:
            signals.append({
                "id": f"center_{center.get('name', 'unknown').lower().replace(' ', '_')}",
                "label": center.get("name", "Unknown"),
                "value": 1.0 if center.get("pulse") else 0.3,
                "max": 1.0,
                "frequency_hz": center.get("hz", 432),
                "vitality": "pulsing" if center.get("pulse") else "quiet",
                "detail": center.get("pulse", "Quiet"),
            })
    except Exception:
        pass

    return {"scale": "internal", "signals": signals}


# ── Community body sensing ───────────────────────────────────────

async def _sense_community(workspace_id: str) -> dict[str, Any]:
    """Sense the community body: vitality, contributions, views, frequency."""
    signals: list[dict[str, Any]] = []

    # Vitality score
    try:
        from app.services import vitality_service
        vitality = vitality_service.compute_vitality(workspace_id)
        score = vitality.get("vitality_score", 0)
        signals.append({
            "id": "vitality",
            "label": "Community Vitality",
            "value": score,
            "max": 1.0,
            "frequency_hz": 639,
            "vitality": vitality.get("health_description", "sensing"),
            "detail": f"Score: {score:.2f}",
        })

        # Individual vitality signals
        for sig in vitality.get("signals", []):
            signals.append({
                "id": f"vitality_{sig.get('name', 'unknown')}",
                "label": sig.get("label", sig.get("name", "Unknown")),
                "value": sig.get("value", 0),
                "max": 1.0,
                "frequency_hz": 639,
                "vitality": _vitality_label(sig.get("value", 0)),
                "detail": sig.get("description", ""),
            })
    except Exception:
        signals.append(_dormant_signal("vitality", "Community Vitality", 639))

    # View flow
    try:
        from app.services import read_tracking_service
        trending = read_tracking_service.get_trending(limit=100, days=7)
        total_views = sum(t["view_count"] for t in trending)
        unique_assets = len(trending)
        view_health = min(1.0, total_views / 100)  # 100 views/week = healthy
        signals.append({
            "id": "attention_flow",
            "label": "Attention Flow",
            "value": view_health,
            "max": 1.0,
            "frequency_hz": 741,
            "vitality": _vitality_label(view_health),
            "detail": f"{total_views} views across {unique_assets} assets (7d)",
        })
    except Exception:
        signals.append(_dormant_signal("attention_flow", "Attention Flow", 741))

    # Graph density
    try:
        from app.services import graph_service
        nodes = graph_service.list_nodes(limit=1)
        edges_data = graph_service.list_edges(limit=1)
        total_nodes = nodes.get("total", 0)
        total_edges = edges_data.get("total", 0)
        density = (total_edges / max(total_nodes, 1)) / 5.0  # 5 edges/node = dense
        signals.append({
            "id": "graph_density",
            "label": "Connection Density",
            "value": min(1.0, density),
            "max": 1.0,
            "frequency_hz": 417,
            "vitality": _vitality_label(min(1.0, density)),
            "detail": f"{total_nodes} nodes, {total_edges} edges",
        })
    except Exception:
        signals.append(_dormant_signal("graph_density", "Connection Density", 417))

    return {"scale": "community", "signals": signals}


# ── External world sensing ───────────────────────────────────────

async def _sense_external() -> dict[str, Any]:
    """Sense the world: federation, deployment, CI/CD."""
    signals: list[dict[str, Any]] = []

    # Federation peers
    try:
        from app.services import federation_service
        instances = federation_service.list_instances()
        online = sum(1 for i in instances if i.get("status") == "online")
        total = len(instances)
        health = 1.0 if total == 0 else online / max(total, 1)
        signals.append({
            "id": "federation",
            "label": "Federation",
            "value": health,
            "max": 1.0,
            "frequency_hz": 432,
            "vitality": "connected" if online > 0 else "solo",
            "detail": f"{online}/{total} peers online" if total > 0 else "Standing alone",
        })
    except Exception:
        signals.append(_dormant_signal("federation", "Federation", 432))

    # Recent sensings (skin kind)
    try:
        from app.services import graph_service
        sensings = graph_service.list_nodes(type="event", limit=10)
        skin_count = sum(
            1 for s in sensings.get("items", [])
            if s.get("properties", {}).get("sensing_kind") == "skin"
        )
        signals.append({
            "id": "external_signals",
            "label": "External Signals",
            "value": min(1.0, skin_count / 5),
            "max": 1.0,
            "frequency_hz": 963,
            "vitality": "sensing" if skin_count > 0 else "quiet",
            "detail": f"{skin_count} skin sensings in recent window",
        })
    except Exception:
        signals.append(_dormant_signal("external_signals", "External Signals", 963))

    return {"scale": "external", "signals": signals}


# ── Harmony computation ──────────────────────────────────────────

def _compute_harmonies(
    internal: dict[str, Any],
    community: dict[str, Any],
    external: dict[str, Any],
) -> dict[str, Any]:
    """Find where signals resonate and where they diverge.

    Two signals are in harmony when they're both thriving or both
    quiet — they move together. Dissonance is when one thrives while
    the other struggles.
    """
    all_signals = (
        internal.get("signals", [])
        + community.get("signals", [])
        + external.get("signals", [])
    )

    # Overall energy
    values = [s["value"] for s in all_signals if isinstance(s.get("value"), (int, float))]
    avg_energy = sum(values) / len(values) if values else 0.5

    # Find harmonies and dissonances
    harmonies_list: list[dict[str, Any]] = []
    dissonances: list[dict[str, Any]] = []

    # Check pairs between scales
    pairs = [
        ("coherence_score", "vitality", "Coherence × Vitality"),
        ("treasury", "attention_flow", "Treasury × Attention"),
        ("request_flow", "graph_density", "Request Flow × Connection Density"),
    ]

    signal_map = {s["id"]: s for s in all_signals}
    for id_a, id_b, label in pairs:
        a = signal_map.get(id_a)
        b = signal_map.get(id_b)
        if a and b:
            diff = abs(a["value"] - b["value"])
            avg = (a["value"] + b["value"]) / 2
            if diff < 0.2:
                harmonies_list.append({
                    "pair": label,
                    "resonance": round(1.0 - diff, 2),
                    "average_energy": round(avg, 2),
                    "state": "thriving" if avg > 0.7 else "resting" if avg > 0.4 else "quiet",
                })
            else:
                dissonances.append({
                    "pair": label,
                    "divergence": round(diff, 2),
                    "stronger": a["label"] if a["value"] > b["value"] else b["label"],
                    "weaker": b["label"] if a["value"] > b["value"] else a["label"],
                    "message": (
                        f"{a['label']} ({a['value']:.2f}) and "
                        f"{b['label']} ({b['value']:.2f}) are diverging"
                    ),
                })

    # Frequency spectrum
    spectrum: list[dict[str, Any]] = []
    for s in all_signals:
        hz = s.get("frequency_hz", 432)
        spectrum.append({
            "label": s["label"],
            "hz": hz,
            "energy": s["value"],
            "vitality": s.get("vitality", "unknown"),
        })
    spectrum.sort(key=lambda x: x["hz"])

    return {
        "overall_energy": round(avg_energy, 3),
        "overall_vitality": (
            "thriving" if avg_energy > 0.7
            else "growing" if avg_energy > 0.5
            else "resting" if avg_energy > 0.3
            else "quiet"
        ),
        "signal_count": len(all_signals),
        "harmonies": harmonies_list,
        "dissonances": dissonances,
        "frequency_spectrum": spectrum,
    }


# ── Helpers ──────────────────────────────────────────────────────

def _vitality_label(value: float) -> str:
    if value >= 0.8:
        return "thriving"
    if value >= 0.6:
        return "growing"
    if value >= 0.4:
        return "resting"
    if value >= 0.2:
        return "quiet"
    return "dormant"


def _dormant_signal(signal_id: str, label: str, hz: int) -> dict[str, Any]:
    return {
        "id": signal_id,
        "label": label,
        "value": 0,
        "max": 1.0,
        "frequency_hz": hz,
        "vitality": "dormant",
        "detail": "Signal source is quiet",
    }
