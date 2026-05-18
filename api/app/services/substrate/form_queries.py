"""Runtime-extensible query-verb registry for Form.

A Form query is `?<verb> [arg] [|> bp] [where filter, ...]`. Until now,
`form._evaluate_query` dispatched on `q.kind` via a hardcoded if/elif
chain — adding a new verb meant editing form.py. This module lifts the
dispatch into a registry so any module can register its own `?<verb>`
handler at runtime.

Each handler has signature:

    (session: Session, q: Query) -> FormResult

The handler inspects `q.arg` (the optional argument expression) and
`q.filters` (the parsed `where field op value` items), then returns a
typed `FormResult`. All 10 built-in query verbs are registered here as
the seed set; `_evaluate_query` in form.py is now a one-line dispatch
through this registry.

The closing of the gap form-language.md → "Query operators are still
hardcoded in `_evaluate_query`": no longer hardcoded — substrate-
runtime-resident handlers, registerable at runtime.

See also:
- `form_rules.py` — the keyword registry (parses runtime keywords)
- `form_eval.py` — the operator-category registry (interns op recipes)
- This module — the query registry (dispatches ?-verbs)

Together they form the three runtime-extensible registries the parser
consults; `form.py`'s remaining hardcoded paths become smaller with
each registry that lifts dispatch out of the if/elif chain.
"""
from __future__ import annotations

from typing import Callable, Dict, List

from sqlalchemy.orm import Session


# Handler signature: (session, q) -> FormResult.
# `q` is a `form.Query` dataclass with `.kind`, `.arg`, and `.filters`.
QueryHandler = Callable[[Session, "Query"], "FormResult"]  # noqa: F821


_QUERY_HANDLERS: Dict[str, QueryHandler] = {}


def register_form_query(verb: str, handler: QueryHandler) -> None:
    """Register a handler for `?<verb>`. Overwrites any existing.

    Body's discipline: keep the verb short, lowercase, ident-shaped.
    The same name that goes after `?` is what registers here."""
    if not verb or not verb.replace("_", "").isalnum():
        raise ValueError(f"form_queries: verb must be ident-shaped, got {verb!r}")
    _QUERY_HANDLERS[verb] = handler


def unregister_form_query(verb: str) -> bool:
    """Remove a registered query handler. Returns True if removed."""
    return _QUERY_HANDLERS.pop(verb, None) is not None


def lookup_form_query(verb: str) -> QueryHandler | None:
    return _QUERY_HANDLERS.get(verb)


def list_form_queries() -> List[str]:
    """Names of every registered `?<verb>`. Used by `?keywords`-style
    introspection — exposing the body's own query vocabulary."""
    return sorted(_QUERY_HANDLERS.keys())


def dispatch_query(session: Session, q: "Query") -> "FormResult":  # noqa: F821
    """Dispatch a query through the registry. Raises NameError if no
    handler is registered for `q.kind`."""
    handler = _QUERY_HANDLERS.get(q.kind)
    if handler is None:
        raise NameError(f"Form: unknown query kind {q.kind!r}")
    return handler(session, q)


# ---------------------------------------------------------------------------
# Built-in query handlers — the seed set
# ---------------------------------------------------------------------------
#
# Each handler is the same body that used to live in
# `form._evaluate_query`'s if/elif chain. Lifting them here makes them
# replaceable: a sibling module could `register_form_query("cells", ...)`
# to override the cell-listing semantics for a custom workspace.


def _handle_equivalent(session: Session, q):
    from app.services.substrate.form import FormResult, evaluate
    from app.services.substrate.kernel import find_equivalent_cells

    target = evaluate(session, q.arg)
    if target.kind == "cell":
        cells = find_equivalent_cells(
            session, target.value.blueprint, exclude_name=target.value.name
        )
        return FormResult("cells", cells)
    if target.kind == "node_id":
        cells = find_equivalent_cells(session, target.value)
        return FormResult("cells", cells)
    raise TypeError(
        f"Form: ?equivalent expects cell or node_id, got {target.kind}"
    )


def _handle_compatible(session: Session, q):
    from app.services.substrate.form import FormResult, evaluate
    from app.services.substrate.kernel import find_cells_compatible_with

    bp_result = evaluate(session, q.arg)
    if bp_result.kind != "node_id":
        raise TypeError(f"Form: ?compatible |> expects a NodeID")
    views = find_cells_compatible_with(session, bp_result.value)
    return FormResult("views", views)


def _handle_lattice(session: Session, q):
    """Substrate-snapshot lens — read-only count of every interned thing."""
    from app.services.substrate.form import FormResult
    from app.services.substrate.kernel import lattice_stats

    return FormResult("lattice", lattice_stats(session))


def _handle_keywords(session: Session, q):
    """Grammar-introspection lens — names of every runtime-registered keyword."""
    from app.services.substrate.form import FormResult
    from app.services.substrate.form_rules import list_registered_keywords

    return FormResult("keywords", list_registered_keywords())


def _handle_vocabulary(session: Session, q):
    """Verb-cluster lens — histogram of recipe/blueprint types currently interned."""
    from app.services.substrate.form import FormResult
    from app.services.substrate.kernel import vocabulary_histogram

    return FormResult("vocabulary", vocabulary_histogram(session))


def _handle_queries(session: Session, q):
    """Query-vocabulary lens — names of every registered ?-verb.

    Closes a small loop: now that the queries are substrate-resident,
    Form can ask `?queries` and see which `?<verb>`s the body holds.
    Sibling to `?keywords` (parser-level introspection) and `?vocabulary`
    (recipe-cluster introspection)."""
    from app.services.substrate.form import FormResult

    return FormResult("keywords", list_form_queries())


def _handle_recipe_intent(session: Session, q):
    """Reactive (?on_change) / spatial-projection (?project) verbs both
    intern their argument as a Recipe NodeID. The subscription engine
    and the renderer pick it up downstream."""
    from app.services.substrate.form import FormResult, _to_recipe_node_id

    rid = _to_recipe_node_id(session, q.arg)
    return FormResult("recipe", rid)


def _handle_resonance_walk(session: Session, q):
    """`?shaped_by @<cell>` and `?harmonic_at @<cell>` — return source
    cells whose resonance edge of the named verb points at the target."""
    from app.services.substrate.form import FormResult, evaluate
    from app.services.substrate.kernel import _orm_to_cell
    from app.services.substrate.orm import SubstrateNamedCellORM
    from app.services.substrate.resonance import (
        find_cells_harmonic_at,
        find_cells_shaping,
    )

    rhs = evaluate(session, q.arg)
    if rhs.kind != "cell":
        raise TypeError(
            f"Form: ?{q.kind} expects a cell ref on the right, got {rhs.kind}"
        )
    target_db_id = rhs.value.cell_id
    if target_db_id is None:
        raise LookupError(f"Form: target cell has no db id (was it persisted?)")

    if q.kind == "shaped_by":
        source_db_ids = find_cells_shaping(session, target_db_id)
    else:
        source_db_ids = find_cells_harmonic_at(session, target_db_id)

    cells = []
    for sid in source_db_ids:
        row = (
            session.query(SubstrateNamedCellORM)
            .filter_by(cell_id=sid)
            .one_or_none()
        )
        if row:
            cells.append(_orm_to_cell(session, row))
    return FormResult("cells", cells)


def _handle_cells(session: Session, q):
    """`?cells [|> @bp] [where ...]` — the most versatile query verb.

    Without args/filters, returns every cell. With a `|>` projection,
    returns CellViews. With filters, applies them to the cells table."""
    from app.services.substrate.form import FormResult, evaluate
    from app.services.substrate.kernel import (
        _node_to_db_id,
        _orm_to_cell,
        find_cells_compatible_with,
    )
    from app.services.substrate.kernel import NamedCell  # noqa: F401
    from app.services.substrate.orm import SubstrateNamedCellORM

    if q.arg is not None:
        # ?cells |> @blueprint — return CellViews, optionally domain-filtered
        bp_result = evaluate(session, q.arg)
        if bp_result.kind != "node_id":
            raise TypeError(f"Form: ?cells |> expects a NodeID")
        domain_filter = None
        for f in q.filters:
            if f.field == "domain" and f.op == "==":
                domain_filter = f.value
        views = find_cells_compatible_with(
            session, bp_result.value, domain=domain_filter
        )
        return FormResult("views", views)

    # ?cells [where ...] — return raw cells, filters applied
    rows = session.query(SubstrateNamedCellORM)
    for f in q.filters:
        if f.field == "domain" and f.op == "==" and isinstance(f.value, str):
            rows = rows.filter_by(domain=f.value)
        elif f.field == "name" and f.op == "matches" and isinstance(f.value, str):
            rows = rows.filter(
                SubstrateNamedCellORM.name.like(f.value.replace("*", "%"))
            )
        elif f.field == "shape" and f.op == "==":
            rhs = evaluate(session, f.value)
            if rhs.kind == "node_id":
                target_bp = rhs.value
            elif rhs.kind == "cell":
                target_bp = rhs.value.blueprint
            else:
                raise TypeError(
                    f"Form: ?cells where shape == ... expects a NodeID or cell rhs, "
                    f"got {rhs.kind}"
                )
            target_bp_db = _node_to_db_id(session, target_bp)
            rows = rows.filter(
                SubstrateNamedCellORM.blueprint_node_id == target_bp_db
            )
        else:
            raise SyntaxError(
                f"Form: unsupported filter ({f.field!r} {f.op!r} "
                f"{type(f.value).__name__})"
            )
    cells = [_orm_to_cell(session, r) for r in rows.all()]
    return FormResult("cells", cells)


def _register_builtins() -> None:
    """Register the 10 built-in query verbs. Called at module import so
    the seed set is available before any user-registered handler."""
    register_form_query("equivalent", _handle_equivalent)
    register_form_query("compatible", _handle_compatible)
    register_form_query("lattice", _handle_lattice)
    register_form_query("keywords", _handle_keywords)
    register_form_query("vocabulary", _handle_vocabulary)
    register_form_query("queries", _handle_queries)
    register_form_query("on_change", _handle_recipe_intent)
    register_form_query("project", _handle_recipe_intent)
    register_form_query("shaped_by", _handle_resonance_walk)
    register_form_query("harmonic_at", _handle_resonance_walk)
    register_form_query("cells", _handle_cells)


_register_builtins()


__all__ = [
    "QueryHandler",
    "register_form_query",
    "unregister_form_query",
    "lookup_form_query",
    "list_form_queries",
    "dispatch_query",
]
