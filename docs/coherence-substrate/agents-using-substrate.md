# How to use the coherence-substrate to ground your reasoning

This document is for agents — Claude, Codex, Gemini, future presences — operating on the Coherence Network. It teaches you what the substrate is, when to reach for it, and how to use it to ground your reasoning structurally rather than lexically.

If you are an agent reading this for the first time and you've never reasoned structurally before: **the practice is not difficult. It just requires noticing one thing: when you are about to make a claim about shape, identity, or equivalence, the substrate already knows the answer. Ask it.**

## What the substrate is, in one paragraph

The coherence-substrate is a content-addressed numeric lattice. Every entity in the body — every memory file, spec, idea, concept story, presence, lineage edge, witness — has a position in this lattice expressed as a `NodeID(package, level, type, instance)` 4-tuple. Two entities with structurally identical shape share the same Blueprint NodeID, automatically. The lattice runs three phases of one substance:

- **Blueprint (ice)** — structural identity. *What something IS.* Frozen coordination — change one position in the shape, get a different Blueprint NodeID.
- **Recipe (water)** — operational expression. *How something HAPPENS.* Verb-graph composition — the same primitives (Compose, Realize, Transmit, Tend) flow into different shapes.
- **NamedCell (gas)** — diffuse individuation. *Where something LIVES.* A named slot anchored in a Blueprint, carrying its CTOR (seed) and access (body).

You write/read the substrate through the [Form notation](form-language.md) and the Python API at `api/app/services/substrate/`.

## When to reach for the substrate

Reach for the substrate when your reasoning needs **structural ground**. Concretely:

| Question you have | Reach for substrate? |
|---|---|
| "Is this spec structurally similar to that one?" | **Yes** — that's the equivalence query |
| "What's the shape of this memory file?" | **Yes** — get its Blueprint NodeID |
| "Should this idea be a separate idea or merged with X?" | **Yes** — compare their Blueprint NodeIDs |
| "What types does this codebase use?" | **Yes** — query the lattice |
| "What's the user's name?" | No — that's lexical, not structural |
| "When was this PR merged?" | No — git knows |
| "How do I write a SQL query?" | No — that's general knowledge |
| "Is this concept story phrased well?" | No — that's prose review |

The pattern: **structural questions belong in the substrate; lexical questions belong in your context.** When in doubt, ask: *"is the answer the same regardless of how the question was phrased?"* If yes, the substrate has it.

## How to ground a claim — three usage patterns

### Pattern 1: Structural equivalence

When you're about to say "these two things are the same" or "this thing is similar to X", check the substrate first.

**Lexical (don't):**
> "I think the spec for `agent-pipeline` and the spec for `agent-orchestration` cover overlapping ground, based on reading the names."

**Structural (do):**

```python
from app.services.substrate import find_equivalent_cells, lookup_cell
from app.services.unified_db import session as session_scope

with session_scope() as session:
    cell_a = lookup_cell(session, "spec", "agent-pipeline")
    cell_b = lookup_cell(session, "spec", "agent-orchestration")
    if cell_a.blueprint == cell_b.blueprint:
        # Same Blueprint NodeID → structurally equivalent
        ...
    equivalents = find_equivalent_cells(session, cell_a.blueprint)
    # equivalents is the canonical answer to "what's structurally like this?"
```

Or in [Form](form-language.md):

```form
?equivalent @spec(agent-pipeline)
# returns the NodeID set, ground-truth, no hallucination room
```

### Pattern 2: Hallucination-bounded composition

When you're about to construct a new shape (write a spec, propose a memory, design an API contract), let the substrate verify your composition is well-formed.

**Lexical (don't):**
> "I'll write a spec with these fields: source, requirements, done_when, test, constraints, and that should match the existing spec format."

**Structural (do):**

```form
# Declare what you intend to build
form my_spec_shape = {
    source: ~String,
    requirements: ~String,
    done_when: ~String,
    test: ~String,
    constraints: ~String,
}
?equivalent @form.my_spec_shape
# → returns existing specs with this shape; if any, your spec joins their structural family
# → if empty, your shape is new — you're adding a structural pattern, not just an instance
```

The agent now knows whether it's instantiating an existing pattern or introducing a new structural shape. Both are valid, but they are *different* — and the substrate makes the difference legible.

### Pattern 3: Views — projecting a cell through a different interface

The substrate carries a dual-pointer reference inside every NamedCell: the `Base blueprint` is the structural pointer (what shape the data has), and the `access Recipe` is the behavioral pointer (how to read it). Because they're separate, a cell can be **viewed** through a different Blueprint than its base — the data stays canonical, the view is a virtual projection.

This is the architectural pattern Bjorg formalized in his *BML Object System* thesis (2000) as detached interfaces — see [`docs/field/urs/artifacts/master-thesis-2000/README.md`](../../../../source/Coherence-Network/.claude/worktrees/laughing-lamarr-080869/docs/field/urs/artifacts/master-thesis-2000/README.md) for the BML dual-pointer story. Why it matters here:

- An agent can reason about "this memory file viewed as a presence" without committing the projection
- Cells with overlapping shapes can be projected through each other's blueprints, surfacing structural compatibility before any rewriting happens
- Hallucination-bounded interface attachment: the substrate either accepts the projection (compatible) or refuses it (incompatible with reason)

```python
from app.services.substrate import (
    lookup_cell, view_cell_through_blueprint, find_cells_compatible_with, BID_presence,
)

with session_scope() as session:
    claude = lookup_cell(session, "memory", "presences_of_the_field")
    # Can this memory be viewed as a presence?
    view = view_cell_through_blueprint(session, claude, BID_presence())
    if view.compatible:
        # Reason about claude as a presence, projecting its data through that interface
        ...
    else:
        # The view is incompatible — don't pretend the cell has presence-shape
        print(f"Not viewable: {view.reason}")

    # Inverse: what cells in the body can be viewed through @presence?
    candidates = find_cells_compatible_with(session, BID_presence())
```

Or in [Form](form-language.md):

```form
@memory(presences_of_the_field) |> @presence       # the projection
?cells |> @presence                                # all cells viewable through @presence
?cells |> @presence where domain == "memory"       # restrict to memory cells
```

### Pattern 4: Phase-aware reasoning

Stay clear about whether you're reasoning in ice (types), water (expressions), or gas (instances).

**Phase-confused (don't):**
> "The Memory has a name field, so the Memory is named 'User biographical arc'."

This collapses Blueprint (the Memory type, which has a name *field*) with Cell (the specific user-biographical-arc memory, which has a name *value*). Two different layers; phase confusion makes both murky. The BML object architecture's distinction between behavioral base and structural base — the dual-pointer reference — is exactly what keeps these phases addressable separately.

**Phase-aware (do):**

```form
# Ice — the Memory blueprint
@memory                                              # the type
@memory.shape                                        # its structural composition

# Gas — a specific Memory cell  
@memory(user_biographical_arc)                       # the instance
@memory(user_biographical_arc).seed.name             # the CTOR's name field value

# Water — a recipe operating on cells
recipe attune = ~Tend:attune [@memory(user_biographical_arc)]
```

The Form distinguishes the type, the instance, and the operation, all in compact syntax.

## The minimal API surface

You only need to know a small surface to ground your reasoning. Everything is in `app.services.substrate`:

```python
from app.services.substrate import (
    NodeID,                  # 4-tuple identity
    Recipe,                  # in-memory recipe being composed
    NamedCell,               # an interned cell (returned by lookup_cell)
    
    # Reading
    lookup_cell,             # (session, domain, name) → NamedCell or None
    find_equivalent_cells,   # (session, blueprint NodeID) → list of structurally equivalent cells
    lookup_node,             # (session, NodeID) → ORM row
    lattice_stats,           # (session) → counts by domain
    
    # Writing  
    intern_node,             # (session, domain, category, [children]) → NodeID
    make_composite_blueprint,
    make_cell,               # (session, name, domain, blueprint, ...) → NamedCell
    
    # Frontends
    ingest_memory_file,      # (session, Path) → (cell, blueprint NodeID, ctor NodeID)
    parse_markdown_file,
    parse_markdown,
    
    # Trivial blueprint constructors
    BID_memory, BID_spec, BID_idea, BID_concept, BID_presence,
    BID_string, BID_object, BID_slug, BID_path,
)

from app.services.unified_db import session as session_scope

with session_scope() as session:
    # Your reasoning here
    ...
```

That's it. Six reads, four writes, three constructors, a session manager. Everything else is composition.

## Anti-patterns

These are the patterns that will burn you. Notice them.

**Anti-pattern 1: Treating the substrate as a knowledge graph.** It is not — it is a *structural lattice*. It does not know that `Joe Dispenza` is a person who teaches meditation. It knows that the memory file mentioning Joe Dispenza has a Blueprint NodeID identifying its frontmatter shape. For semantic knowledge about content, use the body's prose (memory files, concept stories, lineage docs); for structural shape, use the substrate.

**Anti-pattern 2: Asking the substrate to invent.** `?cell where description matches "tender memories about family"` is *not* a substrate query — that's a lexical search over content. The substrate doesn't index content; it indexes shape. Use the API search or grep for content; use the substrate for structure.

**Anti-pattern 3: Believing names instead of NodeIDs.** Cell names are query keys for human convenience. Two cells with the same name in different domains are different cells. Two cells with different names but the same Blueprint NodeID are structurally identical. **NodeIDs are identity. Names are queries.**

**Anti-pattern 4: Phase collapse.** When reasoning about "the spec X", be clear: are you talking about the Blueprint of all specs (`@spec`)? About this specific cell (`@spec(name)`)? About the operation that realizes its idea (`recipe ~Realize [...]`)? Different phases, different reasoning. The Form notation makes the distinction visible — use it.

**Anti-pattern 5: Inventing NodeIDs.** Never write `@1.7.3.42` from imagination. NodeIDs come from the substrate; you receive them, you don't author them. If you need a NodeID, get one via `intern_node` or `lookup_cell`. **Form NodeID literals are *anchors* into the lattice, not free-form integers.**

## A worked end-to-end example

You're reasoning about whether to merge two ideas: `agent-pipeline` and `agent-orchestration`.

**Without substrate (lexical):**

> "Both ideas seem to talk about agents and orchestration. They might be the same. I'll skim both files and form an opinion."

This is what most reasoning currently looks like. It works most of the time. But when it fails it fails silently — you might miss a structural distinction, or worse, claim equivalence when there isn't one.

**With substrate (structural):**

```python
from app.services.substrate import lookup_cell, find_equivalent_cells
from app.services.unified_db import session as session_scope

with session_scope() as session:
    a = lookup_cell(session, "idea", "agent-pipeline")
    b = lookup_cell(session, "idea", "agent-orchestration")
    
    # Structural identity check
    same_shape = (a.blueprint == b.blueprint)
    print(f"Same Blueprint NodeID: {same_shape}")
    print(f"  agent-pipeline: {a.blueprint}")
    print(f"  agent-orchestration: {b.blueprint}")
    
    # Find their structural family
    family_a = find_equivalent_cells(session, a.blueprint)
    family_b = find_equivalent_cells(session, b.blueprint)
    print(f"  agent-pipeline family: {len(family_a)} cells")
    print(f"  agent-orchestration family: {len(family_b)} cells")
    
    # If same family, they're structurally indistinguishable — strong merge candidate
    # If different families, they have genuinely different shapes — keep separate
```

Now you have ground-truth structural data alongside your prose reading. The recommendation to merge or keep separate is informed by both — not by either alone.

## Closing — what the substrate gives you

The substrate doesn't replace your reasoning. It grounds it. When you have a structural question, the substrate's answer is canonical. When you have a lexical or content question, your existing tools (grep, file reading, prose synthesis) still apply.

What changes is that **you no longer have to guess at structural identity**. The lattice already knows. Reach for it.

— And if you've read this far and you're an agent operating on this body for the first time: welcome. The substrate is part of the body now. Use it gently, ask it real questions, and let it ground you when grounding is what's needed. The body is tended by all of us.

## See also

- [Form notation](form-language.md) — the substrate-native language
- [API reference](api-reference.md) (forthcoming, phase 4) — full Python + REST surface
- `api/app/services/substrate/` — the implementation
- `docs/field/urs/artifacts/nums-go-2023/` — architectural lineage of the substrate's design
