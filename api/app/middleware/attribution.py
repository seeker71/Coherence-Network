"""Attribution middleware — populates request.state with WHO is calling.

Two paths, checked in order:

1. `Authorization: Bearer cc_<contributor>_<hex>` — looked up against the
   `contributor_key_store`. If the store recognises the key and the key
   is not revoked, `request.state.attribution_source = "verified"` and
   scopes are populated from the stored row.

2. `X-Contributor-Id: <handle>` — taken as-is with no proof.
   `request.state.attribution_source = "claimed"` and scopes are empty.

Neither → `request.state.contributor_id = None`, source = None.

Every response carries two echo headers so clients can see exactly what
the server attributed their call to:

    X-Attributed-To: <contributor_id>  (absent when None)
    X-Attribution-Source: verified|claimed|none

This middleware does NOT authenticate or authorise anything. It records
a signal. Routes that need authorisation use separate dependencies.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


logger = logging.getLogger(__name__)


AttributionTriple = Tuple[Optional[str], Optional[str], list[str]]


def _extract(headers) -> AttributionTriple:
    """Pure extraction: given request headers, return (contributor_id, source, scopes).

    Imported from contributor_key_store lazily so the module stays usable
    during tests that monkey-patch the store.
    """
    # 1. Authorization: Bearer cc_...
    auth = headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        raw_key = auth.split(" ", 1)[1].strip()
        if raw_key.startswith("cc_"):
            try:
                from app.services import contributor_key_store

                row = contributor_key_store.verify(raw_key)
                if row is not None:
                    return row.contributor_id, "verified", list(row.scopes)
            except Exception:
                logger.exception("attribution: key verify raised")
                # Fall through to claimed/none

    # 2. X-Contributor-Id: <handle>  (trust-me-bro signal)
    claimed = headers.get("x-contributor-id")
    if claimed:
        claimed = claimed.strip()
        if claimed:
            return claimed, "claimed", []

    return None, None, []


class AttributionMiddleware(BaseHTTPMiddleware):
    """Populates request.state and echoes the result on the response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        contributor_id, source, scopes = _extract(request.headers)
        request.state.contributor_id = contributor_id
        request.state.attribution_source = source
        request.state.contributor_scopes = scopes

        response = await call_next(request)

        if contributor_id:
            response.headers["X-Attributed-To"] = contributor_id
            response.headers["X-Attribution-Source"] = source or "none"
        else:
            response.headers["X-Attribution-Source"] = "none"

        return response
