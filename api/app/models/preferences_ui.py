"""Pydantic models for per-contributor UI preferences (UX overhaul / tabbed shell)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UIMode = Literal["novice", "expert"]
IdeasListView = Literal["cards", "table", "graph"]
IdeaDetailTab = Literal[
    "overview",
    "specs",
    "tasks",
    "contributors",
    "edges",
    "history",
]


class ExpertFlags(BaseModel):
    """Expert-mode affordances (IDs, raw JSON, API links)."""

    show_ids: bool = False
    show_raw_json: bool = False
    show_api_links: bool = False


class MobilePrefs(BaseModel):
    """Mobile-first shell options."""

    bottom_nav_enabled: bool = True
    card_swipe_hints_dismissed: bool = False


class UIPreferencesResponse(BaseModel):
    """Full stored UI preferences returned by GET and PUT."""

    schema_version: int = Field(default=1, ge=1)
    contributor_id: str
    updated_at: str
    ui_mode: UIMode = "novice"
    ideas_list_view: IdeasListView = "cards"
    idea_detail_tab: IdeaDetailTab = "overview"
    primary_nav_collapsed: bool = False
    expert: ExpertFlags = Field(default_factory=ExpertFlags)
    mobile: MobilePrefs = Field(default_factory=MobilePrefs)


class UIPreferencesUpdate(BaseModel):
    """Partial update body for PUT — omitted fields leave existing values."""

    ui_mode: UIMode | None = None
    ideas_list_view: IdeasListView | None = None
    idea_detail_tab: IdeaDetailTab | None = None
    primary_nav_collapsed: bool | None = None
    expert: ExpertFlags | None = None
    mobile: MobilePrefs | None = None
