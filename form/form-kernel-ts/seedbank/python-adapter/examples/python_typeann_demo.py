# python_typeann_demo.py — Python type annotations through the full
# Python → Form → native-kernel pipeline. Closes the "annotations crash
# the parser" gap that lived between PR #1793 (assignment) and the float
# work in PR #2056.
#
# Type annotations carry no runtime semantics in CPython — they live on
# __annotations__ for the typing module's introspection but never
# participate in arithmetic, comparison, or control flow. The adapter
# parses them and drops them on the floor, so the recipe tree the
# kernel sees is identical to the un-annotated equivalent. This file
# exercises every annotation surface the adapter knows:
#   - parameter annotations (atomic + subscripted-generic forms)
#   - return annotations (atomic + subscripted forms)
#   - variable annotations (bare + annotated-assignment)
#
# All annotations use the built-in generic aliases shipped in Python
# 3.9+ (`list[int]`, `dict[str, int]`) so the file runs unchanged under
# CPython without `from typing import …` — which the parser doesn't
# need to handle for annotations to round-trip.
#
# Runs identically under:
#   python3 python_typeann_demo.py             — CPython
#   npm run kernel -- python-eval ...          — TS evalPython
#   form-kernel-rust python_typeann_demo.fk    — native kernel binary


# Parameter + return annotations — atomic types.
def add(a: int, b: int) -> int:
    return a + b


# Float arithmetic with float-typed params + return.
def scale(value: float, factor: float) -> float:
    return value * factor


# Subscripted generic parameter (list[int]) + atomic return.
# The parser absorbs `list[int]` through parseExpr → parsePostfix's
# subscript rule. No special-case for typing — the annotation is just
# an expression that gets thrown away.
def sum_list(xs: list[int]) -> int:
    total: int = 0
    for x in xs:
        total = total + x
    return total


# Nested subscripted generic (list[list[int]]) — exercises recursive
# subscript parsing in the annotation slot.
def sum_grid(grid: list[list[int]]) -> int:
    out: int = 0
    for row in grid:
        for v in row:
            out = out + v
    return out


# Bare variable annotation — no runtime effect.
result_kind: str

# Annotated assignment — lowers to plain assignment.
base: int = 10
multiplier: float = 2.5

# Drive the annotated functions.
sum_a: int = add(3, 4)                                # 7
sum_b: float = scale(2.0, 0.5)                        # 1.0
sum_c: int = sum_list([1, 2, 3, 4])                   # 10
sum_d: int = sum_grid([[1, 2], [3, 4], [5, 6]])       # 21
weighted: float = base * multiplier                    # 25.0

# Final expression: 7 + 1.0 + 10 + 21 + 25.0 = 64.0
sum_a + sum_b + sum_c + sum_d + weighted
