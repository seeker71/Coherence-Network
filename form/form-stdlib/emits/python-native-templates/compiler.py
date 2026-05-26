"""Compiler driver — readable expression of form-source-compile-file.

Top-level entry point. Reads a Python source file (or the package's own
source for --self-compile), runs the parser, applies BMF rules to every
statement, writes a .fkb binary + .fkl lens.

Run:
    python3 -m kernels.python_bmf.compiler --self-test
    python3 -m kernels.python_bmf.compiler --file path/to/some.py --out some.fkb
    python3 -m kernels.python_bmf.compiler --self-compile --out roundtrip.fkb
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from .objects import BmfModule, BmfStatementTree
from .parser import parse_python
from .rules import compile_statement
from .sdk import Lens, NodeID, intern, lens_path_for, write_fkb


@dataclass
class CompileResult:
    module_id: NodeID
    nodes: list
    lens: Lens
    statement_count: int


class Compiler:
    def compile_text(self, text, path="<source>"):
        module = parse_python(text, path)
        return self._compile_module(module, path)

    def compile_file(self, path):
        p = Path(path)
        return self.compile_text(p.read_text(), str(p))

    def _compile_module(self, module, path):
        statement_ids = []
        nodes = []
        lens = Lens()

        seen_ids = set()

        def _push_statement(stmt_id, tree):
            """Idempotent push of the leaf statement node + lens entry.

            Token kinds are preserved alongside values so the decompiler
            can re-quote strings, render integers raw, etc.
            """
            key = str(stmt_id)
            if key in seen_ids:
                return
            seen_ids.add(key)
            lens.entries[key] = {
                "symbol": tree.cpython_rule,
                "span": tree.span.__dict__,
            }
            nodes.append(
                {
                    "nodeid": stmt_id,
                    "kind": "statement",
                    "value": {
                        "cpython_rule": tree.cpython_rule,
                        "tokens": [(t.kind, t.value) for t in tree.tokens],
                    },
                    "children": [],
                }
            )

        def visit(tree):
            stmt_id = compile_statement(tree)
            _push_statement(stmt_id, tree)
            child_ids = [visit(c) for c in tree.children]
            if child_ids:
                composed = intern(
                    "statement-block",
                    {"head": str(stmt_id), "child_count": len(child_ids)},
                    children=[stmt_id, *child_ids],
                )
                if str(composed) not in seen_ids:
                    seen_ids.add(str(composed))
                    nodes.append(
                        {
                            "nodeid": composed,
                            "kind": "statement-block",
                            "value": {"cpython_rule": tree.cpython_rule},
                            "children": [stmt_id, *child_ids],
                        }
                    )
                    lens.entries[str(composed)] = {
                        "symbol": f"{tree.cpython_rule}-block",
                        "span": tree.span.__dict__,
                    }
                return composed
            return stmt_id

        for s in module.statements:
            statement_ids.append(visit(s))

        module_id = intern(
            "module",
            {"path": path, "statement_count": len(statement_ids)},
            children=statement_ids,
        )
        nodes.append(
            {
                "nodeid": module_id,
                "kind": "module",
                "value": {"path": path, "statement_count": len(statement_ids)},
                "children": statement_ids,
            }
        )
        lens.entries[str(module_id)] = {"symbol": Path(path).stem, "span": {}}
        return CompileResult(
            module_id=module_id,
            nodes=nodes,
            lens=lens,
            statement_count=len(statement_ids),
        )

    def write(self, result, out_path):
        write_fkb(out_path, result.nodes)
        result.lens.write(lens_path_for(out_path))


SELF_TEST_SOURCE = '''
import os
from typing import Any

CONST = 7

def add(a, b):
    return a + b

def main():
    x = 1
    y = 2
    z = add(x, y)
    return z
'''


def self_test():
    compiler = Compiler()
    result = compiler.compile_text(SELF_TEST_SOURCE, "<self-test>")
    assert result.statement_count >= 4, f"expected >=4 statements, got {result.statement_count}"
    assert result.module_id is not None
    assert any(n["kind"] == "module" for n in result.nodes)
    print(f"self-test ok - module {result.module_id}, {result.statement_count} top-level statements")
    return 0


def self_compile(out_path):
    """Compile the package's own source as a roundtrip smoke."""
    here = Path(__file__).parent
    compiler = Compiler()
    statement_total = 0
    all_nodes = []
    lens = Lens()
    module_ids = []
    for src in sorted(here.glob("*.py")):
        if src.name.startswith("_"):
            continue
        result = compiler.compile_file(src)
        statement_total += result.statement_count
        all_nodes.extend(result.nodes)
        lens.entries.update(result.lens.entries)
        module_ids.append(result.module_id)
    package_id = intern(
        "package",
        {"name": "kernels.python_bmf", "module_count": len(module_ids)},
        children=module_ids,
    )
    all_nodes.append(
        {
            "nodeid": package_id,
            "kind": "package",
            "value": {"name": "kernels.python_bmf", "module_count": len(module_ids)},
            "children": module_ids,
        }
    )
    write_fkb(out_path, all_nodes)
    lens.write(lens_path_for(out_path))
    print(f"self-compile ok - {len(module_ids)} modules, {statement_total} statements -> {out_path}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -m kernels.python_bmf.compiler",
        description="Native Python BMF compiler - readable expression of python-bmf.fk",
    )
    parser.add_argument("--file", help="compile a Python source file to .fkb")
    parser.add_argument("--out", help="output .fkb path")
    parser.add_argument("--self-test", action="store_true", help="smoke test the package")
    parser.add_argument("--self-compile", action="store_true", help="compile the package's own source")
    parser.add_argument("--roundtrip", help="compile + decompile, report gaps")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.self_test:
        return self_test()
    if args.self_compile:
        out = args.out or "kernels/python_bmf/.cache/roundtrip.fkb"
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        return self_compile(out)
    if args.roundtrip:
        from .decompiler import decompile_module
        compiler = Compiler()
        original = Path(args.roundtrip).read_text()
        result = compiler.compile_file(args.roundtrip)
        decompiled = decompile_module(result.nodes, module_id=str(result.module_id))
        out = args.out or args.roundtrip + ".roundtrip"
        Path(out).write_text(decompiled)
        print(f"roundtrip ok - {result.statement_count} statements -> {out}")
        print(f"  original lines:    {len(original.splitlines())}")
        print(f"  decompiled lines:  {len(decompiled.splitlines())}")
        return 0
    if args.file:
        if not args.out:
            print("--out required when using --file", file=sys.stderr)
            return 2
        compiler = Compiler()
        result = compiler.compile_file(args.file)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        compiler.write(result, args.out)
        print(f"ok - {result.statement_count} statements -> {args.out}")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
