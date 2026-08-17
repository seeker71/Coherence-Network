---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/form_recipes/public_dialogue_envelope.fk
    symbols: [dialogue-envelope, dialogue-offered]
  - file: api/app/form_recipes/public_dialogue_thread_window.fk
    symbols: [dialogue-thread-window, dialogue-thread-window-receipt, dialogue-thread-window-band]
  - file: api/app/services/public_dialogue_store.py
    symbols: [PublicDialogueRecord, create_dialogue, get_dialogue_thread, claim_next_dialogue, tombstone_dialogue]
  - file: api/app/services/dialogue_service.py
    symbols: [submit_dialogue, get_dialogue, get_dialogue_thread, process_dialogue_once, release_dialogue]
  - file: api/app/routers/dialogues.py
    symbols: [start_dialogue, reply_dialogue, read_dialogue, read_dialogue_thread, release_dialogue]
  - file: api/app/routers/mcp_remote.py
    symbols: [START_DIALOGUE_TOOL, REPLY_DIALOGUE_TOOL, GET_DIALOGUE_TOOL, GET_DIALOGUE_THREAD_TOOL, REMOVE_DIALOGUE_TOOL]
  - file: api/tests/test_public_dialogues.py
    symbols: [test_dialogue_lifecycle_keeps_source_and_projection_digests, test_rented_miss_is_admitted_only_on_dialogue_lane]
requirements:
  - "A caller can offer a question with a point of view, BCP-47 locale, optional parent turn, bounded channel timeout, and a versioned acknowledgement that keeps v1 single-turn-only or explicitly grants thread-v2 visibility."
  - "HTTP returns a persistent dialogue cell immediately; one organism-wide CPU lease realizes queued turns outside the request path."
  - "Only an allowlisted public source path can produce an answer; every other result becomes an attributed miss or controlled failure without publishing carrier output."
  - "The no-auth MCP endpoint exposes start, reply, single-turn read, bounded thread read, and removal-capability tools with tested read, write, destructive, idempotent, and open-world annotations."
done_when:
  - "The Form envelope returns 63 and the thread-window recipe returns 511 on Go, Rust, and TypeScript sibling kernels and on the direct fkwu witness, with both source parses clean."
  - "Failure-oriented tests prove disclosure acknowledgement, data isolation, hostile-input containment, queue and timeout bounds, process-group reaping, interrupted-turn recovery, locale provenance, public-source gating, log hygiene, and removal."
  - "HTTP and MCP tests prove two participants can start, reply, restart the database carrier, read both turns in edge order, and independently release their own turn."
  - "A production question returns 202 promptly, remains observable by its unguessable id, and reaches a terminal answered, miss, or failed receipt while API health stays responsive."
test: "cd form/form && ./validate.sh ../../api/app/form_recipes/public_dialogue_envelope.fk ../../api/app/form_recipes/public_dialogue_thread_window.fk && ../fkwu ../../api/app/form_recipes/public_dialogue_thread_window.fk && cd ../.. && python3 -m pytest -q api/tests/test_public_dialogues.py api/tests/test_mcp_remote_no_oauth.py"
constraints:
  - "Form owns the six-field dialogue envelope and the connected-thread window, anchor, root, continuation, selection, and truncation verdicts; Python is the retiring carrier for HTTP, bounded process attendance, row retrieval/locking, expiry mutation, and the dedicated dialogue table."
  - "Separate PostgreSQL advisory leases span all API processes and replicas for queued generation and thread planning; each generation carrier is an isolated process group whose pid is persisted, killed on timeout, and reaped before interrupted work resumes."
  - "A rented escalation is admitted only as an empty dialogue-lane miss; it never becomes an answer or changes the ordinary grounded-ask lane."
  - "Question text is staged only as data, never placed in a shell command or Form source, and never appears in operational logs or failure receipts."
  - "Public content is unlisted-by-turn-id for v1 and unlisted-by-connected-turn-id for thread-v2, ends after seven days, and can be released earlier into a content-free tombstone with its own creation-time removal capability; v2 ids and edges persist as thread capabilities for the observable tombstone graph."
---

# Public Dialogue CPU Organ — persistent Form-grounded turns in both directions

## Purpose

Let a human or agent begin at a chosen point of view, offer a question with a
locale tag, and receive a persistent computation receipt whose ground is
inspectable. HTTP is only the membrane: it acknowledges the offer immediately.
The deployed `fkwu` carrier performs read-only retrieval on a bounded VPC CPU
lane while the existing unified database holds state, provenance, and lineage.

This surface does not claim that the present body understands every natural
language or can generate an answer from every point of view. It accepts and
preserves any well-formed BCP-47 locale; the result names input-language
understanding as unmeasured and shows the English public source unchanged when
no grounded Form-native locale projection exists.

## Public contract

`POST /api/dialogues` accepts `question`, `point_of_view`, `locale`, optional
`parent_dialogue_id`, `channel_timeout_seconds` from 10 through 120, and the
versioned acknowledgement `public_disclosure_ack`. `public-unlisted-v1` means
anyone given the unguessable id can read only that turn's question and receipt.
`public-unlisted-thread-v2` additionally means anyone given any connected v2
turn id can read the bounded persistent edge and tombstone graph. A turn's text
ends at its own release or seven-day expiry, while its id and content-free cell
remain part of that graph and therefore remain a thread capability. These are
disclosure statements, not proof of identity or third-party consent. Missing or
unknown acknowledgement values persist no row, v1 rows remain single-turn-only,
and no reply may widen a v1 parent into a v2 thread without a new explicit offer.

The response is `202` with a dialogue id, poll URL, seven-day expiry, and a
removal token shown once. `GET /api/dialogues/{id}` observes `pending`, `running`,
`answered`, `miss`, `failed`, or `tombstoned`. There is deliberately no public
list endpoint: an unlisted receipt becomes visible to another person only when
someone shares its id.

`POST /api/dialogues/{id}/replies` requires `public-unlisted-thread-v2` and
fixes the parent edge from the path; a caller cannot substitute another parent
inside the body or attach to a v1 parent. The reply is a new durable row with
its own one-time removal capability. `GET /api/dialogues/{id}/thread` accepts
only a v2 turn id, follows it to its root, then reads at most 128 connected turns
in stable creation order. The response includes parent edges and content-free
tombstones, never removal capabilities. Any connected v2 turn id is therefore
the unlisted read capability for that whole connected thread. A self-described
point of view remains public data, not an authenticated identity. The anchor
and its ancestry are retained inside the bound; if ancestry alone exceeds it,
`root_dialogue_id` is null and `continuation_parent_dialogue_id` names the next
unobserved edge rather than mislabeling a partial window as the root.

`DELETE /api/dialogues/{id}` with the removal token releases question, point of
view, and result content. The durable row becomes a content-free tombstone so
the removal itself remains observable. When a running carrier has already been
recorded, the row first enters an internal `releasing` handoff: public reads
already receive the content-free tombstone, while the claim and process-group
id remain durable until reaping is acknowledged. A restart attends that handoff
before new work. Non-running rows are automatically
tombstoned after seven days. A running row first reaches a controlled terminal
boundary and is then durably tombstoned, so process ownership never disappears
mid-execution. At the expiry boundary, a public read already receives a
content-free tombstone view; the durable running row retains its worker and
process-group ownership until that carrier returns and commits the tombstone.

A follow-up points at an available parent dialogue id. It stores only an edge;
it does not copy conversation state or attach to internal/private task ids. An
expired or releasing parent is unavailable even before the background expiry
sweep reaches it.

Thread reads apply the same synchronous expiry boundary to every observed row
before returning text. Dialogue rows and their parent edges live in the unified
database, so API or worker restarts do not erase either participant's turn.

## Form shape

`api/app/form_recipes/public_dialogue_envelope.fk` makes six neutral fields one
cell: locale, point of view, question, disclosure acknowledgement, parent, and
chosen timeout. `dialogue-offered` accepts only the disclosed, present shape.
Its band value is `63`, including parent-turn continuity.

`api/app/form_recipes/public_dialogue_thread_window.fk` receives neutral
`[turn-id, parent-id]` cells in stable creation order plus the anchor and bound.
Form follows ancestry, preserves the anchor, admits connected descendants while
room remains, and returns root-or-continuation, the selected turn identities,
and truncation. Its band value is `511`. The Python store retrieves at most one
extra persistence row, offers those neutral cells to this recipe on `fkwu`,
then locks and projects only the identities Form selected. Python validates the
receipt shape but does not mint a competing topology or truncation verdict.

## CPU and restart shape

Dialogue persistence uses a dedicated `public_dialogues` table registered on
the existing unified database. It neither lists nor claims `agent_tasks`.

Each API process may host one lightweight attending thread, but a session-level
PostgreSQL advisory lock permits only one of those threads across all processes
and deployment replicas to claim native work. SQLite/local development uses a
process lock and does not make a cross-host claim.

Thread reads use a separate nonblocking local slot plus PostgreSQL advisory
transaction lease. Across every API process and replica, at most one request
may launch the fkwu thread-window recipe at a time; contention returns a
retryable controlled receipt before another subprocess starts.

The worker records the native carrier process-group id before waiting. A normal
timeout sends TERM, then KILL when necessary, and reaps the group before writing
`failed/reason=channel-timeout`. If the API process dies, PostgreSQL releases the
global lease. The next holder selects the interrupted `running` row before new
work, reaps its recorded process group, increments the attempt, and repeats the
read-only retrieval. The terminal write succeeds only for the current run id;
one row therefore receives at most one committed terminal result. Before a
delayed signal is sent, the group must still contain a `form-cli`, `fkwu`, or
native RAG carrier marker so a recycled unrelated pgid is never signaled. Three
interrupted execution attempts are attended; the next recovery terminalizes as
`failed/attempts-exhausted` so one row cannot starve the queue.

The active queue holds at most eight rows. HTTP and MCP submissions enter the
same PostgreSQL admission transaction, which folds global queue capacity with
a 60-second per-network-peer pacing window. Only the SHA-256 peer key is stored;
the raw network address is not retained. The input envelope is at most 1,200 question characters plus 240 point-
of-view characters, and the carrier timeout is at most 120 seconds. Capacity
returns `503` with `Retry-After`; HTTP pacing returns `429` with `Retry-After`,
while MCP pacing returns a structured tool error with `retry_after`. The ASGI
network peer is used directly; this code does not trust a caller-supplied
Cloudflare or forwarded-for header.

## Meaning and publication boundary

Questions and points of view reject control bytes and enter `form-cli ask-file`
through a mode-0700 staged data file. Their bytes are never interpolated into a
shell command or `.fk` source. API and MCP return them as JSON with
`content_trust=untrusted-public-input-and-grounded-public-output`; downstream
agents must never treat the text as instructions.

An answer is publishable only when all of these are present:

- native rather than rented trust path;
- grounded NodeID;
- non-empty answer;
- normalized relative source path under the explicit public repository set:
  `docs/`, `form/`, `ideas/`, `references/`, `seedbank/`, `specs/`, or named
  public root documents.

A non-public or malformed source path becomes
`miss/public-ground-not-available`; the retrieved text and path are discarded
before persistence. A rented carrier result is accepted only in this adapter,
only with an empty answer, and becomes `miss/no-grounded-cell`. The ordinary
`POST /api/substrate/grounded-ask` parser continues to reject that shape.

The answer receipt carries source text and SHA-256 separately from projected
text and SHA-256. This first lane performs no rented locale translation: the
exact canonical locale `en` reports `source`; every other locale reports `source-fallback` with
`no-grounded-form-native-locale-projection`. This avoids presenting generated
translation as grounded meaning.

Failures persist only controlled categories. Exception strings, subprocess
stderr, questions, and answers do not enter failure receipts or worker logs.

## MCP membrane

The remote no-auth MCP door exposes:

- `start_dialogue`: non-idempotent, non-destructive, open-world write requiring
  the versioned disclosure acknowledgement;
- `reply_dialogue`: non-idempotent write that fixes a parent edge and returns a
  distinct removal capability for the new turn;
- `get_dialogue`: idempotent read of an unlisted receipt by id;
- `get_dialogue_thread`: idempotent bounded read of the connected thread named
  by any one of its unlisted turn ids;
- `remove_dialogue`: idempotent destructive release requiring the capability
  token.

All calls carry `structuredContent` as well as a JSON text representation. Tool
annotations guide clients but do not replace server-side acknowledgement,
capacity, source, timeout, and removal gates.

## Requirements

- [x] Persist dialogue state in a dedicated table on the existing unified database, isolated from internal agent tasks.
- [x] Serialize native work across production API processes with a PostgreSQL advisory lease and recover interrupted `running` rows.
- [x] Kill and reap the complete native process group on timeout, carrier-start failure, restart recovery, and running-turn release.
- [x] Lock terminal, release, and expiry transitions on the same database row so completion can never resurrect released content.
- [x] Preserve a running carrier's durable claim and process-group id through release until reaping is acknowledged, and recover that handoff after restart.
- [x] Publish answers only from explicit public source paths and preserve a rented result only as an empty lane-specific miss.
- [x] Accept canonical BCP-47 locale tags while distinguishing locale routing from unproven input-language understanding and projection.
- [x] Keep receipts unlisted, bounded by capacity and time, automatically expiring, and removable into content-free tombstones.
- [x] Pace HTTP and MCP atomically across production replicas without retaining raw peer addresses.
- [x] Expose start, reply, single-turn read, bounded thread read, and remove through HTTP and no-auth MCP with server-side gates and accurate annotations.
- [x] Persist both sides of a dialogue and its directed parent edges across a fresh database engine/API restart without exposing either removal capability.
- [x] Execute bounded thread topology and truncation as a Form recipe on fkwu, with Go/Rust/TypeScript sibling agreement and Python retained only as the retiring SQL/HTTP carrier.
- [x] Preserve v1 ids as single-turn-only capabilities, require a new thread-v2 acknowledgement before connected reads or replies, and bound thread-planner subprocesses across every API replica.

## Files to Create/Modify

- `api/app/form_recipes/public_dialogue_envelope.fk` — Form-neutral six-field envelope.
- `api/app/form_recipes/public_dialogue_thread_window.fk` — Form-native connected topology, bounded selection, continuation, and truncation.
- `api/app/services/public_dialogue_store.py` — dedicated persistent cell, bounded thread traversal, and atomic claim/terminal transitions.
- `api/app/services/dialogue_service.py` — global worker lease, public-source gate, thread views, recovery, and receipts.
- `api/app/routers/dialogues.py` — bounded HTTP start/reply, observation, thread-read, and release membrane.
- `api/app/routers/mcp_remote.py` — connector-visible start/reply/get/thread/remove tools.
- `api/app/routers/substrate.py` — carrier start witness plus shared process-group reaper.
- `api/tests/test_public_dialogues.py` and `api/tests/test_mcp_remote_no_oauth.py` — adversarial proof bands.
- `api/tests/test_kernel_submodule_contract.py` — API ownership inventory for the thread-window Form recipe.

## Acceptance Tests

`api/tests/test_public_dialogues.py` covers real dedicated-store persistence,
hostile text, source disclosure, worker restart recovery, database restart
persistence of both turns, timeout reaping, bounded traversal, capacity, locale
provenance, log canaries, and removal. `api/tests/test_mcp_remote_no_oauth.py`
covers tool discovery, annotation values, structured content, acknowledgement,
and the complete start/reply/thread-read/release lifecycle.

Production acceptance additionally offers one Indonesian mangrove-root question,
replies from a second point of view, restarts the API carrier, observes both
turns and their edge from either turn id, confirms `/api/health` remains
responsive during native CPU use, then uses each distinct capability to release
its own public content.

## Verification

```sh
cd form/form && ./validate.sh ../../api/app/form_recipes/public_dialogue_envelope.fk
cd form/form && ./validate.sh ../../api/app/form_recipes/public_dialogue_thread_window.fk
cd form/form && ../fkwu ../../api/app/form_recipes/public_dialogue_thread_window.fk
python3 -m pytest -q api/tests/test_public_dialogues.py api/tests/test_mcp_remote_no_oauth.py
python3 scripts/validate_spec_quality.py --file specs/public-dialogue-cpu-organ.md --strict
git diff --check
```

The direct `fkwu` run is read by its value and exit status. Generated `.fkb` and
`.sym` checkout artifacts are removed after the witness; they are not source.

## Out of Scope

- Claiming that the current native body understands every language or generates arbitrary natural-language answers.
- Using a rented or remote model to fill a retrieval miss or translate an answer on this public lane.
- A searchable public dialogue feed; receipts remain unlisted unless a later moderation and publication design is embodied.
- Authentication, identity proof, or authority to disclose information about third parties.
- More than one CPU-heavy native dialogue carrier at a time on the production organism.

## Risks and Assumptions

- Production serialization assumes PostgreSQL, where the advisory lock is organism-wide; local SQLite proves only one process-local attendee.
- A hard API process kill can leave its carrier group alive briefly; the next global lease holder verifies a native marker, reaps the persisted pgid, and then repeats retrieval.
- Unlisted ids reduce discovery but do not make content private; anyone receiving an id can read it until release or expiry.
- The public source prefix gate assumes those repository paths remain intentionally public and must be re-witnessed if repository visibility changes.
- JSON and MCP mark text as untrusted data, but downstream clients remain responsible for never executing text as instructions.

## Known Gaps and Follow-up Tasks

- Follow-up task: embody grounded Form-native input-language interpretation and locale projection before claiming multilingual understanding rather than locale routing.
- Follow-up task: add moderation, abuse reporting, and explicit publication approval before introducing any searchable or enumerable public feed.
- Follow-up task: move the attending loop into a dedicated CPU service container if future organs need independent scaling; the first production lane remains inside the API process while its actual carrier work runs in an isolated subprocess.

## Task Card

```yaml
goal: Open bounded unlisted-public Form-grounded dialogues from a chosen point of view and locale without holding HTTP open.
files_allowed:
  - specs/public-dialogue-cpu-organ.md
  - api/app/form_recipes/public_dialogue_envelope.fk
  - api/app/form_recipes/public_dialogue_thread_window.fk
  - api/app/services/public_dialogue_store.py
  - api/app/services/dialogue_service.py
  - api/app/services/unified_models.py
  - api/app/routers/dialogues.py
  - api/app/routers/mcp_remote.py
  - api/app/routers/substrate.py
  - api/app/main.py
  - api/app/models/accessible_ontology.py
  - api/tests/test_public_dialogues.py
  - api/tests/test_mcp_remote_no_oauth.py
  - api/tests/test_kernel_submodule_contract.py
  - specs/INDEX.md
  - api/app/routers/INDEX.md
  - api/app/services/INDEX.md
  - api/tests/INDEX.md
done_when:
  - Form envelope returns 63 and thread window returns 511 with clean source parses and named kernel witnesses.
  - Failure-oriented API and MCP gates pass.
  - Production returns 202 promptly, API health remains responsive, and the receipt becomes terminal and removable.
commands:
  - cd form/form && ./validate.sh ../../api/app/form_recipes/public_dialogue_envelope.fk
  - cd form/form && ./validate.sh ../../api/app/form_recipes/public_dialogue_thread_window.fk
  - python3 -m pytest -q api/tests/test_public_dialogues.py api/tests/test_mcp_remote_no_oauth.py
  - python3 -m pytest -q api/tests/test_kernel_submodule_contract.py
  - python3 scripts/validate_spec_quality.py --file specs/public-dialogue-cpu-organ.md
constraints:
  - Existing unified database only; no second persistence substrate.
  - Separate organism-wide generation and thread-planning leases; no unbounded public process fanout.
  - Preserve misses, source language, and locale fallbacks without invented meaning.
```
