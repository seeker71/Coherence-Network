"""Contributor Profile Service — what the system knows about a contributor.

Three layers of knowledge:
1. Identity — who you are (contributor record + linked external accounts)
2. Interests — what you care about (ideas created, staked, questioned, voted)
3. Activity — what you've done (commits, API usage, value lineage participation)

The profile feeds into:
- News resonance matching (personalized daily briefs)
- Task routing (assign tasks matching contributor expertise)
- Coherence scoring (active contributors boost network coherence)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ContributorProfile:
    """Aggregated view of what the system knows about a contributor."""

    # Identity layer
    contributor_id: str = ""
    name: str = ""
    email: str = ""
    contributor_type: str = "HUMAN"  # HUMAN or SYSTEM
    linked_identities: list[dict] = field(default_factory=list)  # [{provider, provider_id}]

    # Interest layer — derived from actions
    created_ideas: list[dict] = field(default_factory=list)
    staked_ideas: list[dict] = field(default_factory=list)
    asked_questions: list[dict] = field(default_factory=list)
    votes_cast: list[dict] = field(default_factory=list)

    # Activity layer
    commit_count: int = 0
    api_call_count: int = 0
    last_active: Optional[str] = None

    # Derived: keywords that represent this contributor's interests
    interest_keywords: set[str] = field(default_factory=set)

    # Derived: resonance weights per idea (how much they care about each)
    idea_weights: dict[str, float] = field(default_factory=dict)

    def compute_interest_keywords(self) -> set[str]:
        """Extract keywords from all ideas this contributor has interacted with."""
        from app.services.news_resonance_service import extract_keywords

        all_text = []
        # Ideas they created get highest weight
        for idea in self.created_ideas:
            all_text.append(idea.get("name", "") + " " + idea.get("description", ""))
        # Ideas they staked on
        for idea in self.staked_ideas:
            all_text.append(idea.get("name", "") + " " + idea.get("description", ""))
        # Questions they asked reveal interest
        for q in self.asked_questions:
            all_text.append(q.get("question", ""))

        combined = " ".join(all_text)
        self.interest_keywords = extract_keywords(combined)
        return self.interest_keywords

    def compute_idea_weights(self) -> dict[str, float]:
        """Compute how much this contributor cares about each idea.

        Weight factors:
        - Created the idea: 1.0
        - Staked CC on it: 0.8
        - Asked a question: 0.5
        - Voted on a related change: 0.3
        """
        weights: dict[str, float] = {}

        for idea in self.created_ideas:
            iid = idea.get("id", "")
            weights[iid] = weights.get(iid, 0) + 1.0

        for idea in self.staked_ideas:
            iid = idea.get("id", "")
            weights[iid] = weights.get(iid, 0) + 0.8

        for q in self.asked_questions:
            iid = q.get("idea_id", "")
            weights[iid] = weights.get(iid, 0) + 0.5

        for v in self.votes_cast:
            iid = v.get("idea_id", "")
            weights[iid] = weights.get(iid, 0) + 0.3

        # Normalize to 0-1
        if weights:
            max_w = max(weights.values())
            if max_w > 0:
                weights = {k: v / max_w for k, v in weights.items()}

        self.idea_weights = weights
        return weights


async def build_profile(
    contributor_id: str,
    api_base: str = "https://api.coherencycoin.com",
) -> ContributorProfile:
    """Build a contributor profile by aggregating data from multiple API endpoints.

    This is the "what we know about you" function. It pulls from:
    - Contributor record (identity)
    - Linked identities (GitHub, Ethereum, etc.)
    - Ideas they created or staked on (interests)
    - Questions they asked (curiosity signal)
    - Governance votes (investment signal)
    """
    profile = ContributorProfile(contributor_id=contributor_id)

    async with httpx.AsyncClient(
        base_url=api_base,
        headers={"User-Agent": "coherence-profile/1.0"},
        timeout=10,
    ) as client:
        # 1. Identity
        try:
            resp = await client.get(f"/api/contributors/{contributor_id}")
            if resp.status_code == 200:
                data = resp.json()
                profile.name = data.get("name", "")
                profile.email = data.get("email", "")
                profile.contributor_type = data.get("type", "HUMAN")
        except Exception as e:
            logger.warning("Could not fetch contributor %s: %s", contributor_id, e)

        # 2. Linked identities
        try:
            resp = await client.get(f"/api/identity/{contributor_id}")
            if resp.status_code == 200:
                profile.linked_identities = resp.json() if isinstance(resp.json(), list) else []
        except Exception:
            pass

        # 3. Ideas (all, then filter by contributor)
        try:
            resp = await client.get("/api/ideas", params={"limit": 200})
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("items", [])
                for idea in items:
                    cid = idea.get("contributor_id", "")
                    if cid == contributor_id:
                        profile.created_ideas.append(idea)
        except Exception:
            pass

    # Compute derived data
    profile.compute_interest_keywords()
    profile.compute_idea_weights()

    return profile


def profile_to_ideas_for_resonance(profile: ContributorProfile) -> list[dict]:
    """Convert a contributor profile into the ideas list format expected by resonance matching.

    If the contributor has staked ideas, use those.
    If not, use all ideas they created.
    If neither, return empty (will fall back to all ideas).
    """
    ideas = []
    seen = set()

    # Staked ideas first (highest signal)
    for idea in profile.staked_ideas:
        iid = idea.get("id", "")
        if iid and iid not in seen:
            seen.add(iid)
            weight = profile.idea_weights.get(iid, 0.5)
            ideas.append({
                "id": iid,
                "name": idea.get("name", ""),
                "description": idea.get("description", ""),
                "confidence": weight,
            })

    # Created ideas
    for idea in profile.created_ideas:
        iid = idea.get("id", "")
        if iid and iid not in seen:
            seen.add(iid)
            weight = profile.idea_weights.get(iid, 0.8)
            ideas.append({
                "id": iid,
                "name": idea.get("name", ""),
                "description": idea.get("description", ""),
                "confidence": weight,
            })

    return ideas
