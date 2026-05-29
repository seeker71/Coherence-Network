# Static name-resolution + blueprint-type checker for the substrate Form dialect.
#
# Form text becomes recipes (`_to_recipe_node_id`) or values (`form_runtime.execute`)
# through two AST walks that resolve names lazily — they raise on the FIRST
# unresolved name, only when that node is reached, only at run time. That is
# enough to run a known-good expression; it is NOT enough to refactor with
# confidence. Rename a global cell, a function, or a blueprint and nothing
# tells you what broke until you happen to execute the exact path that touches it.
#
# This module is a THIRD walk over the same AST — alongside the recipe walk and
# the value walk, a *resolution* walk. It threads a lexical Scope (mirroring the
# runtime Frame), resolves every name against the same namespaces the runtime
# uses, infers a conservative blueprint for each expression, and COLLECTS every
# problem instead of raising on the first. The output is the whole map of what a
# refactor broke, in one pass, before anything runs.
#
# Three namespaces, the three the request named:
#   • blueprints — `~Integer`/`~Memory` (TRIVIAL_REFS) and bare `@domain`
#   • recipes    — named callables: `defn` closures (arity-checked) + built-ins
#   • global cells — `@domain(name)` resolved against the live substrate
#
# Single source of truth: the checker draws its "known names" from the same live
# registries the runtime reads (`_BUILTIN_FUNCTIONS`, `TRIVIAL_REFS`,
# `lookup_eval_category`, `lookup_cell`), never a second hand-maintained copy.
# When a built-in or operator is added, the checker learns it for free.
#
# Calibration — the checker must never cry wolf, or it stops being trusted:
#   • Name/scope/operator resolution failures are unambiguous → ERROR.
#   • Blueprint/type mismatches in a dynamically-typed substrate are best-effort
#     → WARNING, and only raised when a value is *definitely* the wrong shape.
#   • Anything the walk can't statically know (cell-field access, method
#     dispatch, builtin results) infers as UNKNOWN and is never flagged.
#
# Dialect scope: this checks the substrate Form dialect that the Python
# `form_runtime` executes — what `coh substrate form/run` and the MCP substrate
# tools accept. It deliberately does NOT check the TS-kernel `.fk`/stdlib dialect
# (a different runtime with a different, larger builtin vocabulary); pointing a
# Python-vocabulary checker at those would be all false positives. Sibling-parity
# for the TS kernel is a separate follow-up.
#
# Canonical shape (this checker in Form's own voice):
# docs/coherence-substrate/name-resolution-as-recipe.form — the resolution walk
# as the third peer of the recipe-walk and value-walk.

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.services.substrate import form as F
from app.services.substrate.kernel import NodeID, lookup_cell


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

ERROR = "error"
WARNING = "warning"


@dataclass
class Diagnostic:
    """One thing the resolution walk found. `code` is a stable kebab-case
    identifier so tooling can filter; `message` is the human sentence;
    `snippet` is a compact Form rendering of the offending node so a reader
    can grep the source for it."""

    severity: str  # ERROR | WARNING
    code: str
    message: str
    snippet: str = ""

    def __str__(self) -> str:
        loc = f"  in `{self.snippet}`" if self.snippet else ""
        return f"[{self.severity}] {self.code}: {self.message}{loc}"


# ---------------------------------------------------------------------------
# Inferred blueprint types — a small conservative lattice
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FormType:
    """A statically-inferred blueprint. `kind` is the coarse shape; `arity`
    carries a closure's parameter count; `domain` carries a cell's domain.
    UNKNOWN is the top — it unifies with everything and is never flagged."""

    kind: str
    arity: int = -1
    domain: str = ""

    def __str__(self) -> str:
        if self.kind == "closure":
            return f"closure/{self.arity}"
        if self.kind == "cell":
            return f"cell<{self.domain}>" if self.domain else "cell"
        return self.kind


UNKNOWN = FormType("unknown")
NULL = FormType("null")
INT = FormType("int")
DECIMAL = FormType("decimal")
BOOL = FormType("bool")
STRING = FormType("string")
SLUG = FormType("slug")
NODEID = FormType("nodeid")
BLUEPRINT = FormType("blueprint")
LIST = FormType("list")
DICT = FormType("dict")

_NUMERIC = {"int", "decimal"}


def _join(a: FormType, b: FormType) -> FormType:
    """Least-committed common type of two branches. Equal → that type;
    both numeric → numeric-ish; otherwise UNKNOWN. Used by if/match/choose
    where the result is one branch or another."""
    if a == b:
        return a
    if a.kind in _NUMERIC and b.kind in _NUMERIC:
        return DECIMAL if "decimal" in (a.kind, b.kind) else INT
    return UNKNOWN


def _is_definitely(t: FormType, *kinds: str) -> bool:
    """True only when the type is known to be one of `kinds`. UNKNOWN is
    never 'definitely' anything — that is what keeps the type layer from
    crying wolf."""
    return t.kind in kinds


# ---------------------------------------------------------------------------
# Lexical scope — mirrors form_runtime.Frame, carrying types instead of values
# ---------------------------------------------------------------------------


@dataclass
class Scope:
    vars: dict = field(default_factory=dict)  # name -> FormType
    parent: Optional["Scope"] = None
    has_subject: bool = False  # inside a `with` / catch / method body

    def child(self, *, has_subject: bool = False) -> "Scope":
        return Scope(parent=self, has_subject=has_subject)

    def define(self, name: str, t: FormType) -> None:
        self.vars[name] = t

    def lookup(self, name: str) -> Optional[FormType]:
        s: Optional[Scope] = self
        while s is not None:
            if name in s.vars:
                return s.vars[name]
            s = s.parent
        return None

    def in_with(self) -> bool:
        s: Optional[Scope] = self
        while s is not None:
            if s.has_subject:
                return True
            s = s.parent
        return False


# ---------------------------------------------------------------------------
# Compact AST renderer — for the `snippet` field of diagnostics
# ---------------------------------------------------------------------------


def render(node: Any) -> str:
    """Best-effort compact Form-ish rendering of a node, for diagnostics.
    Not a faithful pretty-printer — enough that a reader recognizes the
    offending construct and can grep for it."""
    n = node
    if isinstance(n, F.IntLit):
        return str(n.value)
    if isinstance(n, F.BoolLit):
        return "true" if n.value else "false"
    if isinstance(n, F.StringLit):
        return f'"{n.value}"'
    if isinstance(n, F.Identifier):
        return n.name
    if isinstance(n, F.TrivialRef):
        return f"~{n.name}"
    if isinstance(n, F.CellRef):
        return f"@{n.domain}" if n.name is None else f"@{n.domain}({n.name})"
    if isinstance(n, F.BinOp):
        return f"{render(n.left)} {n.op} {render(n.right)}"
    if isinstance(n, F.UnaryOp):
        return f"{n.op}{render(n.operand)}"
    if isinstance(n, F.FnCall):
        return f"{n.name}({', '.join(render(a) for a in n.args)})"
    if isinstance(n, F.SetExpr):
        return f"set {n.name} = {render(n.value)}"
    if isinstance(n, F.Let):
        return f"let {n.name} = {render(n.value)}"
    if isinstance(n, F.SelfRef):
        return ".self"
    if isinstance(n, F.Access):
        return f"{render(n.target)}.{n.field}"
    if isinstance(n, F.IndexExpr):
        return f"{render(n.target)}[{render(n.index)}]"
    if isinstance(n, list):
        return f"[{', '.join(render(x) for x in n)}]"
    return f"<{type(n).__name__}>"


# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------


class Checker:
    """One resolution walk. Construct with a substrate session (cell lookups
    flow through it), call `check(ast)`, read `diagnostics`.

    Design: the nodes that carry genuine scope / reference / type semantics
    get explicit handlers (that knowledge lives nowhere else and is exactly
    what a type system needs). Every other node — pure containers and future
    additions — falls through to `_walk`, a generic recursion into all
    AST-shaped fields. So adding a new container AST node needs no change
    here: its sub-expressions are name-checked automatically."""

    def __init__(self, session: Session):
        self.session = session
        self.diagnostics: List[Diagnostic] = []
        # Pulled once from the live registries — single source of truth.
        from app.services.substrate.form_runtime import (
            _BUILTIN_FUNCTIONS,
            _BUILTIN_IDENTIFIERS,
        )

        self._builtin_fns = set(_BUILTIN_FUNCTIONS)
        self._builtin_idents = dict(_BUILTIN_IDENTIFIERS)
        # Cell existence only means something against an ingested lattice. On an
        # empty substrate every `@domain(name)` would flag as unresolved — pure
        # noise — so sense once whether the lattice carries cells and skip cell
        # existence (with a single honest note) when it doesn't. Domain validity
        # (`@notadomain`) is static and stays on regardless.
        self._lattice_populated = self._sense_lattice()
        self._skip_note_emitted = False

    def _sense_lattice(self) -> bool:
        try:
            from app.services.substrate.orm import SubstrateNamedCellORM

            return self.session.query(SubstrateNamedCellORM).limit(1).count() > 0
        except Exception:
            # If we can't sense the lattice, don't claim cells are missing.
            return False

    # -- diagnostic helpers --------------------------------------------------

    def _err(self, code: str, message: str, node: Any) -> None:
        self.diagnostics.append(Diagnostic(ERROR, code, message, render(node)))

    def _warn(self, code: str, message: str, node: Any) -> None:
        self.diagnostics.append(Diagnostic(WARNING, code, message, render(node)))

    # -- entry ---------------------------------------------------------------

    def check(self, ast: Any, scope: Optional[Scope] = None) -> FormType:
        if scope is None:
            scope = Scope()
        return self._dispatch(ast, scope)

    # -- dispatch ------------------------------------------------------------

    def _dispatch(self, node: Any, scope: Scope) -> FormType:
        # Literals -----------------------------------------------------------
        if isinstance(node, F.IntLit):
            return INT
        if isinstance(node, F.BoolLit):
            return BOOL
        if isinstance(node, F.StringLit):
            return STRING
        if isinstance(node, F.NodeIDLit):
            return NODEID
        if isinstance(node, list):
            for item in node:
                self._dispatch(item, scope)
            return LIST

        # Names --------------------------------------------------------------
        if isinstance(node, F.Identifier):
            return self._check_identifier(node, scope)
        if isinstance(node, F.FnCall):
            return self._check_fncall(node, scope)
        if isinstance(node, F.SetExpr):
            return self._check_set(node, scope)

        # Blueprints + cells -------------------------------------------------
        if isinstance(node, F.TrivialRef):
            return self._check_trivial(node)
        if isinstance(node, F.CellRef):
            return self._check_cellref(node)

        # Operators ----------------------------------------------------------
        if isinstance(node, F.BinOp):
            return self._check_binop(node, scope)
        if isinstance(node, F.UnaryOp):
            return self._check_unop(node, scope)

        # Binding forms ------------------------------------------------------
        if isinstance(node, F.Let):
            t = self._dispatch(node.value, scope)
            scope.define(node.name, t)
            return t
        if isinstance(node, F.FnDef):
            return self._check_fndef(node, scope)
        if isinstance(node, F.DoBlock):
            return self._check_do(node, scope)

        # Control flow -------------------------------------------------------
        if isinstance(node, F.IfExpr):
            self._dispatch(node.cond, scope)
            t_then = self._dispatch(node.then_branch, scope)
            if node.else_branch is None:
                return UNKNOWN
            return _join(t_then, self._dispatch(node.else_branch, scope))
        if isinstance(node, F.TernaryExpr):
            self._dispatch(node.cond, scope)
            return _join(
                self._dispatch(node.then_branch, scope),
                self._dispatch(node.else_branch, scope),
            )
        if isinstance(node, F.MatchExpr):
            return self._check_match(node, scope)
        if isinstance(node, F.ChooseExpr):
            t = UNKNOWN
            for i, cand in enumerate(node.candidates):
                ct = self._dispatch(cand, scope)
                t = ct if i == 0 else _join(t, ct)
            return t

        # Scopes -------------------------------------------------------------
        if isinstance(node, F.WithExpr):
            self._dispatch(node.subject, scope)
            return self._dispatch(node.body, scope.child(has_subject=True))
        if isinstance(node, F.SelfRef):
            if not scope.in_with():
                self._err(
                    "self-outside-with",
                    "`.self` used outside a `with` block (no implicit subject in scope)",
                    node,
                )
            return UNKNOWN
        if isinstance(node, F.ForExpr):
            self._dispatch(node.iter, scope)
            sub = scope.child()
            sub.define(node.var, UNKNOWN)
            self._dispatch(node.body, sub)
            return LIST
        if isinstance(node, F.WhileExpr):
            # Runtime runs the body in the caller's frame (so accumulation via
            # `set` persists) — mirror that: no child scope.
            self._dispatch(node.cond, scope)
            self._dispatch(node.body, scope)
            return UNKNOWN

        # Containers with known result shape --------------------------------
        if isinstance(node, F.DictExpr):
            for _key, value in node.pairs:
                self._dispatch(value, scope)
            return DICT
        if isinstance(node, F.IndexExpr):
            target_t = self._dispatch(node.target, scope)
            self._dispatch(node.index, scope)
            if _is_definitely(target_t, "int", "decimal", "bool"):
                self._warn(
                    "not-indexable",
                    f"indexing a value inferred as {target_t} — only lists, "
                    "strings, and dicts are indexable",
                    node,
                )
            return UNKNOWN

        # Methods + cell-shared forms (dynamic dispatch — refs only) ---------
        if isinstance(node, F.MethodDefExpr):
            self._dispatch(node.target, scope)
            body_scope = scope.child(has_subject=True)
            for p in node.params:
                body_scope.define(p, UNKNOWN)
            self._dispatch(node.body, body_scope)
            return UNKNOWN
        if isinstance(node, F.TryCatchExpr):
            self._dispatch(node.body, scope.child())
            # The raised payload is the catch block's `.self`.
            self._dispatch(node.handler, scope.child(has_subject=True))
            return UNKNOWN

        # Everything else: generic recursion into AST-shaped fields ----------
        return self._walk(node, scope)

    # -- generic fallback ----------------------------------------------------

    def _walk(self, node: Any, scope: Scope) -> FormType:
        """Recurse into every AST-shaped field of a node we don't model
        explicitly. Sub-expressions still get name-checked; the node itself
        infers as UNKNOWN. This is what lets new container nodes drop in as
        data without touching the dispatch ladder."""
        if not dataclasses.is_dataclass(node):
            return UNKNOWN
        for f in dataclasses.fields(node):
            value = getattr(node, f.name)
            self._recurse_value(value, scope)
        return UNKNOWN

    def _recurse_value(self, value: Any, scope: Scope) -> None:
        if self._is_ast(value):
            self._dispatch(value, scope)
        elif isinstance(value, (list, tuple)):
            for item in value:
                self._recurse_value(item, scope)

    @staticmethod
    def _is_ast(value: Any) -> bool:
        # AST dataclasses live in the form module; NodeID is a value dataclass,
        # not an AST node, so exclude it.
        return (
            dataclasses.is_dataclass(value)
            and not isinstance(value, NodeID)
            and type(value).__module__ == F.__name__
        )

    # -- name handlers -------------------------------------------------------

    def _check_identifier(self, node: F.Identifier, scope: Scope) -> FormType:
        name = node.name
        if name in self._builtin_idents:
            v = self._builtin_idents[name]
            if v is True or v is False:
                return BOOL
            return NULL
        t = scope.lookup(name)
        if t is not None:
            return t
        # A bare name that's a known built-in function used without call is a
        # callable value — legal (e.g. passed to map). Resolve it.
        if name in self._builtin_fns:
            return UNKNOWN
        self._err(
            "unresolved-name",
            f"`{name}` is not bound in scope and is not a built-in",
            node,
        )
        return UNKNOWN

    def _check_fncall(self, node: F.FnCall, scope: Scope) -> FormType:
        for a in node.args:
            self._dispatch(a, scope)
        name = node.name
        bound = scope.lookup(name)
        if bound is not None:
            if bound.kind == "closure" and bound.arity >= 0:
                if len(node.args) != bound.arity:
                    self._err(
                        "arity-mismatch",
                        f"`{name}` takes {bound.arity} arg(s), called with "
                        f"{len(node.args)}",
                        node,
                    )
            elif bound.kind not in ("closure", "unknown"):
                self._warn(
                    "not-callable",
                    f"`{name}` is bound as {bound} — calling a non-closure value",
                    node,
                )
            return UNKNOWN
        if name in self._builtin_fns:
            return self._builtin_result_type(name)
        self._err(
            "unresolved-function",
            f"`{name}` is not a defined function (no `defn`/binding in scope) "
            "and not a built-in",
            node,
        )
        return UNKNOWN

    @staticmethod
    def _builtin_result_type(name: str) -> FormType:
        # Only the built-ins whose result shape is certain. The rest stay
        # UNKNOWN so nothing downstream is wrongly flagged.
        return {
            "len": INT,
            "int": INT,
            "str": STRING,
            "bool": BOOL,
            "range": LIST,
            "reverse": LIST,
            "concat": LIST,
            "map": LIST,
            "filter": LIST,
            "sum": INT,
            "abs": INT,
            "nchildren": INT,
            "integer_value": INT,
            "string_value": STRING,
            "bool_value": BOOL,
            "child": NODEID,
            "category": NODEID,
            "file_exists": BOOL,
            "file_contains": BOOL,
            "file_size": INT,
            "symbol_in_file": BOOL,
            "pytest_passes": BOOL,
        }.get(name, UNKNOWN)

    def _check_set(self, node: F.SetExpr, scope: Scope) -> FormType:
        t = self._dispatch(node.value, scope)
        if scope.lookup(node.name) is None:
            self._err(
                "set-unbound",
                f"`set {node.name} = ...` but `{node.name}` has no binding in "
                "scope — use `let` to introduce it",
                node,
            )
        else:
            scope.define(node.name, t)
        return t

    # -- blueprint + cell handlers ------------------------------------------

    def _check_trivial(self, node: F.TrivialRef) -> FormType:
        if node.name not in F.TRIVIAL_REFS:
            self._err(
                "unresolved-blueprint",
                f"`~{node.name}` is not a known trivial blueprint",
                node,
            )
        return BLUEPRINT

    def _check_cellref(self, node: F.CellRef) -> FormType:
        if node.name is None:
            if node.domain not in F.DOMAIN_TO_REF:
                self._err(
                    "unknown-domain",
                    f"`@{node.domain}` is not a known substrate domain",
                    node,
                )
            return BLUEPRINT
        # @domain(name) — resolve against the live substrate, but only when the
        # lattice is actually ingested (else every ref is a false alarm).
        if not self._lattice_populated:
            if not self._skip_note_emitted:
                self._skip_note_emitted = True
                self._warn(
                    "cell-resolution-skipped",
                    "substrate lattice is empty — cell existence not checked "
                    "(run `coh substrate ingest --all` to enable cell resolution)",
                    node,
                )
            return FormType("cell", domain=node.domain)
        try:
            cell = lookup_cell(self.session, node.domain, node.name)
        except Exception:
            cell = None
        if cell is None:
            self._err(
                "unresolved-cell",
                f"global cell `@{node.domain}({node.name})` not found in the "
                "substrate",
                node,
            )
        return FormType("cell", domain=node.domain)

    # -- operator handlers ---------------------------------------------------

    def _check_binop(self, node: F.BinOp, scope: Scope) -> FormType:
        lt = self._dispatch(node.left, scope)
        rt = self._dispatch(node.right, scope)
        from app.services.substrate.form_eval import lookup_eval_category

        if lookup_eval_category(node.op, "binary") is None:
            self._err(
                "unknown-operator",
                f"binary operator `{node.op}` has no evaluation mapping",
                node,
            )
            return UNKNOWN
        return self._binop_type(node, lt, rt)

    def _binop_type(self, node: F.BinOp, lt: FormType, rt: FormType) -> FormType:
        op = node.op
        if op in ("==", "!=", "<", "<=", ">", ">="):
            # Ordering comparisons on a definitely-bool / cell / blueprint
            # operand are almost surely a mistake; equality accepts anything.
            if op not in ("==", "!="):
                for t in (lt, rt):
                    if _is_definitely(t, "bool", "cell", "blueprint", "nodeid"):
                        self._warn(
                            "type-mismatch",
                            f"`{op}` orders a value inferred as {t}",
                            node,
                        )
                        break
            return BOOL
        if op in ("&&", "||"):
            return _join(lt, rt)
        # Arithmetic. `+` is overloaded (numeric add / string concat / list
        # concat), so only flag the strictly-numeric operators.
        if op == "+":
            if _is_definitely(lt, "string") or _is_definitely(rt, "string"):
                return STRING
            if lt.kind in _NUMERIC and rt.kind in _NUMERIC:
                return _join(lt, rt)
            return UNKNOWN
        if op in ("-", "*", "/", "%"):
            for t in (lt, rt):
                if _is_definitely(t, "string", "bool", "cell", "blueprint"):
                    self._warn(
                        "type-mismatch",
                        f"arithmetic `{op}` on a value inferred as {t}",
                        node,
                    )
                    break
            if op == "/":
                return DECIMAL if "decimal" in (lt.kind, rt.kind) else INT
            return _join(lt, rt) if (lt.kind in _NUMERIC and rt.kind in _NUMERIC) else UNKNOWN
        return UNKNOWN

    def _check_unop(self, node: F.UnaryOp, scope: Scope) -> FormType:
        t = self._dispatch(node.operand, scope)
        from app.services.substrate.form_eval import lookup_eval_category

        if lookup_eval_category(node.op, "unary") is None:
            self._err(
                "unknown-operator",
                f"unary operator `{node.op}` has no evaluation mapping",
                node,
            )
            return UNKNOWN
        if node.op == "!":
            return BOOL
        if node.op == "-":
            if _is_definitely(t, "string", "bool", "cell", "blueprint"):
                self._warn(
                    "type-mismatch", f"unary `-` on a value inferred as {t}", node
                )
            return t if t.kind in _NUMERIC else UNKNOWN
        return UNKNOWN

    # -- binding-form handlers ----------------------------------------------

    def _check_fndef(self, node: F.FnDef, scope: Scope) -> FormType:
        closure_t = FormType("closure", arity=len(node.params))
        # Name visible to siblings AND inside its own body (recursion).
        scope.define(node.name, closure_t)
        body_scope = scope.child()
        body_scope.define(node.name, closure_t)
        for p in node.params:
            body_scope.define(p, UNKNOWN)
        self._dispatch(node.body, body_scope)
        return closure_t

    def _check_do(self, node: F.DoBlock, scope: Scope) -> FormType:
        # One sub-scope for the whole block; `let`s accumulate so later
        # statements see earlier bindings (matches the runtime's single
        # sub-frame). Last statement's type is the block's type.
        sub = scope.child()
        t: FormType = NULL
        for stmt in node.statements:
            t = self._dispatch(stmt, sub)
        return t

    def _check_match(self, node: F.MatchExpr, scope: Scope) -> FormType:
        self._dispatch(node.scrutinee, scope)
        result: Optional[FormType] = None
        for arm in node.arms:
            # `_` wildcard is a pattern sentinel, not a name reference.
            if not (isinstance(arm.pattern, F.Identifier) and arm.pattern.name == "_"):
                self._dispatch(arm.pattern, scope)
            bt = self._dispatch(arm.body, scope)
            result = bt if result is None else _join(result, bt)
        return result if result is not None else UNKNOWN


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def check_ast(session: Session, ast: Any) -> List[Diagnostic]:
    """Resolve names and infer blueprints across an already-parsed AST.
    Returns every diagnostic found (empty list = clean)."""
    checker = Checker(session)
    checker.check(ast)
    return checker.diagnostics


def check_text(
    session: Session, code: str, *, prefer_registered: bool = False
) -> List[Diagnostic]:
    """Parse and check a Form expression in one step. A parse failure surfaces
    as a single `parse-error` diagnostic rather than an exception, so callers
    that check a whole corpus get a uniform diagnostic stream."""
    try:
        ast = F.parse(code, prefer_registered=prefer_registered)
    except SyntaxError as e:
        return [Diagnostic(ERROR, "parse-error", str(e))]
    return check_ast(session, ast)


def has_errors(diagnostics: List[Diagnostic]) -> bool:
    return any(d.severity == ERROR for d in diagnostics)


def format_report(diagnostics: List[Diagnostic]) -> str:
    """Render diagnostics as a block of lines, errors before warnings."""
    if not diagnostics:
        return "✓ no resolution or type problems found"
    errs = [d for d in diagnostics if d.severity == ERROR]
    warns = [d for d in diagnostics if d.severity == WARNING]
    lines = [str(d) for d in errs] + [str(d) for d in warns]
    tail = f"\n{len(errs)} error(s), {len(warns)} warning(s)"
    return "\n".join(lines) + tail
