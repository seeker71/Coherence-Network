---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/form_recipes/public_dialogue_envelope.fk
    symbols: [dialogue-envelope, dialogue-offered]
  - file: api/app/services/public_dialogue_store.py
    symbols: [PublicDialogueRecord, create_dialogue, claim_next_dialogue, tombstone_dialogue]
  - file: api/app/services/dialogue_service.py
    symbols: [submit_dialogue, get_dialogue, process_dialogue_once, release_dialogue]
  - file: api/app/routers/dialogues.py
    symbols: [start_dialogue, read_dialogue, release_dialogue]
  - file: api/app/routers/mcp_remote.py
    symbols: [START_DIALOGUE_TOOL, GET_DIALOGUE_TOOL, REMOVE_DIALOGUE_TOOL]
  - file: api/tests/test_public_dialogues.py
    symbols: [test_dialogue_lifecycle_keeps_source_and_projection_digests, test_rented_miss_is_admitted_only_on_dialogue_lane]
requirements:
  - "A caller can offer a question with a point of view, BCP-47 locale, optional parent turn, bounded channel timeout, and versioned acknowledgement that the turn is unlisted-public."
  - "HTTP returns a persistent dialogue cell immediately; one organism-wide CPU lease realizes queued turns outside the request path."
  - "Only an allowlisted public source path can produce an answer; every other result becomes an attributed miss or controlled failure without publishing carrier output."
  - "The no-auth MCP endpoint exposes start, get, and removal-capability tools with tested read, write, destructive, idempotent, and open-world annotations."
done_when:
  - "The Form envelope returns 63 on Go, Rust, and TypeScript sibling kernels and 63 on the direct fkwu witness, with the source preflight clean."
  - "Failure-oriented tests prove disclosure acknowledgement, data isolation, hostile-input containment, queue and timeout bounds, process-group reaping, interrupted-turn recovery, locale provenance, public-source gating, log hygiene, and removal."
  - "MCP tests prove a connector can start, read, and release a dialogue and receives untrusted structured content."
  - "A production question returns 202 promptly, remains observable by its unguessable id, and reaches a terminal answered, miss, or failed receipt while API health stays responsive."
test: "cd form/form && ./validate.sh ../../api/app/form_recipes/public_dialogue_envelope.fk && cd ../.. && python3 -m pytest -q api/tests/test_public_dialogues.py api/tests/test_mcp_remote_no_oauth.py"
constraints:
  - "Form owns the six-field dialogue envelope; Python carries HTTP, bounded process attendance, and the dedicated dialogue table in the existing unified database."
  - "One PostgreSQL advisory lease spans all API processes and replicas; each native carrier is an isolated process group whose pid is persisted, killed on timeout, and reaped before interrupted work resumes."
  - "A rented escalation is admitted only as an empty dialogue-lane miss; it never becomes an answer or changes the ordinary grounded-ask lane."
  - "Question text is staged only as data, never placed in a shell command or Form source, and never appears in operational logs or failure receipts."
  - "Public visibility is unlisted-by-id, expires after seven days, and can be released earlier into a content-free tombstone with the creation-time removal capability."
---

# Public Dialogue CPU Organ — one observable Form-grounded turn at a time

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
literal acknowledgement `public_disclosure_ack: public-unlisted-v1`. The
acknowledgement means anyone given the unguessable id can read the question and
receipt. It is a disclosure statement, not proof of identity or third-party
consent. Missing or different acknowledgement values persist no row.

The response is `202` with a dialogue id, poll URL, seven-day expiry, and a
removal token shown once. `GET /api/dialogues/{id}` observes `pending`, `running`,
`answered`, `miss`, `failed`, or `tombstoned`. There is deliberately no public
list endpoint: an unlisted receipt becomes visible to another person only when
someone shares its id.

`DELETE /api/dialogues/{id}` with the removal token releases question, point of
view, and result content. The durable row becomes a content-free tombstone so
the removal itself remains observable. Non-running rows are automatically
tombstoned after seven days. A running row first reaches a controlled terminal
boundary and is then durably tombstoned, so process ownership never disappears
mid-execution. At the expiry boundary, a public read already receives a
content-free tombstone view; the durable running row retains its worker and
process-group ownership until that carrier returns and commits the tombstone.

A follow-up points at an available parent dialogue id. It stores only an edge;
it does not copy conversation state or attach to internal/private task ids.

## Form shape

`api/app/form_recipes/public_dialogue_envelope.fk` makes six neutral fields one
cell: locale, point of view, question, disclosure acknowledgement, parent, and
chosen timeout. `dialogue-offered` accepts only the disclosed, present shape.
Its band value is `63`, including parent-turn continuity.

## CPU and restart shape

Dialogue persistence uses a dedicated `public_dialogues` table registered on
the existing unified database. It neither lists nor claims `agent_tasks`.

Each API process may host one lightweight attending thread, but a session-level
PostgreSQL advisory lock permits only one of those threads across all processes
and deployment replicas to claim native work. SQLite/local development uses a
process lock and does not make a cross-host claim.

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
- `get_dialogue`: idempotent read of an unlisted receipt by id;
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
- [x] Publish answers only from explicit public source paths and preserve a rented result only as an empty lane-specific miss.
- [x] Accept canonical BCP-47 locale tags while distinguishing locale routing from unproven input-language understanding and projection.
- [x] Keep receipts unlisted, bounded by capacity and time, automatically expiring, and removable into content-free tombstones.
- [x] Pace HTTP and MCP atomically across production replicas without retaining raw peer addresses.
- [x] Expose start, get, and remove through HTTP and no-auth MCP with server-side gates and accurate annotations.

## Files to Create/Modify

- `api/app/form_recipes/public_dialogue_envelope.fk` — Form-neutral six-field envelope.
- `api/app/services/public_dialogue_store.py` — dedicated persistent cell and atomic claim/terminal transitions.
- `api/app/services/dialogue_service.py` — global worker lease, public-source gate, recovery, and receipts.
- `api/app/routers/dialogues.py` — bounded HTTP start, observation, and release membrane.
- `api/app/routers/mcp_remote.py` — connector-visible start/get/remove tools.
- `api/app/routers/substrate.py` — carrier start witness plus shared process-group reaper.
- `api/tests/test_public_dialogues.py` and `api/tests/test_mcp_remote_no_oauth.py` — adversarial proof bands.

## Acceptance Tests

`api/tests/test_public_dialogues.py` covers real dedicated-store persistence,
hostile text, source disclosure, restart recovery, timeout reaping, capacity,
locale provenance, log canaries, and removal. `api/tests/test_mcp_remote_no_oauth.py`
covers tool discovery, annotation values, structured content, acknowledgement,
and the complete start/read/release lifecycle.

Production acceptance additionally offers one Indonesian mangrove-root question,
observes `202` before native work completes, polls the receipt to a terminal
state, confirms `/api/health` remains responsive during native CPU use, then
uses the returned capability to release the public content.

## Verification

```sh
cd form/form && ./validate.sh ../../api/app/form_recipes/public_dialogue_envelope.fk
form/fkwu api/app/form_recipes/public_dialogue_envelope.fk
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
  - specs/INDEX.md
  - api/app/routers/INDEX.md
  - api/app/services/INDEX.md
  - api/tests/INDEX.md
done_when:
  - Form envelope returns 63 with clean preflight and named kernel witnesses.
  - Failure-oriented API and MCP gates pass.
  - Production returns 202 promptly, API health remains responsive, and the receipt becomes terminal and removable.
commands:
  - cd form/form && ./validate.sh ../../api/app/form_recipes/public_dialogue_envelope.fk
  - python3 -m pytest -q api/tests/test_public_dialogues.py api/tests/test_mcp_remote_no_oauth.py
  - python3 scripts/validate_spec_quality.py --file specs/public-dialogue-cpu-organ.md
constraints:
  - Existing unified database only; no second persistence substrate.
  - One organism-wide CPU lease; no unbounded public process fanout.
  - Preserve misses, source language, and locale fallbacks without invented meaning.
```
