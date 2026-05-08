"""Bootstrap self-hosting — Form's grammar expressed as Form rules.

Step 6 of the bootstrap-to-self-hosting path. The bootstrap parser
(`form.py`) carries Python code for `if`, `do`, `match`, `let`,
`choose`, `fail`, `stop`. This module re-expresses each (where the
current pattern DSL allows) as substrate-resident `(pattern, template)`
pairs registered via `register_form_keyword`.

Currently expressible with the pattern DSL (after IdentCapture +
RepeatedCapture extensions):

  if cond then body [else other]    Capture(cond), Capture(body), Opt(else)
  let name = value                   IdentCapture(name) + Capture(value)
  fail                               bare-keyword leaf
  stop                               bare-keyword leaf
  choose [a, b, c]                   RepeatedCapture with `,` separator
  do { stmt; stmt; ...; expr }       RepeatedCapture with `;` separator

What still needs further pattern-DSL extensions:

  match x { pat => body, ... }       ← needs MapBuild to wrap each captured
                                       arm-dict as a MatchArm AST instance
  arithmetic / comparison / logic    ← needs precedence-aware pattern
                                       primitives or operator-precedence
                                       declarations

This module ships **expanded partial self-hosting**: every keyword
listed above produces Recipe NodeIDs IDENTICAL to the bootstrap when
`prefer_registered=True`.
"""
from __future__ import annotations

from typing import Any, List

from sqlalchemy.orm import Session

from app.services.substrate.form_builders import Build, CaptureRef, Const
from app.services.substrate.form_rules import (
    Capture,
    IdentCapture,
    Literal,
    Opt,
    RepeatedCapture,
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

    # `let name = value` — IdentCapture binds `name` as a string
    register_form_keyword(
        "let",
        Sequence([
            Literal("IDENT", "let"),
            IdentCapture("name"),
            Literal("ASSIGN", None),
            Capture("value"),
        ]),
        template=Build(
            "Let",
            name=CaptureRef("name"),
            value=CaptureRef("value"),
        ),
        ast_module=ast_module,
        session=session,
    )
    registered.append("let")

    # `fail` — bare-keyword leaf
    register_form_keyword(
        "fail",
        Sequence([Literal("IDENT", "fail")]),
        template=Build("FailExpr"),
        ast_module=ast_module,
        session=session,
    )
    registered.append("fail")

    # `stop` — bare-keyword leaf
    register_form_keyword(
        "stop",
        Sequence([Literal("IDENT", "stop")]),
        template=Build("StopExpr"),
        ast_module=ast_module,
        session=session,
    )
    registered.append("stop")

    # `choose [a, b, c]` — RepeatedCapture for variable-length list
    register_form_keyword(
        "choose",
        Sequence([
            Literal("IDENT", "choose"),
            Literal("LBRACK", None),
            RepeatedCapture(
                "candidates",
                item_pattern=Capture("__item__"),
                separator=Literal("COMMA", None),
            ),
            Literal("RBRACK", None),
        ]),
        template=Build(
            "ChooseExpr",
            candidates=CaptureRef("candidates"),
        ),
        ast_module=ast_module,
        session=session,
    )
    registered.append("choose")

    # `do { stmt; stmt; ...; expr }` — RepeatedCapture with semicolon
    register_form_keyword(
        "do",
        Sequence([
            Literal("IDENT", "do"),
            Literal("LBRACE", None),
            RepeatedCapture(
                "statements",
                item_pattern=Capture("__item__"),
                separator=Literal("SEMI", None),
            ),
            Literal("RBRACE", None),
        ]),
        template=Build(
            "DoBlock",
            statements=CaptureRef("statements"),
        ),
        ast_module=ast_module,
        session=session,
    )
    registered.append("do")

    return registered


def list_bootstrap_self_host_keywords() -> List[str]:
    """Return the set of bootstrap keywords that `bootstrap_self_host`
    currently re-expresses. Useful for tests + agent introspection."""
    return ["if", "unless", "whenever", "let", "fail", "stop", "choose", "do"]
