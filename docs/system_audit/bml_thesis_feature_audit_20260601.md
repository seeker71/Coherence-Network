# BML Thesis Feature Audit - 2026-06-01

This audit checks the current Form BML support against the thesis and
companion source material in
`docs/field/urs/artifacts/master-thesis-2000/`.

## Result

The current work proves substantial BML/BMF support, but it does not yet prove
FULL thesis `.bml` source compilation into native Form kernel execution.

What is proven today:

- BMF grammar sections such as `section [bml.bmf]` compile to native `.fkb`
  sidecars and execute through `walk_recipe_here`.
- The BML/BMF thesis primitive set is represented: `Nil`, `Fail`,
  `EndOfFile`, `EndOfLine`, `Cut`, `MultiMatch`, and `Primitive`.
- A BMA-like execution band runs forward and backward, including explicit
  `DO` and `UNDO` trace proof.
- A BML class/interface/inheritance component model covers structural bases,
  delegated bases, inherited interfaces, default interface methods, section
  property inheritance, class/static flags, member lookup, access checks, and
  `BML.lang.Application.Main` detection.

What is not proven yet:

- The source compiler scans `section [...]` blocks; it is not yet a
  standalone thesis `.bml` file compiler.
- Full `.bml` files from the thesis companion source tree do not compile end to
  end as source into Form native kernel execution.
- Most thesis grammar rules are present as a BMF rulebook/manifest, but many
  still lower through `bml-emit-node-source` instead of a semantic emitter that
  constructs executable Form/BMA code.
- The current executable `form.bml` support is a maintenance dialect for Form
  stdlib authoring, not the full thesis BML language.

## Coverage Numbers

Current local counts from `form/form-stdlib/grammars/bml.fk`:

- `bml-reference-rule-names`: 172 named thesis/reference grammar entries.
- `section [bml.bmf]`: 163 BML BMF rule entries.
- `section [bml.bmf]` entries using generic `bml-emit-node-source`: 140.
- Explicit reversible/native BML source rules with `<=` reverse emitters: 19.
- Native BML recipe-section compiler rules exposed in `bml-recipe-section`: 19.

These counts mean the grammar surface is recorded, but full semantic lowering
is not complete rule-for-rule.

## Status Vocabulary

- `native-executed`: source or AST lowers to Form/BMA recipe or ops and is run
  by `form/validate.sh`.
- `component-proven`: semantic model functions are exercised in Form tests, but
  a full source parser/emitter path is not proven.
- `grammar-manifest`: the rule name or BMF rule exists, but it lowers to a
  generic source node.
- `thesis-deferred`: the thesis itself marks the feature unsupported or future.
- `gap`: required for the full claim, not yet implemented/proven.

## Feature Matrix

| Thesis area | Thesis reference | Current status | Proof / gap |
| --- | --- | --- | --- |
| BMF top-down backtracking parser and undoable attributes | `backtracking-model-languages.txt:76-86` | native-executed for current Form/BMF engine, component-proven for BMA undo | `bml-thesis-exit-proof.fk` proves branch undo and forward/backward trace; full thesis ParseStream/Context API remains a gap. |
| Runtime grammar extension, modify/add/delete rules during parsing | `backtracking-model-languages.txt:78-82` | grammar-manifest | BMF sections can be compiled at runtime to `.fkb`; live mutation of the active grammar during a parse remains a gap. |
| Grammar-as-objects, nonterminals as classes with inheritance/interfaces | `backtracking-model-languages.txt:86`, `:129-139` | component-proven | BMF reference classes and BML component model are represented; full `.bml` class definitions for every BMF object are not source-compiled. |
| BMF containers: rule, rule ref, template rule, branch, sequence, repeat | `backtracking-model-languages.txt:144-158` | native-executed for Form BMF object model | Existing BMF compiler/runtime tests cover these shapes; BML thesis source files for those classes remain outside full `.bml` compile. |
| BMF primitives: Cut, Fail, EOF, EOL, MultiMatch | `backtracking-model-languages.txt:160-169`; `source-samples/BMF-includes.bml:21-27` | native-executed / component-proven | `bmf-thesis-primitives-band.fk` and `bml-thesis-exit-proof.fk` prove rule presence and primitive statement execution. |
| BMF terminals: char ranges and literals with whitespace control | `backtracking-model-languages.txt:171-174` | native-executed for existing Form BMF subset | Full thesis whitespace/comment placement semantics remain a gap. |
| Tags and semantic methods | `backtracking-model-languages.txt:176-182` | component-proven in BMF object model | Runtime method predicates with thesis ParseStack/Context API remain a gap. |
| `.bml` files, packages, imports, program start | `backtracking-model-languages.txt:241-270` | component-proven for package/import objects and Application.Main detection | End-to-end `.bml` file compile and link remains a gap. |
| Lexical conventions: nested comments, keywords, identifiers, operators, int/hex/bin/float/char/string | `backtracking-model-languages.txt:243-253` | grammar-manifest | Current proof has selected atoms and literals; complete source scanner parity remains a gap. |
| Binary types, structures, lvalue/rvalue | `backtracking-model-languages.txt:271-275` | grammar-manifest | No full binary layout/get-put code generation proof yet. |
| Expressions, casts, member access, calls, `instanceof`, arrays, operators, assignment | `backtracking-model-languages.txt:292-594` | grammar-manifest with small executable expression subset | `method-return-add`, `char-lit`, and `array-int` execute; full precedence, overload, cast, assign, bitwise, logical, and member dispatch remain gaps. |
| Statements: if/select/switch/while/do/loop/for/break/continue/return/choice/try/throw/fail/with | `backtracking-model-languages.txt:596-636` | native-executed for selected BMA subset; grammar-manifest for most source forms | return/break/continue/throw/try/fail/cut/mark/choice/choose execute in proof tests; full control-flow lowering remains a gap. |
| Companion backtracking syntax: `choose`, `if_fail`, `while_success`, `cut`, `mark` | `companion/bml-search-algorithms.txt:49-78` | native-executed for choose/fail/cut/mark; grammar-manifest for if_fail/while_success | Need semantic lowering for full `if_fail` and `while_success`. |
| Local and anonymous functions / blocks with context | `companion/bml-search-algorithms.txt:81-89`, `:212-218`; `backtracking-model-languages.txt:234` | grammar-manifest | Closure capture and block execution semantics remain gaps. |
| Properties and attributes | `backtracking-model-languages.txt:640-689` | component-proven for many helpers; thesis-deferred for several attrs | Tests prove access/class/default/final/deferred/delegate/shared/get/put/strict/relaxed flags as data. Runtime enforcement/codegen is incomplete; thesis itself defers unique, singleton, delegate, shared, strict/relaxed, nostate, const/cost/default/final/inline, out/inout/cast, and access enforcement in lines `651-685`. |
| Classes, sections, syntax blocks, class interfaces | `backtracking-model-languages.txt:692-695` | component-proven; grammar-manifest for full source | Source headers and component bodies are proven; full class block source compilation remains a gap. |
| Interfaces and parent interfaces | `backtracking-model-languages.txt:700-703` | component-proven | Interface inheritance/default lookup is proven; full method declaration/implementation separation from source remains a gap. |
| Multiple inheritance, delegation, inherited interfaces, ambiguity | `backtracking-model-languages.txt:719-723`; `sgb-bml-objects.txt:704-715` | component-proven | Structural/delegated lookup is proven; generated hidden delegate fields, deferred forward calls, and ambiguity diagnostics remain gaps. |
| Access control | `backtracking-model-languages.txt:724-732` | component-proven as helper predicates; thesis-deferred for enforcement | Full compiler/runtime enforcement remains a gap. |
| Constructors, inner construction, casts/coercions | `backtracking-model-languages.txt:737-745` | grammar-manifest | Constructor inheritance/default constructor generation and coercion chains remain gaps. |
| Overloading and templates | `backtracking-model-languages.txt:750-757` | component-proven for template kind restrictions; grammar-manifest for full source | Method/operator overload resolution and template instantiation remain gaps. |
| Exceptions | `backtracking-model-languages.txt:760-762` | native-executed for int throw/catch proof slice | Arbitrary object exception typing/catch matching remains a gap. |
| BML syntax blocks and multi-syntax streams | `backtracking-model-languages.txt:1012-1014`; `bml-search-algorithms.txt:239-246` | native-executed for source-section sidecars; gap for object syntax dispatch | `source-compiler-runtime.fk` and `source-compiler-multi-dialect-band.fk` prove section sidecars; parsing arbitrary objects by syntax name remains a gap. |
| Object runtime definitions, dispatch, casting, instantiators | `sgb-bml-objects.txt:569-655`, `:778-791` | component-proven only for selected lookup helpers | Full instance/interface/method definitions, indexed dispatch, arbitrary interface casts, unique/singleton instantiators, and detached interfaces remain gaps. |
| Companion `.bml` source samples | `companion/source-samples/*.bml` | gap | `BMF-grammar.bml`, `container-Rule.bml`, `primitive-Cut.bml`, and related files are reference inputs, not passing compile fixtures yet. |

## Companion Source Boundary Checks

Concrete thesis sample constructs that are outside the current executable
source subset:

- `BMF-includes.bml` starts with `#include "BMF/Argument.bml"`; the current BML
  rulebook references `include` from `main-rule`, but there is no semantic
  source include rule.
- `BMF-grammar.bml` has `class BMF [public] : Application`; current executable
  BML source handles simplified headers, while full property/body class source
  is still generic.
- `BMF-grammar.bml` has initialized fields such as
  `String m_strDefaultConfigFile = "BMF.cfg";`; the executable `field` proof
  currently covers `$type $name;`.
- `BMF-grammar.bml` has array parameters such as `void Main( String[] hArgs )`;
  current executable method proof covers the no-arg integer-addition slice.
- `primitive-Cut.bml` calls `System.Cut( hContext.Argument( 0 ))`; current
  native proof covers the BMA `cut` operation and `cut;` statement slice, not
  full method-call runtime dispatch.
- `container-Rule.bml` uses constructors and `self(...)` chaining; constructor
  lowering and self-call execution are still gaps.

## Exit Criteria For The FULL Claim

To honestly claim full thesis `.bml` compile-to-native support, the repo needs
all of these passing as machine proof:

1. A `.bml` source scanner/parser that accepts the companion source samples
   directly, including nested comments, full literals, property blocks,
   sections, syntax blocks, classes, interfaces, templates, asm, and all
   statement/expression forms.
2. A semantic emitter for each thesis/reference grammar rule, replacing the
   generic `bml-emit-node-source` path where executable meaning is required.
3. A source-to-model phase that constructs the BML component/object model from
   real `.bml` files, not only from test-built components.
4. A model-to-native phase that lowers classes, methods, statements,
   expressions, exceptions, object dispatch, and backtracking into Form/BMA
   recipes or ops that the native kernels execute.
5. A bidirectional source proof for supported rules: source to object/code and
   object/code back to source where the BMF rule declares a reverse emitter.
6. A forward/backward execution proof over source-originated programs, not only
   hand-built AST slices.
7. A companion-corpus gate that compiles and runs at least
   `BMF-grammar.bml`, `container-Rule.bml`, `primitive-Cut.bml`, and a
   `BML.lang.Application` sample.

## Current Proof Commands

The current proof set is still valuable and should stay as the regression band:

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/grammar-chars.fk form-stdlib/tests/bmf-thesis-primitives-band.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-class-inheritance-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-full-class-model-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-thesis-exit-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk form-stdlib/tests/source-compiler-runtime.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk form-stdlib/tests/source-compiler-multi-dialect-band.fk
```
