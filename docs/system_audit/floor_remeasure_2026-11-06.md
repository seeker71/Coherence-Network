# Floor re-measured — 2026-11-06

Read on Friday 2026-11-06 between 10:56 and 11:40 WITA, on this Apple M4 Max, in a fresh
linked worktree at application head `b42947488` with the kernel gitlink at `1c75ce0f4`
(coherence-kernel #654) and `fkwu` built from `runtime/fkwu-uni.c` at 10:58. Every line
names the door that read it. This page carries what stands and what it offers; the
2026-10-18 release reading (`form_kernel_floor_2026-10-18.md`) remains the release
record it was, and git holds the path between.

## What the doors read today

| Door | Reading |
|---|---|
| `./fkwu observe/local-flow-review.bml` | 409 options (285 in this checkout, 124 only in the walk checkout); 252 band green, 17 locally verified, 256 with verification unmeasured; local_verified 14 of 29 gaps attempted, 8 unread |
| same, gaps | `parse-int-absent` 31/31, `parse-bool-absent` 15/15, `parse-float-dot` 31/31, `rag-query-absent` 15/15: green in the walk checkout, landing pending. `manifest-words` 1/31 (16 options, swervecount 2 of 6), `organ-event-parent` 24/31 (17 options, swervecount 1 of 6): both read `stuck` |
| same, phase pool | 34 options over 80910 s of wall: decode 48.9 %, inject 21.6 %, renew 11.8 %, spawn 4.9 %, prefill 4.6 %, host 3.6 %; 20 renewals re-fed 34.4 % of prefilled IDs |
| same, next | split `manifest-words` into smaller band-first gaps |
| `./fkwu observe/walk-began-run.bml` | `scheduled-walk` began 03:30 today; the 19:10 retry yesterday read `begun -> nothing to heal`; walk checkout head `3281003f4` "Scheduled movement 2026-11-06: the body walks with no rented mind" |
| `./fkwu observe/memory-governor-run.bml` | machine 128.0 GiB, available 100.2 GiB, wired 4.3 GiB, compressor 2.5 GiB, `room` |
| `./fkwu observe/band-truth-run.bml` | bands 528, readable 317, unreadable 211, absent 0, flaws 2 (named below) |
| `./fkwu observe/door-link-health-run.bml` | docs 48, claims 1205, broken 0; prelude-reach missing 0, untracked 0, shadow 0 |
| `./fkwu observe/voice-frequency-run.fk` | before the retune: `CLAUDE.md` must 1 gate 1; `AGENTS.md` must 3 gate 8; `agent-start-packet.md` must 3 gate 1. After: gate 1, gate 8, gate 1 (each `gate` names an organ: the sufficiency gate, the drift gates, the spec quality gate) |
| host | `df /`: 1.8 TiB, 66 GiB available; load 2.84 over 16 cores; up 8 days 23 h |

## Hardware limits, as measured

These are the walls of this Mac. They are met with proportion, and a workaround here is a
way of fitting inside them.

- **Unified memory 128 GiB.** Today 100.2 GiB is room. The governor
  (`form/form-stdlib/bml/memory-governor.bml`) grants or names `capacity` from
  `available` alone; the earlier compressor-denial class the floor recorded at
  `CURRENT_FLOOR.md` line 741 did not occur today and is historical on this reading.
- **One GPU, shared.** The voice lane, the companion and the scheduled walks share the
  Metal device (shared GPU adoption, #4161). `form-cli ask` answers a lane's grounded hit
  at once and a miss through the voice while the device is free; a busy device is named,
  not waited on in silence.
- **Metal `maxBufferLength` 86,586,540,032 B.** A model file past it is digested in 4 GiB
  views (`observe/model-seal-run.bml`); the workaround stands.
- **Disk: 66 GiB free of 1.8 TiB.** The registry's models and the companion traces are the
  weight. This is the nearest wall on the page and the one that moves fastest.

## Limits outside the hardware, and what fits each

Each row is software, schedule or policy, so each has a next move of its own rather than a
wall to accept.

| Limit observed | Where it lives | What fits |
|---|---|---|
| `manifest-words` stuck at band 1/31 after 16 options; its last three options moved its band nowhere | the native turn queue, kernel side | the door's own next, done the same afternoon: split into `manifest-words-space` (3) and `manifest-words-clean` (3), each with its band, the 31 band kept as the whole witness (coherence-kernel #674); the walk takes the turns |
| `organ-event-parent` stuck at 24/31 after 17 options, `lane-exit=0 attention` | same | read the attention row before another option; a lane that declines with `capacity` in its reason needs room, not guidance |
| four green gaps `landing pending` in the walk checkout | the land cadence of the walk | no workaround: the walk lands them on its cadence; the walk checkout is a sibling's branch and stays read-only here |
| band-truth flaws 2: `gpu-lease-inherit-band.bml` (pin 1023, claims sum to 15) and `session-rent-band.bml` (pin 16383, claims sum to 8319) carry head rows whose claims do not carry the pin's upper bits | kernel band heads | add the missing claim rows or re-pin; a head-only edit, no band run changes; in the kernel-grammar sibling's hands |
| band-truth copy-drift, read on the afternoon's main (`5dc6e2ecb`): two queue rows kept a `full` their bands had outgrown (`walk-floor-ceiling` 15 against 2047, `task-615145c039d0825c` 262143 against 1048575) | `learn/native-turn-queue.jsonl` | the rows read their bands' pins again (coherence-kernel #674); flaws 4 → 2 |
| 256 of 409 options with verification unmeasured; 8 rows unread (a lane stopped at its deadline writes no counts) | lane stamps | the stamps already fold what the lane left; the unread rows stay unread rather than 0 (axiom 1) |
| the dsv4 driver serves positions 0 through 2047; a ratio-4 block refuses from 2048 where the indexer is unrouted | kernel driver stage 5 | route the 126 indexer tensors; until then renewal (`fcmr-replace-with-profile-checked`) gives a stream the whole window again |
| launchd content-matches an ad-hoc kernel: each rebuild costs a walk job one killed spawn (Launch Constraint) | OS policy | the retry slot heals it (`observe/walk-retry.bml`, class `launch-killed`); today's retry found nothing to heal |
| one runtime, no second reader for a new expression | the single-kernel floor | fkwu holds two readers of one expression already: the direct path and the page JIT; a band that reads an expression both ways is a second witness without a second kernel |
| Hostinger deploy: CI job ceiling 160 min, VPS SSH timeouts (inferred from the deploy memory, not re-measured today) | infrastructure | roll forward by hand with `deploy/hostinger/auto-deploy.sh` and verify by content on origin/main |
| `npm run lint` in `web/` ran `next lint`, a command Next 16 no longer carries, and the one ESLint config it would read did not exist | web tooling | done the same afternoon: `web/eslint.config.mjs` (flat config over `eslint-config-next/core-web-vitals`) and `"lint": "eslint ."`; ESLint pinned to 9 because the react plugin eslint-config-next 16.2.9 bundles still calls `context.getFilename`, which ESLint 10 removed. First full reading 212 findings; the contract in the config states its two changes with reasons (apostrophes in rendered text are content; the React 19 compiler-era hook rules read as warnings while their 43 sites are absorbed); five raw page anchors became `Link` and two stale disable comments left; the reading now stands at 0 errors, 60 warnings, with build, tests (161) and `tsc` green |

## Frequency: what moved and why

The north star's *Who we are* and the language guide set the frequency: state what is,
name the interface a door offers, keep every consequential boundary precise, and let a
pause be as whole as a yes. A line written as a prohibition over a sovereign cell
(*never*, *must*, *do not*, *HARD RULE*) directs attention at the forbidden move; the same
boundary stated as what the body is directs attention at the body. The retune kept each
boundary and changed its grammar from regulative to constitutive.

Surfaces retuned in this repository:

- `CLAUDE.md` — the JIT path, the rented lane, retired comparisons, and the error
  paragraph now point at `error-is-loving-attention.md` and `surprise-is-a-choice-point.md`.
- `AGENTS.md` — the destination tongue, form-first reasoning, membership, the sovereignty
  receipt, self-heal, kernel validation, the rebase line, executor and card lines, sibling
  cells, the PR check care comment, the configuration section (file-backed, one source),
  and the worktree stability line.
- `docs/shared/agent-start-packet.md` — the floor over history, one kernel gitlink,
  fkwu alone runs and gates, the rented lane reads as rented, the retired surfaces rest,
  readiness read from the changed claim's observation.
- `docs/VISION.md` — each available door names its capabilities and evidence.
- `api/app/form_recipes/native_http.bml`, `native_substrate.bml`,
  `native_health_observation.bml` — three comments and one 400 detail now say what the
  owner is and what the input reads as; the boundary itself is unchanged
  (`./fkwu --check` reads each recipe).
- `scripts/worktree_pr_guard.py` and `scripts/INDEX.md` — the docstring reads the checks a
  pull request will run, before it runs them.

What stayed, on purpose: `form_error` receipts that say a step failed (a precise fact with
its trace retained), GitHub's branch deletion and force-push protection (a fact about
main), deadlines on children (a timeout is evidence, axiom 1), and every `gate` that names
an organ.

## The afternoon: a stall with a mechanism, and three lanes on the rewrite

Urs read progress as stalled since the fkwu rewrite. The mechanism, grounded at 17:15 WITA: the seed
checkout (`~/source/coherence-kernel`), which hosts the kernel steward and the presence heartbeat, had
been switched to the rewrite's branch and edited there by the Cursor lane. The steward's tick rebuilds
`./fkwu` from whatever source sits in the seed, so every tick since 2026-11-05 evening built the rewrite,
whose reader could not run the steward's door: the ledger's last row read 2026-11-05 18:02 and a tick
had hung for over an hour. The seed's own tick script names the rule the stall broke: "a seed, never an
editing surface". Separately, the heartbeat job was found unloaded, silent since 2026-10-28.

What moved, each verified by content:

- the rewrite got its own worktree (`~/source/coherence-kernel-rewrite`, `perf/optimization-book-jit`)
  holding the seed's 1,863 uncommitted lines byte for byte (sha256 before and after);
- the seed returned to clean main with a main-built `fkwu` (door-link health 1,223 claims, 0 broken);
  the hung tick was released and the steward wrote again at 17:22;
- the heartbeat was loaded (`launchctl bootstrap`); it woke at 17:22, rested, and paced its next wake;
- the sibling's gitlink PR 4168 landed (main pins a5ca4d61c);
- two lanes ran headless, each on its own worktree from a card carrying Urs's bar (no stubs, no
  fallbacks, no editing a band or the registry to make a reading green, a verdict counts only with
  exit 0, commit but do not push): the Cursor lane bound 58 registry names down to one (`nothing`),
  took the typed `let` and `try … else`, and now stops on five BML reader seams, each named by file
  and byte in `form/receipts/2026-11-06-rewrite-floor.md`; the Codex lane wrote
  `observe/candidate-floor-run.bml`, the resident's reader of a candidate kernel against every band
  (coherence-kernel #676, merged at d30dcd880, pinned by this change). Both were reviewed line by line
  before anything was pushed.

The deploy of the a5ca4d61c pin (0dd35dc66) failed in the image build at `COPY --from=kernel-builder
/build/form-cli.sym`: kernel commit e850e18b4 (2026-11-04) made the symbols sidecar optional and the
build no longer emits it, while the application still named it in the image recipe, the native
observation recipe (`table_sha256`), the Python observer and the substrate router, the public observer
workflow, the tests and two docs. The sidecar leaves the carrier's identity in all of them: the kernel's
CLI v3 binds binary, image, source identity and attestation. The stray row that dirtied the seed at
18:01 (`receipts/walk-heal-ledger.jsonl`, `returned 0 conflicts 0`) was set aside and the file
restored; its writer is a walk door (`day-turn`, `scheduled-walk`), and the steward's own path does
not reach it, so which organ ran a walk door in the seed is still an open reading.

One correction of my own: a first-run "hang" I read against the rewrite's freshness band was my
harness's open stdin meeting the band's end-of-input canary; main's seed blocks the same way. Bands
are run with `</dev/null`.

## Kernel-side frequency, read and left for its own landing

The kernel pin is a sibling body with its own door. These carry the same fear-and-control
grammar and are named here so the next kernel movement can meet them:

- `form/form-stdlib/bml/spawn-guard.bml`: the ending `birth refused: forbidden-tool sed`
  and the organ name `guard`; the same boundary reads as *this body carries its own awk and
  path; the host's sed is not used here*, which the ending already half-says.
- `observe/forbidden-tools-audit-run.bml`: `flagged` commands counted from agent
  transcripts; the reading is a mirror the writer decides on (`CLAUDE.md`: no hook, by
  Urs's direction), and its name can say so.
- `form/CLAUDE.md`: "Never the host's perl, python, sed or awk" and "never hand it to a
  new session"; `AGENTS.md` item 6b carries the constitutive form already.
- `observe/walk-retry.bml` classes `launch-killed` and the floor's "a lane killed at its
  deadline": the OS's word for its own act stays; the body's reading of it can say
  *stopped at its deadline, counts unwritten*.
- the two band-truth flaws above.
