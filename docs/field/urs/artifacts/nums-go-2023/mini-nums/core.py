"""mini-nums: a minimal content-addressed numeric substrate.

Phase 1c of the NUMS study. Implements the core trinity (Blueprint, Recipe,
NamedCell) plus TreeDB interning, in ~250 lines of Python. The kernel is
language-agnostic; frontends in calc.py and jsonschema.py drive it from
two different surface syntaxes to demonstrate cross-language structural
equivalence.

What this proves (or fails to prove, surfacing gaps in my understanding):
- NodeID 4-tuple (Package, Level, Type, Instance)
- Per-level TreeDB interning by serialized-tree-string
- Make_SelfID idempotency
- Bottom-up recipe composition through recursive interning
- NamedCell carrying access-recipe + Base + Name + CTOR
- Two surface syntaxes hashing structurally-identical things to the same NodeID
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple


class Level(IntEnum):
    UNDEFINED = 0
    TRIVIAL = 1
    BASIC = 2
    COMPLEX_1 = 3
    COMPLEX_2 = 4
    COMPLEX_3 = 5
    COMPLEX_4 = 6


class BType(IntEnum):
    """Blueprint trivial-types (Level 1)."""
    UNDEFINED = 0
    VOID = 1
    NUMERIC = 2


class BNumeric(IntEnum):
    """Numeric instances (Level 1, Type=NUMERIC)."""
    UNDEFINED = 0
    BOOL = 1
    INTEGER = 2
    DECIMAL = 3
    STRING = 4


class BBasic(IntEnum):
    """Blueprint basic-types (Level 2)."""
    UNDEFINED = 0
    CONTAINER = 1
    RECIPE = 2


class BContainer(IntEnum):
    UNDEFINED = 0
    LIST = 1
    OBJECT = 2


class RType(IntEnum):
    """Recipe trivial-types (Level 1)."""
    UNDEFINED = 0
    NULL = 1
    BOOL = 2
    INTEGER = 3
    DECIMAL = 4
    STRING = 5
    LOCAL_DECL = 6
    LOCAL_ACCESS = 7
    GLOBAL = 8
    BLUEPRINT = 9


class RBasic(IntEnum):
    """Recipe basic-types (Level 2)."""
    UNDEFINED = 0
    MATH = 1
    WRITE = 2
    BLOCK = 3
    CALL = 4


class Math(IntEnum):
    PLUS = 1
    MINUS = 2
    MULTIPLY = 3
    DIVIDE = 4


@dataclass(frozen=True)
class NodeID:
    """The universal handle. 4-tuple of integers.

    Frozen so it hashes; the body holds these everywhere as immutable values.
    """
    package: int = 1
    level: int = 0
    type_: int = 0
    instance: int = 0

    def is_undefined(self) -> bool:
        return self.level == 0 and self.type_ == 0

    def __str__(self) -> str:
        return f"{self.package}.{self.level}.{self.type_}.{self.instance}"


# ---- Trivial / Basic constructors ---------------------------------------

def BID_undefined() -> NodeID: return NodeID()
def BID_void() -> NodeID: return NodeID(1, Level.TRIVIAL, BType.VOID, 0)
def BID_bool() -> NodeID: return NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.BOOL)
def BID_integer() -> NodeID: return NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.INTEGER)
def BID_decimal() -> NodeID: return NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.DECIMAL)
def BID_string() -> NodeID: return NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.STRING)
def BID_list() -> NodeID: return NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.LIST)
def BID_object() -> NodeID: return NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.OBJECT)
def BID_function() -> NodeID: return NodeID(1, Level.BASIC, BBasic.RECIPE, 1)


def RID_global(inst: int) -> NodeID: return NodeID(1, Level.TRIVIAL, RType.GLOBAL, inst)
def RID_local_decl(inst: int) -> NodeID: return NodeID(1, Level.TRIVIAL, RType.LOCAL_DECL, inst)
def RID_local_access(inst: int) -> NodeID: return NodeID(1, Level.TRIVIAL, RType.LOCAL_ACCESS, inst)
def RID_integer_lit(inst: int) -> NodeID: return NodeID(1, Level.TRIVIAL, RType.INTEGER, inst)
def RID_decimal_lit(inst: int) -> NodeID: return NodeID(1, Level.TRIVIAL, RType.DECIMAL, inst)
def RID_string_lit(inst: int) -> NodeID: return NodeID(1, Level.TRIVIAL, RType.STRING, inst)
def RID_blueprint_ref(inst: int) -> NodeID: return NodeID(1, Level.TRIVIAL, RType.BLUEPRINT, inst)
def RID_math(op: Math) -> NodeID: return NodeID(1, Level.BASIC, RBasic.MATH, op)
def RID_write_assign() -> NodeID: return NodeID(1, Level.BASIC, RBasic.WRITE, 5)  # =
def RID_block_compound() -> NodeID: return NodeID(1, Level.BASIC, RBasic.BLOCK, 2)
def RID_call() -> NodeID: return NodeID(1, Level.BASIC, RBasic.CALL, 1)


# ---- TreeDB: content-addressed interning --------------------------------

def get_level(category_level: int, child_levels: List[int]) -> int:
    """Bottom-up level computation. Mirrors NUMS.Go's get_level."""
    if not child_levels:
        return category_level
    if category_level == Level.TRIVIAL:
        return category_level
    return max(max(child_levels), category_level) + 1


def serialize_tree(category: NodeID, children: List[NodeID]) -> str:
    """The hash key — exactly the format NUMS uses."""
    return str(category) + "".join("+" + str(c) for c in children)


@dataclass
class TreeLevelDB:
    entries: Dict[Tuple[int, int], str] = field(default_factory=dict)
    rev_entries: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    counts: Dict[Tuple[int, int], int] = field(default_factory=dict)

    def record(self, level: int, type_: int, serialized: str) -> NodeID:
        key = self.rev_entries.get(serialized)
        if key is not None:
            self.counts[key] = self.counts.get(key, 0) + 1
            return NodeID(1, level, key[0], key[1])
        instance = len(self.entries) + 1
        key = (type_, instance)
        self.entries[key] = serialized
        self.rev_entries[serialized] = key
        self.counts[key] = 1
        return NodeID(1, level, type_, instance)


@dataclass
class TreeDB:
    by_level: Dict[int, TreeLevelDB] = field(default_factory=dict)

    def record(self, category: NodeID, children: List[NodeID]) -> NodeID:
        # Trivial leaves don't get re-interned (they're already unique).
        if not children and category.level <= Level.BASIC:
            return category
        level = get_level(category.level, [c.level for c in children])
        if children and level <= Level.BASIC:
            level = Level.COMPLEX_1
        ldb = self.by_level.setdefault(level, TreeLevelDB())
        return ldb.record(level, category.type_, serialize_tree(category, children))


# ---- The trinity --------------------------------------------------------

@dataclass
class Module:
    """The body. Holds two TreeDBs and a name lookup."""
    name: str = "<module>"
    blueprint_db: TreeDB = field(default_factory=TreeDB)
    recipe_db: TreeDB = field(default_factory=TreeDB)
    blueprint_names: Dict[str, NodeID] = field(default_factory=dict)
    cells_by_name: Dict[str, "NamedCell"] = field(default_factory=dict)
    next_global: int = 0
    integer_literals: Dict[str, int] = field(default_factory=dict)
    decimal_literals: Dict[str, int] = field(default_factory=dict)
    string_literals: Dict[str, int] = field(default_factory=dict)

    def emplace_integer(self, val: str) -> int:
        if val not in self.integer_literals:
            self.integer_literals[val] = len(self.integer_literals) + 1
        return self.integer_literals[val]

    def emplace_decimal(self, val: str) -> int:
        if val not in self.decimal_literals:
            self.decimal_literals[val] = len(self.decimal_literals) + 1
        return self.decimal_literals[val]

    def emplace_string(self, val: str) -> int:
        if val not in self.string_literals:
            self.string_literals[val] = len(self.string_literals) + 1
        return self.string_literals[val]

    def emplace_global(self, name: str) -> int:
        self.next_global += 1
        return self.next_global


@dataclass
class Blueprint:
    """Structural identity. What something IS (the ice phase)."""
    module: Module
    id: NodeID
    name: str = ""

    @staticmethod
    def trivial(module: Module, bid: NodeID, name: str = "") -> "Blueprint":
        bp = Blueprint(module, bid, name)
        if name:
            module.blueprint_names[name] = bid
        return bp

    @staticmethod
    def composite(module: Module, category: NodeID, children: List[NodeID], name: str = "") -> "Blueprint":
        """Build a composite blueprint and intern it. Make_SelfID equivalent."""
        bid = module.blueprint_db.record(category, children)
        bp = Blueprint(module, bid, name)
        if name:
            module.blueprint_names[name] = bid
        return bp

    def __repr__(self) -> str:
        return f"BP({self.name or '<anon>'} {self.id})"


@dataclass
class Recipe:
    """Operational expression. How something HAPPENS (the water phase).

    Recipe-tree assembly is bottom-up: build child recipes first, then
    compose with a category. make_self_id walks recursively.
    """
    module: Module
    category: NodeID
    blueprint: NodeID  # the type this expression evaluates to
    children: List["Recipe"] = field(default_factory=list)
    _self_id: Optional[NodeID] = None

    def make_self_id(self) -> NodeID:
        if self._self_id is not None:
            return self._self_id
        if not self.children:
            self._self_id = self.category
            return self._self_id
        child_ids = [c.make_self_id() for c in self.children]
        self._self_id = self.module.recipe_db.record(self.category, child_ids)
        return self._self_id

    def __repr__(self) -> str:
        sid = self._self_id or self.category
        return f"R({self.category}→{sid}, {len(self.children)} kids, bp={self.blueprint})"


@dataclass
class NamedCell:
    """Where structure and process meet, with name and seed (the gas phase)."""
    module: Module
    name: str
    base: NodeID                  # parent blueprint (undefined for globals)
    blueprint: NodeID             # this cell's type
    access: Recipe                # reading the cell IS running this recipe
    ctor: Optional[NodeID] = None # the seed-recipe ID, if any

    def __repr__(self) -> str:
        ctor_s = f", ctor={self.ctor}" if self.ctor else ""
        return f"Cell({self.name}: {self.blueprint}{ctor_s})"


# ---- Cell birth ---------------------------------------------------------

def make_global_cell(module: Module, name: str, blueprint: NodeID, init: Optional[Recipe] = None) -> NamedCell:
    """Mirrors EmitModule.Make_Field for globals. Phase 1c validation point."""
    inst = module.emplace_global(name)
    access_rid = RID_global(inst)
    access = Recipe(module, access_rid, blueprint)

    ctor_id = None
    if init is not None:
        # CTOR is itself a recipe: BlockComma(access, Write(=, access, init))
        write = Recipe(
            module, RID_write_assign(), blueprint,
            children=[access, init],
        )
        ctor_body = Recipe(
            module, RID_block_compound(), BID_void(),
            children=[access, write],
        )
        ctor_id = ctor_body.make_self_id()  # interns the CTOR

    cell = NamedCell(
        module=module, name=name, base=BID_undefined(),
        blueprint=blueprint, access=access, ctor=ctor_id,
    )
    module.cells_by_name[name] = cell
    return cell


def make_object_blueprint(module: Module, name: str, fields: List[Tuple[str, NodeID]]) -> Blueprint:
    """Build a struct/object blueprint where children are field blueprints.

    Mirrors End_Blueprint: serialize Category + ordered child blueprint IDs,
    intern, return the resulting blueprint.
    """
    field_ids = [f[1] for f in fields]
    bp = Blueprint.composite(module, BID_object(), field_ids, name=name)
    # Build NamedCell for each field, anchored in this blueprint.
    for fname, fid in fields:
        access = Recipe(module, RID_local_access(0), fid)  # simplified
        cell = NamedCell(
            module=module, name=fname, base=bp.id,
            blueprint=fid, access=access, ctor=None,
        )
        # We don't add to cells_by_name here — fields live inside the blueprint.
    return bp


def make_list_blueprint(module: Module, element: NodeID) -> Blueprint:
    return Blueprint.composite(module, BID_list(), [element])


# ---- Inspection helpers -------------------------------------------------

def lattice_stats(module: Module) -> Dict[str, int]:
    bp_levels = {lvl: len(db.entries) for lvl, db in module.blueprint_db.by_level.items()}
    rec_levels = {lvl: len(db.entries) for lvl, db in module.recipe_db.by_level.items()}
    return {
        "blueprints_by_level": bp_levels,
        "blueprints_total": sum(bp_levels.values()),
        "recipes_by_level": rec_levels,
        "recipes_total": sum(rec_levels.values()),
        "named_blueprints": len(module.blueprint_names),
        "named_cells": len(module.cells_by_name),
    }
