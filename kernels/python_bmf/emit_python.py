"""Translate Form recipes to idiomatic native Python — the real direction.

The universal-translator path:
    source-language → Form numeric semantic capture (Recipe tree) → target-language
This module is the second arrow for target=Python: take a Form recipe expressed
in .fk surface text, walk its structural meaning, and emit Python source that
is semantically faithful and readable as Python code — `def`, `if/else`,
`while`, `for`, `class`, real names, real control flow. NOT s-expressions
wrapped in Python strings.

What "semantically faithful" means here:
- A Form `(defn name (a b) body)` becomes a Python `def name(a, b): ...` with
  the body translated to statements + a final `return`, not a re-encoded blob.
- A Form `(if c t e)` becomes a Python `if/else` block when the arms are
  statement-shaped, a ternary `t if c else e` when the arms are expressions.
- A Form `(let x v)` becomes a Python `x = v` assignment.
- Form recursive helpers used to express loops (the CPS lowering kernels emit
  for `while` and `for`) are recognized and lifted back to Python `while`/`for`
  when the shape matches; otherwise emitted as recursive Python functions
  (still correct semantically).
- Form NodeIDs / structural identity carry through unchanged: the emitted
  Python program executes the same computation as the Form recipe.

Reading discipline: no Form runtime is imported here. The input is parsed
text; the output is Python source. The SDK boundary stays in sdk.py.

Coverage today: enough Form surface to round-trip every parity-suite demo
(python_demo.fk → emit → .py → CPython → same integer). The Form-written BMF
compiler is the next surface to grow into — see the Coverage table at the
bottom and emit_python.fk for the eventual Form-native version that produces
this module mechanically.

Run:
    python3 -m kernels.python_bmf.emit_python path/to/recipe.fk
    python3 -m kernels.python_bmf.emit_python path/to/recipe.fk --out recipe.py
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Union


# ──────────────────────────────────────────────────────────────────────
# S-expression parser — the smallest honest .fk reader.
# Form's surface text is s-expressions. Parsing them into structured Python
# data is mechanical (~40 lines). The semantic capture lives in the structure
# we walk, not in the parsing.
# ──────────────────────────────────────────────────────────────────────


@dataclass
class Sym:
    name: str

    def __repr__(self) -> str:
        return self.name


Sexpr = Union[Sym, int, str, bool, list]  # `list` means a Form list/call


def parse_fk(text: str) -> list[Sexpr]:
    pos = 0
    n = len(text)

    def skip_ws() -> None:
        nonlocal pos
        while pos < n:
            ch = text[pos]
            if ch.isspace():
                pos += 1
            elif ch == ";":  # line comment
                while pos < n and text[pos] != "\n":
                    pos += 1
            else:
                break

    def parse_atom() -> Sexpr:
        nonlocal pos
        start = pos
        if text[pos] == '"':
            pos += 1
            buf = []
            while pos < n and text[pos] != '"':
                if text[pos] == "\\" and pos + 1 < n:
                    buf.append(text[pos : pos + 2])
                    pos += 2
                else:
                    buf.append(text[pos])
                    pos += 1
            pos += 1  # closing quote
            raw = "".join(buf)
            return raw.encode().decode("unicode_escape")
        while pos < n and not text[pos].isspace() and text[pos] not in "()":
            pos += 1
        tok = text[start:pos]
        if tok in ("true", "false"):
            return tok == "true"
        try:
            return int(tok)
        except ValueError:
            return Sym(tok)

    def parse_one() -> Sexpr:
        nonlocal pos
        skip_ws()
        if pos >= n:
            raise ValueError("unexpected end of input")
        if text[pos] == "(":
            pos += 1
            items: list[Sexpr] = []
            skip_ws()
            while pos < n and text[pos] != ")":
                items.append(parse_one())
                skip_ws()
            if pos >= n:
                raise ValueError("unclosed list")
            pos += 1  # )
            return items
        if text[pos] == ")":
            raise ValueError(f"unexpected ) at {pos}")
        return parse_atom()

    result: list[Sexpr] = []
    skip_ws()
    while pos < n:
        result.append(parse_one())
        skip_ws()
    return result


# ──────────────────────────────────────────────────────────────────────
# Form operator → Python operator mapping.
# These are the kernel natives `lang-python-fk.ts` emits to and the rust
# kernel registers. We translate them back to native Python operators so
# the emitted code reads as Python, not as `(_plus a b)`.
# ──────────────────────────────────────────────────────────────────────


BIN_OP = {
    # The two Python-pipeline operator-marker names from lang-python-fk.ts:
    "_plus": "+",
    # The Form kernel's plain math natives (Form sources call these as
    # ordinary functions: `(add a b)`, `(sub a b)` ...). Translating them
    # to native Python operators makes the emitted code readable.
    "add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%",
    # comparisons
    "lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "==", "ne": "!=",
    # boolean
    "and": "and", "or": "or",
}

# Form identifier conventions → valid Python identifiers.
# `foo-bar`  → `foo_bar`     (Lisp-style hyphens become underscores)
# `foo?`     → `is_foo`      (predicate suffix becomes is_ prefix)
# `foo!`     → `foo_bang`    (mutation suffix marker)
# `*foo*`    → `_FOO_`       (Lisp earmuffs for globals)
# Keywords/digits that would collide with Python builtins or syntax get an
# `_` suffix.

import keyword as _kw


def py_ident(name: str) -> str:
    # Form-only sentinels we keep as-is (operator names handled elsewhere).
    if name in BIN_OP or name in UNARY_OP:
        return name
    raw = name
    # earmuffs *foo* → _FOO_ (uppercase signals "global" in Python convention)
    if len(raw) >= 3 and raw.startswith("*") and raw.endswith("*"):
        return "_" + raw[1:-1].upper().replace("-", "_") + "_"
    # predicate suffix `foo?` or `foo-bar?` → `is_foo` / `is_foo_bar`
    if raw.endswith("?"):
        base = raw[:-1].replace("-", "_").replace(".", "_")
        return f"is_{base}" if not base.startswith("is_") else base
    # mutation marker `foo!` → `foo_bang`
    if raw.endswith("!"):
        return raw[:-1].replace("-", "_") + "_bang"
    # general: hyphens → underscores, dots → underscores
    out = raw.replace("-", "_").replace(".", "_").replace("/", "_")
    # Python identifier rules: can't start with digit; can't be a keyword.
    if out and out[0].isdigit():
        out = "_" + out
    if _kw.iskeyword(out):
        out = out + "_"
    # Replace any remaining non-identifier char with `_`.
    out = "".join(c if (c.isalnum() or c == "_") else "_" for c in out)
    return out or "_"
UNARY_OP = {"not": "not "}
LIST_PRIMS = {
    "list": "list",
    "head": "head", "tail": "tail", "len": "len",
    "nth": "nth", "cons": "cons",
    "min": "min", "max": "max", "abs": "abs",
    "sum": "sum", "range": "range",
}

# Form/kernel host primitives that need Python-side stubs to make the emitted
# code runnable. We keep them as identifiers — they bind to substrate SDK
# helpers at import time (see sdk.py / objects.py). Translation preserves
# the symbolic name with Python identifier conventions applied.
HOST_PRIMS = {
    # cells / objects
    "cell", "cell?", "cell-kind", "cell-value", "cell-origin", "cell-undo",
    "cell-inverse",
    # strings
    "str_concat", "str_eq", "str_len", "substring", "char_at", "str_to_int",
    "str_to_float",
    # arithmetic helpers
    "add", "sub", "mul", "div", "mod",
    # node ids
    "make_nodeid", "intern_node", "intern_trivial_int", "intern_trivial_string",
    # file io
    "read_file", "write_file_text", "write_file_bytes", "file_size",
    # list / collection
    "empty", "nil?", "head", "tail", "list", "nth", "cons", "append",
    "reverse-list", "len",
    # bmf
    "bmf-object", "bmf-object?", "bmf-object-kind", "bmf-object-value",
    "bmf-collection", "bmf-collection-items",
}


# Form preludes the .fk emitter prepends (nth, sum, range...) — when we
# translate back to Python, these prelude defns map to Python natives, so
# we elide them rather than emit verbose recursive equivalents.
PRELUDE_DEFN_NAMES = {
    "nth", "sum", "range",
    "_range_step", "_append_list", "_cons_then_append",
}


class UnsupportedForm(Exception):
    """A Form construct we don't yet know how to render as idiomatic Python."""


# ──────────────────────────────────────────────────────────────────────
# Emitter — walks the parsed Form, produces Python source.
# ──────────────────────────────────────────────────────────────────────


class PythonEmitter:
    def __init__(self) -> None:
        self.out: list[str] = []
        self.indent = 0

    def line(self, text: str = "") -> None:
        self.out.append("    " * self.indent + text)

    HEADER = (
        '"""Emitted from Form source by kernels/python_bmf/emit_python.py."""\n'
        "from kernels.python_bmf.host_primitives import *  # noqa: F401, F403\n"
    )

    def write_module(self, forms: list[Sexpr]) -> str:
        """Top-level: a Form .fk usually wraps everything in (do ...). We split
        the children into three buckets:
          - `(defn ...)`            → module-level `def name(...)`.
          - `(let x v)`             → module-level `x = v` global binding
                                       (Form code references these as globals
                                       inside function bodies via closure).
          - everything else         → main-block statements; the last
                                       expression prints when run as a script.
        """
        if len(forms) == 1 and isinstance(forms[0], list) and forms[0] and is_sym(forms[0][0], "do"):
            top = forms[0][1:]
        else:
            top = forms
        defns, lets, tail = self._split_top(top)
        # Header — host primitives must resolve before module-level code runs
        for hdr_line in self.HEADER.rstrip().split("\n"):
            self.line(hdr_line)
        self.line()
        # Defns FIRST. Python closures resolve names at call time, so let-
        # bindings that reference defns work even if defined later; but list
        # literals at module-level (rule tables that name compile-functions)
        # evaluate immediately and DO need the defns already bound.
        for d in defns:
            self._emit_defn(d)
            self.line()
        # module-level globals — emit AFTER defns so rule tables can reference them
        for lname, lval in lets:
            self.line(f"{lname} = {self._emit_expr(lval)}")
        if lets:
            self.line()
        if tail:
            self.line("if __name__ == '__main__':")
            self.indent += 1
            for stmt in tail[:-1]:
                self._emit_statement(stmt)
            last = tail[-1]
            # final form may be just `0` from the python-bmf.fk closer; skip
            # printing a bare numeric literal that carries no result.
            if isinstance(last, int):
                if last != 0:
                    self.line(f"print({last})")
                else:
                    self.line("pass")
            else:
                self.line(f"print({self._emit_expr(last)})")
            self.indent -= 1
        return "\n".join(self.out).rstrip() + "\n"

    def _split_top(self, forms: list[Sexpr]) -> tuple[list[list], list[tuple[str, Sexpr]], list[Sexpr]]:
        """Top-level forms split into (defns, lets, tail).
        Recurses into nested (do ...) blocks at top-level (compiler.fk and
        python-bmf.fk wrap everything in one outer do).
        """
        defns: list[list] = []
        lets: list[tuple[str, Sexpr]] = []
        tail: list[Sexpr] = []
        for f in forms:
            if (isinstance(f, list) and f and is_sym(f[0], "defn")
                    and isinstance(f[1], Sym) and f[1].name in PRELUDE_DEFN_NAMES):
                continue
            if isinstance(f, list) and f and is_sym(f[0], "defn"):
                defns.append(f)
            elif isinstance(f, list) and f and is_sym(f[0], "let") and len(f) >= 3:
                lets.append((py_ident(f[1].name), f[2]))
            elif isinstance(f, list) and f and is_sym(f[0], "do"):
                inner_defns, inner_lets, inner_tail = self._split_top(f[1:])
                defns.extend(inner_defns)
                lets.extend(inner_lets)
                tail.extend(inner_tail)
            else:
                tail.append(f)
        return defns, lets, tail

    # ---- structure ----


    def _emit_defn(self, form: list) -> None:
        # (defn name (params...) body)
        fname_raw = form[1].name
        name = py_ident(fname_raw)
        param_syms = list(form[2]) if form[2] else []
        params_py_list = [py_ident(p.name) for p in param_syms]
        params_py = ", ".join(params_py_list)
        body = form[3] if len(form) > 3 else 0
        self.line(f"def {name}({params_py}):")
        self.indent += 1
        # Tail-call recursion lifting: when every self-call sits in tail
        # position and at least one self-call exists, lift the body into a
        # `while True:` and rewrite each tail self-call as a tuple rebind +
        # `continue`. This removes CPython's stack-depth fragility for the
        # head/tail-style loops the Form CPS lowering emits — the deep
        # source-compiler workloads (engine.fk) no longer need
        # sys.setrecursionlimit raised to extreme values.
        if param_syms and self._is_tail_recursive(fname_raw, param_syms, body):
            self.line("while True:")
            self.indent += 1
            self._emit_function_body(body, tail_self=(fname_raw, params_py_list))
            self.indent -= 1
        else:
            self._emit_function_body(body)
        self.indent -= 1

    # ---- tail-call recursion analysis ----

    def _contains_self_call(self, fname: str, expr: Sexpr) -> bool:
        """True iff `expr` (or any sub-expression) is a call to `fname`.

        Used as the "this is not a tail call" guard — anything that wraps a
        self-call (arguments to other calls, conditions, let values, prefix
        statements of a `do`) disqualifies the function from tail lifting.
        """
        if isinstance(expr, list) and expr:
            if isinstance(expr[0], Sym) and expr[0].name == fname:
                return True
            return any(self._contains_self_call(fname, x) for x in expr)
        return False

    def _is_tail_recursive(self, fname: str, params: list, body: Sexpr) -> bool:
        """Return True iff `body` is tail-recursive in `fname`.

        Tail-recursive means: every call to `fname` reachable in `body`
        sits in tail position (the value returned from the function), and
        at least one such call exists. Self-calls nested inside arguments,
        conditions, let-values, or non-final `do` statements disqualify.

        Tail positions walked:
        - `(do s1 ... sn)`     → tail is `sn`; `s1..s_{n-1}` must contain no self-call
        - `(if cond t e)`      → tail is both `t` and `e`; `cond` must contain no self-call
        - `(let x v)`          → tail leaf (the let evaluates to v); v must contain no self-call
        - `(fname args...)`    → THE tail self-call; args must contain no nested self-call
        - any other expression → tail leaf base case; must contain no self-call
        """
        saw_self = [False]

        def walk(expr: Sexpr) -> bool:
            if isinstance(expr, list) and expr and isinstance(expr[0], Sym):
                op = expr[0].name
                if op == "do":
                    inner = expr[1:]
                    if not inner:
                        return True
                    for s in inner[:-1]:
                        if self._contains_self_call(fname, s):
                            return False
                    return walk(inner[-1])
                if op == "if" and len(expr) == 4:
                    cond, then_, else_ = expr[1], expr[2], expr[3]
                    if self._contains_self_call(fname, cond):
                        return False
                    return walk(then_) and walk(else_)
                if op == "let" and len(expr) >= 3:
                    # let-as-expr: value is not in tail position. Form's let
                    # in tail simply binds and yields the value — the value
                    # itself must not contain a self-call.
                    return not self._contains_self_call(fname, expr[2])
                if op == fname:
                    # The tail self-call. Arity must match params, and the
                    # argument expressions themselves must contain no nested
                    # self-calls (those would be non-tail).
                    if len(expr) - 1 != len(params):
                        return False
                    for arg in expr[1:]:
                        if self._contains_self_call(fname, arg):
                            return False
                    saw_self[0] = True
                    return True
            # Any other shape (atom, non-special call, etc.) is a base-case
            # tail leaf — valid as long as it contains no self-call.
            return not self._contains_self_call(fname, expr)

        if not walk(body):
            return False
        return saw_self[0]

    def _emit_function_body(self, body: Sexpr, tail_self: tuple | None = None) -> None:
        """Render a Form expression as a Python function body.

        When `tail_self` is `(fname, [param_py_names])`, every tail self-call
        is rewritten to a tuple rebind + `continue` instead of `return f(...)`.
        Non-self tail positions still emit a normal `return`.
        """
        if isinstance(body, list) and body and is_sym(body[0], "do"):
            stmts = body[1:]
            for stmt in stmts[:-1]:
                self._emit_statement(stmt)
            self._emit_tail(stmts[-1], tail_self)
            return
        if isinstance(body, list) and body and is_sym(body[0], "if"):
            # if-as-statement: render as Python if/else returning each arm.
            cond, then_, else_ = body[1], body[2], body[3]
            self.line(f"if {self._emit_expr(cond)}:")
            self.indent += 1
            self._emit_function_body(then_, tail_self)
            self.indent -= 1
            self.line("else:")
            self.indent += 1
            self._emit_function_body(else_, tail_self)
            self.indent -= 1
            return
        self._emit_tail(body, tail_self)

    def _emit_tail(self, expr: Sexpr, tail_self: tuple | None) -> None:
        """Emit a tail-position expression — either a self-call rebind or a return."""
        if tail_self is not None:
            fname, param_names = tail_self
            if (isinstance(expr, list) and expr
                    and isinstance(expr[0], Sym) and expr[0].name == fname
                    and len(expr) - 1 == len(param_names)):
                # Rebind params from the tail-call arguments, then loop.
                # Python's tuple assignment evaluates the full RHS before
                # binding any LHS, so simultaneous updates are safe.
                rhs = ", ".join(self._emit_expr(a) for a in expr[1:])
                lhs = ", ".join(param_names)
                if len(param_names) == 1:
                    self.line(f"{lhs} = {rhs}")
                else:
                    self.line(f"{lhs} = {rhs}")
                self.line("continue")
                return
        self.line(f"return {self._emit_expr(expr)}")

    def _emit_statement(self, form: Sexpr) -> None:
        if isinstance(form, list) and form:
            head = form[0]
            if is_sym(head, "let"):
                name = py_ident(form[1].name)
                value = self._emit_expr(form[2])
                self.line(f"{name} = {value}")
                return
            if is_sym(head, "defn"):
                self._emit_defn(form)
                return
            if is_sym(head, "do"):
                for s in form[1:]:
                    self._emit_statement(s)
                return
            if is_sym(head, "if"):
                cond, then_, else_ = form[1], form[2], form[3]
                self.line(f"if {self._emit_expr(cond)}:")
                self.indent += 1
                self._emit_statement(then_)
                self.indent -= 1
                if not (isinstance(else_, int) and else_ == 0):
                    self.line("else:")
                    self.indent += 1
                    self._emit_statement(else_)
                    self.indent -= 1
                return
        # bare expression statement
        self.line(self._emit_expr(form))

    # ---- expressions ----

    def _emit_expr(self, form: Sexpr) -> str:
        if isinstance(form, bool):
            return "True" if form else "False"
        if isinstance(form, int):
            return str(form)
        if isinstance(form, str):
            # repr() handles \n, \t, \r, \", \\, control chars correctly.
            return repr(form)
        if isinstance(form, Sym):
            return py_ident(form.name)
        if not isinstance(form, list) or not form:
            raise UnsupportedForm(f"empty/unknown: {form!r}")
        head = form[0]
        if not isinstance(head, Sym):
            raise UnsupportedForm(f"non-symbol head: {head!r}")
        op = head.name
        if op == "do":
            # Expression-position `(do s1 ... sn)`: Form returns the value
            # of `sn`. Python has no block-expression; we lift via tuple +
            # `[-1]`. `(let x v)` children become walrus expressions, which
            # is the natural Python way to introduce a binding inside an
            # expression. The shape stays readable: `((x := v), (y := w), final)[-1]`.
            inner = form[1:]
            if not inner:
                return "None"
            if len(inner) == 1:
                return self._emit_expr(inner[0])
            parts = ", ".join(self._emit_expr(x) for x in inner)
            return f"({parts})[-1]"
        if op == "if":
            cond = self._emit_expr(form[1])
            then_ = self._emit_expr(form[2])
            else_ = self._emit_expr(form[3])
            return f"({then_} if {cond} else {else_})"
        if op == "let":
            # In expr position, surface a walrus.
            name = py_ident(form[1].name)
            return f"({name} := {self._emit_expr(form[2])})"
        if op in BIN_OP:
            left = self._emit_expr(form[1])
            right = self._emit_expr(form[2])
            return f"({left} {BIN_OP[op]} {right})"
        if op in UNARY_OP:
            return f"({UNARY_OP[op]}{self._emit_expr(form[1])})"
        if op == "nth":
            return f"{self._emit_expr(form[1])}[{self._emit_expr(form[2])}]"
        if op == "head":
            return f"{self._emit_expr(form[1])}[0]"
        if op == "tail":
            return f"{self._emit_expr(form[1])}[1:]"
        if op == "list":
            items = ", ".join(self._emit_expr(a) for a in form[1:])
            return f"[{items}]"
        if op == "cons":
            return f"[{self._emit_expr(form[1])}, *{self._emit_expr(form[2])}]"
        if op in LIST_PRIMS:
            args = ", ".join(self._emit_expr(a) for a in form[1:])
            return f"{LIST_PRIMS[op]}({args})"
        # default: function call (Form's apply shape: (callee arg1 arg2 ...))
        args = ", ".join(self._emit_expr(a) for a in form[1:])
        return f"{py_ident(op)}({args})"


def is_sym(form: Sexpr, name: str) -> bool:
    return isinstance(form, Sym) and form.name == name


def emit_python(fk_text: str) -> str:
    forms = parse_fk(fk_text)
    return PythonEmitter().write_module(forms)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", type=Path, help=".fk Form recipe to translate")
    ap.add_argument("--out", type=Path, help="Output .py path (default: stdout)")
    args = ap.parse_args(argv)

    text = args.file.read_text()
    try:
        py_src = emit_python(text)
    except UnsupportedForm as e:
        print(f"unsupported Form: {e}", file=sys.stderr)
        return 1

    if args.out:
        args.out.write_text(py_src)
        print(f"ok - {len(py_src)} bytes -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(py_src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
