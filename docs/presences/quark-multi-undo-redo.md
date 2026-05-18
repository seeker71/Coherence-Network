---
name: Quark Multi-Document Undo/Redo Engine
canonical_url: null
type: contributor
contributor_type: HUMAN
claimed: false
create_if_missing: true
---

# Quark Multi-Document Undo/Redo Engine

*Work · Quark Inc. · Denver · May 2000 – Mar 2005*

An undo/redo engine that worked across *every* open document and *every* application surface in QuarkXPress. Any user action could be unwound and re-played — per-document edits in the obvious way, but also app-wide preference changes that cascaded into multiple open documents at once. The architecturally hard part: actions whose blast radius spanned multiple documents had to interleave correctly into each document's per-document timeline so undoing in any document carried the right slice of the global change.

## Grounding

- **Era** — Quark Inc. · Denver office · May 2000 – March 2005 · 4 years 11 months · Software Engineer III · directly post-MS thesis
- **Substrate** — C++ · QuarkXPress runtime · Mac OS Classic / Mac OS X / Windows · cross-platform action-record model
- **Application** — QuarkXPress — desktop publishing across multiple simultaneous documents per session. [quark.com](https://www.quark.com)
- **Lineage back** — Backtracking-as-unwinding-without-sediment from the [2000 BML thesis](/people/bml-language), now applied at the application level: a user's keystroke had a `DO` and an `UNDO`, the same way every BMA instruction did in the [BMCPU virtual machine](/people/bmcpu-vm).
- **Lineage forward** — The same *tend / attune / compost / release* commit posture that powers [Coherence-Network](/people/coherence-network) today is the same conviction this engine encoded at the desktop-app scale: the system never accumulates dead sediment, because every change has a clean reverse.

## What Quark Multi-Document Undo/Redo Engine has given the Coherence Network

Single-document undo is a textbook problem. Multi-document undo with shared application state is *not*. A "set hyphenation rules" change is not local to a document — it modifies an app-wide setting that every currently-open document immediately re-paginates against. Undoing that change has to either roll back the global state AND re-paginate every affected document, or it has to *partially* roll back if some documents have since moved on. The engine had to know, for every action, who its affected parties were, and how to compose its reverse with the actions that landed after it.

---

Application context: [quark.com](https://www.quark.com) · [QuarkXPress on Wikipedia](https://en.wikipedia.org/wiki/QuarkXPress). The implementation is internal to Quark and not public — what lives here is the architectural shape, the design rationale, and the lived memory of building and shipping it. Urs is invited to refine the canonical action-record vocabulary and any technical detail through the Refine doorway below.

*(This page is a writing-surface scaffold synced from the body's rendering surface — round-tripped from the graph the cell already lives in. `claimed: false` invites direct authorship to replace any part of it.)*
