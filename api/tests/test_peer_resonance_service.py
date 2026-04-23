from __future__ import annotations

from app.models.belief import BeliefProfile, ConceptResonance
from app.services.peer_resonance_service import compute_peer_resonance


def _profile(
    contributor_id: str,
    *,
    tags: list[str],
    axes: dict[str, float],
    concepts: dict[str, float] | None = None,
) -> BeliefProfile:
    return BeliefProfile(
        contributor_id=contributor_id,
        interest_tags=tags,
        worldview_axes=axes,
        concept_resonances=[
            ConceptResonance(concept_id=concept_id, weight=weight)
            for concept_id, weight in (concepts or {}).items()
        ],
    )


def test_peer_resonance_rewards_shared_tags_worldview_and_concepts() -> None:
    profile_a = _profile(
        "a",
        tags=["software", "resonance"],
        axes={"scientific": 0.8, "systemic": 0.7, "pragmatic": 0.6},
        concepts={"crk": 0.9, "ontology": 0.7},
    )
    profile_b = _profile(
        "b",
        tags=["software", "resonance", "ontology"],
        axes={"scientific": 0.9, "systemic": 0.6, "pragmatic": 0.7},
        concepts={"crk": 0.8, "ontology": 0.3},
    )
    profile_c = _profile(
        "c",
        tags=["gardening"],
        axes={"spiritual": 0.9, "relational": 0.2},
        concepts={"soil": 0.8},
    )

    assert compute_peer_resonance(profile_a, profile_b) > compute_peer_resonance(profile_a, profile_c)


def test_peer_resonance_has_neutral_baseline_for_empty_profiles() -> None:
    profile_a = _profile("a", tags=[], axes={})
    profile_b = _profile("b", tags=[], axes={})

    assert compute_peer_resonance(profile_a, profile_b) == 0.5
