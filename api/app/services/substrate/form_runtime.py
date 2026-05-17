"""Recipe-execution engine — Form expressions running, not just interned.

Until now the substrate held Form expressions as content-addressed Recipe
NodeIDs but had no engine that turned a recipe into a value. `1 + 2`
interned successfully; nothing computed `3`. `with X { .self }` interned
successfully; `.self` had nowhere to resolve. `choose [a, b, c]` interned
successfully; speculation lived only at the parser layer.

This module is that engine. It walks Form ASTs (the in-memory tree the
parser produces, which carries full-fidelity literal values and names)
and returns Python values. The Recipe NodeID remains the content-
addressed signature alongside — two expressions that compute the same
shape share one NodeID; their values are computed by walking the AST,
which is the natural runtime IR (the same separation Python makes
between bytecode and its hash).

Connection to parser-level speculation: this engine re-uses
`FailSignal` and `StopSignal` from form_speculation. `fail` and `stop`
inside `choose` flow through the same exceptions parser-level
speculation uses. The Choice.FAIL / Choice.STOP recipe categories that
the substrate has been storing for shapes finally have a runtime that
catches them.

What this closes:

- Self-executing — Form expressions run, not just intern
- `.self` runtime resolution — WithExpr binds subject in a Frame; SelfRef walks up the chain
- FailSignal/StopSignal flow through Choice recipes at runtime, not just parser-time

What stays a future breath:

- Persistent name resolution from cells (let-bound names live in the
  Frame; cell-domain symbols are looked up via CellRef at evaluation
  time; integrating these two name spaces is its own pass)
- Recipe-NodeID → AST round-trip evaluation (the engine walks the AST;
  walking the serialized recipe directly requires resolving hashed
  string instances back via substrate_strings — own breath)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.substrate.form import (
    Access,
    BoolLit,
    CellRef,
    ChooseExpr,
    DoBlock,
    FailExpr,
    FnCall,
    FnDef,
    Identifier,
    IfExpr,
    IntLit,
    Let,
    MatchArm,
    MatchExpr,
    MethodCall,
    NodeIDLit,
    Projection,
    SelfRef,
    StopExpr,
    StringLit,
    TrivialRef,
    UnaryOp,
    BinOp,
    TRIVIAL_REFS,
    DOMAIN_TO_REF,
    WithExpr,
    parse as form_parse,
)
from app.services.substrate.form_speculation import FailSignal, StopSignal
from app.services.substrate.kernel import NodeID, lookup_cell, view_cell_through_blueprint


# ---------------------------------------------------------------------------
# Frame — lexical scope
# ---------------------------------------------------------------------------


@dataclass
class Closure:
    """A runtime function value — captured params + body + defining frame.

    `defining_frame` is the lexical scope active when the closure was
    created. A call pushes a child frame parented at `defining_frame`,
    not at the caller's frame — that is the closure rule. The function's
    own name is visible inside its body so recursion works without a
    separate `rec` form (we register the closure in `defining_frame`
    before evaluating the body).
    """

    name: str
    params: List[str]
    body: Any
    defining_frame: "Frame"


@dataclass
class Frame:
    """A lexical scope.

    `bindings` holds names introduced by `let`. `subject` holds the
    implicit receiver of a `with` block (read by `.self`). Frames chain
    via `parent` to form a scope walk.
    """

    bindings: Dict[str, Any] = field(default_factory=dict)
    subject: Any = None
    has_subject: bool = False
    parent: Optional["Frame"] = None

    def lookup(self, name: str) -> Any:
        f: Optional[Frame] = self
        while f is not None:
            if name in f.bindings:
                return f.bindings[name]
            f = f.parent
        raise NameError(f"Form runtime: unbound name {name!r}")

    def has(self, name: str) -> bool:
        f: Optional[Frame] = self
        while f is not None:
            if name in f.bindings:
                return True
            f = f.parent
        return False

    def nearest_subject(self) -> Any:
        f: Optional[Frame] = self
        while f is not None:
            if f.has_subject:
                return f.subject
            f = f.parent
        raise NameError("Form runtime: .self used outside a `with` block")


# Singleton used when no caller-provided frame exists.
def _root_frame() -> Frame:
    return Frame()


# ---------------------------------------------------------------------------
# Built-in identifier resolution
# ---------------------------------------------------------------------------


_BUILTIN_IDENTIFIERS: Dict[str, Any] = {
    "true": True,
    "false": False,
    "null": None,
}


# ---------------------------------------------------------------------------
# execute — walk the AST
# ---------------------------------------------------------------------------


def execute(session: Session, ast: Any, frame: Optional[Frame] = None) -> Any:
    """Walk a Form AST and return a Python value.

    Raises:
        FailSignal: when a `fail` expression evaluates outside a `choose`
        StopSignal: when a `stop` evaluates and bubbles past the nearest choose
        NameError, TypeError, ZeroDivisionError, ...: normal Python errors
    """
    if frame is None:
        frame = _root_frame()

    # --- Leaves with full value fidelity ------------------------------------

    if isinstance(ast, IntLit):
        return ast.value
    if isinstance(ast, BoolLit):
        return ast.value
    if isinstance(ast, StringLit):
        return ast.value

    if isinstance(ast, Identifier):
        if ast.name in _BUILTIN_IDENTIFIERS:
            return _BUILTIN_IDENTIFIERS[ast.name]
        return frame.lookup(ast.name)

    if isinstance(ast, NodeIDLit):
        return NodeID(ast.package, ast.level, ast.type_, ast.instance)

    if isinstance(ast, TrivialRef):
        nid = TRIVIAL_REFS.get(ast.name)
        if nid is None:
            raise NameError(f"Form runtime: unknown trivial ~{ast.name}")
        return nid

    if isinstance(ast, CellRef):
        if ast.name is None:
            ref_name = DOMAIN_TO_REF.get(ast.domain)
            if ref_name is None:
                raise NameError(f"Form runtime: unknown domain @{ast.domain}")
            return TRIVIAL_REFS[ref_name]
        cell = lookup_cell(session, ast.domain, ast.name)
        if cell is None:
            raise LookupError(f"Form runtime: cell ({ast.domain}, {ast.name}) not found")
        return cell

    # --- .self ---------------------------------------------------------------

    if isinstance(ast, SelfRef):
        return frame.nearest_subject()

    # --- Operators -----------------------------------------------------------

    if isinstance(ast, BinOp):
        # Short-circuit for && and ||
        if ast.op == "&&":
            l = execute(session, ast.left, frame)
            if not l:
                return l
            return execute(session, ast.right, frame)
        if ast.op == "||":
            l = execute(session, ast.left, frame)
            if l:
                return l
            return execute(session, ast.right, frame)
        left = execute(session, ast.left, frame)
        right = execute(session, ast.right, frame)
        return _apply_binop(ast.op, left, right)

    if isinstance(ast, UnaryOp):
        value = execute(session, ast.operand, frame)
        return _apply_unop(ast.op, value)

    # --- Control flow --------------------------------------------------------

    if isinstance(ast, IfExpr):
        cond = execute(session, ast.cond, frame)
        if cond:
            return execute(session, ast.then_branch, frame)
        if ast.else_branch is not None:
            return execute(session, ast.else_branch, frame)
        return None

    if isinstance(ast, DoBlock):
        sub = Frame(parent=frame)
        result: Any = None
        for stmt in ast.statements:
            result = execute(session, stmt, sub)
        return result

    if isinstance(ast, Let):
        value = execute(session, ast.value, frame)
        frame.bindings[ast.name] = value
        return value

    if isinstance(ast, MatchExpr):
        scrut = execute(session, ast.scrutinee, frame)
        for arm in ast.arms:
            if _is_wildcard(arm.pattern):
                return execute(session, arm.body, frame)
            pat_value = execute(session, arm.pattern, frame)
            if pat_value == scrut:
                return execute(session, arm.body, frame)
        return None

    # --- Speculation ---------------------------------------------------------

    if isinstance(ast, ChooseExpr):
        for candidate in ast.candidates:
            try:
                return execute(session, candidate, frame)
            except FailSignal:
                continue
            except StopSignal:
                # `stop` inside this candidate — the speculation is
                # locked but the choose still returns. StopSignal does
                # NOT propagate past its enclosing choose; bubbling past
                # would require a deeper unwind primitive.
                return None
        raise FailSignal("Form runtime: all `choose` candidates failed")

    if isinstance(ast, FailExpr):
        raise FailSignal("Form runtime: `fail`")

    if isinstance(ast, StopExpr):
        raise StopSignal("Form runtime: `stop`")

    # --- with / projection ---------------------------------------------------

    if isinstance(ast, WithExpr):
        subject = execute(session, ast.subject, frame)
        sub = Frame(parent=frame, subject=subject, has_subject=True)
        return execute(session, ast.body, sub)

    # --- Functions ----------------------------------------------------------

    if isinstance(ast, FnDef):
        closure = Closure(
            name=ast.name,
            params=list(ast.params),
            body=ast.body,
            defining_frame=frame,
        )
        frame.bindings[ast.name] = closure
        return closure

    if isinstance(ast, FnCall):
        callable_value = frame.lookup(ast.name)
        if not isinstance(callable_value, Closure):
            raise TypeError(
                f"Form runtime: `{ast.name}` is not callable "
                f"(got {type(callable_value).__name__})"
            )
        if len(ast.args) != len(callable_value.params):
            raise TypeError(
                f"Form runtime: `{ast.name}` takes {len(callable_value.params)} arg(s), "
                f"got {len(ast.args)}"
            )
        # Evaluate arguments in the CALLER's frame, then bind them in a
        # fresh frame parented at the closure's defining frame.
        evaluated = [execute(session, a, frame) for a in ast.args]
        call_frame = Frame(parent=callable_value.defining_frame)
        for param_name, value in zip(callable_value.params, evaluated):
            call_frame.bindings[param_name] = value
        return execute(session, callable_value.body, call_frame)

    if isinstance(ast, Projection):
        cell = execute(session, ast.cell, frame)
        bp = execute(session, ast.blueprint, frame)
        if not isinstance(bp, NodeID):
            raise TypeError("Form runtime: |> requires a NodeID on the right")
        # Allow both a NamedCell and a bare NodeID on the left (the latter
        # is meaningful when a cell-by-id is supplied).
        if isinstance(cell, NodeID):
            raise TypeError(
                "Form runtime: |> on a bare NodeID requires a cell lookup "
                "(use @<domain>(<name>) on the left)"
            )
        return view_cell_through_blueprint(session, cell, bp)

    # --- Tree navigation — the fractal/holographic seams --------------------
    #
    # The substrate composes every entity bottom-up: a Cell holds a
    # Blueprint NodeID + a CTOR Recipe NodeID; each of those is itself a
    # tree (category + ordered children). `.field` is the syntax that
    # makes that tree navigable. The point: structure stays as tree, not
    # flattened to slug or object.

    if isinstance(ast, Access):
        target = execute(session, ast.target, frame)
        return _resolve_access(session, target, ast.field)

    if isinstance(ast, MethodCall):
        target = execute(session, ast.target, frame)
        evaluated_args = [execute(session, a, frame) for a in ast.args]
        return _resolve_method(session, target, ast.method, evaluated_args)

    raise TypeError(f"Form runtime: cannot execute {type(ast).__name__}")


# ---------------------------------------------------------------------------
# Tree navigation helpers
# ---------------------------------------------------------------------------


def _resolve_access(session: Session, target: Any, field: str) -> Any:
    """Field access on a Cell, Blueprint NodeID, or Recipe NodeID.

    Cells expose: blueprint, ctor, base, access, name, domain, source.
    NodeIDs expose: package, level, type_, instance, category, children.
    """
    from app.services.substrate.kernel import NamedCell, lookup_node

    if isinstance(target, NamedCell):
        if field == "blueprint":
            return target.blueprint
        if field == "ctor":
            return target.ctor
        if field == "base":
            return target.base
        if field == "access":
            return target.access
        if field == "name":
            return target.name
        if field == "domain":
            return target.domain
        if field == "source":
            return target.source_path
        raise AttributeError(
            f"Form runtime: cell has no field {field!r} "
            f"(try: blueprint, ctor, base, access, name, domain, source)"
        )

    if isinstance(target, NodeID):
        if field == "package":
            return target.package
        if field == "level":
            return target.level
        if field == "type_" or field == "type":
            return target.type_
        if field == "instance":
            return target.instance
        if field == "category":
            return _node_category(session, target)
        if field == "children":
            return _node_children(session, target)
        if field == "nchildren":
            return len(_node_children(session, target))
        raise AttributeError(
            f"Form runtime: NodeID has no field {field!r} "
            f"(try: package, level, type, instance, category, children, nchildren)"
        )

    raise TypeError(
        f"Form runtime: cannot access .{field} on {type(target).__name__}"
    )


def _resolve_method(session: Session, target: Any, method: str, args: List[Any]) -> Any:
    """Method-call on a Cell, Blueprint, or Recipe — currently `child(n)`.

    `.child(n)` returns the n-th child NodeID. Out-of-range raises.
    """
    if isinstance(target, NodeID):
        if method == "child":
            if len(args) != 1 or not isinstance(args[0], int):
                raise TypeError("Form runtime: .child(n) takes one integer arg")
            children = _node_children(session, target)
            n = args[0]
            if n < 0 or n >= len(children):
                raise IndexError(
                    f"Form runtime: .child({n}) out of range "
                    f"(have {len(children)} children)"
                )
            return children[n]
    raise TypeError(
        f"Form runtime: cannot call .{method}() on {type(target).__name__}"
    )


def _node_category(session: Session, nid: NodeID) -> NodeID:
    """The category of a NodeID. For trivials, the node IS its category.
    For composites, parse the substrate row's serialized form."""
    from app.services.substrate.kernel import lookup_node

    row = lookup_node(session, nid)
    if row is None or not row.serialized:
        return nid  # trivial — category is itself
    parts = row.serialized.split("+")
    if len(parts) <= 1:
        return nid
    return _parse_nodeid(parts[0])


def _node_children(session: Session, nid: NodeID) -> List[NodeID]:
    """Ordered children of a composite NodeID. Empty list for trivials."""
    from app.services.substrate.kernel import lookup_node

    row = lookup_node(session, nid)
    if row is None or not row.serialized:
        return []
    parts = row.serialized.split("+")
    if len(parts) <= 1:
        return []
    return [_parse_nodeid(p) for p in parts[1:]]


def _parse_nodeid(s: str) -> NodeID:
    """`'1.5.4.1'` → NodeID(1, 5, 4, 1)."""
    a, b, c, d = s.split(".")
    return NodeID(int(a), int(b), int(c), int(d))


# ---------------------------------------------------------------------------
# Operator application
# ---------------------------------------------------------------------------


def _apply_binop(op: str, left: Any, right: Any) -> Any:
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return left / right if isinstance(left, float) or isinstance(right, float) else left // right
    if op == "%":
        return left % right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    raise SyntaxError(f"Form runtime: unknown binary op {op!r}")


def _apply_unop(op: str, value: Any) -> Any:
    if op == "-":
        return -value
    if op == "!":
        return not value
    raise SyntaxError(f"Form runtime: unknown unary op {op!r}")


def _is_wildcard(pattern: Any) -> bool:
    return isinstance(pattern, Identifier) and pattern.name == "_"


# ---------------------------------------------------------------------------
# Top-level: parse + execute
# ---------------------------------------------------------------------------


def form_execute_text(
    session: Session,
    text: str,
    *,
    frame: Optional[Frame] = None,
    prefer_registered: bool = False,
) -> Any:
    """Parse a Form expression and run it. Returns the computed value.

    The substrate session is passed through so cell lookups (`@<domain>(<name>)`)
    and any future substrate-touching operations work.
    """
    ast = form_parse(text, prefer_registered=prefer_registered)
    return execute(session, ast, frame=frame)
