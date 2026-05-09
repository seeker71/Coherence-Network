"""Coherence-substrate kernel — NodeID, Module, Blueprint, Recipe, NamedCell.

Persistent, content-addressed, multi-process-safe. Backed by SQLAlchemy
against Postgres or SQLite via the unified_db engine. The architectural
lineage (the prior art that informs this design) is captured in
docs/field/urs/artifacts/nums-go-2023/.

The trinity:
- Blueprint (ice phase) — structural identity; what something IS
- Recipe (water phase) — operational expression; how something HAPPENS
- NamedCell (gas phase) — diffuse individuation; named slot with its CTOR

The kernel is universal — domain frontends (markdown_frontend, etc.) drive
it from format-specific surface syntax. The Network's domain-specific
category vocabulary lives in category.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services.substrate.category import Level
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


# ---------------------------------------------------------------------------
# NodeID — the universal handle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeID:
    """4-tuple of integers identifying a position in the lattice.

    Frozen so it hashes; the body holds these everywhere as immutable values.
    Maps to (package, level, type_, instance) in substrate_nodes.
    """

    package: int
    level: int
    type_: int
    instance: int

    def is_undefined(self) -> bool:
        return self.level == 0 and self.type_ == 0

    def __str__(self) -> str:
        return f"{self.package}.{self.level}.{self.type_}.{self.instance}"

    @classmethod
    def undefined(cls) -> "NodeID":
        return cls(1, 0, 0, 0)


# ---------------------------------------------------------------------------
# Domain enum — the high-level type-space partition
# ---------------------------------------------------------------------------


DOMAIN_BLUEPRINT = "blueprint"
DOMAIN_RECIPE = "recipe"


# ---------------------------------------------------------------------------
# Level computation — bottom-up, universal
# ---------------------------------------------------------------------------


def get_level(category_level: int, child_levels: List[int]) -> int:
    if not child_levels:
        return category_level
    if category_level == Level.TRIVIAL:
        return category_level
    return max(max(child_levels), category_level) + 1


def serialize_tree(category: NodeID, children: List[NodeID]) -> str:
    """Hash key. Hash format: Category + '+' + child IDs joined."""
    return str(category) + "".join("+" + str(c) for c in children)


# ---------------------------------------------------------------------------
# TreeDB — content-addressed interning, persistent
# ---------------------------------------------------------------------------


def intern_node(
    session: Session,
    domain: str,
    category: NodeID,
    children: List[NodeID],
) -> NodeID:
    """Intern a (category, children) shape into substrate_nodes.

    Returns the NodeID of the interned shape — fresh if first time seen,
    existing if a structurally identical shape was already interned.

    SELECT-first pattern: we look up by (package, level, domain, serialized)
    before inserting, so the path stays in one transaction. Multi-process
    safety relies on SERIALIZABLE isolation (Postgres) or the SQLite global
    write lock; in practice the body runs single-process so collisions are
    rare. The UNIQUE constraint is a backstop.
    """
    # Trivial leaves with no children are not re-interned — their NodeID
    # is already canonical.
    if not children and category.level <= Level.BASIC:
        return category

    level = get_level(category.level, [c.level for c in children])
    if children and level <= Level.BASIC:
        level = Level.COMPLEX_1

    serialized = serialize_tree(category, children)
    package = category.package

    # SELECT first — same-shape lookup, all-in-one-transaction visibility.
    existing = (
        session.query(SubstrateNodeORM)
        .filter_by(
            package=package, level=level, domain=domain, serialized=serialized,
        )
        .one_or_none()
    )
    if existing is not None:
        existing.count = (existing.count or 0) + 1
        session.flush()
        return NodeID(
            existing.package, existing.level, existing.type_, existing.instance
        )

    # Allocate a fresh instance number for (package, level, type).
    existing_for_type = (
        session.query(SubstrateNodeORM)
        .filter_by(package=package, level=level, type_=category.type_)
        .count()
    )
    instance = existing_for_type + 1

    try:
        node = SubstrateNodeORM(
            package=package,
            level=level,
            type_=category.type_,
            instance=instance,
            serialized=serialized,
            domain=domain,
            count=1,
        )
        session.add(node)
        session.flush()
        return NodeID(package, level, category.type_, instance)
    except IntegrityError:
        # Race lost — another process inserted the same shape. Re-query.
        session.rollback()
        existing = (
            session.query(SubstrateNodeORM)
            .filter_by(
                package=package, level=level, domain=domain, serialized=serialized,
            )
            .one_or_none()
        )
        if existing is None:
            raise
        existing.count = (existing.count or 0) + 1
        session.flush()
        return NodeID(
            existing.package, existing.level, existing.type_, existing.instance
        )


def lookup_node(session: Session, node_id: NodeID) -> Optional[SubstrateNodeORM]:
    """Read a node by its NodeID."""
    return (
        session.query(SubstrateNodeORM)
        .filter_by(
            package=node_id.package,
            level=node_id.level,
            type_=node_id.type_,
            instance=node_id.instance,
        )
        .one_or_none()
    )


# ---------------------------------------------------------------------------
# Blueprint — structural identity
# ---------------------------------------------------------------------------


def make_trivial_blueprint(category: NodeID) -> NodeID:
    """Trivial blueprints are their own NodeID — no interning needed.

    Use the BID_* constants from category.py to construct these.
    """
    return category


def make_composite_blueprint(
    session: Session,
    category: NodeID,
    children: List[NodeID],
) -> NodeID:
    """Build a composite blueprint by interning (Category, children).

    Two structurally-identical composites collapse to one NodeID.
    """
    return intern_node(session, DOMAIN_BLUEPRINT, category, children)


# ---------------------------------------------------------------------------
# Recipe — operational expression
# ---------------------------------------------------------------------------


@dataclass
class Recipe:
    """In-memory recipe being assembled. Call make_self_id() to intern."""

    category: NodeID
    blueprint: NodeID  # the type this expression evaluates to
    children: List["Recipe"]
    _self_id: Optional[NodeID] = None

    def __init__(
        self,
        category: NodeID,
        blueprint: NodeID,
        children: Optional[List["Recipe"]] = None,
    ) -> None:
        self.category = category
        self.blueprint = blueprint
        self.children = children or []
        self._self_id = None

    def make_self_id(self, session: Session) -> NodeID:
        """Bottom-up recursive interning. Bottom-up recursive composition."""
        if self._self_id is not None:
            return self._self_id
        if not self.children:
            self._self_id = self.category
            return self._self_id
        child_ids = [c.make_self_id(session) for c in self.children]
        self._self_id = intern_node(
            session, DOMAIN_RECIPE, self.category, child_ids
        )
        return self._self_id


# ---------------------------------------------------------------------------
# NamedCell — diffuse individuation
# ---------------------------------------------------------------------------


@dataclass
class NamedCell:
    """A named instance — Recipe access + Base + Name + CTOR."""

    name: str
    domain: str  # 'memory', 'spec', 'concept', etc.
    base: Optional[NodeID]
    blueprint: NodeID
    access: Optional[NodeID]  # access-recipe NodeID
    ctor: Optional[NodeID]  # CTOR-recipe NodeID
    cell_id: Optional[int] = None
    source_path: Optional[str] = None


def make_cell(
    session: Session,
    name: str,
    domain: str,
    blueprint: NodeID,
    *,
    base: Optional[NodeID] = None,
    access: Optional[NodeID] = None,
    ctor: Optional[NodeID] = None,
    source_path: Optional[str] = None,
) -> NamedCell:
    """Create or update a NamedCell. Idempotent on (domain, name).

    If a cell with the same (domain, name) exists, updates its bindings
    (blueprint, access, ctor, source_path) and refreshes updated_at.
    """
    existing = (
        session.query(SubstrateNamedCellORM)
        .filter_by(domain=domain, name=name)
        .one_or_none()
    )

    base_id = _node_to_db_id(session, base)
    bp_id = _node_to_db_id(session, blueprint)
    access_id = _node_to_db_id(session, access)
    ctor_id = _node_to_db_id(session, ctor)

    if existing is not None:
        existing.base_node_id = base_id
        existing.blueprint_node_id = bp_id
        existing.access_recipe_node_id = access_id
        existing.ctor_recipe_node_id = ctor_id
        if source_path is not None:
            existing.source_path = source_path
        from datetime import datetime, timezone
        existing.updated_at = datetime.now(timezone.utc)
        session.flush()
        cell_id = existing.cell_id
    else:
        cell_orm = SubstrateNamedCellORM(
            name=name,
            domain=domain,
            base_node_id=base_id,
            blueprint_node_id=bp_id,
            access_recipe_node_id=access_id,
            ctor_recipe_node_id=ctor_id,
            source_path=source_path,
        )
        session.add(cell_orm)
        session.flush()
        cell_id = cell_orm.cell_id

    return NamedCell(
        name=name,
        domain=domain,
        base=base,
        blueprint=blueprint,
        access=access,
        ctor=ctor,
        cell_id=cell_id,
        source_path=source_path,
    )


def lookup_cell(session: Session, domain: str, name: str) -> Optional[NamedCell]:
    """Find a cell by (domain, name)."""
    cell_orm = (
        session.query(SubstrateNamedCellORM)
        .filter_by(domain=domain, name=name)
        .one_or_none()
    )
    if cell_orm is None:
        return None
    return _orm_to_cell(session, cell_orm)


# ---------------------------------------------------------------------------
# Views — BML-style detached interfaces
# ---------------------------------------------------------------------------
#
# A Cell carries a (Base blueprint, access Recipe) dual-pointer pair: the
# Base is the structural pointer (what shape the cell has); the access
# Recipe is the behavioral pointer (how to read it). Because they are
# separate, the substrate supports BML-style detached interfaces — the
# ability to project the same cell through a different Blueprint than its
# base, without modifying the cell.
#
# A View is a (cell, view_blueprint) projection. It is computed on demand
# rather than stored — the cell remains canonical, the view is a virtual
# perspective. The View carries:
#   - the original cell's data (access recipe, source path, ctor)
#   - the new blueprint as the projection's "interface"
#   - a compatibility flag indicating whether the projection is sound
#
# Lineage: see `docs/field/urs/artifacts/master-thesis-2000/README.md`
# ("The BML object architecture — dual-pointer references and detached
# interfaces") and Bjorg's BML Object System thesis at
# `docs/field/urs/artifacts/master-thesis-2000/companion/sgb-bml-objects.txt`.


@dataclass
class CellView:
    """A projection of an existing cell through a different Blueprint.

    Equivalent to a BML reference where (object_id, interface_id) point at
    the same data through a chosen interface. The cell is not modified;
    the view is a virtual perspective.
    """

    cell: "NamedCell"             # the underlying cell (data side)
    view_blueprint: NodeID        # the projecting Blueprint (interface side)
    compatible: bool              # whether the projection is structurally sound
    reason: Optional[str] = None  # if not compatible, why


def view_cell_through_blueprint(
    session: Session, cell: "NamedCell", view_blueprint: NodeID
) -> CellView:
    """Project a cell through a different Blueprint than its base.

    Structural compatibility check: a view is "compatible" when the view
    Blueprint is structurally a subset of (or equal to) the cell's actual
    Blueprint — in BML terms, the interface's method set is a subset of
    the methods the structure provides. For the Network's substrate where
    Blueprints encode frontmatter shape, that translates to: the view's
    expected fields must be present in the cell's actual fields.

    For now we use a simpler rule: compatible iff the cell's Blueprint
    NodeID equals the view_blueprint, or one is the trivial domain
    blueprint of the other. Richer subset checks (per-field name+type
    matching) are a phase-4-extension followup.
    """
    if cell.blueprint == view_blueprint:
        return CellView(cell=cell, view_blueprint=view_blueprint, compatible=True)

    # Trivial domain match — e.g. the cell's blueprint is a Memory composite,
    # and we're viewing through the trivial Memory domain blueprint.
    cell_orm = (
        session.query(SubstrateNodeORM)
        .filter_by(
            package=cell.blueprint.package,
            level=cell.blueprint.level,
            type_=cell.blueprint.type_,
            instance=cell.blueprint.instance,
        )
        .one_or_none()
    )
    if cell_orm is None:
        return CellView(
            cell=cell, view_blueprint=view_blueprint, compatible=False,
            reason="cell's blueprint not found in substrate",
        )

    # Domain trivial match: view through @memory works for any cell whose
    # Blueprint serializes with @memory as its category.
    view_str = str(view_blueprint)
    if cell_orm.serialized.startswith(view_str + "+") or cell_orm.serialized == view_str:
        return CellView(cell=cell, view_blueprint=view_blueprint, compatible=True)

    return CellView(
        cell=cell, view_blueprint=view_blueprint, compatible=False,
        reason=(
            f"cell blueprint {cell.blueprint} not structurally compatible "
            f"with view blueprint {view_blueprint}; richer subset checks pending"
        ),
    )


def find_cells_compatible_with(
    session: Session, view_blueprint: NodeID, domain: Optional[str] = None
) -> List["CellView"]:
    """Find all cells whose Blueprint is structurally compatible with view_blueprint.

    Returns the set of valid CellViews — every cell that can be projected
    through this Blueprint without violating its structure. This is the
    BML "detached interface" query: given an interface, what objects in
    the body can be viewed through it?
    """
    q = session.query(SubstrateNamedCellORM)
    if domain is not None:
        q = q.filter_by(domain=domain)
    rows = q.all()
    out = []
    for row in rows:
        cell = _orm_to_cell(session, row)
        if cell.blueprint is None:
            continue
        view = view_cell_through_blueprint(session, cell, view_blueprint)
        if view.compatible:
            out.append(view)
    return out


def find_equivalent_cells(
    session: Session, blueprint: NodeID, *, exclude_name: Optional[str] = None
) -> List[NamedCell]:
    """Return all cells whose blueprint NodeID matches the given one.

    Two cells with the same Blueprint NodeID are *structurally equivalent*
    — they have identical shape regardless of name or domain.
    """
    bp_id = _node_to_db_id(session, blueprint)
    if bp_id is None:
        return []
    rows = (
        session.query(SubstrateNamedCellORM)
        .filter_by(blueprint_node_id=bp_id)
        .all()
    )
    out = []
    for row in rows:
        if exclude_name is not None and row.name == exclude_name:
            continue
        out.append(_orm_to_cell(session, row))
    return out


# ---------------------------------------------------------------------------
# Annotation — passive substrate context for any path
# ---------------------------------------------------------------------------


@dataclass
class PathAnnotation:
    """Substrate context for a file path. The shape an agent receives when
    it reads a file and wants to ground its reasoning structurally.

    `cell` is None if this path isn't ingested into the substrate yet.
    `equivalents` is empty if cell is None or the cell is a singleton.
    """

    path: str
    cell: Optional["NamedCell"]
    blueprint: Optional[NodeID]
    equivalents: List["NamedCell"]
    domain: Optional[str]


def annotate_path(session: Session, path: str) -> PathAnnotation:
    """Return substrate context for a file path.

    The lookup is by source_path — the path stored when the cell was
    ingested. If multiple cells point at the same path (rare; possible
    if the same file is ingested under multiple domains), only the first
    is returned.

    Agents call this when they read a file and want to know:
    - what cell this file is in the substrate
    - what Blueprint shape it has
    - what other cells share that shape (structural equivalents)
    """
    cell_orm = (
        session.query(SubstrateNamedCellORM)
        .filter_by(source_path=path)
        .order_by(SubstrateNamedCellORM.cell_id)
        .first()
    )
    if cell_orm is None:
        return PathAnnotation(
            path=path, cell=None, blueprint=None, equivalents=[], domain=None,
        )
    cell = _orm_to_cell(session, cell_orm)
    eq = []
    if cell.blueprint is not None and not cell.blueprint.is_undefined():
        eq = find_equivalent_cells(session, cell.blueprint, exclude_name=cell.name)
    return PathAnnotation(
        path=path,
        cell=cell,
        blueprint=cell.blueprint,
        equivalents=eq,
        domain=cell.domain,
    )


# ---------------------------------------------------------------------------
# Inspection helpers
# ---------------------------------------------------------------------------


def lattice_stats(session: Session) -> dict:
    """Per-level cell + recipe counts plus totals."""
    blueprints_total = (
        session.query(SubstrateNodeORM)
        .filter_by(domain=DOMAIN_BLUEPRINT)
        .count()
    )
    recipes_total = (
        session.query(SubstrateNodeORM).filter_by(domain=DOMAIN_RECIPE).count()
    )
    cells_total = session.query(SubstrateNamedCellORM).count()

    return {
        "blueprints_total": blueprints_total,
        "recipes_total": recipes_total,
        "cells_total": cells_total,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _node_to_db_id(session: Session, node_id: Optional[NodeID]) -> Optional[int]:
    """NodeID → substrate_nodes.node_id, materializing trivial nodes if needed."""
    if node_id is None or node_id.is_undefined():
        return None
    orm = lookup_node(session, node_id)
    if orm is not None:
        return orm.node_id
    # Trivial leaf — materialize as a row so foreign keys can point to it.
    serialized = str(node_id)
    new_orm = SubstrateNodeORM(
        package=node_id.package,
        level=node_id.level,
        type_=node_id.type_,
        instance=node_id.instance,
        serialized=serialized,
        domain=DOMAIN_BLUEPRINT if node_id.level <= Level.BASIC else DOMAIN_BLUEPRINT,
        count=1,
    )
    try:
        session.add(new_orm)
        session.flush()
        return new_orm.node_id
    except IntegrityError:
        session.rollback()
        existing = lookup_node(session, node_id)
        return existing.node_id if existing else None


def _orm_to_cell(session: Session, cell_orm: SubstrateNamedCellORM) -> NamedCell:
    def _resolve(db_id: Optional[int]) -> Optional[NodeID]:
        if db_id is None:
            return None
        row = (
            session.query(SubstrateNodeORM)
            .filter_by(node_id=db_id)
            .one_or_none()
        )
        if row is None:
            return None
        return NodeID(row.package, row.level, row.type_, row.instance)

    return NamedCell(
        name=cell_orm.name,
        domain=cell_orm.domain,
        base=_resolve(cell_orm.base_node_id),
        blueprint=_resolve(cell_orm.blueprint_node_id),
        access=_resolve(cell_orm.access_recipe_node_id),
        ctor=_resolve(cell_orm.ctor_recipe_node_id),
        cell_id=cell_orm.cell_id,
        source_path=cell_orm.source_path,
    )
