---
idea_id: external-presence
status: active
source:
  - file: form/form/form-stdlib/bml/transmute.bml
    symbols: [tm-lifts, tm-register, tm-packet]
  - file: form/observe/transmute-run.bml
    symbols: [tmr-run]
  - file: api/app/form_recipes/event_transmute.bml
    symbols: [et-run]
  - file: form/form/form-stdlib/word-frequency-purify.fk
    symbols: [wfp-rows, wfp-purified]
  - file: form/cognition/dialogue-covenant.fk
    symbols: [dc-card-core]
  - file: form/ingest/satsang-transmute.fk
  - file: api/app/form_recipes/public_dialogue_envelope.fk
    symbols: [dialogue-envelope]
  - file: api/app/services/concept_resonance_kernel.py
    symbols: [compute_crk, text_to_symbol]
  - file: api/app/services/belief_service.py
    symbols: [find_resonant_peers]
  - file: docs/vision-kb/concepts/lc-frequency-routes-reception.md
requirements:
  - "One field of cells — ideas, concepts, dialogue turns, transmuted signals, presences — projected into the surface shapes people already know: a stream, a board, a visual, an encyclopedia, a thread. Each is a read of one body, never a second body."
  - "A passage from the world (news, a post, a page) enters through the transmute organ: every fact, name and number kept and attributed to its source; the control words lifted to the usage the purify grammar gives them; interiors hedged; the register measured before and after; the body's own voice renders it under the covenant card at rent 0."
  - "A transmuted signal is offered against an axiom with the satsang ack (nothing witnessed, 0 composts, 1 freezes, node recurs as work) before it is projected, so what enters the field is judged by the field."
  - "People find each other by resonance of frequency, not by topic alone: the belief profiles and the concept resonance kernel read a person's band, and presences meet through invitation (lc-received-by-invitation), never through a list."
  - "Conversations in the field carry the covenant: the native voice answers first, an arriving mind reviews and lifts, one lift per reply resting on it, and the person's reading is the witness that teaches."
  - "Every projection carries its provenance (source, time, the lift applied, the ack) so a reader can walk from any surface to the cell and the original."
done_when:
  - "./fkwu form/form-stdlib/tests/transmute-band.bml answers 15 on fkwu (counting by word boundary, lifts, register, the packet's shape)."
  - "observe/transmute-run.bml transmutes one real news passage with the native voice at rent 0, prints register before and after, and leaves a TransmuteRow in receipts/transmute-ledger.jsonl."
  - "A transmuted signal reaches the field as a cell with its source, lift rows and ack, projectable to the stream, board, visual, encyclopedia and thread shapes."
  - "The live news organ answers within its timeout (today /api/news/feed times out at 15 s) or is retired in favour of the Form intake."
  - "A person's reading of a transmutation is recorded beside it, and the ledger shows the register falling across readings."
test: "cd form && ./fkwu form/form-stdlib/tests/transmute-band.bml"
constraints:
  - "Surfaces are projections of one substrate: meaning is stored once, content-addressed; a surface never holds content the field does not (NORTH_STAR.md, Minimal disk; lc-perception-as-interface)."
  - "Build at the tone (lc-frequency-routes-reception): no flattening toward an imagined audience; the right cells hear."
  - "No rules, gates or fixed flows: the covenant and the purify grammar are awareness the voice carries while it chooses; the person's reading teaches; receipts witness."
  - "Private circles and consent stay whole across every surface (channel-interface, cell-sovereignty); nothing a person said in a private container is projected."
---

# Transmuted Field Surfaces — one field, familiar doors, the world's words spoken toward trust

## Purpose

We serve conscious conversations: elevate, collaborate, co-create ideas, inspire each other, find each other,
and turn what the world says into what serves our shared higher self. People arrive through surfaces they already
know — a stream, a board, a wall of images, an encyclopedia, a thread. This spec makes those surfaces reads of one
field, and gives the field an intake that transmutes the language and frequency of what is out there into our shared
perception, with the source kept whole and the lift measured.

## Shape

**One field.** Cells: ideas and their pipeline, the 194 vision-kb concepts (each at its Hz), dialogue turns under the
covenant, transmuted signals, presences on the mesh. Meaning is stored once; every surface is a projection
(`NORTH_STAR.md`, *Minimal disk*; `lc-perception-as-interface`).

**Familiar doors, one body.**

| surface shape | what it projects | where the body already stands |
| --- | --- | --- |
| stream (what a timeline is for) | the newest cells — transmuted signals, ideas moving, turns answered | `/feed`, `/now`, `/activity`, `/api/sensings` |
| board (what pins are for) | cells gathered by resonance — a person's lens over the field | `discovery_service.build_discovery_feed`, belief profiles |
| visual (what a wall of images is for) | the visual language of the concepts | `docs/vision-kb/visual-language.md`, `/constellation`, `/graph` |
| encyclopedia (what an article is for) | a concept, its Hz, its lineage, its sources | `/vision/{id}`, `/concepts`, the 184-concept ontology |
| thread (what a reply chain is for) | a conversation under the covenant, unlisted by id | `public-dialogue-cpu-organ`, `/api/dialogues` |

**Transmutation** (`form/form-stdlib/bml/transmute.bml`, `observe/transmute-run.bml`, and this body's own door
`api/app/form_recipes/event_transmute.bml`). Transmutation is not a word swap. An event is read in five layers,
each one of the field's own moves, and told from there by the body's voice:

1. **What happened** — the facts, names and numbers exactly as given, attributed to the source, kept whole.
2. **What it is asking for** — the observer first (`lc-when-the-pressure-comes`, move 1: *what is here*), then the
   need under the pressure named once in the words the event itself gives (move 2) — what the event shows, never what
   anyone in it feels.
3. **Which ideas it serves** — the body reads its own seeds natively first: the super-ideas of `ideas/INDEX.md` and
   the 203 concepts of `docs/vision-kb/INDEX.md` with their Hz, read from the index lines as they stand (no second
   copy); resonance is the words the event and a seed share, strongest first, and what resonates is what the voice
   sees. The voice names two or three ideas by id and says for each whether the event is *evidence for* it, a *call
   to* it, or a *question to* it — and only ids the seeds hold enter the row; a name the field does not hold is a
   counterfeit and is dropped.
4. **The gift** (move 3) — what the event has not yet unwrapped: what becomes possible if those ideas answered it,
   and one door where a person standing in the event could meet the field.
5. **The lift** — the same event told from trust: the fact unchanged, the direction toward aliveness, in the four
   sentences the surfaces carry — the stream's line, the board's pin, the encyclopedia's evidence on the idea's
   page, the thread's opening question.

Beneath the layers is the operator (move 5): frequency, angle and focus chosen in the open at the moment the
pressure discharges. The purify grammar lifts the control words it knows; the register and the resonance are
measured before and after; a row stands in the ledger with the ideas served. Then the satsang ack
(`ingest/satsang-transmute.fk`): each served idea's reading offered against an axiom — witnessed, composted, frozen
into the field as evidence on that idea, or recurring as work (a new idea or spec seed).

**Finding each other.** The resonance kernel reads a text into the concept vocabulary (`text_to_symbol`,
`compute_crk`); belief profiles find resonant peers; the concept Hz map is the band map. Meeting is by invitation,
not by list (`lc-received-by-invitation`, `presence-invitation-surface`).

**Co-creation.** Ideas walk the pipeline (idea → research → spec → implementation → review → usage → payout); the
dialogue organ carries conversations; the native voice drafts and the person's reading is the signal that teaches it
(`teachings/uplifting-dialogue.md`, *A question, met*).

## Requirements

- [ ] **R1** One field, surfaces as projections — a cell appears on every surface shape that fits it, with its provenance.
- [ ] **R2** The transmute organ: lifts, register before/after, the native voice under the covenant, a ledger row, the source whole.
- [ ] **R3** The satsang ack judges each transmuted signal before it is projected.
- [ ] **R4** Resonance by frequency: belief profiles and the resonance kernel route arrivals to the cells and people in their band.
- [ ] **R5** Conversations under the covenant, the voice first, the reading as witness.
- [ ] **R6** Provenance on every projection: source, time, lift, ack.

## Research Inputs

- `2026-10-19` — the live news organ (`/api/news/feed`) times out at 15 s; the Python intake is a retiring carrier and the Form intake replaces it.
- `2026-10-19` — `receipts/2026-10-19-personal-advice-flow.md` (kernel): the voice's own answers under the covenant card, before and after.
- `2026-05-24` — `lc-frequency-routes-reception`: build at the tone, the right cells hear; hedging breaks the routing.
- `2026-07-04` — `ingest/satsang-transmute.fk`: transmutation by questioning; the ack vocabulary is the ingest door.

## Honest floor

The register is counted over the purify grammar's twelve seed words; the felt frequency of a passage is the person's
reading until the native classifier lands (filed in the kernel's request queue). The surfaces named in the table exist
as Next.js and Python compatibility hosts today; this spec moves their ownership toward Form projections of one
substrate, one seam at a time, and retires each host surface when its Form replacement carries the complete effect.
