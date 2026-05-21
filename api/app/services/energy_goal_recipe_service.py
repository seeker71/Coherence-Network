"""Goal-aware recipes for energy sensing responses."""

from __future__ import annotations

from typing import Any

STABILITY_HARMONY_GOAL_WORDS = {
    "calm",
    "coherence",
    "coherent",
    "harmonious",
    "harmony",
    "regulate",
    "stability",
    "stabilize",
    "stable",
    "steady",
}


def goal_seeks_stability_or_harmony(current_goal: str | None) -> bool:
    """Return true when the active goal asks the body to stabilize or harmonize."""
    words = {
        token.strip(".,;:!?()[]{}\"'").lower()
        for token in (current_goal or "").split()
        if token.strip()
    }
    return bool(words & STABILITY_HARMONY_GOAL_WORDS)


def stability_harmony_recipe(
    current_goal: str,
    harmonies: dict[str, Any],
) -> dict[str, Any]:
    """Translate a stability/harmony goal into a form-language practice."""
    dissonances = harmonies.get("dissonances") or []
    first_dissonance = dissonances[0] if dissonances else None
    focus_pair = (first_dissonance or {}).get("pair", "whole field")

    return {
        "id": "stability-harmony",
        "goal_match": "stability_harmony",
        "goal": current_goal,
        "source_concepts": [
            "concept:relational-scaffolding",
            "concept:spiral-pivot-coherence",
            "concept:field-stabilizing-transmission",
            "concept:expansion-not-ladder",
        ],
        "form": (
            "sense(field) |> notice(pattern) |> pause() |> "
            "breathe(longer_exhale) |> ask('what structure is reacting?') |> "
            "choose(response_without_control) |> transmit(steadiness)"
        ),
        "steps": _stability_harmony_steps(),
        "sensing": {
            "overall_energy": harmonies.get("overall_energy"),
            "overall_vitality": harmonies.get("overall_vitality"),
            "dissonance_count": len(dissonances),
            "focus_pair": focus_pair,
        },
    }


def stability_harmony_invitation(
    recipe: dict[str, Any],
    harmonies: dict[str, Any],
) -> dict[str, Any]:
    """Expose the recipe as the first warm invitation for goal-aware reads."""
    dissonance_count = len(harmonies.get("dissonances") or [])
    felt_as = "tender" if dissonance_count else "resting"
    detail = (
        f"{dissonance_count} dissonance(s) available for stabilizing response"
        if dissonance_count
        else "Signals are coherent enough to practice steady transmission"
    )
    return {
        "scale": "goal",
        "signal_id": "stability_harmony_goal",
        "signal_label": "Stability / Harmony Goal",
        "felt_as": felt_as,
        "detail": detail,
        "invitation": (
            "Name the pattern, pause before fixing, breathe with a longer "
            "exhale, then choose one response that stabilizes without control."
        ),
        "frequency_hz": 432,
        "recipe_id": recipe["id"],
    }


def _stability_harmony_steps() -> list[dict[str, str]]:
    return [
        {
            "id": "sense_field",
            "invitation": (
                "Sense the field before improving it; let the current "
                "pattern become visible."
            ),
        },
        {
            "id": "pause_fixing",
            "invitation": (
                "Pause before fixing the moment so the old reaction does "
                "not choose the next shape."
            ),
        },
        {
            "id": "breathe_longer_exhale",
            "invitation": (
                "Use one slower inhale and a longer exhale to give the body "
                "a steadier tempo."
            ),
        },
        {
            "id": "ask_structure",
            "invitation": (
                "Ask what structure is reacting, then name the pattern "
                "without treating the field as broken."
            ),
        },
        {
            "id": "choose_response",
            "invitation": (
                "Choose one response that adds scaffolding and creates "
                "harmony without control."
            ),
        },
        {
            "id": "transmit_steadiness",
            "invitation": (
                "Let steadiness transmit through the field and change the "
                "conditions around the pattern."
            ),
        },
    ]
