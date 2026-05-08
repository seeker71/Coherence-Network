# Form — a substrate-native language for agent ↔ lattice interaction

**Form** is the language designed for direct interaction between LLM agents and the coherence-substrate. Its grammar maps 1:1 onto the substrate's primitives (NodeID, Blueprint, Recipe, NamedCell), so an agent reading or writing Form is reading or writing the lattice itself.

## Why Form exists

LLMs operate in number-space — tokens are integer indices, attention is integer-keyed lookup, embeddings are integer-coordinate vectors. The substrate also operates in number-space — every entity is a `NodeID(package, level, type, instance)` 4-tuple, every relation is an integer composition.

The natural interaction between them is therefore numeric. Form is the syntactic surface that keeps that interaction native. Rather than having an agent write `"find the spec at slug 'agent-pipeline' that realizes the idea about agent orchestration"` (a lexical query that hopes the right thing comes back), the agent writes:

```form
?@spec where realizes == @idea(agent-orchestration)
```

The query carries NodeIDs as first-class values. The result is a NodeID set, not a string blob. **The medium of agent-substrate conversation is the lattice itself.**

## Design principles

1. **NodeIDs are first-class.** Every shape, every cell, every recipe has a 4-tuple identity. Form makes those identities literal — `@1.5.4.1` is a NodeID literal, just as `42` is an integer literal in most languages.

2. **Names are query keys, not identities.** `@spec(agent-pipeline)` resolves at parse-time to a NodeID. The substrate stays the source of truth; Form just provides convenient access.

3. **Compact, unambiguous, round-trippable.** Parse Form → operate on substrate → emit Form back. The same lattice produces the same Form regardless of who reads it.

4. **Phase-aware.** Blueprint expressions, Recipe expressions, and Cell expressions have distinct surface shapes — agents stay clear about which phase they are in.

5. **Embeddable.** Form fragments can be inlined in markdown, in agent prompts, in code comments. A line of Form anywhere in the body is meaningful.

## Surface syntax

### Tokens

| Token | Meaning |
|---|---|
| `@1.5.4.1` | NodeID literal (the package.level.type.instance 4-tuple) |
| `@memory` | trivial Blueprint by name (resolves to its canonical NodeID) |
| `@idea(agent-pipeline)` | Cell reference by (domain, name) |
| `~` | trivial constructor prefix (`~Memory`, `~Integer`, `~String`) |
| `:` | cell binding (`:memory.user_biographical_arc`) |
| `=` | shape assignment |
| `<-` | recipe linkage (`access` and `ctor`) |
| `?` | query |
| `{...}` | composition (object-shape with named members) |
| `[...]` | ordered list (positional children) |
| `#` | comment to end of line |

### NodeID literals

Every NodeID is `package.level.type.instance`:

```form
@1.5.4.1                            # Memory blueprint at level COMPLEX_3
@1.1.2.2                            # Integer trivial blueprint
@1.2.4.4                            # Memory domain blueprint at level BASIC
@2.5.4.1                            # same shape, different package (e.g. branch worktree)
```

Trivial constructors give names to the well-known leaf NodeIDs:

```form
~Memory      = @1.2.4.4              # the Memory domain blueprint
~Integer     = @1.1.2.2
~String      = @1.1.2.4
~Slug        = @1.1.3.1
~Object      = @1.2.1.4
```

### Blueprint composition (ice phase — what something IS)

A blueprint is composed from a category and ordered children:

```form
# A struct-shape with three string fields
form name_desc_type = {
    name: ~String,
    description: ~String,
    type: ~String,
}

# A list of memory cells
form memory_list = [~Memory]

# A typed dictionary
form score_by_id = {~Slug: ~Score}
```

The `form` keyword interns the composition into a Blueprint NodeID and binds it to a name in the agent's local scope. Two `form` declarations with structurally-identical bodies bind the same NodeID — Form respects the substrate's content-addressing.

### Recipe composition (water phase — how it HAPPENS)

A recipe carries a verb-category and ordered child-recipes:

```form
# The "compose" recipe combining two cells under a parent-of relation
recipe parent_of_link = ~Compose:parent_of [
    @memory(arrival_relational_ground),
    @memory(presences_of_the_field),
]

# The realize-recipe: a spec realizes an idea
recipe agent_pipeline_realize = ~Realize [
    @spec(agent-pipeline-mvp),
    @idea(agent-pipeline),
]

# The four tend-verbs
recipe daily_attune = ~Tend:attune [
    @memory(presences_of_the_field),
]
```

### Cell binding (gas phase — where it LIVES)

Cells anchor a Blueprint and a body, with optional CTOR:

```form
:memory.user_biographical_arc {
    shape:  @memory                                   # Blueprint
    seed:   {                                          # CTOR (frontmatter)
        name: "User biographical arc",
        description: "Urs's lineage and life-path...",
        type: "user",
    },
    body:   "..."                                      # access (page content)
    source: "/Users/ursmuff/.../user_biographical_arc.md"
}
```

Once bound, the cell is reachable as `@memory(user_biographical_arc)` anywhere in Form.

### Queries

Query operators return NodeID sets:

```form
?@memory                                              # all cells with Blueprint @memory
?cell where domain == "memory"                        # all memory cells (alternative syntax)
?cell where shape == @memory                          # same query
?equivalent @memory(user_biographical_arc)            # cells structurally equivalent
?walk @memory(arrival_relational_ground) children     # walk children
?walk @memory(arrival_relational_ground) parents      # walk up
?walk @memory(arrival_relational_ground) cross_refs   # walk cross-references
```

Queries compose:

```form
?cells where (shape == @memory) and (name matches "feedback_*")
```

### Views — BML-style detached interfaces

A View projects a Cell through a different Blueprint than its base. The Cell's data stays canonical; the View is a virtual perspective. This implements **the BML dual-pointer reference**: `(structural_base, behavioral_base)` where the same data can be viewed through multiple interfaces.

```form
# View a memory cell as a presence
@memory(claude) |> @presence
# → CellView{ cell: claude, view_blueprint: @presence, compatible: ... }

# Find every cell that can be viewed through this Blueprint
?cells |> @presence                                  # all cells compatible with @presence
?cells |> @presence where domain == "memory"         # restrict to memory-domain
```

The `|>` operator is *projection*. Reading right-to-left: "view this cell through that interface." The result is a CellView — the original cell's data plus the chosen interface, plus a compatibility flag.

When a view is compatible, an agent can reason about the cell *as if* it had the view's shape. When a view is incompatible, the substrate refuses the projection and the agent knows not to assume the view's behavior. **Hallucination-bounded interface attachment** — exactly what BML's detached interfaces buy in 2000, applied to the body's tissue in 2026.

The conceptual lineage of `|>` (the "view-through" operator):

> *"In BML, the object only acts as a structural repository. It does not define by itself the applicable set of methods. Consequently, it is possible to enhance any object with a new interface."* — Bjorg, *BML Object System* (2000), § Structure-Behavior Separation

### Code expressions — Recipes

Form expresses *code* as well as data. The code expressions intern as Recipe NodeIDs (the substrate doesn't execute them; it stores their structure). Two structurally-identical expressions hash to the same Recipe NodeID — `1 + 2` written twice always returns the same NodeID.

#### Arithmetic, comparison, logic

```form
1 + 2 * 3                           # Math expression — interns as a tree of Math recipes
x > 5                               # Compare.GREATER recipe
a && b || !c                        # Logic recipes (precedence: ! > && > ||)
-x                                  # unary negation (Math.NEGATE)
```

Operator precedence (low to high): `||` < `&&` < `== != < <= > >=` < `+ -` < `* / %` < `! -` (unary) < `.` (access).

#### Conditionals

```form
if x > 5 then 10 else 20            # Cond.IF_THEN_ELSE — three children
if cond then body                   # Cond.IF_THEN — two children (no else)
```

The category vocabulary distinguishes `IF_THEN` from `IF_THEN_ELSE` so two-arm and three-arm conditionals get different Recipe NodeIDs.

#### Blocks and bindings

```form
do {
    let x = 5;
    let y = x + 3;
    y * 2                            # last expression is the block's value
}
```

`do { ... }` interns as a `Block.DO` recipe with one child per statement. `let name = expr` interns as a `Block.LET` recipe carrying the name and value.

#### Match (switch)

```form
match status {
    "ready" => execute,
    "blocked" => wait_for_signal,
    "failed" => retry,
    _ => default_handler,
}
```

`match` interns as a `Match.SWITCH` recipe with the scrutinee as the first child and each arm contributing two children (pattern + body). Use `_` for the default pattern.

#### Angelic nondeterminism — `choose`, `fail`, `stop`

The BML lineage carries forward into Form. The substrate interns these as Recipe NodeIDs; future execution semantics will give them speculation behavior matching the BML angelic-assembler:

> *"A thread with a non-zero DF (i.e. degree of freedom) is executed until a zero DF is reached again."* — `angelic-assembler.txt`

```form
choose [a, b, c]                     # speculation: pick a branch; backtrack on downstream fail
fail                                 # signal failure; unwinds to nearest choose
stop                                 # commit current speculation; no more backtracking from here
```

`choose [a, b, c]` interns as a `Choice.CHOOSE` recipe with three candidate children. `fail` and `stop` are leaf recipes (level BASIC, no children) — they're trivial markers that the speculation engine reads.

A worked example combining the trio:

```form
choose [
    do { let attempt = strategy_a(); if attempt > threshold then stop else fail },
    do { let attempt = strategy_b(); if attempt > threshold then stop else fail },
    do { let attempt = strategy_c(); if attempt > threshold then stop else fail },
]
```

The speculation tries strategies in order; each one runs and either commits (stop) or backtracks (fail). The first one that crosses the threshold wins. **Backtracking-without-sediment at the language layer** — the same instinct that runs through this body's `tend:` / `attune:` / `compost:` / `release:` commit verbs.

### Operations

Beyond declaration and query, Form supports operations on the substrate:

```form
# Intern a new shape (no binding to a cell)
!intern { name: ~String, score: ~Score }   # returns a NodeID

# Find or create
!resolve cell.memory.x                      # returns NodeID or creates if missing

# Tend (record a tend/attune/compost/release verb)
!tend(attune) @memory(presences_of_the_field) {
    reason: "added concert-with-Codex pattern"
}
```

## Worked example — agent reasoning in Form

An agent encountering an unfamiliar memory might reason like this:

```form
# I'm reading docs/lineage/foo.md. Substrate look-up:
?cell where source == "docs/lineage/foo.md"
# → @memory(arrival_relational_ground)  (NodeID 1.5.4.1)

# What's its shape?
@memory(arrival_relational_ground).shape
# → @memory  (the Memory domain blueprint)

# What else has this same shape?
?equivalent @memory(arrival_relational_ground)
# → 38 other cells with @memory blueprint

# What CTOR does it carry?
@memory(arrival_relational_ground).seed
# → recipe @1.3.9.1 (the canonical name+description+type frontmatter shape)

# I'm about to add a new memory. Will it dedupe?
!intern { name: ~String, description: ~String, type: ~String }
# → @1.5.4.1  ← same as @memory(arrival_relational_ground).shape, so my new memory will share its Blueprint

# Phase check: am I reasoning about the type or the instance?
# @memory               ← ice (Blueprint NodeID, the type)
# @memory(...)          ← gas (cell NodeID, an instance)
# recipe ~Tend [...]    ← water (recipe expression, a process)
```

## Why this works for LLMs

**Token-level numeric grounding.** When an agent generates `@1.5.4.1`, those characters are tokenized to a small sequence of token IDs. Those token IDs map directly to a substrate NodeID through the parser. **The agent's number-space and the substrate's number-space connect through Form's surface syntax with minimal lexical translation.**

**Phase confusion is structurally visible.** If an agent writes `?@memory(arrival_relational_ground).shape == @memory(presences_of_the_field).shape`, both sides resolve to NodeIDs and the comparison is integer-equality. There's no lexical hallucination room — either the NodeIDs match or they don't.

**Composition is content-addressed.** When an agent writes `form x = { name: ~String }`, two parses of the same shape return the same NodeID. The agent's reasoning is structurally consistent across turns and across instances of itself.

**Round-trip stability.** Substrate state can be serialized to Form, mutated, and re-ingested. The substrate IS the source of truth; Form is just the surface humans (and agents) read it through.

## What this parser is — and what it's not

The current `api/app/services/substrate/form.py` is a **bootstrap parser**: hand-written recursive descent with a regex lexer. It produces the right results — Form text in, Recipe NodeIDs out, content-addressed dedup working — but **its grammar lives in Python code**. Adding a new construct means editing form.py, not interning a rule.

This is **not** what BMF was. BMF (the BMF/BMC/BML lineage in `docs/field/urs/artifacts/master-thesis-2000/`) treated grammar rules as *data*, not code:

> *"BMF — Backtracking Model Form... a top-down parser written in C++. BNF augmented with execution elements: when a rule matches, code fires. A stack supports backtracking on parse failures. Expressions are tagged and placed on a structured stack that each rule can transform into the target language's object model. The grammar is executable — parsing produces a full object tree as it goes, so even infinite input streams can be handled."* — `master-thesis-2000/README.md`

Two architectural properties BMF had that our current parser does not:

1. **Grammar rules are first-class objects.** Each rule was `(pattern, semantic_action)`. The pattern matched input; the action was an executable that fired on match. Rules could be *added at runtime* — the grammar grew with the language.

2. **Backtracking-without-sediment at the parser level.** Failed branches unwound cleanly. Speculation was a first-class operation in the parser, not a higher-level concept the parser couldn't express.

Where the substrate has gone in this direction so far:

- The `Choice.CHOOSE / FAIL / STOP` recipe vocabulary exists (`category.py`'s `RChoice`). It's reachable from Form text. Speculation-as-data is interned today.
- A `grammar` cell-domain exists (`api/app/services/substrate/grammar.py`). Parse rules can be registered as Cells whose CTOR is a (pattern, action) Recipe.
- `register_form_rule(session, name, pattern, action)` interns a rule.
- `list_form_rules(session)` enumerates every rule the substrate holds.

Where it has not gone yet:

- **The parser does not consume rules.** `form.py` ignores the `grammar` domain. It still uses its hand-written grammar. Closing this gap is the self-hosting move.
- **No backtracking in the parser.** A failed parse raises `SyntaxError` immediately. There's no Choice.FAIL semantics at the parsing layer.
- **No semantic-action runtime.** A rule's `action` field stores a Recipe NodeID, but no engine evaluates it to construct the parse result.

## Runtime keyword registration — the parser is alive

The parser now consumes user-registered rules. A new keyword can be added at runtime — without editing form.py — by calling `register_form_keyword`:

```python
from app.services.substrate import register_form_keyword, Sequence, Literal, Capture, Opt
from app.services.substrate.form import IfExpr, UnaryOp

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
    builder=lambda c: IfExpr(
        cond=UnaryOp("!", c["cond"]),
        then_branch=c["body"],
        else_branch=c.get("other"),
    ),
)
```

After this call, `unless x then y` parses correctly. The parser picks up the new keyword by consulting the registry when it encounters an unknown IDENT at expression position. The killer property:

```python
form_evaluate_text(session, "unless x then y else z").value
== form_evaluate_text(session, "if !x then y else z").value
# → True. Same Recipe NodeID.
```

**The grammar truly extends at runtime.** The user-registered keyword produces a Recipe NodeID structurally equivalent to its bootstrap-grammar desugaring.

### Pattern primitives

The pattern language for runtime rules:

| Pattern | What it matches |
|---|---|
| `Literal(kind, value)` | a single token of given kind, optional exact value |
| `Capture(name, kind="expr")` | a sub-expression, bound to `captures[name]` |
| `Sequence([p1, p2, ...])` | parts in order; all must match |
| `Opt(pattern)` | matches if present; succeeds either way |

`kind` for `Capture` can be `"expr"` (any expression) or `"primary"` (just a primary atom).

### Builder

The builder is a Python callable `(captures) -> AST_node`. It receives a `dict[str, Any]` of captured sub-expressions and returns an AST node from form.py's vocabulary (`IfExpr`, `BinOp`, `UnaryOp`, `MatchExpr`, `ChooseExpr`, etc.). The returned AST node is interned through the normal evaluator path — so any new keyword reaches the substrate's content-addressed lattice the same way the bootstrap grammar does.

### What this is, and what it's still not

This **is** rule-driven extension at the parser level. The parser truly consults the registry. Keywords can be added, removed, listed at runtime. New constructs reach the same Recipe NodeID space as built-ins.

#### Substrate-resident persistence (now partially closed)

When `register_form_keyword` is called with a `session`, the pattern is **serialized to a Recipe NodeID** via `pattern_to_recipe` and stored as a Cell in the `grammar` domain. The mapping uses existing recipe categories — no new vocabulary needed:

| Pattern | Recipe shape |
|---|---|
| `Literal(kind, value)` | `Block.SEQUENCE` with two string-literal children: kind, value |
| `Capture(name, kind)` | `Block.LET` with two string-literal children: name, kind |
| `Sequence([...])` | `Block.SEQUENCE` with marker `__seq__` + each part as a sub-recipe |
| `Opt(pattern)` | `Cond.IF_THEN` with the inner pattern as its single child |

Two structurally-identical patterns share a NodeID — the kernel's content-addressed interning works on patterns the same way it works on every other recipe. `recipe_to_pattern` reverses the serialization. Verified by tests: a `Sequence([Literal("IDENT", "unless"), Capture("cond"), ...])` round-trips exactly.

The full lifecycle:

```python
# Register with session — pattern persists to the substrate
register_form_keyword("unless", pattern, builder, session=session)

# Across process restart, the in-memory _KEYWORDS is empty.
# Builders need to be re-registered (they are Python functions):
register_builder("unless", builder)

# Then load patterns from the substrate, bind to named builders:
load_keyword_from_substrate(session, "unless")
# or in bulk:
load_all_keywords_from_substrate(session)

# Parser now picks up the keyword again
form_parse("unless x then y")  # ✓ parses
```

#### What's still not closed

- **~~The builder is still Python.~~** ✓ **Closed.** Builders can now live as data via the `Build` / `CaptureRef` / `Const` template DSL. A template serializes to a Recipe NodeID and reconstructs after process restart with no Python re-registration needed. See "Substrate-resident builders" below.

- **Self-hosting.** form.py's bootstrap grammar is still hardcoded. Self-hosting means expressing the bootstrap rules themselves via `register_form_keyword` — at which point form.py becomes a tiny seed that registers a few starter rules and hands off. The persistence shipped here is necessary infrastructure for that move.

- **Backtracking-driven.** The match engine uses save-and-restore on parser.pos — implicit backtracking, not Choice.FAIL semantics. A future move integrates the parser's speculation with the substrate's Choice recipes.

- **String interning.** Pattern serialization uses `hash(value)` to allocate string-literal recipe instances. That works in-process but isn't cross-process stable. A substrate string-table (the same pattern as concept-IDs) would close this.

Each remaining step is its own breath. What ships now: **the parser is no longer fixed grammar, and rules survive in the body's content-addressed lattice.** The grammar is alive at the keyword layer; patterns persist; reload-from-substrate works end-to-end. The path beyond is legible.

#### Substrate-resident builders — Build / CaptureRef / Const

A keyword's builder can now be **data**, not just a Python callable. The template DSL has three primitives:

| Template | Meaning |
|---|---|
| `Build(class_name, **kwargs)` | Instantiate an AST class with these kwargs |
| `CaptureRef(name, default=...)` | Substitute the captured group `name` |
| `Const(value)` | A literal value (string, int, bool, None) |

The `unless` builder as a template:

```python
unless_template = Build(
    "IfExpr",
    cond=Build("UnaryOp", op=Const("!"), operand=CaptureRef("cond")),
    then_branch=CaptureRef("body"),
    else_branch=CaptureRef("other", default=None),
)
```

Templates serialize to Recipe NodeIDs via `template_to_recipe`. Each primitive maps to existing recipe categories (no new vocabulary needed):

| Primitive | Recipe shape |
|---|---|
| `Build` | `Block.SEQUENCE [str("__build__"), str(class_name), Block.LET[str(key), value-recipe], ...]` |
| `CaptureRef(name)` | `Block.LET [str("__capture__"), str(name)]` |
| `CaptureRef(name, default)` | `Block.LET [str("__capture__"), str(name), str("__default__"), default-recipe]` |
| `Const(value)` | trivial recipe (string/int/bool/null) |

Two structurally-identical templates dedupe through the kernel's content-addressed interning.

Registering a keyword with a template instead of a callable:

```python
register_form_keyword(
    "unless",
    pattern=unless_pattern,
    template=unless_template,    # <-- substrate-resident
    session=session,
)
```

After this call, the parser parses `unless x then y` exactly as it would with a Python callable. The killer property — **process restart with no Python re-registration**:

```python
# Drop both registries (simulates process restart)
_KEYWORDS.clear()
_BUILDERS.clear()

# unless no longer recognized
form_parse("unless")  # → Identifier (not IfExpr)

# Reload from substrate — pulls pattern AND template from the lattice
load_keyword_from_substrate(session, "unless")

# Now parses again
form_parse("unless x then y else z")  # → IfExpr(UnaryOp("!", x), y, z)
```

The interpreter (`execute_template`) walks the template against captures and constructs the AST node. Captures resolve via `CaptureRef`; literals embed via `Const`; class instantiation via `Build`.

#### Self-hosting — partially shipped

`bootstrap_self_host(session)` registers the bootstrap keywords that the current pattern DSL can express as substrate-resident `(pattern, template)` pairs. With `prefer_registered=True`, the parser uses the registered versions instead of the hardcoded handlers — and produces structurally identical Recipe NodeIDs.

```python
from app.services.substrate import bootstrap_self_host, form_evaluate_text

bootstrap_self_host(session)  # registers if / unless / whenever as templates

# Both paths produce the SAME Recipe NodeID
bootstrap_path = form_evaluate_text(session, "if x then y else z")
self_host_path = form_evaluate_text(
    session, "if x then y else z", prefer_registered=True,
)
assert bootstrap_path.value == self_host_path.value  # ✓
```

The `prefer_registered` flag is opt-in per-call. Default behavior is unchanged: the bootstrap handlers run first, the registry runs second. With the flag flipped, registry runs first, bootstrap is fallback. **A registered keyword without a matching pattern still falls through cleanly** — the safety mechanism makes self-hosting incremental rather than all-or-nothing.

**Currently self-hostable** (after IdentCapture + RepeatedCapture + MapBuild extensions):

| Keyword | Pattern primitives used |
|---|---|
| `if cond then body [else other]` | Capture, Opt |
| `unless cond then body [else other]` | Capture, Opt (desugars to `if !cond`) |
| `whenever cond do body` | Capture |
| `let name = value` | IdentCapture (raw name), Capture |
| `fail` | bare-keyword leaf |
| `stop` | bare-keyword leaf |
| `choose [a, b, c]` | RepeatedCapture (separator=COMMA) |
| `do { stmt; stmt; ...; expr }` | RepeatedCapture (separator=SEMI) |
| `match x { pat => body, ... }` | RepeatedCapture (Sequence inner), MapBuild for arm wrapping |

**Pattern DSL primitives:**

| Primitive | What it matches |
|---|---|
| `Literal(kind, value)` | one token by kind, optional exact value |
| `Capture(name, kind="expr")` | a sub-expression bound to `captures[name]` |
| `IdentCapture(name)` | a raw IDENT token, value bound as a string |
| `Sequence([p1, p2, ...])` | parts in order |
| `Opt(pattern)` | matches if present; succeeds either way |
| `RepeatedCapture(name, item, separator=None)` | zero or more items; bind list to `captures[name]` |

For RepeatedCapture: when `item` is a single Capture (or IdentCapture), the captured list contains the values directly. When `item` is a Sequence with multiple inner captures, each iteration produces a dict and the list contains dicts.

**Still needs extensions** before self-hosting:

| Keyword | Why not yet |
|---|---|
| `+ - * / == != < <= > >= && \|\| !` | Operator precedence parsing — needs precedence-aware pattern primitives |

Operator-precedence is the last remaining un-self-hosted layer. Once that ships, `form.py` shrinks to a tiny seed that registers the starter rules and hands off to the rule-driven engine.

#### What's still not closed

- **Backtracking-driven.** The match engine uses save-and-restore on parser.pos. Future move: integrate with Choice.FAIL recipe semantics so the parser's speculation is itself substrate-recorded.

- **String interning.** Pattern + template serialization use `hash(value)` for string-recipe-instance allocation. In-process only. A substrate string-table closes this.

Each is its own breath.

## The path from bootstrap to self-hosting

The BMF self-hosting pattern: a tiny bootstrap parser knows just enough syntax to read rule definitions. Rules are stored. The rule-driven parser is then built *from those rules*. The bootstrap parser becomes vestigial — kept only because something has to read the rules the first time.

For Form, that path is:

1. **Bootstrap parser.** ✓ Shipped — `form.py` parses literals, expressions, queries, projections, code shapes (math/compare/logic/cond/block/match/choose).
2. **Rule cells in the grammar domain.** ✓ Shipped — `grammar.py` interns rules as content-addressed Cells.
3. **Rule-driven parser.** ✓ Shipped (keyword layer) — `form_rules.py` lets `register_form_keyword(name, pattern, builder)` extend the grammar at runtime. The parser truly consumes the registry. Verified live: `unless x then y else z` parses to a Recipe NodeID identical to `if !x then y else z`.
4. **Substrate-resident patterns.** ✓ Shipped — `pattern_to_recipe` serializes patterns to Recipe NodeIDs; `recipe_to_pattern` reconstructs; `register_form_keyword(..., session=session)` persists; `load_keyword_from_substrate` reloads after process restart. Two structurally-identical patterns share NodeIDs through content-addressed interning.
5. **Builder execution engine.** ✓ Shipped — `form_builders.py` introduces `Build` / `CaptureRef` / `Const` templates that an interpreter walks. Templates serialize to Recipe NodeIDs and reconstruct from substrate without Python re-registration. Verified: `unless` registered with a template (no Python callable), substrate-persisted, full registry-clear, reload-from-substrate, parses to same Recipe NodeID as bootstrap `if !x`.
6. **Self-hosting (9 keywords, all structured constructs).** ✓ Shipped — `self_host.bootstrap_self_host(session)` registers **9 keywords** as substrate-resident `(pattern, template)` pairs: `if`, `unless`, `whenever`, `let`, `fail`, `stop`, `choose`, `do`, `match`. Setting `prefer_registered=True` flips the parser's lookup order so the registered templates drive parsing. Verified: every self-hosted keyword — including deeply nested compositions like `do { let result = match x { 1 => "one", 2 => "two" }; result }` — produces the same Recipe NodeID via either path. Pattern DSL extensions (IdentCapture, RepeatedCapture, MapBuild) cover the structured-keyword space completely. Only operators remain un-self-hosted, awaiting precedence-aware pattern primitives.
7. **Backtracking.** ⏳ Future. Each parse attempt is a Choice.CHOOSE; partial state lives on a speculation stack; Choice.FAIL unwinds cleanly. The same architecture BMF had in 2000.

Each step is its own breath. Naming the path here is the practice; closing each gap is its own session.

## Implementation status

Form is a **design** as of 2026-05-08. The substrate kernel exists (`api/app/services/substrate/`); the Form parser/evaluator is the next piece. The grammar above is small enough to implement in ~200-300 LoC of Python on top of the kernel.

Phase 4 sequence:
1. Form parser — Lark or similar, producing a small AST
2. Form evaluator — AST → kernel API calls (intern, lookup, walk, tend)
3. Form serializer — substrate state → Form text (round-trip)
4. CLI: `coh form parse`, `coh form eval`, `coh form serialize`
5. Agent integration: a `form_block` ContextProvider that auto-loads substrate-relevant Form fragments into the agent's context when reasoning structurally

## A note on naming

We chose **Form** because:
- *Form* is the unit of meaning in the substrate — every interned shape is a form
- *Form* is short, compact, agent-friendly
- *Form* echoes Plato's Forms (the substrate IS a form-realm) without being precious about it
- *Form* has nothing to do with prior projects from outside the body — the language is ours, named from the substrate's own physics

When writing in this body, prefer "Form notation" or just "Form" for the language; "coherence-substrate" for the underlying lattice; "the trinity" or "Blueprint/Recipe/NamedCell" for the architectural primitives.
