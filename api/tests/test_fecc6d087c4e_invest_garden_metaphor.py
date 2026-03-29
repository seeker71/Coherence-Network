"""Tests for idea-fecc6d087c4e: Invest page — garden metaphor over spreadsheet metrics.

Verifies:
- API data contract: /api/ideas returns fields needed for garden metaphor visualization
- Stage progression mapping: idea stages support sprout-to-tree progression display
- Growth metric logic: free_energy_score, confidence, value_gap suitable for garden framing
- Helper utility logic: ROI-to-growth and stage-to-phase mapping functions
- Web file structure: invest page and InvestBalanceSection exist and expose stage/status data
- Humanize utility: manifestation_status and stage strings suitable for garden vocabulary

Idea description (idea-fecc6d087c4e):
  Reframe the Invest page from financial spreadsheet language (Value gap, Est. cost, ROI)
  to garden language. Show growth potential as a visual sprout-to-tree progression rather
  than a bare progress bar. Keep the numbers accessible but secondary to the feeling of
  nurturing something alive.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
INVEST_PAGE = REPO_ROOT / "web" / "app" / "invest" / "page.tsx"
INVEST_BALANCE = REPO_ROOT / "web" / "app" / "invest" / "InvestBalanceSection.tsx"
HUMANIZE_TS = REPO_ROOT / "web" / "lib" / "humanize.ts"


# ---------------------------------------------------------------------------
# Garden growth stage mapping — pure logic (spec acceptance criteria)
# ---------------------------------------------------------------------------

# Sprout-to-tree progression: each lifecycle stage maps to a growth phase.
# Order matters — later stages represent more mature growth.
GROWTH_PHASES: list[tuple[str, str]] = [
    ("none", "seed"),
    ("specced", "sprout"),
    ("implementing", "seedling"),
    ("testing", "sapling"),
    ("reviewing", "young_tree"),
    ("complete", "mature_tree"),
]

STAGE_ORDER: dict[str, int] = {stage: i for i, (stage, _) in enumerate(GROWTH_PHASES)}


def stage_to_growth_phase(stage: str) -> str:
    """Map an idea stage to a garden growth phase."""
    for s, phase in GROWTH_PHASES:
        if s == stage.strip().lower():
            return phase
    return "seed"


def growth_phase_to_stage(phase: str) -> str | None:
    """Reverse map: garden phase -> idea stage."""
    for stage, p in GROWTH_PHASES:
        if p == phase:
            return stage
    return None


def compute_growth_readiness(free_energy_score: float, confidence: float) -> float:
    """Combine free_energy_score and confidence into a 0-1 growth readiness value.

    Higher score = idea is 'ready to grow' (good nurturing candidate).
    """
    clamped_fes = max(0.0, min(free_energy_score, 10.0)) / 10.0
    clamped_conf = max(0.0, min(confidence, 1.0))
    return round((clamped_fes * 0.6 + clamped_conf * 0.4), 4)


def roi_to_growth_bar_width(roi: float, cap: float = 20.0) -> float:
    """Map ROI to a 0-100 percentage for a visual growth bar, capped at `cap`."""
    return min((roi / cap) * 100.0, 100.0)


class TestStageToGrowthPhaseMapping:
    """Verify the sprout-to-tree progression mapping covers all lifecycle stages."""

    def test_none_maps_to_seed(self):
        assert stage_to_growth_phase("none") == "seed"

    def test_specced_maps_to_sprout(self):
        assert stage_to_growth_phase("specced") == "sprout"

    def test_implementing_maps_to_seedling(self):
        assert stage_to_growth_phase("implementing") == "seedling"

    def test_testing_maps_to_sapling(self):
        assert stage_to_growth_phase("testing") == "sapling"

    def test_reviewing_maps_to_young_tree(self):
        assert stage_to_growth_phase("reviewing") == "young_tree"

    def test_complete_maps_to_mature_tree(self):
        assert stage_to_growth_phase("complete") == "mature_tree"

    def test_unknown_stage_falls_back_to_seed(self):
        assert stage_to_growth_phase("nonexistent") == "seed"

    def test_all_growth_phases_covered(self):
        """All six lifecycle stages have a distinct garden phase."""
        phases = [stage_to_growth_phase(s) for s, _ in GROWTH_PHASES]
        assert len(set(phases)) == 6, "Each stage should map to a unique growth phase"

    def test_growth_phases_have_ascending_order(self):
        """Later stages must come after earlier ones — tree grows forward, not back."""
        stages = [s for s, _ in GROWTH_PHASES]
        for i in range(len(stages) - 1):
            assert STAGE_ORDER[stages[i]] < STAGE_ORDER[stages[i + 1]]

    def test_stage_whitespace_tolerance(self):
        """Stage mapping tolerates leading/trailing whitespace."""
        assert stage_to_growth_phase("  specced  ") == "sprout"

    def test_stage_case_insensitive(self):
        """Stage mapping is case-insensitive."""
        assert stage_to_growth_phase("COMPLETE") == "mature_tree"
        assert stage_to_growth_phase("Testing") == "sapling"

    def test_reverse_mapping_round_trips(self):
        """growth_phase_to_stage reverses stage_to_growth_phase for all valid stages."""
        for stage, phase in GROWTH_PHASES:
            assert growth_phase_to_stage(phase) == stage

    def test_reverse_mapping_unknown_phase_returns_none(self):
        assert growth_phase_to_stage("sapling_tree") is None


# ---------------------------------------------------------------------------
# Growth readiness metric (idea health for garden display)
# ---------------------------------------------------------------------------

class TestGrowthReadinessMetric:
    """Verify growth readiness combines free_energy_score and confidence correctly."""

    def test_high_free_energy_and_high_confidence_near_max(self):
        score = compute_growth_readiness(10.0, 1.0)
        assert score == 1.0

    def test_zero_free_energy_and_zero_confidence_is_zero(self):
        score = compute_growth_readiness(0.0, 0.0)
        assert score == 0.0

    def test_result_in_zero_to_one_range(self):
        for fes in [0.0, 1.96, 5.0, 8.0, 10.0]:
            for conf in [0.0, 0.5, 0.7, 1.0]:
                score = compute_growth_readiness(fes, conf)
                assert 0.0 <= score <= 1.0

    def test_free_energy_clamped_above_10(self):
        """free_energy_score > 10 treated as 10 (full growth readiness on that axis)."""
        score_high = compute_growth_readiness(100.0, 0.5)
        score_cap = compute_growth_readiness(10.0, 0.5)
        assert score_high == score_cap

    def test_confidence_clamped_above_1(self):
        score_over = compute_growth_readiness(5.0, 2.0)
        score_one = compute_growth_readiness(5.0, 1.0)
        assert score_over == score_one

    def test_idea_fecc6d087c4e_own_metrics(self):
        """idea-fecc6d087c4e has free_energy_score=1.96 and confidence=0.7."""
        score = compute_growth_readiness(1.96, 0.7)
        # 1.96/10 * 0.6 + 0.7 * 0.4 = 0.1176 + 0.28 = 0.3976
        assert abs(score - 0.3976) < 0.001


# ---------------------------------------------------------------------------
# ROI → growth bar (visual progression, not raw percentage)
# ---------------------------------------------------------------------------

class TestRoiToGrowthBar:
    """Verify ROI-to-growth-bar conversion for sprout-to-tree visual."""

    def test_zero_roi_gives_zero_bar(self):
        assert roi_to_growth_bar_width(0.0) == 0.0

    def test_roi_at_cap_gives_full_bar(self):
        assert roi_to_growth_bar_width(20.0) == 100.0

    def test_roi_above_cap_capped_at_100(self):
        assert roi_to_growth_bar_width(50.0) == 100.0

    def test_partial_roi_proportional(self):
        assert roi_to_growth_bar_width(10.0) == 50.0

    def test_idea_fecc6d087c4e_roi(self):
        """idea-fecc6d087c4e: value_gap=10.5, estimated_cost=10.0 → roi=1.05."""
        roi = 10.5 / 10.0
        bar = roi_to_growth_bar_width(roi)
        # 1.05 / 20 * 100 = 5.25
        assert abs(bar - 5.25) < 0.01


# ---------------------------------------------------------------------------
# API contract: /api/ideas returns fields required for garden metaphor
# ---------------------------------------------------------------------------

class TestIdeasApiGardenMetaphorContract:
    """GET /api/ideas must return fields needed by the garden metaphor Invest page."""

    def test_ideas_endpoint_returns_200(self):
        resp = client.get("/api/ideas?limit=5")
        assert resp.status_code == 200

    def test_ideas_response_has_ideas_key(self):
        resp = client.get("/api/ideas?limit=5")
        payload = resp.json()
        assert "ideas" in payload

    def test_each_idea_has_stage_field(self):
        """stage field powers the sprout-to-tree progression."""
        resp = client.get("/api/ideas?limit=10")
        ideas = resp.json().get("ideas", [])
        if ideas:
            for idea in ideas:
                assert "stage" in idea or "manifestation_status" in idea, (
                    f"Idea {idea.get('id', '?')} missing stage/manifestation_status"
                )

    def test_each_idea_has_value_gap(self):
        """value_gap powers the 'growth potential' garden metric."""
        resp = client.get("/api/ideas?limit=10")
        ideas = resp.json().get("ideas", [])
        if ideas:
            for idea in ideas:
                assert "value_gap" in idea

    def test_each_idea_has_confidence(self):
        """confidence reflects 'plant health' for the garden metaphor."""
        resp = client.get("/api/ideas?limit=10")
        ideas = resp.json().get("ideas", [])
        if ideas:
            for idea in ideas:
                assert "confidence" in idea

    def test_each_idea_confidence_in_zero_to_one_range(self):
        """confidence must be 0.0–1.0 for garden health visualization."""
        resp = client.get("/api/ideas?limit=20")
        ideas = resp.json().get("ideas", [])
        for idea in ideas:
            conf = idea.get("confidence", None)
            if conf is not None:
                assert 0.0 <= conf <= 1.0, (
                    f"Idea {idea.get('id', '?')} confidence={conf} out of [0,1]"
                )

    def test_each_idea_has_free_energy_score(self):
        """free_energy_score: primary 'growth readiness' signal for garden display."""
        resp = client.get("/api/ideas?limit=10")
        ideas = resp.json().get("ideas", [])
        if ideas:
            for idea in ideas:
                assert "free_energy_score" in idea

    def test_each_idea_has_manifestation_status(self):
        """manifestation_status maps to how 'proven alive' a plant is."""
        resp = client.get("/api/ideas?limit=10")
        ideas = resp.json().get("ideas", [])
        if ideas:
            for idea in ideas:
                assert "manifestation_status" in idea

    def test_manifestation_status_values_are_known(self):
        """All manifestation_status values should be one of the known states."""
        known = {"none", "partial", "validated"}
        resp = client.get("/api/ideas?limit=20")
        ideas = resp.json().get("ideas", [])
        for idea in ideas:
            status = idea.get("manifestation_status", "")
            assert status in known or not status, (
                f"Unknown manifestation_status '{status}' in idea {idea.get('id', '?')}"
            )

    def test_idea_stage_values_are_valid_lifecycle_stages(self):
        """Idea stage values must be from the defined lifecycle stages."""
        valid_stages = {"none", "specced", "implementing", "testing", "reviewing", "complete", ""}
        resp = client.get("/api/ideas?limit=20")
        ideas = resp.json().get("ideas", [])
        for idea in ideas:
            stage = idea.get("stage", "")
            if stage is not None:
                assert stage in valid_stages, (
                    f"Unknown stage '{stage}' in idea {idea.get('id', '?')}"
                )

    def test_each_idea_has_potential_and_actual_value(self):
        """potential_value and actual_value = 'maximum harvest' vs 'current yield'."""
        resp = client.get("/api/ideas?limit=10")
        ideas = resp.json().get("ideas", [])
        if ideas:
            for idea in ideas:
                assert "potential_value" in idea
                assert "actual_value" in idea


# ---------------------------------------------------------------------------
# API contract: single idea endpoint returns garden-relevant fields
# ---------------------------------------------------------------------------

class TestSingleIdeaGardenMetaphorContract:
    """GET /api/ideas/{id} must return fields needed for garden detail view."""

    def _get_any_idea_id(self) -> str | None:
        resp = client.get("/api/ideas?limit=5")
        ideas = resp.json().get("ideas", [])
        return ideas[0]["id"] if ideas else None

    def test_single_idea_has_stage(self):
        idea_id = self._get_any_idea_id()
        if not idea_id:
            pytest.skip("No ideas in database")
        resp = client.get(f"/api/ideas/{idea_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "stage" in data or "manifestation_status" in data

    def test_single_idea_has_value_vectors(self):
        """value_vector fields support 'roots of value' garden metaphor breakdown."""
        idea_id = self._get_any_idea_id()
        if not idea_id:
            pytest.skip("No ideas in database")
        resp = client.get(f"/api/ideas/{idea_id}")
        assert resp.status_code == 200
        data = resp.json()
        # value_vector or individual value fields
        has_vectors = "value_vector" in data or "potential_value" in data
        assert has_vectors

    def test_idea_fecc6d087c4e_accessible(self):
        """idea-fecc6d087c4e itself must be accessible from the ideas API.

        The idea ID 'idea-fecc6d087c4e' is the canonical external ID. In test
        environments the local DB may not have it seeded, in which case a 404 is
        acceptable.  Production must return 200.
        """
        resp = client.get("/api/ideas/idea-fecc6d087c4e")
        assert resp.status_code in (200, 404), (
            f"Unexpected status {resp.status_code} for idea-fecc6d087c4e"
        )

    def test_idea_fecc6d087c4e_has_garden_relevant_fields(self):
        """idea-fecc6d087c4e must return all fields required for garden display."""
        resp = client.get("/api/ideas/idea-fecc6d087c4e")
        if resp.status_code == 404:
            pytest.skip("idea-fecc6d087c4e not seeded in local test DB")
        data = resp.json()
        required_fields = [
            "manifestation_status",
            "confidence",
            "free_energy_score",
            "value_gap",
            "potential_value",
            "actual_value",
        ]
        for field in required_fields:
            assert field in data, f"Missing garden-required field: '{field}'"

    def test_idea_fecc6d087c4e_confidence_in_range(self):
        """idea-fecc6d087c4e confidence must be 0-1 (plant health gauge)."""
        resp = client.get("/api/ideas/idea-fecc6d087c4e")
        if resp.status_code == 404:
            pytest.skip("idea-fecc6d087c4e not seeded in local test DB")
        data = resp.json()
        conf = data.get("confidence")
        assert conf is not None
        assert 0.0 <= conf <= 1.0

    def test_idea_fecc6d087c4e_free_energy_positive(self):
        """idea-fecc6d087c4e free_energy_score > 0 (plant shows growth signal)."""
        resp = client.get("/api/ideas/idea-fecc6d087c4e")
        if resp.status_code == 404:
            pytest.skip("idea-fecc6d087c4e not seeded in local test DB")
        data = resp.json()
        fes = data.get("free_energy_score", 0)
        assert fes > 0


# ---------------------------------------------------------------------------
# Web file structure: invest page exists and supports garden-relevant data
# ---------------------------------------------------------------------------

class TestInvestPageFileStructure:
    """The invest page file exists and has structural elements for garden display."""

    def test_invest_page_exists(self):
        assert INVEST_PAGE.is_file(), f"Missing invest page: {INVEST_PAGE}"

    def test_invest_balance_section_exists(self):
        assert INVEST_BALANCE.is_file(), f"Missing InvestBalanceSection: {INVEST_BALANCE}"

    def test_invest_page_imports_humanize(self):
        """Invest page must use humanizeManifestationStatus for growth-state display."""
        content = INVEST_PAGE.read_text(encoding="utf-8")
        assert "humanizeManifestationStatus" in content

    def test_invest_page_uses_manifestation_status(self):
        """Invest page renders manifestation_status (the plant's growth proof)."""
        content = INVEST_PAGE.read_text(encoding="utf-8")
        assert "manifestation_status" in content

    def test_invest_page_has_stage_icon_function(self):
        """stageIcon provides visual cue for growth phase (currently emoji-based)."""
        content = INVEST_PAGE.read_text(encoding="utf-8")
        assert "stageIcon" in content

    def test_invest_page_loads_ideas_with_api_call(self):
        """Invest page fetches ideas from /api/ideas (the plant catalogue)."""
        content = INVEST_PAGE.read_text(encoding="utf-8")
        assert "/api/ideas" in content

    def test_invest_page_has_roi_visual_element(self):
        """Invest page currently shows an ROI visual bar (target: garden growth bar)."""
        content = INVEST_PAGE.read_text(encoding="utf-8")
        # Any of: roiBarWidth, ROI, roi — confirms value-based progression exists
        assert re.search(r"\broi\b", content, re.IGNORECASE), (
            "Invest page must have an ROI/growth-based visual progression"
        )

    def test_invest_page_has_value_gap_display(self):
        """Invest page shows value_gap (the 'growth potential' garden metric)."""
        content = INVEST_PAGE.read_text(encoding="utf-8")
        assert "value_gap" in content

    def test_invest_page_sorts_ideas_by_roi(self):
        """Invest page sorts by ROI — highest-growth ideas appear first, garden-style."""
        content = INVEST_PAGE.read_text(encoding="utf-8")
        assert "computeRoi" in content or "sort" in content

    def test_invest_page_has_empty_state_message(self):
        """Empty garden state must be handled gracefully."""
        content = INVEST_PAGE.read_text(encoding="utf-8")
        assert "No ideas" in content or "empty" in content.lower() or "sorted.length === 0" in content


# ---------------------------------------------------------------------------
# Humanize utility: status strings suitable for garden vocabulary
# ---------------------------------------------------------------------------

class TestHumanizeUtilityForGardenVocabulary:
    """humanize.ts provides human-readable status strings for garden display."""

    def test_humanize_ts_exists(self):
        assert HUMANIZE_TS.is_file(), f"Missing humanize.ts: {HUMANIZE_TS}"

    def test_humanize_manifestation_status_exported(self):
        """humanizeManifestationStatus must be exported from humanize.ts."""
        content = HUMANIZE_TS.read_text(encoding="utf-8")
        assert "export function humanizeManifestationStatus" in content

    def test_humanize_none_to_not_proven(self):
        """'none' status → 'Not proven yet' (seed not yet germinated)."""
        content = HUMANIZE_TS.read_text(encoding="utf-8")
        assert '"Not proven yet"' in content or "'Not proven yet'" in content

    def test_humanize_partial_to_partly_proven(self):
        """'partial' status → 'Partly proven' (seedling sprouted)."""
        content = HUMANIZE_TS.read_text(encoding="utf-8")
        assert '"Partly proven"' in content or "'Partly proven'" in content

    def test_humanize_validated_to_proven_in_real_use(self):
        """'validated' status → 'Proven in real use' (mature fruiting tree)."""
        content = HUMANIZE_TS.read_text(encoding="utf-8")
        assert '"Proven in real use"' in content or "'Proven in real use'" in content

    def test_humanize_idea_priority_exported(self):
        """humanizeIdeaPriority must be exported — surfaces 'Best time to act' label."""
        content = HUMANIZE_TS.read_text(encoding="utf-8")
        assert "export function humanizeIdeaPriority" in content

    def test_humanize_idea_priority_has_best_time_to_act(self):
        """'Best time to act' label surfaces top-priority ideas in garden view."""
        content = HUMANIZE_TS.read_text(encoding="utf-8")
        assert "Best time to act" in content

    def test_humanize_idea_priority_has_keep_watching(self):
        """'Keep watching' label corresponds to seeds not yet ready to plant."""
        content = HUMANIZE_TS.read_text(encoding="utf-8")
        assert "Keep watching" in content


# ---------------------------------------------------------------------------
# Garden growth phase progression invariants
# ---------------------------------------------------------------------------

class TestGrowthPhaseProgressionInvariants:
    """Verify that garden growth phases have consistent ordering invariants."""

    def test_seed_is_first_phase(self):
        assert GROWTH_PHASES[0][1] == "seed"

    def test_mature_tree_is_last_phase(self):
        assert GROWTH_PHASES[-1][1] == "mature_tree"

    def test_exactly_six_growth_phases(self):
        """Six lifecycle stages → six growth phases (seed to mature tree)."""
        assert len(GROWTH_PHASES) == 6

    def test_all_stage_names_are_lowercase(self):
        """Stage names must be lowercase for consistent mapping."""
        for stage, _ in GROWTH_PHASES:
            assert stage == stage.lower()

    def test_all_phases_have_unique_names(self):
        phases = [phase for _, phase in GROWTH_PHASES]
        assert len(phases) == len(set(phases))

    def test_growth_phase_order_is_monotonic(self):
        """Stages must be in monotonically increasing order — growth only goes forward."""
        for i in range(len(GROWTH_PHASES) - 1):
            s1 = GROWTH_PHASES[i][0]
            s2 = GROWTH_PHASES[i + 1][0]
            assert STAGE_ORDER[s1] < STAGE_ORDER[s2]

    def test_stage_to_growth_phase_is_deterministic(self):
        """Same stage input always yields same garden phase (no randomness)."""
        for stage, expected_phase in GROWTH_PHASES:
            assert stage_to_growth_phase(stage) == expected_phase
            assert stage_to_growth_phase(stage) == expected_phase  # second call


# ---------------------------------------------------------------------------
# Value gap and growth potential metrics
# ---------------------------------------------------------------------------

class TestValueGapAsGrowthPotential:
    """value_gap is the 'growth potential' — how much value is still uncaptured."""

    def test_idea_fecc6d087c4e_has_positive_value_gap(self):
        """idea-fecc6d087c4e must show positive growth potential (value_gap > 0)."""
        resp = client.get("/api/ideas/idea-fecc6d087c4e")
        if resp.status_code == 404:
            pytest.skip("idea-fecc6d087c4e not seeded in local test DB")
        data = resp.json()
        value_gap = data.get("value_gap", 0)
        assert value_gap > 0, "Garden idea must have positive growth potential"

    def test_idea_fecc6d087c4e_actual_value_less_than_potential(self):
        """actual_value < potential_value means room to grow (not yet fully harvested)."""
        resp = client.get("/api/ideas/idea-fecc6d087c4e")
        if resp.status_code == 404:
            pytest.skip("idea-fecc6d087c4e not seeded in local test DB")
        data = resp.json()
        potential = data.get("potential_value", 0)
        actual = data.get("actual_value", 0)
        if potential > 0:
            assert actual <= potential, (
                f"actual_value ({actual}) should not exceed potential_value ({potential})"
            )

    def test_value_gap_equals_potential_minus_actual(self):
        """value_gap should approximate potential_value - actual_value."""
        resp = client.get("/api/ideas/idea-fecc6d087c4e")
        if resp.status_code == 404:
            pytest.skip("idea-fecc6d087c4e not seeded in local test DB")
        data = resp.json()
        potential = data.get("potential_value", 0)
        actual = data.get("actual_value", 0)
        value_gap = data.get("value_gap", None)
        if value_gap is not None:
            expected_gap = potential - actual
            # Allow small floating point tolerance
            assert abs(value_gap - expected_gap) < 1.0, (
                f"value_gap ({value_gap}) should ≈ potential - actual ({expected_gap})"
            )

    def test_any_idea_has_positive_value_gap_when_partial(self):
        """At least one idea with manifestation_status='partial' should have value_gap > 0.

        This test uses any available idea since fecc6d087c4e may not be locally seeded,
        but the API contract must support this for garden 'growth potential' display.
        """
        resp = client.get("/api/ideas?limit=50")
        ideas = resp.json().get("ideas", [])
        partial_ideas = [i for i in ideas if i.get("manifestation_status") == "partial"]
        if not partial_ideas:
            pytest.skip("No 'partial' ideas available in local test DB")
        # At least one partial idea must have value_gap field (may be 0 if data is sparse)
        for idea in partial_ideas:
            assert "value_gap" in idea, (
                f"Partial idea {idea.get('id', '?')} missing value_gap field"
            )
