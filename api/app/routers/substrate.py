"""Coherence-substrate REST API.

Read-only endpoints for agent reasoning. The substrate is built by the
ingestion frontends (markdown_frontend, etc.) and consumed via these
endpoints + the Form notation parser (forthcoming).

See docs/coherence-substrate/ for usage; see api/app/services/substrate/
for the implementation.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.substrate import (
    CellView,
    NamedCell,
    NodeID,
    PathAnnotation,
    annotate_path,
    find_cells_compatible_with,
    find_equivalent_cells,
    lattice_stats,
    lookup_cell,
    lookup_node,
    view_cell_through_blueprint,
)
from app.services.substrate.kernel import DOMAIN_BLUEPRINT, DOMAIN_RECIPE
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.unified_db import session as session_scope


router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class NodeIDOut(BaseModel):
    package: int
    level: int
    type_: int = Field(alias="type")
    instance: int

    model_config = {"populate_by_name": True}

    @classmethod
    def from_node_id(cls, node_id: NodeID | None) -> "NodeIDOut | None":
        if node_id is None or node_id.is_undefined():
            return None
        return cls(
            package=node_id.package,
            level=node_id.level,
            type=node_id.type_,
            instance=node_id.instance,
        )


class CellOut(BaseModel):
    cell_id: int
    name: str
    domain: str
    blueprint: NodeIDOut
    base: NodeIDOut | None = None
    access: NodeIDOut | None = None
    ctor: NodeIDOut | None = None
    source_path: str | None = None

    @classmethod
    def from_cell(cls, cell: NamedCell) -> "CellOut":
        return cls(
            cell_id=cell.cell_id or 0,
            name=cell.name,
            domain=cell.domain,
            blueprint=NodeIDOut.from_node_id(cell.blueprint),
            base=NodeIDOut.from_node_id(cell.base),
            access=NodeIDOut.from_node_id(cell.access),
            ctor=NodeIDOut.from_node_id(cell.ctor),
            source_path=cell.source_path,
        )


class NodeOut(BaseModel):
    id: NodeIDOut
    serialized: str
    domain: str
    count: int

    @classmethod
    def from_orm(cls, orm_obj: SubstrateNodeORM) -> "NodeOut":
        return cls(
            id=NodeIDOut(
                package=orm_obj.package,
                level=orm_obj.level,
                type=orm_obj.type_,
                instance=orm_obj.instance,
            ),
            serialized=orm_obj.serialized,
            domain=orm_obj.domain,
            count=orm_obj.count or 0,
        )


class EquivalentResponse(BaseModel):
    blueprint: NodeIDOut
    cells: list[CellOut]
    count: int


class LatticeStatsOut(BaseModel):
    blueprints_total: int
    recipes_total: int
    cells_total: int


class HistogramEntry(BaseModel):
    blueprint: NodeIDOut
    count: int
    sample_names: list[str]


class HistogramOut(BaseModel):
    domain: str
    entries: list[HistogramEntry]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/lattice/stats", response_model=LatticeStatsOut, tags=["substrate"])
def get_lattice_stats() -> LatticeStatsOut:
    """Return per-domain counts (blueprints, recipes, cells)."""
    with session_scope() as session:
        s = lattice_stats(session)
        return LatticeStatsOut(**s)


@router.get("/cell/{domain}/{name:path}", response_model=CellOut, tags=["substrate"])
def get_cell(domain: str, name: str) -> CellOut:
    """Look up a cell by (domain, name)."""
    with session_scope() as session:
        cell = lookup_cell(session, domain, name)
        if cell is None:
            raise HTTPException(status_code=404, detail=f"cell ({domain}, {name}) not found")
        return CellOut.from_cell(cell)


@router.get("/node/{package}/{level}/{type_}/{instance}", response_model=NodeOut, tags=["substrate"])
def get_node(package: int, level: int, type_: int, instance: int) -> NodeOut:
    """Look up a substrate_nodes row by NodeID."""
    nid = NodeID(package, level, type_, instance)
    with session_scope() as session:
        orm = lookup_node(session, nid)
        if orm is None:
            raise HTTPException(status_code=404, detail=f"node {nid} not found")
        return NodeOut.from_orm(orm)


@router.get("/equivalent/{domain}/{name:path}", response_model=EquivalentResponse, tags=["substrate"])
def get_equivalent(domain: str, name: str) -> EquivalentResponse:
    """Find structurally-equivalent cells to (domain, name).

    Returns all cells whose Blueprint NodeID matches that of the named cell.
    Two cells with the same Blueprint NodeID are structurally identical
    regardless of name or domain.
    """
    with session_scope() as session:
        cell = lookup_cell(session, domain, name)
        if cell is None:
            raise HTTPException(status_code=404, detail=f"cell ({domain}, {name}) not found")
        equivalents = find_equivalent_cells(session, cell.blueprint, exclude_name=cell.name)
        return EquivalentResponse(
            blueprint=NodeIDOut.from_node_id(cell.blueprint),
            cells=[CellOut.from_cell(c) for c in equivalents],
            count=len(equivalents),
        )


@router.get("/cells", tags=["substrate"])
def list_cells(
    domain: str | None = Query(None, description="Filter by domain"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> dict[str, Any]:
    """List cells (optionally filtered by domain)."""
    with session_scope() as session:
        base = session.query(SubstrateNamedCellORM)
        if domain is not None:
            base = base.filter_by(domain=domain)
        total = base.count()
        rows = base.offset(offset).limit(limit).all()
        from app.services.substrate.kernel import _orm_to_cell  # internal helper
        items = [CellOut.from_cell(_orm_to_cell(session, r)) for r in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}


class PathAnnotationOut(BaseModel):
    path: str
    cell: CellOut | None = None
    blueprint: NodeIDOut | None = None
    domain: str | None = None
    equivalents: list[CellOut] = Field(default_factory=list)
    equivalents_count: int = 0
    in_substrate: bool


@router.get("/annotate", response_model=PathAnnotationOut, tags=["substrate"])
def get_annotation(path: str = Query(..., description="File path to annotate")) -> PathAnnotationOut:
    """Return substrate context for a file path.

    The agent-grounding endpoint: when an agent reads a file and wants to
    know what cell that path is in the substrate (NodeID, Blueprint shape,
    structural equivalents), it calls this. Returns in_substrate=False
    when the path isn't ingested.

    See docs/coherence-substrate/agents-using-substrate.md "Pattern 5:
    Auto-annotation on file reads" for usage.
    """
    with session_scope() as session:
        ann = annotate_path(session, path)
        return PathAnnotationOut(
            path=ann.path,
            cell=CellOut.from_cell(ann.cell) if ann.cell else None,
            blueprint=NodeIDOut.from_node_id(ann.blueprint) if ann.blueprint else None,
            domain=ann.domain,
            equivalents=[CellOut.from_cell(c) for c in ann.equivalents],
            equivalents_count=len(ann.equivalents),
            in_substrate=ann.cell is not None,
        )


class CellViewOut(BaseModel):
    cell: CellOut
    view_blueprint: NodeIDOut
    compatible: bool
    reason: str | None = None


@router.get("/view/{cell_domain}/{cell_name:path}", response_model=CellViewOut, tags=["substrate"])
def get_view(
    cell_domain: str,
    cell_name: str,
    blueprint_package: int = Query(..., alias="bp_package"),
    blueprint_level: int = Query(..., alias="bp_level"),
    blueprint_type: int = Query(..., alias="bp_type"),
    blueprint_instance: int = Query(..., alias="bp_instance"),
) -> CellViewOut:
    """Project a cell through a different Blueprint than its base.

    BML-style detached interface: the cell's data stays canonical; this
    endpoint returns a CellView that pairs the cell with a chosen view
    Blueprint, plus a compatibility flag indicating whether the projection
    is structurally sound.

    The substrate already has the dual-pointer shape implicitly in
    NamedCell{access Recipe, base Blueprint}. This endpoint exposes the
    Views explicitly so agents can reason about "this cell viewed as X"
    without committing the projection.
    """
    view_bp = NodeID(
        blueprint_package, blueprint_level, blueprint_type, blueprint_instance
    )
    with session_scope() as session:
        cell = lookup_cell(session, cell_domain, cell_name)
        if cell is None:
            raise HTTPException(
                status_code=404, detail=f"cell ({cell_domain}, {cell_name}) not found"
            )
        view = view_cell_through_blueprint(session, cell, view_bp)
        return CellViewOut(
            cell=CellOut.from_cell(view.cell),
            view_blueprint=NodeIDOut.from_node_id(view.view_blueprint),
            compatible=view.compatible,
            reason=view.reason,
        )


@router.get("/compatible_with/{package}/{level}/{type_}/{instance}", tags=["substrate"])
def get_compatible_cells(
    package: int,
    level: int,
    type_: int,
    instance: int,
    domain: str | None = Query(None),
) -> list[CellViewOut]:
    """Find all cells that can be viewed through this Blueprint.

    BML detached-interface query: given an interface (Blueprint), what
    cells in the body can be projected through it? Returns the set of
    compatible CellViews.
    """
    view_bp = NodeID(package, level, type_, instance)
    with session_scope() as session:
        views = find_cells_compatible_with(session, view_bp, domain=domain)
        return [
            CellViewOut(
                cell=CellOut.from_cell(v.cell),
                view_blueprint=NodeIDOut.from_node_id(v.view_blueprint),
                compatible=v.compatible,
                reason=v.reason,
            )
            for v in views
        ]


@router.get("/histogram/{domain}", response_model=HistogramOut, tags=["substrate"])
def get_histogram(domain: str) -> HistogramOut:
    """Vocabulary distribution for a domain — group cells by Blueprint NodeID.

    Returns: for this domain, how many cells share each Blueprint, with up to
    3 sample names per blueprint. The killer query: agents reasoning about
    "what shapes exist in this domain" call this and reason from the result.
    """
    with session_scope() as session:
        rows = (
            session.query(SubstrateNamedCellORM)
            .filter_by(domain=domain)
            .all()
        )
        by_blueprint: dict[int, dict[str, Any]] = {}
        for r in rows:
            bp_id = r.blueprint_node_id
            if bp_id not in by_blueprint:
                bp_orm = (
                    session.query(SubstrateNodeORM).filter_by(node_id=bp_id).one_or_none()
                )
                if bp_orm is None:
                    continue
                by_blueprint[bp_id] = {
                    "blueprint": NodeIDOut(
                        package=bp_orm.package,
                        level=bp_orm.level,
                        type=bp_orm.type_,
                        instance=bp_orm.instance,
                    ),
                    "count": 0,
                    "sample_names": [],
                }
            by_blueprint[bp_id]["count"] += 1
            if len(by_blueprint[bp_id]["sample_names"]) < 3:
                by_blueprint[bp_id]["sample_names"].append(r.name)

        entries = [HistogramEntry(**v) for v in by_blueprint.values()]
        entries.sort(key=lambda e: e.count, reverse=True)
        return HistogramOut(domain=domain, entries=entries)
