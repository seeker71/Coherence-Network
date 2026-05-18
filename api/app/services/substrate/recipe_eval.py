"""Recipe-execution engine — a thin NodeID-walking shim over `form_runtime.execute`.

The substrate stores Form expressions as content-addressed Recipe NodeIDs.
Two interpreters existed side-by-side:
- `form_runtime.execute(session, ast)` walks the parser's AST (the richer engine)
- `recipe_eval.eval_recipe(session, nid)` walked NodeIDs directly (the older shim)

Both implemented overlapping semantics (math/compare/logic/cond/block/state/
exception/choice) — real duplication.

This module unifies them. `eval_recipe` now:
1. Reconstructs an AST from the NodeID (via `node_to_ast`)
2. Delegates to `form_runtime.execute` — the canonical engine

What round-trips losslessly: integers, booleans, null, strings (via the
substrate string-table), composites whose category determines the AST shape
(math, compare, logic, cond, block, state, exception, choice, with, delegate,
common, method, reactive, projection, try, reverse).

What's lossy through the substrate layer: Identifier names (hash-derived
instance can't recover the original string) and Let binding names (same).
For those, reconstruction yields placeholder names that still evaluate
correctly when the value isn't later referenced by its original name.
This is a property of content-addressing — names are query keys, not stored
identity.

The Environment / ExecutionContext / FailSignal / StopSignal / RaiseSignal
classes stay exported for back-compat; they delegate to or re-export
form_runtime's equivalents.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.substrate.category import (
    BBasic,
    BNumeric,
    BType,
    Level,
    RBasic,
    RBlock,
    RChoice,
    RCompare,
    RCond,
    RDelegate,
    RException,
    RLogic,
    RMath,
    RMethod,
    RProjection,
    RReactive,
    RReverse,
    RState,
    RTry,
    RType,
)
from app.services.substrate.kernel import NodeID, lookup_node
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


# ---------------------------------------------------------------------------
# Re-exports for back-compat — form_runtime is now the canonical engine
# ---------------------------------------------------------------------------


from app.services.substrate.form_runtime import (
    Frame as _Frame,
    RaiseSignal,
    fire_subscriptions,  # noqa: F401
)
from app.services.substrate.form_speculation import FailSignal, StopSignal


# Back-compat Environment shim — older recipe_eval tests imported this name
# (form_runtime calls the equivalent class `Frame`).
Environment = _Frame


class ExecutionContext:
    """Back-compat shell. Wraps a form_runtime Frame for the state-stack and
    env-bindings APIs the older recipe_eval tests use directly.

    New code should use form_runtime's Frame + execute directly.
    """

    def __init__(self) -> None:
        self.frame: _Frame = _Frame()
        # The legacy state_stack attribute lives on the root frame; expose it
        # here for tests that read/write it directly.
        if not hasattr(self.frame, "_state_stack"):
            self.frame._state_stack = []

    @property
    def state_stack(self) -> List[Dict[str, Any]]:
        return self.frame._state_stack

    @property
    def env(self):
        """Legacy attribute — returns the Frame, which exposes .bindings."""
        return self.frame


# ---------------------------------------------------------------------------
# Serialized → (category, child NodeIDs) parsing
# ---------------------------------------------------------------------------


def _parse_node_id(s: str) -> NodeID:
    parts = s.split(".")
    if len(parts) != 4:
        raise ValueError(f"recipe_eval: bad NodeID {s!r}")
    return NodeID(int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))


def _parse_serialized(serialized: str) -> Tuple[NodeID, List[NodeID]]:
    """Inverse of `serialize_tree`. Returns (category, children-as-NodeIDs)."""
    chunks = serialized.split("+")
    category = _parse_node_id(chunks[0])
    children = [_parse_node_id(c) for c in chunks[1:]]
    return category, children


# ---------------------------------------------------------------------------
# Trivial-leaf value recovery (leaves don't have rows in substrate_nodes)
# ---------------------------------------------------------------------------


_UNRECOVERABLE = object()


def _recover_trivial(node: NodeID, session=None) -> Any:
    """Recover the runtime value of a trivial-leaf NodeID.

    StringLit recovery requires the session (string-table lookup); when called
    without a session, strings return `_UNRECOVERABLE`. All other types are
    pure-numeric and recover without the session.
    """
    if node.level != Level.TRIVIAL:
        return _UNRECOVERABLE
    if node.type_ == RType.INTEGER:
        return node.instance - 1 if node.instance > 0 else 0
    if node.type_ == RType.BOOL:
        return bool(node.instance)
    if node.type_ == RType.NULL:
        return None
    if node.type_ == RType.STRING and session is not None:
        from app.services.substrate.substrate_strings import lookup_string_value
        value = lookup_string_value(session, node.instance)
        if value is not None:
            return value
    return _UNRECOVERABLE


# ---------------------------------------------------------------------------
# NodeID → AST reconstruction
# ---------------------------------------------------------------------------
#
# Bridge between the substrate's content-addressed form and the parser's AST.
# Built so eval_recipe can route through form_runtime.execute (one engine).


def _math_ast(instance: int, kids: list) -> Any:
    from app.services.substrate.form import BinOp, UnaryOp
    op = {
        RMath.PLUS: "+", RMath.MINUS: "-", RMath.MULTIPLY: "*",
        RMath.DIVIDE: "/", RMath.MODULO: "%", RMath.NEGATE: "-",
    }[instance]
    if instance == RMath.NEGATE:
        return UnaryOp(op="-", operand=kids[0])
    return BinOp(op=op, left=kids[0], right=kids[1])


def _compare_ast(instance: int, kids: list) -> Any:
    from app.services.substrate.form import BinOp
    op = {
        RCompare.EQUAL: "==", RCompare.NOT_EQUAL: "!=",
        RCompare.LESS: "<", RCompare.LESS_EQUAL: "<=",
        RCompare.GREATER: ">", RCompare.GREATER_EQUAL: ">=",
    }[instance]
    return BinOp(op=op, left=kids[0], right=kids[1])


def _logic_ast(instance: int, kids: list) -> Any:
    from app.services.substrate.form import BinOp, UnaryOp
    if instance == RLogic.NOT:
        return UnaryOp(op="!", operand=kids[0])
    op = "&&" if instance == RLogic.AND else "||"
    return BinOp(op=op, left=kids[0], right=kids[1])


def _cond_ast(instance: int, kids: list) -> Any:
    from app.services.substrate.form import IfExpr
    if instance == RCond.IF_THEN:
        return IfExpr(cond=kids[0], then_branch=kids[1], else_branch=None)
    return IfExpr(cond=kids[0], then_branch=kids[1], else_branch=kids[2])


def _block_ast(session: Session, instance: int, child_nids: List[NodeID], kids: list) -> Any:
    """Block recipes: DO/SEQUENCE → DoBlock, LET → Let, WITH → WithExpr."""
    from app.services.substrate.form import DoBlock, Let, WithExpr, Identifier, StringLit
    if instance == RBlock.DO or instance == RBlock.SEQUENCE:
        return DoBlock(statements=kids)
    if instance == RBlock.LET:
        # Children = [name-string, value]. Try to recover the name from the
        # string-table; if lossy, synthesize a placeholder.
        from app.services.substrate.substrate_strings import lookup_string_value
        name_nid = child_nids[0]
        name = None
        if name_nid.type_ == RType.STRING:
            name = lookup_string_value(session, name_nid.instance)
        if name is None:
            name = f"__hashed_{name_nid.instance}"
        return Let(name=name, value=kids[1])
    if instance == RBlock.WITH:
        return WithExpr(subject=kids[0], body=kids[1])
    raise ValueError(f"recipe_eval: unknown block instance {instance}")


def _choice_ast(instance: int, kids: list) -> Any:
    from app.services.substrate.form import ChooseExpr, FailExpr, StopExpr
    if instance == RChoice.CHOOSE:
        return ChooseExpr(candidates=kids)
    if instance == RChoice.FAIL:
        return FailExpr()
    return StopExpr()


def _state_ast(instance: int) -> Any:
    from app.services.substrate.form import SaveExpr, RestoreExpr, DiscardExpr
    return {RState.SAVE: SaveExpr, RState.RESTORE: RestoreExpr, RState.DISCARD: DiscardExpr}[instance]()


def _exception_ast(instance: int, kids: list) -> Any:
    from app.services.substrate.form import RaiseExpr, ResumeExpr
    if instance == RException.RAISE:
        return RaiseExpr(value=kids[0] if kids else None)
    return ResumeExpr()


def _reverse_ast(instance: int, kids: list) -> Any:
    from app.services.substrate.form import UndoExpr, InverseExpr
    if instance == RReverse.UNDO:
        return UndoExpr(child=kids[0])
    return InverseExpr(child=kids[0])


def _method_ast(session: Session, instance: int, child_nids: List[NodeID], kids: list) -> Any:
    from app.services.substrate.form import MethodDefExpr, MethodInvokeExpr, StringLit
    from app.services.substrate.substrate_strings import lookup_string_value
    name_nid = child_nids[0]
    name = lookup_string_value(session, name_nid.instance) if name_nid.type_ == RType.STRING else None
    name = name or f"__method_{name_nid.instance}"
    target = kids[1]
    if instance == RMethod.DEFINE:
        # children: [name_str, target, params_seq, body]
        body = kids[3]
        return MethodDefExpr(name=name, target=target, body=body, params=[])
    # INVOKE: [name_str, target, *args]
    return MethodInvokeExpr(name=name, target=target, args=kids[2:])


def _cell_ref_ast(session: Session, nid: NodeID) -> Any:
    """A cell-ref encoded as (TRIVIAL, RType.GLOBAL=8 or RType.REF=9, cell_id).

    Reconstructs a CellRef by looking up the cell row.
    """
    from app.services.substrate.form import CellRef, NodeIDLit
    if nid.type_ in (8, RType.REF):
        cell_id = nid.instance
        row = (
            session.query(SubstrateNamedCellORM)
            .filter_by(cell_id=cell_id)
            .one_or_none()
        )
        if row is not None:
            return CellRef(domain=row.domain, name=row.name)
    # Unknown — return as a NodeIDLit (carries the raw coordinates).
    return NodeIDLit(package=nid.package, level=nid.level, type_=nid.type_, instance=nid.instance)


def _identifier_ast(nid: NodeID) -> Any:
    """A bare identifier encoded as (TRIVIAL, 7, hash). Name is lossy."""
    from app.services.substrate.form import Identifier
    return Identifier(name=f"__hashed_{nid.instance}")


# Bounded reconstruction cache. The substrate is append-only at the row
# level (interned shapes, allocated string-instances, created cells never
# change after writing), so a NodeID maps to a stable AST shape across
# the process lifetime. Evaluators (form_runtime.execute, _to_recipe_node_id)
# walk AST nodes read-only, so sharing a single AST object across callers
# is safe. Capping the cache keeps memory bounded under heavy use.
_NODE_TO_AST_CACHE: "OrderedDict[NodeID, Any]" = OrderedDict()
_NODE_TO_AST_CACHE_MAX = 1024


def node_to_ast(session: Session, nid: NodeID) -> Any:
    """Reconstruct an AST node from a Recipe NodeID.

    The canonical bridge between content-addressed substrate form and the
    parser's AST. `eval_recipe` calls this then hands the result to
    `form_runtime.execute` — one engine, two input modes.
    """
    cached = _NODE_TO_AST_CACHE.get(nid)
    if cached is not None:
        _NODE_TO_AST_CACHE.move_to_end(nid)
        return cached
    ast = _node_to_ast_uncached(session, nid)
    _NODE_TO_AST_CACHE[nid] = ast
    if len(_NODE_TO_AST_CACHE) > _NODE_TO_AST_CACHE_MAX:
        _NODE_TO_AST_CACHE.popitem(last=False)
    return ast


def _node_to_ast_uncached(session: Session, nid: NodeID) -> Any:
    from app.services.substrate.form import (
        IntLit, BoolLit, StringLit, Identifier,
        CommonExpr, DelegateExpr, OnChangeExpr, ProjectExpr, TryCatchExpr,
        DoBlock,
    )
    from app.services.substrate.substrate_strings import lookup_string_value

    # Trivial leaves recover directly from coordinates.
    if nid.level == Level.TRIVIAL:
        if nid.type_ == RType.INTEGER:
            return IntLit(value=nid.instance - 1 if nid.instance > 0 else 0)
        if nid.type_ == RType.BOOL:
            return BoolLit(value=bool(nid.instance))
        if nid.type_ == RType.NULL:
            return Identifier(name="null")
        if nid.type_ == RType.STRING:
            value = lookup_string_value(session, nid.instance) or ""
            return StringLit(value=value)
        if nid.type_ in (8, RType.REF):
            return _cell_ref_ast(session, nid)
        if nid.type_ == 7:  # LOCAL_ACCESS / placeholder identifier
            return _identifier_ast(nid)
        # Unknown trivial — fall back to a NodeIDLit.
        from app.services.substrate.form import NodeIDLit
        return NodeIDLit(package=nid.package, level=nid.level, type_=nid.type_, instance=nid.instance)

    # Bare BASIC-level leaves (no row) — CHOICE/STATE/EXCEPTION primitives.
    row = lookup_node(session, nid)
    if row is None or not row.serialized or "+" not in row.serialized:
        # Bare-leaf primitives at BASIC level (without rows / serialized).
        if nid.level == Level.BASIC:
            if nid.type_ == RBasic.CHOICE:
                return _choice_ast(nid.instance, [])
            if nid.type_ == RBasic.STATE:
                return _state_ast(nid.instance)
            if nid.type_ == RBasic.EXCEPTION:
                return _exception_ast(nid.instance, [])
        # Unknown — return a NodeIDLit so the engine can evaluate it as-is.
        from app.services.substrate.form import NodeIDLit
        return NodeIDLit(package=nid.package, level=nid.level, type_=nid.type_, instance=nid.instance)

    # Composite: parse serialized form, recurse on children.
    category, child_nids = _parse_serialized(row.serialized)
    kids = [node_to_ast(session, c) for c in child_nids]

    if category.type_ == RBasic.MATH:
        return _math_ast(category.instance, kids)
    if category.type_ == RBasic.COMPARE:
        return _compare_ast(category.instance, kids)
    if category.type_ == RBasic.LOGIC:
        return _logic_ast(category.instance, kids)
    if category.type_ == RBasic.COND:
        return _cond_ast(category.instance, kids)
    if category.type_ == RBasic.BLOCK:
        return _block_ast(session, category.instance, child_nids, kids)
    if category.type_ == RBasic.CHOICE:
        return _choice_ast(category.instance, kids)
    if category.type_ == RBasic.STATE:
        return _state_ast(category.instance)
    if category.type_ == RBasic.EXCEPTION:
        return _exception_ast(category.instance, kids)
    if category.type_ == RBasic.REVERSE:
        return _reverse_ast(category.instance, kids)
    if category.type_ == RBasic.DELEGATE:
        return DelegateExpr(source=kids[0], target=kids[1])
    if category.type_ == RBasic.COMMON:
        return CommonExpr(a=kids[0], b=kids[1])
    if category.type_ == RBasic.METHOD:
        return _method_ast(session, category.instance, child_nids, kids)
    if category.type_ == RBasic.REACTIVE:
        return OnChangeExpr(query=kids[0], body=kids[1])
    if category.type_ == RBasic.PROJECTION:
        return ProjectExpr(cell=kids[0], coord_fn=kids[1])
    if category.type_ == RBasic.TRY:
        return TryCatchExpr(body=kids[0], handler=kids[1])

    # Unknown composite category — fall back to a DoBlock around the children.
    return DoBlock(statements=kids)


# ---------------------------------------------------------------------------
# Public API — eval_recipe + eval_text now route through form_runtime
# ---------------------------------------------------------------------------


def eval_recipe(
    session: Session,
    node: NodeID,
    ctx: Optional[ExecutionContext] = None,
) -> Any:
    """Evaluate a Recipe NodeID by reconstructing its AST and routing through
    `form_runtime.execute` — the canonical engine.

    `ctx` is accepted for back-compat (the state-stack on the Frame is
    initialized fresh per-call); pass one explicitly when state-stack
    continuity matters across multiple `eval_recipe` calls.
    """
    from app.services.substrate.form_runtime import execute

    ast = node_to_ast(session, node)
    frame = ctx.frame if ctx is not None else None
    return execute(session, ast, frame=frame)


def eval_text(session: Session, text: str) -> Any:
    """Parse and run a Form expression via the canonical engine.

    Direct wrapper over `form_runtime.form_execute_text`; the entire engine
    flows through one path now.
    """
    from app.services.substrate.form_runtime import form_execute_text
    return form_execute_text(session, text)


def _eval_state(instance: int, ctx: ExecutionContext) -> Any:
    """Back-compat shim — older tests call this directly to exercise the
    state-stack mechanics. Operates on the wrapping ExecutionContext's frame
    (the canonical state-stack lives on the root Frame in form_runtime).
    """
    if instance == RState.SAVE:
        ctx.state_stack.append(dict(ctx.frame.bindings))
        return None
    if instance == RState.RESTORE:
        if not ctx.state_stack:
            raise IndexError("recipe_eval: restore with empty state stack")
        ctx.frame.bindings = ctx.state_stack.pop()
        return None
    if instance == RState.DISCARD:
        if not ctx.state_stack:
            raise IndexError("recipe_eval: discard with empty state stack")
        ctx.state_stack.pop()
        return None
    raise ValueError(f"recipe_eval: unknown state instance {instance}")


__all__ = [
    "Environment",
    "ExecutionContext",
    "FailSignal",
    "RaiseSignal",
    "StopSignal",
    "eval_recipe",
    "eval_text",
    "node_to_ast",
]
