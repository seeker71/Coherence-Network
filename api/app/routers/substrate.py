"""Coherence-substrate REST API.

Read endpoints for agent reasoning + one write endpoint (POST /ingest)
so a visiting body can place markdown content into the lattice without
a repo clone. The substrate is also built by the ingestion frontends
(markdown_frontend, etc.) running on disk content; the consumed surfaces
include these endpoints + the Form notation parser (POST /form).

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
    annotate_path,
    find_cells_compatible_with,
    find_equivalent_cells,
    form_evaluate_text,
    form_execute_text,
    form_stream_emit,
    ingest_markdown_text,
    lattice_stats,
    lookup_cell,
    lookup_node,
    view_cell_through_blueprint,
)
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


# ---------------------------------------------------------------------------
# Shape-health — does each cell's CTOR carry structured composition or
# flat type-markers? Catches silent flatten regressions where aggregate
# counts look stable while cell CTORs point at flat encodings.
# ---------------------------------------------------------------------------


class DomainShapeOut(BaseModel):
    total: int
    structured: int
    flat: int
    no_ctor: int
    ratio: float  # structured / (structured + flat), 0..1


class ShapeHealthOut(BaseModel):
    overall: DomainShapeOut
    domains: dict[str, DomainShapeOut]
    flags: list[str]


# A CTOR's serialized representation looks like
#   "1.2.9.1+<child>+<child>+..."
# where each `<child>` is a NodeID in `package.level.type.instance` form.
# Structured CTORs have children at composite level (level >= 3, e.g.
# `1.3.X.Y`) — each child is itself a composed (key, value) recipe.
# Flat CTORs have children at trivial level (`1.1.X.Y`, level == 1) —
# each child is a leaf recipe carrying a type-marker string.
#
# The discriminator: a CTOR is structured iff at least one direct child
# is at level >= 2 (i.e. carries internal composition); flat iff every
# direct child is at level 1 (trivial leaves only).


@router.get("/shape_health", response_model=ShapeHealthOut, tags=["substrate"])
def get_shape_health() -> ShapeHealthOut:
    """Sense whether cells carry composed CTORs or flat type-markers.

    The structural-composition discipline (CLAUDE.md → "Structural
    composition discipline") promises every cell's CTOR is a tree of
    R_Block.LET (key, value) pairs all the way down. The earlier flat
    encoder produced CTORs whose children were trivial-string recipes
    holding type-marker strings like "name=str".

    Both shapes hash to NodeIDs that look superficially similar; the
    lattice/stats endpoint reports the same recipe count whether cells
    point at structured or flat CTORs. This endpoint distinguishes them
    by examining each CTOR's direct children: a `+1.2.9.3` token in the
    serialized representation means R_Block.LET is present (structured);
    children that are only `+1.1.5.*` (trivial strings) mean flat.

    Flags raised when ratio < 0.95 (5%+ of cells carry flat CTORs) so
    the wellness check surfaces silent flatten regressions before they
    compound.
    """
    with session_scope() as session:
        cells = session.query(SubstrateNamedCellORM).all()

        # Pre-fetch all CTOR node serialized strings in one batch.
        ctor_ids = {c.ctor_recipe_node_id for c in cells if c.ctor_recipe_node_id}
        ctor_nodes = (
            session.query(SubstrateNodeORM)
            .filter(SubstrateNodeORM.node_id.in_(ctor_ids))
            .all()
        ) if ctor_ids else []
        ctor_serialized: dict[int, str] = {n.node_id: n.serialized for n in ctor_nodes}

        def _classify(node_id: int | None) -> str:
            if not node_id:
                return "no_ctor"
            serialized = ctor_serialized.get(node_id, "")
            # Parse "category+child+child+..." into child NodeIDs and
            # read each child's level (second integer in p.l.t.i form).
            parts = serialized.split("+")
            if len(parts) <= 1:
                return "no_ctor"
            child_levels: list[int] = []
            for child in parts[1:]:
                segments = child.split(".")
                if len(segments) >= 2:
                    try:
                        child_levels.append(int(segments[1]))
                    except ValueError:
                        continue
            if not child_levels:
                return "no_ctor"
            # Structured iff any direct child has level >= 2 (i.e. is itself
            # a composed recipe). Flat iff every child is at level 1.
            return "structured" if any(lv >= 2 for lv in child_levels) else "flat"

        by_domain: dict[str, dict[str, int]] = {}
        overall_counts = {"structured": 0, "flat": 0, "no_ctor": 0, "total": 0}
        for cell in cells:
            kind = _classify(cell.ctor_recipe_node_id)
            bucket = by_domain.setdefault(
                cell.domain, {"structured": 0, "flat": 0, "no_ctor": 0, "total": 0}
            )
            bucket[kind] += 1
            bucket["total"] += 1
            overall_counts[kind] += 1
            overall_counts["total"] += 1

        def _to_out(counts: dict[str, int]) -> DomainShapeOut:
            denom = counts["structured"] + counts["flat"]
            ratio = (counts["structured"] / denom) if denom > 0 else 1.0
            return DomainShapeOut(
                total=counts["total"],
                structured=counts["structured"],
                flat=counts["flat"],
                no_ctor=counts["no_ctor"],
                ratio=round(ratio, 4),
            )

        domains = {d: _to_out(c) for d, c in by_domain.items()}
        overall = _to_out(overall_counts)

        flags: list[str] = []
        if overall.ratio < 0.95 and overall.flat > 0:
            flags.append(
                f"overall structured ratio {overall.ratio:.0%} — "
                f"{overall.flat} of {overall.flat + overall.structured} "
                f"cells carry flat CTORs; re-ingest with --structured"
            )
        for name, shape in domains.items():
            if shape.ratio < 0.95 and shape.flat > 0:
                flags.append(
                    f"{name}: structured ratio {shape.ratio:.0%} — "
                    f"{shape.flat} flat cells "
                    f"(of {shape.flat + shape.structured})"
                )

        return ShapeHealthOut(overall=overall, domains=domains, flags=flags)


# ---------------------------------------------------------------------------
# Form-language evaluation — the substrate-native query DSL
# ---------------------------------------------------------------------------


class FormRequest(BaseModel):
    expression: str = Field(
        ...,
        min_length=1,
        description=(
            "Form-notation expression. Examples: '?equivalent @spec(agent-pipeline)', "
            "'@memory(presences_of_the_field)', '?cells where domain == \"spec\"'. "
            "Grammar: docs/coherence-substrate/form-language.md."
        ),
    )
    mode: str = Field(
        default="ast",
        pattern="^(ast|streaming|run)$",
        description=(
            "Evaluation path. 'ast' uses the structural Form evaluator; 'streaming' "
            "uses the BMF-style direct Recipe emitter for its supported recipe subset; "
            "'run' executes Form through the runtime and returns the computed value."
        ),
    )


class FormResultOut(BaseModel):
    """Discriminated union of Form evaluation outcomes.

    `kind` names which field carries the result. Other fields are null.
    Kinds: node_id, recipe, cell, view, cells, views, lattice, keywords,
    vocabulary, value.
    """

    kind: str
    node_id: NodeIDOut | None = None
    cell: CellOut | None = None
    view: CellViewOut | None = None
    cells: list[CellOut] | None = None
    views: list[CellViewOut] | None = None
    lattice: dict[str, int] | None = None
    keywords: list[str] | None = None
    vocabulary: dict[str, dict[str, int]] | None = None
    value: Any | None = None


def _cell_view_out(v: CellView) -> CellViewOut:
    return CellViewOut(
        cell=CellOut.from_cell(v.cell),
        view_blueprint=NodeIDOut.from_node_id(v.view_blueprint),
        compatible=v.compatible,
        reason=v.reason,
    )


def _runtime_value_out(value: Any) -> Any:
    """Render Form runtime values into JSON-safe response payloads."""
    if isinstance(value, NodeID):
        node = NodeIDOut.from_node_id(value)
        return node.model_dump(by_alias=True) if node else None
    if isinstance(value, NamedCell):
        return CellOut.from_cell(value).model_dump(by_alias=True)
    if isinstance(value, CellView):
        return _cell_view_out(value).model_dump(by_alias=True)
    if isinstance(value, list):
        return [_runtime_value_out(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _runtime_value_out(item) for key, item in value.items()}
    return value


@router.post("/form", response_model=FormResultOut, tags=["substrate"])
def evaluate_form(req: FormRequest) -> FormResultOut:
    """Evaluate a Form-notation expression against the substrate.

    The substrate's native query language. Lets an outside caller ask
    structural questions the body knows how to answer — without composing
    multiple lookup calls.

    Returns a discriminated result: the `kind` field names which payload
    field carries the value (node_id / recipe / cell / view / cells /
    views). `mode="streaming"` routes supported recipe expressions through
    the direct-emission parser and returns the emitted Recipe NodeID.
    `mode="run"` executes Form and returns the runtime value, including
    host-bound effects such as `ask(...)`. Parse and evaluation errors
    return HTTP 400 with the failure reason.

    Grammar lives in docs/coherence-substrate/form-language.md.
    """
    with session_scope() as session:
        try:
            if req.mode == "streaming":
                node_id = form_stream_emit(session, req.expression)
                return FormResultOut(
                    kind="recipe",
                    node_id=NodeIDOut.from_node_id(node_id),
                )
            if req.mode == "run":
                value = form_execute_text(session, req.expression)
                return FormResultOut(kind="value", value=_runtime_value_out(value))
            result = form_evaluate_text(session, req.expression)
        except LookupError as exc:
            # The expression parsed and evaluated cleanly, but a cell or
            # node it referenced isn't in the lattice. 404 is the honest
            # answer — the body simply doesn't hold the thing referenced.
            # Distinct from 400 (parser rejected the expression itself).
            raise HTTPException(
                status_code=404,
                detail=f"form lookup failed: {exc}",
            ) from exc
        except (
            ValueError,
            SyntaxError,
            TypeError,
            KeyError,
            NameError,
            RuntimeError,
            IndexError,
        ) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"form parse/eval failed: {type(exc).__name__}: {exc}",
            ) from exc

        if result.kind in {"node_id", "recipe"}:
            return FormResultOut(
                kind=result.kind,
                node_id=NodeIDOut.from_node_id(result.value),
            )
        if result.kind == "cell":
            return FormResultOut(kind="cell", cell=CellOut.from_cell(result.value))
        if result.kind == "view":
            return FormResultOut(kind="view", view=_cell_view_out(result.value))
        if result.kind == "cells":
            return FormResultOut(
                kind="cells",
                cells=[CellOut.from_cell(c) for c in result.value],
            )
        if result.kind == "views":
            return FormResultOut(
                kind="views",
                views=[_cell_view_out(v) for v in result.value],
            )
        if result.kind == "lattice":
            # ?lattice — substrate-snapshot lens
            return FormResultOut(kind="lattice", lattice=result.value)
        if result.kind == "keywords":
            # ?keywords — grammar-introspection lens
            return FormResultOut(kind="keywords", keywords=list(result.value))
        if result.kind == "vocabulary":
            # ?vocabulary — verb-cluster histogram. Translate type_ ints to
            # category names so the response is legible without a category
            # lookup table on the caller's side.
            from app.services.substrate.category import BBasic, RBasic

            raw = result.value
            named: dict[str, dict[str, int]] = {"recipes": {}, "blueprints": {}}
            for type_int, count in raw.get("recipes", {}).items():
                try:
                    name = RBasic(type_int).name
                except ValueError:
                    name = f"type_{type_int}"
                named["recipes"][name] = count
            for type_int, count in raw.get("blueprints", {}).items():
                try:
                    name = BBasic(type_int).name
                except ValueError:
                    name = f"type_{type_int}"
                named["blueprints"][name] = count
            return FormResultOut(kind="vocabulary", vocabulary=named)
        raise HTTPException(
            status_code=500,
            detail=f"unknown FormResult.kind: {result.kind}",
        )


# ---------------------------------------------------------------------------
# Ingest — let a visiting body place markdown content into the lattice
# ---------------------------------------------------------------------------


_INGEST_DOMAINS = {"memory", "spec", "idea", "concept", "presence"}
_MAX_INGEST_CHARS = 64 * 1024  # 64KB — generous for memory/spec/idea/concept content


class IngestRequest(BaseModel):
    domain: str = Field(
        ...,
        description=(
            "Domain blueprint to ingest under. One of: memory, spec, idea, "
            "concept, presence."
        ),
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_INGEST_CHARS,
        description=(
            "Raw markdown content. If a frontmatter block is present, the "
            "domain's expected name field (e.g. 'name' for memory, 'id' for "
            "concept) is preferred; otherwise the body is hashed for identity."
        ),
    )
    source_label: str | None = Field(
        default=None,
        max_length=512,
        description=(
            "Provenance hint stored on the cell. Honest description of where "
            "this content came from (e.g. 'web:contributor:abc123')."
        ),
    )


class IngestResponse(BaseModel):
    cell: CellOut
    blueprint: NodeIDOut
    ctor: NodeIDOut | None = None


@router.post("/ingest", response_model=IngestResponse, tags=["substrate"])
def ingest_content(req: IngestRequest) -> IngestResponse:
    """Place markdown content into the lattice from outside the repo.

    The body-reads-itself practice still holds: this endpoint creates or
    updates a NamedCell keyed by the frontmatter name field (or body hash
    when no name is present). Cross-references in the content do *not*
    auto-bind to existing cells — equivalence in the substrate is
    structural, not lexical. Two ingested cells with the same shape
    converge automatically; two with different shapes stay distinct.
    """
    if req.domain not in _INGEST_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown domain '{req.domain}'; expected one of "
                f"{sorted(_INGEST_DOMAINS)}"
            ),
        )
    with session_scope() as session:
        try:
            cell, blueprint_id, ctor_id = ingest_markdown_text(
                session,
                req.domain,
                req.content,
                source_label=req.source_label,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return IngestResponse(
            cell=CellOut.from_cell(cell),
            blueprint=NodeIDOut.from_node_id(blueprint_id),
            ctor=NodeIDOut.from_node_id(ctor_id) if ctor_id else None,
        )
