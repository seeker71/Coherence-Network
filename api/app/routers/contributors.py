"""Contributors router — backed by graph_nodes (type=contributor)."""
from __future__ import annotations

import hashlib
import re
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.contributor import Contributor, ContributorCreate
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services import graph_service, contributor_service

router = APIRouter()


# ── Identity providers ────────────────────────────────────────────
#
# A contributor is the ONE stable node; its identity can be asserted
# by any of several providers. Whichever provider a visitor arrives
# with (email on the laptop, wallet on the phone, crypto keypair on
# their workstation), they all resolve to the same contributor id
# and carry the same profile. Adding a new provider = register a
# handler in ``_PROVIDERS`` below; no churn in the endpoint logic.

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _validate_email(value: str) -> str:
    norm = _normalize_email(value)
    if not norm or not _EMAIL_RE.match(norm):
        raise HTTPException(status_code=400, detail="email is not well-formed")
    return norm


def _normalize_public_key(value: str) -> str:
    # Strip 0x prefix, lowercase, keep only hex. Two callers who
    # copy-paste with slightly different formatting still land on
    # the same id.
    v = (value or "").strip().lower()
    if v.startswith("0x"):
        v = v[2:]
    return "".join(c for c in v if c in "0123456789abcdef")


def _validate_public_key(value: str) -> str:
    norm = _normalize_public_key(value)
    if len(norm) < 32:
        raise HTTPException(status_code=400, detail="public_key is too short")
    return norm


def _normalize_wallet(value: str) -> str:
    # Checksum-case doesn't matter for equality; we store lowercase.
    return (value or "").strip().lower()


def _validate_wallet(value: str) -> str:
    norm = _normalize_wallet(value)
    if not norm:
        raise HTTPException(status_code=400, detail="wallet_address is required")
    if norm.startswith("0x") and len(norm) != 42:
        raise HTTPException(status_code=400, detail="wallet_address looks malformed")
    return norm


# Each provider handler: how to normalize its claim, how to derive
# the stable contributor slug from it, and which node property the
# claim lands in for lookup. Adding "oauth_google" or "did_key" is a
# matter of adding an entry here + teaching the client to send it.
_PROVIDERS: dict[str, dict] = {
    "email": {
        "normalize": _normalize_email,
        "validate": _validate_email,
        "slug": lambda v: f"email-{hashlib.sha256(v.encode()).hexdigest()[:16]}",
        "property": "email",
        "label": "email",
    },
    "public_key": {
        "normalize": _normalize_public_key,
        "validate": _validate_public_key,
        "slug": lambda v: f"key-{hashlib.sha256(v.encode()).hexdigest()[:16]}",
        "property": "public_key",
        "label": "public key",
    },
    "wallet_address": {
        "normalize": _normalize_wallet,
        "validate": _validate_wallet,
        "slug": lambda v: f"wallet-{hashlib.sha256(v.encode()).hexdigest()[:16]}",
        "property": "wallet_address",
        "label": "wallet address",
    },
}


def _collect_claims(body: "GraduateIn") -> list[tuple[str, str]]:
    """Pull every identity claim the caller sent into a normalized
    ``[(provider, value), ...]`` list. Empty/missing fields are
    silently dropped so a graduate call with only an email is fine."""
    claims: list[tuple[str, str]] = []
    for provider, handler in _PROVIDERS.items():
        raw = getattr(body, provider, None)
        if not raw:
            continue
        norm = handler["normalize"](raw)
        if norm:
            claims.append((provider, norm))
    return claims


def _find_contributor_by_claims(claims: list[tuple[str, str]]) -> dict | None:
    """Look up a contributor by any of the provided identity claims.

    Fast path: try each provider's slug-id; one hit wins. Slow path:
    scan the contributor bucket matching on the property — catches
    pre-existing nodes that were created before this provider's slug
    scheme existed, and nodes registered via a different entry
    point (crypto /join) that stored the identity on a property
    without adopting the derived id."""
    for provider, value in claims:
        handler = _PROVIDERS[provider]
        slug = handler["slug"](value)
        node = graph_service.get_node(f"contributor:{slug}")
        if node:
            return node

    # Slow path only runs when fast path misses. One DB read covers
    # all providers.
    if not claims:
        return None
    result = graph_service.list_nodes(type="contributor", limit=1000)
    for n in result.get("items", []):
        for provider, value in claims:
            prop_name = _PROVIDERS[provider]["property"]
            stored = n.get(prop_name) or ""
            if _PROVIDERS[provider]["normalize"](str(stored)) == value:
                return n
    return None


def _stable_slug_for(claims: list[tuple[str, str]]) -> str:
    """Pick which claim derives the new contributor's id. Preference
    order matches _PROVIDERS insertion order: email first (most
    humans have one), then public_key, then wallet. Whichever claim
    the visitor arrived with becomes the root, and later identities
    land as additional properties on the same node."""
    for provider in _PROVIDERS:
        for p, v in claims:
            if p == provider:
                return _PROVIDERS[provider]["slug"](v)
    return ""  # caller handles empty (falls back to fingerprint path)


class GraduateIn(BaseModel):
    """Soft-identity graduation request.

    A visitor graduates to a real contributor node by asserting one
    or more identity claims: ``email``, ``public_key``, or
    ``wallet_address`` (more providers — oauth, DID — slot in via
    ``_PROVIDERS`` with no endpoint-level changes).

    All identity claims on a single call resolve to the SAME
    contributor. First claim wins the stable id; additional claims
    land on the node as properties so later lookups by any of them
    find the same contributor. When a visitor arrives on a new
    device asserting an identity the server has seen before, they
    get their existing contributor id back — no duplicate node, full
    profile intact.

    ``device_fingerprint`` is a legacy fallback: when no real
    identity claim is provided (quick reactions, voices before a
    real sign-in), the id falls back to ``{name}-{fingerprint}``.
    That path mints per-device contributors, which is acceptable for
    transient presence but not for the lived identity a human
    carries across their devices.
    """
    author_name: str
    # Identity providers — any combination. Empty/missing → soft
    # fingerprint fallback.
    email: str | None = None
    public_key: str | None = None
    wallet_address: str | None = None
    device_fingerprint: str | None = None
    invited_by: str | None = None
    # Optional profile bundle that carries forward on every
    # graduation. Merges onto the contributor node so all settings
    # live on one source of truth — no duplicate
    # interested-person sibling, no consent flags scattered across
    # localStorage.
    locale: str | None = None
    location: str | None = None
    skills: str | None = None
    offering: str | None = None
    resonant_roles: list[str] | None = None
    message: str | None = None
    consent_share_name: bool | None = None
    consent_share_location: bool | None = None
    consent_share_skills: bool | None = None
    consent_findable: bool | None = None
    consent_email_updates: bool | None = None


class GraduateOut(BaseModel):
    contributor_id: str
    created: bool
    invited_by: str | None = None
    # The merged state — so the client doesn't need a second
    # round-trip to pick up what landed on the node.
    email: str | None = None
    public_key: str | None = None
    wallet_address: str | None = None
    author_display_name: str | None = None
    locale: str | None = None
    resonant_roles: list[str] = []


def _merge_profile(existing: dict, body: GraduateIn, name: str) -> dict:
    """Compute the property set for a graduate call. When fields are
    omitted (None) on the input, the existing value is preserved so
    partial updates (e.g. just a new locale) don't wipe earlier
    consent flags. Empty strings are respected as an explicit clear."""
    props = dict(existing)

    # Name changes always land — the visitor's latest self-description
    # is the truth. ``author_display_name`` preserves the original
    # rendering ('Ana María') even when we slug-normalize elsewhere.
    props["author_display_name"] = name

    # Optional profile fields: only merge when the client sent them.
    simple_fields = (
        "locale",
        "location",
        "skills",
        "offering",
        "message",
        "consent_share_name",
        "consent_share_location",
        "consent_share_skills",
        "consent_findable",
        "consent_email_updates",
    )
    for field in simple_fields:
        value = getattr(body, field, None)
        if value is not None:
            props[field] = value

    if body.resonant_roles is not None:
        # Roles replace rather than append — the form is the full list
        # each submit, so a role de-selected on the second visit
        # should drop off.
        props["resonant_roles"] = body.resonant_roles

    return props


def _strip_prefix(node_id: str) -> str:
    return node_id.removeprefix("contributor:") if node_id.startswith("contributor:") else node_id


def _response_from_node(
    node: dict,
    *,
    created: bool,
    name_fallback: str,
) -> GraduateOut:
    roles = node.get("resonant_roles") or []
    if not isinstance(roles, list):
        roles = []
    return GraduateOut(
        contributor_id=_strip_prefix(node["id"]),
        created=created,
        invited_by=node.get("invited_by"),
        email=node.get("email"),
        public_key=node.get("public_key"),
        wallet_address=node.get("wallet_address"),
        author_display_name=node.get("author_display_name") or name_fallback,
        locale=node.get("locale"),
        resonant_roles=roles,
    )


@router.post(
    "/contributors/graduate",
    response_model=GraduateOut,
    summary="Soft-identity graduation — multi-provider, idempotent across devices",
)
def graduate_contributor(body: GraduateIn) -> GraduateOut:
    """Create (or return) the contributor that matches the asserted
    identity claims.

    Provider-agnostic: email, public_key, and wallet_address each
    resolve to the same contributor when they point to the same
    person. Profile fields merge onto the node on every call —
    later calls can update a subset without clobbering earlier
    values; ``invited_by`` is recorded only on the initial create.

    ``device_fingerprint`` is a legacy soft-identity fallback: when
    no real provider claim is sent, the id falls back to
    ``{name}-{fingerprint}``. That path is for reactions/voices
    before a sign-in — anything that should cross devices should
    send a real identity claim instead."""
    name = (body.author_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="author_name is required")

    # Validate every claim up-front so a malformed email doesn't
    # silently get stored alongside a valid public_key.
    validated: list[tuple[str, str]] = []
    for provider, handler in _PROVIDERS.items():
        raw = getattr(body, provider, None)
        if raw:
            validated.append((provider, handler["validate"](raw)))

    # ── Real identity path ────────────────────────────────────────
    if validated:
        existing = _find_contributor_by_claims(validated)
        if existing:
            merged = _merge_profile(existing, body, name)
            merged.setdefault("contributor_type", "HUMAN")
            # Every asserted claim lands on the node — if the visitor
            # is linking a new identity to an existing contributor
            # (e.g. adding a wallet to their email-based account),
            # it's recorded here.
            for provider, value in validated:
                prop_name = _PROVIDERS[provider]["property"]
                merged[prop_name] = value
            graph_service.update_node(
                existing["id"],
                name=name,
                properties=merged,
            )
            # Re-fetch to get the latest merged state for the response.
            refreshed = graph_service.get_node(existing["id"]) or existing
            return _response_from_node(refreshed, created=False, name_fallback=name)

        # First time we've seen any of these claims — mint a new
        # contributor keyed by the first (preferred) claim.
        slug = _stable_slug_for(validated)
        invited_by = (body.invited_by or "").strip() or None
        props: dict = {
            "contributor_type": "HUMAN",
            "author_display_name": name,
            "invited_by": invited_by,
        }
        # Fingerprint optional per-device cache (not the stable key).
        fp = (body.device_fingerprint or "").strip()[:24]
        if fp:
            props["first_fingerprint"] = fp
        for provider, value in validated:
            props[_PROVIDERS[provider]["property"]] = value
        props.update(_merge_profile({}, body, name))
        # Re-assert authoritative identity values after the merge so
        # _merge_profile can't overwrite them with None/empty.
        for provider, value in validated:
            props[_PROVIDERS[provider]["property"]] = value
        node_id = f"contributor:{slug}"
        graph_service.create_node(
            id=node_id,
            type="contributor",
            name=name,
            description="HUMAN contributor",
            phase="water",
            properties=props,
        )
        created_node = graph_service.get_node(node_id) or {
            "id": node_id, **props,
        }
        return _response_from_node(created_node, created=True, name_fallback=name)

    # ── Fingerprint fallback (legacy) ─────────────────────────────
    fp = (body.device_fingerprint or uuid4().hex[:8]).strip()[:24]
    safe_name = "".join(c for c in name.lower() if c.isalnum() or c in "-_") or "friend"
    safe_fp = "".join(c for c in fp.lower() if c.isalnum() or c in "-_") or uuid4().hex[:8]
    candidate_id = f"{safe_name}-{safe_fp}"[:64]

    existing = graph_service.get_node(f"contributor:{candidate_id}")
    if existing:
        return _response_from_node(existing, created=False, name_fallback=name)

    invited_by = (body.invited_by or "").strip() or None
    node_id = f"contributor:{candidate_id}"
    graph_service.create_node(
        id=node_id,
        type="contributor",
        name=candidate_id,
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"{candidate_id}@coherence.network",
            "author_display_name": name,
            "invited_by": invited_by,
        },
    )
    created_node = graph_service.get_node(node_id) or {"id": node_id, "author_display_name": name}
    return _response_from_node(created_node, created=True, name_fallback=name)


class ClaimByIdentityIn(BaseModel):
    """Resolve a contributor by any of its known identity claims. The
    caller sends whichever they have — email on a phone, public_key
    on a workstation, wallet_address from a connected wallet — and
    the server returns the matching contributor's full profile."""
    email: str | None = None
    public_key: str | None = None
    wallet_address: str | None = None


class ClaimByIdentityOut(BaseModel):
    contributor_id: str
    author_display_name: str | None = None
    locale: str | None = None
    resonant_roles: list[str] = []
    invited_by: str | None = None
    email: str | None = None
    public_key: str | None = None
    wallet_address: str | None = None
    matched_provider: str


@router.post(
    "/contributors/claim-by-identity",
    response_model=ClaimByIdentityOut,
    responses={404: {"model": ErrorDetail, "description": "No contributor matches the provided identity"}},
    summary="Restore a contributor on a new device by any identity provider",
)
def claim_by_identity(body: ClaimByIdentityIn) -> ClaimByIdentityOut:
    """Look up a contributor by any identity claim the caller holds.

    No magic-link verification yet — anyone who knows an email (or
    public_key, or wallet_address) can claim that identity from a
    new device. Acceptable for soft identity (reactions, voices,
    resonance); anything that touches the wallet / treasury layers
    crypto signatures on top of this."""
    # Validate every provided claim; at least one must be present.
    claims: list[tuple[str, str]] = []
    for provider, handler in _PROVIDERS.items():
        raw = getattr(body, provider, None)
        if raw:
            claims.append((provider, handler["validate"](raw)))
    if not claims:
        raise HTTPException(
            status_code=400,
            detail="at least one identity claim (email, public_key, wallet_address) is required",
        )

    node = _find_contributor_by_claims(claims)
    if not node:
        raise HTTPException(
            status_code=404,
            detail="No contributor registered for the provided identity",
        )

    # Which claim matched? Useful for the UI ('welcome back, signed
    # in via wallet') and telemetry.
    matched_provider = claims[0][0]
    for provider, value in claims:
        prop_name = _PROVIDERS[provider]["property"]
        stored = _PROVIDERS[provider]["normalize"](str(node.get(prop_name) or ""))
        if stored == value:
            matched_provider = provider
            break

    roles = node.get("resonant_roles") or []
    if not isinstance(roles, list):
        roles = []
    return ClaimByIdentityOut(
        contributor_id=_strip_prefix(node["id"]),
        author_display_name=node.get("author_display_name") or node.get("name"),
        locale=node.get("locale"),
        resonant_roles=roles,
        invited_by=node.get("invited_by"),
        email=node.get("email"),
        public_key=node.get("public_key"),
        wallet_address=node.get("wallet_address"),
        matched_provider=matched_provider,
    )


def _node_to_contributor(node: dict) -> Contributor:
    """Convert a graph node to a Contributor model."""
    legacy_id = node.get("legacy_id", "")
    try:
        cid = UUID(legacy_id) if legacy_id and "-" in legacy_id else uuid4()
    except (ValueError, AttributeError):
        cid = uuid4()
    email = node.get("email") or ""
    # Contributor model requires a valid email — use a placeholder if missing
    if not email or "@" not in email:
        email = f"{node.get('name', 'unknown')}@coherence.network"
    # Coerce unknown contributor_type values to SYSTEM so a stray label in
    # the graph never blows up the endpoint for every caller.
    raw_type = str(node.get("contributor_type") or "HUMAN").strip().upper()
    try:
        from app.models.contributor import ContributorType
        contrib_type = ContributorType(raw_type)
    except ValueError:
        contrib_type = ContributorType.SYSTEM
    # ``claimed`` defaults to True for living contributors — only
    # placeholder identities minted by the inspired-by resolver carry
    # ``claimed: False``. The directory uses this to render the waiting
    # distinctly from the walked-in.
    claimed = bool(node.get("claimed", True))
    return Contributor(
        id=cid,
        name=node.get("name", ""),
        type=contrib_type,
        email=email,
        wallet_address=node.get("wallet_address") or None,
        hourly_rate=float(node["hourly_rate"]) if node.get("hourly_rate") else None,
        locale=node.get("locale") or None,
        claimed=claimed,
        canonical_url=node.get("canonical_url") or None,
    )


@router.post(
    "/contributors",
    response_model=Contributor,
    status_code=201,
    summary="Create contributor",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
def create_contributor(contributor: ContributorCreate) -> Contributor:
    """Register a new contributor (human or system) in the network."""
    from app.services.contributor_hygiene import is_test_contributor_email
    contrib = Contributor(**contributor.model_dump())
    if is_test_contributor_email(contrib.email):
        raise HTTPException(status_code=422, detail="Test email domains are not allowed for persistent contributors")
    node_id = f"contributor:{contrib.name}"
    existing = graph_service.get_node(node_id)
    if existing:
        raise HTTPException(status_code=422, detail=f"Contributor '{contrib.name}' already exists")
    graph_service.create_node(
        id=node_id, type="contributor", name=contrib.name,
        description=f"{contrib.type or 'HUMAN'} contributor",
        phase="water",
        properties={
            "contributor_type": contrib.type,
            "email": contrib.email,
            "wallet_address": contrib.wallet_address,
            "hourly_rate": float(contrib.hourly_rate) if contrib.hourly_rate else None,
            "legacy_id": str(contrib.id),
        },
    )
    return contrib


@router.get(
    "/contributors/{contributor_id}",
    response_model=Contributor,
    summary="Get contributor by ID",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def get_contributor(contributor_id: str) -> Contributor:
    """Retrieve a single contributor by name or UUID."""
    # Try by name first, then by UUID
    node = graph_service.get_node(f"contributor:{contributor_id}")
    if not node:
        # Search by legacy UUID
        result = graph_service.list_nodes(type="contributor", limit=500)
        for n in result.get("items", []):
            if n.get("legacy_id") == str(contributor_id) or n.get("name") == contributor_id:
                node = n
                break
    if not node:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return _node_to_contributor(node)


@router.get(
    "/contributors/{contributor_id}/spend",
    summary="Get contributor spend metrics (daily/monthly)",
    tags=["contributors"],
)
def get_contributor_spend(contributor_id: str) -> dict:
    """Return CC spent in the last 24h and last 30 days for budgeting."""
    from app.services import contribution_ledger_service
    return contribution_ledger_service.get_spend_metrics(contributor_id)


@router.get(
    "/contributors",
    response_model=PaginatedResponse[Contributor],
    summary="List contributors",
)
def list_contributors(
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> PaginatedResponse[Contributor]:
    """List contributors with pagination metadata."""
    result = graph_service.list_nodes(type="contributor", limit=limit, offset=offset)
    items = [_node_to_contributor(n) for n in result.get("items", [])]
    return PaginatedResponse(items=items, total=result.get("total", len(items)), limit=limit, offset=offset)
