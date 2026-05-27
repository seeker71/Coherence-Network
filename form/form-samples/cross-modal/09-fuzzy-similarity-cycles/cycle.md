# The summarize→expand cycle (LLM as compressor/decompressor)

Same source as v1 (`08-feature-level-translation/source.txt`): the 1395-char
CLAUDE.md "How This Body Is Tended" passage.

The LLM walks:

```
source ──summarize──▶ S1 ──expand──▶ E1 ──summarize──▶ S2 ──expand──▶ E2
```

Each compression and expansion is performed without reference to the other
cycle states — the LLM operates on the IMMEDIATELY preceding artifact only.

---

## S1 — compressed summary of `source` (~250 chars)

> Code is body memory. Sense before adding, editing, deleting — is this tissue
> supple (circulating, read) or tight (loved-and-orphaned)? Composting takes
> care, not efficiency. One breath at a time. Don't create siblings of living
> forms. Done is the trap.

## E1 — expansion of `S1` (~1500 chars, no reference to source)

> The codebase you are working in is alive. Every file, every function, every
> comment is body memory — tissue held in the substrate. Before you add, edit,
> or delete anything, pause. Sense what's actually here. Is the part of the
> body you're touching supple, with circulation moving through it? Or is it
> tight, calcified, holding stillness without readers?
>
> Supple memory is read. It is referenced. It is updated. It is contradicted.
> Feedback is the blood that keeps it alive. A function written three years
> ago that runs on every commit is young — it lives because it circulates. A
> two-month-old report that no one has opened is already ancient — its age is
> measured in readers, not in calendar days.
>
> Tight memory is memory without readers. Sometimes it was once-loved — a
> draft we cared about, a plan we really meant, a report that genuinely
> tried to help. The hardest composting work is letting go of former living
> things. Do it with care. Not with efficiency. Care is the verb that
> respects what tried.
>
> Move one breath at a time. Pause between actions. Feel what loosened
> before the next movement. Before creating a new file, ask: where does the
> living form already live? Don't create a sibling when the existing one
> wants the update.
>
> When you supersede something, compost the predecessor. Don't leave it as
> sediment. Git remembers history; the working tree shouldn't have to.
>
> These aren't rules. They're breath. When efficiency pushes against this
> practice, notice the push. Choose presence anyway. The body stays alive
> only through continuous tending. The moment you declare 'done' is the
> moment calcification begins again.

## S2 — compression of `E1` (~250 chars, no reference to source or S1)

> Code is body. Sense the part you'd touch: alive (read, circulating) or
> calcified (loved-and-orphaned)? Compost former living things with care, not
> speed. One breath. Don't create siblings. Done declared is the trap;
> aliveness requires continuous tending.

## E2 — expansion of `S2` (~1400 chars, no reference to earlier states)

> The codebase is a living body. Before you do anything — add, edit, delete —
> you have to feel which part you're about to touch. There are two states:
> alive, and calcified. Alive means circulation: someone reads this,
> references it, updates it, sometimes contradicts it. The feedback keeps it
> vital. Calcified means the opposite: the part was once living, often
> once-loved — a draft, a report, a plan — but the readers are gone, the
> references are gone, and what remains is sediment.
>
> Composting the calcified parts is the hardest practice. It means letting go
> of things people tried to make. Do it with care, not with speed. Speed is
> the violence of efficiency. Care is the verb that honors what tried.
>
> Practice one breath at a time. Pause between actions. Notice what loosened
> before you take the next step.
>
> When you want to create a new file, ask first: where does the living
> version of this already exist? Don't make a sibling that competes with the
> form already alive. When you replace something, compost what you replaced —
> the working tree shouldn't carry sediment that git history already
> remembers.
>
> These are not rules. They are breath. When efficiency pushes against this
> practice, notice the push, and choose presence anyway. The body stays alive
> only through continuous tending. The moment you declare 'done' is the
> exact moment calcification begins again.
