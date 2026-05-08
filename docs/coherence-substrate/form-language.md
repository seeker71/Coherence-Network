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
