"""Acceptance tests for idea-fecc6d087c4e — Invest garden metaphor (TS/Python parity).

Idea: Reframe Invest from spreadsheet metrics toward growth-oriented visuals; ROI bar and
compute paths must stay consistent between `web/app/invest/page.tsx` and measurable rules.

This module adds parity checks that complement `test_fecc6d087c4e_invest_garden_metaphor.py`
without modifying that file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INVEST_PAGE = REPO_ROOT / "web" / "app" / "invest" / "page.tsx"


def _mirror_ts_compute_roi(value_gap: float, estimated_cost: float) -> float:
    """Mirror `computeRoi` in page.tsx: cost = estimated_cost > 0 ? estimated_cost : 1."""
    cost = estimated_cost if estimated_cost > 0 else 1.0
    return value_gap / cost


def _mirror_ts_roi_bar_width(roi: float) -> float:
    """Mirror `roiBarWidth`: min((roi / 20) * 100, 100)."""
    return min((roi / 20.0) * 100.0, 100.0)


class TestFecc6d087c4eRoiComputeParity:
    """ROI = value_gap / effective_cost — powers growth-bar width input."""

    @pytest.mark.parametrize(
        ("value_gap", "estimated_cost", "expected"),
        [
            (10.5, 10.0, 1.05),
            (0.0, 5.0, 0.0),
            (20.0, 0.0, 20.0),  # cost coerces to 1
            (3.0, -1.0, 3.0),  # non-positive cost → 1
        ],
    )
    def test_compute_roi_matches_ts_contract(
        self, value_gap: float, estimated_cost: float, expected: float
    ) -> None:
        assert abs(_mirror_ts_compute_roi(value_gap, estimated_cost) - expected) < 1e-9


class TestFecc6d087c4eRoiBarWidthParity:
    """Visual growth bar: same cap-20 formula as TS `roiBarWidth`."""

    @pytest.mark.parametrize(
        ("roi", "expected_width"),
        [
            (0.0, 0.0),
            (1.05, 5.25),
            (10.0, 50.0),
            (20.0, 100.0),
            (50.0, 100.0),
        ],
    )
    def test_roi_bar_width_matches_ts_contract(
        self, roi: float, expected_width: float
    ) -> None:
        got = _mirror_ts_roi_bar_width(roi)
        assert abs(got - expected_width) < 1e-9


class TestFecc6d087c4eInvestPageSourceFormulas:
    """Source must retain the acceptance formulas (regression guard for garden visual)."""

    @pytest.fixture
    def page_src(self) -> str:
        assert INVEST_PAGE.is_file(), f"Missing {INVEST_PAGE}"
        return INVEST_PAGE.read_text(encoding="utf-8")

    def test_page_defines_compute_roi_with_value_gap_over_cost(self, page_src: str) -> None:
        assert "function computeRoi" in page_src
        assert "return idea.value_gap / cost;" in page_src

    def test_page_uses_estimated_cost_guard(self, page_src: str) -> None:
        assert "idea.estimated_cost > 0 ? idea.estimated_cost : 1" in page_src

    def test_page_defines_roi_bar_width_cap_20(self, page_src: str) -> None:
        assert "function roiBarWidth" in page_src
        assert "return Math.min((roi / 20) * 100, 100);" in page_src

    def test_page_applies_roi_bar_to_style_width(self, page_src: str) -> None:
        assert "roiBarWidth(roi)" in page_src
        assert "width:" in page_src and "roiBarWidth(roi)}%" in page_src

    def test_page_fetches_ideas_endpoint(self, page_src: str) -> None:
        assert "/api/ideas" in page_src

    def test_page_sorts_by_roi_descending(self, page_src: str) -> None:
        assert "computeRoi(b) - computeRoi(a)" in page_src


class TestFecc6d087c4eGrowthOrderingInvariant:
    """Higher ROI must sort before lower — 'tallest growth' first for invest list."""

    def test_sort_key_matches_roi_desc(self) -> None:
        ideas = [
            {"id": "a", "value_gap": 5.0, "estimated_cost": 10.0},
            {"id": "b", "value_gap": 30.0, "estimated_cost": 10.0},
            {"id": "c", "value_gap": 10.0, "estimated_cost": 10.0},
        ]

        def roi(i: dict) -> float:
            return _mirror_ts_compute_roi(i["value_gap"], i["estimated_cost"])

        sorted_ids = [x["id"] for x in sorted(ideas, key=lambda x: roi(x), reverse=True)]
        assert sorted_ids[0] == "b" and sorted_ids[-1] == "a"
