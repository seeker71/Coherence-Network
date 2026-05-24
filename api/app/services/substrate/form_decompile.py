"""Form decompiler — Recipe NodeID → canonical Form text.

The companion of `form_evaluate_text` (parser). The substrate is
content-addressed: two textually-different surfaces of the same shape
intern to the same Recipe NodeID. This module emits a *canonical* Form
text from any Recipe NodeID — a representative of the equivalence class
the Recipe sits in.

When chained with the parser, this gives source round-trip fidelity:

    text  ──form_evaluate_text──>  Recipe NodeID
                                         │
                                   recipe_to_form
                                         ↓
    text' ──form_evaluate_text──>  Recipe NodeID'   == Recipe NodeID

Round-trip equality at the lattice level is the strongest form of
fidelity we can express: not "same answer" (behavioral), not "matching
literals" (lexical), but "same coordinate in the content-addressed
substrate." Any prose claim that two pieces of code are structurally
equivalent can be checked by decompiling and re-parsing.

Coverage today:
    - Math arms       (PLUS / MINUS / MULTIPLY / DIVIDE / MODULO)
    - Compare arms    (EQUAL / NOT_EQUAL / LESS / LESS_EQUAL / GREATER / GREATER_EQUAL)
    - Logic arms      (AND / OR / NOT)
    - Conditional     (IF_THEN / IF_THEN_ELSE)
    - Trivial leaves  (INTEGER / STRING / BOOL / NULL via `_trivial_value`)

Adding a verb-category is mechanical: one elif arm matching the
RBasic.<verb>.value and one operator-symbol lookup. The shape mirrors
`form-engine.form`'s dispatch table arm-for-arm.

This module is the first half of closing GAP-W (substrate write) named
in `docs/coherence-substrate/form-runtime-in-form.form`: where the
runtime needs `intern_recipe` / `intern_trivial` to write recipes from
Form, the reader needs `recipe_to_form` to read them back as Form.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.substrate.category import RBasic
from app.services.substrate.kernel import NodeID
from app.services.substrate.form_runtime import (
    _CURRENT_SESSION,
    _node_category,
    _node_children,
    _trivial_value,
)

_MATH_OPS = {1: "+", 2: "-", 3: "*", 4: "/", 5: "%"}
_COMPARE_OPS = {1: "==", 2: "!=", 3: "<", 4: "<=", 5: ">", 6: ">="}
_LOGIC_OPS = {1: "&&", 2: "||"}


def recipe_to_form(session: Session, nid: NodeID) -> str:
    """Decompile a Recipe NodeID back to canonical Form source text.

    The emitted text is fully parenthesized (no precedence ambiguity)
    and uses the same operator symbols Form's parser accepts. Re-parsing
    the emitted text MUST produce the same NodeID — that is the
    round-trip property this function is for.

    Raises on verb-categories not yet supported (BLOCK/MATCH/CHOICE/
    STATE/EXCEPTION/etc.) so callers know coverage is partial. Each
    `NotImplementedError` is one mechanical arm away from coverage.
    """
    _CURRENT_SESSION[0] = session
    children = _node_children(session, nid)
    if not children:
        return _decompile_trivial(session, nid)
    cat = _node_category(session, nid)
    kids = [recipe_to_form(session, c) for c in children]
    if cat.type_ == RBasic.MATH.value:
        return f"({kids[0]} {_MATH_OPS[cat.instance]} {kids[1]})"
    if cat.type_ == RBasic.COMPARE.value:
        return f"({kids[0]} {_COMPARE_OPS[cat.instance]} {kids[1]})"
    if cat.type_ == RBasic.LOGIC.value:
        if cat.instance == 3:
            return f"(!{kids[0]})"
        return f"({kids[0]} {_LOGIC_OPS[cat.instance]} {kids[1]})"
    if cat.type_ == RBasic.COND.value:
        if cat.instance == 1:
            return f"(if {kids[0]} then {kids[1]})"
        return f"(if {kids[0]} then {kids[1]} else {kids[2]})"
    if cat.type_ == RBasic.BLOCK.value:
        # RBlock instances: 1=DO, 2=SEQUENCE, 3=LET, 4=WITH
        if cat.instance == 1:
            body = "; ".join(kids)
            return f"do {{ {body} }}"
        if cat.instance == 2:
            return "; ".join(kids)
        if cat.instance == 3:
            if len(kids) == 2:
                return f"let {kids[0]} = {kids[1]}"
            return "let (" + ", ".join(kids) + ")"
        if cat.instance == 4:
            return f"with {kids[0]} {{ {kids[1]} }}"
    if cat.type_ == RBasic.RESONANCE.value:
        # RResonance instances: 1=SHAPES, 2=HARMONIC_AT, 3=BRIDGES,
        # 4=EMBEDS_IN, 5=NEAR, 6=POLAR_TO, 7=CARRIES_RATIO
        verbs = {
            1: "SHAPES", 2: "HARMONIC_AT", 3: "BRIDGES", 4: "EMBEDS_IN",
            5: "NEAR", 6: "POLAR_TO", 7: "CARRIES_RATIO",
        }
        verb = verbs.get(cat.instance, f"RESONANCE_{cat.instance}")
        if len(kids) == 2:
            return f"({kids[0]} -{verb}-> {kids[1]})"
        return f"{verb}({', '.join(kids)})"
    if cat.type_ == RBasic.REALIZE.value:
        # RRealize instances: 1=REALIZE, 2=PARTIAL_REALIZE, 3=SUPERSEDE
        # (Other instances fall through with a verb-tagged form preserving
        # round-trip identity for the substrate even when the surface name
        # isn't fully canonical.)
        verbs = {1: "REALIZE", 2: "PARTIAL_REALIZE", 3: "SUPERSEDE"}
        verb = verbs.get(cat.instance, f"REALIZE_{cat.instance}")
        if len(kids) == 2:
            return f"({kids[0]} -{verb}-> {kids[1]})"
        return f"{verb}({', '.join(kids)})"
    if cat.type_ == RBasic.TEND.value:
        # RTend covers tend/attune/compost/release — body-relational verbs.
        # Verb names follow the RTend enum; unknown instances stay tagged
        # for round-trip identity.
        if len(kids) == 1:
            return f"TEND_{cat.instance}({kids[0]})"
        return f"TEND_{cat.instance}({', '.join(kids)})"
    # Remaining RBasic arms — each preserves verb-category + instance so
    # round-trip identity holds at the substrate level. Surface naming
    # follows the enum; specific instance verbs (e.g. `match` vs
    # `switch`) can land per-arm as the parser grows to accept them.
    if cat.type_ == RBasic.MATCH.value:
        return f"MATCH_{cat.instance}({', '.join(kids)})"
    if cat.type_ == RBasic.CHOICE.value:
        # Angelic nondeterminism: choose/fail/stop
        verbs = {1: "choose", 2: "fail", 3: "stop"}
        verb = verbs.get(cat.instance, f"CHOICE_{cat.instance}")
        return f"{verb}({', '.join(kids)})"
    if cat.type_ == RBasic.STATE.value:
        # BML save/restore/discard
        verbs = {1: "save", 2: "restore", 3: "discard"}
        verb = verbs.get(cat.instance, f"STATE_{cat.instance}")
        return f"{verb}({', '.join(kids)})"
    if cat.type_ == RBasic.EXCEPTION.value:
        verbs = {1: "raise", 2: "resume"}
        verb = verbs.get(cat.instance, f"EXCEPTION_{cat.instance}")
        return f"{verb}({', '.join(kids)})"
    if cat.type_ == RBasic.DELEGATE.value:
        if len(kids) == 2:
            return f"(delegate {kids[0]} to {kids[1]})"
        return f"DELEGATE_{cat.instance}({', '.join(kids)})"
    if cat.type_ == RBasic.REVERSE.value:
        verbs = {1: "undo", 2: "inverse"}
        verb = verbs.get(cat.instance, f"REVERSE_{cat.instance}")
        return f"{verb}({', '.join(kids)})"
    if cat.type_ == RBasic.COMMON.value:
        if len(kids) >= 2:
            return f"(common {' '.join(kids)})"
        return f"COMMON_{cat.instance}({', '.join(kids)})"
    if cat.type_ == RBasic.METHOD.value:
        # METHOD recipes carry (receiver, method-name, args...)
        if len(kids) >= 2:
            return f"({kids[0]}.{kids[1]}({', '.join(kids[2:])}))"
        return f"METHOD_{cat.instance}({', '.join(kids)})"
    if cat.type_ == RBasic.REACTIVE.value:
        # on_change / subscription primitives
        verbs = {1: "on_change", 2: "subscribe"}
        verb = verbs.get(cat.instance, f"REACTIVE_{cat.instance}")
        return f"{verb}({', '.join(kids)})"
    if cat.type_ == RBasic.PROJECTION.value:
        # `|>` projection
        if len(kids) == 2:
            return f"({kids[0]} |> {kids[1]})"
        return f"PROJECTION_{cat.instance}({', '.join(kids)})"
    if cat.type_ == RBasic.TRY.value:
        if len(kids) == 2:
            return f"try {{ {kids[0]} }} catch {{ {kids[1]} }}"
        return f"TRY_{cat.instance}({', '.join(kids)})"
    raise NotImplementedError(
        f"recipe_to_form: verb-category {cat} not yet covered. "
        f"Add one elif arm matching the RBasic.<verb>.value."
    )


def _decompile_trivial(session: Session, nid: NodeID) -> str:
    """Decode a trivial-leaf Recipe back to its Form surface.

    Type-aware: SLUGs render as bare identifiers (no quotes) since they
    carry the identity-role; STRINGs render quoted as content. This is
    what lets `let x = 42` round-trip — the Identifier `x` interns as
    SLUG and decompiles back to the bare name, not the quoted string.
    """
    from app.services.substrate.category import RType
    value = _trivial_value(session, nid)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return "null"
    if isinstance(value, str):
        if nid.type_ == RType.SLUG:
            return value  # bare identifier, no quotes
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise NotImplementedError(
        f"recipe_to_form: trivial value type {type(value).__name__} not yet covered."
    )
