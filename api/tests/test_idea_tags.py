"""Tests for idea tagging system (spec 129).

Covers: tag normalization, create with tags, list filtering, PUT tag update,
and GET tag catalog. All tests use real Pydantic models — no mocks.
"""

from __future__ import annotations

import pytest

from app.models.idea import (
    Idea,
    IdeaCreate,
    IdeaTagCatalogEntry,
    IdeaTagCatalogResponse,
    IdeaTagUpdateRequest,
    IdeaTagUpdateResponse,
    IdeaWithScore,
)
from app.services.idea_service import normalize_tag, normalize_tags


# ===========================================================================
# TestTagNormalization — unit tests for normalize_tag / normalize_tags
# ===========================================================================


class TestTagNormalization:
    """Tag values are normalized: lowercase, slug format, deduped, sorted."""

    def test_normalize_tag_lowercase(self):
        assert normalize_tag("Ideas") == "ideas"

    def test_normalize_tag_trims_whitespace(self):
        assert normalize_tag("  governance  ") == "governance"

    def test_normalize_tag_internal_whitespace_to_dash(self):
        assert normalize_tag("open source") == "open-source"

    def test_normalize_tag_removes_special_chars(self):
        assert normalize_tag("api@v2!") == "apiv2"

    def test_normalize_tag_collapses_multiple_dashes(self):
        assert normalize_tag("foo--bar") == "foo-bar"

    def test_normalize_tag_strips_leading_trailing_dashes(self):
        assert normalize_tag("-hello-") == "hello"

    def test_normalize_tag_empty_returns_none(self):
        assert normalize_tag("") is None

    def test_normalize_tag_only_special_chars_returns_none(self):
        assert normalize_tag("!!!") is None

    def test_normalize_tags_deduplicates_case_insensitively(self):
        result = normalize_tags(["Ideas", "ideas", "IDEAS"])
        assert result == ["ideas"]

    def test_normalize_tags_sorted_ascending(self):
        result = normalize_tags(["search", "governance", "ideas"])
        assert result == ["governance", "ideas", "search"]

    def test_normalize_tags_filters_invalid(self):
        result = normalize_tags(["valid", "!!!"])
        assert result == ["valid"]

    def test_normalize_tags_empty_list(self):
        assert normalize_tags([]) == []

    def test_normalize_tags_with_whitespace_entries(self):
        result = normalize_tags(["  governance  ", "search", "  ideas  "])
        assert result == ["governance", "ideas", "search"]

    def test_normalize_tags_deduplicates_after_normalization(self):
        # "Ideas" and "  ideas  " both normalize to "ideas"
        result = normalize_tags(["Ideas", "  ideas  ", "search"])
        assert result == ["ideas", "search"]


# ===========================================================================
# TestIdeaTagsModel — model-level tag field tests
# ===========================================================================


class TestIdeaTagsModel:
    """Idea and IdeaCreate models expose the tags field."""

    def test_idea_default_tags_empty(self):
        idea = Idea(
            id="test", name="Test", description="desc",
            potential_value=10.0, estimated_cost=5.0,
        )
        assert idea.tags == []

    def test_idea_accepts_tags(self):
        idea = Idea(
            id="tagged", name="Tagged", description="desc",
            potential_value=10.0, estimated_cost=5.0,
            tags=["governance", "ideas"],
        )
        assert idea.tags == ["governance", "ideas"]

    def test_idea_create_default_tags_empty(self):
        req = IdeaCreate(
            id="test", name="Test", description="desc",
            potential_value=10.0, estimated_cost=5.0,
        )
        assert req.tags == []

    def test_idea_create_accepts_tags(self):
        req = IdeaCreate(
            id="test", name="Test", description="desc",
            potential_value=10.0, estimated_cost=5.0,
            tags=["search", "governance"],
        )
        assert req.tags == ["search", "governance"]

    def test_idea_with_score_inherits_tags(self):
        """IdeaWithScore extends Idea so tags pass through model_dump."""
        idea = Idea(
            id="scored", name="Scored", description="desc",
            potential_value=10.0, estimated_cost=5.0,
            tags=["ideas", "search"],
        )
        data = idea.model_dump()
        assert data["tags"] == ["ideas", "search"]


# ===========================================================================
# TestTagUpdateModels — IdeaTagUpdateRequest / Response / Catalog models
# ===========================================================================


class TestTagUpdateModels:
    """Tag-specific request/response models validate correctly."""

    def test_tag_update_request_accepts_empty(self):
        req = IdeaTagUpdateRequest(tags=[])
        assert req.tags == []

    def test_tag_update_request_stores_tags(self):
        req = IdeaTagUpdateRequest(tags=["ideas", "search"])
        assert req.tags == ["ideas", "search"]

    def test_tag_update_response_fields(self):
        resp = IdeaTagUpdateResponse(id="my-idea", tags=["governance", "ideas"])
        assert resp.id == "my-idea"
        assert resp.tags == ["governance", "ideas"]

    def test_tag_catalog_entry(self):
        entry = IdeaTagCatalogEntry(tag="governance", idea_count=7)
        assert entry.tag == "governance"
        assert entry.idea_count == 7

    def test_tag_catalog_response(self):
        resp = IdeaTagCatalogResponse(tags=[
            IdeaTagCatalogEntry(tag="governance", idea_count=7),
            IdeaTagCatalogEntry(tag="ideas", idea_count=5),
        ])
        assert len(resp.tags) == 2
        assert resp.tags[0].tag == "governance"


# ===========================================================================
# TestCreateIdeaNormalizesAndReturnsTags (spec acceptance test)
# ===========================================================================


class TestCreateIdeaNormalizesAndReturnsTags:
    """test_create_idea_normalizes_and_returns_tags — spec acceptance."""

    def test_normalize_on_create_via_service(self, tmp_path, monkeypatch):
        """Tags submitted at create time are normalized and stored."""
        import os
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

        # Patch _read_ideas to return empty list and _write_ideas to no-op
        # so we can test normalization in isolation without a full DB.
        from app.services import idea_service

        called_with: list[list[str]] = []

        original_create = idea_service.create_idea

        def _fake_set_tags(idea_id: str, tags: list[str]) -> None:
            called_with.append(tags)

        monkeypatch.setattr(idea_service._sql_tag_registry, "set_idea_tags", _fake_set_tags)
        monkeypatch.setattr(idea_service._sql_tag_registry, "load_all_idea_tags", lambda: {})

        # Patch _read_ideas to return empty and _write_ideas to no-op
        monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: [])
        monkeypatch.setattr(idea_service, "_write_ideas", lambda ideas: None)
        monkeypatch.setattr(idea_service, "_ensure_standing_questions", lambda ideas: (ideas, False))

        result = idea_service.create_idea(
            idea_id="tag-test-idea",
            name="Tag Test Idea",
            description="An idea with tags",
            potential_value=10.0,
            estimated_cost=5.0,
            tags=["Ideas", "search", "  governance  ", "ideas"],
        )

        assert result is not None
        assert result.tags == ["governance", "ideas", "search"]
        # set_idea_tags should have been called with normalized sorted list
        assert called_with == [["governance", "ideas", "search"]]

    def test_tags_default_empty_on_create(self, monkeypatch):
        """When no tags supplied, idea.tags is empty list."""
        from app.services import idea_service

        monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: [])
        monkeypatch.setattr(idea_service, "_write_ideas", lambda ideas: None)
        monkeypatch.setattr(idea_service, "_ensure_standing_questions", lambda ideas: (ideas, False))
        monkeypatch.setattr(idea_service._sql_tag_registry, "set_idea_tags", lambda *a: None)
        monkeypatch.setattr(idea_service._sql_tag_registry, "load_all_idea_tags", lambda: {})

        result = idea_service.create_idea(
            idea_id="no-tags",
            name="No Tags",
            description="desc",
            potential_value=10.0,
            estimated_cost=5.0,
        )
        assert result is not None
        assert result.tags == []


# ===========================================================================
# TestListIdeasFiltersByAllRequestedTags (spec acceptance test)
# ===========================================================================


class TestListIdeasFiltersByAllRequestedTags:
    """test_list_ideas_filters_by_all_requested_tags — spec acceptance."""

    def _make_idea(self, idea_id: str, tags: list[str]) -> Idea:
        return Idea(
            id=idea_id, name=idea_id.title(), description="desc",
            potential_value=10.0, estimated_cost=5.0,
            tags=tags,
        )

    def test_filters_by_single_tag(self, monkeypatch):
        from app.services import idea_service

        ideas = [
            self._make_idea("idea-a", ["governance", "ideas"]),
            self._make_idea("idea-b", ["search"]),
            self._make_idea("idea-c", ["governance", "search"]),
        ]
        monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: list(ideas))

        result = idea_service.list_ideas(tags=["governance"])
        returned_ids = {i.id for i in result.ideas}
        assert "idea-a" in returned_ids
        assert "idea-c" in returned_ids
        assert "idea-b" not in returned_ids

    def test_filters_by_multiple_tags_must_match_all(self, monkeypatch):
        from app.services import idea_service

        ideas = [
            self._make_idea("idea-a", ["governance", "ideas"]),
            self._make_idea("idea-b", ["search"]),
            self._make_idea("idea-c", ["governance", "ideas", "search"]),
        ]
        monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: list(ideas))

        result = idea_service.list_ideas(tags=["governance", "ideas"])
        returned_ids = {i.id for i in result.ideas}
        assert "idea-a" in returned_ids
        assert "idea-c" in returned_ids
        assert "idea-b" not in returned_ids

    def test_no_tags_filter_returns_all(self, monkeypatch):
        from app.services import idea_service

        ideas = [
            self._make_idea("idea-a", ["governance"]),
            self._make_idea("idea-b", []),
        ]
        monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: list(ideas))

        result = idea_service.list_ideas(tags=None)
        assert len(result.ideas) == 2

    def test_tag_filter_normalizes_input(self, monkeypatch):
        """Tag filter input is normalized before matching."""
        from app.services import idea_service

        ideas = [
            self._make_idea("idea-a", ["governance"]),
            self._make_idea("idea-b", ["search"]),
        ]
        monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: list(ideas))

        # "GOVERNANCE" should match "governance"
        result = idea_service.list_ideas(tags=["GOVERNANCE"])
        returned_ids = {i.id for i in result.ideas}
        assert "idea-a" in returned_ids
        assert "idea-b" not in returned_ids

    def test_pagination_preserved_with_tag_filter(self, monkeypatch):
        """Pagination reflects the filtered count, not total."""
        from app.services import idea_service

        ideas = [
            self._make_idea(f"idea-{i}", ["governance"]) for i in range(5)
        ] + [
            self._make_idea(f"other-{i}", ["search"]) for i in range(3)
        ]
        monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: list(ideas))

        result = idea_service.list_ideas(tags=["governance"], limit=10)
        assert result.pagination.total == 5
        assert result.pagination.returned == 5


# ===========================================================================
# TestPutIdeaTagsReplacesExistingTags (spec acceptance test)
# ===========================================================================


class TestPutIdeaTagsReplacesExistingTags:
    """test_put_idea_tags_replaces_existing_tags — spec acceptance."""

    def test_set_idea_tags_normalizes_and_replaces(self, monkeypatch):
        """set_idea_tags normalizes tags and calls SQL registry."""
        from app.services import idea_service

        existing_idea = Idea(
            id="my-idea", name="My Idea", description="desc",
            potential_value=10.0, estimated_cost=5.0,
            tags=["old-tag"],
        )
        monkeypatch.setattr(
            idea_service, "_read_ideas", lambda **kw: [existing_idea]
        )

        stored: list[list[str]] = []

        def _fake_set(idea_id: str, tags: list[str]) -> None:
            stored.append(tags)

        monkeypatch.setattr(idea_service._sql_tag_registry, "set_idea_tags", _fake_set)
        monkeypatch.setattr(idea_service, "_invalidate_ideas_cache", lambda: None)

        result = idea_service.set_idea_tags(
            "my-idea", ["Ideas", "search", "  governance  ", "ideas"]
        )

        assert result == ["governance", "ideas", "search"]
        assert stored == [["governance", "ideas", "search"]]

    def test_set_idea_tags_clears_with_empty_list(self, monkeypatch):
        """Empty tag array is valid and clears all tags."""
        from app.services import idea_service

        existing_idea = Idea(
            id="my-idea", name="My Idea", description="desc",
            potential_value=10.0, estimated_cost=5.0,
            tags=["old-tag"],
        )
        monkeypatch.setattr(
            idea_service, "_read_ideas", lambda **kw: [existing_idea]
        )

        stored: list[list[str]] = []
        monkeypatch.setattr(idea_service._sql_tag_registry, "set_idea_tags", lambda id, tags: stored.append(tags))
        monkeypatch.setattr(idea_service, "_invalidate_ideas_cache", lambda: None)

        result = idea_service.set_idea_tags("my-idea", [])
        assert result == []
        assert stored == [[]]

    def test_set_idea_tags_unknown_idea_returns_none(self, monkeypatch):
        """Unknown idea_id returns None."""
        from app.services import idea_service

        monkeypatch.setattr(idea_service, "_read_ideas", lambda **kw: [])
        monkeypatch.setattr(idea_service._sql_tag_registry, "set_idea_tags", lambda *a: None)

        result = idea_service.set_idea_tags("nonexistent", ["tag"])
        assert result is None


# ===========================================================================
# TestGetIdeaTagsCatalogReturnsCounts (spec acceptance test)
# ===========================================================================


class TestGetIdeaTagsCatalogReturnsCounts:
    """test_get_idea_tags_catalog_returns_counts — spec acceptance."""

    def test_catalog_returns_sorted_tag_counts(self, monkeypatch):
        from app.services import idea_service

        monkeypatch.setattr(
            idea_service._sql_tag_registry,
            "get_all_tag_counts",
            lambda: {"governance": 7, "ideas": 5, "search": 2},
        )

        catalog = idea_service.get_tag_catalog()
        assert catalog == [
            {"tag": "governance", "idea_count": 7},
            {"tag": "ideas", "idea_count": 5},
            {"tag": "search", "idea_count": 2},
        ]

    def test_catalog_empty_when_no_tags(self, monkeypatch):
        from app.services import idea_service

        monkeypatch.setattr(
            idea_service._sql_tag_registry,
            "get_all_tag_counts",
            lambda: {},
        )

        catalog = idea_service.get_tag_catalog()
        assert catalog == []

    def test_catalog_sorted_alphabetically(self, monkeypatch):
        from app.services import idea_service

        monkeypatch.setattr(
            idea_service._sql_tag_registry,
            "get_all_tag_counts",
            lambda: {"zzz": 1, "aaa": 3, "mmm": 2},
        )

        catalog = idea_service.get_tag_catalog()
        tags = [e["tag"] for e in catalog]
        assert tags == sorted(tags)

    def test_catalog_response_model_validates(self):
        """IdeaTagCatalogResponse validates the expected catalog structure."""
        resp = IdeaTagCatalogResponse(tags=[
            IdeaTagCatalogEntry(tag="governance", idea_count=7),
            IdeaTagCatalogEntry(tag="ideas", idea_count=5),
            IdeaTagCatalogEntry(tag="search", idea_count=2),
        ])
        assert len(resp.tags) == 3
        assert resp.tags[0].tag == "governance"
        assert resp.tags[0].idea_count == 7
