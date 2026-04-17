"""Personal feed — your corner of the organism.

A read across existing tables. Each item carries a reason caption so
the UI can show why it's in your feed.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.services import personal_feed_service
from app.services.localized_errors import caller_lang

router = APIRouter()


@router.get(
    "/feed/personal",
    summary="Your corner of the organism — voices, reactions, proposals you touched or were touched by",
)
async def personal_feed(
    request: Request,
    contributor_id: str | None = Query(None),
    author_name: str | None = Query(None),
    limit: int = Query(40, ge=1, le=200),
    lang: str | None = Query(None),
) -> dict:
    locale = caller_lang(request, lang)
    items = personal_feed_service.build_personal_feed(
        contributor_id=contributor_id,
        author_name=author_name,
        limit=limit,
        locale=locale,
    )
    return {
        "items": items,
        "count": len(items),
        "locale": locale,
    }
