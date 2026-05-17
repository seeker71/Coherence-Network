"""Recipe-execution engine — the shared dependency for runtime semantics.

Every Form construct that landed at the structural layer (save / restore /
discard / raise / resume / math / compare / logic / cond / block / let /
choose / fail / stop) intern as Recipe NodeIDs but had no runtime semantics
— the structural form lived, the execution was the named shared follow-on.

This module is that follow-on. It walks a Recipe NodeID by reading its row
from `substrate_nodes`, parsing the serialized `(category, [child_ids])`
shape, dispatching on category, and recursing for children. Returns a
runtime value.

What activates here:
- Trivial literals: int (recoverable from NodeID instance), bool, null
- Math: + - * / % negate
- Compare: == != < <= > >=
- Logic: && || !
- Cond: if-then, if-then-else
- Block: do-sequences, let-bindings (with Environment)
- State: save / restore / discard (state stack)
- Exception: raise / resume (try-frame stack)
- Choice: fail / stop (signal exceptions)

What does NOT activate here (needs specialized engines):
- @cell-ref evaluation against the substrate cell graph
- delegate (dispatch chain walk)
- method def + invoke (cell-attached methods, dispatch)
- common (multi-base reconciliation)
- on_change (subscription engine)
- project (renderer engine)
- resonance edges (structural, not executable)

The interpreter is honest about its scope: pure-computation primitives
become alive; cell-aware and external-engine constructs remain named as
their own specialized layers.
"""
from __future__ import annotations

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
    RException,
    RLogic,
    RMath,
    RState,
    RType,
)
from app.services.substrate.kernel import NodeID, lookup_node
from app.services.substrate.orm import SubstrateNodeORM


# ---------------------------------------------------------------------------
# Runtime data
# ---------------------------------------------------------------------------


class FailSignal(Exception):
    """Raised by `fail` recipe — unwinds to nearest `choose` (when speculation lands)
    or surfaces as runtime failure."""


class StopSignal(Exception):
    """Raised by `stop` recipe — commits speculation; in a non-speculative
    context this stops evaluation and returns the in-flight value."""


class RaiseSignal(Exception):
    """Raised by `raise` recipe — caught by the next try-frame or surfaces."""

    def __init__(self, payload: Any = None):
        super().__init__(payload)
        self.payload = payload


class Environment:
    """Let-binding scope. Parent chain for nested do-blocks."""

    def __init__(self, parent: Optional["Environment"] = None):
        self.parent = parent
        self.bindings: Dict[str, Any] = {}

    def lookup(self, name: str) -> Any:
        if name in self.bindings:
            return self.bindings[name]
        if self.parent:
            return self.parent.lookup(name)
        raise NameError(f"unbound name: {name!r}")

    def define(self, name: str, value: Any) -> None:
        self.bindings[name] = value

    def child(self) -> "Environment":
        return Environment(parent=self)


class ExecutionContext:
    """Per-evaluation state: state stack + environment + (future) speculation."""

    def __init__(self):
        self.state_stack: List[Dict[str, Any]] = []
        self.env: Environment = Environment()


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


def _recover_trivial(node: NodeID, session=None) -> Any:
    """Recover the runtime value of a trivial-leaf NodeID.

    Form's IntLit/BoolLit/StringLit/NullLit AST nodes encode their values as
    the instance integer of a Level.TRIVIAL NodeID. This reverses that encoding.

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


_UNRECOVERABLE = object()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def eval_recipe(
    session: Session,
    node: NodeID,
    ctx: Optional[ExecutionContext] = None,
) -> Any:
    """Evaluate a Recipe NodeID against the substrate.

    The interpreter:
    1. Tries to recover the node as a trivial leaf (int/bool/null).
    2. Looks up the row; if missing, treats the node as an opaque value.
    3. Parses the serialized payload to get the category + child NodeIDs.
    4. Dispatches on category's (type_, instance).

    Cell-aware and external-engine constructs (delegate, method, common,
    on_change, project) return the recipe NodeID itself unchanged — the
    interpreter is honest about which constructs it activates and which
    remain in specialized engines.
    """
    if ctx is None:
        ctx = ExecutionContext()

    # Trivial leaf — recoverable directly from the NodeID coordinates.
    # Pass session so StringLit instances can resolve via the string-table.
    recovered = _recover_trivial(node, session=session)
    if recovered is not _UNRECOVERABLE:
        return recovered

    # Bare-leaf primitives (CHOICE/STATE/EXCEPTION with no children) live as
    # pure NodeIDs without rows in substrate_nodes — the kernel doesn't intern
    # trivial-level leaves. Dispatch them by category directly before the
    # row fallback.
    if node.level == Level.BASIC and not _has_children_in_substrate(session, node):
        leaf = _dispatch_bare_leaf(node, ctx)
        if leaf is not _UNRECOVERABLE:
            return leaf

    # Lookup row; if there's no row, return the NodeID unchanged
    # (it might be a cell-ref, a string-literal, or other un-interpreted shape).
    row = lookup_node(session, node)
    if row is None or not row.serialized:
        return node

    category, children = _parse_serialized(row.serialized)

    return _dispatch(session, category, children, ctx, node)


def _has_children_in_substrate(session: Session, node: NodeID) -> bool:
    """A composite node has a row with `serialized` containing `+`."""
    row = lookup_node(session, node)
    return row is not None and row.serialized and "+" in row.serialized


def _dispatch_bare_leaf(node: NodeID, ctx: ExecutionContext) -> Any:
    """Bare-leaf primitives: choose/fail/stop, save/restore/discard, raise/resume.

    These intern as bare category NodeIDs without children rows. Dispatch them
    here so the runtime semantics fires even though the substrate has no row.
    """
    if node.type_ == RBasic.CHOICE:
        if node.instance == RChoice.FAIL:
            raise FailSignal()
        if node.instance == RChoice.STOP:
            raise StopSignal()
    if node.type_ == RBasic.STATE:
        return _eval_state(node.instance, ctx)
    if node.type_ == RBasic.EXCEPTION:
        if node.instance == RException.RAISE:
            raise RaiseSignal()
        if node.instance == RException.RESUME:
            return None  # resume on its own is a marker
    return _UNRECOVERABLE


def _dispatch(
    session: Session,
    category: NodeID,
    children: List[NodeID],
    ctx: ExecutionContext,
    self_node: NodeID,
) -> Any:
    # Math
    if category.level == Level.BASIC and category.type_ == RBasic.MATH:
        return _eval_math(session, category.instance, children, ctx)

    # Compare
    if category.level == Level.BASIC and category.type_ == RBasic.COMPARE:
        return _eval_compare(session, category.instance, children, ctx)

    # Logic
    if category.level == Level.BASIC and category.type_ == RBasic.LOGIC:
        return _eval_logic(session, category.instance, children, ctx)

    # Cond (if-then / if-then-else)
    if category.level == Level.BASIC and category.type_ == RBasic.COND:
        return _eval_cond(session, category.instance, children, ctx)

    # Block (do-sequence / let-binding)
    if category.level == Level.BASIC and category.type_ == RBasic.BLOCK:
        return _eval_block(session, category.instance, children, ctx)

    # State stack — save / restore / discard
    if category.level == Level.BASIC and category.type_ == RBasic.STATE:
        return _eval_state(category.instance, ctx)

    # Exception flow — raise / resume
    if category.level == Level.BASIC and category.type_ == RBasic.EXCEPTION:
        return _eval_exception(session, category.instance, children, ctx)

    # Choice — fail / stop signal as exceptions
    if category.level == Level.BASIC and category.type_ == RBasic.CHOICE:
        if category.instance == RChoice.FAIL:
            raise FailSignal()
        if category.instance == RChoice.STOP:
            raise StopSignal()

    # Cell-aware / external-engine constructs (delegate, method, common,
    # reactive, projection, resonance) return the NodeID unchanged — those
    # need their specialized engines (dispatch walker, method binder,
    # subscription engine, renderer respectively).
    return self_node


def _eval_math(session: Session, instance: int, children: List[NodeID], ctx: ExecutionContext) -> Any:
    vals = [eval_recipe(session, c, ctx) for c in children]
    if instance == RMath.PLUS:
        return vals[0] + vals[1]
    if instance == RMath.MINUS:
        return vals[0] - vals[1]
    if instance == RMath.MULTIPLY:
        return vals[0] * vals[1]
    if instance == RMath.DIVIDE:
        return vals[0] / vals[1]
    if instance == RMath.MODULO:
        return vals[0] % vals[1]
    if instance == RMath.NEGATE:
        return -vals[0]
    raise ValueError(f"recipe_eval: unknown math instance {instance}")


def _eval_compare(session: Session, instance: int, children: List[NodeID], ctx: ExecutionContext) -> bool:
    a = eval_recipe(session, children[0], ctx)
    b = eval_recipe(session, children[1], ctx)
    if instance == RCompare.EQUAL:
        return a == b
    if instance == RCompare.NOT_EQUAL:
        return a != b
    if instance == RCompare.LESS:
        return a < b
    if instance == RCompare.LESS_EQUAL:
        return a <= b
    if instance == RCompare.GREATER:
        return a > b
    if instance == RCompare.GREATER_EQUAL:
        return a >= b
    raise ValueError(f"recipe_eval: unknown compare instance {instance}")


def _eval_logic(session: Session, instance: int, children: List[NodeID], ctx: ExecutionContext) -> bool:
    if instance == RLogic.NOT:
        return not eval_recipe(session, children[0], ctx)
    a = eval_recipe(session, children[0], ctx)
    if instance == RLogic.AND:
        return bool(a) and bool(eval_recipe(session, children[1], ctx))
    if instance == RLogic.OR:
        return bool(a) or bool(eval_recipe(session, children[1], ctx))
    raise ValueError(f"recipe_eval: unknown logic instance {instance}")


def _eval_cond(session: Session, instance: int, children: List[NodeID], ctx: ExecutionContext) -> Any:
    cond = eval_recipe(session, children[0], ctx)
    if instance == RCond.IF_THEN:
        if cond:
            return eval_recipe(session, children[1], ctx)
        return None
    if instance == RCond.IF_THEN_ELSE:
        if cond:
            return eval_recipe(session, children[1], ctx)
        return eval_recipe(session, children[2], ctx)
    raise ValueError(f"recipe_eval: unknown cond instance {instance}")


def _eval_block(session: Session, instance: int, children: List[NodeID], ctx: ExecutionContext) -> Any:
    if instance == RBlock.DO or instance == RBlock.SEQUENCE:
        # Evaluate statements in order, returning the last value.
        result = None
        try:
            for c in children:
                result = eval_recipe(session, c, ctx)
        except StopSignal:
            pass  # `stop` commits the in-flight value
        return result
    if instance == RBlock.LET:
        # children = [name-string-recipe, value-recipe]
        # Name recovery uses the string-table; if unrecoverable, skip binding.
        from app.services.substrate.substrate_strings import lookup_string_value
        name_node = children[0]
        value = eval_recipe(session, children[1], ctx)
        if name_node.type_ == RType.STRING:
            name = lookup_string_value(session, name_node.instance)
            if name is not None:
                ctx.env.define(name, value)
        return value
    if instance == RBlock.WITH:
        # subject-recipe + body-recipe
        # Evaluate the body in a child environment with `.self` bound to subject.
        subject = eval_recipe(session, children[0], ctx)
        old_env = ctx.env
        ctx.env = ctx.env.child()
        ctx.env.define("__self__", subject)
        try:
            return eval_recipe(session, children[1], ctx)
        finally:
            ctx.env = old_env
    raise ValueError(f"recipe_eval: unknown block instance {instance}")


def _eval_state(instance: int, ctx: ExecutionContext) -> Any:
    if instance == RState.SAVE:
        ctx.state_stack.append(dict(ctx.env.bindings))
        return None
    if instance == RState.RESTORE:
        if not ctx.state_stack:
            raise IndexError("recipe_eval: restore with empty state stack")
        ctx.env.bindings = ctx.state_stack.pop()
        return None
    if instance == RState.DISCARD:
        if not ctx.state_stack:
            raise IndexError("recipe_eval: discard with empty state stack")
        ctx.state_stack.pop()
        return None
    raise ValueError(f"recipe_eval: unknown state instance {instance}")


def _eval_exception(session: Session, instance: int, children: List[NodeID], ctx: ExecutionContext) -> Any:
    if instance == RException.RAISE:
        payload = eval_recipe(session, children[0], ctx) if children else None
        raise RaiseSignal(payload)
    if instance == RException.RESUME:
        # Resume is a marker; on its own it has no effect outside a try/catch.
        # When the recipe-execution engine grows try-frames, RESUME will return
        # control to the most-recent catch point with the supplied value.
        return eval_recipe(session, children[0], ctx) if children else None
    raise ValueError(f"recipe_eval: unknown exception instance {instance}")


# ---------------------------------------------------------------------------
# Convenience: evaluate a Form text directly
# ---------------------------------------------------------------------------


def eval_text(session: Session, text: str) -> Any:
    """Parse + intern + evaluate a Form expression. Returns the runtime value."""
    from app.services.substrate.form import evaluate_text as form_evaluate_text

    result = form_evaluate_text(session, text)
    if result.kind == "recipe":
        return eval_recipe(session, result.value)
    if result.kind == "node_id":
        # Already a NodeID literal — try to recover, else return as-is.
        recovered = _recover_trivial(result.value, session=session)
        if recovered is not _UNRECOVERABLE:
            return recovered
        return eval_recipe(session, result.value)
    # Cells, views, lattice, keywords, vocabulary — return as-is.
    return result.value


__all__ = [
    "Environment",
    "ExecutionContext",
    "FailSignal",
    "RaiseSignal",
    "StopSignal",
    "eval_recipe",
    "eval_text",
]
