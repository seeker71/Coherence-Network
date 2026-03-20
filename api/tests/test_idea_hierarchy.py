"""Tests for idea hierarchy: super-ideas and child-ideas (spec 117).

All tests use real Pydantic models — no mocks, no placeholders.
"""

from __future__ import annotations

import pytest

from app.models.idea import Idea, IdeaType, IdeaWithScore, ManifestationStatus


# ===========================================================================
# TestIdeaTypeModel
# ===========================================================================

class TestIdeaTypeModel:
    """Test the IdeaType enum and Idea model fields."""

    def test_default_type_is_standalone(self):
        """Backward compat: ideas without idea_type default to standalone."""
        idea = Idea(
            id="test", name="Test", description="desc",
            potential_value=10.0, estimated_cost=5.0,
        )
        assert idea.idea_type == IdeaType.STANDALONE

    def test_super_idea_creation(self):
        idea = Idea(
            id="parent", name="Parent", description="strategic goal",
            potential_value=100.0, estimated_cost=50.0,
            idea_type=IdeaType.SUPER,
            child_idea_ids=["child-a", "child-b"],
        )
        assert idea.idea_type == IdeaType.SUPER
        assert idea.child_idea_ids == ["child-a", "child-b"]
        assert idea.parent_idea_id is None

    def test_child_idea_creation(self):
        idea = Idea(
            id="child-a", name="Child A", description="actionable work",
            potential_value=30.0, estimated_cost=10.0,
            idea_type=IdeaType.CHILD,
            parent_idea_id="parent",
        )
        assert idea.idea_type == IdeaType.CHILD
        assert idea.parent_idea_id == "parent"
        assert idea.child_idea_ids == []

    def test_standalone_has_no_parent(self):
        idea = Idea(
            id="lone", name="Lone", description="standalone",
            potential_value=50.0, estimated_cost=20.0,
        )
        assert idea.idea_type == IdeaType.STANDALONE
        assert idea.parent_idea_id is None
        assert idea.child_idea_ids == []

    def test_idea_type_from_string(self):
        """JSON deserialization uses string values."""
        idea = Idea(
            id="x", name="X", description="d",
            potential_value=1.0, estimated_cost=1.0,
            idea_type="super",
        )
        assert idea.idea_type == IdeaType.SUPER

    def test_idea_type_enum_values(self):
        assert IdeaType.SUPER.value == "super"
        assert IdeaType.CHILD.value == "child"
        assert IdeaType.STANDALONE.value == "standalone"


# ===========================================================================
# TestIdeaWithScoreHierarchy
# ===========================================================================

class TestIdeaWithScoreHierarchy:
    """Test that IdeaWithScore inherits hierarchy fields."""

    def test_super_idea_with_score(self):
        idea = IdeaWithScore(
            id="parent", name="Parent", description="strategic",
            potential_value=100.0, estimated_cost=50.0,
            idea_type=IdeaType.SUPER,
            child_idea_ids=["c1", "c2"],
            free_energy_score=5.0, value_gap=80.0,
        )
        assert idea.idea_type == IdeaType.SUPER
        assert idea.child_idea_ids == ["c1", "c2"]

    def test_child_idea_with_score(self):
        idea = IdeaWithScore(
            id="c1", name="Child 1", description="actionable",
            potential_value=30.0, estimated_cost=10.0,
            idea_type=IdeaType.CHILD,
            parent_idea_id="parent",
            free_energy_score=3.0, value_gap=25.0,
        )
        assert idea.parent_idea_id == "parent"


# ===========================================================================
# TestBackwardCompat
# ===========================================================================

class TestBackwardCompat:
    """Test that existing ideas without hierarchy fields still work."""

    def test_idea_from_dict_without_type(self):
        """Existing JSON without idea_type/parent_idea_id deserializes cleanly."""
        data = {
            "id": "legacy-idea",
            "name": "Legacy",
            "description": "Before hierarchy was added",
            "potential_value": 50.0,
            "estimated_cost": 10.0,
        }
        idea = Idea(**data)
        assert idea.idea_type == IdeaType.STANDALONE
        assert idea.parent_idea_id is None
        assert idea.child_idea_ids == []

    def test_model_dump_includes_hierarchy_fields(self):
        """JSON export includes the new fields."""
        idea = Idea(
            id="test", name="Test", description="d",
            potential_value=10.0, estimated_cost=5.0,
            idea_type=IdeaType.CHILD,
            parent_idea_id="parent",
        )
        data = idea.model_dump()
        assert data["idea_type"] == IdeaType.CHILD
        assert data["parent_idea_id"] == "parent"
        assert data["child_idea_ids"] == []

    def test_model_dump_json_mode(self):
        """JSON mode serializes enum as string."""
        idea = Idea(
            id="test", name="Test", description="d",
            potential_value=10.0, estimated_cost=5.0,
            idea_type=IdeaType.SUPER,
        )
        data = idea.model_dump(mode="json")
        assert data["idea_type"] == "super"


# ===========================================================================
# TestSuperIdeaExclusion
# ===========================================================================

class TestSuperIdeaExclusion:
    """Test that super-ideas are excluded from task pickup filtering."""

    def test_filter_excludes_super_ideas(self):
        """Simulate the filter logic from next_highest_roi_task."""
        answered = [
            {"idea_id": "parent", "idea_type": "super", "answer_roi": 10.0, "question_roi": 5.0},
            {"idea_id": "child-a", "idea_type": "child", "answer_roi": 8.0, "question_roi": 4.0},
            {"idea_id": "standalone", "idea_type": "standalone", "answer_roi": 6.0, "question_roi": 3.0},
        ]
        actionable = [
            row for row in answered
            if isinstance(row, dict) and str(row.get("idea_type", "standalone")) != "super"
        ]
        assert len(actionable) == 2
        assert actionable[0]["idea_id"] == "child-a"
        assert actionable[1]["idea_id"] == "standalone"

    def test_filter_includes_standalone_by_default(self):
        """Ideas without idea_type (legacy) default to standalone and are included."""
        answered = [
            {"idea_id": "legacy", "answer_roi": 5.0},
        ]
        actionable = [
            row for row in answered
            if isinstance(row, dict) and str(row.get("idea_type", "standalone")) != "super"
        ]
        assert len(actionable) == 1

    def test_all_super_returns_empty(self):
        """When all answered questions are from super-ideas, nothing is actionable."""
        answered = [
            {"idea_id": "p1", "idea_type": "super", "answer_roi": 10.0},
            {"idea_id": "p2", "idea_type": "super", "answer_roi": 8.0},
        ]
        actionable = [
            row for row in answered
            if isinstance(row, dict) and str(row.get("idea_type", "standalone")) != "super"
        ]
        assert len(actionable) == 0


# ===========================================================================
# TestDefaultIdeasHierarchy
# ===========================================================================

class TestSeedIdeasHierarchy:
    """Verify inline SEED_IDEAS has correct hierarchy (single source of truth)."""

    @pytest.fixture(autouse=True)
    def _load_seed(self):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "scripts"))
        from seed_db import SEED_IDEAS
        self.seed_ideas = SEED_IDEAS
        self._by_id = {s["id"]: s for s in SEED_IDEAS}

    def test_portfolio_governance_is_super(self):
        pg = self._by_id["portfolio-governance"]
        assert pg["idea_type"] == "super"
        assert "coherence-signal-depth" in pg["child_idea_ids"]

    def test_coherence_signal_depth_is_child(self):
        csd = self._by_id["coherence-signal-depth"]
        assert csd["idea_type"] == "child"
        assert csd["parent_idea_id"] == "portfolio-governance"

    def test_oss_interface_alignment_is_super(self):
        oss = self._by_id["oss-interface-alignment"]
        assert oss["idea_type"] == "super"
        assert "interface-trust-surface" in oss["child_idea_ids"]
        assert "minimum-e2e-path" in oss["child_idea_ids"]

    def test_federated_is_standalone(self):
        """Federation idea has no children yet -- stays standalone."""
        fed = self._by_id["federated-instance-aggregation"]
        assert fed.get("idea_type", "standalone") == "standalone"

    def test_derived_agent_pipeline_is_super(self):
        pipeline = self._by_id["coherence-network-agent-pipeline"]
        assert pipeline["idea_type"] == "super"
        assert "agent-prompt-ab-roi" in pipeline["child_idea_ids"]

    def test_derived_child_ideas_have_parents(self):
        for child_id in ["interface-trust-surface", "minimum-e2e-path", "funder-proof-page", "idea-hierarchy-model"]:
            meta = self._by_id[child_id]
            assert meta["idea_type"] == "child", f"{child_id} should be child"
            assert meta.get("parent_idea_id"), f"{child_id} should have parent_idea_id"


# ===========================================================================
# TestServiceAPIContracts
# ===========================================================================

class TestServiceAPIContracts:
    """Verify model contracts."""

    def test_idea_type_in_idea_model(self):
        assert "idea_type" in Idea.model_fields

    def test_parent_idea_id_in_idea_model(self):
        assert "parent_idea_id" in Idea.model_fields

    def test_child_idea_ids_in_idea_model(self):
        assert "child_idea_ids" in Idea.model_fields

    def test_idea_type_enum_has_three_values(self):
        assert len(IdeaType) == 3
