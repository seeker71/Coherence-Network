"""Request-level attribution — who the current caller claims to be.

Routes read the result of the attribution middleware through these
helpers. Nothing in this module does authentication: attribution is a
signal, and the source is explicit (`"verified"` vs `"claimed"`).

See `app/middleware/attribution.py` for how the fields land on
`request.state` in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fastapi import HTTPException, Request


AttributionSource = Literal["verified", "claimed"]


@dataclass(frozen=True)
class Attribution:
    """What the middleware saw for this request.

    - `verified` — a valid `Authorization: Bearer cc_*` that the store
      recognised. The contributor is who they say they are.
    - `claimed` — an `X-Contributor-Id` header with no proof. Use as a
      hint for analytics or attribution-only flows; never trust it for
      access control.
    - `None` — no attribution headers at all.
    """

    contributor_id: str | None = None
    source: AttributionSource | None = None
    scopes: list[str] = field(default_factory=list)


def get_attribution(request: Request) -> Attribution:
    """FastAPI Depends: pull the middleware's attribution off request.state."""
    cid = getattr(request.state, "contributor_id", None)
    source = getattr(request.state, "attribution_source", None)
    scopes = getattr(request.state, "contributor_scopes", None) or []
    return Attribution(
        contributor_id=cid,
        source=source,
        scopes=list(scopes),
    )


def require_verified_contributor(request: Request) -> Attribution:
    """FastAPI Depends: 401 unless the request carries a verified key.

    Claimed-only attribution is NOT sufficient. Use for self-administration
    endpoints like key listing and revocation.
    """
    att = get_attribution(request)
    if att.contributor_id is None or att.source != "verified":
        raise HTTPException(
            status_code=401,
            detail="verified contributor API key required (Authorization: Bearer cc_...)",
        )
    return att


def require_attribution(request: Request) -> Attribution:
    """FastAPI Depends: 400 unless *some* attribution is present.

    Accepts either verified keys or claimed headers. Useful for routes
    that need to record who did something but don't care whether the
    claim is trusted.
    """
    att = get_attribution(request)
    if att.contributor_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "attribution required — send Authorization: Bearer cc_... "
                "or X-Contributor-Id: <handle>"
            ),
        )
    return att
