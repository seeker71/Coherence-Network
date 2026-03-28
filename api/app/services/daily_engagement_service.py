"""Aggregate personalized daily engagement: news brief, skill opportunities, tasks, peers, patterns."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.agent import TaskStatus
from app.models.daily_engagement import (
    ContributorNearby,
    DailyEngagementResponse,
    IdeaOpportunity,
    MorningBriefSection,
    NetworkPattern,
    NewsMatchBrief,
    TaskOpportunity,
)
from app.services import agent_service, contribution_ledger_service, idea_service, news_ingestion_service, news_resonance_service


def _ideas_as_dicts(ideas) -> list[dict[str, Any]]:
    return [
        {
            "id": idea.id,
            "name": idea.name,
            "description": idea.description,
            "confidence": idea.confidence,
        }
        for idea in ideas
    ]


def _staked_idea_ids(contributor_id: str) -> set[str]:
    staked: set[str] = set()
    try:
        records = contribution_ledger_service.get_contributor_history(contributor_id, limit=500)
        for rec in records:
            idea_id = rec.get("idea_id") if isinstance(rec, dict) else getattr(rec, "idea_id", None)
            if idea_id:
                staked.add(idea_id)
    except Exception:
        pass
    return staked


def _keyword_surface_for_staked(staked_ids: set[str], idea_map: dict[str, Any]) -> set[str]:
    """Tokens from staked ideas' names and descriptions."""
    from app.services.news_resonance_service import extract_keywords

    tokens: set[str] = set()
    for iid in staked_ids:
        idea = idea_map.get(iid)
        if idea is None:
            continue
        text = f"{idea.name} {idea.description}"
        tokens |= extract_keywords(text)
    return tokens


def _ideas_needing_skills(
    portfolio_ideas: list,
    staked_tokens: set[str],
    limit: int = 8,
) -> list[IdeaOpportunity]:
    """Ideas with unanswered questions, ranked by keyword overlap with staked surface."""
    from app.services.news_resonance_service import extract_keywords

    if not staked_tokens:
        return []

    scored: list[tuple[float, IdeaOpportunity]] = []
    for idea in portfolio_ideas:
        unanswered: list[str] = []
        for q in idea.open_questions:
            ans = getattr(q, "answer", None)
            if ans and str(ans).strip():
                continue
            unanswered.append(q.question)

        if not unanswered:
            continue

        q_text = " ".join(unanswered)
        q_tokens = extract_keywords(q_text + " " + idea.name + " " + idea.description)
        if not q_tokens:
            continue
        inter = len(q_tokens & staked_tokens)
        union = len(q_tokens | staked_tokens) or 1
        jaccard = inter / union
        scored.append(
            (
                jaccard,
                IdeaOpportunity(
                    idea_id=idea.id,
                    name=idea.name,
                    skill_overlap_score=round(min(1.0, jaccard * 2.5), 4),
                    open_questions=unanswered[:3],
                ),
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


def _flatten_top_news_matches(
    resonance_results: list,
    max_items: int,
) -> list[NewsMatchBrief]:
    """Deduplicate by URL and take highest-scoring matches across ideas."""
    seen: set[str] = set()
    flat: list[NewsMatchBrief] = []

    for r in resonance_results:
        idea_name = getattr(r, "idea_name", "") or ""
        idea_id = getattr(r, "idea_id", "") or ""
        for m in getattr(r, "matches", []) or []:
            ni = m.news_item
            url = ni.get("url", "") if isinstance(ni, dict) else getattr(ni, "url", "")
            if not url or url in seen:
                continue
            if getattr(m, "resonance_score", 0) < 0.12:
                continue
            seen.add(url)
            title = ni.get("title", "") if isinstance(ni, dict) else getattr(ni, "title", "")
            src = ni.get("source", "") if isinstance(ni, dict) else getattr(ni, "source", "")
            kws = list(getattr(m, "matched_keywords", []) or [])
            flat.append(
                NewsMatchBrief(
                    score=float(getattr(m, "resonance_score", 0.0)),
                    title=title[:500],
                    url=url[:2000],
                    source=str(src)[:200],
                    idea_id=idea_id,
                    idea_name=idea_name[:300],
                    reason=str(getattr(m, "reason", ""))[:500],
                    matched_keywords=kws[:20],
                )
            )
            if len(flat) >= max_items:
                return sorted(flat, key=lambda x: x.score, reverse=True)

    return sorted(flat, key=lambda x: x.score, reverse=True)


async def build_daily_engagement(
    contributor_id: str,
    *,
    refresh: bool = False,
    news_limit: int = 100,
    top_news_matches: int = 10,
    task_limit: int = 12,
    peer_limit: int = 12,
) -> DailyEngagementResponse:
    """Compose news brief, skill-fit ideas, pending tasks, peers, and network patterns."""
    now = datetime.now(timezone.utc)

    items = await news_ingestion_service.fetch_feeds(force_refresh=refresh)
    items = items[: max(1, min(news_limit, 500))]

    staked = _staked_idea_ids(contributor_id)
    portfolio = idea_service.list_ideas()
    all_ideas = portfolio.ideas
    idea_map = {i.id: i for i in all_ideas}
    idea_dicts = _ideas_as_dicts(all_ideas)

    if staked:
        filtered_ideas = [i for i in idea_dicts if i["id"] in staked]
    else:
        filtered_ideas = idea_dicts

    resonance_results = news_resonance_service.compute_resonance(
        items, filtered_ideas, top_n=5
    )
    top_matches = _flatten_top_news_matches(resonance_results, top_news_matches)

    staked_tokens = _keyword_surface_for_staked(staked, idea_map)
    if not staked_tokens and all_ideas:
        from app.services.news_resonance_service import extract_keywords

        for idea in all_ideas[:40]:
            staked_tokens |= extract_keywords(f"{idea.name} {idea.description}")
    ideas_skills = _ideas_needing_skills(all_ideas, staked_tokens, limit=8)

    tasks_out: list[TaskOpportunity] = []
    if task_limit > 0:
        raw_tasks, _total, _fb = agent_service.list_tasks(
            status=TaskStatus.PENDING,
            limit=max(1, min(task_limit, 50)),
            offset=0,
        )
    else:
        raw_tasks = []
    for t in raw_tasks[:task_limit] if task_limit else []:
        tid = str(t.get("id", ""))
        tasks_out.append(
            TaskOpportunity(
                task_id=tid,
                direction=str(t.get("direction", ""))[:2000],
                task_type=str(t.get("task_type", "impl")),
                status=str(t.get("status", "pending")),
            )
        )

    from app.services import graph_service

    peers: list[ContributorNearby] = []
    cid_lower = contributor_id.strip().lower()
    cid_node = f"contributor:{cid_lower}"
    if peer_limit <= 0:
        peers_raw = {"items": []}
    else:
        peers_raw = graph_service.list_nodes(type="contributor", limit=peer_limit + 5, offset=0)
    for node in peers_raw.get("items", []) or []:
        name = str(node.get("name", "") or "")
        nid = str(node.get("id", "") or "")
        if name.lower() == cid_lower or nid.lower() == cid_node or nid.lower() == cid_lower:
            continue
        ctype = str(node.get("contributor_type") or "")
        peers.append(
            ContributorNearby(
                node_id=nid,
                name=name[:500],
                description=str(node.get("description", "") or "")[:800],
                contributor_type=ctype,
            )
        )
        if len(peers) >= peer_limit:
            break

    patterns: list[NetworkPattern] = []
    try:
        trending = news_ingestion_service.extract_trending_keywords(items, top_n=8)
        for row in trending[:5]:
            kw = row.get("keyword", "")
            cnt = float(row.get("count", 0))
            if kw:
                patterns.append(
                    NetworkPattern(
                        kind="trending_keyword",
                        label=kw,
                        detail="from today's news scan",
                        score=cnt,
                    )
                )
    except Exception:
        pass

    try:
        feed = idea_service.get_resonance_feed(window_hours=48, limit=5)
        for row in feed:
            patterns.append(
                NetworkPattern(
                    kind="idea_activity",
                    label=str(row.get("name", "idea")),
                    detail=f"recent activity · {row.get('manifestation_status', '')}",
                    score=float(row.get("free_energy_score", 0.0)),
                )
            )
    except Exception:
        pass

    brief = MorningBriefSection(
        articles_scanned=len(items),
        ideas_considered=len(filtered_ideas),
        staked_idea_count=len(staked),
        top_matches=top_matches,
    )

    return DailyEngagementResponse(
        generated_at=now,
        contributor_id=contributor_id,
        morning_brief=brief,
        ideas_needing_skills=ideas_skills,
        tasks_for_providers=tasks_out,
        contributors_nearby=peers,
        network_patterns=patterns[:12],
        meta={
            "news_refresh": refresh,
            "fallback_all_ideas": len(staked) == 0,
        },
    )
