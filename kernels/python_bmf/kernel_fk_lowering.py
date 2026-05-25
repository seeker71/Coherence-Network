"""Sanity-check lowering: Python source → .fk s-expression text.

SCOPE: this is *not* the universal translator. It is a regression utility that
produces the .fk surface form-kernel-rust executes, so we can run the same
program under both CPython and the kernel and confirm they agree numerically.

The real universal-translator emit direction is `.fk → idiomatic native target
code` (see emit_python.py for the Form→Python translator). This module exists
because the cross-runtime comparison needs *some* path from .py to .fk; until
the Form-native emitter materializes one, we use Python's ast as the most
natural Python way to read Python.

Do not extend this module to cover more Python constructs as a substitute for
the real translator. New work belongs in emit_python.py (Form→Python) or in
the Form-native emit_python.fk recipe that produces it.

Run:
    python3 -m kernels.python_bmf.kernel_fk_lowering path/to/some.py
    python3 -m kernels.python_bmf.kernel_fk_lowering path/to/some.py --out some.fk
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


# Python operator → Form kernel native dispatch name. Matches the canonical
# mapping in form/form-kernel-ts/src/lang-python-fk.ts.
BINOP = {
    ast.Add: "_plus",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.Div: "div",
    ast.FloorDiv: "div",
    ast.Mod: "mod",
}
CMPOP = {
    ast.Eq: "eq",
    ast.NotEq: "ne",
    ast.Lt: "lt",
    ast.LtE: "le",
    ast.Gt: "gt",
    ast.GtE: "ge",
}
BOOLOP = {ast.And: "and", ast.Or: "or"}


class UnsupportedConstruct(Exception):
    """A Python construct outside what the kernel can execute today."""


# Form kernels lost `nth` as a native on 2026-05-22; canonical implementation
# is in the rust kernel's source comment. We prepend it as a Form-level defn
# when subscript is used. Same for `range`/`sum` which the kernel doesn't
# carry. Adding more preludes is one-line edits.
PRELUDE = {
    # Form kernels lost `nth` as a native on 2026-05-22; the rust kernel's
    # source comment carries the canonical implementation. Same for `range`
    # and `sum`/`min`/`max` — staleness in the canonical .fk corpus that we
    # close by prepending the defns when needed.
    "nth": "(defn nth (xs n) (if (eq n 0) (head xs) (nth (tail xs) (sub n 1))))",
    "sum": "(defn sum (xs) (if (eq (len xs) 0) 0 (_plus (head xs) (sum (tail xs)))))",
    "range": (
        "(defn _range_step (i n) (if (eq i n) (list) (cons i (_range_step (_plus i 1) n)))) "
        "(defn range (n) (_range_step 0 n))"
    ),
}


def _assigned_names(body: list[ast.stmt]) -> list[str]:
    """Free variables on the LHS inside a loop body — these become the carry."""
    names: list[str] = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id not in names:
                    names.append(t.id)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id not in names:
                names.append(node.target.id)
    return names


class Emitter:
    def __init__(self) -> None:
        self._loop_counter = 0
        self.needs: set[str] = set()

    def gensym(self, prefix: str) -> str:
        name = f"{prefix}_{self._loop_counter}"
        self._loop_counter += 1
        return name

    # ---------------- module / statement ----------------

    def emit_module(self, tree: ast.Module) -> str:
        parts = [self.emit_stmt(s) for s in tree.body]
        prelude = [PRELUDE[name] for name in ("nth", "sum", "range") if name in self.needs]
        return "(do " + " ".join(prelude + parts) + ")"

    def emit_stmt(self, node: ast.stmt) -> str:
        if isinstance(node, ast.FunctionDef):
            params = " ".join(a.arg for a in node.args.args)
            body = self.emit_body(node.body)
            return f"(defn {node.name} ({params}) {body})"
        if isinstance(node, ast.Return):
            return self.emit_expr(node.value) if node.value is not None else "0"
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise UnsupportedConstruct(f"assign target: {ast.dump(node.targets[0])}")
            return f"(let {node.targets[0].id} {self.emit_expr(node.value)})"
        if isinstance(node, ast.AugAssign):
            if not isinstance(node.target, ast.Name):
                raise UnsupportedConstruct("aug-assign target must be Name")
            op = BINOP.get(type(node.op))
            if op is None:
                raise UnsupportedConstruct(f"aug-assign op: {type(node.op).__name__}")
            return f"(let {node.target.id} ({op} {node.target.id} {self.emit_expr(node.value)}))"
        if isinstance(node, ast.If):
            cond = self.emit_expr(node.test)
            then = self.emit_body(node.body)
            else_ = self.emit_body(node.orelse) if node.orelse else "0"
            return f"(if {cond} {then} {else_})"
        if isinstance(node, ast.While):
            return self.emit_while(node)
        if isinstance(node, ast.For):
            return self.emit_for(node)
        if isinstance(node, ast.Expr):
            return self.emit_expr(node.value)
        raise UnsupportedConstruct(f"stmt: {type(node).__name__}")

    def emit_body(self, stmts: list[ast.stmt]) -> str:
        """A function/branch body — early returns collapse to the returned expr."""
        if len(stmts) == 1:
            return self.emit_stmt(stmts[0])
        rendered: list[str] = []
        for i, s in enumerate(stmts):
            if isinstance(s, ast.Return):
                rendered.append(self.emit_expr(s.value) if s.value is not None else "0")
                break
            if isinstance(s, ast.If) and has_return(s.body):
                rendered.append(self.emit_if_with_return(s, stmts[i + 1 :]))
                break
            rendered.append(self.emit_stmt(s))
        if len(rendered) == 1:
            return rendered[0]
        return "(do " + " ".join(rendered) + ")"

    def emit_if_with_return(self, node: ast.If, tail: list[ast.stmt]) -> str:
        cond = self.emit_expr(node.test)
        then = self.emit_body(node.body)
        if node.orelse:
            else_ = self.emit_body(node.orelse)
        elif tail:
            else_ = self.emit_body(tail)
        else:
            else_ = "0"
        return f"(if {cond} {then} {else_})"

    # ---------------- while / for — CPS lowering ----------------

    def emit_while(self, node: ast.While) -> str:
        if node.orelse:
            raise UnsupportedConstruct("while-else")
        carry = _assigned_names(node.body)
        if not carry:
            raise UnsupportedConstruct("infinite while loop has no carry")
        loop = self.gensym("_while")
        params = " ".join(carry)
        body_stmts = [self.emit_stmt(s) for s in node.body]
        body = "(do " + " ".join(body_stmts) + ")"
        rebind_call = f"({loop} {params})"
        recur_block = f"(do {body} {rebind_call})"
        carry_return = "(list " + " ".join(carry) + ")"
        loop_body = f"(if {self.emit_expr(node.test)} {recur_block} {carry_return})"
        result_var = f"_while_{self._loop_counter}_result"
        self._loop_counter += 1
        unpack = [
            f"(let {name} (nth {result_var} {i}))" for i, name in enumerate(carry)
        ]
        self.needs.add("nth")
        return (
            f"(do (defn {loop} ({params}) {loop_body}) "
            f"(let {result_var} ({loop} {params})) "
            + " ".join(unpack)
            + ")"
        )

    def emit_for(self, node: ast.For) -> str:
        if node.orelse:
            raise UnsupportedConstruct("for-else")
        if not isinstance(node.target, ast.Name):
            raise UnsupportedConstruct("for target must be a single Name")
        iter_expr = self.emit_expr(node.iter)
        carry = _assigned_names(node.body)
        loop = self.gensym("_for")
        params = "_remaining " + " ".join(carry) if carry else "_remaining"
        rebind_step = [f"(let {node.target.id} (head _remaining))"]
        rebind_step.extend(self.emit_stmt(s) for s in node.body)
        rebind_block = "(do " + " ".join(rebind_step) + ")"
        recur_args = "(tail _remaining)" + (" " + " ".join(carry) if carry else "")
        recur_call = f"({loop} {recur_args})"
        carry_return = "(list " + " ".join(carry) + ")" if len(carry) != 1 else carry[0]
        body = (
            f"(if (eq (len _remaining) 0) {carry_return} "
            f"(do {rebind_block} {recur_call}))"
        )
        result_var = f"_for_{self._loop_counter}_result"
        self._loop_counter += 1
        unpack: list[str]
        if not carry:
            return f"(do (defn {loop} ({params}) {body}) ({loop} {iter_expr}))"
        if len(carry) == 1:
            return (
                f"(do (defn {loop} ({params}) {body}) "
                f"(let {carry[0]} ({loop} {iter_expr} {carry[0]})))"
            )
        self.needs.add("nth")
        unpack = [f"(let {name} (nth {result_var} {i}))" for i, name in enumerate(carry)]
        return (
            f"(do (defn {loop} ({params}) {body}) "
            f"(let {result_var} ({loop} {iter_expr} {' '.join(carry)})) "
            + " ".join(unpack)
            + ")"
        )

    # ---------------- expressions ----------------

    def emit_expr(self, node: ast.expr) -> str:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return "true" if node.value else "false"
            if isinstance(node.value, int):
                return str(node.value)
            if isinstance(node.value, str):
                escaped = node.value.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{escaped}"'
            if node.value is None:
                return "0"
            raise UnsupportedConstruct(f"constant: {type(node.value).__name__}")
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.BinOp):
            op = BINOP.get(type(node.op))
            if op is None:
                raise UnsupportedConstruct(f"binop: {type(node.op).__name__}")
            return f"({op} {self.emit_expr(node.left)} {self.emit_expr(node.right)})"
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return f"(sub 0 {self.emit_expr(node.operand)})"
            if isinstance(node.op, ast.Not):
                return f"(not {self.emit_expr(node.operand)})"
            if isinstance(node.op, ast.UAdd):
                return self.emit_expr(node.operand)
            raise UnsupportedConstruct(f"unaryop: {type(node.op).__name__}")
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise UnsupportedConstruct("chained comparison")
            op = CMPOP.get(type(node.ops[0]))
            if op is None:
                raise UnsupportedConstruct(f"cmpop: {type(node.ops[0]).__name__}")
            return f"({op} {self.emit_expr(node.left)} {self.emit_expr(node.comparators[0])})"
        if isinstance(node, ast.BoolOp):
            op = BOOLOP.get(type(node.op))
            if op is None:
                raise UnsupportedConstruct(f"boolop: {type(node.op).__name__}")
            parts = [self.emit_expr(v) for v in node.values]
            result = parts[0]
            for p in parts[1:]:
                result = f"({op} {result} {p})"
            return result
        if isinstance(node, ast.IfExp):
            return (
                f"(if {self.emit_expr(node.test)} "
                f"{self.emit_expr(node.body)} {self.emit_expr(node.orelse)})"
            )
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise UnsupportedConstruct("only direct named calls supported today")
            if node.func.id in PRELUDE:
                self.needs.add(node.func.id)
            args = " ".join(self.emit_expr(a) for a in node.args)
            return f"({node.func.id}{(' ' + args) if args else ''})"
        if isinstance(node, ast.List):
            items = " ".join(self.emit_expr(e) for e in node.elts)
            return f"(list{(' ' + items) if items else ''})"
        if isinstance(node, ast.Subscript):
            self.needs.add("nth")
            return f"(nth {self.emit_expr(node.value)} {self.emit_expr(node.slice)})"
        raise UnsupportedConstruct(f"expr: {type(node).__name__}")


def has_return(stmts: list[ast.stmt]) -> bool:
    for s in stmts:
        if isinstance(s, ast.Return):
            return True
        if isinstance(s, ast.If):
            if has_return(s.body) or has_return(s.orelse):
                return True
    return False


def emit_fk(source: str) -> str:
    tree = ast.parse(source)
    return Emitter().emit_module(tree)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", type=Path, help="Python source file")
    ap.add_argument("--out", type=Path, help="Output .fk path (default: stdout)")
    args = ap.parse_args(argv)

    text = args.file.read_text()
    try:
        fk = emit_fk(text)
    except UnsupportedConstruct as e:
        print(f"unsupported: {e}", file=sys.stderr)
        return 1

    if args.out:
        args.out.write_text(fk + "\n")
        print(f"ok - {len(fk)} bytes -> {args.out}", file=sys.stderr)
    else:
        print(fk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
