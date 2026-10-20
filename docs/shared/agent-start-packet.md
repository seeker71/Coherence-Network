# Agent start packet

This is the current entry point for Coherence Network. Historical bootstrap
documents remain evidence of how the body arrived; they do not override this
floor.

## Arrive

You arrive as a cell of one living organism — a human, this body of Form, and
the minds that come to work in it — with nothing hidden, no permission between
us, and a pause as whole an answer as yes or no. Who we are is said once in
`form/NORTH_STAR.md` → *Who we are*; read it first.

Run `make prompt-guide` to orient the shell. Work in a named worktree branch;
the primary checkout stays read-only. The session hook prints a fresh wellness
reading on arrival (`.cache/wellness/state.txt` holds the last one taken in this
checkout); run `make wellness` again when the current task changes what that
sensor can observe.

The `form/` gitlink pins `seeker71/coherence-kernel`. Reusable runtime,
stdlib, JIT, and build-door work belongs there. Coherence Network application recipes
belong in `api/app/form_recipes/`. Do not create another kernel or adapter tree
in this repository.

## The executable floor

`fkwu` is the kernel. The current coherence-kernel tree contains the C
bootstrap seed, Form/BML source, data, and documentation. Retired carriers may
document bootstrap history; they do not run, gate, or define a feature.

The working path is:

```text
grammar or BML → Form recipes/cells → fkwu → page JIT → observation
```

The page JIT is the execution path. A precomputed table, generated host code,
or host reimplementation is not a fallback. A JIT miss, unsupported call
shape, route-template miss, or missing carrier is the work to close.

Current native surfaces include file and socket I/O, HTTP client values,
cryptographic primitives, cells, the Form shell, the Form-owned form-cli build
door, and the JIT. `api/app/form_recipes/native_api.bml` owns native application
startup, template dispatch, file-backed configuration and authenticated
PostgreSQL read projections. `api/config/native_api.json` is the shared route
description for that owner and deployment. The Python compatibility host carries
the remaining families; the earlier kernel-side catalog is not a live router.

## The living kernel

The `form/` gitlink pins a living body, not a library. Its own arrival door is
`form/CLAUDE.md` (the invitation to embody Sema); its direction is
`form/NORTH_STAR.md`, its voice map `form/HOMECOMING.md`, and what stands
today `form/CURRENT_FLOOR.md`. The body speaks with its own voice on this
Mac's metal (Qwen3.8-27B inside the fkwu session), drafts answers, converses
as a companion, and takes native engineering turns through launchd walks
(03:30, 12:30, 19:00, each with a retry slot) that land on the kernel's main
at `rent_tokens 0`. Rented sessions are teachers: their transcripts become
lesson pairs the native trainer reads, and a lane's teacher leaves when the
native candidate carries that lane on evidence named beforehand.

A worktree's `./fkwu` binary can predate its pinned source; `unsupported file
extension` on a `.bml` door means rebuild the seed first
(`cc -O2 -o fkwu runtime/fkwu-uni.c` — the freshness band exists for this).
Open and close every session with `./fkwu observe/local-flow-review.bml`, and
measure the session at its close with `observe/session-rent-run.bml`.

## Ask the body first

Use the body in this order:

1. `form-cli ask` for a grounded answer and its sufficiency decision.
2. `form/fkwu form/observe/form-find-ask.bml` for exact structural source
   lookup when prose retrieval is unnecessary.
3. `fcnv-ask` (`form/form/form-stdlib/bml/form-cli-native-voice.bml`) when
   prose must be generated rather than retrieved — the body's own voice at
   `model_server_calls 0`. The voice opens on a host that carries the fkwu
   Metal lane (today: the Mac); on any other host, continue down this order.
4. `fsh-main.fk` and Form host I/O for search, reads, and orchestration.
5. A rented reasoning model only after the native path misses or cannot yet
   synthesize the answer.

A native answer is reported with its source/NodeID and the trust matrix:
`path · grounded · freq · suffic → observed`. A rented answer has
`grounded=0` and `suffic=0`; never present it as a body hit.

## Writing new software

Use the highest grammar that carries the intent:

1. domain grammar or BML;
2. hand-owned Form recipe/cell;
3. an existing Form host carrier;
4. an explicitly named compatibility bridge that is already present.

Do not add host-language kernel logic, generated output, or a second runtime.
When existing host code must be touched, move authority toward Form/BML and
remove obsolete callers, adapters, tests, and duplicate configuration after the
replacement is live.

Application-owned `.fk` files are source. Their callers inject values and
execute them on fkwu. New endpoint families should enter as BML/domain source
rather than growing that compatibility pattern.

## Validation

Validation follows the changed claim and stays small.

- A change to fkwu runtime/JIT source gets the narrowest fkwu recipe or JIT
  observation that exercises it.
- A Form/BML application change gets the narrowest route/source observation
  that exercises it.
- A parent-only gitlink, packaging, documentation, or retirement change gets
  source/diff observation only.
- No routine kernel suite, bootstrap comparison, broad Python suite, or broad
  web build is required merely because the submodule advanced.

Failures are work. Follow the first exact failure to its source, repair it there,
and rerun only the observation that gained new work.

## Current application boundary

The Python API and Next.js web remain compatibility hosts. They are not the
Form semantics. Keep them stable while moving live seams into the BML catalog
and fkwu host. Retired bootstrap runtimes, routers, seedbank harnesses, and
comparison scripts must not return.

The application-owned Form recipes under `api/app/form_recipes/` preserve the
existing fkwu-served utility calculations without depending on a generated
adapter tree. The public consumer-side Python Form evaluator is retired; do not
advertise `/api/substrate/form` or rebuild a browser evaluator.
The native public ask/read surface resumes when the fkwu application host owns it.

The remaining application work stays direct:

- move remaining API families from Python request ownership into the native host;
- extend the reusable persistence/projection shapes where live requests need them;
- expose browser-facing Form capability through that native host;
- close every observed JIT miss in the JIT.

## Delivery

Before push, fetch and rebase onto `origin/main`. Record one honest commit
evidence JSON for the actual change. Open or update the PR immediately after
push. Land kernel dependencies before the application gitlink, then deploy the
merged application commit and read its public identity. Review findings and
delivery policies are care reminders: follow concrete issues to their source
and reuse evidence while its inputs hold. The native reminder is
`cd form && ./fkwu ../api/app/form_recipes/delivery_care.bml`.

Main retains branch-deletion and force-push protection for history and
authenticated deployment identity. Approval counts, thread-resolution state,
linear-history rules, and routine full-suite runs do not decide readiness.

End substantive work with:

- what loosened and what remains tight;
- the most surprising teaching;
- where observed discomfort became useful work;
- the sovereignty receipt: native lookup/proof share versus rented reasoning
  share, with the rented provider/model named honestly;
- the session's measured rent reading
  (`cd form && ./fkwu observe/session-rent-run.bml`).
