"""Cross-Domain Concept Resonance router — Spec 179.

Endpoints:
  GET  /api/resonance/cross-domain
  POST /api/resonance/cross-domain/scan
  GET  /api/resonance/cross-domain/scans/{scan_id}
  GET  /api/resonance/cross-domain/proof
  GET  /api/resonance/cross-domain/{id}
  DELETE /api/resonance/cross-domain/{id}
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.cross_domain_resonance import (
    CrossDomainResonanceItem,
    CrossDomainResonanceList,
    NodeSummary,
    ProofResponse,
    ScanRequest,
    ScanResponse,
    ScanStatus,
)
from app.services import cross_domain_resonance_service as svc

router = APIRouter()


def _record_to_item(rec: dict) -> CrossDomainResonanceItem:
    """Convert a DB record dict to the API response model."""
    try:
        from app.services import graph_service
        node_a_raw = graph_service.get_node(rec["node_a_id"]) or {}
        node_b_raw = graph_service.get_node(rec["node_b_id"]) or {}
    except Exception:
        node_a_raw = {}
        node_b_raw = {}

    node_a = NodeSummary(
        id=rec["node_a_id"],
        name=node_a_raw.get("name", rec["node_a_id"]),
        domain=rec["domain_a"],
    )
    node_b = NodeSummary(
        id=rec["node_b_id"],
        name=node_b_raw.get("name", rec["node_b_id"]),
        domain=rec["domain_b"],
    )

    discovered = rec["discovered_at"]
    confirmed = rec["last_confirmed"]
    if isinstance(discovered, str):
        discovered = datetime.fromisoformat(discovered)
    if isinstance(confirmed, str):
        confirmed = datetime.fromisoformat(confirmed)

    return CrossDomainResonanceItem(
        id=rec["id"],
        node_a=node_a,
        node_b=node_b,
        domain_a=rec["domain_a"],
        domain_b=rec["domain_b"],
        resonance_score=rec["resonance_score"],
        structural_sim=rec["structural_sim"],
        depth2_sim=rec["depth2_sim"],
        crk_score=rec["crk_score"],
        edge_id=rec.get("edge_id"),
        discovered_at=discovered,
        last_confirmed=confirmed,
        scan_mode=rec["scan_mode"],
        source=rec.get("source", "cdcr"),
    )


@router.get(
    "/resonance/cross-domain",
    response_model=CrossDomainResonanceList,
    summary="List cross-domain resonances",
    tags=["resonance"],
)
async def list_resonances(
    domain_a: Optional[str] = Query(None, description="Filter by domain A"),
    domain_b: Optional[str] = Query(None, description="Filter by domain B"),
    min_score: float = Query(0.65, ge=0.0, le=1.0, description="Minimum resonance score"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List discovered cross-domain resonances, newest first."""
    result = svc.list_resonances(
        domain_a=domain_a,
        domain_b=domain_b,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )
    items = [_record_to_item(r.to_dict()) for r in result["items"]]
    return CrossDomainResonanceList(
        items=items,
        total=result["total"],
        limit=limit,
        offset=offset,
    )


@router.post(
    "/resonance/cross-domain/scan",
    response_model=ScanResponse,
    status_code=202,
    summary="Trigger a resonance scan",
    tags=["resonance"],
)
async def trigger_scan(body: ScanRequest):
    """Trigger an on-demand cross-domain resonance scan."""
    if body.mode == "seed" and not body.seed_node_id:
        raise HTTPException(status_code=400, detail="seed_node_id required for mode=seed")

    if body.mode == "seed" and body.seed_node_id:
        try:
            from app.services import graph_service
            node = graph_service.get_node(body.seed_node_id)
            if not node:
                raise HTTPException(
                    status_code=404,
                    detail=f"Node '{body.seed_node_id}' not found",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    try:
        scan = svc.trigger_scan(mode=body.mode, seed_node_id=body.seed_node_id)
    except RuntimeError:
        raise HTTPException(status_code=429, detail="Scan already in progress")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ScanResponse(
        scan_id=scan["scan_id"],
        mode=scan["mode"],
        seed_node_id=scan["seed_node_id"],
        status=scan["status"],
        message=(
            f"Scan queued. Results available at "
            f"GET /api/resonance/cross-domain/scans/{scan['scan_id']}"
        ),
    )


@router.get(
    "/resonance/cross-domain/scans/{scan_id}",
    response_model=ScanStatus,
    summary="Get scan status",
    tags=["resonance"],
)
async def get_scan_status(scan_id: str):
    """Get the status and results of a resonance scan."""
    scan = svc.get_scan_status(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan '{scan_id}' not found")
    return ScanStatus(
        scan_id=scan["scan_id"],
        status=scan["status"],
        mode=scan["mode"],
        nodes_evaluated=scan.get("nodes_evaluated", 0),
        pairs_compared=scan.get("pairs_compared", 0),
        resonances_found=scan.get("resonances_found", 0),
        resonances_created=scan.get("resonances_created", 0),
        resonances_updated=scan.get("resonances_updated", 0),
        duration_ms=scan.get("duration_ms"),
        started_at=scan.get("started_at"),
        completed_at=scan.get("completed_at"),
    )


@router.get(
    "/resonance/cross-domain/proof",
    response_model=ProofResponse,
    summary="Proof that the resonance engine is working",
    tags=["resonance"],
)
async def get_proof():
    """Aggregate evidence that the ontology is growing organically."""
    data = svc.get_proof()
    return ProofResponse(**data)


@router.get(
    "/resonance/cross-domain/{resonance_id}",
    response_model=CrossDomainResonanceItem,
    summary="Get a single resonance record",
    tags=["resonance"],
)
async def get_resonance(resonance_id: str):
    """Get a single cross-domain resonance record by ID."""
    rec = svc.get_resonance(resonance_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Resonance not found")
    return _record_to_item(rec)


@router.delete(
    "/resonance/cross-domain/{resonance_id}",
    status_code=204,
    summary="Remove a false-positive resonance",
    tags=["resonance"],
)
async def delete_resonance(resonance_id: str):
    """Remove a resonance record and its analogous-to edge (human override)."""
    deleted = svc.delete_resonance(resonance_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resonance not found")
