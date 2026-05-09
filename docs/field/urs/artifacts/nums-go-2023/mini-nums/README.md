# mini-nums — phase 1c validation

A minimal NUMS-shaped substrate in Python (~500 LoC), written from scratch after walking the NUMS.Go source. The point is empirical: **build it; if my understanding is wrong, the tests will fail at exactly the wrong assumption.**

Files:

| File | What it carries |
|---|---|
| `core.py` | the kernel — NodeID, TreeDB, Module, Blueprint, Recipe, NamedCell, `make_global_cell` |
| `calc.py` | calculator frontend (`let x = 2 + 3 * 4`) |
| `jsonschema.py` | JSON-Schema frontend (`{"type": "object", "properties": {...}}`) |
| `test_mini.py` | seven validation tests |

## Run

```bash
cd docs/field/urs/artifacts/nums-go-2023/mini-nums
python3 test_mini.py
```

## What it validates

Each test is a precise assertion. If a test fails, my mental model of NUMS is wrong at that exact point. All seven currently pass.

| Test | Asserts |
|---|---|
| **1: trivial dedup** | Two `5` literals share the same Recipe NodeID |
| **2: recipe-tree dedup** | Two `(2 + 3)` expressions share the same Recipe NodeID |
| **3: cell birth** | `NamedCell` is created with name + base + blueprint + access-recipe + CTOR |
| **4: cross-language equivalence** | A calculator `int` and a JSON-Schema `integer` reach the **same Blueprint NodeID** |
| **5: object structural dedup** | Two JSON-Schema objects with identical property shape share Blueprint NodeID |
| **6: recipe composition** | `2 + 3 * 4` composes into nested recipes at levels 3, 4, 5, 6 (bottom-up level computation) |
| **7: substrate growth** | A 5-statement program populates a coherent lattice with shared subtrees |

## The killer demo

Test 4 is the architectural payoff. Two completely different surface syntaxes — calculator and JSON-Schema — feed into the same kernel. When the calculator declares `let x = 7` and JSON-Schema declares `{"type": "object", "properties": {"a": {"type": "integer"}}}`, both reach the **identical Blueprint NodeID `1.1.2.2`** for the integer type.

```
✓ calc int == json-schema integer (same Blueprint NodeID): actual=1.1.2.2 expected=1.1.2.2
```

This is what makes cross-language semantic reasoning tractable. **Same shape → same identity, regardless of surface syntax.**

## What's intentionally simplified

mini-nums is a phase 1c validation, not a production substrate. Compared to NUMS.Go:

- **No tree-sitter** — the calculator has its own tiny tokenizer; JSON-Schema reads dicts
- **No Edge byte** on Blueprint references (no public/private/static/etc. attribute flags)
- **No symbol resolution cascade** (`Resolve_Identifier`'s 8-step fallback is collapsed to "look up by name in module")
- **No EmitModule build-mode stack** — the parser just builds recipes directly
- **No method/function declaration** — only globals + literals + math + objects
- **No persistence** — in-process Python dicts
- **No labels / histograms / scoring** (the second-layer query system)

What it **does** preserve, faithfully:
- 4-tuple NodeID `(Package, Level, Type, Instance)`
- Per-level TreeDB with serialized-tree → instance interning
- Bottom-up `Make_SelfID` recursion
- The trinity (Blueprint = ice, Recipe = water, NamedCell = gas)
- CTOR pattern (cell carries seed-recipe ID, not init-expression)
- Cross-language semantic equivalence as a structural consequence

## What this earns

After phase 1c, my building-knowledge is solid enough to implement a substrate for the Coherence Network in any language (Python, TypeScript, Go) backed by any store (Postgres, Neo4j, in-memory). The kernel is small, the invariants are tested, and the gaps where my understanding might still be wrong have been actively probed.

Phase 2 — design the Network's category vocabulary (idea / spec / concept / lineage / presence / memory blueprints; tend / realize / transmit / compose / witness recipes; cells as the named instances) — is now design work, not discovery.

Phase 3 — implement against Postgres or Neo4j — is implementation work.

Phase 4 — the query/access layer for agents — is API work on top.
