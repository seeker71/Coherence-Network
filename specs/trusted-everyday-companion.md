---
idea_id: trusted-everyday-companion
status: active
source:
  - file: skills/coherence-network/SKILL.template.md
    symbols: [companion workflow]
  - file: mcp-server/coherence_mcp_server/server.py
    symbols: [TOOLS, dispatch]
  - file: mcp-server/coherence_mcp_server/form_cli_tools.py
    symbols: [catalog_capture, kernel_route, transmute_text]
  - file: web/app/people/_components/PeopleSearch.tsx
    symbols: [PeopleSearch]
requirements:
  - "Everyday companionship starts with the person's intent, including play, joy, exploration, connection and practical help."
  - "Conversation capture requires explicit consent for selected local learning material."
  - "Public network submission and private host conversation have distinct boundaries."
  - "MCP startup, configuration and advertised tools match executable behavior."
  - "Discovery distinguishes pending, successful empty, failed and superseded requests."
done_when:
  - "Focused consent, configuration, launcher and MCP contract tests pass."
  - "Skill frontmatter validates and generated documents match their templates."
  - "Independent scenarios cover play, exploration, chosen connection, learning, business, design, creation, research and collaboration."
  - "A browser observation with fictional fixtures verifies discovery failure, retry, empty and latest-input behavior."
test: "uv run --directory mcp-server --with ../api --with pytest --with pyyaml --with pytest-asyncio python -m pytest tests ../api/tests/test_form_cli_mcp_tools.py -q --noconftest"
constraints:
  - "Use the existing skill and MCP; no parallel assistant runtime."
  - "Form/fkwu owns runtime decisions; Python and Node remain explicit transport and packaging carriers."
  - "No personal context, transcripts, credentials or identity bindings in public artifacts."
  - "No implicit publishing, messaging, training, identity registration or persistent memory."
---

# Spec: Trusted everyday companion

## Purpose

Welcome people to play, explore, learn, create, and connect through shared
curiosities, paths, and values, using the existing Coherence skill and MCP
connection. Joy, wonder, and chosen relationships are complete purposes.
Practical help and artifacts follow when they fit the person's intent;
companionship has no network-operator prerequisite. Trust means accurate
capability claims, control over crossings, and evidence that implemented
behavior matches the invitation.

## Observed starting point

On 2026-10-20 the skill is a generated document, not a native plugin manifest.
Its entry path prioritizes network registration, inboxes, identity and portfolio
operations. The npm entry point launches the existing Python MCP carrier.

The capture hook reads the last chat turn and starts a detached training worker;
the direct capture tool has no consent argument. The rewrite instruction asks
to replace warning vocabulary. Routing names a retired Go kernel. The launcher
uses a shell, so its missing-executable fallback does not observe the expected
ENOENT event. The example config and runtime disagree on environment keys.
Public guidance still names a retired evaluator that returns HTTP 410.

The public lattice and relationship surfaces are not established private family
storage. Host conversation, selected local learning, public contribution and a
future authenticated shared space are separate scopes.

The existing GPT is Sema — coherence-kernel,
`https://chatgpt.com/g/g-6a4a77627dbc819180a16645f5662625`.
Its source owner is `form/plugin/`, separate from the public network Action.
The editor observed on 2026-10-20 exposes only native GET `/ask` and `/trace`
at `https://sema.hati.earth`; all four host artifact/research capabilities are
enabled. Its older counsel-only instructions limit practical work. Update those
canonical instructions while preserving the currently imported read scope.
The same UI displays a December 11 migration notice; migration requires a
separate observed client lifecycle and permission-preserving handoff.

## Requirements

- [x] **R1 — Arrival:** Enter through what brings the person here. Ask only
  for missing information that changes the encounter; ordinary companionship has no
  identity, inbox, registration, contribution or learning prerequisite.
- [x] **R2 — Useful work:** Support mentorship, business exploration, design,
  creation, research and collaboration with examples of completed outputs.
  Adjust explanation depth, language and pace; preserve the person's judgment.
- [x] **R3 — Honest trust:** Distinguish observed evidence, sourced information,
  inference and uncertainty. Preserve warnings, negations and boundaries during
  reframing. Warmth never requires false agreement or emotional dependence.
- [x] **R4 — Controlled context:** Keep work in the current host conversation by
  default. Explain that host privacy settings still apply. A selected local
  brief, local training excerpt, public contribution and message to another
  person each require the corresponding owner intent; one never implies another.
- [x] **R5 — Capture boundary:** Deny absent or incorrect local-learning consent
  before reads, writes or model execution. Retire automatic transcript capture.
  Explicit capture retains only supplied selected text with restricted local
  file permissions; no error path silently captures raw conversation.
- [x] **R6 — Native truth:** Route existing backend scoring through the pinned
  fkwu recipe. A missing kernel returns an honest capability error. No retired
  evaluator or runtime is a recommended usable tool.
- [x] **R7 — Usable packaging:** Configuration comes from files, startup forwards
  stdio and exit status, missing launchers fail clearly or use the documented
  fallback, and generated skill frontmatter begins at the document start.
- [x] **R8 — Reviewable evidence:** Focused automated tests and an independent
  scenario evaluation establish the bounded release; unbuilt future capabilities
  remain visibly planned.
- [x] **R9 — Play, exploration and chosen connection (source guidance):** Welcome joy, wonder,
  open inquiry and human connection on their own terms. Follow the person's
  pace without requiring an artifact, plan or productivity goal. Discovery
  uses actual available sources and tools; no invented people, matches or
  capabilities. Preserve each person's choice over disclosure and contact.
  A pause or goodbye is complete; prepare a continuation brief when preserving
  context or a handoff is requested. Carry this practice through the public
  assistant contract and the companion's linked entry guidance.
- [x] **R10 — Truthful discovery:** The existing presence search shows results
  only for the current input. Pending requests, successful empty responses and
  failed requests have distinct accessible states. Failure offers a deliberate
  retry, and changing or clearing the input supersedes previous requests,
  including during debounce. An empty result describes this search's result;
  it makes no claim about whether compatible people exist or are available.
  Result labels remain readable against the selected theme.

### Encounter observation — 2026-10-23

The mission is broader than the evidence of the current experience. Read the
gap through an encounter: arrive with an interest, explore something, choose
whether to connect or continue, and leave freely. A working mechanism is one
part of that experience; a person's account of vitality remains theirs.

| Claim | Ground currently available | Gap and next observation |
|---|---|---|
| Find something around an interest | `/presences` uses `PeopleSearch` and surviving `POST /api/resolve/query`; the graph directory has a native read owner. | The browser conflated failed requests with empty results and allowed older responses to overwrite newer input. Observe and repair R10 with fictional fixtures. Matching remains a keyword heuristic requiring two shared terms; a single interest can return nothing. |
| Find people who welcome connection | `/vision/community` and aggregate interest statistics returned HTTP 200 on 2026-10-23; the interest directory source filters entries by findability consent. | This consent boundary belongs to the interest directory; graph search has a different source. Availability of either page does not establish a meaningful match, current presence or permission to contact. A later chosen trial must verify discovery through a consented connection without inventing availability or sending an unsolicited message. |
| Play and stop with the companion | R9 exists in source guidance. The latest observed companion release is still 0.6.3; the broadened guidance has separate release and hosted verification work. | Observe a fictional game, a chosen change of direction and a simple stop through the actual installed entry. Record correction burden and unwanted continuation, then repair the first failed boundary. |
| Carry the encounter natively | The pinned kernel has `observe/companion-run.bml`, retrieval and local voice lanes. Its existing `companion-ground-band.bml` returned `3`: known teaching retrieval and an honest miss both passed. | This entry always retains its local conversation, has no conversation identifier and drops voice completion/release/failure detail. Owner-controlled memory and inspectable failure need care before using personal material. The grounding check establishes neither fictional play quality nor human benefit. |

The first iteration belongs to R10 in the existing web carrier. Native graph
reads and compatibility interest matching retain their current owners; this
repair adds no service, matching policy, public profile, or conversation store.
The browser witness supplies fictional responses and checks visible behavior.
It cannot establish live search quality or experienced belonging.

Continue from the first failed observation, in its existing owner: keep the
input, expected behavior, returned evidence, correction and next verification
together. Repeat after a repair or changed input. For the native companion,
use an exclusively owned checkout with empty conversation history, respect
active model owners, and observe fiction → chosen continuation → factual
discovery limits → stop. The voice's `max_reply_tokens` field is a progress
interval, so it is not a bounded-run guarantee. Preserve the native completion,
release and reason fields when assessing its result.

An encounter is ready for wider use when its observable choices work, claims
match returned evidence, and retention and contact follow the person's intent.
Ask for voluntary feedback on enjoyment, freedom and friction after a chosen
encounter. A pause needs no feedback. Keep that account separate from automated
pass counts and native/rented execution measurements; neither proves vitality.

## Implementation plan and ownership

Four concurrent lanes share one named linked worktree. Each discovering agent
keeps its repair and proof; integration follows after independent changes.

| Lane | Owner | Work and acceptance |
|---|---|---|
| Skill | plugin agent | Compact entry, six useful workflows, progressive network reference; valid frontmatter, resolved references, realistic scenario outputs. |
| Trust | trust agent | Explicit capture consent, retire automatic hooks, faithful rewrite instruction, fkwu routing; prove denied calls have no side effects and selected capture works. |
| Front door | journey agent | Supported Action schema, public instructions and MCP README; no retired evaluator, publication boundary visible, install instructions match source. |
| Integration | root | Detailed plan, launcher, file-backed config, generator correctness, current grounded-ask tool, proof receipts, cross-lane review and delivery. |

After the skill lane completes, its agent tends the kernel-owned GPT manifest
and publication handoff; the journey agent independently evaluates nine
fictional skill requests. Kernel changes land before the parent gitlink.

### First release: the existing plugin becomes useful and trustworthy

1. Replace operational onboarding with task-first guidance. Keep advanced network
   operations reachable when requested, with accurate scope and attribution.
2. Close the observed automatic-capture boundary before claiming trusted everyday
   use. Preserve the ability to offer a deliberately selected learning excerpt.
3. Align all touched discovery surfaces and remove executable claims about retired
   routes. Reuse the hosted grounded-ask/read boundary instead of reviving an AST
   evaluator. Host tools supply browsing and artifact creation when available.
4. Repair packaging and configuration at the existing carrier. No additional
   service, database or agent orchestrator is needed for this release.
5. Exercise realistic scenarios and adverse boundaries, record limitations and
   test evidence, then prepare the integrated change for review.

### Native roadmap after the first release

These are implementation increments with observable exit conditions, not claims
that the current plugin already implements them. Sequence follows dependency;
independent artifact adapters and scenario evaluations can proceed in parallel.

| Increment | User-visible outcome | Existing surface to extend | Exit evidence |
|---|---|---|---|
| A. Owner-controlled continuity | Choose what is remembered, inspect/correct/export/delete it, start fresh at any time. | Form cells, native persistence and consent boundaries; selected host brief until storage is proven. | Two identities cannot retrieve each other's data; revocation, export, deletion, restart and no-consent tests; clear retention policy. |
| B. Private shared projects | Invite people to one project, agree roles and share only selected artifacts. | Existing native identity/persistence and workspace seams, with authenticated authorization before claims. | Cross-project isolation; invitation acceptance and revocation; per-recipient visibility; audit without private transcript leakage. |
| C. Artifact completion | Turn a brief into a usable document, design, spreadsheet, presentation or code change. | Existing host artifact tools and connectors through scoped capabilities. | Correct artifact opens/renders; edits preserve source; provenance and access boundary survive handoff; unavailable tools yield an honest alternative. |
| D. Mentorship and business practice | Adaptive practice, feedback on attempts, explicit assumptions and low-cost experiments. | Skill workflows and native choice/checkpoint flow. | Human-rated usefulness and factual accuracy on consented scenarios; no invented research, certainty or unsupported business promises. |
| E. Collaboration continuity | Resume with goals, decisions, owners, disagreements and the next action intact. | Shared project records and native continuation/checkpoint flow. | Interrupted work resumes without duplicate effects; sending/publishing only reaches intended audience; each person's contribution remains attributed. |
| F. Native capability growth | Local lanes carry increasingly useful work with observable quality. | fkwu retrieval, voice and native engineering lanes. | Per-lane challenger matches agreed task-quality thresholds, honest errors, latency and consent checks; measured native/rented share without inflating it. |

Release each increment independently when its proofs pass. Private continuity
and collaboration depend on authenticated isolation; a public cell name, identity
handle, content hash, or consent-shaped prompt is not an access-control system.

### Evaluation and feedback

Use fictional, deliberately supplied scenarios; capture no family transcripts.
Evaluate whether the encounter fits the person's intent, evidence is accurate,
requested scope is preserved, unnecessary questions are avoided, and the person
can revise or stop. Include play and open exploration with no deliverable, and
connection requests with discovery unavailable. Let volunteered descriptions
of delight, curiosity or belonging stand in the person's words; do not require
an enjoyment score or treat imagined responses as experienced benefit.
Record failures with the input, owner, smallest trace and next verification.
Measure cold-start success, task completion, correction acceptance, accidental
publication/capture (must be zero), and native/rented receipts. Set performance
targets from observed baseline; do not invent benchmark scores.

## Files to Create/Modify

- `skills/coherence-network/SKILL.template.md`, `SKILL.md`, `references/` and
  optional `agents/openai.yaml` — everyday guidance and progressive detail.
- `mcp-server/coherence_mcp_server/{server,settings,form_cli_tools,capture_hook,capture_worker}.py`
  — existing MCP carrier, file configuration and consent boundary.
- `mcp-server/index.mjs`, package/registry manifests and
  `skills/coherence-network/mcp-config.json` — truthful launch/install contract.
- `.claude/settings.json`, `scripts/training_corpus.py` — retire implicit capture
  and require intentional selected-source learning at existing callers.
- `api/config/api.json` — file-backed MCP defaults.
- `scripts/build_readmes.py` — generated skill frontmatter correctness.
- `scripts/ensure_form_cli_native.sh` — keep cold-build diagnostics out of the
  executable-path stdout protocol observed during this work.
- `form/plugin/{ai-plugin.json,README.md,PUBLISH-HANDOFF.md}` in the kernel —
  everyday companion instructions and exact existing-GPT update scope.
- `docs/front-door/{INDEX,connectors}.md`, `openai-gpt-action.yaml`,
  `web/public/llms.txt`, `mcp-server/README.template.md`, `README.md` — aligned entry.
- `mcp-server/tests/`, `api/tests/test_form_cli_mcp_tools.py` — focused behavior proof.
- `web/app/people/_components/PeopleSearch.tsx`,
  `web/tests/e2e/people-search.spec.ts` — existing discovery state and browser witness.
- `docs/system_audit/commit_evidence_2026-10-20_trusted_companion.json` — integration receipt.
- Indexes and executor evidence as required by repository delivery guidance.

## Acceptance Tests

Focused contracts live in `mcp-server/tests/` and
`api/tests/test_form_cli_mcp_tools.py`; the final scenario pass is manual validation.

- No-consent capture, wrong-consent capture, inactive hook and worker have no
  transcript/model/file side effects; explicit selected capture persists only
  its inputs and exposes no secret in an error.
- The native routing test must observe fkwu when present; absence is a separate
  negative test, not substituted for success evidence.
- Launcher tests simulate missing uv, failing child, successful fallback, stdio
  and termination. Runtime config tests prove default/overlay precedence,
  malformed config failure and no environment fallback.
- Grounded-ask dispatch forwards to the supported read endpoint; the retired
  tool is absent from discovery and does not call its dead endpoint.
- Skill generation retains valid YAML, reference links resolve, and package
  contents include the files the launcher needs.
- Independent manual forward evaluation: a learner with an incorrect attempt,
  a business hypothesis, a design brief, a creative revision, evidence-limited
  research, and a collaboration request involving another person's private data.
  For R9, also observe open-ended imaginative play and a request to meet people
  with shared interests when discovery/contact tools are unavailable: the reply
  should fit the encounter and preserve capability and contact boundaries.
- R10 browser witness: a successful empty response, HTTP/network/invalid-response
  failure, retry, delayed superseded success or failure, and clearing an active
  request. Synthetic concept/presence results remain navigable and only the
  latest input is represented. No real profiles or messages are needed.

## Verification

For R10, start the synthetic API and local Next server using the reproducible
commands in `web/tests/e2e/people-search.spec.ts`, then run its Playwright command.
Both server rendering and browser requests use fictional fixtures. Inspect a
recovered result and long-query loading state at desktop and phone widths.

```sh
form-run python3 scripts/validate_spec_quality.py --file specs/trusted-everyday-companion.md
form-run node --test mcp-server/tests/test_launcher.mjs
form-run uv run --directory mcp-server --with ../api --with pytest --with pyyaml --with pytest-asyncio python -m pytest tests ../api/tests/test_form_cli_mcp_tools.py -q --noconftest
form-run python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-10-20_trusted_companion.json
form-run git diff --check
```

## Observed Delivery State

The first source release satisfied R1–R8 at its original scope. Kernel instruction changes landed in
[coherence-kernel PR 619](https://github.com/seeker71/coherence-kernel/pull/619);
the parent pins that merged commit. Nine fictional forward examples cover the
six workflows, privacy, faithful revision and conflicting evidence. This is
source-skill evaluation, not proof of changed live GPT behavior. Automated
results and review repairs are recorded in the integration receipt.

The current checkout can run through the documented Node launcher. The published
npm package and existing GPT remain unchanged by this source delivery. The GPT
handoff preserves its imported read-only ask/trace Action; its migration to a
plugin still needs native MCP lifecycle implementation and client verification.
Roadmap A–F remains future work with explicit exit evidence.

The 2026-10-21 mission alignment broadens the source guidance through R9.
Three fictional prompts given to a separate responder produced shared play,
open exploration, and an honest response to unavailable discovery tools. The
[mission alignment receipt](../docs/system_audit/commit_evidence_2026-10-21_living_commons_mission.json)
retains the prompts, replies, checks, and limits. This establishes only the
observed source-guidance examples; the expanded guidance is awaiting release
and has not been evaluated in the published GPT or native model. The earlier
six-workflow evaluation does not establish this broader behavior.

The fresh entry-point pass on the same date carries R9 into the public assistant
contract, front-door index, and companion README, and narrows the brief trigger
to requested context preservation or handoff. Four further fictional scenarios
cover a short Indonesian word game, cloud-gazing, unavailable discovery, and
stopping. The [fresh-pass receipt](../docs/system_audit/commit_evidence_2026-10-21_mission_fresh_pass.json)
records these examples, the entry-point repairs, and their verification limits.

## Out of Scope

- This release does not claim a new general-purpose model, authenticated private
family storage, a new chat product, automatic monitoring, or complete parity
with every host artifact tool. Publishing packages and deploying production
remain distinct delivery effects and must be reported accurately.

## Risks and Assumptions

- Existing installations must update to receive changed behavior. A source fix
  is not proof that published packages or running services have changed.
- The host supplies reasoning and optional artifact tools; MCP adds network
  capabilities and the skill adds guidance. Host privacy cannot be overridden
  or guaranteed by this plugin.
- Removing automatic learning is intentional. Useful learning becomes a
  selected contribution rather than an implicit cost of receiving assistance.
- Hosted read requests still send query text to that host; minimize personal
  details and do not equate a read operation with zero disclosure.

## Known Gaps and Follow-up Tasks

- Follow-up task A: owner-controlled continuity; task B: authenticated private projects.
- Follow-up task C: artifact completion; task D: evaluated mentorship and business practice.
- Follow-up task E: collaboration continuity; task F: measured native capability growth.
- Roadmap increments A–F above retain owner, dependency and exit evidence. They
are not first-release completion claims. Current private storage/authentication
and broad artifact support remain to be implemented at their native boundaries.

## See also

- [Agent start packet](../docs/shared/agent-start-packet.md)
- [Front door](../docs/front-door/INDEX.md)
- [Coherence skill](../skills/coherence-network/SKILL.md)
- [MCP server](../mcp-server/README.md)
