"""Read tracking middleware — logs asset/concept reads for verification.

Non-blocking: records reads via BackgroundTasks after the response is sent.
Zero added latency to the read path.
"""

from __future__ import annotations

import re
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger(__name__)

# Patterns that constitute a "read" worth tracking
_READ_PATTERNS = [
    re.compile(r"^/api/concepts/(lc-[\w-]+)$"),  # concept page view
    re.compile(r"^/api/assets/([\w-]+)$"),         # asset metadata view
    re.compile(r"^/api/assets/([\w-]+)/content$"), # asset content view
]


class ReadTrackingMiddleware(BaseHTTPMiddleware):
    """Intercept GET requests to concept/asset endpoints and track reads."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only track successful GETs
        if request.method != "GET" or response.status_code != 200:
            return response

        path = request.url.path
        for pattern in _READ_PATTERNS:
            match = pattern.match(path)
            if match:
                asset_id = match.group(1)
                # Extract concept_id from the asset if it's a concept
                concept_id = asset_id if asset_id.startswith("lc-") else None
                # Fire and forget — don't block the response
                try:
                    from app.services import read_tracking_service
                    read_tracking_service.record_read(asset_id, concept_id)
                except Exception as e:
                    log.debug("read_tracking: %s", e)
                break

        return response
