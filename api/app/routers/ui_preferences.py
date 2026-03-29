"""UI Preferences router — spec ux-tabs-mobile-friendly.

Stores per-contributor UI preferences:
- view_mode: tab layout variant (tabs | cards | table | graph)
- expert_mode: show IDs, raw JSON, API links
- nav_layout: primary navigation style (top | bottom_bar)
- idea_detail_tab: last active tab on idea detail (overview | specs | tasks | contributors | edges | history)
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/preferences", tags=["ui-preferences"])

# In-memory store keyed by contributor_id.
# In production this would be backed by the unified DB.
_STORE: dict[str, dict] = {}

ALLOWED_VIEW_MODES = {"tabs", "cards", "table", "graph"}
ALLOWED_NAV_LAYOUTS = {"top", "bottom_bar"}
ALLOWED_IDEA_TABS = {"overview", "specs", "tasks", "contributors", "edges", "history"}
ALLOWED_IDEAS_VIEWS = {"cards", "table", "graph"}


class UIPreferences(BaseModel):
    contributor_id: str = Field(..., description="Identifier of the contributor")
    expert_mode: bool = Field(
        False,
        description=(
            "Expert mode: show IDs, raw JSON toggle, API endpoint links. "
            "When False, technical fields are hidden and guided tooltips are shown."
        ),
    )
    nav_layout: Literal["top", "bottom_bar"] = Field(
        "top",
        description="Primary navigation position: 'top' header tabs or 'bottom_bar' for mobile.",
    )
    ideas_view: Literal["cards", "table", "graph"] = Field(
        "cards",
        description="Ideas list view mode: cards | table | graph.",
    )
    idea_detail_tab: Literal[
        "overview", "specs", "tasks", "contributors", "edges", "history"
    ] = Field(
        "overview",
        description="Last active tab on the idea detail page.",
    )
    swipeable_cards: bool = Field(
        False,
        description="Enable swipeable card deck on mobile (touch-optimised).",
    )
    collapsible_sections: bool = Field(
        True,
        description="Collapse long content sections on mobile to reduce scroll depth.",
    )
    show_tooltips: bool = Field(
        True,
        description="Show guided tooltips for novice mode. Disabled automatically in expert mode.",
    )


class UIPreferencesUpdate(BaseModel):
    expert_mode: Optional[bool] = None
    nav_layout: Optional[Literal["top", "bottom_bar"]] = None
    ideas_view: Optional[Literal["cards", "table", "graph"]] = None
    idea_detail_tab: Optional[
        Literal["overview", "specs", "tasks", "contributors", "edges", "history"]
    ] = None
    swipeable_cards: Optional[bool] = None
    collapsible_sections: Optional[bool] = None
    show_tooltips: Optional[bool] = None


def _defaults(contributor_id: str) -> dict:
    return {
        "contributor_id": contributor_id,
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }


@router.get(
    "/ui",
    response_model=UIPreferences,
    summary="Get UI preferences for a contributor",
    description=(
        "Returns UI preferences for the given contributor. "
        "If no preferences have been saved, returns defaults. "
        "Pass ?contributor_id=<id> to scope to a specific contributor."
    ),
)
def get_ui_preferences(contributor_id: str = "anonymous") -> UIPreferences:
    data = _STORE.get(contributor_id, _defaults(contributor_id))
    return UIPreferences(**data)


@router.put(
    "/ui",
    response_model=UIPreferences,
    summary="Upsert UI preferences for a contributor",
)
def upsert_ui_preferences(
    body: UIPreferences,
) -> UIPreferences:
    """Create or fully replace UI preferences for a contributor."""
    if not body.contributor_id or not body.contributor_id.strip():
        raise HTTPException(status_code=422, detail="contributor_id is required")
    _STORE[body.contributor_id] = body.model_dump()
    return body


@router.patch(
    "/ui",
    response_model=UIPreferences,
    summary="Partially update UI preferences for a contributor",
)
def patch_ui_preferences(
    contributor_id: str,
    body: UIPreferencesUpdate,
) -> UIPreferences:
    """Partial update — only supplied fields are changed."""
    if not contributor_id or not contributor_id.strip():
        raise HTTPException(status_code=422, detail="contributor_id query param is required")

    current = _STORE.get(contributor_id, _defaults(contributor_id))
    patch = body.model_dump(exclude_none=True)
    current.update(patch)
    _STORE[contributor_id] = current
    return UIPreferences(**current)


@router.delete(
    "/ui",
    summary="Reset UI preferences to defaults for a contributor",
    status_code=204,
)
def reset_ui_preferences(contributor_id: str = "anonymous") -> None:
    """Remove stored preferences, reverting to system defaults on next GET."""
    _STORE.pop(contributor_id, None)
