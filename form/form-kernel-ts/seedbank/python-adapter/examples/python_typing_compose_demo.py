# python_typing_compose_demo.py — three surfaces composing.
#
# Closes the loop on PR #2057 (typeann), #2058 (imports + math), and
# #2060 (classes) by exercising all three in a single file that runs
# identically under CPython, TS evalPython, and form-kernel-rust.
#
# The composition matters because each surface was shipped on its own
# branch from the `floats` foundation; without a demo that joins them
# the three-way parity claim is only proven per-surface, not per-program.
# This file is the proof that the substrate-grammar surfaces compose.
#
# What's exercised here:
#   - `from typing import List, Optional, Dict, Tuple, Any, Callable` —
#     parser binds each typing name to the opaque-sentinel native; the
#     names are only referenced inside annotation slots, which are
#     parse-and-ignored, so the native never fires at runtime. All six
#     names import cleanly; only the single-argument forms (`List[T]`,
#     `Optional[T]`) are exercised in annotation bodies — multi-argument
#     subscripts (`Dict[k, v]`, `Tuple[a, b]`) are an honest gap of the
#     v1 subscript parser, named below.
#   - `class Bucket:` with typed `__init__(self, label: str, base: int, …)`
#     — class lowering + parameter annotations using built-in + typing
#     names side by side.
#   - typed instance methods `score(self) -> int` and
#     `shifted(self, delta: int) -> Optional[int]` — return annotations
#     that reference typing-imported names alongside built-ins.
#   - `class Tally:` with a typed method whose parameter is
#     `List[Bucket]` — composing user-class identity inside a typing
#     generic, exercising the recursive subscript-in-annotation path.
#   - typed variable annotations on locals and module-level bindings —
#     both bare (`header: str`) and annotated-assignment forms.
#
# The runtime path the kernel walks is identical to the un-annotated,
# un-imported version: annotations dropped, imports rewritten to noops,
# classes lowered to constructor + lifted methods. The compose demo is
# evidence that those three lowerings interleave without surprise.
#
# Gaps named for the next breath:
#   - Multi-argument generic subscripts: `Dict[str, int]`, `Tuple[int, str]`,
#     `Callable[[int], int]`. The v1 subscript parser accepts a single
#     index expression — extending to comma-separated index lists is one
#     follow-up. The import of `Dict`, `Tuple`, `Callable` still binds
#     cleanly; only their use inside subscripts is the open gap.
#
# Runs identically under:
#   python3 python_typing_compose_demo.py             — CPython
#   npm run kernel -- python-eval ...                 — TS evalPython
#   form-kernel-rust python_typing_compose_demo.fk    — native kernel binary

from typing import List, Optional, Dict, Tuple, Any, Callable


class Bucket:
    def __init__(self, label: str, base: int, weight: int):
        self.label = label
        self.base = base
        self.weight = weight

    # Typed instance method — return annotation parses cleanly and is
    # dropped before lowering; the kernel sees an int returned from
    # `base * weight`.
    def score(self) -> int:
        return self.base * self.weight

    # Optional[int] in the return slot — single-argument generic
    # exercises the typing-name + subscript-in-annotation path.
    def shifted(self, delta: int) -> Optional[int]:
        return self.base + delta


class Tally:
    def __init__(self, seed: int):
        self.seed = seed

    # Method whose parameter type composes typing.List with a user-class.
    # The annotation parses (List is a typing name, Bucket is a bare
    # ident, [Bucket] is a subscript) and is then discarded — the body
    # treats `buckets` as a plain list.
    def combine(self, buckets: List[Bucket]) -> int:
        total: int = self.seed
        for b in buckets:
            total = total + b.score()
        return total


# Typed module-level annotations — bare + annotated-assignment shapes.
header: str
multiplier: int = 1

# Typed local construction.
red: Bucket   = Bucket("red", 3, 4)             # score = 12
blue: Bucket  = Bucket("blue", 5, 6)            # score = 30
green: Bucket = Bucket("green", 7, 2)           # score = 14

# Method calls with typed returns — runtime sees plain ints.
red_score: int   = red.score()                  # 12
blue_score: int  = blue.score()                 # 30
green_score: int = green.score()                # 14

# Optional[int] return — exercised as plain int.
red_shift: Optional[int] = red.shifted(10)      # 13

# Compose all three buckets through Tally.combine — drives the
# List[Bucket] annotation path through a method call.
tally: Tally   = Tally(100)
combined: int  = tally.combine([red, blue, green])   # 100 + 12 + 30 + 14 = 156

# Final expression — sum of every scalar above, exercising attribute
# reads alongside method results so the class lowering carries through.
# 12 + 30 + 14 + 13 + 156 + 3 + 5 + 7 + 1 = 241
red_score + blue_score + green_score + red_shift + combined + red.base + blue.base + green.base + multiplier
