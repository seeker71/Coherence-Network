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
    CommonExpr,
    DelegateExpr,
    DiscardExpr,
    DoBlock,
    FailExpr,
    FnCall,
    FnDef,
    Identifier,
    DictExpr,
    ForExpr,
    IfExpr,
    SetExpr,
    InverseExpr,
    IntLit,
    IndexExpr,
    Let,
    MatchExpr,
    MethodCall,
    MethodDefExpr,
    MethodInvokeExpr,
    NodeIDLit,
    OnChangeExpr,
    ProjectExpr,
    Projection,
    RaiseExpr,
    RestoreExpr,
    ResumeExpr,
    SaveExpr,
    SelfRef,
    StopExpr,
    StringLit,
    TernaryExpr,
    TrivialRef,
    TryCatchExpr,
    UnaryOp,
    UndoExpr,
    BinOp,
    TRIVIAL_REFS,
    DOMAIN_TO_REF,
    WhileExpr,
    WithExpr,
    parse as form_parse,
)
from app.services.substrate.form_speculation import FailSignal, StopSignal
from app.services.substrate.kernel import (
    NodeID,
    lookup_cell,
    register_mutation_callback as _register_mc,
    view_cell_through_blueprint,
)


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

    def define(self, name: str, value: Any) -> None:
        """Bind `name` in this frame's local bindings — used by `let` and by
        tests that operate on a frame directly without going through AST."""
        self.bindings[name] = value

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
# Runtime registries — specialized engines for cell-aware constructs
# ---------------------------------------------------------------------------
#
# Each registry maps a structural key (cell-pair, method-on-cell, watched
# recipe) to its runtime behavior. The form-layer constructs (delegate,
# method def/invoke, common, on_change, project) read/write these registries
# at execute-time. Module-level for simplicity; session-scoped would isolate
# multi-tenant work but isn't load-bearing yet.


class RaiseSignal(Exception):
    """`raise` evaluates here — caught by the next try-frame or surfaces."""

    def __init__(self, payload: Any = None):
        super().__init__(payload)
        self.payload = payload


# Method definitions: (cell_domain, cell_name, method_name) -> body AST
_METHOD_REGISTRY: Dict[tuple, Any] = {}

# Delegation: (cell_domain, cell_name) -> (target_domain, target_name)
_DELEGATE_REGISTRY: Dict[tuple, tuple] = {}

# Common bases: list of frozensets representing equivalence classes of cells.
_COMMON_GROUPS: List[frozenset] = []

# Reactive subscriptions: list of (watched_value_snapshot, body_ast, frame).
# fire_subscriptions() re-evaluates each watched recipe and fires bodies
# whose value changed.
_SUBSCRIPTIONS: List[Dict[str, Any]] = []

# Coordinate functions for spatial-projection rendering.
# Registered by `register_coord_fn(name, callable)`; looked up by ProjectExpr.
_COORD_FNS: Dict[str, Any] = {}


def register_coord_fn(name: str, fn: Any) -> None:
    """Register a coordinate function for `?project @cell @<name>` rendering."""
    _COORD_FNS[name] = fn


def fire_subscriptions(session: Session) -> List[Any]:
    """Re-evaluate every watched recipe; fire bodies whose value changed.

    Returns the list of fired-body results. Auto-called after every substrate
    mutation via kernel's mutation-callback registry (see `_auto_fire_callback`
    below). Callable directly for manual fire.
    """
    results = []
    # Snapshot in case fired bodies mutate the subscription list.
    for sub in list(_SUBSCRIPTIONS):
        try:
            new_value = execute(session, sub["query"], sub["frame"])
        except Exception:
            # Subscription whose watched query errors stays subscribed but
            # contributes nothing this round — keeps the reactive layer
            # tolerant of transient eval failures.
            continue
        if new_value != sub["last"]:
            sub["last"] = new_value
            results.append(execute(session, sub["body"], sub["frame"]))
    return results


# Re-entry guard: mutation callbacks fire on every intern_node / make_cell.
# When fire_subscriptions itself causes a mutation (e.g. a fired body interns
# new recipes), we would re-enter recursively. The guard short-circuits to
# break the loop.
_FIRING = False


def _auto_fire_callback(session: Session) -> None:
    """Kernel mutation hook — re-fires subscriptions whose watched query changed.

    Registered on module import so any `intern_node` or `make_cell` call
    automatically pushes reactive bodies. The `_FIRING` guard prevents
    recursive re-entry when fired bodies themselves intern recipes.
    """
    global _FIRING
    if _FIRING or not _SUBSCRIPTIONS:
        return
    _FIRING = True
    try:
        fire_subscriptions(session)
    finally:
        _FIRING = False


# Auto-register on module import so reactive lenses fire without callers
# needing to wire up the callback explicitly.
_register_mc(_auto_fire_callback)


def reset_runtime_registries() -> None:
    """Test-helper: clear method/delegate/common/subscription/coord-fn state."""
    _METHOD_REGISTRY.clear()
    _DELEGATE_REGISTRY.clear()
    _COMMON_GROUPS.clear()
    _SUBSCRIPTIONS.clear()
    _COORD_FNS.clear()


def _cell_key(cell: Any) -> Optional[tuple]:
    """`(domain, name)` key for a NamedCell (or any object exposing those attrs)."""
    if hasattr(cell, "domain") and hasattr(cell, "name"):
        return (cell.domain, cell.name)
    return None


def _delegate_chain(start_key: tuple) -> List[tuple]:
    """Walk the delegation chain starting at `start_key`.

    Yields (domain, name) pairs in order: start, target, target-of-target, ...
    Stops on cycle or when no further delegate is registered.
    """
    chain = [start_key]
    seen = {start_key}
    current = start_key
    while current in _DELEGATE_REGISTRY:
        target = _DELEGATE_REGISTRY[current]
        if target in seen:
            break
        chain.append(target)
        seen.add(target)
        current = target
    return chain


def _common_peers(key: tuple) -> set:
    """All cells sharing a common-base group with `key`."""
    for group in _COMMON_GROUPS:
        if key in group:
            return set(group) - {key}
    return set()


# ---------------------------------------------------------------------------
# Built-in identifier resolution
# ---------------------------------------------------------------------------


_BUILTIN_IDENTIFIERS: Dict[str, Any] = {
    "true": True,
    "false": False,
    "null": None,
}


# Built-in functions — invokable from FnCall when the name isn't bound to a Closure.
# Each value is a Python callable receiving the evaluated positional args.
def _builtin_map(fn, xs):
    if not isinstance(xs, list):
        raise TypeError("Form runtime: map expects a list as second argument")
    if isinstance(fn, Closure):
        return [_invoke_closure(fn, [x]) for x in xs]
    if callable(fn):
        return [fn(x) for x in xs]
    raise TypeError("Form runtime: map expects a callable as first argument")


def _builtin_filter(pred, xs):
    if not isinstance(xs, list):
        raise TypeError("Form runtime: filter expects a list as second argument")
    if isinstance(pred, Closure):
        return [x for x in xs if _invoke_closure(pred, [x])]
    if callable(pred):
        return [x for x in xs if pred(x)]
    raise TypeError("Form runtime: filter expects a callable as first argument")


def _builtin_fold(fn, init, xs):
    if not isinstance(xs, list):
        raise TypeError("Form runtime: fold expects a list as third argument")
    acc = init
    if isinstance(fn, Closure):
        for x in xs:
            acc = _invoke_closure(fn, [acc, x])
        return acc
    if callable(fn):
        for x in xs:
            acc = fn(acc, x)
        return acc
    raise TypeError("Form runtime: fold expects a callable as first argument")


def _invoke_closure(closure: "Closure", args: list) -> Any:
    """Helper: invoke a Form Closure (with proper frame chaining) from a built-in.

    Pulls the active session out via a module-level slot the execute() loop
    populates before each call. This keeps the built-in API session-agnostic
    while still allowing closures (which need the session for substrate ops)
    to execute correctly.
    """
    if len(args) != len(closure.params):
        raise TypeError(
            f"Form runtime: closure `{closure.name}` takes {len(closure.params)} arg(s), "
            f"got {len(args)}"
        )
    call_frame = Frame(parent=closure.defining_frame)
    for name, value in zip(closure.params, args):
        call_frame.bindings[name] = value
    sess = _CURRENT_SESSION[0]
    if sess is None:
        raise RuntimeError("Form runtime: no active session for closure invocation")
    return execute(sess, closure.body, call_frame)


# Per-call session slot for built-ins that invoke closures.
_CURRENT_SESSION: list = [None]


def _builtin_category(nid: Any) -> Any:
    """`category(r)` — return the category NodeID of a Recipe NodeID.

    For composite recipes, returns the category-NodeID embedded in the
    serialized row. For trivial leaves, the node IS its own category
    (the coordinate carries the type/instance directly).

    This is the load-bearing recipe-introspection primitive: with it,
    Form code can dispatch on category and walk recipes recursively —
    the meta-circular evaluator-in-Form (form-engine.form) can finally
    express what the Python evaluator does."""
    sess = _CURRENT_SESSION[0]
    if sess is None:
        raise RuntimeError("Form runtime: category() requires an active session")
    if not isinstance(nid, NodeID):
        raise TypeError(
            f"Form runtime: category() expects a NodeID, got {type(nid).__name__}"
        )
    return _node_category(sess, nid)


def _builtin_nchildren(nid: Any) -> int:
    """`nchildren(r)` — arity of a composite Recipe NodeID. Zero for trivials."""
    sess = _CURRENT_SESSION[0]
    if sess is None:
        raise RuntimeError("Form runtime: nchildren() requires an active session")
    if not isinstance(nid, NodeID):
        raise TypeError(
            f"Form runtime: nchildren() expects a NodeID, got {type(nid).__name__}"
        )
    return len(_node_children(sess, nid))


def _builtin_child(nid: Any, index: Any) -> NodeID:
    """`child(r, n)` — n-th child Recipe NodeID of a composite."""
    sess = _CURRENT_SESSION[0]
    if sess is None:
        raise RuntimeError("Form runtime: child() requires an active session")
    if not isinstance(nid, NodeID):
        raise TypeError(
            f"Form runtime: child() expects a NodeID as first arg, got {type(nid).__name__}"
        )
    if not isinstance(index, int):
        raise TypeError(
            f"Form runtime: child() expects an integer index, got {type(index).__name__}"
        )
    kids = _node_children(sess, nid)
    if index < 0 or index >= len(kids):
        raise IndexError(
            f"Form runtime: child({nid}, {index}) — recipe has {len(kids)} child(ren)"
        )
    return kids[index]


def _builtin_integer_value(nid: Any) -> int:
    """`integer_value(r)` — decode a trivial INTEGER Recipe NodeID to its int.

    The companion primitive to `category`/`nchildren`/`child`: once the
    evaluator has descended to a leaf, this pulls the actual int value
    out of the coordinate so arithmetic can happen."""
    sess = _CURRENT_SESSION[0]
    if sess is None:
        raise RuntimeError("Form runtime: integer_value() requires an active session")
    if not isinstance(nid, NodeID):
        raise TypeError(
            f"Form runtime: integer_value() expects a NodeID, got {type(nid).__name__}"
        )
    v = _trivial_value(sess, nid)
    if not isinstance(v, int) or isinstance(v, bool):
        raise TypeError(
            f"Form runtime: integer_value() expected an integer trivial, got {type(v).__name__}"
        )
    return v


def _builtin_string_value(nid: Any) -> str:
    """`string_value(r)` — decode a trivial STRING Recipe NodeID to its str."""
    sess = _CURRENT_SESSION[0]
    if sess is None:
        raise RuntimeError("Form runtime: string_value() requires an active session")
    if not isinstance(nid, NodeID):
        raise TypeError(
            f"Form runtime: string_value() expects a NodeID, got {type(nid).__name__}"
        )
    v = _trivial_value(sess, nid)
    if not isinstance(v, str):
        raise TypeError(
            f"Form runtime: string_value() expected a string trivial, got {type(v).__name__}"
        )
    return v


def _builtin_bool_value(nid: Any) -> bool:
    """`bool_value(r)` — decode a trivial BOOL Recipe NodeID to its bool."""
    sess = _CURRENT_SESSION[0]
    if sess is None:
        raise RuntimeError("Form runtime: bool_value() requires an active session")
    if not isinstance(nid, NodeID):
        raise TypeError(
            f"Form runtime: bool_value() expects a NodeID, got {type(nid).__name__}"
        )
    v = _trivial_value(sess, nid)
    if not isinstance(v, bool):
        raise TypeError(
            f"Form runtime: bool_value() expected a bool trivial, got {type(v).__name__}"
        )
    return v


def _builtin_file_exists(path: Any) -> bool:
    """Does the file at `path` exist on disk?

    Form predicate for spec recipes — `done_when: - form: file_exists("X")`.
    The result is content-addressed by the runtime, so two evaluations of
    the same expression intern to the same Recipe NodeID. The substrate's
    cache IS the body's persistent record of "what does this assertion
    return for this path."
    """
    from pathlib import Path as _Path
    if not isinstance(path, str):
        raise TypeError(f"file_exists: path must be string, got {type(path).__name__}")
    return _Path(path).exists()


def _builtin_file_contains(path: Any, needle: Any) -> bool:
    """Does the file at `path` contain the substring `needle`?

    The honest baseline for spec-symbol resolution. The wellness check uses
    a smarter language-aware regex; this is the substrate-native check that
    runs from any Form expression. False when the file doesn't exist.
    """
    from pathlib import Path as _Path
    if not isinstance(path, str):
        raise TypeError(f"file_contains: path must be string, got {type(path).__name__}")
    if not isinstance(needle, str):
        raise TypeError(f"file_contains: needle must be string, got {type(needle).__name__}")
    p = _Path(path)
    if not p.is_file():
        return False
    try:
        return needle in p.read_text(errors="replace")
    except OSError:
        return False


def _builtin_file_size(path: Any) -> int:
    """Size of `path` in bytes. 0 when path does not exist (not an error —
    spec predicates may want to compose `file_size("X") > 0` without
    a missing-file exception interrupting evaluation)."""
    from pathlib import Path as _Path
    if not isinstance(path, str):
        raise TypeError(f"file_size: path must be string, got {type(path).__name__}")
    p = _Path(path)
    if not p.is_file():
        return 0
    try:
        return p.stat().st_size
    except OSError:
        return 0


def _builtin_symbol_in_file(path: Any, symbol: Any) -> bool:
    """Alias for file_contains keyed by a symbol-named string. Semantic
    clarity for spec.source predicates: `symbol_in_file(file, "ingest_one")`
    reads naturally as 'does ingest_one resolve in file?'"""
    return _builtin_file_contains(path, symbol)


def _builtin_ask(*args: Any) -> dict[str, Any]:
    """`ask(agent_id, question, choices=[], context={})` — open a human question.

    This is a host-bound effect: Form emits into the agent question channel,
    which in turn feeds the existing SSE web surface.
    """
    if len(args) < 2 or len(args) > 4:
        raise TypeError(
            "Form runtime: ask(agent_id, question, choices=[], context={}) "
            f"expects 2 to 4 arg(s), got {len(args)}"
        )
    agent_id, question = args[0], args[1]
    if not isinstance(agent_id, str) or not isinstance(question, str):
        raise TypeError("Form runtime: ask() expects string agent_id and question")
    choices: list[str] = []
    if len(args) >= 3 and args[2] is not None:
        if not isinstance(args[2], list):
            raise TypeError("Form runtime: ask() choices must be a list of strings")
        choices = [str(choice) for choice in args[2]]
    context: dict[str, Any] = {}
    if len(args) >= 4 and args[3] is not None:
        if not isinstance(args[3], dict):
            raise TypeError("Form runtime: ask() context must be a dict")
        context = dict(args[3])

    from app.services.agent_question_service import create_question

    task_id = context.get("task_id")
    thread_id = context.get("thread_id")
    return create_question(
        agent_id=agent_id,
        question=question,
        choices=choices,
        context=context,
        task_id=str(task_id) if task_id is not None else None,
        thread_id=str(thread_id) if thread_id is not None else None,
    )


def _builtin_await_answer(question_id: Any) -> str | None:
    """`await_answer(question_id)` — read the current answer, or null."""
    if not isinstance(question_id, str):
        raise TypeError("Form runtime: await_answer() expects a question id string")
    from app.services.agent_question_service import get_question

    question = get_question(question_id)
    if question is None:
        raise LookupError(f"Form runtime: question {question_id!r} not found")
    answer = question.get("answer")
    return str(answer) if answer is not None else None


_BUILTIN_FUNCTIONS: Dict[str, Any] = {
    # List ops
    "len": lambda x: len(x),
    "head": lambda xs: xs[0] if xs else None,
    "tail": lambda xs: xs[1:] if xs else [],
    "reverse": lambda xs: list(reversed(xs)) if isinstance(xs, list) else xs[::-1],
    "concat": lambda a, b: a + b,
    "map": _builtin_map,
    "filter": _builtin_filter,
    "fold": _builtin_fold,
    "range": lambda *args: list(range(*args)),
    # Type coercion
    "str": lambda x: str(x),
    "int": lambda x: int(x),
    "bool": lambda x: bool(x),
    # Numeric
    "min": lambda *xs: min(*xs) if len(xs) > 1 else min(xs[0]),
    "max": lambda *xs: max(*xs) if len(xs) > 1 else max(xs[0]),
    "sum": lambda xs: sum(xs),
    "abs": lambda x: abs(x),
    # Recipe introspection — the meta-circular primitives. With these
    # three, Form code can walk Recipe NodeIDs from inside Form: dispatch
    # on category, recurse on children, bottom-out at trivials. The
    # evaluator-in-Form (form-engine.form Part 2) becomes expressible.
    "category": _builtin_category,
    "nchildren": _builtin_nchildren,
    "child": _builtin_child,
    # Trivial-leaf decoders — the bottom of the recursion. The evaluator
    # descends to a leaf via category/child, then pulls the value via
    # one of these.
    "integer_value": _builtin_integer_value,
    "string_value": _builtin_string_value,
    "bool_value": _builtin_bool_value,
    # Host effects — bridge Form execution into the agent question channel.
    "ask": _builtin_ask,
    "await_answer": _builtin_await_answer,
    # Filesystem facts — the predicates spec recipes need to assert about
    # the body's structural reality. Result is content-addressed; the
    # substrate's cache holds the answer once evaluated. See
    # docs/coherence-substrate/spec-as-playable-recipe.form (S4 — these
    # builtins close the predicate vocabulary for `done_when:` items).
    "file_exists": _builtin_file_exists,
    "file_contains": _builtin_file_contains,
    "file_size": _builtin_file_size,
    "symbol_in_file": _builtin_symbol_in_file,
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

    # List literal (`[1, 2, 3]`) — parser returns a Python list of ExprNodes;
    # runtime evaluates each item and yields a Python list.
    if isinstance(ast, list):
        return [execute(session, item, frame) for item in ast]

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

    # Query wrapper (parser-emitted for ?on_change / ?project). Unwrap to the
    # inner AST and execute. For purely-reading queries (?cells, ?equivalent,
    # ?lattice, ?keywords, ?shaped_by, ?harmonic_at, ?vocabulary), delegate
    # to form.evaluate which has the substrate-aware implementations.
    from app.services.substrate.form import Query
    if isinstance(ast, Query):
        if ast.kind in ("on_change", "project"):
            return execute(session, ast.arg, frame)
        from app.services.substrate.form import _evaluate_query
        result = _evaluate_query(session, ast)
        return result.value

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
            left_value = execute(session, ast.left, frame)
            if not left_value:
                return left_value
            return execute(session, ast.right, frame)
        if ast.op == "||":
            left_value = execute(session, ast.left, frame)
            if left_value:
                return left_value
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

    if isinstance(ast, TernaryExpr):
        if execute(session, ast.cond, frame):
            return execute(session, ast.then_branch, frame)
        return execute(session, ast.else_branch, frame)

    if isinstance(ast, DictExpr):
        return {key: execute(session, value, frame) for key, value in ast.pairs}

    if isinstance(ast, ForExpr):
        iterable = execute(session, ast.iter, frame)
        if not hasattr(iterable, "__iter__"):
            raise TypeError(
                f"Form runtime: `for` requires an iterable, got {type(iterable).__name__}"
            )
        results = []
        for item in iterable:
            sub = Frame(parent=frame)
            sub.bindings[ast.var] = item
            results.append(execute(session, ast.body, sub))
        return results

    if isinstance(ast, WhileExpr):
        # Loop body shares the caller's frame so `let x = ...` updates
        # persist across iterations (otherwise the loop variable never
        # changes and the loop would be infinite or not progress).
        result = None
        guard = 0
        max_iterations = 100_000
        while execute(session, ast.cond, frame):
            result = execute(session, ast.body, frame)
            guard += 1
            if guard > max_iterations:
                raise RuntimeError(
                    f"Form runtime: `while` loop exceeded {max_iterations} iterations"
                )
        return result

    if isinstance(ast, IndexExpr):
        target = execute(session, ast.target, frame)
        index = execute(session, ast.index, frame)
        try:
            return target[index]
        except (KeyError, IndexError, TypeError) as e:
            raise TypeError(
                f"Form runtime: cannot index {type(target).__name__} with "
                f"{type(index).__name__} ({index!r}): {e}"
            )

    if isinstance(ast, DoBlock):
        sub = Frame(parent=frame)
        result: Any = None
        try:
            for stmt in ast.statements:
                result = execute(session, stmt, sub)
        except StopSignal:
            # `stop` commits the in-flight value — last computed result wins,
            # remaining statements skipped.
            pass
        return result

    if isinstance(ast, Let):
        value = execute(session, ast.value, frame)
        frame.bindings[ast.name] = value
        return value

    if isinstance(ast, SetExpr):
        # Walk the frame chain looking for the nearest binding of `name`.
        # Update in-place where found. Raise if no enclosing frame has it.
        value = execute(session, ast.value, frame)
        f = frame
        while f is not None:
            if ast.name in f.bindings:
                f.bindings[ast.name] = value
                return value
            f = f.parent
        raise NameError(
            f"Form runtime: `set {ast.name} = ...` — no binding for `{ast.name}` "
            f"in enclosing scope (use `let` to introduce)"
        )

    if isinstance(ast, MatchExpr):
        scrut = execute(session, ast.scrutinee, frame)
        for arm in ast.arms:
            if _is_wildcard(arm.pattern):
                return execute(session, arm.body, frame)
            pat_value = execute(session, arm.pattern, frame)
            if pat_value == scrut:
                return execute(session, arm.body, frame)
        # No arm matched and no `_` wildcard — refuse to silently coerce
        # to null. The honest answer is that the engine doesn't know what
        # the value of this expression should be. Add an explicit `_ => ...`
        # arm to say what to do in the unmatched case (it can be `null` if
        # that's what you want — but say it).
        raise LookupError(
            f"Form runtime: `match` exhausted without a matching arm "
            f"(scrutinee={scrut!r}). Add an explicit `_ => ...` arm to "
            f"name the fallback — silent null is a coercion the engine refuses."
        )

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
        # Built-in first, then frame lookup, so the body can override
        # `len`/`map`/etc. with a user defn if it chooses.
        if ast.name in _BUILTIN_FUNCTIONS and not frame.has(ast.name):
            evaluated = [execute(session, a, frame) for a in ast.args]
            _CURRENT_SESSION[0] = session
            try:
                return _BUILTIN_FUNCTIONS[ast.name](*evaluated)
            finally:
                _CURRENT_SESSION[0] = None
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

    # --- BML state-stack — save / restore / discard --------------------------
    #
    # save snapshots the current frame's bindings dict; restore pops + applies;
    # discard pops without applying. The stack lives on the root frame (walked
    # via the parent chain) so siblings share the same stack within a session.

    if isinstance(ast, SaveExpr):
        _state_stack_of(frame).append(dict(frame.bindings))
        return None

    if isinstance(ast, RestoreExpr):
        stack = _state_stack_of(frame)
        if not stack:
            raise IndexError("Form runtime: `restore` with empty state stack")
        frame.bindings = stack.pop()
        return None

    if isinstance(ast, DiscardExpr):
        stack = _state_stack_of(frame)
        if not stack:
            raise IndexError("Form runtime: `discard` with empty state stack")
        stack.pop()
        return None

    # --- BML exception-flow — raise / resume --------------------------------

    if isinstance(ast, RaiseExpr):
        payload = None
        if getattr(ast, "value", None) is not None:
            payload = execute(session, ast.value, frame)
        raise RaiseSignal(payload)

    if isinstance(ast, ResumeExpr):
        # `resume` on its own is a marker; in a try-frame it returns control
        # to the handler. Until try-frames land at the runtime layer, resume
        # outside an exception context yields None.
        return None

    # --- BML reverse semantics — undo / inverse -----------------------------

    if isinstance(ast, UndoExpr):
        # Undo wraps a recipe; semantically it executes the inverse pass.
        # For pure-computation expressions (the only ones we can invert today)
        # we re-evaluate the inner expression — the substrate's content-
        # addressing makes the inverse the same Recipe NodeID. For richer
        # constructs the inverse pass needs paired DO/UNDO instruction-level
        # semantics; that pairs with the per-instruction reverse work named
        # at the VM layer.
        return execute(session, ast.child, frame)

    if isinstance(ast, InverseExpr):
        # `inverse(<recipe>)` yields the inverse-recipe NodeID without
        # running it. Until paired DO/UNDO lands, we return the structural
        # Recipe NodeID of the child expression (the inverse shape lives at
        # `(RBasic.REVERSE, RReverse.INVERSE, [child])` which already interns).
        from app.services.substrate.form import _to_recipe_node_id
        return _to_recipe_node_id(session, ast.child)

    # --- BML Common Objects — common @X @Y ----------------------------------

    if isinstance(ast, CommonExpr):
        a = execute(session, ast.a, frame)
        b = execute(session, ast.b, frame)
        a_key = _cell_key(a)
        b_key = _cell_key(b)
        if a_key is None or b_key is None:
            raise TypeError("Form runtime: `common` requires two cells")
        # Merge into an existing group containing either, or create new.
        merged: set = {a_key, b_key}
        remaining: List[frozenset] = []
        for group in _COMMON_GROUPS:
            if a_key in group or b_key in group:
                merged |= set(group)
            else:
                remaining.append(group)
        remaining.append(frozenset(merged))
        _COMMON_GROUPS.clear()
        _COMMON_GROUPS.extend(remaining)
        return frozenset(merged)

    # --- BML method-on-object — method NAME on @X { body } -----------------

    if isinstance(ast, MethodDefExpr):
        target = execute(session, ast.target, frame)
        key = _cell_key(target)
        if key is None:
            raise TypeError("Form runtime: `method` requires a cell target")
        # Store (params, body) so invocation can bind arg values to param names.
        _METHOD_REGISTRY[(key[0], key[1], ast.name)] = {
            "params": list(getattr(ast, "params", []) or []),
            "body": ast.body,
        }
        return ast.body

    if isinstance(ast, MethodInvokeExpr):
        target = execute(session, ast.target, frame)
        key = _cell_key(target)
        if key is None:
            raise TypeError("Form runtime: `invoke` requires a cell target")
        # Evaluate args in the caller's frame.
        evaluated_args = [execute(session, a, frame) for a in getattr(ast, "args", []) or []]
        # Walk delegation chain, then common-base peers, looking up the method.
        candidates = list(_delegate_chain(key)) + list(_common_peers(key))
        for cand_key in candidates:
            entry = _METHOD_REGISTRY.get((cand_key[0], cand_key[1], ast.name))
            if entry is None:
                continue
            # Support legacy registrations where the entry is just an AST body
            # (no params) for back-compat with PR #1676.
            if isinstance(entry, dict):
                params = entry["params"]
                body = entry["body"]
            else:
                params, body = [], entry
            if len(params) != len(evaluated_args):
                raise TypeError(
                    f"Form runtime: method `{ast.name}` on @{cand_key[0]}({cand_key[1]}) "
                    f"takes {len(params)} arg(s), got {len(evaluated_args)}"
                )
            # Execute the body with .self bound to the original target and
            # params bound to the evaluated args. The sub-frame's parent is
            # the call-time frame (lexical look-ups for names defined above).
            sub = Frame(parent=frame, subject=target, has_subject=True)
            for name, value in zip(params, evaluated_args):
                sub.bindings[name] = value
            return execute(session, body, sub)
        raise AttributeError(
            f"Form runtime: no method `{ast.name}` on @{key[0]}({key[1]}) "
            f"(delegate chain: {_delegate_chain(key)}; peers: {sorted(_common_peers(key))})"
        )

    # --- BML try/catch — catching frame for raised exceptions --------------

    if isinstance(ast, TryCatchExpr):
        try:
            sub = Frame(parent=frame)
            return execute(session, ast.body, sub)
        except RaiseSignal as sig:
            # The raised payload (if any) is bound as the catch frame's
            # subject so `.self` inside catch resolves to the raised value.
            sub = Frame(
                parent=frame,
                subject=sig.payload,
                has_subject=sig.payload is not None,
            )
            return execute(session, ast.handler, sub)

    # --- Delegation declaration --------------------------------------------

    if isinstance(ast, DelegateExpr):
        source = execute(session, ast.source, frame)
        target = execute(session, ast.target, frame)
        s_key = _cell_key(source)
        t_key = _cell_key(target)
        if s_key is None or t_key is None:
            raise TypeError("Form runtime: `delegate` requires two cells")
        _DELEGATE_REGISTRY[s_key] = t_key
        return (s_key, t_key)

    # --- Reactive lens — ?on_change <recipe> { body } ----------------------

    if isinstance(ast, OnChangeExpr):
        # Snapshot the watched value now; register the (query, body, frame)
        # for future `fire_subscriptions(session)` calls.
        initial = execute(session, ast.query, frame)
        _SUBSCRIPTIONS.append({
            "query": ast.query,
            "body": ast.body,
            "frame": frame,
            "last": initial,
        })
        return initial

    # --- Spatial-projection lens — ?project @cell @coord_fn -----------------

    if isinstance(ast, ProjectExpr):
        cell = execute(session, ast.cell, frame)
        coord_fn_ref = execute(session, ast.coord_fn, frame)
        # The coord_fn ref is a cell whose name keys into _COORD_FNS.
        name = coord_fn_ref.name if hasattr(coord_fn_ref, "name") else None
        if name is None or name not in _COORD_FNS:
            # Honest passthrough: return the (cell, coord_fn_ref) tuple so the
            # caller knows what was projected even when no renderer is registered.
            return (cell, coord_fn_ref)
        return _COORD_FNS[name](cell)

    raise TypeError(f"Form runtime: cannot execute {type(ast).__name__}")


def _state_stack_of(frame: Frame) -> List[Dict[str, Any]]:
    """The state stack lives on the root of the frame chain so save/restore/
    discard work across nested do-blocks."""
    root = frame
    while root.parent is not None:
        root = root.parent
    if not hasattr(root, "_state_stack"):
        root._state_stack = []
    return root._state_stack


# ---------------------------------------------------------------------------
# Tree navigation helpers
# ---------------------------------------------------------------------------


def _trivial_value(session: Session, nid: NodeID) -> Any:
    """Decode a trivial (Level.TRIVIAL) Recipe NodeID to its Python value.

    Single source of truth for the leaf encoding — keeps Form's `.value`
    accessor and the Python engine's leaf decode reading the same shape,
    so a change to the integer encoding moves both at once.

    Raises ValueError for non-trivials (composites have no atomic value;
    their value is what evaluating the recipe returns).
    """
    from app.services.substrate.category import Level, RType
    from app.services.substrate.substrate_strings import lookup_string_value

    if nid.level != Level.TRIVIAL:
        raise ValueError(
            f"Form runtime: .value requires a trivial leaf, got {nid} "
            f"(level={nid.level}); composites carry no atomic value"
        )
    if nid.type_ == RType.NULL:
        return None
    if nid.type_ == RType.BOOL:
        return nid.instance == 1
    if nid.type_ == RType.INTEGER:
        return nid.instance - 1 if nid.instance > 0 else 0
    if nid.type_ == RType.STRING:
        return lookup_string_value(session, nid.instance) or ""
    if nid.type_ == RType.SLUG:
        # Slugs share the substrate_strings interning table with strings;
        # they differ in type-tag (identity-role vs content-role) but the
        # surface decoding is the same lookup. Letting `let x = 42` round-trip
        # required this arm; without it, the Identifier child x stays opaque.
        return lookup_string_value(session, nid.instance) or ""
    raise ValueError(
        f"Form runtime: .value has no decoder for RType={nid.type_} "
        f"(supported: NULL, BOOL, INTEGER, STRING, SLUG)"
    )


def _ctor_field_lookup(session: Session, ctor: Any, field: str) -> Any:
    """Walk a structured CTOR (R_Block.DO of R_Block.LET) for a named field.

    Returns the decoded value of the LET binding whose key matches `field`,
    or None if the CTOR is not in structured-LET shape, or no binding
    matches. Composite values are returned as their NodeID (so the caller
    can walk further); trivial values are decoded.

    The shape this walks is what `frontmatter_to_structured_ctor` produces:

        do {
            let "idea_id" = "...";   # LET[SLUG, STRING]
            let "title"   = "...";   # LET[SLUG, STRING]
            ...
        }
    """
    if ctor is None or not isinstance(ctor, NodeID):
        return None
    from app.services.substrate.category import RBasic
    ctor_cat = _node_category(session, ctor)
    if ctor_cat.type_ != RBasic.BLOCK.value:
        return None
    for let_nid in _node_children(session, ctor):
        let_cat = _node_category(session, let_nid)
        if let_cat.type_ != RBasic.BLOCK.value or let_cat.instance != 3:
            continue  # not a LET
        let_kids = _node_children(session, let_nid)
        if len(let_kids) != 2:
            continue
        try:
            key = _trivial_value(session, let_kids[0])
        except (ValueError, AttributeError):
            continue
        if key != field:
            continue
        # Match — decode the value if trivial, else return the NodeID.
        try:
            return _trivial_value(session, let_kids[1])
        except (ValueError, AttributeError):
            return let_kids[1]
    return None


def _resolve_access(session: Session, target: Any, field: str) -> Any:
    """Field access on a Cell, Blueprint NodeID, Recipe NodeID, or dict.

    Cells expose: blueprint, ctor, base, access, name, domain, source.
    NodeIDs expose: package, level, type_, instance, category, children,
                    nchildren, value (trivial-leaf decode).
    Dicts expose their keys; missing key raises AttributeError.
    """
    from app.services.substrate.kernel import NamedCell

    # Dict literal access — `{a: 1, b: 2}.a` → 1.
    if isinstance(target, dict):
        if field in target:
            return target[field]
        raise AttributeError(
            f"Form runtime: dict has no field {field!r} "
            f"(keys: {sorted(target.keys())})"
        )

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
        # Fall through to structured-CTOR field-by-name access.
        # If the cell's CTOR is a R_Block.DO whose children are R_Block.LET
        # recipes (the structured-CTOR shape since 2026-05-23), walk the
        # LET-bindings looking for one whose key matches `field`. This is
        # what makes `@idea(realization).title` work: the human reads YAML,
        # the substrate walks LET, the AI bridges — same value, three voices.
        ctor_value = _ctor_field_lookup(session, target.ctor, field)
        if ctor_value is not None:
            return ctor_value
        raise AttributeError(
            f"Form runtime: cell has no field {field!r} "
            f"(try: blueprint, ctor, base, access, name, domain, source, "
            f"or any frontmatter key from the structured CTOR)"
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
        if field == "value":
            return _trivial_value(session, target)
        # Fall through to structured-CTOR field-by-name access on a Recipe.
        # A R_Block.DO whose children are R_Block.LET (the structured-CTOR
        # shape) walks by key name. This lets the runtime navigate nested
        # structured frontmatter — `cell.capabilities.children[0].title`
        # works without explicit walking once both layers fall through.
        ctor_value = _ctor_field_lookup(session, target, field)
        if ctor_value is not None:
            return ctor_value
        raise AttributeError(
            f"Form runtime: NodeID has no field {field!r} "
            f"(try: package, level, type, instance, category, children, "
            f"nchildren, value, or any LET-binding key in a structured CTOR)"
        )

    raise TypeError(
        f"Form runtime: cannot access .{field} on {type(target).__name__}"
    )


def _resolve_method(session: Session, target: Any, method: str, args: List[Any]) -> Any:
    """Method-call on a Cell, Blueprint, or Recipe.

    Built-in on NodeIDs: `.child(n)` returns the n-th child NodeID.
    User-defined on Cells: `@concept(X).greet()` dispatches via the same
    delegation/common-base chain `invoke greet on @concept(X)` uses.
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

    # User-defined method dispatch on a Cell — same chain as MethodInvokeExpr.
    key = _cell_key(target)
    if key is not None:
        for cand_key in list(_delegate_chain(key)) + list(_common_peers(key)):
            entry = _METHOD_REGISTRY.get((cand_key[0], cand_key[1], method))
            if entry is None:
                continue
            if isinstance(entry, dict):
                params = entry["params"]
                body = entry["body"]
            else:
                params, body = [], entry
            if len(params) != len(args):
                raise TypeError(
                    f"Form runtime: method `.{method}` on @{cand_key[0]}({cand_key[1]}) "
                    f"takes {len(params)} arg(s), got {len(args)}"
                )
            sub = Frame(parent=Frame(), subject=target, has_subject=True)
            for name, value in zip(params, args):
                sub.bindings[name] = value
            return execute(session, body, sub)

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
