"""User-extensible Form keywords — runtime grammar extension.

The bootstrap parser in `form.py` has a hand-written grammar. This module
makes ONE part of that grammar live: when an agent encounters an unknown
keyword, the parser consults a registry of user-registered keywords. If
a rule matches, the parser captures sub-expressions using the rule's
pattern and hands them to the rule's builder to construct the AST.

Two layers of persistence now coexist:

1. **Python in-memory registry** (`_KEYWORDS`) — the live registry the
   parser consults during a session. Patterns + builders live here.

2. **Substrate-resident persistence** — when `register_form_keyword` is
   called with a `session`, the pattern is serialized to a Recipe NodeID
   via `pattern_to_recipe` and stored as a Cell in the `grammar` domain.
   The builder is referenced by name (registered via `register_builder`)
   so it can be re-bound after process restart.

`load_keyword_from_substrate(session, name)` reconstructs the in-memory
registration from the substrate: pattern recipe → Pattern, builder name
→ Python callable from the builder registry.

What this module is NOT yet:
- Builders are still Python callables. A substrate-resident builder
  would need a recipe execution engine that walks a Build template and
  substitutes captures. That's a future breath.
- Backtracking is implicit (try-and-rewind via parser.pos save/restore),
  not Choice.FAIL-driven speculation.
- Self-hosting: form.py's bootstrap is still hardcoded. Re-expressing
  built-in keywords (if, do, match, etc.) via this registry is future.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.substrate.category import (
    BBasic,
    BDomain,
    Level,
    RBasic,
    RBlock,
    RCond,
    RType,
)


# ---------------------------------------------------------------------------
# Pattern primitives
# ---------------------------------------------------------------------------


@dataclass
class Literal:
    """Match a single token by kind + optional value."""
    kind: str                       # token kind (e.g. "IDENT", "PROJECT")
    value: Optional[str] = None     # exact value to match (or None for any)


@dataclass
class Capture:
    """Capture a sub-expression under a name.

    `kind` is the parser-rule to invoke for this capture:
      - "expr" — any expression (calls parse_expr)
      - "primary" — a primary atom only
    """
    name: str
    kind: str = "expr"


@dataclass
class Sequence:
    """Match a sequence of patterns in order."""
    parts: List[Any]


@dataclass
class Optional_:
    """Match a sub-pattern if it's there; succeed with no captures otherwise."""
    pattern: Any


# Public alias — `Optional_` would shadow typing.Optional otherwise
Opt = Optional_


@dataclass
class IdentCapture:
    """Capture a raw IDENT token's *value* as a string.

    Distinct from `Capture(name, "expr")` which parses the next token(s)
    as an expression. IdentCapture takes a single IDENT token and binds
    its string value directly. Used for `let <name> = ...` where `name`
    is a raw identifier, not a sub-expression.
    """
    name: str


@dataclass
class RepeatedCapture:
    """Match `item_pattern` zero or more times; bind the resulting list.

    When `item_pattern` is a single Capture, the captured list contains
    the captured values (e.g. expressions) directly. When `item_pattern`
    is a Sequence with multiple captures, each iteration's captures dict
    is appended to the list.

    `separator` (if provided) must match between successive items.
    If `separator` is absent, items are matched greedily until one fails.
    """
    name: str
    item_pattern: Any
    separator: Any = None  # Optional Literal (or any pattern) to match between items


# ---------------------------------------------------------------------------
# Match engine
# ---------------------------------------------------------------------------


@dataclass
class MatchResult:
    success: bool
    captures: Dict[str, Any] = field(default_factory=dict)


def try_match(parser, pattern: Any) -> MatchResult:
    """Try to match a pattern against the parser's current position.

    Delegates to the structured speculation engine in form_speculation.
    On success, returns MatchResult(success=True, captures=...). On
    fail, the speculation engine cleanly unwinds parser state — without
    sediment — and returns MatchResult(success=False).

    Captures partially-populated during a failed attempt are also
    cleared, not just `parser.pos`. The previous ad-hoc save/restore
    only restored position; the speculation engine restores the full
    captured state.
    """
    from app.services.substrate.form_speculation import speculate
    result = speculate(parser, pattern)
    if result.success:
        return MatchResult(True, result.captures)
    return MatchResult(False)


def _do_match(parser, pattern: Any, captures: Dict[str, Any]) -> bool:
    if isinstance(pattern, Literal):
        t = parser.peek()
        if t.kind != pattern.kind:
            return False
        if pattern.value is not None and t.value != pattern.value:
            return False
        parser.consume(pattern.kind)
        return True

    if isinstance(pattern, Capture):
        try:
            if pattern.kind == "expr":
                node = parser.parse_expr()
            elif pattern.kind == "primary":
                node = parser.parse_primary()
            else:
                return False
        except SyntaxError:
            return False
        captures[pattern.name] = node
        return True

    if isinstance(pattern, IdentCapture):
        t = parser.peek()
        if t.kind != "IDENT":
            return False
        captures[pattern.name] = t.value
        parser.consume("IDENT")
        return True

    if isinstance(pattern, RepeatedCapture):
        items: List[Any] = []
        # Determine whether item_pattern produces a single value or a dict
        single_capture_name = _single_capture_name(pattern.item_pattern)

        while True:
            saved = parser.pos
            sub_captures: Dict[str, Any] = {}
            if not _do_match(parser, pattern.item_pattern, sub_captures):
                parser.pos = saved
                break
            if single_capture_name is not None:
                items.append(sub_captures.get(single_capture_name))
            else:
                items.append(dict(sub_captures))

            # If a separator is required, match it; if it fails, we're done.
            if pattern.separator is not None:
                sep_saved = parser.pos
                if not _do_match(parser, pattern.separator, {}):
                    parser.pos = sep_saved
                    break

        captures[pattern.name] = items
        return True

    if isinstance(pattern, Sequence):
        for part in pattern.parts:
            if not _do_match(parser, part, captures):
                return False
        return True

    if isinstance(pattern, Optional_):
        saved = parser.pos
        sub_captures: Dict[str, Any] = {}
        if _do_match(parser, pattern.pattern, sub_captures):
            captures.update(sub_captures)
            return True
        parser.pos = saved
        return True  # optional: not matching is success

    return False


def _single_capture_name(pattern: Any) -> Optional[str]:
    """If `pattern` is a single Capture (or IdentCapture), return its name.
    Otherwise return None — RepeatedCapture should yield dicts."""
    if isinstance(pattern, Capture):
        return pattern.name
    if isinstance(pattern, IdentCapture):
        return pattern.name
    return None


# ---------------------------------------------------------------------------
# Pattern serialization — patterns ↔ Recipe NodeIDs
# ---------------------------------------------------------------------------
#
# Each pattern primitive maps to a Recipe in the substrate:
#
#   Literal(kind, value)       → Block.SEQUENCE recipe with two
#                                 string-literal children: kind, value
#   Capture(name, kind)        → Block.LET recipe with two string-literal
#                                 children: name, kind
#   Sequence([p1, p2, ...])    → Block.SEQUENCE recipe with each part
#                                 serialized as a sub-recipe child
#   Opt(pattern)               → Cond.IF_THEN recipe with the inner
#                                 pattern as its single child
#
# This mapping uses existing Recipe categories — no new vocabulary needed.
# Two structurally-identical patterns dedupe through the kernel's content-
# addressed interning. The serialized form is round-trippable.


def _string_recipe_id(value: str) -> "NodeIDForRecipe":
    """Encode a string as a trivial String recipe NodeID.

    Uses the same hash-based instance-allocation as the markdown frontend's
    string-literal handling. NOT cross-process stable; future work moves
    string interning to a substrate string-table.
    """
    from app.services.substrate.kernel import NodeID
    inst = abs(hash(value)) % (10**9) + 1
    return NodeID(1, Level.TRIVIAL, RType.STRING, inst)


def _literal_marker_id() -> "NodeIDForRecipe":
    """Block.SEQUENCE category — used as the literal-pattern wrapper."""
    from app.services.substrate.kernel import NodeID
    return NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.SEQUENCE)


def _capture_marker_id() -> "NodeIDForRecipe":
    """Block.LET category — used as the capture-pattern wrapper."""
    from app.services.substrate.kernel import NodeID
    return NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.LET)


def _opt_marker_id() -> "NodeIDForRecipe":
    """Cond.IF_THEN category — used as the optional-pattern wrapper."""
    from app.services.substrate.kernel import NodeID
    return NodeID(1, Level.BASIC, RBasic.COND, RCond.IF_THEN)


def pattern_to_recipe(session: Session, pattern: Any):
    """Serialize a pattern to a Recipe NodeID. Two structurally-identical
    patterns share a NodeID via the kernel's content-addressed interning.
    """
    from app.services.substrate.kernel import DOMAIN_RECIPE, intern_node

    if isinstance(pattern, Literal):
        kind_id = _string_recipe_id(pattern.kind, session)
        value_id = _string_recipe_id(pattern.value or "", session)
        return intern_node(
            session, DOMAIN_RECIPE, _literal_marker_id(), [kind_id, value_id]
        )

    if isinstance(pattern, Capture):
        name_id = _string_recipe_id(pattern.name, session)
        kind_id = _string_recipe_id(pattern.kind, session)
        return intern_node(
            session, DOMAIN_RECIPE, _capture_marker_id(), [name_id, kind_id]
        )

    if isinstance(pattern, IdentCapture):
        # Encoded as Capture with kind="__ident__" — a special-cased kind
        # that the deserializer recognizes.
        name_id = _string_recipe_id(pattern.name, session)
        kind_id = _string_recipe_id("__ident__", session)
        return intern_node(
            session, DOMAIN_RECIPE, _capture_marker_id(), [name_id, kind_id]
        )

    if isinstance(pattern, RepeatedCapture):
        # Encoded as Block.SEQUENCE with marker "__repeat__":
        # [str("__repeat__"), str(name), item_recipe, separator_recipe?]
        marker = _string_recipe_id("__repeat__", session)
        name_id = _string_recipe_id(pattern.name, session)
        item_id = pattern_to_recipe(session, pattern.item_pattern)
        children = [marker, name_id, item_id]
        if pattern.separator is not None:
            sep_id = pattern_to_recipe(session, pattern.separator)
            children.append(sep_id)
        return intern_node(
            session, DOMAIN_RECIPE, _literal_marker_id(), children
        )

    if isinstance(pattern, Sequence):
        children = [pattern_to_recipe(session, p) for p in pattern.parts]
        # We use a marker child to distinguish Sequence from Literal (both
        # use Block.SEQUENCE category). The marker is a string "seq".
        marker = _string_recipe_id("__seq__", session)
        return intern_node(
            session, DOMAIN_RECIPE, _literal_marker_id(), [marker] + children
        )

    if isinstance(pattern, Optional_):
        inner = pattern_to_recipe(session, pattern.pattern)
        return intern_node(session, DOMAIN_RECIPE, _opt_marker_id(), [inner])

    raise TypeError(f"Form: cannot serialize pattern {type(pattern).__name__}")


def recipe_to_pattern(session: Session, recipe_id) -> Any:
    """Reverse of pattern_to_recipe: reconstruct a Python Pattern from a
    Recipe NodeID."""
    from app.services.substrate.orm import SubstrateNodeORM

    row = (
        session.query(SubstrateNodeORM)
        .filter_by(
            package=recipe_id.package, level=recipe_id.level,
            type_=recipe_id.type_, instance=recipe_id.instance,
        )
        .one_or_none()
    )
    if row is None:
        raise LookupError(f"Form: pattern recipe {recipe_id} not found in substrate")

    parts = row.serialized.split("+")
    category = _parse_node_id_str(parts[0])
    children_ids = [_parse_node_id_str(p) for p in parts[1:]]

    # Cond.IF_THEN with one child → Optional
    if category.level == Level.BASIC and category.type_ == RBasic.COND and category.instance == RCond.IF_THEN:
        if len(children_ids) == 1:
            return Optional_(pattern=recipe_to_pattern(session, children_ids[0]))

    # Block.LET with two string children → Capture or IdentCapture
    if category.level == Level.BASIC and category.type_ == RBasic.BLOCK and category.instance == RBlock.LET:
        if len(children_ids) == 2:
            name = _string_from_recipe(session, children_ids[0])
            kind = _string_from_recipe(session, children_ids[1])
            if kind == "__ident__":
                return IdentCapture(name=name)
            return Capture(name=name, kind=kind)

    # Block.SEQUENCE with various marker patterns
    if category.level == Level.BASIC and category.type_ == RBasic.BLOCK and category.instance == RBlock.SEQUENCE:
        if len(children_ids) == 2:
            kind_str = _string_from_recipe(session, children_ids[0])
            value_str = _string_from_recipe(session, children_ids[1])
            if kind_str not in ("__seq__", "__repeat__"):
                return Literal(kind=kind_str, value=value_str if value_str else None)

        if len(children_ids) >= 1:
            marker = _string_from_recipe(session, children_ids[0])
            if marker == "__seq__":
                parts_list = [recipe_to_pattern(session, c) for c in children_ids[1:]]
                return Sequence(parts=parts_list)
            if marker == "__repeat__":
                # [marker, name, item_pattern, separator?]
                if len(children_ids) >= 3:
                    name = _string_from_recipe(session, children_ids[1])
                    item_pattern = recipe_to_pattern(session, children_ids[2])
                    separator = None
                    if len(children_ids) >= 4:
                        separator = recipe_to_pattern(session, children_ids[3])
                    return RepeatedCapture(
                        name=name, item_pattern=item_pattern, separator=separator,
                    )

    raise ValueError(f"Form: unrecognized pattern recipe shape at {recipe_id}")


def _parse_node_id_str(s: str):
    """Parse 'p.l.t.i' back into a NodeID."""
    from app.services.substrate.kernel import NodeID
    parts = s.split(".")
    if len(parts) != 4:
        raise ValueError(f"Form: malformed NodeID string {s!r}")
    return NodeID(int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))


def _string_from_recipe(session: Optional[Session], recipe_id) -> str:
    """Reverse-lookup a string-literal recipe to its original string value.

    Uses the substrate string-table when `session` is provided (cross-
    process stable). Falls back to the in-process `_STRING_CACHE` when
    not — for unit tests of bare functions without DB access.
    """
    if session is not None:
        from app.services.substrate.substrate_strings import lookup_string_value
        value = lookup_string_value(session, recipe_id.instance)
        if value is not None:
            return value
    return _STRING_CACHE.get(_node_id_key(recipe_id), "")


# In-process cache. Populated by `_string_recipe_id` whether or not a
# session is in play. Keeps `_string_from_recipe(None, ...)` working.
_STRING_CACHE: Dict[tuple, str] = {}


def _node_id_key(node_id) -> tuple:
    return (node_id.package, node_id.level, node_id.type_, node_id.instance)


def _string_recipe_id(value: str, session: Optional[Session] = None):
    """Encode a string as a trivial String recipe NodeID.

    When `session` is provided, uses the substrate string-table — the
    instance is sequentially-allocated and cross-process stable. Without
    a session, falls back to the legacy hash-based allocation (in-process
    only). Either path populates `_STRING_CACHE` so the reverse lookup
    can resolve.
    """
    from app.services.substrate.kernel import NodeID
    if session is not None:
        from app.services.substrate.substrate_strings import intern_string_instance
        inst = intern_string_instance(session, value)
    else:
        inst = abs(hash(value)) % (10**9) + 1
    nid = NodeID(1, Level.TRIVIAL, RType.STRING, inst)
    _STRING_CACHE[_node_id_key(nid)] = value
    return nid


# ---------------------------------------------------------------------------
# Builder registry — name → callable, for substrate-resident lookup
# ---------------------------------------------------------------------------


_BUILDERS: Dict[str, Callable[[Dict[str, Any]], Any]] = {}


def register_builder(name: str, builder: Callable[[Dict[str, Any]], Any]) -> None:
    """Register a named builder. Used by `register_form_keyword` to bind
    the keyword's builder under a name so it can be recovered after
    substrate persistence + process restart."""
    _BUILDERS[name] = builder


def lookup_builder(name: str) -> Optional[Callable[[Dict[str, Any]], Any]]:
    return _BUILDERS.get(name)


def list_builders() -> List[str]:
    return list(_BUILDERS.keys())


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


# `keyword_name` → (pattern, builder)
# Pattern is a RulePattern; builder takes captures dict and returns an AST node.
_KEYWORDS: Dict[str, tuple] = {}


def register_form_keyword(
    name: str,
    pattern: Any,
    builder: Optional[Callable[[Dict[str, Any]], Any]] = None,
    *,
    template: Any = None,
    ast_module: Any = None,
    session: Optional[Session] = None,
    builder_name: Optional[str] = None,
) -> None:
    """Register a user-defined Form keyword.

    Two builder forms are supported:

    1. `builder=<callable>` — Python function from captures to AST.
       The substrate stores the builder *name* as a tag; the callable
       must be re-registered after process restart via `register_builder`.

    2. `template=<Build/CaptureRef/Const tree>` — substrate-resident
       data. The template is serialized to a Recipe NodeID stored as the
       rule's action. After process restart, the template is reconstructed
       from the substrate; no Python re-registration needed. Pass
       `ast_module` so the interpreter can resolve class names (defaults
       to `app.services.substrate.form`).

    Either form can be combined with `session=` for substrate
    persistence of the pattern.
    """
    if builder is None and template is None:
        raise ValueError("register_form_keyword: pass either builder= or template=")

    if ast_module is None:
        from app.services.substrate import form as _form_mod
        ast_module = _form_mod

    if template is not None:
        from app.services.substrate.form_builders import make_builder_from_template
        builder = make_builder_from_template(template, ast_module)

    _KEYWORDS[name] = (pattern, builder)

    bn = builder_name or name
    register_builder(bn, builder)

    if session is not None:
        from app.services.substrate.grammar import register_form_rule
        pattern_recipe_id = pattern_to_recipe(session, pattern)
        if template is not None:
            from app.services.substrate.form_builders import template_to_recipe
            action_recipe_id = template_to_recipe(session, template)
        else:
            # The action recipe is a string-literal carrying the builder's
            # name. After reload, the builder is recovered from the named
            # registry via lookup_builder.
            action_recipe_id = _string_recipe_id(bn, session)
        register_form_rule(session, name, pattern_recipe_id, action_recipe_id)


def load_keyword_from_substrate(
    session: Session, name: str, *, ast_module: Any = None,
) -> Optional[tuple]:
    """Reconstruct a keyword's (pattern, builder) from the substrate.

    Lookup order for the builder:
    1. The action recipe is a string-literal — try lookup_builder(string)
       to find a Python callable that was re-registered at boot.
    2. The action recipe is a Build template — reconstruct it via
       recipe_to_template and wrap with make_builder_from_template.
       This path needs no Python pre-registration. Pass `ast_module` to
       resolve AST class names (defaults to substrate.form).

    Side effect: registers the keyword in the in-memory `_KEYWORDS` so
    the parser will pick it up.
    """
    from app.services.substrate.grammar import lookup_form_rule

    rule = lookup_form_rule(session, name)
    if rule is None or rule.pattern.is_undefined():
        return None
    try:
        pattern = recipe_to_pattern(session, rule.pattern)
    except (LookupError, ValueError):
        return None

    builder = None

    # Path 1: action is a string-literal carrying the builder name
    if rule.action.level == Level.TRIVIAL and rule.action.type_ == RType.STRING:
        builder_name = _string_from_recipe(session, rule.action)
        if builder_name:
            builder = lookup_builder(builder_name)

    # Path 2: action is a Build template — reconstruct
    if builder is None:
        try:
            from app.services.substrate.form_builders import (
                make_builder_from_template,
                recipe_to_template,
            )
            template = recipe_to_template(session, rule.action)
            if ast_module is None:
                from app.services.substrate import form as _form_mod
                ast_module = _form_mod
            builder = make_builder_from_template(template, ast_module)
        except (LookupError, ValueError, NameError):
            return None

    if builder is None:
        return None

    _KEYWORDS[name] = (pattern, builder)
    return (pattern, builder)


def load_all_keywords_from_substrate(session: Session) -> List[str]:
    """Walk every rule cell in the grammar domain and reconstruct each
    keyword. Returns the names that were successfully loaded."""
    from app.services.substrate.grammar import list_form_rules

    loaded = []
    for rule in list_form_rules(session):
        if load_keyword_from_substrate(session, rule.name) is not None:
            loaded.append(rule.name)
    return loaded


def unregister_form_keyword(name: str) -> bool:
    """Remove a keyword from the registry. Useful in tests."""
    return _KEYWORDS.pop(name, None) is not None


def lookup_form_keyword(name: str) -> Optional[tuple]:
    """Return (pattern, builder) or None."""
    return _KEYWORDS.get(name)


def list_registered_keywords() -> List[str]:
    """All currently-registered keyword names."""
    return list(_KEYWORDS.keys())


def try_apply_keyword_rule(parser, name: str) -> Optional[Any]:
    """If `name` is a registered keyword, try its rule against the parser.

    Returns the built AST node on success, None on miss-or-fail.
    Note: parser.pos is NOT consumed past 'name' on entry — the rule's
    pattern itself must match the keyword token (typically as the first
    Literal in the Sequence).
    """
    entry = _KEYWORDS.get(name)
    if entry is None:
        return None
    pattern, builder = entry
    result = try_match(parser, pattern)
    if not result.success:
        return None
    return builder(result.captures)
