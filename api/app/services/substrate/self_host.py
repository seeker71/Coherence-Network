"""Bootstrap self-hosting — Form's grammar expressed as Form rules.

Step 6 of the bootstrap-to-self-hosting path. The bootstrap parser
(`form.py`) carries Python code for `if`, `do`, `match`, `let`,
`choose`, `fail`, `stop`. This module re-expresses each (where the
current pattern DSL allows) as substrate-resident `(pattern, template)`
pairs registered via `register_form_keyword`.

What's currently expressible with the existing pattern DSL:

  if cond then body [else other]
      pure expression captures, no special syntax

What needs pattern-DSL extensions to express (future work):

  do { stmt; stmt; ...; expr }      ← needs RepeatedCapture(separator=";")
  let name = expr                    ← needs IdentCapture (raw IDENT name,
                                       not parsed as a sub-expression)
  match x { pat => body, ... }       ← RepeatedCapture for arms,
                                       and a "=>" infix pattern
  choose [a, b, c]                   ← RepeatedCapture inside `[...]`
  fail / stop                        ← bare-keyword leaf pattern
  arithmetic / comparison / logic    ← needs precedence-aware pattern
                                       primitives or operator-precedence
                                       declarations

This module ships **partial self-hosting**: `if` (and the user-style
`unless` and `whenever`) — the cases the current pattern DSL can fully
express. The proof: when `prefer_registered=True`, the parser uses
these templates and produces Recipe NodeIDs IDENTICAL to the bootstrap.

The remaining keywords stay in the bootstrap until the pattern DSL
grows IdentCapture + RepeatedCapture. Each of those is its own breath.
"""
from __future__ import annotations

from typing import Any, List

from sqlalchemy.orm import Session

from app.services.substrate.form_builders import Build, CaptureRef, Const
from app.services.substrate.form_rules import (
    Capture,
    Literal,
    Opt,
    Sequence,
    register_form_keyword,
)


def bootstrap_self_host(session: Session, ast_module: Any = None) -> List[str]:
    """Register the bootstrap keywords (that the current pattern DSL can
    express) as substrate-resident `(pattern, template)` pairs.

    Returns the list of keyword names that were registered.

    To use the registered versions in parsing, set
    `prefer_registered=True` on `form_parse` / `form_evaluate_text`.
    Otherwise the bootstrap hardcoded handlers continue to take priority.
    """
    if ast_module is None:
        from app.services.substrate import form as _form_mod
        ast_module = _form_mod

    registered: List[str] = []

    # `if cond then then_branch [else else_branch]`
    register_form_keyword(
        "if",
        Sequence([
            Literal("IDENT", "if"),
            Capture("cond"),
            Literal("IDENT", "then"),
            Capture("then_branch"),
            Opt(Sequence([
                Literal("IDENT", "else"),
                Capture("else_branch"),
            ])),
        ]),
        template=Build(
            "IfExpr",
            cond=CaptureRef("cond"),
            then_branch=CaptureRef("then_branch"),
            else_branch=CaptureRef("else_branch", default=None),
        ),
        ast_module=ast_module,
        session=session,
    )
    registered.append("if")

    # `unless cond then body [else other]` — desugars to `if !cond then ...`
    register_form_keyword(
        "unless",
        Sequence([
            Literal("IDENT", "unless"),
            Capture("cond"),
            Literal("IDENT", "then"),
            Capture("body"),
            Opt(Sequence([
                Literal("IDENT", "else"),
                Capture("other"),
            ])),
        ]),
        template=Build(
            "IfExpr",
            cond=Build("UnaryOp", op=Const("!"), operand=CaptureRef("cond")),
            then_branch=CaptureRef("body"),
            else_branch=CaptureRef("other", default=None),
        ),
        ast_module=ast_module,
        session=session,
    )
    registered.append("unless")

    # `whenever cond do body` — desugars to `if cond then body`
    register_form_keyword(
        "whenever",
        Sequence([
            Literal("IDENT", "whenever"),
            Capture("cond"),
            Literal("IDENT", "do"),
            Capture("body"),
        ]),
        template=Build(
            "IfExpr",
            cond=CaptureRef("cond"),
            then_branch=CaptureRef("body"),
            else_branch=Const(None),
        ),
        ast_module=ast_module,
        session=session,
    )
    registered.append("whenever")

    return registered


def list_bootstrap_self_host_keywords() -> List[str]:
    """Return the set of bootstrap keywords that `bootstrap_self_host`
    currently re-expresses. Useful for tests + agent introspection."""
    return ["if", "unless", "whenever"]
