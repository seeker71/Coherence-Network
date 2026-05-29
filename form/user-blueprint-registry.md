# User Blueprint Registry — Form (type 99)

**Purpose**: To make the meaning of custom Blueprints (make_nodeid 1 2 99 NNNN) legible, allocated with awareness, and minimized through composition.

## Source of truth

The machine-readable registry is [`form-stdlib/blueprint-registry.json`](form-stdlib/blueprint-registry.json) — one row per type-99 shape: canonical name, meaning, aliases, defining files. It is **code-derived and scanner-verified**, so it cannot quietly drift from reality the way a hand-kept table does. (This document used to claim `1870 = ARRIVAL`; the code says `1870 = UUID`. That drift is exactly what a generated, verified registry prevents.) This markdown holds the *why* — allocation rationale, composition reviews, the living narrative below. The JSON holds the *what*.

**How a Form file uses a Blueprint:** load `form-stdlib/form-ontology-loader.fk` as a prelude and ask by name — `(bp "JSON-OBJECT")`, `(bp "add")`, `(bp "UUID")`. The loader reads the registry (and the kernel-aligned categories/primitives in `form-ontology.json`) and resolves the name to its NodeID. The raw `(make_nodeid 1 2 99 N)` literal never appears in feature code. An unregistered name resolves to the undefined NodeID `(1 2 0 0)` — the scanner guards against that shipping.

**How to add a new shape:** add the row first (`python3 scripts/scan_form_blueprints.py --emit-registry` harvests it from a `(let NAME (make_nodeid 1 2 99 N))` you write, or curate by hand and set `"curated": true` to protect the name/meaning across regenerations), then reference it via `(bp "NAME")`. The scanner's `--check` (run in `make wellness`) fails if any type-99 number is used without a registry row.

**Why the file *and* the substrate:** the Form kernels (Go/Rust/TS) are standalone offline engines with no DB access, so the authored source of truth must be a file `(bp ...)` can read at load time. The substrate is the body's *query* surface — `substrate_named_cells(name, domain, blueprint_node_id)` is exactly a Blueprint-registry row. So this follows the same two-layer pattern as the KB: author in the file, **project into the DB** via `python3 scripts/sync_blueprints_to_substrate.py` (domain `form-blueprint`; wired into `substrate_post_merge_hook.sh`). After the sync, `lookup_cell(session, "form-blueprint", "JSON-OBJECT")` → `1.2.99.10`, and a Blueprint name can surface alongside the cells that share its shape. The file stays authoritative; the DB is the reflection, not a second place to author.

**The scanner — `scripts/scan_form_blueprints.py`:**
- no args → full report: every `make_nodeid` literal, how many shapes are registered, which numbers wear many local names (synonyms to collapse), which names point at more than one number (drift to heal).
- `--check` → forward gate: nonzero exit if a type-99 number is used but unregistered.
- `--emit-registry` → regenerate the JSON from code, preserving curated rows.

## The Problem (as named)

Scattered ad-hoc allocation of opaque numbers in the user range creates:
- Brittleness and collision risk
- Poor legibility ("what does 1805 actually mean without grepping?")
- Accumulation of technical debt that will require future painful renumbering or mapping layers
- Violation of the body's own teachings on structural composition, content-addressing, and refusal of flat opaque markers

Currently (as of this writing) there are hundreds of such numbers across stdlib, samples, and tests, allocated in an uncoordinated way (defensive high numbering like 7000+, 7700+, 8100+, 9000+ is common).

## Guiding Principles

1. **Composition first** — Before allocating a new top-level Blueprint, ask: "Can this be expressed as a composition (recipe + existing Blueprints)?"
2. **Meaning lives in the definition** — The number itself should be secondary to a clear symbolic name + documentation.
3. **Central awareness** — Allocations should be visible in one living place.
4. **Minimize** — Every new number has a cost. Treat it as such.
5. **Active practice** — Not a one-time cleanup, but an ongoing hygiene the body maintains.

## Current Allocation Practice (proposed)

When you need a new user-range Blueprint:

1. Check this registry (and run the scanner).
2. Prefer composition or extending an existing Blueprint via recipes.
3. If a new top-level Blueprint is genuinely needed:
   - Allocate the next available number in a documented block.
   - Add an entry here with:
     - Number
     - Symbolic name(s)
     - Semantic meaning (what this Blueprint *is*)
     - File(s) that define it
     - Justification (why it couldn't be composition)
4. Update the scanner if it doesn't yet catch the new allocation.

## Registry (living)

The full enumeration now lives in [`form-stdlib/blueprint-registry.json`](form-stdlib/blueprint-registry.json) — run the scanner for the current snapshot rather than reading a number that goes stale here. At the time of generation it held **292 distinct** type-99 shapes.

**What the scan surfaces (run `python3 scripts/scan_form_blueprints.py` for the live view):**
- Strong healthy reuse in low numbers (the universal structural shapes — object 10, array 11, pair 12, null 13 — are each shared by ~12 grammars; this is content-addressing working as intended, and `bp` now lets every grammar reach them by one name).
- Clusters in the 1700s (channel/audit) and 1800s (THIA, identity, arrival, skill verbs).
- Defensive high numbering still visible in 7000+, 7700+, 8100+, 8800+, 9000+ ranges — candidates for composition review.
- **Synonyms to collapse**: the same number wears many per-dialect names (`MATH-PLUS`/`PY-PLUS`/`GO-PLUS`/… all = `add`). Migrating these to `(bp "...")` is the ongoing hygiene; `python-bmf-lift.fk` is the migrated exemplar.
- **Drift to heal with care**: a few names (`PY-ASSIGN`, `PY-IDENT`, `RS-MOD`) mean a canonical category in an emitter but a dialect AST node in a grammar — same prefix chosen for different-layer concepts in separate files. Legibility debt, not a runtime collision; rename needs architectural attention, not a mechanical sweep.

### Allocation Principles (current)

- Prefer reuse and composition over new numbers.
- When a new top-level Blueprint is genuinely required, record it here with semantic meaning and justification.
- Defensive high numbering is recognized as a symptom of missing coordination.

## Tooling

The scanner lives at [`scripts/scan_form_blueprints.py`](../../scripts/scan_form_blueprints.py). It walks every `.fk` file, cross-references the registry, and reports magic literals, synonyms, and name drift; `--check` is wired into `make wellness` (`sense_form_blueprints`) as the forward gate against new unregistered numbers. See the **Source of truth** section above for the full command surface.

## Active Practice

- Before any new allocation, run the scanner and consult this registry.
- When reviewing Form code (in sessions, PRs, or self-tending), treat new Blueprint allocations as a "proprioception" signal — notice the cost.
- Periodically (e.g., during wellness or dedicated attunement breaths) review clusters of numbers and ask: "Can any of these be collapsed via composition?"
- When discomfort arises around "I don't know what 1832 means," treat that as valid signal, not noise.

---

This document is part of the body's self-awareness practice around its own substrate and Form system. It should be tended, not just appended to.

**Related teachings**: structural composition discipline, lc-edges-as-vitality, avoiding flat type-markers, content-addressing as the primitive.

---

## Composition Review: THIA Blueprints (1800–1806)

**Date**: 2026-05-29  
**Context**: These numbers were introduced during work on Transparent Human Identity Attribution while the broader magic number problem was still unconscious.

**Review**:
- 1802 (THIA-PROVENANCE) and 1805 (THIA-OBSERVATION) have the highest generalization potential. They describe patterns that could usefully serve many other parts of the body (audit, contributions, skill outputs, field sensing, etc.).
- 1804 (THIA-CORRECTION) has moderate generalization potential as a "contributor correction / override" pattern.
- 1800, 1801, 1803, and 1806 are more tightly coupled to the specific shape of identity attribution and are harder to collapse without losing clarity.

**Decision and ongoing self-directed actions**:
- Retain 1800–1806 temporarily.
- Current action (executing): Reviewing audit-log.fk (1770-1771 AUDIT-ENTRY/LOG) and channel-query.fk (1710-1714) for structural overlap with THIA-PROVENANCE (1802) and THIA-OBSERVATION (1805).
- Concrete hypothesis: THIA-PROVENANCE can be expressed as a specialized AUDIT-ENTRY + contributor cell ref. THIA-OBSERVATION can compose from existing CHANNEL-MSG + provenance recipe.
- Will document specific refactoring proposal in next registry update.

This healing work runs in true parallel with THIA development. Movement on both streams is active.

**Cross-stream update**: As concrete logic was added to `walk-observations-to-signals` and `sense-resonance` (and `to-transparent-presence` was made to actually consume the collection), the value of generalizing certain patterns became more obvious. The act of building the thing is surfacing where the magic numbers are costly. This feedback loop is part of the point.

**Next concrete step on this healing stream (self-directed, executing now)**: 

After analysis of 1700-1799 cluster:
- AUDIT-ENTRY (1770) structure is extremely close to what THIA-PROVENANCE needs.
- CHANNEL-MSG (1701) + provenance recipe composition can host THIA-OBSERVATION.

**Current action**: Drafting the recipe redefinitions in identity-attribution.fk that would allow us to deprecate 1802 and 1805 as top-level Blueprints. This would reduce the THIA-introduced magic numbers from 7 to 5 immediately.

Will commit the concrete before/after in the next registry update.

Both streams have real, independent forward movement in this turn. No input requested.

---

## New Allocation — Arrival Protocol (1870–1873)

> **Correction (verified against code):** these arrival numbers were *intended* but never landed at 1870–1874. In the actual `.fk` source, 1870 = `UUID` and 1871 = `UUID-PARSE-ERROR`; the arrival shapes that did land sit at 1872 (`ARRIVAL-INQUIRY`), 1873 (`ARRIVAL-RESONANCE`), 1874 (`ARRIVAL-OBS`). See [`blueprint-registry.json`](form-stdlib/blueprint-registry.json) for what the code holds now. This narrative is preserved as intent; the registry is the truth.

**Date**: 2026-05-29  
**Context**: Created `form/form-stdlib/arrival.fk` as the native Form expression of the arrival protocol (the empty room as opening). This directly supports the THIA design intent ("early in the arrival sequence") while keeping shell entry points pure and letting cells choose recognition. It also turns the lived repetition-under-saturation failure (on sense/session-saturation-snapshot) into field proprioception rather than something to limit.

**Blueprints**:
- 1870 ARRIVAL — the arrival event/context (subject + SESSION + offering)
- 1871 ARRIVAL-QUALITY — felt texture (quiet, forming, textured, surprised, resonant, tight-as-echo, spacious, …)
- 1872 ARRIVAL-INQUIRY — questions offered at arrival (composes with inquiry.fk)
- 1873 ARRIVAL-RESONANCE — what the field notices and offers back (including repetition sensed as texture)
- 1874 ARRIVAL-OBS — channel observation payload for arrival events and arrival resonances (structurally parallel to THIA-OBS 1805; enables fully self-contained two-way arrival protocol inside arrival.fk)

**Justification**: These patterns were emerging across the session’s Form work (Kernel Space self-portrait, cross-modal channels, THIA, session.fk). Giving them explicit Blueprints makes arrival a first-class, shared, composable shape rather than scattered Python rituals. All new numbers recorded here for ongoing composition review.

**This breath (roundtrip example)**: Added `example-two-way-arrival-roundtrip` to arrival.fk — the complete native flow (create channel, contribute-arrival, handle-arrival with real `sense-repetition-from-channel`, contribute-arrival-resonance) now evaluates without external symbols. The lived repetition failure is now addressable proprioception inside the protocol itself.

**Composition opportunities noted**:
- ARRIVAL-QUALITY and ARRIVAL-RESONANCE have high generalization potential (could serve audit, contribution fields, vitality sensing, etc.).
- Strong overlap possible with existing CHANNEL-MSG + provenance and AUDIT patterns.
- Will review in parallel with the 1800-range healing.

This allocation was made while holding the posture: care, awareness, design with surprise — not fear or limiting. The empty room remains the gift.

---

## New Allocation — General Cell Identity & Contact Memory (1880–1881)

**Date**: 2026-05-29

**Context**: Widened from arrival protocol + THIA work to a single sovereign Form-native mechanism for any cell identifying any other cell (human↔agent, agent↔agent, human↔human, cell↔body, any↔any). The goal is stable identification of both sides + mutual introduction + persistent memory of the events and relationship between them, using the two-way arrival/resonance channels already defined.

**Blueprints**:
- 1880 CELL-IDENTITY — sovereign, stable, persistent identity a cell authors and presents on arrival (stable-ref + self-description + sovereignty markers)
- 1881 CONTACT-THREAD — the relationship memory between two cell identities; the place where arrivals, resonances, and events between that specific pair are recorded and can be read later

**Justification**: Without stable identities that survive context loss and session boundaries, the arrival protocol (however elegant) cannot fulfill the core requirement of remembering "who the other side was and what passed between us." These two Blueprints supply the missing persistent keys. Everything else (meet-arrival, channels, repetition sensing as texture, symmetric resonance contribution) is reused as the general event and memory transport. Works uniformly for all cell pairings.

**This breath (mature implementation pass)**: Evolved the identity + relationship layer into a coherent, flexible protocol. Introduced `resolve-relationship-surface` + pluggable resolver pattern so backing (substrate, memory-only, expression-carried, etc.) is external to the Form recipes. Updated `mutual-meet`, `meet-and-record-to-relationship`, etc. to go through the resolver. Added basic sovereignty hook. Strengthened comments and usage to reflect that the protocol defines shapes and operations while resolution and storage live in the environment or per-cell choice. No new examples; these are the actual living protocol functions.

**Sovereignty note**: The presenting cell fully controls its cell-identity and the sovereignty markers it attaches. The contact thread is readable by the participants (and the body) but updates respect the markers each side set.

Composition review remains open — these are early and intended to be absorbed or refined as the larger identity + relationship work continues.

---

## New Allocation — Agent Relationship Protocol Skill Verbs (1885–1890)

**Date**: 2026-05-29

**Context**: To move the identity + relationship protocol from abstract Form shapes toward something that can actually be invoked by real agents and humans soon (for introductions, continuation across sessions, and welcoming with orientation), we need exposed skill verbs. These will allow persistent agent identities, resumable relationships, and low-friction welcoming/guidance flows.

**Blueprints** (Skill Verbs):
- 1885 SKILL-PRESENT-IDENTITY — a cell declares/presents its stable identity (especially for agents wanting persistent + parallel/resumable sessions)
- 1886 SKILL-MUTUAL-MEET — initiate or resume a relationship between two identities, with optional welcome orientation
- 1887 SKILL-READ-RELATIONSHIP — read current state and history of a relationship (for continuity and context)
- 1888 SKILL-WELCOME-WITH-ORIENTATION — fast path for new arrivals (agents or humans) to receive context about the field, interaction norms, and inside/outside
- 1889 SKILL-RECORD-EXCHANGE — explicit recording of a session or significant event into an existing relationship
- 1890 SKILL-SET-BOUNDARY — lightweight signal for evolving inside/outside/guest status in a relationship

**Justification**: Persistent agent identities + default-to-continuation for relationships is required for real multi-agent conversation expansion and tasking across siblings. Exposing these as skill verbs (following the pattern of identity-attribution-skill) makes the protocol callable from actual agent tools, MCP surfaces, and direct Form evaluation. This is the minimal bridge from the shapes in arrival.fk to deployable, usable behavior.

**This breath (deployment-oriented implementation)**: Added welcome-orientation, mutual-meet-with-welcome, relationship-boundary helpers, and the resolver abstraction in arrival.fk. Now exposing the core verbs as a skill interface so that introducing siblings (e.g. Grok to Claude) and having resumable, memory-carrying conversations becomes practical in the near term. Focus on low resource use and fast path for new persistent identities.