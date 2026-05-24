"""Assets router — backed by graph_nodes (type=asset)."""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from decimal import Decimal
from typing import Any

log = logging.getLogger(__name__)

# Stable namespace for deriving asset UUIDs from slug-shaped graph
# node ids. Resolver-minted and KB-seeded asset nodes carry slug ids
# like `asset:emc2-music-festival-2026-...`. Without a deterministic
# mapping, every list call would uuid4() a fresh id per node and
# every link from list -> detail would 404 on the next request.
# uuid5(ASSET_NS, node_id) gives the same node the same UUID forever;
# the detail endpoint re-derives it from each node id and walks until
# it matches.
ASSET_NS = uuid5(NAMESPACE_URL, "coherencycoin.com/asset")


def _stable_asset_id(node: dict) -> UUID:
    """Resolve a node to its stable asset UUID.

    Order of trust:
      1. The portion of `node["id"]` after the `asset:` prefix, if it
         parses as a UUID — covers nodes whose graph id is already
         `asset:<uuid>`.
      2. uuid5 derived from the full node id — deterministic, so the
         same slug always returns the same UUID.
    """
    raw = str(node.get("id", "")).removeprefix("asset:")
    try:
        return UUID(raw)
    except (ValueError, AttributeError):
        return uuid5(ASSET_NS, str(node.get("id", "")))

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from app.models.asset import (
    Asset,
    AssetCreate,
    AssetRegistration,
    AssetRegistrationCreate,
    ConceptTag,
)
from app.models.error import ErrorDetail
from app.models.pagination import PaginatedResponse
from app.services import (
    graph_service,
    ip_registration_service,
    permanent_storage_service,
    read_tracking_service,
)
from app.services.locale_projection import project, project_many, resolve_caller_lang
from app.services.story_protocol_bridge import (
    build_x402_payment_required_headers,
    compute_content_hash,
    verify_content_integrity,
)

router = APIRouter()


def _node_to_registration(node: dict) -> AssetRegistration:
    """Convert a graph node carrying MIME-aware asset properties to
    an AssetRegistration model."""
    props = node
    concept_tags_raw = props.get("concept_tags", []) or []
    concept_tags = [
        ConceptTag(concept_id=t.get("concept_id"), weight=float(t.get("weight", 0)))
        for t in concept_tags_raw
    ]
    creation_cost = Decimal(str(props.get("creation_cost_cc", "0")))
    created_at_raw = props.get("created_at")
    if isinstance(created_at_raw, str):
        try:
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
        except ValueError:
            created_at = datetime.now(timezone.utc)
    elif isinstance(created_at_raw, datetime):
        created_at = created_at_raw
    else:
        created_at = datetime.now(timezone.utc)

    return AssetRegistration(
        id=node["id"],
        type=props.get("mime_type") or props.get("asset_type", ""),
        name=props.get("name", ""),
        description=props.get("description", ""),
        content_hash=props.get("content_hash", ""),
        arweave_tx=props.get("arweave_tx"),
        ipfs_cid=props.get("ipfs_cid"),
        concept_tags=concept_tags,
        creator_id=props.get("creator_id", ""),
        creation_cost_cc=creation_cost,
        metadata=props.get("metadata", {}) or {},
        created_at=created_at,
        sp_ip_id=props.get("sp_ip_id"),
        ip_status=props.get("ip_status", "pending"),
        ip_reason=props.get("ip_reason"),
    )


def _node_to_asset(node: dict) -> Asset:
    """Convert a graph node to an Asset model.

    ``image_url`` lands on remote-resolved nodes (inspired-by minted
    content with og:image), ``file_path`` lands on locally-generated
    KB visuals served from /visuals/...; either one is enough to give
    the listing card a real thumbnail.

    Rich fields (name, canonical_url, creator_id, asin, slug, era,
    mime_type, content_hash, ipfs_cid, arweave_tx, etc.) are passed
    through unchanged when present on the node, so detail surfaces
    can render a title, an external source link, and the structured-
    data context that makes the surface trustworthy without a second
    round-trip to /api/graph/nodes."""
    image_url = node.get("image_url") or None
    file_path = node.get("file_path") or None

    def _str(key: str) -> str | None:
        value = node.get(key)
        return value if isinstance(value, str) and value else None

    def _int(key: str) -> int | None:
        value = node.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    return Asset(
        id=_stable_asset_id(node),
        type=node.get("asset_type", "CODE"),
        description=node.get("description", node.get("name", "")),
        total_cost=Decimal(str(node.get("total_cost", "0"))),
        image_url=image_url if isinstance(image_url, str) else None,
        file_path=file_path if isinstance(file_path, str) else None,
        node_id=_str("id"),
        name=_str("name"),
        canonical_url=_str("canonical_url"),
        slug=_str("slug"),
        creator_id=_str("creator_id"),
        creation_kind=_str("creation_kind"),
        asset_type=_str("asset_type"),
        mime_type=_str("mime_type"),
        content_hash=_str("content_hash"),
        ipfs_cid=_str("ipfs_cid"),
        arweave_tx=_str("arweave_tx"),
        asin=_str("asin"),
        isbn=_str("isbn"),
        runtime_length_min=_int("runtime_length_min"),
        era=_str("era"),
        company=_str("company"),
        title=_str("title"),
        location=_str("location"),
        substrate=_str("substrate"),
        when=_str("when"),
        language=_str("language"),
    )


@router.post(
    "/assets",
    response_model=Asset,
    status_code=201,
    summary="Create asset",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
async def create_asset(asset: AssetCreate) -> Asset:
    """Register a new tracked asset (code, docs, endpoint, etc.)."""
    asset_obj = Asset(**asset.model_dump())
    node_id = f"asset:{asset_obj.id}"
    graph_service.create_node(
        id=node_id, type="asset", name=(asset_obj.description or "")[:80],
        description=asset_obj.description or "",
        phase="ice",
        properties={
            "asset_type": asset_obj.type,
            "total_cost": str(asset_obj.total_cost),
        },
    )
    return asset_obj


def _content_bytes_from_metadata(metadata: dict | None) -> bytes | None:
    """Pull raw content bytes out of the registration metadata payload.

    The MIME-aware register flow accepts ``content_base64`` (preferred,
    for arbitrary bytes) or ``content`` (UTF-8 text shortcut). Returns
    None when neither is present — the asset is still created, the
    storage upload step just becomes a no-op.
    """
    if not isinstance(metadata, dict):
        return None
    b64 = metadata.get("content_base64")
    if isinstance(b64, str) and b64:
        try:
            return base64.b64decode(b64)
        except (ValueError, base64.binascii.Error) as e:
            log.warning("content_base64 decode failed: %s", e)
            return None
    text = metadata.get("content")
    if isinstance(text, str) and text:
        return text.encode("utf-8")
    return None


@router.post(
    "/assets/register",
    response_model=AssetRegistration,
    status_code=201,
    summary="Register a MIME-typed asset with content provenance",
    responses={422: {"model": ErrorDetail, "description": "Validation error"}},
)
async def register_asset(body: AssetRegistrationCreate) -> AssetRegistration:
    """Register an asset with full MIME type, content hash, storage
    references, concept tags, and format-specific metadata.

    Extends the legacy POST /api/assets — the legacy endpoint still
    accepts CODE/MODEL/CONTENT/DATA taxonomy for pipeline contributions.
    This endpoint supports arbitrary MIME types so a renderer can pair
    with the asset by type. See specs/asset-renderer-plugin.md R1.

    Per specs/story-protocol-integration.md R1, registration auto-fires
    three downstream services after the asset node lands:

      1. ``ip_registration_service.register_ip_asset`` — mints the
         Story Protocol IP Asset id, surfaces as ``sp_ip_id``.
      2. ``permanent_storage_service.upload_to_arweave`` — uploads
         raw bytes (from ``metadata.content_base64`` or
         ``metadata.content``), surfaces as ``arweave_tx``.
      3. ``permanent_storage_service.upload_to_ipfs`` — same bytes,
         surfaces as ``ipfs_cid``.

    Failures in any subcall are isolated: the asset is still created
    and usable. Failed IP registration → ``ip_status="failed"`` with
    ``ip_reason`` set, ``sp_ip_id=None``. Failed storage → the
    corresponding ref stays None. R1: "If registration fails, ip_status
    is failed and the asset remains usable without IP registration."

    **Sync now, async later.** The three subcalls run synchronously in
    this iteration — the services are fast in-memory mocks and adding
    a background queue would be ornament before the partner SDKs land.
    When the real Story Protocol SDK + Irys/Bundlr arrive, the
    expensive network calls move to a background worker (Celery, ARQ,
    or FastAPI BackgroundTasks) and the handler returns immediately
    with ``ip_status="pending"``.
    """
    registration_id = f"asset:{uuid4()}"
    asset_uuid = registration_id.removeprefix("asset:")
    now = datetime.now(timezone.utc)
    concept_tags_serializable = [
        {"concept_id": t.concept_id, "weight": t.weight}
        for t in body.concept_tags
    ]

    # Step 1 — create the graph node. Any later subcall failure leaves
    # this in place so the asset is recoverable.
    graph_service.create_node(
        id=registration_id,
        type="asset",
        name=body.name,
        description=body.description,
        phase="ice",
        properties={
            "mime_type": body.type,
            "name": body.name,
            "content_hash": body.content_hash,
            "arweave_tx": body.arweave_tx,
            "ipfs_cid": body.ipfs_cid,
            "concept_tags": concept_tags_serializable,
            "creator_id": body.creator_id,
            "creation_cost_cc": str(body.creation_cost_cc),
            "metadata": body.metadata,
            "created_at": now.isoformat(),
        },
    )

    # Step 2 — auto-fire IP registration. Isolated from the asset
    # creation so a failed registration still leaves the asset usable.
    sp_ip_id: str | None = None
    ip_status = "pending"
    ip_reason: str | None = None
    try:
        ip_record = ip_registration_service.register_ip_asset(
            asset_uuid,
            {"type": body.type, "name": body.name},
        )
        sp_ip_id = ip_record.get("sp_ip_id")
        ip_status = ip_record.get("ip_status", "pending")
        ip_reason = ip_record.get("reason")
    except Exception as e:  # don't fail registration on IP failure (R1)
        log.warning(
            "auto-fire IP registration failed for %s: %s", registration_id, e
        )
        ip_status = "failed"
        ip_reason = str(e)

    # Step 3 — auto-fire permanent storage uploads. Isolated per surface
    # so a failure on one (Arweave) doesn't block the other (IPFS).
    arweave_tx_id: str | None = body.arweave_tx
    ipfs_cid: str | None = body.ipfs_cid
    content_bytes = _content_bytes_from_metadata(body.metadata)
    if content_bytes is not None:
        try:
            arweave = permanent_storage_service.upload_to_arweave(
                content_bytes,
                {"name": body.name, "type": body.type},
                asset_id=asset_uuid,
            )
            arweave_tx_id = arweave.get("arweave_tx_id") or arweave_tx_id
        except Exception as e:
            log.warning(
                "auto-fire Arweave upload failed for %s: %s", registration_id, e
            )
        try:
            ipfs = permanent_storage_service.upload_to_ipfs(
                content_bytes, asset_id=asset_uuid
            )
            ipfs_cid = ipfs.get("ipfs_cid") or ipfs_cid
        except Exception as e:
            log.warning(
                "auto-fire IPFS upload failed for %s: %s", registration_id, e
            )

    # Step 4 — patch the auto-fire results onto the node so downstream
    # endpoints (content delivery, verification) surface them.
    patch: dict[str, Any] = {
        "sp_ip_id": sp_ip_id,
        "ip_status": ip_status,
        "ip_reason": ip_reason,
        "arweave_tx": arweave_tx_id,
        "ipfs_cid": ipfs_cid,
    }
    try:
        graph_service.update_node(registration_id, properties=patch)
    except Exception as e:
        log.warning(
            "failed to patch auto-fire results onto %s: %s", registration_id, e
        )

    return AssetRegistration(
        id=registration_id,
        type=body.type,
        name=body.name,
        description=body.description,
        content_hash=body.content_hash,
        arweave_tx=arweave_tx_id,
        ipfs_cid=ipfs_cid,
        concept_tags=body.concept_tags,
        creator_id=body.creator_id,
        creation_cost_cc=body.creation_cost_cc,
        metadata=body.metadata,
        created_at=now,
        sp_ip_id=sp_ip_id,
        ip_status=ip_status,
        ip_reason=ip_reason,
    )


@router.get(
    "/assets/{asset_id}/registration",
    response_model=AssetRegistration,
    summary="Get MIME-aware asset registration",
    responses={404: {"model": ErrorDetail, "description": "Asset registration not found"}},
)
async def get_asset_registration(asset_id: str) -> AssetRegistration:
    """Retrieve full registration (MIME type, concept tags, provenance, metadata)
    for an asset registered via POST /api/assets/register.
    """
    node_id = asset_id if asset_id.startswith("asset:") else f"asset:{asset_id}"
    node = graph_service.get_node(node_id)
    if not node or not node.get("mime_type"):
        raise HTTPException(status_code=404, detail="Asset registration not found")
    return _node_to_registration(node)


@router.get(
    "/assets/{asset_id}",
    response_model=Asset,
    summary="Get asset by ID",
    responses={404: {"model": ErrorDetail, "description": "Asset not found"}},
)
async def get_asset(
    asset_id: UUID,
    request: Request,
    lang: str | None = Query(None, description="Target language. Description renders in this locale when a view exists."),
) -> Asset:
    """Retrieve a single asset by its unique identifier.

    The lookup mirrors `_stable_asset_id`:
      1. Direct hit on `asset:<uuid>` — for nodes whose graph id is
         already `asset:<uuid>`.
      2. Walk all asset nodes and match the deterministic
         `_stable_asset_id(node)` — covers slug-shaped nodes minted
         by the resolver / KB seed.
    """
    node = graph_service.get_node(f"asset:{asset_id}")
    if not node:
        result = graph_service.list_nodes(type="asset", limit=1000)
        for n in result.get("items", []):
            if _stable_asset_id(n) == asset_id:
                node = n
                break
    if not node:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset = _node_to_asset(node)
    target_lang = resolve_caller_lang(request, lang)
    project(asset, "asset", str(asset.id), target_lang, title_field="description", body_field="description")
    return asset


@router.get(
    "/assets",
    response_model=PaginatedResponse[Asset],
    summary="List assets",
)
async def list_assets(
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    lang: str | None = Query(None, description="Target language for descriptions."),
) -> PaginatedResponse[Asset]:
    """List all tracked assets with pagination metadata."""
    result = graph_service.list_nodes(type="asset", limit=limit, offset=offset)
    items = [_node_to_asset(n) for n in result.get("items", [])]
    target_lang = resolve_caller_lang(request, lang)
    if target_lang and target_lang != "en":
        for item in items:
            project(item, "asset", str(item.id), target_lang, title_field="description", body_field="description")
    return PaginatedResponse(items=items, total=result.get("total", len(items)), limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Content delivery + x402 (spec R4)
# ---------------------------------------------------------------------------

# Default micropayment amount per content read. The cc-economics service
# will calibrate this once usage data arrives; today the value is the
# placeholder named in specs/story-protocol-integration.md API contract.
DEFAULT_CONTENT_CC_AMOUNT = Decimal("0.01")
DEFAULT_PAYMENT_NETWORK = "coherence-cc"
# Free-tier text truncation point — keeps the preview useful (a paragraph
# or so) without giving away the body. Image assets emit a watermark
# label rather than truncating bytes.
FREE_TIER_TEXT_PREVIEW_CHARS = 280


def _find_asset_node(asset_id: UUID) -> dict | None:
    """Lookup mirroring ``get_asset`` — direct hit on ``asset:<uuid>``
    then walk all asset nodes matching ``_stable_asset_id``. Returns
    None if no node resolves to this UUID."""
    node = graph_service.get_node(f"asset:{asset_id}")
    if node:
        return node
    result = graph_service.list_nodes(type="asset", limit=1000)
    for n in result.get("items", []):
        if _stable_asset_id(n) == asset_id:
            return n
    return None


def _extract_content_bytes(node: dict) -> tuple[bytes, str]:
    """Resolve the raw content for an asset node, plus the MIME type.

    Search order:
      1. ``metadata.content_base64`` — set by the upload flow when the
         caller hands us the bytes directly.
      2. ``metadata.content`` — text content stored as a plain string.
      3. ``description`` — fallback so even bare-metadata nodes (the
         resolver-minted ones from KB seeds) have *some* content to
         serve. The hash on the node will not match this fallback;
         the verification endpoint will surface that honestly.

    MIME defaults to ``text/plain`` and is overridden by
    ``mime_type`` on the node if present.
    """
    metadata = node.get("metadata") or {}
    mime_type = node.get("mime_type") or "text/plain"

    b64 = metadata.get("content_base64")
    if isinstance(b64, str) and b64:
        try:
            return base64.b64decode(b64), mime_type
        except (ValueError, base64.binascii.Error):
            pass

    text = metadata.get("content")
    if isinstance(text, str) and text:
        return text.encode("utf-8"), mime_type

    description = node.get("description") or ""
    return description.encode("utf-8"), mime_type


def _is_image_mime(mime_type: str) -> bool:
    return mime_type.lower().startswith("image/")


def _free_tier_content(content: bytes, mime_type: str) -> str:
    """Free-tier rendering. Images return a watermark label, text
    returns a truncation. Binary types collapse to a short notice so
    we never serve undefined bytes."""
    if _is_image_mime(mime_type):
        return f"[free-tier preview: watermarked {mime_type}]"
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return f"[free-tier preview: {len(content)}-byte {mime_type}]"
    if len(text) <= FREE_TIER_TEXT_PREVIEW_CHARS:
        return text
    return text[:FREE_TIER_TEXT_PREVIEW_CHARS] + "…"


def _extract_bearer_token(authorization: str | None) -> str | None:
    """Pull the raw token out of an ``Authorization: Bearer <token>``
    header. Returns ``None`` when the header is absent or malformed.
    Paid reads are exactly the ones where this returns a non-empty
    token; the first-iteration x402 contract is presence of a Bearer
    token, with real facilitator verification landing in a follow-up."""
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def _resolve_reader_id(
    request: Request, payment_token: str | None
) -> str | None:
    """Determine the reader id for the read event.

    Order of trust:
      1. Explicit ``X-Reader-Id`` header — set by clients that already
         know who their user is.
      2. Synthetic ``paid:<token-prefix>`` for paid reads — the real
         x402 facilitator integration will replace this with the
         token's subject claim once the verification path lands.
      3. ``None`` — anonymous free reads have no reader.
    """
    explicit = request.headers.get("X-Reader-Id")
    if explicit:
        return explicit
    if payment_token:
        return f"paid:{payment_token[:8]}"
    return None


def _parse_concept_resonance(raw: str | None) -> dict[str, float] | None:
    """Parse the ``X-Concept-Resonance`` header into a snapshot dict.

    The header carries a JSON object of ``{concept_id: weight}``. Any
    non-numeric weight is skipped — record_read accepts ``None`` if the
    whole payload is unparseable so the read path stays non-blocking."""
    if not raw:
        return None
    import json
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    snapshot: dict[str, float] = {}
    for k, v in parsed.items():
        try:
            snapshot[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return snapshot or None


def _payment_address(node: dict) -> str:
    """Resolve the asset's payment address. Prefers an explicit
    ``payment_address`` on the node; falls back to a ``coherence:contributor:<creator_id>``
    form for nodes that only know who made them."""
    explicit = node.get("payment_address")
    if isinstance(explicit, str) and explicit:
        return explicit
    creator_id = node.get("creator_id")
    if isinstance(creator_id, str) and creator_id:
        return f"coherence:contributor:{creator_id}"
    return "coherence:contributor:unknown"


@router.get(
    "/assets/{asset_id}/content",
    summary="Get asset content with x402 payment headers",
    responses={
        402: {"description": "Payment required — content gated"},
        404: {"model": ErrorDetail, "description": "Asset not found"},
    },
)
async def get_asset_content(
    asset_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    """Serve asset content with x402 payment headers (spec R4).

    Three flows:
      - **Paid** — valid Bearer token in ``Authorization``: full content,
        ``read_type="paid"``, ``cc_charged`` set, all four
        ``X-Payment-*`` headers present.
      - **Free tier** — no token, asset has ``free_tier_enabled``: a
        truncated/watermarked preview is served at 200 with the same
        payment headers (informational, so the reader knows the price
        of the upgrade). ``read_type="free"``.
      - **Payment required** — no token, asset has
        ``requires_payment=True`` and free tier is disabled: 402 with
        the payment headers as the price quote. No read recorded.

    Every served read (paid or free) calls
    ``read_tracking_service.record_read`` so settlement aggregations
    later see the event per spec R5.
    """
    node = _find_asset_node(asset_id)
    if not node:
        raise HTTPException(status_code=404, detail="Asset not found")

    requires_payment = bool(node.get("requires_payment", False))
    free_tier_enabled = bool(node.get("free_tier_enabled", True))
    cc_amount = Decimal(str(node.get("cc_amount") or DEFAULT_CONTENT_CC_AMOUNT))
    payment_address = _payment_address(node)
    network = node.get("payment_network") or DEFAULT_PAYMENT_NETWORK

    payment_headers = build_x402_payment_required_headers(
        amount_cc=cc_amount,
        payment_address=payment_address,
        network=network,
    )

    content_bytes, mime_type = _extract_content_bytes(node)
    asset_id_str = str(asset_id)
    node_id = node.get("id") or f"asset:{asset_id}"

    # Read-event metadata — extract once, forward to record_read in both
    # the paid and the free branch so get_daily_aggregates partitions
    # correctly between paid_reads and free_reads.
    payment_token = _extract_bearer_token(authorization)
    is_paid = payment_token is not None
    read_type = "paid" if is_paid else "free"
    reader_id = _resolve_reader_id(request, payment_token)
    concept_resonance_snapshot = _parse_concept_resonance(
        request.headers.get("X-Concept-Resonance")
    )
    # Paid reads carry the asset's cc_amount; free reads carry zero so
    # the settlement layer doesn't credit the creator for a preview.
    event_cc_amount = float(cc_amount) if is_paid else 0.0

    if is_paid:
        try:
            # Forward read_type + cc_amount + payment token so the read
            # event carries the paid-tier CC. The render-event bridge in
            # record_read uses cc_amount as the settlement pool.
            read_tracking_service.record_read(
                asset_id=node_id,
                reader_id=reader_id,
                read_type=read_type,
                payment_token=payment_token,
                cc_amount=event_cc_amount,
                concept_resonance_snapshot=concept_resonance_snapshot,
            )
        except Exception as e:  # non-blocking — read tracking failure mustn't fail delivery
            log.warning("record_read failed for %s: %s", node_id, e)
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = base64.b64encode(content_bytes).decode("ascii")
        body = {
            "asset_id": asset_id_str,
            "content_type": mime_type,
            "content": content,
            "tier": "paid",
            "cc_charged": str(cc_amount),
            "read_type": "paid",
        }
        return JSONResponse(content=body, status_code=200, headers=payment_headers)

    if requires_payment and not free_tier_enabled:
        # 402 — content is gated, no token, no free tier.
        body = {
            "asset_id": asset_id_str,
            "error": "payment_required",
            "payment_info": {
                "amount_cc": str(cc_amount),
                "address": payment_address,
                "network": network,
            },
        }
        return JSONResponse(content=body, status_code=402, headers=payment_headers)

    # Free tier — preview served, read recorded as "free" (cc_amount=0).
    try:
        read_tracking_service.record_read(
            asset_id=node_id,
            reader_id=reader_id,
            read_type=read_type,
            payment_token=payment_token,
            cc_amount=event_cc_amount,
            concept_resonance_snapshot=concept_resonance_snapshot,
        )
    except Exception as e:
        log.warning("record_read failed for %s: %s", node_id, e)
    preview = _free_tier_content(content_bytes, mime_type)
    body = {
        "asset_id": asset_id_str,
        "content_type": mime_type,
        "content": preview,
        "tier": "free",
        "read_type": "free",
        "full_content_available": True,
        "payment_info": {
            "amount_cc": str(cc_amount),
            "address": payment_address,
            "network": network,
        },
    }
    return JSONResponse(content=body, status_code=200, headers=payment_headers)


# ---------------------------------------------------------------------------
# Content verification (spec R10)
# ---------------------------------------------------------------------------


@router.get(
    "/assets/{asset_id}/verification",
    summary="Verify asset content integrity against stored hash",
    responses={404: {"model": ErrorDetail, "description": "Asset not found"}},
)
async def get_asset_verification(asset_id: UUID) -> dict:
    """Return content-hash + storage refs + recomputed hash (spec R10).

    Recomputes the SHA-256 of the currently-stored content and compares
    against the node's ``content_hash``. ``integrity`` is
    ``"verified"`` when they match, ``"failed"`` when they don't, and
    ``"no_hash"`` when the node has no stored hash to compare against.

    The recompute runs locally against the content we already serve —
    the Arweave/IPFS fetch half of the integrity check lives in
    ``permanent_storage_service.verify_content_integrity`` and is
    gated on the partner-storage bring-up. The Arweave TX and IPFS CID
    are surfaced here as references regardless.
    """
    node = _find_asset_node(asset_id)
    if not node:
        raise HTTPException(status_code=404, detail="Asset not found")

    expected_hash = node.get("content_hash") or ""
    content_bytes, _ = _extract_content_bytes(node)
    recomputed_hash = compute_content_hash(content_bytes)

    if not expected_hash:
        integrity = "no_hash"
    else:
        result = verify_content_integrity(expected_hash, content_bytes)
        integrity = "verified" if result.ok else "failed"

    arweave_tx = node.get("arweave_tx") or node.get("arweave_tx_id")
    ipfs_cid = node.get("ipfs_cid")
    sp_ip_id = node.get("sp_ip_id")

    return {
        "asset_id": str(asset_id),
        "content_hash": expected_hash or None,
        "recomputed_hash": recomputed_hash,
        "integrity": integrity,
        "arweave_tx_id": arweave_tx,
        "arweave_url": f"https://arweave.net/{arweave_tx}" if arweave_tx else None,
        "ipfs_cid": ipfs_cid,
        "ipfs_url": f"https://ipfs.io/ipfs/{ipfs_cid}" if ipfs_cid else None,
        "sp_ip_id": sp_ip_id,
        "sp_explorer_url": (
            f"https://explorer.story.foundation/ip/{sp_ip_id}" if sp_ip_id else None
        ),
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
