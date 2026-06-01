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
- A real `.bml` file can now be scanned from disk, parsed through BML BMF
  executable rules, lowered into BMA, and run forward/backward through the
  native kernels for the focused thesis exit slice in
  `form/form-stdlib/tests/fixtures/bml-thesis-forward-backward-demo.bml`.
- A companion-shaped `.bml` declaration file is now scanned from disk and parsed
  through BML/BMF rules into BML package/import/interface/class components,
  including sections, properties, structural/delegated bases, a string const,
  and a source-originated `Application.Main` body that lowers to BMA and runs.
- The original companion `BMF-includes.bml` file is now scanned from disk and
  parsed as 28 native BML/BMF include declarations.
- The original companion `primitive-Cut.bml` file is now scanned from disk,
  parsed through BML/BMF declaration rules into a `Cut : Primitive` class with
  method parameters, and its `System.Cut(...)` method body lowers to native BMA
  `cut` with forward/backward `DO`/`UNDO` proof. Its string-returning methods
  also lower and execute through the native kernels.
- BML file scanning now has a sibling-native scanner in the Go, Rust, and
  TypeScript kernels so larger `.bml` files do not overflow the Form-level
  recursive scanner before BMF rules run.
- The original companion `container-Rule.bml` and `BMF-grammar.bml` files now
  scan and parse as whole source files. `BMF-grammar.bml` still lands as a
  class shell while its grammar body lowering remains an explicit gap.
- The original companion `container-Rule.bml` file now parses real class
  bodies for `RuleProcess` and `Rule`, including sections, fields,
  constructors, method signatures, parameters, properties, initialized fields,
  and source body tokens. Its method bodies are represented as source-bearing
  components; full statement/expression semantic lowering for those bodies is
  still a gap.
- A first source-originated body execution bridge now runs simple assignment
  bodies from the original `container-Rule.bml` through native record state:
  the full `Rule(...)` constructor assigns parsed fields, and `SetProcess()`
  mutates `m_hProcess` from the real method body tokens.
- Source-originated `self(...)` constructor chaining now executes for
  `container-Rule.bml`: overloads forward into the full constructor, bind
  actual arguments into the target constructor environment, and mutate native
  record state through the assignment body executor.
- A BML class/interface/inheritance component model covers structural bases,
  delegated bases, inherited interfaces, default interface methods, section
  property inheritance, class/static flags, member lookup, access checks, and
  `BML.lang.Application.Main` detection.

What is not proven yet:

- The source compiler can scan focused standalone executable and declaration
  `.bml` streams, but it is not yet a full thesis `.bml` file compiler.
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
- `section [bml.bmf]`: 172 BML BMF rule entries.
- `section [bml.bmf]` entries using generic `bml-emit-node-source`: 140.
- BML BMF entries with semantic emitters other than `bml-emit-node-source`: 32.
- Explicit reversible BML source rules with `<=` reverse emitters: 17.
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
| BMF primitives: Cut, Fail, EOF, EOL, MultiMatch | `backtracking-model-languages.txt:160-169`; `source-samples/BMF-includes.bml:21-27`; `source-samples/primitive-Cut.bml` | native-executed / component-proven | `bmf-thesis-primitives-band.fk` and `bml-thesis-exit-proof.fk` prove rule presence and primitive statement execution. `bml-thesis-primitive-cut-source-proof.fk` proves the real companion `Cut` class source parses, lowers `System.Cut(...)` to BMA `cut`, and runs forward/backward with undo trace. |
| BMF terminals: char ranges and literals with whitespace control | `backtracking-model-languages.txt:171-174` | native-executed for existing Form BMF subset | Full thesis whitespace/comment placement semantics remain a gap. |
| Tags and semantic methods | `backtracking-model-languages.txt:176-182` | component-proven in BMF object model | Runtime method predicates with thesis ParseStack/Context API remain a gap. |
| `.bml` files, packages, imports, program start | `backtracking-model-languages.txt:241-270` | native-executed for focused executable file; component/native-proven for companion-shaped declaration file | `bml-thesis-file-execution-proof.fk` proves executable file DO/UNDO; `bml-thesis-companion-file-proof.fk` proves real package/import/class/interface declarations and source-originated `Main` method body. Full link/load remains a gap. |
| Lexical conventions: nested comments, keywords, identifiers, operators, int/hex/bin/float/char/string | `backtracking-model-languages.txt:243-253` | native-executed for focused file scanner subset | Current proofs cover line/block comments, keywords, properties, identifiers, operators, ints, strings, and large-file scanning through sibling-native BML scanners; complete hex/bin/float/char escape parity remains a gap. |
| Binary types, structures, lvalue/rvalue | `backtracking-model-languages.txt:271-275` | grammar-manifest | No full binary layout/get-put code generation proof yet. |
| Expressions, casts, member access, calls, `instanceof`, arrays, operators, assignment | `backtracking-model-languages.txt:292-594` | grammar-manifest with small executable expression subset | `method-return-add`, `char-lit`, and `array-int` execute. `bml-thesis-rule-body-execution-proof.fk` proves simple name assignment bodies from `container-Rule.bml` execute against native records. Full precedence, overload, cast, bitwise, logical, member dispatch, and general assignment lowering remain gaps. |
| Statements: if/select/switch/while/do/loop/for/break/continue/return/choice/try/throw/fail/with | `backtracking-model-languages.txt:596-636` | native-executed for selected BMA subset; grammar-manifest for most source forms | return/break/continue/throw/try/fail/cut/mark/choice/choose execute in proof tests; full control-flow lowering remains a gap. |
| Companion backtracking syntax: `choose`, `if_fail`, `while_success`, `cut`, `mark` | `companion/bml-search-algorithms.txt:49-78` | native-executed for choose/fail/cut/mark; grammar-manifest for if_fail/while_success | Need semantic lowering for full `if_fail` and `while_success`. |
| Local and anonymous functions / blocks with context | `companion/bml-search-algorithms.txt:81-89`, `:212-218`; `backtracking-model-languages.txt:234` | grammar-manifest | Closure capture and block execution semantics remain gaps. |
| Properties and attributes | `backtracking-model-languages.txt:640-689` | component-proven for many helpers; thesis-deferred for several attrs | Tests prove access/class/default/final/deferred/delegate/shared/get/put/strict/relaxed flags as data. Runtime enforcement/codegen is incomplete; thesis itself defers unique, singleton, delegate, shared, strict/relaxed, nostate, const/cost/default/final/inline, out/inout/cast, and access enforcement in lines `651-685`. |
| Classes, sections, syntax blocks, class interfaces | `backtracking-model-languages.txt:692-695` | component-proven; source-proven for focused companion declarations | `bml-thesis-companion-file-proof.fk` proves real `.bml` class sections, properties, fields, consts, and a simple method. Full arbitrary class block source compilation remains a gap. |
| Interfaces and parent interfaces | `backtracking-model-languages.txt:700-703` | component-proven; source-proven for focused companion declarations | Real `.bml` interface parent declarations now parse into model components; full method declaration/implementation separation from source remains a gap. |
| Multiple inheritance, delegation, inherited interfaces, ambiguity | `backtracking-model-languages.txt:719-723`; `sgb-bml-objects.txt:704-715` | component-proven; source-proven for two-base header slice | Real `.bml` `class E [public] : C, D {}` now proves first base as structural and remaining bases as delegated; generated hidden delegate fields, deferred forward calls, and ambiguity diagnostics remain gaps. |
| Access control | `backtracking-model-languages.txt:724-732` | component-proven as helper predicates; thesis-deferred for enforcement | Full compiler/runtime enforcement remains a gap. |
| Constructors, inner construction, casts/coercions | `backtracking-model-languages.txt:737-745` | partial native-executed / gap | Real `container-Rule.bml` constructors parse, the full constructor assignment body executes, and `self(...)` overload chaining dispatches into the full constructor. Constructor inheritance/default constructor generation and coercion chains remain gaps. |
| Overloading and templates | `backtracking-model-languages.txt:750-757` | component-proven for template kind restrictions; grammar-manifest for full source | Method/operator overload resolution and template instantiation remain gaps. |
| Exceptions | `backtracking-model-languages.txt:760-762` | native-executed for int throw/catch proof slice | Arbitrary object exception typing/catch matching remains a gap. |
| BML syntax blocks and multi-syntax streams | `backtracking-model-languages.txt:1012-1014`; `bml-search-algorithms.txt:239-246` | native-executed for source-section sidecars; gap for object syntax dispatch | `source-compiler-runtime.fk` and `source-compiler-multi-dialect-band.fk` prove section sidecars; parsing arbitrary objects by syntax name remains a gap. |
| Object runtime definitions, dispatch, casting, instantiators | `sgb-bml-objects.txt:569-655`, `:778-791` | component-proven only for selected lookup helpers | Full instance/interface/method definitions, indexed dispatch, arbitrary interface casts, unique/singleton instantiators, and detached interfaces remain gaps. |
| Companion `.bml` source samples | `companion/source-samples/*.bml` | partial native-executed / gap | `BMF-includes.bml` now parses as a whole source file. `primitive-Cut.bml` now parses as a whole source file and its executable method bodies run natively. `container-Rule.bml` now parses real sections, fields, constructors, method signatures, parameters, properties, field initializers, and body source tokens; its full constructor, `self(...)` constructor chaining, and `SetProcess` simple assignment bodies execute against native records. `BMF-grammar.bml` still parses as a class shell; full grammar-body lowering remains a gap. |
| Focused `.bml` file-to-native execution | `bml-thesis-forward-backward-demo.bml` | native-executed | `bml-thesis-file-execution-proof.fk` scans a real `.bml` file, parses `state-int` plus `try-throw-return`, lowers to BMA, runs DO/UNDO, and verifies restored state. |
| Focused companion-shaped `.bml` declarations | `BMF-grammar.bml`, `container-Rule.bml`, `primitive-Cut.bml` slices | component/native-proven | `bml-thesis-companion-file-proof.fk` scans `bml-thesis-companion-declarations.bml`, parses package/import/interface/class/section/field/string const/two-base/Main method shapes, builds the class model, and runs `Main` through BMA. |

## Companion Source Boundary Checks

Concrete thesis sample constructs that are outside the current executable
source subset:

- `BMF-includes.bml` starts with `#include "BMF/Argument.bml"`; this is now
  covered by `file-include` and `bml-thesis-includes-source-proof.fk`.
- `BMF-grammar.bml` has `class BMF [public] : Application`; the focused
  companion shell proof now covers that class/property/base shape as a whole
  source file, while full arbitrary class body lowering remains a gap.
- `BMF-grammar.bml` has initialized fields such as
  `String m_strDefaultConfigFile = "BMF.cfg";`; the executable `field` proof
  currently covers `$type $name;`.
- `BMF-grammar.bml` has array parameters such as `void Main( String[] hArgs )`;
  current executable method proof covers the no-arg integer-addition slice.
- `primitive-Cut.bml` calls `System.Cut( hContext.Argument( 0 ))`; the source
  file now parses directly and lowers that call shape to native BMA `cut`.
  General method-call runtime dispatch remains a gap.
- `container-Rule.bml` uses private/public sections, initialized fields,
  constructor overloads, `self(...)` chaining, operator methods, and large
  method bodies. `bml-thesis-companion-members-source-proof.fk` now proves the
  real file parses those member surfaces into BML components.
  `bml-thesis-rule-body-execution-proof.fk` proves simple assignment bodies
  from the same real file execute through native `record_set`/`record_get`
  state. `bml-thesis-rule-self-constructor-proof.fk` proves `self(...)`
  constructor overload chaining from the real file. Executable lowering for the
  complex control-flow and expression bodies remains a gap.

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
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-thesis-file-execution-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-thesis-companion-file-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-thesis-includes-source-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-thesis-primitive-cut-source-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-thesis-companion-shell-source-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-thesis-companion-members-source-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-thesis-rule-body-execution-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/bml.fk form-stdlib/tests/bml-thesis-rule-self-constructor-proof.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk form-stdlib/tests/source-compiler-runtime.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk form-stdlib/tests/source-compiler-multi-dialect-band.fk
```
