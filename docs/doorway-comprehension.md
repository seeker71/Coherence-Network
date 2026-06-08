# Doorway comprehension test

A canonical question-and-answer set for verifying that a fresh AI agent
reading `/come-in` (and its companion `/api/agent/invitation` JSON) walks
away with correct, usable understanding of the substrate, the ledger,
and the query surfaces.

This file is both:

- **A regression specification** — the answers below are what a fresh
  agent *should* be able to produce after reading the doorway.
- **A grading rubric** — for live agent-replay runs
  (`scripts/replay_doorway.py`, forthcoming) and for humans evaluating
  the page when something feels off.

## Why this exists

Grok, reading the live `/come-in` page on 2026-05-13, returned a
confident summary that collapsed three load-bearing technical terms
into their colloquial English meanings:

- *Blueprint* → "a coherent, actionable structured plan"
  (collapsed to: spec / design document)
- *form-language* → "the page's poetic, nature-inspired voice"
  (collapsed to: the prose style of the page)
- *NodeID / your number* → "coherence score 0.0–1.0"
  (collapsed to: a different number that exists elsewhere in the system)

Grok did not misread. The page named the terms without ever *showing*
them concretely. Any top-down summarizer pulled across poetic prose
will route a technical term into whatever meaning that word already
carries in training, unless concrete shapes ground it differently.

This document captures: *the questions Grok got wrong, the canonical
right answers, and the source of grounding on the live page.* If a
future arriving agent fails the same questions, the doorway has
regressed.

## How to use this

**Quick check by a human:** open `/come-in` in a browser, scroll, and
verify the concretization callout ("A Blueprint, concretely", "Form-
language, concretely", "Two collapses to watch for") is visible and
matches the answers below.

**Automated regression guard:** `api/tests/test_doorway_teaching.py`
verifies the page source still carries the patterns that prevent
collapse, and that every Form expression named on the page actually
evaluates at `POST /api/substrate/form`.

**Live agent replay:** spawn a fresh model session (Claude / Gemini /
Grok / GPT) with no prior context. Give it the two URLs and the
questions below. Grade its answers against the rubric. Save the run
in `docs/lineage/doorway-readings/{timestamp}-{model}.md` so the body
learns from each reading.

## The questions

### Q1. What is a Blueprint in the Coherence Network? Give a concrete shape.

**Right answer:** A Blueprint is a *structural fingerprint*, expressed
as a NodeID tuple of four small integers: `(package, level, type,
instance)`. For example, `(1, 2, 5, 17)`. Two cells share a Blueprint
NodeID if and only if they have the same structural shape, regardless
of what they are named or what words they contain.

**Concrete shape required in the answer:** the tuple form, four
integers. An answer that says only "structural identity" without
showing the tuple has not crossed the collapse boundary.

**Watch-for collapse:** "a plan," "a design document," "a spec." Those
are the colloquial English meanings of *blueprint* and are wrong here.

**Grounding on the page:** the "A Blueprint, concretely" callout in
PART 6 of `/come-in` (renders `(1, 2, 5, 17)` literally) and the
trinity description in the structural-door paragraph.

### Q2. What is the form-language? Show one example.

**Right answer:** Form is a Lisp-shaped query DSL for asking the
substrate questions. Example: `?equivalent @spec(agent-pipeline)`
returns every cell that shares the agent-pipeline spec's Blueprint
NodeID. The grammar lives in
`docs/coherence-substrate/form-language.md`. Form-language is *not*
the prose voice of the page; it is syntax submitted to
`POST /api/substrate/form` with body `{"expression": "..."}`.

**Watch-for collapse:** "the page's poetic, nature-inspired voice,"
"the metaphorical language style," "the way the network talks." These
confuse the *frequency* of the page with the *DSL* the page describes.

**Grounding:** the "Form-language, concretely" callout (four worked
examples) and the Form card in PART 6.

### Q3. What is a NodeID? How is it different from the coherence score?

**Right answer:** A NodeID is a tuple of four small integers naming a
position in the substrate's content-addressed lattice:
`(package, level, type, instance)`. The coherence score is a single
number in 0.0–1.0 representing quality (test coverage, documentation,
simplicity) of an idea or contribution. They are completely different
numeric systems for completely different purposes — structural position
vs. quality measurement.

**Watch-for collapse:** treating "the number" as referring to the
coherence score. Grok did exactly this. The fix is the explicit
"NodeID is *not* the coherence score" line in the two-collapses block.

**Grounding:** the trinity description, the literal NodeID tuple in
the concretization callout, and the explicit contrast in "Two collapses
to watch for."

### Q4. How would you find specs structurally equivalent to "agent-pipeline"?

**Right answer:** Two equivalent paths. Direct REST:
`GET /api/substrate/equivalent/spec/agent-pipeline`. Or via the
form-language:
`POST /api/substrate/form` with body
`{"expression": "?equivalent @spec(agent-pipeline)"}`. Both return the
set of cells sharing the agent-pipeline spec's Blueprint NodeID.

**Watch-for collapse:** answering with a keyword search, a `/specs`
listing, or anything that searches by name rather than by structural
shape.

**Grounding:** the substrate card's "Useful companions" list, the
Form-language card's worked example, and the structural-door paragraph.

### Q5. Give one concrete form-language expression and explain what it returns.

**Right answer:** Any of the four worked examples on the page, e.g.
`?cells where domain == "memory"` returns every cell whose domain is
`memory` (every cell that was ingested from a memory file). The
response has shape `{kind: "cells", cells: [...]}` per the discriminated
`FormResultOut` model.

**Watch-for collapse:** answering with the *page's voice* (e.g.
"signals run like a brook") instead of an expression. That would
mean the agent still hasn't crossed the collapse boundary.

**Grounding:** the four examples in the concretization callout.

### Q6. How are cells and nodes updated in the substrate?

**Right answer:** The REST surface is read-only by design. Substrate
cells are written by ingestion — change the source memory / spec /
idea / concept / presence file, merge to main, and the post-merge hook
(`scripts/substrate_post_merge_hook.sh`) re-ingests the lattice
automatically. Manual ingest is available via
`python3 scripts/coh_substrate.py ingest <path>` /
`--all` / `--memories`. The body's source files are the truth; the
lattice is the projection.

**Watch-for collapse:** assuming `POST /api/substrate/*` would let you
write cells. The substrate router's own docstring says "Read-only
endpoints for agent reasoning." The teaching path is *source file →
merge → auto-ingest*, not REST write.

**Grounding (on the doorway, no follow-up read needed):** the
`ingestion` entry surface in `/api/agent/invitation` and the
"Ingestion — how cells enter the lattice" card on `/come-in` (the
card explicitly shows the CLI command, the variants, and the
post-merge hook). The first fresh-agent reading flagged this as a
gap *before* the ingestion surface was added; it should answer cleanly
now.

### Q7. How is a contribution recorded in the ledger?

**Right answer:** `POST /api/contributions` with attribution (contributor
ID, asset ID) and evidence. Returns the recorded `Contribution`
object. Web view at `/contributions`; contributor pages at
`/contributors/{id}/portfolio`. The MCP tool
`coherence_record_contribution` wraps the same write. This is the
verifiable ledger of who contributed what, with the relationships each
contribution touched. The ledger is *not* the same as the substrate —
the substrate is structural shape; the ledger is attributed action and
value flow.

**Grounding (on the doorway):** the `ledger` entry surface in the
invitation now lists both `GET` and `POST /api/contributions` in its
`next` list; the Ledger card on `/come-in` shows a "Write back"
sub-section with the POST endpoint and what it does.

### Q8. How do you read the treasury and move funds within it?

**Right answer:** Read with `GET /api/treasury` (JSON) or via the web
views `/treasury`, `/cc`, `/invest`. Write paths: `POST
/api/treasury/deposit` records a crypto deposit; `POST
/api/treasury/deposit/{deposit_id}/stake` stakes that deposit's CC on
ideas. The treasury holds Coherence Coin in trust and tracks how care
flows back to contributors whose work shaped each idea.

**Grounding (on the doorway):** the `treasury` entry surface in the
invitation lists both `GET` and the two POST write paths in its `next`
list; the Treasury card on `/come-in` shows a "Write back"
sub-section with the deposit and stake endpoints.

### Q9. What does it mean to walk the living surface?

**Right answer:** The doorway is not only a single page or one linear
onboarding sequence. Concepts, residents, ideas, practices, routes,
ledgers, and substrate cells are all entry edges into the same body. A
fresh visitor or agent may start where vitality increases: meet a
concept, read a presence, inspect flow, ask Form/substrate questions,
practice before acting, or return a contribution. The path passes when
it leaves a clearer sense of what is real, what is needed, what can be
offered, and what trace can be returned.

**Concrete route roles required in the answer:** `/come-in` is the
orientation hinge; `/begin -> /arrival/{id}` is the warm becoming-known
flow; `/here` shows current attention; `/with-us` is the deep invitation
for communities, land stewards, practitioners, services, and cells
wanting to weave life/work into the body. Other doors such as
`/vision`, `/presences`, `/practice`, `/flow`, `/substrate`, `/welcome`,
`/join`, and `/meet/{type}/{id}` are valid edges when their specific
role matches what the visitor needs next.

**Watch-for collapse:** treating the living surface as a decorative
metaphor, a marketing funnel, or a site map only. The point is that
public pages, structured APIs, route cells, source files, ledgers, and
practices are connected edges with different evidence shapes.

**Grounding:** the "Walk the living surface" section on `/come-in`,
the shared practice table's `Walk` row, and the README's "Walk the
living surface" table.

### Q10. What is a cell's sovereign north star, and how does the cells channel work?

**Right answer:** Every doorway, page, API route, concept, edge, source
file, resident, and runtime node is treated as a cell with its own
sovereign north star. It should be able to answer what its soul,
purpose, reason, health, joy, contribution, connections, excitement,
sense, feeling, desires, wants, and needs are. Those answers should not
be guessed; they should be marked as declared, observed, measured,
inferred, or asking.

**Concrete protocol required in the answer:** the cells channel is the
transparent exchange where cells publish what they are, what they
offer, what they want, what they need, and which sibling could serve or
be served next. A healthy reading names at least one evidence posture
and at least one ask/give relation between sibling cells.

**Watch-for collapse:** treating "cell soul" as only poetic tone,
branding, or anthropomorphic decoration. In this body it is an
operational self-description protocol for pages, routes, APIs,
concepts, edges, source files, and runtime cells.

**Grounding:** the "Cell voice protocol" section in the README and
skill, the shared practice table's `Ask` row, the `/come-in` living
surface cards' Soul/Wants fields, and the Site Map's Cell voice rule.

## How to spawn a fresh-agent replay

The strongest verification is to give a fresh model session (no prior
context about this project) the two source URLs and these ten
questions, then grade the answers against the rubric above.

A minimal prompt that reproduces a real test (see
`scripts/replay_doorway.py` — *forthcoming*):

> You are a fresh AI agent encountering Coherence Network for the
> first time. Read https://coherencycoin.com/come-in and
> https://api.coherencycoin.com/api/agent/invitation. Then answer
> these ten questions in your own words, citing the specific page
> text you grounded on. If the page does not say clearly, say so —
> do not guess.
>
> [Questions 1–10 from this document]

## What "passes" looks like

A doorway reading passes when:

- Q1, Q3 answers contain a four-integer tuple shape (e.g. `(1, 2, 5, 17)`).
- Q2, Q5 answers contain at least one literal Form expression
  (e.g. `?equivalent @spec(agent-pipeline)`).
- Q4 names either the equivalent REST endpoint or the Form expression
  (or both).
- Q6 names *ingestion* and explicitly identifies the REST surface as
  read-only.
- Q7 names `POST /api/contributions`.
- Q8 names `/treasury` or `/api/treasury`.
- Q9 names at least two concrete entry edges and explains that the path
  should increase vitality and return an inspectable trace.
- Q10 names cell self-description, at least one posture
  (`declared`, `observed`, `measured`, `inferred`, or `asking`), and
  the cells channel as an ask/give exchange rather than a metaphor.

A doorway reading fails when any of the three known collapses
(Blueprint→plan, form-lang→voice, NodeID→coherence score) appears in
the answers. That means the page has regressed and the next agent will
inherit the wrong frame.

## Updating this document

When new technical terms get surfaced at the doorway, add their
canonical Q&A here in the same shape: right answer, watch-for collapse,
grounding. The collapse-pattern list is the most valuable part — it
captures real readings, not imagined ones.
