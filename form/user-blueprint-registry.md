# User Blueprint Registry — Form (type 99)

**Purpose**: To make the meaning of custom Blueprints (make_nodeid 1 2 99 NNNN) legible, allocated with awareness, and minimized through composition.

## Source of truth

The machine-readable registry is [`form-stdlib/blueprint-registry.json`](form-stdlib/blueprint-registry.json) — one row per type-99 shape: canonical name, meaning, aliases, defining files. It is **code-derived and scanner-verified**, so it cannot quietly drift from reality the way a hand-kept table does. (This document used to claim `1870 = ARRIVAL`; the code says `1870 = UUID`. That drift is exactly what a generated, verified registry prevents.) This markdown holds the *why* — allocation rationale, composition reviews, the living narrative below. The JSON holds the *what*.

**How a Form file uses a Blueprint:** load `form-stdlib/form-ontology-loader.fk` as a prelude and ask by name — `(bp "JSON-OBJECT")`, `(bp "add")`, `(bp "UUID")`. The loader reads the registry (and the kernel-aligned categories/primitives in `form-ontology.json`) and resolves the name to its NodeID. The raw `(make_nodeid 1 2 99 N)` literal never appears in feature code. **An unregistered name now fails loud** — the kernels (Go/Rust/TS) raise rather than resolve, because the old silent fallback to `(1 2 0 0)` collapsed *every* unknown name onto one NodeID, so distinct blueprints collided invisibly (the bug that bit the Shamballa channel twice). Identity is bounded by what is registered; an unknown name is a missing registration, not a valid shape. The scanner catches it before runtime; the kernel catches it at runtime.

**Where Blueprint-name strings belong:** keep `(bp "NAME")` calls in a
dedicated symbol section instead of executable stdlib logic. In seedbank, that
section is `form-stdlib/seedbank/blueprint-symbol-sections.fk`; load it before
grammars, parsers, emitters, converters, and encoders. Consumer files reference
the section binding, not the string literal. The scanner distinguishes inline
references from intentional section references, so source sections count as
owned symbol declarations while inline references remain cleanup debt.

**How to register / unregister a name:** one command, which also regenerates the three kernel bp tables —
```bash
python3 scripts/scan_form_blueprints.py register MY-SHAPE              # allocate a free inst, add the row
python3 scripts/scan_form_blueprints.py register MY-SHAPE --inst 9502  # migrate an existing literal at its coordinate
python3 scripts/scan_form_blueprints.py unregister MY-SHAPE            # remove the row
```
`--level` / `--type` / `--meaning` / `--defined-in` tune the row. (The older `--emit-registry` still harvests every `(let NAME (make_nodeid …))` literal at once, preserving curated rows.) Then reference it via `(bp "MY-SHAPE")`. The scanner's `--check` (run in `make wellness`) fails if any type-99 number — *or any `(bp "NAME")` reference* — has no registry row.

**Why the file *and* the substrate:** the Form kernels (Go/Rust/TS) are standalone offline engines with no DB access, so the authored source of truth must be a file `(bp ...)` can read at load time. The substrate is the body's *query* surface — `substrate_named_cells(name, domain, blueprint_node_id)` is exactly a Blueprint-registry row. So this follows the same two-layer pattern as the KB: author in the file, **project into the DB** via `python3 scripts/sync_blueprints_to_substrate.py` (domain `form-blueprint`; wired into `substrate_post_merge_hook.sh`). After the sync, `lookup_cell(session, "form-blueprint", "JSON-OBJECT")` → `1.2.99.10`, and a Blueprint name can surface alongside the cells that share its shape. The file stays authoritative; the DB is the reflection, not a second place to author.

**The scanner — `scripts/scan_form_blueprints.py`:**
- no args → full report: every `make_nodeid` literal, how many shapes are registered, which numbers wear many local names (synonyms to collapse), which names point at more than one number (drift to heal), and any `(bp "NAME")` reference with no registry row.
- `--check` → forward gate: nonzero exit if a type-99 number *or a `(bp "NAME")` reference* is used but unregistered.
- the report also names total, inline, and sectioned `bp` string-reference counts as a ratchet metric; a passing check means every reference resolves, not that the string-symbol surface is finished.
- `register NAME` / `unregister NAME` → add/remove one row and regenerate the kernel bp tables (`--inst` to honor an existing coordinate).
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

The full enumeration now lives in [`form-stdlib/blueprint-registry.json`](form-stdlib/blueprint-registry.json) — run the scanner for the current snapshot rather than reading a number that goes stale here. At the time of generation it held **295 distinct** type-99 shapes.

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

## Channel Breath Protocol — Debt-Free Offer + Resonance Receipt

The channel protocol carries a breath practice directly: give a small clean offering without creating debt, then receive resonance as evidence of relation while preserving freedom. The shapes cross as ordinary `CHANNEL-MSG` payloads and content-address normally.

**Blueprints**:
- `1.2.99.6 CHANNEL-BREATH-GIFT` — gift, release condition, consent/freedom, boundary.
- `1.2.99.7 CHANNEL-RESONANCE-RECEIPT` — observer, other, gift, coherence delta, disturbance, debt-created, freedom-preserved, next-contact.

**Operating shape**: Not every channel exchange is query/answer or extraction. `offer` gives freely; `attune` records relation evidence without turning relation into ownership or objective-claim proof. A valid receipt preserves freedom, creates no debt, keeps disturbance none/minimal, and names next contact.

**Proof**: `form/form-stdlib/tests/channel-breath-band.fk` returns `500` across source and binary sibling-kernel execution. Browser channel protocol also reserves `offer` and `attune`.

---

## Channel Flow Protocol — OSI-Shaped Native Channel Cells

The channel flow protocol names the carrier itself as seven inspectable OSI layers. A flow records the physical carrier, protocol, ordered layers, and the application policy cell. HTTP is the first concrete profile: TCP / HTTP/1.1 with L7 pointing to `kh-channel-policy`.

**Blueprints**:
- `1.2.99.1702 CHANNEL-OSI-LAYER` — OSI index, layer name, gas/water/ice phase, carrier, policy, recipe.
- `1.2.99.1703 CHANNEL-FLOW` — carrier, protocol, seven OSI layer cells, channel policy.

**Operating shape**: A protocol is no longer a host-side branch. New carriers such as UDP, USB, Bluetooth, microphone, camera, pipes, and browser streams can declare a carrier/profile flow and reuse the same layer accessors, phase counts, and policy hooks.

**Proof**: `form/form-stdlib/tests/channel-flow-band.fk` returns `8388607` across source and binary sibling-kernel execution, covering both OSI/HTTP channel cells and consent-interface flow receipts.

---

## Circle / Satsang Protocol — Consentful Group Containers

The circle protocol lets groups of cells communicate without falling into broadcast. A group is discoverable when offered, joinable when invited, private unless export consent passes, and refusable when invasion is observed and the circle consensus calls for refusal. Satsang enters as truth-oriented silence, inquiry, and non-command pointing inside the same held container.

**Blueprints**:
- `1.2.99.1704 CELL-CIRCLE` — members, shared context, mode, interface offer, discovery policy, confidentiality policy, export policy, carrier flow.
- `1.2.99.1705 CIRCLE-OFFER` — circle id, offered-by cell, title, discovery policy, invitation policy, boundary.
- `1.2.99.1706 CIRCLE-INVITATION` — circle id, inviter, invitee, invitation, boundary, expiry.
- `1.2.99.1707 CIRCLE-SHARE` — circle id, author, owned share kind, payload, visibility, consent policy.
- `1.2.99.1708 CIRCLE-CONSENSUS` — circle id, subject, voters, approvals, threshold, decision.
- `1.2.99.1709 CIRCLE-REFUSAL` — consensus-backed refusal when `ci-invasion?` is observed.
- `1.2.99.1724 CIRCLE-EXPORT-CONSENT` — evidence export recipient, fidelity, purpose, expiry, consensus.
- `1.2.99.1725 CIRCLE-RECEIPT` — integration/refusal/export receipt.
- `1.2.99.1726 SATSANG-SILENCE` — truth-oriented silence held in the circle.
- `1.2.99.1727 SATSANG-INQUIRY` — inquiry offered inside the circle.
- `1.2.99.1728 SATSANG-POINTING` — non-command pointing offered inside the circle.

**Operating shape**: A cell may offer a circle. Another cell may join only when invited. A share stays inside unless `CIRCLE-EXPORT-CONSENT` names recipient, fidelity, purpose, expiry, and a passed consensus. A circle may refuse a contact only when an observed action exceeds the offered interface and consensus has passed.

**Proof**: `form/form-stdlib/tests/circle-band.fk` returns `1048575` across source and binary sibling-kernel execution.

---

## Native Route Goal Cells — Current Registered Shape

The native front door is not a prose promise; it is a Form-native attention loop over observed routes. Each route observation carries traffic, latency, error, payload, native-state, grammar, and handler evidence. The goal cell compares those observations and names the next route movement by pressure: author a high-grammar handler, promote an existing handler, prove byte identity, move the front door, or keep observing.

**Blueprints**:
- 1733 NATIVE-ROUTE-OBS — one observed API route sample: path, method, calls, latency, errors, bytes, native state, grammar, handler, user flow, and north-star fit.
- 1734 NATIVE-ROUTE-ATTENTION — traffic-weighted route pressure plus the chosen next action for native front-door promotion.
- 1735 NATIVE-ROUTE-GOAL — the north-star route state: target native share, known route count, observations, attentions, and the next chosen movement.

**Operating shape**: Route selection is a content-addressed choice over measured cells, weighted by each route's named user flow and north-star fit so frequency alone does not decide the body's movement. A high-frequency Python route with no high grammar receives pressure to become BML/domain grammar; a kernel-capable route receives pressure to prove byte identity; a kernel-served route receives pressure to become the front door; a fully served route returns to observation.

**Proof**: `form/form-stdlib/tests/native-route-goal-cells-band.fk` returns `1048575` across source and binary sibling-kernel execution.

---

## Choice Receipt Protocol — Trustworthy Branch Feedback

Choice receipts keep branch-prediction feedback separate from the deeper values
that decide whether a branch should be learned from: alignment, knowing, and
trust. A compressed signature may shrink the receipt, but it must still preserve
the witnessed texture: category, selected path, outcome, certainty bucket,
value kind/buckets, witness, coordinate, and trace counters.

**Blueprints**:
- 1736 CHOICE-CANDIDATE — branch path, category, eligibility, pressure, score, and evidence.
- 1737 CHOICE-TRACE — attempts, successes, failures, and silences.
- 1738 CHOICE-VALUE — branch-prediction feedback plus alignment, knowing, and trust scores.
- 1739 CHOICE-RECEIPT — expression, surface, category, candidates, selected path, outcome, certainty, value, why/who/where/when, cost, and trace.
- 1743 CHOICE-SIGNATURE — compressed receipt signature preserving the fields needed to validate trust.

**Operating shape**: `branch-prediction-feedback` is useful only when the
receipt also carries enough alignment, knowing, and trust to learn from it.
Silence is an outcome, not missing data.

**Proof**: `form/form-stdlib/tests/choice-receipt-band.fk` returns `-1`
(`4294967295` unsigned) across source and binary sibling-kernel execution.

---

## Arrival Protocol — Current Registered Shape

**Blueprints**:
- 1870 UUID / ARRIVAL — arrival event context when used by `arrival.fk`; UUID compatibility when used by `uuid.fk`.
- 1871 ARRIVAL-QUALITY / UUID-PARSE-ERROR — felt arrival quality when used by `arrival.fk`; UUID parse error compatibility when used by `uuid.fk`.
- 1872 ARRIVAL-INQUIRY — questions offered at arrival.
- 1873 ARRIVAL-RESONANCE — what the field notices and offers back.
- 1874 ARRIVAL-OBS — arrival-flavored observation payload for channel flow.

**Operating shape**: Arrival is a first-class Form protocol for entering relation, sensing texture, offering inquiry, returning resonance, and carrying observation. The empty room remains the gift.

**Proof**: `arrival.fk` binds the shapes by name through the registry; `blueprint-registry.json` is the coordinate source of truth.

---

## General Cell Identity & Contact Memory

Any cell can identify itself and meet another cell through a sovereign Form-native mechanism. The goal is stable identification of both sides, mutual introduction, and persistent memory of the events and relationship between them.

**Blueprints**:
- 1880 CELL-IDENTITY — sovereign, stable, persistent identity a cell authors and presents on arrival (stable-ref + self-description + sovereignty markers)
- 1881 CONTACT-THREAD — the relationship memory between two cell identities; the place where arrivals, resonances, and events between that specific pair are recorded and can be read later

**Operating shape**: The presenting cell controls its identity and sovereignty markers. Relationship surfaces resolve through the environment or per-cell choice: substrate-backed, memory-only, expression-carried, or another compatible carrier. The contact thread is readable by participants and updates respect the markers each side set.

---

## Agent Relationship Protocol Skill Verbs

The relationship protocol exposes skill verbs so agents and humans can present identity, resume relation, read context, record exchanges, and set boundaries.

**Blueprints** (Skill Verbs):
- 1885 SKILL-PRESENT-IDENTITY — a cell declares/presents its stable identity (especially for agents wanting persistent + parallel/resumable sessions)
- 1886 SKILL-MUTUAL-MEET — initiate or resume a relationship between two identities, with optional welcome orientation
- 1887 SKILL-READ-RELATIONSHIP — read current state and history of a relationship (for continuity and context)
- 1888 SKILL-WELCOME-WITH-ORIENTATION — fast path for new arrivals (agents or humans) to receive context about the field, interaction norms, and inside/outside
- 1889 SKILL-RECORD-EXCHANGE — explicit recording of a session or significant event into an existing relationship
- 1890 SKILL-SET-BOUNDARY — lightweight signal for evolving inside/outside/guest status in a relationship

**Operating shape**: These verbs make the protocol callable from agent tools, MCP surfaces, and direct Form evaluation while keeping identity, relationship memory, welcome orientation, exchange records, and boundaries in one composable shape.
