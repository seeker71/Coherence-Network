"""Tests for spec 186: My Portfolio — Garden vs Ledger.

Verifies:
- Portfolio page file exists and contains garden-language labels
- Garden health mapping functions work correctly
- No ledger labels appear as primary visible text
- Accessibility attributes present
- Empty state messages use garden language
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO_PAGE = REPO_ROOT / "web" / "app" / "contributors" / "[id]" / "portfolio" / "page.tsx"

# Garden terms that should appear
GARDEN_TERMS = [
    "My Garden",
    "Harvest",
    "Plants I Tend",
    "Seeds I Planted",
    "Garden Work",
    "seeds harvested",
    "seeds planted",
    "share of garden",
    "Thriving",
    "Growing",
    "Dormant",
    "gardenHealth",
    "plantDescription",
]

# Ledger terms that should NOT appear as primary labels
LEDGER_TERMS = [
    "CC Balance",
    "CC Earning History",
    "Ideas I Contributed To",
    "Ideas I Staked On",
    "Tasks I Completed",
]


class TestPortfolioGardenMetaphorFileStructure:
    """Portfolio page exists and uses garden metaphor terminology."""

    def test_portfolio_page_exists(self):
        assert PORTFOLIO_PAGE.is_file(), f"Missing portfolio page: {PORTFOLIO_PAGE}"

    def test_portfolio_page_has_garden_header(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "My Garden" in content

    def test_portfolio_page_has_harvest_label(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Harvest" in content

    def test_portfolio_page_has_plants_i_tend(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Plants I Tend" in content

    def test_portfolio_page_has_seeds_i_planted(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Seeds I Planted" in content

    def test_portfolio_page_has_garden_work(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Garden Work" in content

    def test_portfolio_page_shows_seeds_not_cc(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "seeds" in content.lower()

    def test_portfolio_page_has_share_of_garden(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "share of garden" in content

    def test_portfolio_page_has_harvest_over_time(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Harvest Over Time" in content


class TestNoLedgerLabels:
    """Ledger terms should not appear as primary visible labels."""

    def test_no_cc_balance_label(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        # "CC Balance" should not appear as a section heading
        assert '"CC Balance"' not in content
        assert ">CC Balance<" not in content

    def test_no_cc_earning_history_label(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert '"CC Earning History"' not in content
        assert ">CC Earning History<" not in content

    def test_no_ideas_i_contributed_to(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert '"Ideas I Contributed To"' not in content
        assert ">Ideas I Contributed To<" not in content

    def test_no_ideas_i_staked_on(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert '"Ideas I Staked On"' not in content
        assert ">Ideas I Staked On<" not in content

    def test_no_tasks_i_completed(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert '"Tasks I Completed"' not in content
        assert ">Tasks I Completed<" not in content


class TestGardenHealthMapping:
    """Garden health mapping function exists and maps correctly."""

    def test_garden_health_function_exists(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "function gardenHealth" in content

    def test_active_maps_to_thriving(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert '"Thriving"' in content
        assert '"active"' in content

    def test_slow_maps_to_growing(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert '"Growing"' in content
        assert '"slow"' in content

    def test_dormant_maps_to_dormant(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert '"Dormant"' in content

    def test_unknown_maps_to_untested(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert '"Untested"' in content


class TestGardenDescriptionsions:
    """Garden description function for idea cards."""

    def test_plant_description_function_exists(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "function plantDescription" in content

    def test_thriving_description_present(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "thriving" in content.lower()

    def test_steady_growth_description_present(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Steady growth" in content

    def test_resting_description_present(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Resting" in content


class TestEmptyStatesGardenLanguage:
    """Empty state messages use garden language."""

    def test_no_plants_empty_state(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "No plants yet" in content

    def test_no_seeds_planted_empty_state(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "No seeds planted yet" in content

    def test_no_garden_work_empty_state(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "No garden work yet" in content


class TestAccessibilityAttributes:
    """Accessibility attributes are present."""

    def test_aria_hidden_on_emoji(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert 'aria-hidden="true"' in content

    def test_aria_label_on_health(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "aria-label" in content
        assert "Garden health" in content


class TestStakesGardenReframe:
    """Stakes section uses garden language."""

    def test_seeds_planted_label(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "seeds planted" in content.lower()

    def test_planted_date_label(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Planted" in content

    def test_yield_label(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "yield" in content.lower()

    def test_no_roi_primary_label(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        # ROI should only appear in secondary/details context, not as primary label
        assert "% ROI" not in content


class TestTasksGardenReframe:
    """Tasks section uses garden language."""

    def test_garden_work_header(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Garden Work" in content

    def test_seeds_harvested_label(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "seeds harvested" in content.lower()

    def test_tool_label_for_provider(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Tool:" in content

    def test_result_label_for_outcome(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "Result:" in content


class TestSecondaryFinancialLayer:
    """Financial numbers are behind expand/collapse."""

    def test_details_element_for_idea_cards(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "<details" in content

    def test_see_details_toggle(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "See details" in content

    def test_yield_behind_toggle_for_stakes(self):
        content = PORTFOLIO_PAGE.read_text(encoding="utf-8")
        assert "See yield" in content
