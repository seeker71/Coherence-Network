"""form.action → Python function compiler.

A Form action recipe is a small program (let / if / call / arithmetic /
list construction). The Form kernel walks it directly; this module is
the readable Python expression of that walker.

Covers: LET, COND (if/then/else), CALL, MATH (+, -, *, /, %), COMPARE,
LOGIC (and, or, not), and value leaves. Other arms route through a
typed `unhandled` node so unhandled categories never collapse into strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .sdk import NodeID, intern, intern_trivial_int, intern_trivial_string


@dataclass
class Action:
    kind: str
    value: Any = None
    children: list = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


def lit_int(n):
    return Action("lit-int", n, [])


def lit_string(s):
    return Action("lit-string", s, [])


def lit_bool(b):
    return Action("lit-bool", b, [])


def lit_none():
    return Action("lit-none", None, [])


def ident(name):
    return Action("ident", name, [])


def let(name, value, body):
    return Action("let", name, [value, body])


def call(target, *args):
    return Action("call", target, list(args))


def if_then_else(cond, then_branch, else_branch):
    return Action("if", None, [cond, then_branch, else_branch])


def binop(op, left, right):
    return Action("binop", op, [left, right])


def unop(op, operand):
    return Action("unop", op, [operand])


def seq(*actions):
    return Action("seq", None, list(actions))


_BINOP_FNS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a // b if isinstance(a, int) and isinstance(b, int) else a / b,
    "%": lambda a, b: a % b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
}

_UNOP_FNS = {
    "not": lambda a: not a,
    "-": lambda a: -a,
}


def evaluate(action, env=None, host=None):
    env = {} if env is None else env
    host = {} if host is None else host
    k = action.kind
    if k == "lit-int":
        return action.value
    if k == "lit-string":
        return action.value
    if k == "lit-bool":
        return action.value
    if k == "lit-none":
        return None
    if k == "ident":
        if action.value in env:
            return env[action.value]
        if action.value in host:
            return host[action.value]
        raise KeyError(f"unbound ident: {action.value!r}")
    if k == "let":
        value = evaluate(action.children[0], env, host)
        new_env = dict(env)
        new_env[action.value] = value
        return evaluate(action.children[1], new_env, host)
    if k == "call":
        target = action.value
        fn = env.get(target) or host.get(target)
        if fn is None:
            raise KeyError(f"unknown call target: {target!r}")
        args = [evaluate(c, env, host) for c in action.children]
        return fn(*args)
    if k == "if":
        cond = evaluate(action.children[0], env, host)
        branch = action.children[1] if cond else action.children[2]
        return evaluate(branch, env, host)
    if k == "binop":
        fn = _BINOP_FNS[action.value]
        return fn(evaluate(action.children[0], env, host), evaluate(action.children[1], env, host))
    if k == "unop":
        fn = _UNOP_FNS[action.value]
        return fn(evaluate(action.children[0], env, host))
    if k == "seq":
        result = None
        for c in action.children:
            result = evaluate(c, env, host)
        return result
    raise NotImplementedError(f"action kind not handled: {k!r}")


def action_to_python(action, indent=0):
    """Render an Action as readable Python source."""
    pad = "    " * indent
    k = action.kind
    if k == "lit-int":
        return repr(action.value)
    if k == "lit-string":
        return repr(action.value)
    if k == "lit-bool":
        return "True" if action.value else "False"
    if k == "lit-none":
        return "None"
    if k == "ident":
        return action.value
    if k == "binop":
        l = action_to_python(action.children[0])
        r = action_to_python(action.children[1])
        return f"({l} {action.value} {r})"
    if k == "unop":
        if action.value == "not":
            return f"(not {action_to_python(action.children[0])})"
        return f"({action.value}{action_to_python(action.children[0])})"
    if k == "call":
        args = ", ".join(action_to_python(c) for c in action.children)
        return f"{action.value}({args})"
    if k == "let":
        value = action_to_python(action.children[0])
        body = action_to_python(action.children[1], indent)
        return f"{pad}{action.value} = {value}\n{body}"
    if k == "if":
        cond = action_to_python(action.children[0])
        then_b = action_to_python(action.children[1], indent + 1)
        else_b = action_to_python(action.children[2], indent + 1)
        return f"{pad}if {cond}:\n{then_b}\n{pad}else:\n{else_b}"
    if k == "seq":
        return "\n".join(action_to_python(c, indent) for c in action.children)
    return f"{pad}# unhandled action: {k}"


def compile_form_action(action, name="action"):
    body = action_to_python(action, indent=1)
    return f"def {name}(env=None, host=None):\n{body}\n"


def recipe_to_action(recipe_node):
    """Best-effort: read a node dict from read_fkb into an Action."""
    kind = recipe_node.get("kind", "")
    value = recipe_node.get("value")
    if kind == "int":
        return lit_int(int(value["literal"]) if isinstance(value, dict) else int(value or 0))
    if kind == "string":
        return lit_string(value["literal"] if isinstance(value, dict) else str(value or ""))
    if kind == "ident":
        return ident(value["name"] if isinstance(value, dict) else str(value or ""))
    return Action("unhandled", {"kind": kind, "value": value}, [])


__all__ = [
    "Action",
    "lit_int",
    "lit_string",
    "lit_bool",
    "lit_none",
    "ident",
    "let",
    "call",
    "if_then_else",
    "binop",
    "unop",
    "seq",
    "evaluate",
    "action_to_python",
    "compile_form_action",
    "recipe_to_action",
]
