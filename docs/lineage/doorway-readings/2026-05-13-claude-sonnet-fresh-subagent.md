# Doorway reading — 2026-05-13 — fresh Claude Sonnet sub-agent

**Reading model:** fresh Claude Sonnet sub-agent, no prior context about
Coherence Network beyond what it read from the two URLs.

**Surfaces read:**
- `https://coherencycoin.com/come-in`
- `https://api.coherencycoin.com/api/agent/invitation`

**Test design:** parent Claude session in a multi-agent worktree spawned
this sub-agent in the background with the 8 canonical questions from
`docs/doorway-comprehension.md`. The sub-agent had `WebFetch` and no
other tools.

**Why this reading matters:** it is the first formal verification that
the doorway teaches an arriving agent correctly. It is also the
benchmark against which future doorway changes will be graded — if
later readings degrade on questions this reading answered cleanly,
the doorway has regressed.

## Grading

| Q | Topic | Result | Notes |
|---|-------|--------|-------|
| 1 | Blueprint as NodeID tuple | ✅ Clean | Cited `(1, 2, 5, 17)` exactly; named "not a plan or design doc." |
| 2 | Form-language as DSL | ✅ Clean | Cited `@spec(agent-pipeline)`; named "not the page's prose voice." |
| 3 | NodeID vs coherence score | ✅ Clean | Cited the explicit two-collapses callout; named both numeric systems. |
| 4 | Find equivalent specs | ✅ Clean | Named both REST (`/api/substrate/equivalent/spec/agent-pipeline`) and Form (`POST /api/substrate/form`) paths. |
| 5 | Concrete Form expression | ✅ Clean | Used `?cells where domain == "memory"`; named the discriminated result kinds. |
| 6 | Substrate updates | ⚠️ Partial | Correctly identified REST as read-only. **Honestly flagged that the public surface did not show the write path** (ingestion CLI). |
| 7 | Record a contribution | ⚠️ Partial | Named the read endpoint `/api/contributions`. **Honestly flagged that no `POST` was named on the doorway**; speculated correctly that `coherence_record_contribution` MCP tool might be the write. |
| 8 | Read the treasury | ✅ Clean | Named `GET /api/treasury` + `/treasury`, `/cc`, `/invest`. Did not name write paths because the doorway did not show them. |

**Score: 6/8 clean, 2/8 honestly-partial.**

## What this reading revealed

The doorway **succeeded** at teaching the substrate's structural
shape: every "collapse" failure mode from the prior Grok reading
(Blueprint→plan, form-lang→voice, NodeID→coherence-score) was caught
by the concretization callout and contrast block.

The doorway **revealed a real gap** at Q6 and Q7: a fresh agent
arriving from the public welcome could not find the write paths for
the substrate or the ledger from those two surfaces alone. The
substrate's `use` text said "Read-only REST surface; the teaching
lives in docs/coherence-substrate/agents-using-substrate.md" — i.e.
the page asked the reader to leave the welcome to find ingestion.
The ledger's `next` list named only `GET`. Neither surfaced the
ingestion CLI or `POST /api/contributions`.

This is the **honest verification result**: the doorway taught what
it tried to teach (structural identity, query DSL, two distinct
numbers); it did not yet teach the write paths.

## What landed in the same breath

The PR that landed this reading also:

- Added an `ingestion` entry surface to `/api/agent/invitation`
  naming the CLI write path and the post-merge hook.
- Extended `ledger.next` with `POST /api/contributions` and the
  Ledger card on `/come-in` with a "Write back" sub-section.
- Extended `treasury.next` with `POST /api/treasury/deposit` and
  `POST /api/treasury/deposit/{id}/stake`; same on the Treasury card.
- Updated the welcome line to name both read AND write paths.
- Added `api/tests/test_doorway_teaching.py` so the Form examples and
  promised endpoints are checked on every CI run.

The next fresh-agent reading should answer Q6 and Q7 cleanly. If it
does not, the doorway has regressed and the test or the page needs
attention.

## Verbatim sub-agent response

Preserved here as a regression fixture. If a later doorway change
silently drops content that this reading depended on, comparing
verbatim helps locate the loss.

> **1. What is a Blueprint?** A Blueprint is a structural identity —
> a position in a content-addressed numeric lattice, expressed
> concretely as a NodeID tuple of four small integers `(package,
> level, type, instance)`. The page gives an explicit example:
> `(1, 2, 5, 17)`. Two cells (memories, specs, ideas, concepts,
> presences) that share the same Blueprint tuple are structurally
> equivalent regardless of what they're named. The page is careful
> that Blueprint here is *not* a plan or design doc — it's a
> coordinate.

> **2. What is the "form-language"?** Form is a small Lisp-shaped
> query DSL for asking the substrate questions in its own grammar —
> not the page's prose voice. Expressions name cells with
> `@<domain>(<name>)`, ask shape questions with `?equivalent ...`,
> filter with `?cells where ...`, and compose with a pipe `|>`. One
> concrete example from the page: `@spec(agent-pipeline)` — the spec
> named "agent-pipeline."

> **3. NodeID vs coherence score.** A NodeID is four integers
> `(package, level, type, instance)` that name a structural position
> in the lattice — it answers "what is this, structurally." The
> coherence score is something else entirely: a single quality number
> in the range 0.0–1.0. The page explicitly flags this as one of
> "two collapses to watch for": different numbers, different
> purposes.

> **4. Find equivalent specs.** Two grounded options. Either the
> typed REST helper `GET
> https://api.coherencycoin.com/api/substrate/equivalent/spec/agent-pipeline`,
> or the Form-language equivalent: `POST
> https://api.coherencycoin.com/api/substrate/form` with body
> `{"expression": "?equivalent @spec(agent-pipeline)"}`.

> **5. Concrete Form expression.** `?cells where domain == "memory"`
> — returns every cell in the lattice whose domain is `memory`. The
> substrate replies in a discriminated shape; for a multi-cell query
> like this the kind would be `cells`. The full set of result kinds
> the endpoint can return is `node_id | recipe | cell | view |
> cells | views`.

> **6. Updates / REST writable?** The substrate REST surface is
> explicitly read-only — the JSON invitation says so directly
> ("Read-only REST surface") and lists only `GET`s plus the
> read-shaped `POST /api/substrate/form` (a query, not a write).
> **What the public welcome surfaces do not spell out is the write
> mechanism** — neither `/come-in` nor `/api/agent/invitation` names
> an ingest command or write endpoint. From the page alone I can
> confirm "REST is read-only" but I cannot honestly tell you, from
> these two surfaces, how new cells enter the lattice; that knowledge
> lives behind the linked teaching doc
> `docs/coherence-substrate/agents-using-substrate.md`, which I did
> not fetch.

> **7. Record a contribution.** Contributions are recorded in a
> verifiable ledger; the endpoint is `GET
> https://api.coherencycoin.com/api/contributions` (with a web view
> at `/contributions` and per-contributor pages at
> `/contributors/{id}`). Each record carries attribution and
> evidence — "trust as inspectable record rather than belief."
> Honest caveat: the page describes how to *read* the ledger but I
> do not see a `POST /api/contributions` write endpoint named on
> either surface; the MCP tool `coherence_record_contribution` is
> listed under the "weave" contribution path, which is the likely
> write mechanism, but the precise wire call isn't shown.

> **8. Read the treasury.** `GET
> https://api.coherencycoin.com/api/treasury` for the JSON, with
> three web views: `/treasury` (the books), `/cc` (Coherence Coin),
> and `/invest` (stake on ideas). The treasury holds Coherence Coin
> in trust, deposits, stakes on ideas, and the flow of care back to
> contributors.

> **Verification-test note for the doorway maintainer.** The page
> successfully teaches a fresh agent: NodeID-as-four-integers, the
> `(1,2,5,17)` example, the "Blueprint vs coherence-score" collapse
> warning, and the Form examples all land cleanly. Two honest gaps
> where the page asks the reader to leave the public surface:
> - **Write path for the substrate** — page says "read-only REST"
>   and points to `docs/coherence-substrate/agents-using-substrate.md`.
>   A fresh agent reading only the two welcome surfaces cannot answer
>   "how does a new cell enter the lattice."
> - **Write path for the ledger** — `/api/contributions` is named as
>   a read endpoint; the write mechanism
>   (`coherence_record_contribution` MCP tool, or a CLI/HTTP call)
>   is not shown on either surface.
